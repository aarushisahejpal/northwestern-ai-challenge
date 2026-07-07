#!/usr/bin/env python3
"""LD-203 giving map: given a registrant entity (one name, or a roster of them),
report its political giving reported on Senate LD-203 contribution reports —
totals, breakdown by contribution type, top recipients, and per-entity split —
each sample row carrying a filing_uuid resolvable by lda-corpus-loader/show_record.py.

Answers the "...and who are they giving money to?" half of an industry map. Pair
it with lda-entity-resolver's v_client_canonical_spend (P1), which answers the
"what do they spend to lobby?" half.

WHAT IT MATCHES — and the attribution boundary you must not overstate.
LD-203 reports are filed BY REGISTRANTS (and by their individual lobbyists),
never by clients. So this tool resolves your query to a *registrant* entity and
sums the giving filed under that registrant's name. That is valid and clean for:
  - in-house registrants (a company that registers to lobby itself, e.g. Coinbase),
  - trade associations / coalitions (Blockchain Association, The Digital Chamber),
  - lobbying firms (their own firm-wide giving).
It CANNOT attribute an outside firm's giving to that firm's individual clients:
a crypto client that lobbies only through a multi-client firm has no LD-203 giving
of its own here (its outside firm's LD-203 is firm-wide, not client-attributable).
If your query resolves only to a client entity, the tool says so.

SCOPE — LD-203 is not FEC. LD-203 captures lobbyist/registrant-reported FECA
contributions plus honorary, presidential-inaugural, and library payments. It does
NOT capture Super PAC money (that lives in FEC data). For an industry like crypto,
whose headline election spending flows through Super PACs, LD-203 shows the
disclosed lobbyist-side giving — real, citable, and a fraction of the FEC total.

Usage:
  python ld203_giving.py "coinbase"                    # one entity (substring match)
  python ld203_giving.py --names-file crypto.txt       # a roster (exact match/line)
    --db PATH          DuckDB (default db/lda_full.duckdb)
    --names-file PATH  newline-delimited entity names; each matched EXACTLY
                       (canonical name or a known alias) — the industry-map input
    --exact            force exact match for the positional query too
    --type LIST        contribution types to include (default all):
                       feca,he,me,pic,ple  (feca=FEC campaign; he=honorary;
                       pic=presidential inaugural; ple=presidential library; me=meeting/event)
    --since YEAR       only items with filing_year >= YEAR
    --top N            recipients / entities ranked (default 15)
    --limit N          sample record keys shown (default 10)
    --data-root PATH   printed into the show_record.py hint (default ../data/data)
    --json             machine-readable output

Totals are DE-DUPLICATED across LD-203 amendments (the loader does not capture
LD-203 filing_type, so an amended report would otherwise double-count its items);
the raw figure is shown alongside so the amendment delta is visible. Treat totals
as a ranking signal and verify specific items via show_record.py.

The citeable aggregate form of these numbers is queries/ld203_giving.sql (blocks
G1a-G1d) — the labeled SQL a finding cites, per the aggregate-claim rule.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Kept in exact sync with lda-entity-resolver/scripts/resolve_entities.py:norm_name.
# If that normalization changes, change this too — a drift here silently
# under-matches registrants (the class of bug CLAUDE.md's "data facts" warns of).
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


TYPE_LABEL = {
    "feca": "FEC campaign contribution",
    "he": "honorary (event honoring a covered official)",
    "me": "meeting/event payment",
    "pic": "presidential inaugural committee",
    "ple": "presidential library",
}


def q(con, sql, params=None):
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


# --------------------------------------------------------------- entity resolve

def resolve_registrants(con, terms, exact):
    """Resolve query terms -> registrant entities. Returns (entities, norm_keys,
    unresolved, client_only). Substring match for a single interactive term;
    exact (canonical name or alias) for roster lines, so a roster of canonical
    names doesn't pull in accidental substrings. For every matched entity we
    collect ALL of its aliases' norm_keys (an entity can carry several spellings
    with different keys), maximizing recall within the resolver's boundaries."""
    ents, keys, unresolved, client_only = {}, set(), [], []
    for term in terms:
        t = term.strip()
        if not t:
            continue
        if exact:
            rows = q(con, """
                SELECT DISTINCT entity_id, canonical_name, norm_key FROM entities
                WHERE kind='registrant' AND (
                    upper(canonical_name)=upper(?)
                    OR entity_id IN (SELECT entity_id FROM entity_aliases
                                     WHERE upper(raw_name)=upper(?)))""", [t, t])
        else:
            like = f"%{t}%"
            rows = q(con, """
                SELECT DISTINCT entity_id, canonical_name, norm_key FROM entities
                WHERE kind='registrant' AND (
                    canonical_name ILIKE ?
                    OR entity_id IN (SELECT entity_id FROM entity_aliases
                                     WHERE raw_name ILIKE ?))""", [like, like])
        if not rows:
            # Distinguish three misses: (a) a registrant entity DOES exist but the
            # exact string missed it (e.g. a canonical name with an "(F/K/A …)"
            # suffix) — that's an unresolved spelling, NOT client-only; (b) only a
            # client entity matches — genuinely lobbies via outside firms; (c) nothing.
            reg_exists = q(con, """SELECT 1 FROM entities WHERE kind='registrant'
                       AND (canonical_name ILIKE ? OR entity_id IN
                            (SELECT entity_id FROM entity_aliases WHERE raw_name ILIKE ?))
                       LIMIT 1""", [f"%{t}%", f"%{t}%"])
            if reg_exists:
                unresolved.append(t + " (a registrant by this name exists but the "
                                      "exact string didn't match — check spelling / "
                                      "drop --exact / use --loose)")
            else:
                cl = q(con, """SELECT canonical_name FROM entities WHERE kind='client'
                           AND canonical_name ILIKE ? LIMIT 3""", [f"%{t}%"])
                (client_only if cl else unresolved).append(t)
            continue
        for r in rows:
            ents[r["entity_id"]] = r
            if r["norm_key"]:
                keys.add(r["norm_key"])
    # expand to every alias norm_key of the matched entities
    ids = list(ents)
    if ids:
        ph = ",".join("?" for _ in ids)
        for r in q(con, f"SELECT DISTINCT norm_key FROM entity_aliases "
                        f"WHERE entity_id IN ({ph}) AND norm_key IS NOT NULL", ids):
            keys.add(r["norm_key"])
    return list(ents.values()), keys, unresolved, client_only


def loose_registrant_names(con, terms):
    """Recall mode: LD-203 filer names matching a term directly, bypassing entity
    resolution — catches variant spellings the resolver split into separate
    entities (e.g. Payward/Kraken's three filer names). Trades precision for
    recall; the caller must eyeball the matched-name list for conflation."""
    names = {}
    for term in terms:
        t = term.strip()
        if not t:
            continue
        for r in q(con, "SELECT DISTINCT registrant_name FROM senate_contributions "
                        "WHERE registrant_name ILIKE ?", [f"%{t}%"]):
            names[r["registrant_name"]] = True
    return sorted(names)


def matched_registrant_names(con, norm_keys):
    """Concrete senate_contributions.registrant_name values whose normalized key
    is in the resolved set. Normalizing both sides bridges the ~190 LD-203 filer
    names that aren't verbatim aliases but share a canonical key."""
    names = [r["registrant_name"] for r in q(
        con, "SELECT DISTINCT registrant_name FROM senate_contributions "
             "WHERE coalesce(registrant_name,'')<>''")]
    return sorted(n for n in names if norm_name(n) in norm_keys)


# ------------------------------------------------------------------ aggregation

RECIP = "rtrim(upper(trim(coalesce(nullif(i.honoree,''), i.payee, ''))), ' ,.')"

# One de-duplicated item view (collapses original+amendment: same registrant,
# same lobbyist, same year, same contribution). filing_uuid/keys kept only in the
# sample query, which needs a citation anchor.
BASE = """
  base AS (
    SELECT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
           i.contribution_type, i.amount, i.payee, i.honoree, i.date,
           i.contributor_name, c.filing_uuid, {recip} AS recipient
    FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
    JOIN _reg r ON c.registrant_name = r.name
    {where}),
  dd AS (
    SELECT DISTINCT registrant_name, lobbyist_name, filer_type, filing_year,
           contribution_type, amount, payee, honoree, date, contributor_name,
           recipient
    FROM base)
"""


def giving(con, reg_names, types, since, top, limit):
    con.execute("CREATE OR REPLACE TEMP TABLE _reg(name TEXT)")
    con.executemany("INSERT INTO _reg VALUES (?)", [(n,) for n in reg_names])
    conds, params = [], []
    if types:
        conds.append("i.contribution_type IN (" + ",".join("?" for _ in types) + ")")
        params += types
    if since:
        conds.append("c.filing_year >= ?")
        params.append(since)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    base = BASE.format(recip=RECIP, where=where)

    totals = q(con, "WITH " + base + """
      SELECT (SELECT count(*) FROM base) raw_items,
             (SELECT round(sum(amount)) FROM base) raw_total,
             count(*) items, round(sum(amount)) total
      FROM dd""", params)[0]
    by_type = q(con, "WITH " + base + """
      SELECT contribution_type, count(*) items, round(sum(amount)) total
      FROM dd GROUP BY 1 ORDER BY total DESC NULLS LAST""", params)
    by_year = q(con, "WITH " + base + """
      SELECT filing_year, round(sum(amount)) total FROM dd
      GROUP BY 1 ORDER BY 1""", params)
    by_filer = q(con, "WITH " + base + """
      SELECT filer_type, count(*) items, round(sum(amount)) total
      FROM dd GROUP BY 1 ORDER BY total DESC NULLS LAST""", params)
    recipients = q(con, "WITH " + base + """
      SELECT recipient, count(*) items, round(sum(amount)) total
      FROM dd WHERE recipient<>'' GROUP BY 1
      ORDER BY total DESC NULLS LAST LIMIT ?""", params + [top])
    per_entity = q(con, "WITH " + base + """
      SELECT registrant_name, round(sum(amount)) total, count(*) items
      FROM dd GROUP BY 1 ORDER BY total DESC NULLS LAST LIMIT ?""", params + [top])
    sample = q(con, "WITH " + base + """
      SELECT filing_uuid record_key, registrant_name, filer_type,
             contribution_type, amount::BIGINT amount,
             coalesce(nullif(honoree,''), payee) recipient, date
      FROM base WHERE amount IS NOT NULL
      ORDER BY amount DESC LIMIT ?""", params + [limit])
    return {"totals": totals, "by_type": by_type, "by_year": by_year,
            "by_filer": by_filer, "recipients": recipients,
            "per_entity": per_entity, "sample": sample}


# ----------------------------------------------------------------- presentation

def money(v):
    return f"${v:,.0f}" if v is not None else "·"


def render(res, ents, reg_names, label, data_root, types, since,
           unresolved, client_only, multi, loose=False):
    L = ["=" * 78, f"LD-203 GIVING MAP  ·  {label}", "=" * 78]
    head = (f"matched {len(reg_names)} LD-203 filer name(s) directly" if loose
            else f"resolved to {len(ents)} registrant entit"
                 f"{'y' if len(ents)==1 else 'ies'} → {len(reg_names)} LD-203 filer name(s)")
    L.append(head
             + (f"   ·  types={','.join(types)}" if types else "")
             + (f"   ·  since {since}" if since else ""))
    if loose and reg_names:
        L.append("  ⚠ loose mode: eyeball these filer names for conflation — "
                 + "; ".join(n[:40] for n in reg_names[:8])
                 + (f"  (+{len(reg_names)-8})" if len(reg_names) > 8 else ""))
    if multi and ents:
        shown = sorted(e["canonical_name"] for e in ents)[:12]
        L.append("  entities: " + "; ".join(shown)
                 + (f"  (+{len(ents)-12} more)" if len(ents) > 12 else ""))
    if client_only:
        L.append(f"  ⚠ client-only (no LD-203 of their own — lobby via outside "
                 f"firms): {', '.join(client_only)}")
    if unresolved:
        L.append(f"  ⚠ unresolved (no registrant entity matched): {', '.join(unresolved)}")
    L.append("")

    if not reg_names:
        L.append("No LD-203 filer matched. Nothing to report.")
        L.append("(If you expected giving here, the entity may lobby only through "
                 "an outside firm — whose LD-203 is firm-wide, not attributable to it.)")
        return "\n".join(L)

    t = res["totals"]
    dup = (t["raw_total"] or 0) - (t["total"] or 0)
    L.append("── TOTAL DISCLOSED GIVING " + "─" * 52)
    L.append(f"  {money(t['total'])} across {t['items']:,} de-duplicated items"
             + (f"   (raw {money(t['raw_total'])} / {t['raw_items']:,} items — "
                f"{money(dup)} folded out as amendment duplicates)" if dup else ""))
    L.append("  by contribution type:")
    for r in res["by_type"]:
        lab = TYPE_LABEL.get(r["contribution_type"], r["contribution_type"])
        L.append(f"    {money(r['total']):>14}  {r['items']:>5} items  {lab}")
    L.append("  by filer role:")
    for r in res["by_filer"]:
        note = ("the entity's own / PAC giving" if r["filer_type"] == "organization"
                else "personal giving by its registered lobbyists")
        L.append(f"    {money(r['total']):>14}  {r['items']:>5} items  "
                 f"{r['filer_type']:<13} ({note})")
    if res["by_year"]:
        L.append("  by filing year: " + ", ".join(
            f"{r['filing_year']}:{money(r['total'])}" for r in res["by_year"]))
    L.append("")

    L.append("── TOP RECIPIENTS (who the money goes to) " + "─" * 36)
    for r in res["recipients"]:
        L.append(f"    {money(r['total']):>12}  {r['items']:>4}×  {(r['recipient'] or '·')[:48]}")
    L.append("  (recipients are raw honoree/payee strings, lightly normalized for "
             "grouping — NOT entity-resolved; candidates/PACs are a separate namespace)")
    L.append("")

    if multi:
        L.append("── GIVING BY ENTITY " + "─" * 58)
        for r in res["per_entity"]:
            L.append(f"    {money(r['total']):>14}  {r['items']:>5}×  "
                     f"{(r['registrant_name'] or '·')[:48]}")
        L.append("")

    L.append("── SAMPLE ITEMS (largest; show_record.py keys) " + "─" * 31)
    for x in res["sample"]:
        L.append(f"    {x['record_key']}  {money(x['amount']):>12}  "
                 f"[{x['contribution_type']}] {(x['recipient'] or '·')[:30]:30} "
                 f"{x['date'] or '·'}")
    L.append("")
    L.append("* LD-203 amendments are de-duplicated on the contribution identity "
             "(registrant+lobbyist+year+type+amount+payee+honoree+date+contributor);")
    L.append("  the loader does not carry LD-203 filing_type, so this is a heuristic — "
             "treat totals as a ranking signal and verify specific items.")
    L.append("* Attribution: giving is filed by REGISTRANTS, so this is the giving of "
             "in-house registrants / trade groups / firms — not attributable to an")
    L.append("  outside firm's individual clients. Scope is LD-203 only (no Super-PAC/FEC "
             "money). Pair with v_client_canonical_spend (P1) for the lobbying-spend half.")
    L.append(f"  Resolve any key:  python skills/lda-corpus-loader/scripts/show_record.py "
             f"<key> --data-root {data_root} --db db/lda_full.duckdb")
    L.append("  Citeable aggregate form: queries/ld203_giving.sql (G1a-G1d)")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?")
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--names-file")
    ap.add_argument("--exact", action="store_true")
    ap.add_argument("--loose", action="store_true",
                    help="match LD-203 filer names directly (recall over precision; "
                         "catches resolver-split name variants — eyeball for conflation)")
    ap.add_argument("--type", default="")
    ap.add_argument("--since", type=int)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--data-root", default="../data/data")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.names_file:
        terms = [ln for ln in Path(args.names_file).read_text(
            encoding="utf-8").splitlines() if ln.strip()
            and not ln.lstrip().startswith("#")]
        exact = True                      # rosters match exactly by design
        label = f"{len(terms)} entities from {Path(args.names_file).name}"
        multi = True
    elif args.query:
        terms = [args.query]
        exact = args.exact
        label = args.query
        multi = False
    else:
        ap.error("pass an entity name, or --names-file <roster>")

    types = [t.strip().lower() for t in args.type.split(",") if t.strip()]
    con = duckdb.connect(args.db, read_only=True)
    if args.loose:
        ents, keys, unresolved, client_only = [], set(), [], []
        reg_names = loose_registrant_names(con, terms)
        label += "  (loose name match)"
    else:
        ents, keys, unresolved, client_only = resolve_registrants(con, terms, exact)
        reg_names = matched_registrant_names(con, keys) if keys else []
    # roster mode can also match many entities per line -> treat as multi
    multi = multi or len(ents) > 1 or (args.loose and len(reg_names) > 1)
    res = giving(con, reg_names, types, args.since, args.top, args.limit) if reg_names else None

    if args.json:
        print(json.dumps({
            "query": label,
            "resolved_entities": [{"entity_id": e["entity_id"],
                                   "canonical_name": e["canonical_name"]} for e in ents],
            "ld203_filer_names": reg_names,
            "client_only": client_only, "unresolved": unresolved,
            "results": res}, indent=2, default=str))
    else:
        print(render(res or {}, ents, reg_names, label, args.data_root,
                     types, args.since, unresolved, client_only, multi, args.loose))
    con.close()


if __name__ == "__main__":
    main()
