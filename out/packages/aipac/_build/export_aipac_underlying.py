"""Underlying-record indexes for the AIPAC dashboard (2026-07-12, matching the
crypto/pardons/turnover packages' "see the actual filings" pattern).

Writes to data/:
  aipac_press_releases.csv        press widget: matching member releases
  aipac_gov_entity_filings.csv    "who is lobbied" widget: filings naming
                                   each government entity
  aipac_bill_filings.csv          bills widget: AIPAC's own filings naming
                                   each top bill
  aipac_colobby_filings.csv       co-lobbyists widget: the shared-bill filings
                                   behind each displayed co-lobbyist
  aipac_israel_player_filings.csv Israel-policy field widget: filings behind
                                   each displayed player
  aipac_lobbyist_filings.csv      team widget: filings each lobbyist appears on
  aipac_giving_items.csv          giving widget: LD-203 items behind every
                                   recipient AND every year bar (single filer:
                                   AIPAC self-files, so one registrant scope)

Every query reuses the exact scope/filters export_aipac.py already ships, so
per-widget counts reconcile with the shipped chart CSVs — checked below.

Run from the gain-investigation repo root, AFTER export_aipac.py and
enhance_giving.py (reads aipac_giving_deep.json in
out/packages/_build/inputs, refreshed 2026-07-12 with --top 999999 — the
2026-07-08 snapshot was capped at the top 400 recipients, a known truncation
trap already fixed once for crypto; see out/packages/healthcare/_build/
export_healthcare_underlying.py's header for the twin of this fix).
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
OUT = os.path.join(REPO, "out", "packages", "aipac", "data")
INPUTS = os.path.join(REPO, "out", "packages", "_build", "inputs")
DB = os.path.join(REPO, "db", "lda_full.duckdb")
AIPAC = "upper(registrant_name) LIKE '%AMERICAN ISRAEL PUBLIC AFFAIRS%'"
ISRAEL_RE = r"\b(israel|israeli|israelis|antisemitism|anti-semitism|abraham accords|gaza|hamas|hezbollah|iron dome|west bank|palestinian|palestine|golan heights|jerusalem)\b"

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

# ---------- 1. press widget: matching releases ----------
Q_PRESS = f"""
WITH pr AS (
  SELECT p.pr_id, p.date, p.member_name, p.party, p.state, p.chamber, p.title, p.text,
         p.url, p.src_file, p.src_line,
         (substr(p.date,1,4) || '-Q' || CAST(ceil(CAST(substr(p.date,6,2) AS INT)/3.0) AS INT)) AS quarter
  FROM press_releases p WHERE p.date >= '2022-01-01')
SELECT quarter, date, member_name, party, state, chamber, title, url, src_file, src_line
FROM pr
WHERE regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')), '{ISRAEL_RE}')
ORDER BY date, src_file, src_line
"""
prows = con.execute(Q_PRESS).fetchall()
wcsv("aipac_press_releases.csv",
     ["quarter", "date", "member_name", "party", "state", "chamber", "title", "url",
      "src_file", "src_line"], prows)
perq = {}
for r in prows:
    perq[r[0]] = perq.get(r[0], 0) + 1
mism = 0
for row in rd("aipac_press_coupling.csv"):
    want, got = int(row["israel_releases"]), perq.get(row["quarter"], 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH press {row['quarter']}: coupling.csv={want} releases.csv={got}")
print("reconciliation vs aipac_press_coupling.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 2. "who is lobbied" widget: filings naming each gov entity ----------
Q_GOV = f"""
SELECT g.entity_name, f.filing_year, f.filing_period,
       coalesce(f.income, f.expenses)::BIGINT AS amount, f.filing_uuid
FROM senate_gov_entities g JOIN senate_filings f USING (filing_uuid)
WHERE {AIPAC}
ORDER BY g.entity_name, f.filing_year, f.filing_period, f.filing_uuid
"""
grows = con.execute(Q_GOV).fetchall()
wcsv("aipac_gov_entity_filings.csv",
     ["entity_name", "filing_year", "filing_period", "reported_amount", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[4])] for r in grows])
per_ge = {}
for r in grows:
    per_ge[r[0]] = per_ge.get(r[0], 0) + 1
mism = 0
for row in rd("aipac_gov_entities.csv"):
    want, got = int(row["mentions"]), per_ge.get(row["entity_name"], 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH gov entity {row['entity_name']}: gov_entities.csv={want} filings.csv={got}")
print("reconciliation vs aipac_gov_entities.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 3. bills widget: AIPAC's own filings naming each bill ----------
Q_BILLS = f"""
WITH af AS (SELECT filing_uuid, filing_year, filing_period,
                    coalesce(income, expenses)::BIGINT AS amount
            FROM senate_filings WHERE {AIPAC})
SELECT b.bill, af.filing_year, af.filing_period, af.amount, b.record_key AS filing_uuid
FROM bill_mentions b JOIN af ON af.filing_uuid = b.record_key
WHERE b.dataset='senate'
ORDER BY b.bill, af.filing_year, af.filing_period, b.record_key
"""
bill_rows = con.execute(Q_BILLS).fetchall()
seen, dedup_bill_rows = set(), []
for r in bill_rows:
    k = (r[0], r[4])
    if k in seen:
        continue
    seen.add(k)
    dedup_bill_rows.append(r)
wcsv("aipac_bill_filings.csv",
     ["bill", "filing_year", "filing_period", "reported_amount", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[4])] for r in dedup_bill_rows])
per_bill = {}
for r in dedup_bill_rows:
    per_bill[r[0]] = per_bill.get(r[0], 0) + 1
mism = 0
for row in rd("aipac_bills.csv"):
    want, got = int(row["aipac_filings"]), per_bill.get(row["bill"], 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH bills {row['bill']}: bills.csv={want} filings.csv={got}")
print("reconciliation vs aipac_bills.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 4. co-lobbyists widget: shared-bill filings per displayed client ----------
top_colobby = [r["client"] for r in rd("aipac_bill_colobbyists.csv")[:15]]
Q_COLOBBY = f"""
WITH af AS (SELECT filing_uuid FROM senate_filings WHERE {AIPAC}),
aipac_bills AS (
  SELECT DISTINCT b.bill FROM bill_mentions b JOIN af ON af.filing_uuid=b.record_key
  WHERE b.dataset='senate'),
bill_pop AS (
  SELECT b.bill, count(DISTINCT sf.client_id||'|'||sf.registrant_id) AS n_engagements
  FROM bill_mentions b JOIN senate_filings sf ON sf.filing_uuid=b.record_key
  WHERE b.dataset='senate' AND b.bill IN (SELECT bill FROM aipac_bills)
  GROUP BY 1),
distinctive AS (SELECT bill FROM bill_pop WHERE n_engagements <= 200)
SELECT coalesce(e.canonical_name, sf.client_name) AS client, b.bill, sf.registrant_name,
       sf.filing_year, sf.filing_period, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
       b.record_key AS filing_uuid
FROM bill_mentions b
JOIN senate_filings sf ON sf.filing_uuid=b.record_key
LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
LEFT JOIN entities e ON e.entity_id=ea.entity_id
WHERE b.dataset='senate' AND b.bill IN (SELECT bill FROM distinctive)
  AND upper(sf.registrant_name) NOT LIKE '%AMERICAN ISRAEL PUBLIC AFFAIRS%'
  AND coalesce(e.canonical_name, sf.client_name) = ANY(?)
ORDER BY client, b.bill, filing_uuid
"""
co_rows = con.execute(Q_COLOBBY, [top_colobby]).fetchall()
seen, dedup_co_rows = set(), []
for r in co_rows:
    k = (r[0], r[1], r[6])
    if k in seen:
        continue
    seen.add(k)
    dedup_co_rows.append(r)
wcsv("aipac_colobby_filings.csv",
     ["client", "bill", "registrant_name", "filing_year", "filing_period",
      "reported_amount", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[6])] for r in dedup_co_rows])
per_client_filings, per_client_bills = {}, {}
for r in dedup_co_rows:
    per_client_filings[r[0]] = per_client_filings.get(r[0], 0) + 1
    per_client_bills.setdefault(r[0], set()).add(r[1])
mism = 0
for row in rd("aipac_bill_colobbyists.csv")[:15]:
    want_f, got_f = int(float(row["filings_on_those_bills"])), per_client_filings.get(row["client"], 0)
    want_b, got_b = int(row["shared_distinctive_bills"]), len(per_client_bills.get(row["client"], ()))
    if want_f != got_f or want_b != got_b:
        mism += 1
        print(f"  MISMATCH colobby {row['client'][:40]}: colobbyists.csv=({want_b}b,{want_f}f) filings.csv=({got_b}b,{got_f}f)")
print("reconciliation vs aipac_bill_colobbyists.csv (top 15):", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 5. Israel-policy field widget: filings behind each player ----------
Q_ISRAEL = f"""
WITH hits AS (
  SELECT DISTINCT record_key FROM lobbying_freetext
  WHERE dataset='senate' AND regexp_matches(lower(txt), '{ISRAEL_RE}')),
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id,'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year, sf.filing_period, sf.filing_type,
         sf.registrant_name, coalesce(sf.income, sf.expenses)::BIGINT AS amount
  FROM hits h JOIN senate_filings sf ON sf.filing_uuid=h.record_key
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL)
SELECT player, entity_id, filing_year, filing_period, filing_type, registrant_name, amount, filing_uuid
FROM resolved
ORDER BY player, filing_year, filing_period, filing_uuid
"""
irows = con.execute(Q_ISRAEL).fetchall()
wcsv("aipac_israel_player_filings.csv",
     ["player", "entity_id", "filing_year", "filing_period", "filing_type", "registrant_name",
      "reported_amount", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[7])] for r in irows])
per_p = {}
for r in irows:
    per_p.setdefault(r[0], set()).add(r[7])
mism = 0
for row in rd("israel_policy_players.csv"):
    want, got = int(row["israel_filings"]), len(per_p.get(row["player"], ()))
    if want != got:
        mism += 1
        print(f"  MISMATCH israel player {row['player'][:40]}: players.csv={want} filings.csv={got}")
print("reconciliation vs israel_policy_players.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 6. team widget: filings per lobbyist ----------
Q_LOB = f"""
SELECT l.first_name, l.last_name, f.filing_year, f.filing_period, f.filing_uuid
FROM senate_lobbyists l JOIN senate_filings f USING (filing_uuid)
WHERE {AIPAC}
ORDER BY l.last_name, l.first_name, f.filing_year, f.filing_period, f.filing_uuid
"""
lrows = con.execute(Q_LOB).fetchall()
# senate_lobbyists carries one row per (filing, ACTIVITY) — a lobbyist named on
# a 3-activity filing appears 3 times; de-dup to one row per (lobbyist, filing)
seen_l, dedup_lrows = set(), []
for r in lrows:
    k = (r[0], r[1], r[4])
    if k in seen_l:
        continue
    seen_l.add(k)
    dedup_lrows.append(r)
wcsv("aipac_lobbyist_filings.csv",
     ["first_name", "last_name", "filing_year", "filing_period", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[4])] for r in dedup_lrows])
per_l = {}
for r in dedup_lrows:
    per_l[(r[0], r[1])] = per_l.get((r[0], r[1]), 0) + 1
mism = 0
for row in rd("aipac_lobbyists.csv"):
    want = int(row["filings"])
    got = per_l.get((row["first_name"], row["last_name"]), 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH lobbyist {row['first_name']} {row['last_name']}: lobbyists.csv={want} filings.csv={got}")
print("reconciliation vs aipac_lobbyists.csv:", "OK" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 7. giving widget: LD-203 items (recipients + by-year) ----------
mem_by_last = build_index(load_members(DB))
deep = loadj("aipac_giving_deep.json")
Q_ITEMS = """
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
SELECT filing_year, recipient, date, amount::BIGINT, contribution_type, filer_type,
       n_versions, filing_uuid
FROM dd
"""
items = con.execute(Q_ITEMS, [deep["ld203_filer_names"]]).fetchall()
key_to_disp = first_seen_display(mem_by_last, [deep["results"]["recipients"]])
out_rows = []
sums_recip, sums_year = {}, {}
for yr, recip, date, amt, ctype, ftype, nver, uuid in items:
    key, _ = display_key(mem_by_last, recip)
    disp = key_to_disp.get(key, "")
    out_rows.append([yr, disp, recip, date, amt, ctype, ftype, nver, uuid,
                      LDA_CONTRIB.format(uuid)])
    if disp:
        sums_recip[disp] = sums_recip.get(disp, 0) + (amt or 0)
    sums_year[yr] = sums_year.get(yr, 0) + (amt or 0)
wcsv("aipac_giving_items.csv",
     ["filing_year", "recipient_display", "recipient_raw", "date", "amount", "contribution_type",
      "filer_type", "n_amendment_versions", "filing_uuid", "lda_public_url"],
     out_rows)
mism = 0
for row in rd("aipac_ld203_recipients.csv")[:15]:
    want, got = float(row["total"]), sums_recip.get(row["recipient"], 0)
    if abs(got - want) > 1:
        mism += 1
        print(f"  MISMATCH recipient {row['recipient'][:40]!r}: recipients.csv={want:,.0f} items={got:,.0f}")
for row in rd("aipac_ld203_by_year.csv"):
    want, got = float(row["total"]), sums_year.get(int(row["filing_year"]), 0)
    if abs(got - want) > 1:
        mism += 1
        print(f"  MISMATCH year {row['filing_year']}: by_year.csv={want:,.0f} items={got:,.0f}")
print("reconciliation vs aipac_ld203_recipients.csv (top 15) + aipac_ld203_by_year.csv:",
      "OK" if mism == 0 else f"{mism} MISMATCHES")

con.close()
print("\nDONE")
