#!/usr/bin/env python3
"""Industry map (P4): find an industry hidden in the lobbying free-text, then emit
an ENTITY-RESOLVED player list that plugs straight into the two money tools.

Requires: the built DuckDB (lda-corpus-loader) + lda-entity-resolver tables. Corpus
bindings — reference/corpus-profile.md: `freetext_surface`; `entity_tables`;
`canonical_spend_view`; `attribution_grain`. Vocabulary: industry_lexicon.json.

The problem. An industry like crypto can't be found by issue-code filtering: its
free-text scatters across 15+ ALI codes (FIN/BAN/TAX/SCI/CPI/CDT/AGR/...), only
~40% under FIN, and diversified filers (Robinhood, PayPal, Fidelity, Stripe,
banks) lobby on it without "crypto" in their name. So you can't map it by guessing
company names either. You map it by the VOCABULARY the filers use to describe what
they lobby on — the lobbying free-text (senate activity descriptions + House
specific_issues), unified in lobbying_freetext.

Two stages, discovery split from serving (see lda_freetext_discovery.py for discovery):
  build-tags : materialize lobbying_issue_mentions — a deterministic, cited serving
               table tagging lobbying_freetext with a facet's curated vocabulary
               (industry_lexicon.json), one row per (doc, tag, keyword) with the
               raw-record pointer preserved. This is the mirror of the loader's
               press_issue_mentions, on the lobbying side.
  map        : from lobbying_issue_mentions for a facet, resolve every filing's
               registrant + client through lda-entity-resolver (entities/
               entity_aliases) into a player list, and write a roster file the money
               tools consume unchanged:
                 lda_ld203_giving.py --names-file <roster>   (who they give to)
                 v_client_canonical_spend                (what they spend)

Usage:
  # once (or after the lexicon changes): build the serving table for all facets
  python lda_industry_map.py --build-tags
  # the map for a facet (default crypto); writes out/<facet>_roster.txt for the money tools
  python lda_industry_map.py crypto
  # prove recall: list players a name-LIKE '%crypto%' scan would MISS
  python lda_industry_map.py crypto --recall-check

    --db PATH        DuckDB (default db/lda_full.duckdb); needs lobbying_freetext
                     (lda-corpus-loader add_lobbying_freetext.py) + entities/
                     entity_aliases (lda-entity-resolver resolve_entities.py)
    --lexicon PATH   industry_lexicon.json (default: beside this script)
    --facet ID       facet id when not passed positionally (default crypto)
    --build-tags     (re)materialize lobbying_issue_mentions, then continue
    --min-docs N     player must appear in >= N crypto free-text docs (default 1)
    --top N          players / keywords / recipients shown (default 40)
    --out PATH       where to write the entity-resolved roster (default
                     out/<facet>_roster.txt — a gitignored, disposable repo-root
                     dir; never written into skills/). Pass a path to override.
    --no-roster      don't write a roster file (just print the map)
    --recall-check   only report players whose NAME contains no facet phrase
                     (the diversified filers name-matching misses)
    --data-root PATH printed into the show_record.py hint (default ../data/data)
    --json           machine-readable output

Discipline (same as the rest of lead-scanner):
  * Serving stays deterministic + cited. Findings cite the keyword->exact-word->
    record chain (lobbying_issue_mentions), never a model's judgment. FTS/keyness
    only DISCOVER candidate terms; a human adds them to industry_lexicon.json.
  * The player list is entity-resolved so it feeds the money tools unchanged; where
    the resolver split a company's name variants (cleanup C / P6), that is a known,
    documented limitation, not a silent gap.
  * "Crypto lobbying spend rose" is a dataset summary. The deliverable is NAMED
    players, each with sample record keys, whose spend (v_client_canonical_spend)
    and disclosed giving (lda_ld203_giving.py) are then pulled by the money tools.

Citeable aggregate form: queries/p4_industry_map.sql (P4a-P4e).
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Kept in exact sync with lda-entity-resolver/scripts/resolve_entities.py:norm_name
# (and lda_ld203_giving.py). A drift here silently under-matches entities.
LEGAL_SUFFIXES = {
    "LLC", "L L C", "INC", "INCORPORATED", "LTD", "LIMITED", "LLP", "L L P",
    "LP", "L P", "PLC", "CO", "CORP", "CORPORATION", "COMPANY", "PC", "PLLC",
    "SA", "S A", "AG", "GMBH", "NV", "N V", "BV", "B V", "PTY", "USA", "US",
}


def norm_name(raw):
    if not raw:
        return None
    s = raw.upper().strip()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
    words = s.split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words) or None


# --------------------------------------------------------------- keyword matcher
# Same longest-match-wins, whole-word, single-pass matcher as build_db.py's
# _build_issue_matcher (press_issue_mentions). Re-declared inline (not imported)
# to keep this skill self-contained — the lda_bill_lookup.py precedent. If build_db's
# matcher semantics change, mirror them here.

def build_matcher(facets):
    """One alternation regex over every facet's phrases + phrase->tag lookup.
    Longest phrases first so 'digital asset market structure' wins over
    'digital asset' at the same position."""
    kw_to_tag = {}
    for fac in facets:
        for kw in fac["phrases"]:
            canon = " ".join(kw.lower().split())
            if canon in kw_to_tag and kw_to_tag[canon] != fac["tag"]:
                raise ValueError(f"phrase {canon!r} maps to both "
                                 f"{kw_to_tag[canon]} and {fac['tag']}")
            kw_to_tag[canon] = fac["tag"]
    alts = sorted(kw_to_tag, key=len, reverse=True)
    body = "|".join(r"\s+".join(re.escape(t) for t in kw.split()) for kw in alts)
    pattern = re.compile(r"(?<![\w])(?:" + body + r")(?![\w])", re.I)
    return pattern, kw_to_tag


def extract_tags(text, pattern, kw_to_tag):
    if not text:
        return
    seen = set()
    for m in pattern.finditer(text):
        canon = " ".join(m.group(0).lower().split())
        tag = kw_to_tag.get(canon)
        if tag and (tag, canon) not in seen:
            seen.add((tag, canon))
            yield tag, canon


# --------------------------------------------------------------------- lexicon

def load_lexicon(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["_meta"], data["facets"]


# ------------------------------------------------------------- serving table

TAGS_DDL = """
CREATE TABLE IF NOT EXISTS lobbying_issue_mentions (
  doc_id BIGINT, dataset TEXT, record_key TEXT, sub_index INTEGER,
  tag TEXT, keyword TEXT, src_file TEXT, src_index INTEGER);
"""


def build_tags(con, facets, batch=100000):
    """Scan lobbying_freetext with the curated vocabulary and (re)materialize
    lobbying_issue_mentions. Deterministic, idempotent, byte-reproducible."""
    pattern, kw_to_tag = build_matcher(facets)
    con.execute(TAGS_DDL)
    con.execute("DELETE FROM lobbying_issue_mentions")
    max_id = con.execute("SELECT max(doc_id) FROM lobbying_freetext").fetchone()[0] or 0
    total = con.execute("SELECT count(*) FROM lobbying_freetext").fetchone()[0]
    rows, n_docs = [], 0
    lo = 0
    while lo < max_id:
        page = con.execute(
            "SELECT doc_id, dataset, record_key, sub_index, txt, src_file, src_index "
            "FROM lobbying_freetext WHERE doc_id > ? AND doc_id <= ?",
            [lo, lo + batch]).fetchall()
        for doc_id, dataset, rk, sub, txt, src_file, src_index in page:
            n_docs += 1
            for tag, kw in extract_tags(txt, pattern, kw_to_tag):
                rows.append((doc_id, dataset, rk, sub, tag, kw, src_file, src_index))
        lo += batch
        print(f"  scanned {n_docs:,}/{total:,} docs -> {len(rows):,} tag rows",
              end="\r", flush=True)
    print()
    # bulk load via NDJSON COPY (executemany is row-by-row / slow)
    cols = ["doc_id", "dataset", "record_key", "sub_index",
            "tag", "keyword", "src_file", "src_index"]
    fd, tmp = tempfile.mkstemp(suffix=".ndjson")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(dict(zip(cols, r)), ensure_ascii=False,
                                   default=str) + "\n")
        con.execute(f"COPY lobbying_issue_mentions FROM "
                    f"'{tmp.replace(chr(92), '/')}' (FORMAT json)")
    finally:
        os.unlink(tmp)
    by_tag = con.execute("SELECT tag, count(*) n_rows, count(DISTINCT record_key) filings "
                         "FROM lobbying_issue_mentions GROUP BY 1 ORDER BY 2 DESC").fetchall()
    return len(rows), by_tag


def tags_ready(con, tag):
    try:
        return con.execute("SELECT count(*) FROM lobbying_issue_mentions "
                           "WHERE tag=?", [tag]).fetchone()[0]
    except duckdb.Error:
        return 0


# ------------------------------------------------------------------- the map

def q(con, sql, params=None):
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


PLAYERS_SQL = """
WITH docs AS (   -- distinct crypto-tagged filings, per chamber
  SELECT DISTINCT dataset, record_key FROM lobbying_issue_mentions WHERE tag = ?),
sen AS (         -- senate filing -> client + registrant raw names + income/year
  SELECT d.record_key, sf.client_name AS raw, 'client' AS role, 'senate' AS ds,
         sf.income, sf.filing_year
  FROM docs d JOIN senate_filings sf ON sf.filing_uuid = d.record_key
  WHERE d.dataset = 'senate' AND sf.client_name IS NOT NULL
  UNION ALL
  SELECT d.record_key, sf.registrant_name, 'registrant', 'senate', sf.income, sf.filing_year
  FROM docs d JOIN senate_filings sf ON sf.filing_uuid = d.record_key
  WHERE d.dataset = 'senate' AND sf.registrant_name IS NOT NULL),
hou AS (
  SELECT d.record_key, hf.client_name AS raw, 'client' AS role, 'house' AS ds,
         hf.income, hf.report_year AS filing_year
  FROM docs d JOIN house_filings hf ON hf.filing_id = d.record_key
  WHERE d.dataset = 'house' AND hf.client_name IS NOT NULL
  UNION ALL
  SELECT d.record_key, hf.organization_name, 'registrant', 'house', hf.income, hf.report_year
  FROM docs d JOIN house_filings hf ON hf.filing_id = d.record_key
  WHERE d.dataset = 'house' AND hf.organization_name IS NOT NULL),
raw AS (SELECT * FROM sen UNION ALL SELECT * FROM hou),
resolved AS (   -- raw name -> resolved entity via entity_aliases (raw_name join,
                -- same key v_client_canonical_spend uses)
  SELECT r.*, ea.entity_id, e.canonical_name
  FROM raw r
  LEFT JOIN entity_aliases ea
    ON ea.raw_name = r.raw AND ea.kind = r.role AND ea.dataset = r.ds
  LEFT JOIN entities e ON e.entity_id = ea.entity_id)
SELECT role,
       coalesce(canonical_name, raw) AS player,
       coalesce(entity_id, 'UNRESOLVED:' || upper(trim(raw))) AS entity_id,
       count(DISTINCT record_key) AS n_filings,
       min(filing_year) AS first_year, max(filing_year) AS last_year
FROM resolved
GROUP BY 1, 2, 3
"""


def player_list(con, tag, min_docs, top):
    players = q(con, PLAYERS_SQL + " HAVING count(DISTINCT record_key) >= ? "
                "ORDER BY role, n_filings DESC", [tag, min_docs])
    # attach total canonical lobbying spend for client-entities (all issues; the
    # money tool's honest number — filing-level crypto attribution is imprecise)
    spend = {r["client_entity_id"]: r["total"] for r in q(con, """
        SELECT client_entity_id, round(sum(canonical_spend)) AS total
        FROM v_client_canonical_spend GROUP BY 1""") if r["client_entity_id"]}
    for p in players:
        p["total_canonical_spend"] = spend.get(p["entity_id"])
    return players


def top_keywords(con, tag, top):
    return q(con, "SELECT keyword, count(DISTINCT record_key) filings "
             "FROM lobbying_issue_mentions WHERE tag=? GROUP BY 1 "
             "ORDER BY filings DESC LIMIT ?", [tag, top])


# ----------------------------------------------------------------- presentation

def money(v):
    return f"${v:,.0f}" if v is not None else "·"


def render(meta, facet, players, kw, tag, data_root, min_docs, recall_only):
    clients = [p for p in players if p["role"] == "client"]
    regs = [p for p in players if p["role"] == "registrant"]
    phrase_set = set(w.lower() for w in facet["phrases"])

    def name_has_phrase(name):
        low = (name or "").lower()
        return any(re.search(r"\b" + re.escape(w) + r"\b", low) for w in phrase_set)

    for p in players:
        p["name_hit"] = name_has_phrase(p["player"])
    missed = [p for p in clients if not p["name_hit"]]

    L = ["=" * 78, f"INDUSTRY MAP  ·  {facet['label']}  (tag {tag})", "=" * 78]
    L.append(f"lexicon v{meta['version']} ({meta['generated']}) · "
             f"{len(facet['phrases'])} match phrases · serving table "
             f"lobbying_issue_mentions")
    L.append(f"{len(clients)} client-side players · {len(regs)} registrant-side "
             f"players  (>= {min_docs} crypto free-text doc(s) each)")
    L.append("")

    L.append("── RECALL: players a name-LIKE '%crypto%' scan would MISS " + "─" * 20)
    L.append(f"  {len(missed)}/{len(clients)} client players have NO facet phrase in "
             f"their name — found only by what they SAY they lobby on:")
    for p in missed[:20]:
        L.append(f"    {money(p['total_canonical_spend']):>16}  "
                 f"{p['n_filings']:>4} filings  {p['player'][:46]}")
    L.append("")
    if recall_only:
        return "\n".join(L)

    L.append("── CLIENT-SIDE PLAYERS (the industry) " + "─" * 40)
    L.append("  total lobbying spend is ALL-ISSUE (v_client_canonical_spend), a "
             "ranking signal — not crypto-only dollars.")
    for p in clients[:40]:
        flag = "" if p["name_hit"] else "  ⟵ name-invisible"
        L.append(f"    {money(p['total_canonical_spend']):>16}  {p['n_filings']:>4} f  "
                 f"{p['first_year']}-{p['last_year']}  {p['player'][:44]}{flag}")
    L.append("")
    L.append("── REGISTRANT-SIDE PLAYERS (who files for them) " + "─" * 30)
    for p in regs[:25]:
        L.append(f"    {p['n_filings']:>4} f  {p['first_year']}-{p['last_year']}  "
                 f"{p['player'][:52]}")
    L.append("")
    L.append("── TOP MATCHED VOCABULARY (keyword -> filings) " + "─" * 31)
    for r in kw[:20]:
        L.append(f"    {r['filings']:>6}  {r['keyword']}")
    L.append("")
    L.append("* Player list is ENTITY-RESOLVED (lda-entity-resolver). Feed the roster to")
    L.append("  the money tools unchanged:")
    L.append("    lda_ld203_giving.py --names-file <roster>     # who they give to (LD-203)")
    L.append("    v_client_canonical_spend (client name)    # what they spend (all issues)")
    L.append("* Tags are the deterministic keyword->exact-word->record chain in "
             "lobbying_issue_mentions; every player resolves to raw filings via")
    L.append(f"  python skills/lda-corpus-loader/scripts/show_record.py <key> "
             f"--data-root {data_root} --db db/lda_full.duckdb")
    L.append("* Where the resolver split a company's name variants (cleanup C / P6), a "
             "player may appear twice or under-count — a known limitation.")
    L.append("  Citeable aggregate form: queries/p4_industry_map.sql")
    return "\n".join(L)


def write_roster(players, path, role="client"):
    """The roster the money tools consume is the CLIENT-side players — the industry
    itself. Outside registrant firms (FS Vector, Invariant) are shown in the map for
    context but excluded here: ld203_giving on an outside firm reports that FIRM's
    giving, not the industry's. Crypto trade groups (Blockchain Association, Coin
    Center) correctly appear on the client side and stay in."""
    names = sorted({p["player"] for p in players
                    if p["player"] and (role == "all" or p["role"] == role)})
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(names) + "\n", encoding="utf-8")
    return len(names)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("facet", nargs="?", default=None)
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--lexicon",
                    default=str(Path(__file__).with_name("industry_lexicon.json")))
    ap.add_argument("--facet", dest="facet_opt", default="crypto")
    ap.add_argument("--build-tags", action="store_true")
    ap.add_argument("--min-docs", type=int, default=1)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--out", help="roster path (default out/<facet>_roster.txt)")
    ap.add_argument("--no-roster", action="store_true")
    ap.add_argument("--recall-check", action="store_true")
    ap.add_argument("--data-root", default="../data/data")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    meta, facets = load_lexicon(args.lexicon)
    facet_id = args.facet or args.facet_opt
    facet = next((f for f in facets if f["id"] == facet_id), None)
    if not facet:
        sys.exit(f"no facet '{facet_id}' in lexicon; have: "
                 f"{', '.join(f['id'] for f in facets)}")
    tag = facet["tag"]

    con = duckdb.connect(args.db, read_only=False if args.build_tags else True)

    if args.build_tags:
        print(f"Building lobbying_issue_mentions from lexicon v{meta['version']} "
              f"({sum(len(f['phrases']) for f in facets)} phrases) ...")
        n, by_tag = build_tags(con, facets)
        print(f"Done: {n:,} tag rows; "
              + ", ".join(f"{t}={r:,} rows / {fi:,} filings" for t, r, fi in by_tag))
        con.close()
        con = duckdb.connect(args.db, read_only=True)

    if not tags_ready(con, tag):
        con.close()
        sys.exit(f"lobbying_issue_mentions has no '{tag}' rows — run with "
                 f"--build-tags first (needs lobbying_freetext + entity tables).")

    players = player_list(con, tag, args.min_docs, args.top)
    kw = top_keywords(con, tag, args.top)

    if not args.no_roster:
        # Default to a gitignored, disposable repo-root out/ dir — never write a
        # generated artifact into skills/. Override with --out; suppress with --no-roster.
        out_path = args.out or f"out/{facet_id}_roster.txt"
        n = write_roster(players, out_path)
        print(f"Wrote {n} entity-resolved player names -> {out_path}  "
              f"(feed to lda_ld203_giving.py --names-file)")

    if args.json:
        print(json.dumps({"facet": facet_id, "tag": tag,
                          "lexicon_version": meta["version"],
                          "players": players, "top_keywords": kw},
                         indent=2, default=str))
    else:
        print(render(meta, facet, players, kw, tag, args.data_root,
                     args.min_docs, args.recall_check))
    con.close()


if __name__ == "__main__":
    main()
