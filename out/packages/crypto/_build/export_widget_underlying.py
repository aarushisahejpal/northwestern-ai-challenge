"""Underlying-record indexes for the remaining crypto-dashboard widgets
(2026-07-10, Rob's ask: every widget should let the user see the actual
underlying filings/records with links).

Writes four CSVs to data/, each mirroring ITS widget's exact semantics and
reconciling against the widget's own numbers where the grain allows:

  crypto_issue_code_filings.csv   scatter widget: senate filings behind each
                                  issue code's crypto-tagged text blocks
                                  (the chart counts BLOCKS across both chambers;
                                  block counts per code carried for honesty)
  crypto_spend_quarters.csv       money widget: v_client_canonical_spend rows
                                  for every mapped player (the per-quarter
                                  audit of each spend bar)
  crypto_ld203_items.csv          giving widget: the amendment-deduped LD-203
                                  items behind every DISPLAYED recipient row,
                                  keyed to the row label, each item linking to
                                  lda.senate.gov/filings/public/contribution/
  crypto_press_releases.csv       press widget: every crypto-matching member
                                  release with its URL + src_file:src_line key

Run from the gain-investigation repo root, AFTER export_crypto.py (reads its
CSVs + the giving JSONs in ../_build/inputs).
"""
import csv
import json
import os
import re
import sys

import duckdb

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
OUT = os.path.join(REPO, "out", "packages", "crypto", "data")
INPUTS = os.path.join(REPO, "out", "packages", "_build", "inputs")

con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)


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

# ---------- 1. scatter widget: senate filings per issue code ----------
# The chart counts crypto-tagged TEXT BLOCKS (both chambers). This index lists
# the SENATE filings behind each code (house copies are mirrors; only senate
# filings have a stable public URL), with per-filing block counts so the two
# grains reconcile: sum(n_blocks) per code == the code's senate-side block count.
Q_SCATTER = """
WITH cd AS (
  SELECT DISTINCT lim.doc_id, coalesce(lf.issue_code,'(none)') AS issue_code,
         lim.dataset, lim.record_key, lim.keyword
  FROM lobbying_issue_mentions lim JOIN lobbying_freetext lf USING (doc_id)
  WHERE lim.tag='CRYPTO'),
sen AS (
  SELECT issue_code, record_key AS filing_uuid, count(DISTINCT doc_id) AS n_blocks,
         string_agg(DISTINCT keyword, '; ') AS matched_keywords
  FROM cd WHERE dataset='senate' GROUP BY 1, 2)
SELECT DISTINCT s.issue_code,
       coalesce(e.canonical_name, sf.client_name) AS player,
       sf.registrant_name, sf.filing_year, sf.filing_period,
       coalesce(sf.income, sf.expenses)::BIGINT AS reported_amount,
       s.n_blocks, s.matched_keywords, s.filing_uuid
FROM sen s
JOIN senate_filings sf ON sf.filing_uuid = s.filing_uuid
LEFT JOIN entity_aliases ea ON ea.raw_name = sf.client_name
     AND ea.kind='client' AND ea.dataset='senate'
LEFT JOIN entities e ON e.entity_id = ea.entity_id
ORDER BY s.issue_code, reported_amount DESC NULLS LAST, s.filing_uuid
"""
rows = con.execute(Q_SCATTER).fetchall()
wcsv("crypto_issue_code_filings.csv",
     ["issue_code", "player", "registrant_name", "filing_year", "filing_period",
      "reported_amount", "n_crypto_blocks_in_filing", "matched_keywords",
      "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_FILING.format(r[8])] for r in rows])

# ---------- 2. money widget: canonical-spend quarters per player ----------
Q_SPEND = """
WITH players AS (
  SELECT DISTINCT coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM (SELECT DISTINCT record_key FROM lobbying_issue_mentions
        WHERE tag='CRYPTO' AND dataset='senate') t
  JOIN senate_filings sf ON sf.filing_uuid = t.record_key
  LEFT JOIN entity_aliases ea ON ea.raw_name = sf.client_name
       AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id = ea.entity_id
  WHERE sf.client_name IS NOT NULL)
SELECT p.player, v.client_entity_id, v.filing_year, v.filing_period,
       v.has_inhouse_filing, v.inhouse_amount::BIGINT, v.outside_amount::BIGINT,
       v.canonical_spend::BIGINT, v.method, v.n_filings
FROM players p JOIN v_client_canonical_spend v ON v.client_entity_id = p.entity_id
ORDER BY p.player, v.filing_year, v.filing_period
"""
rows = con.execute(Q_SPEND).fetchall()
wcsv("crypto_spend_quarters.csv",
     ["player", "entity_id", "filing_year", "filing_period", "has_inhouse_filing",
      "inhouse_amount", "outside_amount", "canonical_spend", "method", "n_filings"],
     rows)
# reconcile: per-player sum(canonical) == crypto_players.csv total_all_issue_spend
tot = {}
for r in rows:
    tot[r[0]] = tot.get(r[0], 0) + (r[7] or 0)
mism = 0
for p in rd("crypto_players.csv"):
    want = p["total_all_issue_spend"]
    if not want:
        continue
    if abs(tot.get(p["player"], 0) - float(want)) > 1:
        mism += 1
        print(f"  MISMATCH spend {p['player'][:40]}: players.csv={want} quarters={tot.get(p['player'])}")
print("reconciliation vs crypto_players.csv spend:",
      "OK — every player's quarter rows sum to its spend" if mism == 0 else f"{mism} MISMATCHES")

# ---------- 3. giving widget: LD-203 items behind the displayed rows ----------
# Displayed rows (same selection as viz_build): top-10 recipients by combined
# giving + top-10 members by native + top-10 members by diversified. Member
# rows map to raw filed strings via the shipped variant-audit CSV; org rows and
# the Trump merge re-derive the same norm-key grouping enhance_giving used.
TITLE_RE = re.compile(r"^(SEN\.?|SENATOR|REP\.?|REPRESENTATIVE|CONGRESSMAN|CONGRESSWOMAN|HON\.?|SPEAKER|LEADER)\s+", re.I)
ORG_ALIASES = {"DEMOCRATICSENATORIALCAMPAIGNCOMMITTEE": "DSCC",
               "DEMOCRATICCONGRESSIONALCAMPAIGNCOMMITTEE": "DCCC",
               "NATIONALREPUBLICANSENATORIALCOMMITTEE": "NRSC",
               "NATIONALREPUBLICANCONGRESSIONALCOMMITTEE": "NRCC"}


def norm_key(recipient):
    r = TITLE_RE.sub("", recipient.strip().upper())
    k = re.sub(r"[^A-Z0-9]", "", r)
    k = re.sub(r"(INC|LLC)$", "", k)
    return ORG_ALIASES.get(k, k)


split = rd("crypto_ld203_recipients_split.csv")
for r in split:
    r["_a"] = float(r["from_crypto_native"] or 0)
    r["_b"] = float(r["from_diversified_forward"] or 0)
    r["_c"] = float(r["from_ambient_lowshare"] or 0)
members = [r for r in split if r["party"]]
displayed = {r["recipient"]: r for r in
             sorted(split, key=lambda r: -(r["_a"] + r["_b"] + r["_c"]))[:10]
             + sorted(members, key=lambda r: -r["_a"])[:10]
             + sorted(members, key=lambda r: -r["_b"])[:10]}
print(f"  giving: {len(displayed)} displayed rows")

# display row -> set of raw variant strings
variants = {}  # (display, slice) -> set(raw)
aud = rd("crypto_ld203_member_variant_audit.csv")
for row in aud:
    disp = row["member (merged row in the split CSV)"]
    if disp in displayed:
        variants.setdefault((disp, row["giver_slice"]), set()).add(
            row["raw_recipient_string_as_filed"])
J = {"crypto_native": loadj("crypto_giving_pureplay.json"),
     "diversified_forward": loadj("crypto_giving_div_forward.json"),
     "ambient_lowshare": loadj("crypto_giving_div_ambient.json")}
org_rows = {d: r for d, r in displayed.items() if not r["party"]}
for disp, r in org_rows.items():
    if disp.startswith("Trump-Vance Inaugural"):
        match = lambda raw: "TRUMP" in raw.upper()
    else:
        want_key = norm_key(disp)
        match = lambda raw, wk=want_key: norm_key(raw) == wk
    for sl, j in J.items():
        for it in j["results"].get("recipients", []):
            raw = it["recipient"].strip()
            if raw.upper() != "N/A" and match(raw):
                variants.setdefault((disp, sl), set()).add(raw.upper().rstrip(" ,."))

con.execute("CREATE OR REPLACE TEMP TABLE _reg(name TEXT, slice TEXT)")
for sl, j in J.items():
    con.executemany("INSERT INTO _reg VALUES (?, ?)",
                    [(n, sl) for n in j.get("ld203_filer_names", [])])
con.execute("CREATE OR REPLACE TEMP TABLE _want(display TEXT, slice TEXT, recipient TEXT)")
con.executemany("INSERT INTO _want VALUES (?, ?, ?)",
                [(d, sl, raw) for (d, sl), raws in variants.items() for raw in raws])

# kept in sync with lda_ld203_giving.py's BASE/dd (amendment-dedup on the full
# contribution identity); min(filing_uuid) supplies ONE citable filed version
Q_ITEMS = """
WITH base AS (
  SELECT r.slice, c.registrant_name, c.lobbyist_name, c.filer_type, c.filing_year,
         i.contribution_type, i.amount, i.payee, i.honoree, i.date, i.contributor_name,
         c.filing_uuid,
         rtrim(upper(trim(coalesce(nullif(i.honoree,''), i.payee, ''))), ' ,.') AS recipient
  FROM senate_contributions c
  JOIN senate_contribution_items i USING (filing_uuid)
  JOIN _reg r ON c.registrant_name = r.name),
dd AS (
  SELECT slice, registrant_name, lobbyist_name, filer_type, filing_year,
         contribution_type, amount, payee, honoree, date, contributor_name, recipient,
         min(filing_uuid) AS filing_uuid, count(DISTINCT filing_uuid) AS n_versions
  FROM base
  GROUP BY ALL)
SELECT w.display, d.slice, d.recipient, d.registrant_name, d.filer_type,
       d.contributor_name, d.date, d.amount::BIGINT, d.contribution_type,
       d.n_versions, d.filing_uuid
FROM dd d JOIN _want w ON w.slice = d.slice AND w.recipient = d.recipient
ORDER BY w.display, d.slice, d.amount DESC NULLS LAST, d.date
"""
items = con.execute(Q_ITEMS).fetchall()
wcsv("crypto_ld203_items.csv",
     ["display_row", "giver_slice", "recipient_raw", "ld203_filer_org", "filer_type",
      "contributor_name", "date", "amount", "contribution_type",
      "n_amendment_versions", "filing_uuid", "lda_public_url"],
     [list(r) + [LDA_CONTRIB.format(r[10])] for r in items])
# reconcile item sums vs the split CSV totals per displayed row+slice
sums = {}
for r in items:
    sums[(r[0], r[1])] = sums.get((r[0], r[1]), 0) + (r[7] or 0)
mism = 0
for disp, r in displayed.items():
    for sl, want in (("crypto_native", r["_a"]), ("diversified_forward", r["_b"]),
                     ("ambient_lowshare", r["_c"])):
        got = sums.get((disp, sl), 0)
        if abs(got - want) > 1:
            mism += 1
            print(f"  MISMATCH items {disp[:40]!r} {sl}: split={want:,.0f} items={got:,.0f}")
print("reconciliation vs crypto_ld203_recipients_split.csv:",
      "OK — every displayed row's items sum to its chart figure"
      if mism == 0 else f"{mism} MISMATCHES (explain before shipping)")

# ---------- 4. press widget: the matching releases ----------
Q_PRESS = r"""
SELECT (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
       date, member_name, party, state, chamber, title, url,
       src_file, src_line
FROM press_releases
WHERE date >= '2022-01-01'
  AND regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')),
      '\b(crypto|cryptocurrency|cryptocurrencies|stablecoin|stablecoins|digital asset|digital assets|bitcoin|blockchain|central bank digital currency|cbdc)\b')
ORDER BY date, src_file, src_line
"""
prows = con.execute(Q_PRESS).fetchall()
wcsv("crypto_press_releases.csv",
     ["quarter", "date", "member_name", "party", "state", "chamber", "title", "url",
      "src_file", "src_line"], prows)
perq = {}
for r in prows:
    perq[r[0]] = perq.get(r[0], 0) + 1
mism = 0
for row in rd("crypto_press_quarterly.csv"):
    want = int(row["crypto_releases"])
    got = perq.get(row["quarter"], 0)
    if want != got:
        mism += 1
        print(f"  MISMATCH press {row['quarter']}: quarterly.csv={want} releases.csv={got}")
print("reconciliation vs crypto_press_quarterly.csv:",
      "OK — every quarter's release count matches the chart"
      if mism == 0 else f"{mism} MISMATCHES")

con.close()
print("\nDONE")
