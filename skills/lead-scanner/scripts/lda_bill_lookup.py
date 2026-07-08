#!/usr/bin/env python3
"""Bill cross-check: given a bill (number OR named alias), list every Senate
filing, House filing, and press release that touches it, each with a citation
key resolvable by lda-corpus-loader/show_record.py.

Requires: the built DuckDB (lda-corpus-loader). Corpus bindings — see
reference/corpus-profile.md: `citation_keys`; `mirror_sources`/`primary_for_dollars`
(never sum chambers); `attribution_grain` (per-bill dollars rank, not total);
`period_invariant_key` (dedup). Vocabulary: bill_aliases.json.

Why this exists (the L004 lesson). Press releases and members name bills ("the
Farm Bill", "NDAA", "Inflation Reduction Act"); LDA filings cite H.R./S. numbers.
Matching on numbers alone fabricates "lobbied but publicly silent" bills. This
tool bridges the two: a query by number also surfaces the name-cited press (and,
for phrase-primary bills, the name-cited filings), and a query by name reaches
the number-cited filings via the curated crosswalk in bill_aliases.json.

  Number side  -> exact match on the pre-extracted `bill_mentions` table
  Name side    -> whole-word regex on press text (+ filing free-text on request)

Usage:
  python lda_bill_lookup.py <bill-or-alias> [options]
    <bill-or-alias>   "HR5376" | "H.R. 5376" | "Inflation Reduction Act" | "Farm Bill"
  --db PATH           DuckDB (default db/lda_full.duckdb)
  --aliases PATH      alias table (default: bill_aliases.json beside this script)
  --dataset SET       senate,house,press  (comma list; default all)
  --limit N           sample record keys shown per dataset/mode (default 8)
  --top N             top clients/members ranked (default 10)
  --scan-freetext     also NAME-match filing free-text (senate activity
                      descriptions, house specific_issues). Auto-on for
                      phrase-primary bills (no reliable number, e.g. Farm Bill).
  --data-root PATH    printed into the show_record.py hint (default ../../../data/data)
  --json              machine-readable output
  --list-aliases      print the alias table and exit

Aggregate counts/rankings this prints are also expressible as a labeled block in
queries/p2_bill_crosscheck.sql (the citeable form for findings).
"""

import argparse
import json
import re
import sys
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Same normalization build_db.py applies when it fills bill_mentions, so a
# user-typed "H.R. 5376" lands on the stored key "HR5376". Kept in sync by hand;
# if build_db.py's BILL_RE/norm_bill change, change these too.
BILL_RE = re.compile(
    r"\b("
    r"H\.?\s*J\.?\s*RES\.?|S\.?\s*J\.?\s*RES\.?|"
    r"H\.?\s*CON\.?\s*RES\.?|S\.?\s*CON\.?\s*RES\.?|"
    r"H\.?\s*RES\.?|S\.?\s*RES\.?|"
    r"H\.?\s*R\.?|S\.?"
    r")\s*(\d{1,5})\b",
    re.IGNORECASE,
)


def norm_bill(prefix, number):
    return re.sub(r"[^A-Z]", "", prefix.upper()) + number


def normalize_number(text):
    """Return the canonical bill token (e.g. 'HR5376') if `text` is a bill
    number, else None. Anchored so 'CHIPS Act' isn't read as a number."""
    m = BILL_RE.fullmatch(text.strip())
    return norm_bill(m.group(1), m.group(2)) if m else None


def congress_of_year(year):
    # 117th = 2021-22, 118th = 2023-24, 119th = 2025-26, ...
    return 117 + (int(year) - 2021) // 2


def phrase_pattern(phrases):
    """RE2 (DuckDB) whole-word, case-insensitive pattern over the phrase list.
    RE2 has no lookaround, so word boundaries use \\b; metacharacters escaped."""
    esc = [re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", p) for p in phrases]
    return r"(?i)\b(" + "|".join(esc) + r")\b"


# --------------------------------------------------------------- alias resolve

def load_aliases(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["_meta"], data["aliases"]


def resolve(query, aliases):
    """Resolve the input into {bills, phrases, alias, kind, label}.

    - a bill number -> that number (+ any alias whose crosswalk contains it, so
      the number query also gets the alias's name phrases for say-vs-pay)
    - otherwise -> alias lookup by name / id (exact, then unique substring)
    """
    num = normalize_number(query)
    if num:
        hit = next((a for a in aliases if num in a.get("bills", [])), None)
        return {
            "kind": "number",
            "bills": [num],
            "phrases": hit["phrases"] if hit else [],
            "alias": hit,
            "label": f"{num}" + (f'  ("{hit["names"][0]}")' if hit else ""),
        }

    q = query.strip().lower()
    exact = [a for a in aliases
             if q == a["id"] or q in [n.lower() for n in a["names"]]]
    cands = exact or [a for a in aliases
                      if any(q in n.lower() for n in a["names"]) or q in a["id"]]
    if len(cands) == 1:
        a = cands[0]
        return {
            "kind": "alias",
            "bills": list(a.get("bills", [])),
            "phrases": list(a.get("phrases", [])),
            "alias": a,
            "label": f'{a["names"][0]}' + (f'  ({", ".join(a["bills"])})'
                                           if a.get("bills") else "  (phrase-primary)"),
        }
    if len(cands) > 1:
        names = "; ".join(f'{a["names"][0]} [{a["id"]}]' for a in cands)
        sys.exit(f'"{query}" is ambiguous across: {names}\nRe-run with the id.')
    avail = ", ".join(sorted(a["id"] for a in aliases))
    sys.exit(f'No bill number and no alias matched "{query}".\n'
             f"Pass a number (e.g. HR5376) or one of: {avail}")


# ------------------------------------------------------------------ DB queries

def q(con, sql, params=None):
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def in_clause(bills):
    return "(" + ",".join("?" for _ in bills) + ")"


def senate_number(con, bills, top, limit):
    ph = in_clause(bills)
    dedup = f"""
      WITH keys AS (
        SELECT DISTINCT record_key FROM bill_mentions
        WHERE dataset='senate' AND bill IN {ph}),
      f AS (
        SELECT sf.filing_uuid, sf.registrant_name, sf.client_name,
               sf.income, sf.filing_year, sf.filing_period, sf.posted
        FROM senate_filings sf JOIN keys ON sf.filing_uuid = keys.record_key
        QUALIFY row_number() OVER (
          PARTITION BY upper(trim(sf.registrant_name)), upper(trim(sf.client_name)),
                       sf.filing_year, sf.filing_period
          ORDER BY sf.posted DESC) = 1)"""
    raw = q(con, f"SELECT count(DISTINCT record_key) n FROM bill_mentions "
                 f"WHERE dataset='senate' AND bill IN {ph}", bills)[0]["n"]
    summ = q(con, dedup + " SELECT count(*) engagements, "
             "count(DISTINCT upper(trim(client_name))) clients, "
             "sum(income)::BIGINT attributed_income FROM f", bills)[0]
    years = q(con, dedup + " SELECT filing_year, count(*) n FROM f "
              "GROUP BY 1 ORDER BY 1", bills)
    clients = q(con, dedup + " SELECT client_name, "
                "sum(income)::BIGINT attributed_income, count(*) filings FROM f "
                "GROUP BY 1 ORDER BY attributed_income DESC NULLS LAST LIMIT ?",
                bills + [top])
    sample = q(con, dedup + " SELECT filing_uuid record_key, client_name, "
               "registrant_name, income::BIGINT income, filing_year FROM f "
               "ORDER BY income DESC NULLS LAST LIMIT ?", bills + [limit])
    return {"raw_mention_filings": raw, "summary": summ, "years": years,
            "top_clients": clients, "sample": sample}


def house_number(con, bills, top, limit):
    ph = in_clause(bills)
    base = f"""
      WITH keys AS (
        SELECT DISTINCT record_key FROM bill_mentions
        WHERE dataset='house' AND bill IN {ph}),
      f AS (
        SELECT hf.filing_id, hf.organization_name, hf.client_name,
               hf.income, hf.report_year, hf.report_period
        FROM house_filings hf JOIN keys ON hf.filing_id = keys.record_key
        QUALIFY row_number() OVER (
          PARTITION BY upper(trim(hf.organization_name)), upper(trim(hf.client_name)),
                       hf.report_year, hf.report_period
          ORDER BY hf.filing_id DESC) = 1)"""
    summ = q(con, base + " SELECT count(*) filings, "
             "count(DISTINCT upper(trim(client_name))) clients, "
             "sum(income)::BIGINT attributed_income FROM f", bills)[0]
    years = q(con, base + " SELECT report_year, count(*) n FROM f "
              "GROUP BY 1 ORDER BY 1", bills)
    clients = q(con, base + " SELECT client_name, organization_name, "
                "sum(income)::BIGINT attributed_income, count(*) filings FROM f "
                "GROUP BY 1,2 ORDER BY attributed_income DESC NULLS LAST LIMIT ?",
                bills + [top])
    sample = q(con, base + " SELECT filing_id record_key, client_name, "
               "organization_name, income::BIGINT income, report_year FROM f "
               "ORDER BY income DESC NULLS LAST LIMIT ?", bills + [limit])
    return {"summary": summ, "years": years, "top_clients": clients,
            "sample": sample}


def press_side(con, bills, phrases, top, limit):
    """Releases that cite the NUMBER and/or NAME the bill; the name-only set is
    the say-vs-pay coverage a number-only match would have missed."""
    num_keys, name_keys = [], []
    if bills:
        ph = in_clause(bills)
        num_keys = [r["record_key"] for r in q(
            con, f"SELECT DISTINCT record_key FROM bill_mentions "
                 f"WHERE dataset='press' AND bill IN {ph}", bills)]
    if phrases:
        pat = phrase_pattern(phrases)
        name_keys = [r["k"] for r in q(
            con, "SELECT src_file || ':' || src_line k FROM press_releases "
                 "WHERE regexp_matches(text, ?)", [pat])]
    num_set, name_set = set(num_keys), set(name_keys)
    all_keys = num_set | name_set
    if not all_keys:
        return {"n_number": 0, "n_name": 0, "n_name_only": 0, "n_total": 0,
                "top_members": [], "years": [], "sample": []}

    con.execute("CREATE OR REPLACE TEMP TABLE _pk(k TEXT, via TEXT)")
    con.executemany("INSERT INTO _pk VALUES (?, ?)",
                    [(k, "both" if k in num_set and k in name_set
                         else "number" if k in num_set else "name")
                     for k in all_keys])
    joined = """
      FROM _pk JOIN press_releases pr
        ON _pk.k = pr.src_file || ':' || pr.src_line"""
    top_members = q(con, "SELECT pr.member_name, pr.party, pr.state, "
                    "count(*) releases" + joined +
                    " GROUP BY 1,2,3 ORDER BY releases DESC NULLS LAST LIMIT ?", [top])
    years = q(con, "SELECT substr(pr.date,1,4) yr, count(*) n" + joined +
              " WHERE pr.date IS NOT NULL GROUP BY 1 ORDER BY 1")
    sample = q(con, "SELECT _pk.k record_key, _pk.via, pr.member_name, "
               "pr.party, pr.state, pr.date, pr.title" + joined +
               " ORDER BY pr.date DESC NULLS LAST LIMIT ?", [limit])
    return {"n_number": len(num_set), "n_name": len(name_set),
            "n_name_only": len(name_set - num_set), "n_total": len(all_keys),
            "top_members": top_members, "years": years, "sample": sample}


def freetext_name(con, phrases, limit):
    """NAME-match filing free-text: the only filing-side signal for phrase-primary
    bills (Farm Bill), and an optional recall boost for numbered ones."""
    pat = phrase_pattern(phrases)
    sen = q(con, """
        WITH k AS (SELECT DISTINCT filing_uuid FROM senate_activities
                   WHERE regexp_matches(description, ?))
        SELECT count(*) n FROM k""", [pat])[0]["n"]
    sen_s = q(con, """
        WITH k AS (SELECT DISTINCT filing_uuid FROM senate_activities
                   WHERE regexp_matches(description, ?))
        SELECT sf.filing_uuid record_key, sf.client_name, sf.registrant_name,
               sf.income::BIGINT income, sf.filing_year
        FROM senate_filings sf JOIN k USING (filing_uuid)
        ORDER BY sf.income DESC NULLS LAST LIMIT ?""", [pat, limit])
    hou = q(con, "SELECT count(DISTINCT filing_id) n FROM house_filings "
                 "WHERE regexp_matches(specific_issues, ?)", [pat])[0]["n"]
    hou_s = q(con, "SELECT filing_id record_key, client_name, organization_name, "
              "income::BIGINT income, report_year FROM house_filings "
              "WHERE regexp_matches(specific_issues, ?) "
              "ORDER BY income DESC NULLS LAST LIMIT ?", [pat, limit])
    return {"senate_filings": sen, "senate_sample": sen_s,
            "house_filings": hou, "house_sample": hou_s}


# ----------------------------------------------------------------- presentation

def fmt_money(v):
    return f"${v:,}" if isinstance(v, int) else "·"


def render(res, r, datasets, meta, data_root, freetext, scanned_freetext):
    L = []
    a = r["alias"]
    L.append("=" * 78)
    L.append(f"BILL CROSS-CHECK  ·  {r['label']}")
    L.append("=" * 78)
    if a:
        L.append(f"alias id     : {a['id']}")
        if a.get("congress"):
            L.append(f"congress     : {a['congress']}"
                     + (f"   enacted {a['enacted']}  (P.L. {a.get('public_law','?')})"
                        if a.get("enacted") else ""))
        L.append(f"crosswalk    : {', '.join(a['bills']) if a['bills'] else '(none — phrase-primary)'}")
        L.append(f"match phrases: {', '.join(a['phrases']) if a['phrases'] else '(none)'}")
        L.append(f"note         : {a['note']}")
        L.append(f"source       : {a['source']}")
    elif r["phrases"]:
        L.append(f"match phrases: {', '.join(r['phrases'])}   (from crosswalk)")
    else:
        L.append("note         : bare number, no alias in the crosswalk — number "
                 "match only (add a bill_aliases.json entry to get name matching)")
    L.append("")

    if "senate" in datasets and r["bills"]:
        s = res["senate_number"]
        su = s["summary"]
        cohorts = sorted({congress_of_year(y["filing_year"]) for y in s["years"]
                          if y["filing_year"]})
        L.append("── SENATE (number-cited) " + "─" * 53)
        L.append(f"  {su['engagements']} engagement-quarter filings "
                 f"(dedup of {s['raw_mention_filings']} raw) · "
                 f"{su['clients']} distinct clients · "
                 f"{fmt_money(su['attributed_income'])} attributed income*")
        L.append("  by filing year: " + ", ".join(
            f"{y['filing_year']}:{y['n']}" for y in s["years"]))
        # A single enacted law (IRA) referenced across years is implementation
        # lobbying of the SAME bill, not distinct bills — don't cry wolf. The
        # real reassignment risk is a bare/recurring number with no single
        # enacted anchor (H.R.1 each Congress; NDAA's per-FY numbers).
        single_enacted = bool(a and a.get("enacted") and a.get("congress")
                              and len(r["bills"]) == 1)
        if len(cohorts) > 1 and single_enacted:
            L.append(f"  ℹ referenced across {s['years'][0]['filing_year']}–"
                     f"{s['years'][-1]['filing_year']}: ongoing implementation "
                     f"lobbying of the enacted {a['congress']}th-Congress law, "
                     "not distinct bills.")
        elif len(cohorts) > 1:
            L.append(f"  ⚠ AMBIGUITY: mentions span Congresses {cohorts}. "
                     "bill_mentions has no Congress field, so this one number may")
            L.append("    denote a DIFFERENT bill each Congress (e.g. H.R.1 is a "
                     "new bill each term) — split by year before trusting a total.")
        for c in s["top_clients"][:8]:
            L.append(f"    {fmt_money(c['attributed_income']):>16}  "
                     f"{(c['client_name'] or '·')[:52]}")
        L.append("  sample keys (show_record.py):")
        for x in s["sample"]:
            L.append(f"    {x['record_key']}  {fmt_money(x['income']):>14}  "
                     f"{(x['client_name'] or '·')[:44]}")
        L.append("")

    if "house" in datasets and r["bills"]:
        h = res["house_number"]
        hu = h["summary"]
        L.append("── HOUSE (number-cited) " + "─" * 54)
        L.append(f"  {hu['filings']} filings · {hu['clients']} distinct clients · "
                 f"{fmt_money(hu['attributed_income'])} attributed income*  "
                 "(House XML is a partial snapshot — under-counts recent quarters)")
        L.append("  by report year: " + ", ".join(
            f"{y['report_year']}:{y['n']}" for y in h["years"]))
        for c in h["top_clients"][:8]:
            L.append(f"    {fmt_money(c['attributed_income']):>16}  "
                     f"{(c['client_name'] or '·')[:52]}")
        L.append("  sample keys (show_record.py):")
        for x in h["sample"]:
            L.append(f"    {x['record_key']}  {fmt_money(x['income']):>14}  "
                     f"{(x['client_name'] or '·')[:44]}")
        L.append("")

    if "press" in datasets:
        p = res["press"]
        L.append("── PRESS " + "─" * 69)
        if not r["phrases"] and not r["bills"]:
            L.append("  (nothing to match)")
        else:
            L.append(f"  {p['n_total']} distinct releases touch this bill:  "
                     f"{p['n_number']} cite the number · {p['n_name']} name it · "
                     f"{p['n_name_only']} name-only")
            if r["bills"] and r["phrases"] and p["n_name_only"] > p["n_number"]:
                L.append(f"  ⚡ SAY-vs-PAY: {p['n_name_only']} releases name this bill "
                         f"but never cite its number — invisible to number-only")
                L.append("    matching (the L004 trap). Name matching recovers them.")
            if p["years"]:
                L.append("  by year: " + ", ".join(
                    f"{y['yr']}:{y['n']}" for y in p["years"])
                    + "   (see the vintage caveat below)")
            for m in p["top_members"][:8]:
                L.append(f"    {(m['releases']):>5}×  {(m['member_name'] or '·')[:40]} "
                         f"({m['party'] or '?'}-{m['state'] or '?'})")
            L.append("  sample keys (show_record.py):")
            for x in p["sample"]:
                L.append(f"    [{x['via']:>6}] {x['record_key']}  "
                         f"{(x['member_name'] or '·')[:22]}  {x['date'] or '·'}  "
                         f"{(x['title'] or '')[:36]}")
        L.append("")

    if freetext and res.get("freetext"):
        ft = res["freetext"]
        why = "phrase-primary bill" if scanned_freetext == "auto" else "--scan-freetext"
        L.append(f"── FILING FREE-TEXT (name-matched; {why}) " + "─" * 33)
        L.append(f"  senate: {ft['senate_filings']} filings whose activity text "
                 f"names it · house: {ft['house_filings']} filings")
        for x in ft["senate_sample"][:5]:
            L.append(f"    [senate] {x['record_key']}  {fmt_money(x['income']):>14}  "
                     f"{(x['client_name'] or '·')[:40]}")
        for x in ft["house_sample"][:5]:
            L.append(f"    [house ] {x['record_key']}  {fmt_money(x['income']):>14}  "
                     f"{(x['client_name'] or '·')[:40]}")
        L.append("")

    L.append("* attributed income is FILING-LEVEL: a filing naming several bills "
             "attributes its full income to each — a ranking signal, not exact")
    L.append("  dollars. Senate/House are reported separately (never summed: LD-2s "
             "are filed with both chambers). For exact client dollars feed the")
    L.append("  client into lda-entity-resolver's v_client_canonical_spend (P1).")
    L.append("* Press counts are RAW and VINTAGE-SENSITIVE: the press corpus starts "
             "2022-01-01 and grows ~4x by 2025 (19.7k→48.3k releases/yr), and a bill's")
    L.append("  press attention concentrates in its brief legislative window. So an "
             "early-vintage bill (window in the thin 2022 corpus, and any pre-2022")
    L.append("  advocacy unseen) shows far fewer name-matches than a 2025-era one — use "
             "the by-year facet to see WHO named it and WHEN, not to rank bills by loudness.")
    L.append(f"  Resolve any key:  python skills/lda-corpus-loader/scripts/show_record.py "
             f"<key> --data-root {data_root} --db db/lda_full.duckdb")
    L.append("  Citeable aggregate form: queries/p2_bill_crosscheck.sql")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?")
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--aliases",
                    default=str(Path(__file__).with_name("bill_aliases.json")))
    ap.add_argument("--dataset", default="senate,house,press")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--scan-freetext", action="store_true")
    ap.add_argument("--data-root", default="../data/data")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-aliases", action="store_true")
    args = ap.parse_args()

    meta, aliases = load_aliases(args.aliases)
    if args.list_aliases:
        print(f"bill_aliases.json v{meta['version']} ({meta['generated']}) — "
              f"{len(aliases)} entries\n")
        for a in aliases:
            print(f"  {a['id']:38} {', '.join(a['bills']) or '(phrase-primary)':22} "
                  f"{a['names'][0]}")
        return
    if not args.query:
        ap.error("a bill number or alias is required (or use --list-aliases)")

    datasets = [d.strip() for d in args.dataset.split(",") if d.strip()]
    r = resolve(args.query, aliases)
    con = duckdb.connect(args.db, read_only=True)

    res = {}
    if "senate" in datasets and r["bills"]:
        res["senate_number"] = senate_number(con, r["bills"], args.top, args.limit)
    if "house" in datasets and r["bills"]:
        res["house_number"] = house_number(con, r["bills"], args.top, args.limit)
    if "press" in datasets:
        res["press"] = press_side(con, r["bills"], r["phrases"], args.top, args.limit)

    # Filing free-text name match: auto for phrase-primary bills, else opt-in.
    scanned = None
    if r["phrases"]:
        if not r["bills"]:
            scanned = "auto"
        elif args.scan_freetext:
            scanned = "flag"
    if scanned:
        res["freetext"] = freetext_name(con, r["phrases"], args.limit)

    if args.json:
        print(json.dumps({"query": args.query, "resolved": {
            "kind": r["kind"], "bills": r["bills"], "phrases": r["phrases"],
            "alias_id": r["alias"]["id"] if r["alias"] else None},
            "results": res}, indent=2, default=str))
    else:
        print(render(res, r, datasets, meta, args.data_root,
                     bool(scanned), scanned))
    con.close()


if __name__ == "__main__":
    main()
