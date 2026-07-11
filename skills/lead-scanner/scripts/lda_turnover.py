#!/usr/bin/env python3
"""Quarterly turnover / termination tracker (P3): diff a quarter against the
corpus and report WHO ended representation, WHO hired, which clients SWAPPED
firms, which moved IN-HOUSE (or out of it), and which FIRMS churned the most.
The recurring-beat tool: run it each quarter as new filings post.

Requires: the built DuckDB (lda-corpus-loader) + entity tables
(lda-entity-resolver). Corpus binding — reference/corpus-profile.md:
`period_invariant_key`, `dedup_pick`, `entity_tables`, `canonical_spend_view`,
`primary_for_dollars`.

Method (each rule guards a verified trap; see the profile + queries/p3_turnover.sql):
* Terminations are DECLARED, never inferred: senate filing_type termination
  family '^[1-4](T|TY|@|@Y)$' ("... - Termination [Amendment][, No Activity]").
  Absence-between-quarters is NOT termination — late/partial posting fabricates it.
* Senate-primary. House `form` is only LD1/LD2 — it carries no termination signal.
* Termination = EXISTENCE of a T-family filing in the (pair, quarter) group;
  dollars still dedup on filing_period (latest by posted), so a later amendment
  cannot hide the termination.
* Pair identity = registrant_id x resolved client ENTITY. client_id is
  registrant-scoped AND re-issued on re-registration, so grouping by it
  fabricates "new" engagements for re-registered clients.
* Client-level dollar context reads v_client_canonical_spend (P1), never a
  direct sum of filings.

Usage:
  python lda_turnover.py                # latest quarter in the DB
  python lda_turnover.py 2025Q4         # a specific quarter
  python lda_turnover.py 2025Q4 --top 30 --window 2
  python lda_turnover.py 2025Q4 --json > out/turnover_2025Q4.json

    --db PATH     DuckDB (default db/lda_full.duckdb)
    --top N       rows per section (default 15)
    --window N    swap window in quarters around the termination (default 1)
    --json        machine-readable output (all sections, uncapped by --top)

Reading the output:
* trail4_income = the engagement's deduped income over its last 4 quarters —
  the book of business that ended. NULL income on a new engagement usually
  means registration-only so far (RR filed, first quarterly not yet posted).
* re_engaged > 0: the pair files again AFTER the target quarter (came back) —
  read the termination as a pause, not an exit.
* new_this_q on a termination = hired AND terminated inside one quarter.
* Terminations are seasonal (each Q4 2022-2025 runs 22-43% above that year's
  other quarters as engagements close at year-end — P3a): compare a Q4 to
  prior Q4s, not to Q3.
* The LATEST quarter is a snapshot: terminations post with a lag, so a fresh
  quarter under-counts until the next corpus refresh. The tool warns when the
  target is the newest quarter in the DB.
* Every row carries filing_uuid(s) resolvable via show_record.py. Aggregate
  claims cite queries/p3_turnover.sql (P3a–P3e), not this tool's stdout.
"""

import argparse
import json
import re
import sys

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TERM_RE = "^[1-4](T|TY|@|@Y)$"

QIDX = """(filing_year*4 + CASE filing_period
    WHEN 'first_quarter' THEN 0 WHEN 'second_quarter' THEN 1
    WHEN 'third_quarter' THEN 2 WHEN 'fourth_quarter' THEN 3 END)"""

# Shared engagement base: one row per senate filing with quarter index, the
# resolved client entity key (fallback: normalized raw name), and the resolver
# norm_keys that bridge the registrant/client split (in-house detection, as P1).
PAIRS = f"""
pairs AS (
  SELECT f.*, {QIDX} AS qidx,
         coalesce(ea.entity_id, 'raw:' || upper(trim(f.client_name))) AS ckey,
         coalesce(e.canonical_name, f.client_name) AS c_canon,
         e.norm_key AS c_norm, rn.norm_key AS r_norm
  FROM senate_filings f
  LEFT JOIN entity_aliases ea ON ea.raw_name = f.client_name
       AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id
  LEFT JOIN entity_aliases ra ON ra.raw_name = f.registrant_name
       AND ra.kind='registrant' AND ra.dataset='senate'
  LEFT JOIN entities rn ON rn.entity_id = ra.entity_id)
"""

PERIODS = ["first_quarter", "second_quarter", "third_quarter", "fourth_quarter"]


def parse_quarter(s):
    m = re.fullmatch(r"(\d{4})[-_ ]?Q([1-4])", s.strip(), re.IGNORECASE)
    if not m:
        sys.exit(f"cannot parse quarter {s!r}; use e.g. 2025Q4")
    y, q = int(m.group(1)), int(m.group(2))
    return y * 4 + (q - 1)


def qlabel(qidx):
    return f"{qidx // 4}-Q{qidx % 4 + 1}"


def latest_quarter(con):
    return con.execute(f"SELECT max({QIDX}) FROM senate_filings").fetchone()[0]


def counts_for(con, t):
    """(terminations, new engagements) pair counts for one quarter index."""
    return con.execute(f"""
        WITH {PAIRS},
        term AS (SELECT count(DISTINCT (registrant_id, ckey)) n FROM pairs
                 WHERE regexp_matches(filing_type, '{TERM_RE}') AND qidx = {t}),
        new_p AS (SELECT count(*) n FROM (SELECT 1 FROM pairs
                  GROUP BY registrant_id, ckey HAVING min(qidx) = {t}))
        SELECT term.n, new_p.n FROM term, new_p""").fetchone()


def terminations(con, t):
    return con.execute(f"""
        WITH {PAIRS},
        term AS (
          SELECT registrant_id, ckey, min(registrant_name) registrant,
                 min(c_canon) client, min(filing_uuid) term_uuid
          FROM pairs WHERE regexp_matches(filing_type, '{TERM_RE}') AND qidx = {t}
          GROUP BY 1,2),
        hist AS (
          SELECT registrant_id, ckey, min(qidx) first_q, count(*) n_quarters,
                 sum(income) FILTER (WHERE qidx > {t}-4 AND qidx <= {t}) trail4,
                 count(*) FILTER (WHERE qidx > {t}) re_engaged
          FROM (SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
                QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey,
                  filing_year, filing_period ORDER BY posted DESC, filing_uuid) = 1)
          GROUP BY 1,2)
        SELECT t.registrant, t.client, h.trail4::BIGINT, h.n_quarters,
               h.first_q, h.first_q = {t} AS new_this_q, h.re_engaged, t.term_uuid
        FROM term t JOIN hist h USING (registrant_id, ckey)
        ORDER BY coalesce(h.trail4, 0) DESC, t.client, t.registrant""").fetchall()


def new_engagements(con, t):
    return con.execute(f"""
        WITH {PAIRS},
        firstq AS (
          SELECT registrant_id, ckey, min(registrant_name) registrant,
                 min(c_canon) client,
                 arg_min(filing_uuid, (qidx, filing_uuid)) first_uuid
          FROM pairs GROUP BY 1,2 HAVING min(qidx) = {t}),
        dollars AS (
          SELECT registrant_id, ckey, income, filing_uuid
          FROM pairs WHERE filing_type NOT IN ('RR','RA') AND qidx = {t}
          QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey,
            filing_year, filing_period ORDER BY posted DESC, filing_uuid) = 1),
        terminated AS (   -- also gone in the same quarter?
          SELECT DISTINCT registrant_id, ckey FROM pairs
          WHERE regexp_matches(filing_type, '{TERM_RE}') AND qidx = {t})
        SELECT f.registrant, f.client, d.income::BIGINT,
               coalesce(d.filing_uuid, f.first_uuid) AS cite_uuid,
               d.filing_uuid IS NULL AS registration_only,
               te.registrant_id IS NOT NULL AS term_same_q
        FROM firstq f
        LEFT JOIN dollars d USING (registrant_id, ckey)
        LEFT JOIN terminated te USING (registrant_id, ckey)
        ORDER BY coalesce(d.income, 0) DESC, f.client, f.registrant""").fetchall()


def swaps(con, t, window):
    return con.execute(f"""
        WITH {PAIRS},
        term AS (
          SELECT registrant_id, ckey, min(registrant_name) old_firm,
                 min(c_canon) client, min(c_norm) c_norm,
                 min(r_norm) old_r_norm, min(filing_uuid) term_uuid
          FROM pairs WHERE regexp_matches(filing_type, '{TERM_RE}') AND qidx = {t}
          GROUP BY 1,2),
        hires AS (
          SELECT registrant_id, ckey, min(registrant_name) new_firm,
                 min(r_norm) new_r_norm, min(qidx) first_q,
                 arg_min(filing_uuid, (qidx, filing_uuid)) hire_uuid
          FROM pairs GROUP BY 1,2
          HAVING min(qidx) BETWEEN {t}-{window} AND {t}+{window})
        SELECT te.client, te.old_firm, he.new_firm, he.first_q - {t} AS hire_dq,
               CASE WHEN he.new_r_norm IS NOT NULL AND he.new_r_norm = te.c_norm
                      THEN 'to-inhouse'
                    WHEN te.old_r_norm IS NOT NULL AND te.old_r_norm = te.c_norm
                      THEN 'from-inhouse'
                    ELSE '' END AS move,
               v.canonical_spend::BIGINT AS client_q_spend,
               te.term_uuid, he.hire_uuid
        FROM term te
        JOIN hires he ON he.ckey = te.ckey AND he.registrant_id <> te.registrant_id
        LEFT JOIN v_client_canonical_spend v ON v.client_norm_key = te.c_norm
             AND v.filing_year*4 + CASE v.filing_period
                 WHEN 'first_quarter' THEN 0 WHEN 'second_quarter' THEN 1
                 WHEN 'third_quarter' THEN 2 WHEN 'fourth_quarter' THEN 3 END = {t}
        ORDER BY coalesce(v.canonical_spend, 0) DESC, te.client, te.old_firm,
                 he.new_firm""").fetchall()


def firm_churn(con, t):
    return con.execute(f"""
        WITH {PAIRS},
        dedup AS (
          SELECT * FROM pairs WHERE filing_type NOT IN ('RR','RA')
          QUALIFY row_number() OVER (PARTITION BY registrant_id, ckey,
            filing_year, filing_period ORDER BY posted DESC, filing_uuid) = 1),
        term AS (
          SELECT registrant_id, min(registrant_name) registrant,
                 count(DISTINCT ckey) n_lost, sum(trail4) lost_trail4
          FROM (SELECT p.registrant_id, p.registrant_name, p.ckey,
                  (SELECT sum(d.income) FROM dedup d
                   WHERE d.registrant_id = p.registrant_id AND d.ckey = p.ckey
                     AND d.qidx > {t}-4 AND d.qidx <= {t}) trail4
                FROM pairs p
                WHERE regexp_matches(p.filing_type, '{TERM_RE}') AND p.qidx = {t}
                GROUP BY 1,2,3, trail4)
          GROUP BY 1),
        new_p AS (
          SELECT registrant_id, count(*) n_new
          FROM (SELECT registrant_id, ckey FROM pairs
                GROUP BY 1,2 HAVING min(qidx) = {t})
          GROUP BY 1)
        SELECT coalesce(t.registrant, (SELECT min(registrant_name)
                 FROM pairs p WHERE p.registrant_id = n.registrant_id)) registrant,
               coalesce(t.n_lost, 0), t.lost_trail4::BIGINT,
               coalesce(n.n_new, 0),
               coalesce(n.n_new, 0) - coalesce(t.n_lost, 0) AS net
        FROM term t FULL JOIN new_p n USING (registrant_id)
        ORDER BY coalesce(t.n_lost, 0) + coalesce(n.n_new, 0) DESC,
                 registrant""").fetchall()


def fmt_money(v):
    return f"${v:,.0f}" if v is not None else "·"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("quarter", nargs="?", help="target quarter, e.g. 2025Q4 (default: latest in DB)")
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--window", type=int, default=1)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    con = duckdb.connect(args.db, read_only=True)
    latest = latest_quarter(con)
    t = parse_quarter(args.quarter) if args.quarter else latest

    n_term, n_new = counts_for(con, t)
    prev = counts_for(con, t - 1)
    yoy = counts_for(con, t - 4)
    term_rows = terminations(con, t)
    new_rows = new_engagements(con, t)
    swap_rows = swaps(con, t, args.window)
    firm_rows = firm_churn(con, t)
    con.close()

    n_inhouse = sum(1 for r in swap_rows if r[4])

    if args.json:
        print(json.dumps({
            "quarter": qlabel(t), "db": args.db,
            "is_latest_quarter_in_db": t == latest,
            "summary": {"terminations": n_term, "new_engagements": n_new,
                        "swap_rows": len(swap_rows), "inhouse_moves": n_inhouse,
                        "prev_quarter": {"terminations": prev[0], "new_engagements": prev[1]},
                        "same_quarter_prior_year": {"terminations": yoy[0], "new_engagements": yoy[1]}},
            "terminations": [dict(zip(
                ["registrant", "client", "trail4_income", "n_quarters",
                 "first_seen", "new_this_q", "re_engaged", "term_uuid"],
                (*r[:4], qlabel(r[4]), *r[5:]))) for r in term_rows],
            "new_engagements": [dict(zip(
                ["registrant", "client", "q_income", "cite_uuid",
                 "registration_only", "term_same_q"],
                r)) for r in new_rows],
            "swaps": [dict(zip(
                ["client", "old_firm", "new_firm", "hire_dq", "move",
                 "client_q_canonical_spend", "term_uuid", "hire_uuid"],
                r)) for r in swap_rows],
            "firm_churn": [dict(zip(
                ["registrant", "n_lost", "lost_trail4", "n_new", "net"],
                r)) for r in firm_rows],
        }, indent=1))
        return

    print(f"QUARTERLY TURNOVER · {qlabel(t)} · {args.db} (senate-primary; "
          f"declared terminations only)")
    print(f"  terminations {n_term:,} (prev qtr {prev[0]:,}; same qtr prior yr "
          f"{yoy[0]:,})  ·  new engagements {n_new:,} (prev {prev[1]:,}; "
          f"prior yr {yoy[1]:,})")
    print(f"  firm swaps within ±{args.window} qtr: {len(swap_rows):,} "
          f"({n_inhouse} in-house moves)")
    if t == latest:
        print("  NOTE: this is the newest quarter in the DB — terminations post "
              "with a lag, so counts are a floor until the next corpus refresh.")

    print(f"\nTERMINATIONS (top {args.top} by trailing-4-quarter income; "
          f"{n_term:,} total)")
    for r in term_rows[:args.top]:
        reg, cli, trail4, nq, first_q, new_q, re_eng, uuid = r
        flags = "".join([" [ONE-QUARTER]" if new_q else "",
                         f" [RE-ENGAGED +{re_eng}q]" if re_eng else ""])
        print(f"  {fmt_money(trail4):>12}  {cli[:42]:42} ended w/ {reg[:34]:34} "
              f"{nq:>2}q since {qlabel(first_q)}{flags}  {uuid}")

    print(f"\nNEW ENGAGEMENTS (top {args.top} by first-quarter income; "
          f"{n_new:,} total)")
    for r in new_rows[:args.top]:
        reg, cli, inc, uuid, reg_only, term_q = r
        flag = "".join([" [TERMINATED SAME QTR]" if term_q else "",
                        " [registration only]" if reg_only else ""])
        print(f"  {fmt_money(inc):>12}  {cli[:42]:42} hired {reg[:36]:36}"
              f"{flag}  {uuid}")

    inhouse_rows = [r for r in swap_rows if r[4]]
    firm_swap_rows = [r for r in swap_rows if not r[4]]

    def print_swap(r):
        cli, old, new, dq, move, spend, tu, hu = r
        mv = f" <<{move.upper()}>>" if move else ""
        print(f"  {fmt_money(spend):>12}  {cli[:36]:36} {old[:26]:26} -> "
              f"{new[:26]:26} dq{dq:+d}{mv}  term {tu[:8]} hire {hu[:8]}")

    print(f"\nIN-HOUSE MOVES (all {len(inhouse_rows)}; client canonical spend; "
          f"hire_dq = hire qtr minus {qlabel(t)})")
    for r in inhouse_rows[:args.top]:
        print_swap(r)

    print(f"\nFIRM SWAPS (top {args.top} of {len(firm_swap_rows)} by client "
          f"canonical spend)")
    for r in firm_swap_rows[:args.top]:
        print_swap(r)

    print(f"\nFIRM CHURN SCOREBOARD (top {args.top} by gross churn)")
    print(f"  {'lost':>4} {'lost_trail4$':>13} {'new':>4} {'net':>4}  registrant")
    for r in firm_rows[:args.top]:
        reg, lost, lost4, new_n, net = r
        print(f"  {lost:>4} {fmt_money(lost4):>13} {new_n:>4} {net:>+4}  {reg[:52]}")

    print("\nCiteable aggregate form: queries/p3_turnover.sql (P3a–P3e). "
          "Resolve any uuid via show_record.py.")


if __name__ == "__main__":
    main()
