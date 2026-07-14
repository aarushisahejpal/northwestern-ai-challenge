"""Underlying-record indexes for the healthcare dashboard (2026-07-12, matching
the crypto/pardons/turnover packages' "see the actual filings" pattern).

Writes to data/:
  hc_player_filings.csv        player map: health-coded filings behind each player
                                (same resolved-CTE scope as hc_players.csv)
  hc_trend_filings.csv         main trend widget: filings behind each quarter
                                (same `ded` CTE as hc_quarterly_trend.csv)
  hc_code_trend_filings.csv    issue-mix widget: filings behind each
                                code x quarter cell (same `ded`+join as
                                hc_code_trend.csv's own query)
  hc_press_releases.csv        press widget: matching member releases
  hc_bill_filings.csv          bills widget: filings behind each top bill
  hc_giving_org_items.csv      giving widget (left bars): LD-203 items behind
                                each top-10 giving ORG (hc_ld203_by_org.csv)
  hc_giving_recipient_items.csv giving widget (right bars): LD-203 items behind
                                each displayed RECIPIENT/member row

Every query reuses the exact CTEs export_healthcare.py already ships (same
filters, same dedup rules), so per-widget counts reconcile with the shipped
chart CSVs — checked below, MISMATCH printed if not.

Run from the gain-investigation repo root, AFTER export_healthcare.py and
enhance_giving.py (reads their CSVs + the giving JSONs in
out/packages/_build/inputs).
"""
import csv
import json
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + r"\..\..\_build")
from giving_match import build_index, display_key, first_seen_display, load_members  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
OUT = os.path.join(REPO, "out", "packages", "healthcare", "data")
INPUTS = os.path.join(REPO, "out", "packages", "_build", "inputs")
DB = os.path.join(REPO, "db", "lda_full.duckdb")
CODES = "('HCR','MMM','PHA','MED')"

con = duckdb.connect(DB, read_only=True)


def wcsv(name, cols, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"[csv] {name}: {len(rows)} rows")


def rd(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def loadj(name):
    txt = open(os.path.join(INPUTS, name), encoding="utf-8").read()
    return json.loads(txt[txt.find("{"):])


LDA_FILING = "https://lda.senate.gov/filings/public/filing/{}/print/"
LDA_CONTRIB = "https://lda.senate.gov/filings/public/contribution/{}/print/"

# ---------- 1. player map: health-coded filings per player ----------
Q_PLAYERS = f"""
WITH hc AS (
  SELECT DISTINCT a.filing_uuid FROM senate_activities a
  WHERE a.general_issue_code IN {CODES}),
codes AS (
  SELECT filing_uuid, string_agg(DISTINCT general_issue_code, '; ' ORDER BY general_issue_code) AS health_codes
  FROM senate_activities WHERE general_issue_code IN {CODES} GROUP BY 1),
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name, coalesce(sf.income, sf.expenses)::BIGINT AS amount
  FROM hc JOIN senate_filings sf ON sf.filing_uuid=hc.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%')
SELECT r.player, r.entity_id, r.filing_year, r.filing_period, r.filing_type,
       r.registrant_name, r.amount, coalesce(c.health_codes,'') AS health_codes, r.filing_uuid
FROM resolved r LEFT JOIN codes c ON c.filing_uuid=r.filing_uuid
ORDER BY r.player, r.filing_year, r.filing_period, r.filing_uuid
"""
prows = con.execute(Q_PLAYERS).fetchall()
wcsv("hc_player_filings.csv",
     ["player", "entity_id", "filing_year", "filing_period", "filing_type",
      "registrant_name", "reported_amount", "health_codes", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[8])] for r in prows])
counts = {}
for r in prows:
    counts.setdefault(r[0], set()).add(r[8])
mism = 0
for row in rd("hc_players.csv"):
    want, got = int(row["health_filings"]), len(counts.get(row["player"], ()))
    if want != got:
        mism += 1
        print(f"  MISMATCH players {row['player'][:40]}: hc_players.csv={want} filings={got}")
print("reconciliation vs hc_players.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 2. main trend widget: filings per quarter ----------
Q_TREND = f"""
WITH hc AS (
  SELECT DISTINCT a.filing_uuid FROM senate_activities a
  WHERE a.general_issue_code IN {CODES}),
codes AS (
  SELECT filing_uuid, string_agg(DISTINCT general_issue_code, '; ' ORDER BY general_issue_code) AS health_codes
  FROM senate_activities WHERE general_issue_code IN {CODES} GROUP BY 1),
ded AS (
  SELECT sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf JOIN hc ON hc.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT d.filing_year, d.filing_period, d.player, d.registrant_name, d.amount, d.filing_type,
       coalesce(c.health_codes,'') AS health_codes, d.filing_uuid
FROM ded d LEFT JOIN codes c ON c.filing_uuid=d.filing_uuid
ORDER BY d.filing_year, d.filing_period, d.amount DESC NULLS LAST, d.filing_uuid
"""
trows = con.execute(Q_TREND).fetchall()
wcsv("hc_trend_filings.csv",
     ["filing_year", "filing_period", "player", "registrant_name", "reported_amount",
      "filing_type", "health_codes", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[7])] for r in trows])
per_q = {}
for yr, per, *_ in trows:
    per_q[(str(yr), per)] = per_q.get((str(yr), per), 0) + 1
mism = 0
for row in rd("hc_quarterly_trend.csv"):
    want, got = int(row["health_filings"]), per_q.get((row["filing_year"], row["filing_period"]), 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH trend {row['filing_year']} {row['filing_period']}: trend.csv={want} filings.csv={got}")
print("reconciliation vs hc_quarterly_trend.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 3. issue-mix widget: filings per code x quarter ----------
# Mirrors export_healthcare.py section 3's OWN ded (unrestricted by the `hc`
# CTE — matches on a per-activity-row basis after the amendment dedup, exactly
# like the shipped hc_code_trend.csv).
Q_CODE = f"""
WITH ded AS (
  SELECT sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT a.general_issue_code, d.filing_year, d.filing_period, d.player, d.registrant_name,
       d.amount, d.filing_type, d.filing_uuid
FROM ded d JOIN senate_activities a ON a.filing_uuid=d.filing_uuid
WHERE a.general_issue_code IN {CODES}
ORDER BY a.general_issue_code, d.filing_year, d.filing_period, d.amount DESC NULLS LAST, d.filing_uuid
"""
crows = con.execute(Q_CODE).fetchall()
# a filing can carry >1 activity row under the same code (two distinct issues
# both tagged HCR); de-dup to one row per (code, filing_uuid), matching the
# shipped query's count(DISTINCT d.filing_uuid)
seen_cf, dedup_crows = set(), []
for r in crows:
    k = (r[0], r[7])
    if k in seen_cf:
        continue
    seen_cf.add(k)
    dedup_crows.append(r)
wcsv("hc_code_trend_filings.csv",
     ["general_issue_code", "filing_year", "filing_period", "player", "registrant_name",
      "reported_amount", "filing_type", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[7])] for r in dedup_crows])
per_cq = {}
for code, yr, per, *_ in dedup_crows:
    per_cq[(code, str(yr), per)] = per_cq.get((code, str(yr), per), 0) + 1
mism = 0
for row in rd("hc_code_trend.csv"):
    want = int(row["filings"])
    got = per_cq.get((row["general_issue_code"], row["filing_year"], row["filing_period"]), 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH code_trend {row['general_issue_code']} {row['filing_year']} {row['filing_period']}: "
              f"code_trend.csv={want} filings.csv={got}")
print("reconciliation vs hc_code_trend.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 4. press widget: matching releases ----------
Q_PRESS = f"""
WITH pr AS (
  SELECT p.pr_id, p.date, p.member_name, p.party, p.state, p.chamber, p.title, p.url,
         p.src_file, p.src_line,
         (substr(p.date,1,4) || '-Q' || CAST(ceil(CAST(substr(p.date,6,2) AS INT)/3.0) AS INT)) AS quarter
  FROM press_releases p WHERE p.date >= '2022-01-01'),
tagged AS (
  SELECT pr_id, string_agg(DISTINCT issue_code, '; ' ORDER BY issue_code) AS codes
  FROM press_issue_mentions WHERE issue_code IN {CODES} GROUP BY 1)
SELECT pr.quarter, pr.date, pr.member_name, pr.party, pr.state, pr.chamber, pr.title, pr.url,
       t.codes, pr.src_file, pr.src_line
FROM pr JOIN tagged t ON t.pr_id = pr.pr_id
ORDER BY pr.date, pr.src_file, pr.src_line
"""
prrows = con.execute(Q_PRESS).fetchall()
wcsv("hc_press_releases.csv",
     ["quarter", "date", "member_name", "party", "state", "chamber", "title", "url",
      "issue_codes", "src_file", "src_line"], prrows)
perq = {}
for r in prrows:
    perq[r[0]] = perq.get(r[0], 0) + 1
mism = 0
for row in rd("hc_press_coupling.csv"):
    want, got = int(row["health_releases"]), perq.get(row["quarter"], 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH press {row['quarter']}: coupling.csv={want} releases.csv={got}")
print("reconciliation vs hc_press_coupling.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 5. bills widget: filings behind each top bill ----------
top_bills = [r["bill"] for r in rd("hc_bills.csv")]
ph = ",".join("?" for _ in top_bills)
Q_BILLS = f"""
WITH hc AS (
  SELECT DISTINCT a.filing_uuid FROM senate_activities a
  WHERE a.general_issue_code IN {CODES})
SELECT b.bill, coalesce(e.canonical_name, sf.client_name) AS player, sf.registrant_name,
       sf.filing_year, sf.filing_period, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
       b.record_key AS filing_uuid
FROM bill_mentions b
JOIN hc ON hc.filing_uuid=b.record_key
JOIN senate_filings sf ON sf.filing_uuid=b.record_key
LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
LEFT JOIN entities e ON e.entity_id=ea.entity_id
WHERE b.dataset='senate' AND b.bill IN ({ph})
ORDER BY b.bill, amount DESC NULLS LAST, filing_uuid
"""
brows = con.execute(Q_BILLS, top_bills).fetchall()
# de-dup: a filing can name a bill in >1 activity row (bill_mentions is per-mention)
seen, dedup_brows = set(), []
for r in brows:
    k = (r[0], r[6])
    if k in seen:
        continue
    seen.add(k)
    dedup_brows.append(r)
wcsv("hc_bill_filings.csv",
     ["bill", "player", "registrant_name", "filing_year", "filing_period",
      "reported_amount", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[6])] for r in dedup_brows])
per_bill = {}
for r in dedup_brows:
    per_bill[r[0]] = per_bill.get(r[0], 0) + 1
mism = 0
for row in rd("hc_bills.csv"):
    want, got = int(row["filings"]), per_bill.get(row["bill"], 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH bills {row['bill']}: bills.csv={want} filings.csv={got}")
print("reconciliation vs hc_bills.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 6. giving widget (orgs bars): LD-203 items per top-10 giving org ----------
top_orgs = [r["ld203_filer_org"] for r in rd("hc_ld203_by_org.csv")[:10]]
Q_ORG_ITEMS = """
WITH base AS (
  SELECT c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year, i.contribution_type,
         i.amount, i.payee, i.honoree, i.date, i.contributor_name, c.filing_uuid,
         rtrim(upper(trim(coalesce(nullif(i.honoree,''), i.payee, ''))), ' ,.') AS recipient
  FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
  WHERE c.registrant_name = ANY(?)),
dd AS (
  SELECT registrant_name, lobbyist_name, filer_type, filing_year, contribution_type, amount,
         payee, honoree, date, contributor_name, recipient,
         min(filing_uuid) AS filing_uuid, count(DISTINCT filing_uuid) AS n_versions
  FROM base GROUP BY ALL)
SELECT registrant_name, recipient, date, amount::BIGINT, contribution_type, filer_type,
       n_versions, filing_uuid
FROM dd ORDER BY registrant_name, amount DESC NULLS LAST, date
"""
orgitems = con.execute(Q_ORG_ITEMS, [top_orgs]).fetchall()
wcsv("hc_giving_org_items.csv",
     ["ld203_filer_org", "recipient", "date", "amount", "contribution_type", "filer_type",
      "n_amendment_versions", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_CONTRIB.format(r[7])] for r in orgitems])
sums = {}
for r in orgitems:
    sums[r[0]] = sums.get(r[0], 0) + (r[3] or 0)
mism = 0
for row in rd("hc_ld203_by_org.csv")[:10]:
    want = float(row["disclosed_giving_total"])
    got = sums.get(row["ld203_filer_org"], 0)
    if abs(got - want) > 1:
        mism += 1
        print(f"  MISMATCH org items {row['ld203_filer_org'][:40]!r}: by_org.csv={want:,.0f} items={got:,.0f}")
print("reconciliation vs hc_ld203_by_org.csv (top 10):", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 7. giving widget (recipient/member bars): LD-203 items ----------
mem_by_last = build_index(load_members(DB))
split = rd("hc_ld203_recipients_split.csv")
for r in split:
    r["_a"] = float(r["from_health_focused"] or 0)
    r["_b"] = float(r["from_mixed_diversified"] or 0)
members = [r for r in split if r["party"]]
displayed = {r["recipient"]: r for r in
             sorted(split, key=lambda r: -(r["_a"] + r["_b"]))[:10]
             + sorted(members, key=lambda r: -(r["_a"] + r["_b"]))[:12]}
print(f"  giving: {len(displayed)} displayed recipient rows")

foc = loadj("hc_giving_focused.json")
mix = loadj("hc_giving_mixed.json")
con.execute("CREATE OR REPLACE TEMP TABLE _reg(name TEXT, slice TEXT)")
con.executemany("INSERT INTO _reg VALUES (?, ?)",
                [(n, "health_focused") for n in foc["ld203_filer_names"]]
                + [(n, "mixed_diversified") for n in mix["ld203_filer_names"]])
Q_RECIP_ITEMS = """
WITH base AS (
  SELECT r.slice, c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
         i.contribution_type, i.amount, i.payee, i.honoree, i.date, i.contributor_name,
         c.filing_uuid,
         rtrim(upper(trim(coalesce(nullif(i.honoree,''), i.payee, ''))), ' ,.') AS recipient
  FROM senate_contributions c JOIN senate_contribution_items i USING (filing_uuid)
  JOIN _reg r ON c.registrant_name = r.name),
dd AS (
  SELECT slice, registrant_name, lobbyist_name, filer_type, filing_year, contribution_type,
         amount, payee, honoree, date, contributor_name, recipient,
         min(filing_uuid) AS filing_uuid, count(DISTINCT filing_uuid) AS n_versions
  FROM base GROUP BY ALL)
SELECT slice, registrant_name, filer_type, recipient, date, amount::BIGINT,
       contribution_type, n_versions, filing_uuid
FROM dd
"""
ritems = con.execute(Q_RECIP_ITEMS).fetchall()
# key -> winning display text, replicating enhance_giving.py's first-seen-wins
# merge (recipients lists are already sorted by total DESC, same as the tool)
key_to_disp = first_seen_display(mem_by_last,
                                  [foc["results"]["recipients"], mix["results"]["recipients"]])
out_rows, sums = [], {}
for slice_, reg, ftype, recip, date, amt, ctype, nver, uuid in ritems:
    key, _ = display_key(mem_by_last, recip)
    disp = key_to_disp.get(key)
    if disp is None or disp not in displayed:
        continue
    out_rows.append([disp, slice_, recip, reg, ftype, date, amt, ctype, nver, uuid,
                      LDA_CONTRIB.format(uuid)])
    sums[(disp, slice_)] = sums.get((disp, slice_), 0) + (amt or 0)
out_rows.sort(key=lambda r: (r[0], r[1], -(r[6] or 0)))
wcsv("hc_giving_recipient_items.csv",
     ["display_row", "giver_slice", "recipient_raw", "ld203_filer_org", "filer_type", "date",
      "amount", "contribution_type", "n_amendment_versions", "filing_uuid", "lda_public_url"],
     out_rows)
mism = 0
for disp, r in displayed.items():
    for slice_, want in (("health_focused", r["_a"]), ("mixed_diversified", r["_b"])):
        got = sums.get((disp, slice_), 0)
        if abs(got - want) > 1:
            mism += 1
            print(f"  MISMATCH recipient items {disp[:40]!r} {slice_}: split={want:,.0f} items={got:,.0f}")
print("reconciliation vs hc_ld203_recipients_split.csv (displayed rows):",
      "OK" if mism == 0 else f"{mism} MISMATCHES (explain before shipping)")

con.close()
print("\nDONE")
