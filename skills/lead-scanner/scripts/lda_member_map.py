#!/usr/bin/env python3
"""Member map (P4 mirror): given a member of Congress, find every LD-203 giver that
resolves to them, then tag each giver with the industry_lexicon facets its own
lobbying free-text carries — the reverse of the industry map (facet -> players ->
who they give to). This answers "who gives to Lindsey Graham, and what industries
are they in?" instead of "who are crypto's players, and who do they give to?"

Requires: the built DuckDB (lda-corpus-loader) + lda-entity-resolver's member layer
(build_members.py -> members_all/member_terms/member_committees) + lobbying_issue_mentions
already built (lda_industry_map.py --build-tags). Corpus bindings — reference/
corpus-profile.md: `external_money`=ld203; `entity_tables`; `freetext_surface`;
`lexicons` (industry_lexicon.json). Member resolution is the shared P6 layer,
reference/congress-legislators.md.

THE ATTRIBUTION RULE THIS TOOL ENFORCES (same boundary as the other two money tools).
LD-203 giving is filed BY REGISTRANTS. A registrant is only tagged with an industry
facet if it ALSO appears on the CLIENT side of a facet-tagged filing (i.e. it is
itself a player in that industry — an in-house registrant or a trade association,
the same self-representation rule lda_industry_map.py's write_roster() already
applies to the forward direction). An outside multi-client lobbying firm that merely
FILES disclosures naming a tagged client is never attributed to that client's
industry — its PAC giving reflects its whole book of business, not one client's. Such
firms surface in an "also files for" context note, never in the industry breakdown.

Usage:
  python lda_member_map.py "Lindsey Graham"
  python lda_member_map.py "AOC"                       # common shorthand, see below
  python lda_member_map.py "Ocasio-Cortez" --facet crypto   # one facet only
  python lda_member_map.py "Sinema" --json

    --db PATH        DuckDB (default db/lda_full.duckdb); needs lobbying_issue_mentions
                     (lda_industry_map.py --build-tags) + members_all/member_terms/
                     member_committees (build_members.py). Bridges the LD-203 giver
                     side to the client-tag side by normalized NAME, not entity_id
                     (see the reverse-facet-index comment) — entities/entity_aliases
                     are not queried here.
    --lexicon PATH   industry_lexicon.json (default: beside this script)
    --facet ID       restrict the breakdown to one facet (default: all facets)
    --type LIST      contribution types to include (default all): feca,he,me,pic,ple
    --since YEAR     only items with filing_year >= YEAR
    --top N          givers shown per facet / untagged (default 15)
    --limit N        sample record keys shown (default 10)
    --data-root PATH printed into the show_record.py hint (default ../data/data)
    --json           machine-readable output

A member query is resolved by the same MemberResolver used for LD-203 recipient
strings (member_resolve.py) — it matches on the member's legal name, not a filed
spelling, so most full names resolve directly ("Lindsey Graham", "Ocasio-Cortez").
A small CLI-only shorthand table below covers a few universally known initialisms
("AOC") by rewriting the query before resolution; this is NOT the same list as
member_aliases.json, which curates evidence-sourced AS-FILED spellings observed in
LD-203 data. Add to member_aliases.json only when you observe a real filed string
that fails to resolve; add to the shorthand table here only for unambiguous public
shorthand for the query itself.

Ambiguous names (same-surname pairs) are reported, never guessed — the tool exits
with the candidate list and asks for a more specific query (add "Sen."/"Rep." or a
first name).

Scans every distinct LD-203 recipient string in the corpus once (cached per string),
same cost class as lda_ld203_giving.py's --names-file member rollup run against a
large roster — expect it to take longer than a single-entity giving-map query.

Citeable aggregate form: none committed yet. After a real run, add
queries/p4b_member_map.sql (labels P4Ma...) following the ld203_giving.sql /
p4_industry_map.sql pattern — swap in the resolved bioguide_id's matched LD-203
filer/recipient strings from a --json run, don't re-derive the resolution by SQL.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# CLI-input convenience only — see docstring. NOT the evidence-sourced
# member_aliases.json list; rewrites the query string before resolution.
COMMON_SHORTHAND = {
    "AOC": "Ocasio-Cortez",
}

# Kept in exact sync with lda-entity-resolver/scripts/resolve_entities.py:norm_name
# (and lda_industry_map.py / lda_ld203_giving.py). A drift here silently
# under-matches the client-side facet index.
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


def q(con, sql, params=None):
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


# ------------------------------------------------------------------ lexicon

def load_lexicon(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["_meta"], data["facets"]


def mentions_ready(con):
    try:
        return con.execute("SELECT count(*) FROM lobbying_issue_mentions").fetchone()[0]
    except duckdb.Error:
        return 0


# ---------------------------------------------------- reverse facet index
# The mirror of lda_industry_map.py's PLAYERS_SQL: instead of one facet's tag ->
# players, this builds every facet's tag set keyed on the player's NORMALIZED name
# (not entity_id — a giving registrant's entity_id and a client entity's entity_id
# for the same real company are resolved separately, per profile §4's "known
# ceiling", so name-level norm_key is the only bridge between the two roles).

REVERSE_SQL = """
WITH docs AS (SELECT DISTINCT dataset, record_key, tag FROM lobbying_issue_mentions),
cli AS (
  SELECT d.tag, sf.client_name AS raw
  FROM docs d JOIN senate_filings sf ON sf.filing_uuid = d.record_key
  WHERE d.dataset = 'senate' AND sf.client_name IS NOT NULL
  UNION ALL
  SELECT d.tag, hf.client_name AS raw
  FROM docs d JOIN house_filings hf ON hf.filing_id = d.record_key
  WHERE d.dataset = 'house' AND hf.client_name IS NOT NULL),
reg AS (
  SELECT d.tag, sf.registrant_name AS raw
  FROM docs d JOIN senate_filings sf ON sf.filing_uuid = d.record_key
  WHERE d.dataset = 'senate' AND sf.registrant_name IS NOT NULL
  UNION ALL
  SELECT d.tag, hf.organization_name AS raw
  FROM docs d JOIN house_filings hf ON hf.filing_id = d.record_key
  WHERE d.dataset = 'house' AND hf.organization_name IS NOT NULL)
SELECT 'client' AS role, tag, raw FROM cli
UNION ALL
SELECT 'registrant' AS role, tag, raw FROM reg
"""


def build_reverse_index(con):
    """norm_key -> {tag,...} for CLIENT-side (the player-is-in-this-industry index
    this tool tags givers with) and REGISTRANT-side (context-only: this firm FILES
    disclosures naming a tagged client, never attributed to that client's giving)."""
    client_idx, reg_idx = {}, {}
    for r in q(con, REVERSE_SQL):
        nk = norm_name(r["raw"])
        if not nk:
            continue
        idx = client_idx if r["role"] == "client" else reg_idx
        idx.setdefault(nk, set()).add(r["tag"])
    return client_idx, reg_idx


# ------------------------------------------------------------ member resolution

def load_resolver(db):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                           / "lda-entity-resolver" / "scripts"))
    from member_resolve import MemberResolver
    return MemberResolver(db)


def resolve_target(con, resolver, query):
    """Resolve a plain member-name query to one bioguide_id, or exit with a
    candidate list / suggestion. Never guesses among ambiguous matches."""
    q_rewritten = COMMON_SHORTHAND.get(query.strip().upper(), query)
    shown = f"'{query}'" if q_rewritten == query else f"'{query}' (tried as '{q_rewritten}')"
    rep = resolver.resolve(q_rewritten)
    if rep["kind"] == "member" and not rep["ambiguous"] and len(rep["matches"]) == 1:
        m = rep["matches"][0]
        return resolver.by_bio[m["bioguide_id"]]
    if rep["kind"] == "member" and rep["ambiguous"]:
        lines = [f"  {m['name']} ({m['chamber']}, {m['state']})  bioguide={m['bioguide_id']}"
                 for m in rep["matches"]]
        sys.exit(f"{shown} is ambiguous among {len(rep['matches'])} members - "
                 f"be more specific (add Sen./Rep. or a first name):\n" + "\n".join(lines))
    # fall back to a direct ILIKE scan of members_all for a helpful suggestion list
    like = f"%{q_rewritten.strip()}%"
    cands = q(con, """
        SELECT bioguide_id, name, chamber, state FROM members_all
        WHERE name ILIKE ? OR last_name ILIKE ? OR first_name ILIKE ? OR aka_names ILIKE ?
        ORDER BY name LIMIT 10""", [like, like, like, like])
    if cands:
        lines = [f"  {c['name']} ({c['chamber']}, {c['state']})  bioguide={c['bioguide_id']}"
                 for c in cands]
        sys.exit(f"{shown} didn't resolve by exact name-token match; closest members_all "
                 f"rows (pick the exact name and retry):\n" + "\n".join(lines))
    sys.exit(f"{shown} matched no member in members_all - check spelling, or the member "
             f"may be outside the corpus window (build_members.py --since-end).")


# ---------------------------------------------------------------- giving scan

RECIP = "rtrim(upper(trim(coalesce(nullif(i.honoree,''), i.payee, ''))), ' ,.')"

# Same dedup identity as lda_ld203_giving.py's BASE, minus the roster (_reg) join —
# this tool scans EVERY registrant, not a pre-built roster. filing_uuid is kept OUT
# of dd (same reason as the sibling tool: including a per-row unique key in the
# DISTINCT would defeat amendment dedup) — citation keys are pulled separately, by
# a second targeted query, only for the recipient strings that already resolved to
# the target member.
ALL_BASE = """
  base AS (
    SELECT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
           i.contribution_type, i.amount, i.payee, i.honoree, i.date,
           i.contributor_name, c.filing_uuid, {recip} AS recipient
    FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
    {where}),
  dd AS (
    SELECT DISTINCT registrant_name, lobbyist_name, filer_type, filing_year,
           contribution_type, amount, payee, honoree, date, contributor_name,
           recipient
    FROM base)
"""

ATTRIB_TIERS = ("direct", "campaign-committee", "leadership-pac")


def scan_member_giving(con, resolver, target_bio, types, since, sample_limit):
    conds, params = [], []
    if types:
        conds.append("i.contribution_type IN (" + ",".join("?" for _ in types) + ")")
        params += types
    if since:
        conds.append("c.filing_year >= ?")
        params.append(since)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    base = ALL_BASE.format(recip=RECIP, where=where)
    items = q(con, "WITH " + base + """
      SELECT registrant_name, recipient, date, amount, contribution_type
      FROM dd WHERE recipient<>'' AND amount IS NOT NULL""", params)

    cache, by_reg = {}, {}
    n_ambiguous = n_matched = 0
    parties_seen = []
    target_recipients = set()
    for it in items:
        rep = cache.get(it["recipient"])
        if rep is None:
            rep = cache[it["recipient"]] = resolver.resolve(it["recipient"])
        if rep["ambiguous"]:
            if any(m["bioguide_id"] == target_bio for m in rep["matches"]):
                n_ambiguous += 1
            continue
        bucket = None
        for m in rep["matches"]:
            if m["bioguide_id"] != target_bio:
                continue
            tier = m["tier"]
            bucket = tier if tier in ATTRIB_TIERS else \
                ("jfc" if tier.startswith("jfc") else
                 "multi" if tier.startswith("multi-honoree") else None)
            break
        if bucket is None:
            continue
        target_recipients.add(it["recipient"])
        n_matched += 1
        r = by_reg.setdefault(it["registrant_name"], {
            "registrant_name": it["registrant_name"], "direct": 0.0,
            "campaign-committee": 0.0, "leadership-pac": 0.0,
            "jfc": 0.0, "multi": 0.0, "items": 0})
        r[bucket] += it["amount"]
        r["items"] += 1
        pl, _src = resolver.party_at(target_bio, it["date"] or None)
        if pl not in parties_seen:
            parties_seen.append(pl)

    for r in by_reg.values():
        r["total_attributable"] = sum(r[t] for t in ATTRIB_TIERS)
    totals = {t: sum(r[t] for r in by_reg.values()) for t in ATTRIB_TIERS}

    # Citation keys: a SECOND, targeted query against the un-deduped `base` (which
    # still carries filing_uuid), restricted to the small set of recipient strings
    # already proven (above) to resolve to this member — never re-derives the
    # resolution in SQL, just fetches a key for rows we already trust.
    sample = []
    if target_recipients:
        trlist = list(target_recipients)
        ph = ",".join("?" for _ in trlist)
        sample = q(con, "WITH " + base + f"""
          SELECT filing_uuid record_key, registrant_name, contribution_type,
                 amount::BIGINT amount, recipient, date
          FROM base WHERE recipient IN ({ph}) AND amount IS NOT NULL
          ORDER BY amount DESC LIMIT ?""", params + trlist + [sample_limit])
        for s in sample:
            rep = cache[s["recipient"]]
            for m in rep["matches"]:
                if m["bioguide_id"] == target_bio:
                    tier = m["tier"]
                    s["bucket"] = tier if tier in ATTRIB_TIERS else \
                        ("jfc" if tier.startswith("jfc") else "multi")
                    break

    return {
        "registrants": list(by_reg.values()),
        "total_attributable": sum(totals.values()),
        "by_tier": totals,
        "jfc_total": sum(r["jfc"] for r in by_reg.values()),
        "multi_total": sum(r["multi"] for r in by_reg.values()),
        "n_ambiguous_items": n_ambiguous,
        "n_items_matched": n_matched,
        "n_recipients_scanned": len(cache),
        "parties_seen": parties_seen,
        "sample": sample,
    }


# ----------------------------------------------------------------- classify

def classify(registrants, client_idx, reg_idx, facet_tags):
    """Attach facet tags (client-side only, the attribution-safe set) and a
    context note (registrant-side only, informational) to each giver. facet_tags
    are lobbying_issue_mentions.tag values (e.g. 'CRYPTO'), NOT lexicon ids
    ('crypto') — the two differ for every facet except case (CRITMIN/GENIUS)."""
    by_facet = {t: [] for t in facet_tags}
    untagged = []
    for r in registrants:
        nk = norm_name(r["registrant_name"])
        tags = sorted((client_idx.get(nk) or set()) & set(facet_tags)) if nk else []
        r["facet_tags"] = tags
        r["context_tags"] = sorted((reg_idx.get(nk) or set()) - set(tags)) if nk else []
        if tags:
            for t in tags:
                by_facet[t].append(r)
        else:
            untagged.append(r)
    for t in by_facet:
        by_facet[t].sort(key=lambda r: -r["total_attributable"])
    untagged.sort(key=lambda r: -r["total_attributable"])
    return by_facet, untagged


# ----------------------------------------------------------------- presentation

def money(v):
    return f"${v:,.0f}" if v is not None else "·"


def render(member, res, by_facet, untagged, facets_by_tag, data_root, top, limit, facet_only):
    bracket = f"({'>'.join(res['parties_seen']) or member['party'][:1]}-{member['state']})"
    title = "Sen." if member["chamber"] == "Senate" else "Rep."
    L = ["=" * 78, f"MEMBER MAP  ·  {title} {member['name']} {bracket}", "=" * 78]
    L.append(f"bioguide {member['bioguide_id']} · scanned {res['n_recipients_scanned']:,} "
             f"distinct LD-203 recipient strings corpus-wide")
    if res["n_ambiguous_items"]:
        L.append(f"  ⚠ {res['n_ambiguous_items']} item(s) named a string ambiguous between "
                 f"this member and another — excluded, never guessed (see --json)")
    L.append("")

    L.append("── TOTAL DISCLOSED GIVING RECEIVED " + "─" * 42)
    if res["n_items_matched"] == 0:
        L.append("  none found in the scanned window.")
        return "\n".join(L)
    parts = [f"direct {money(res['by_tier']['direct'])}"]
    if res["by_tier"]["campaign-committee"]:
        parts.append(f"campaign {money(res['by_tier']['campaign-committee'])}")
    if res["by_tier"]["leadership-pac"]:
        parts.append(f"ldpac {money(res['by_tier']['leadership-pac'])}")
    L.append(f"  {money(res['total_attributable'])} across {res['n_items_matched']} items  "
             f"[{' · '.join(parts)}]")
    shared = "".join(f"  +{lbl} {money(res[k])} (unalloc)"
                     for k, lbl in (("jfc_total", "jfc-shared"), ("multi_total", "multi-honoree"))
                     if res[k])
    if shared:
        L.append(f"  {shared.strip()}")
    L.append(f"  from {len(res['registrants'])} distinct registrants")
    L.append("")

    def print_facet(tag, rows):
        f = facets_by_tag.get(tag, {"label": tag})
        L.append(f"── {f['label'].upper()}  ({len(rows)} giver(s)) " + "─" * max(2, 50 - len(f['label'])))
        for r in rows[:top]:
            L.append(f"    {money(r['total_attributable']):>12}  {r['items']:>4}×  "
                     f"{r['registrant_name'][:50]}")
        L.append("")

    shown_any = False
    for tag, rows in by_facet.items():
        if facet_only and tag != facet_only:
            continue
        if rows:
            print_facet(tag, rows)
            shown_any = True
    if not shown_any and facet_only:
        L.append(f"(no givers tagged {facet_only} for this member)")
        L.append("")

    if not facet_only:
        L.append("── UNTAGGED (no industry_lexicon facet on the CLIENT side) " + "─" * 18)
        L.append("  self-represents in no curated facet, or is an outside multi-client firm — "
                 "'files for' below is context, NOT attribution:")
        for r in untagged[:top]:
            ctx = f"  (files for tagged clients: {', '.join(r['context_tags'])})" \
                if r["context_tags"] else ""
            L.append(f"    {money(r['total_attributable']):>12}  {r['items']:>4}×  "
                     f"{r['registrant_name'][:44]}{ctx}")
        L.append("")

    L.append("── SAMPLE ITEMS (largest; show_record.py keys) " + "─" * 31)
    for x in res["sample"]:
        L.append(f"    {x['record_key']}  {money(x['amount']):>12}  "
                 f"[{x['contribution_type']}] {x.get('bucket', '?'):<20} "
                 f"{x['registrant_name'][:28]}")
    L.append("")
    L.append("* Attribution: a giver is tagged with a facet only if it appears on the CLIENT side")
    L.append("  of a tagged filing (self-representing player) — an outside firm's giving is never")
    L.append("  attributed to one client's industry, same boundary as lda_ld203_giving.py.")
    L.append("* Scope is LD-203 only (no Super-PAC/FEC money) — see lda_ld203_giving.py's scope note.")
    L.append("* Rollup, never conflation: JFC / multi-honoree dollars are shared & UNALLOCATED, never")
    L.append("  summed into the member total (member_resolve.py, P6 discipline).")
    L.append(f"  Resolve any key:  python skills/lda-corpus-loader/scripts/show_record.py "
             f"<key> --data-root {data_root} --db db/lda_full.duckdb")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("member")
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--lexicon",
                    default=str(Path(__file__).with_name("industry_lexicon.json")))
    ap.add_argument("--facet")
    ap.add_argument("--type", default="")
    ap.add_argument("--since", type=int)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--data-root", default="../data/data")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    meta, facets = load_lexicon(args.lexicon)
    facets_by_id = {f["id"]: f for f in facets}
    facets_by_tag = {f["tag"]: f for f in facets}
    if args.facet and args.facet not in facets_by_id:
        sys.exit(f"no facet '{args.facet}' in lexicon; have: {', '.join(facets_by_id)}")
    facet_only_tag = facets_by_id[args.facet]["tag"] if args.facet else None

    con = duckdb.connect(args.db, read_only=True)
    if not mentions_ready(con):
        con.close()
        sys.exit("lobbying_issue_mentions is empty/missing — run "
                 "lda_industry_map.py --build-tags first.")
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if {"members_all", "member_terms", "member_committees"} - tables:
        con.close()
        sys.exit("member tables missing — run "
                 "skills/lda-entity-resolver/scripts/build_members.py first.")

    resolver = load_resolver(args.db)
    member = resolve_target(con, resolver, args.member)

    types = [t.strip().lower() for t in args.type.split(",") if t.strip()]
    res = scan_member_giving(con, resolver, member["bioguide_id"], types, args.since,
                             args.limit)
    client_idx, reg_idx = build_reverse_index(con)
    by_facet, untagged = classify(res["registrants"], client_idx, reg_idx,
                                  [f["tag"] for f in facets])

    if args.json:
        print(json.dumps({
            "member": {"bioguide_id": member["bioguide_id"], "name": member["name"],
                      "chamber": member["chamber"], "state": member["state"]},
            "lexicon_version": meta["version"],
            "totals": {k: v for k, v in res.items() if k not in ("registrants", "sample")},
            "by_facet": {t: rows for t, rows in by_facet.items()},
            "untagged": untagged,
            "sample": res["sample"],
        }, indent=2, default=str))
    else:
        print(render(member, res, by_facet, untagged, facets_by_tag, args.data_root,
                     args.top, args.limit, facet_only_tag))
    con.close()


if __name__ == "__main__":
    main()
