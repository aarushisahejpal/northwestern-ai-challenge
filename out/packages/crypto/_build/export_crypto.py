"""Crypto package exporter — from-scratch derivation (2026-07-08).
Reads db/lda_full.duckdb (read-only) + the three tool JSONs in scratchpad,
writes CSV flat files to out/packages/crypto/data/.
Run from the gain-investigation repo root.

Discipline: senate-primary (never sum chambers); filings deduped on
(registrant_id, client_id, filing_year, filing_period) latest-by-posted;
registrations (filing_type R*) excluded from dollar work; client spend only
via v_client_canonical_spend (P1); per-item dollars are ranking signals.
"""
import duckdb, json, csv, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
S = os.path.join(REPO, "out", "packages", "_build", "inputs")  # durable tool-JSON copies (was: the 2026-07-08 session scratchpad)
OUT = os.path.join(REPO, "out", "packages", "crypto", "data")
os.makedirs(OUT, exist_ok=True)

con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)

def wcsv(name, cols, rows):
    p = os.path.join(OUT, name)
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"[csv] {name}: {len(rows)} rows")

def sql_csv(name, q):
    cur = con.execute(q)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    wcsv(name, cols, rows)
    return cols, rows

def loadj(p):
    txt = open(p, encoding="utf-8").read()
    return json.loads(txt[txt.find("{"):])

NAME_VIS = r"(?i)\b(crypto|cryptocurrenc|blockchain|bitcoin|digital asset|stablecoin|defi|web3|digital currenc|coin center|dogecoin|ethereum|solana|ripple)"

# ---------- 1. players (senate-side, entity-resolved, tiered + intensity) ----------
# acts CTE = the crypto ACTIVITY-SHARE metric (2026-07-11, Rob-approved): share of a
# client's senate free-text activity blocks that are crypto-tagged. Mirrors the
# healthcare package's activity-share semantics (a self-filer's single quarterly lists
# dozens of blocks, so filing-level share reads ~100% for every mega-filer; block-level
# share is the honest intensity signal). Numerator = curated-lexicon tags; denominator =
# all the client's senate blocks, registrations excluded. Share is ENTITY-grain — known
# resolver-split families (Mastercard x3, Visa x2, a16z…) each carry their own share.
q_players = f"""
WITH crypto_clients AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='CRYPTO' AND lim.dataset='senate'),
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year
  FROM crypto_clients c
  JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL),
players AS (
  SELECT entity_id, any_value(player) AS player,
         count(DISTINCT filing_uuid) AS crypto_filings_senate,
         min(filing_year) AS first_year, max(filing_year) AS last_year
  FROM resolved GROUP BY 1),
acts AS (
  SELECT coalesce(ea.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         count(*) AS all_activity_blocks,
         count(t.record_key) AS crypto_activity_blocks
  FROM senate_filings sf
  JOIN lobbying_freetext lf ON lf.record_key = sf.filing_uuid AND lf.dataset='senate'
  LEFT JOIN (SELECT DISTINCT raw_name, entity_id FROM entity_aliases
             WHERE kind='client' AND dataset='senate') ea ON ea.raw_name = sf.client_name
  LEFT JOIN (SELECT DISTINCT record_key, sub_index FROM lobbying_issue_mentions
             WHERE tag='CRYPTO' AND dataset='senate') t
         ON t.record_key = lf.record_key AND t.sub_index = lf.sub_index
  WHERE sf.client_name IS NOT NULL AND sf.filing_type NOT LIKE 'R%'
  GROUP BY 1),
spend AS (
  SELECT client_entity_id, round(sum(canonical_spend))::BIGINT AS total_all_issue_spend
  FROM v_client_canonical_spend GROUP BY 1)
SELECT p.player, p.entity_id, p.crypto_filings_senate, p.first_year, p.last_year,
       s.total_all_issue_spend,
       CASE WHEN regexp_matches(p.player, '{NAME_VIS}') THEN 'yes' ELSE 'no' END AS crypto_term_in_name,
       CASE WHEN p.crypto_filings_senate>=8 THEN 'core'
            WHEN p.crypto_filings_senate>=3 THEN 'active'
            ELSE 'peripheral' END AS tier,
       a.crypto_activity_blocks, a.all_activity_blocks,
       round(100.0*a.crypto_activity_blocks/a.all_activity_blocks, 1) AS crypto_activity_share_pct,
       CASE WHEN a.all_activity_blocks IS NULL THEN 'n/a (registrations only)'
            WHEN 100.0*a.crypto_activity_blocks/a.all_activity_blocks >= 25 THEN 'dedicated'
            WHEN 100.0*a.crypto_activity_blocks/a.all_activity_blocks >= 5 THEN 'engaged'
            ELSE 'ambient' END AS crypto_share_band
FROM players p
LEFT JOIN acts a USING (entity_id)
LEFT JOIN spend s ON s.client_entity_id=p.entity_id
ORDER BY p.crypto_filings_senate DESC, s.total_all_issue_spend DESC NULLS LAST
"""
cols, rows = sql_csv("crypto_players.csv", q_players)
n_core = sum(1 for r in rows if r[7] == "core")
n_act = sum(1 for r in rows if r[7] == "active")
n_per = sum(1 for r in rows if r[7] == "peripheral")
n_invis = sum(1 for r in rows if r[6] == "no")
n_band = {}
for r in rows:
    n_band[r[11]] = n_band.get(r[11], 0) + 1
print(f"  players={len(rows)} core={n_core} active={n_act} peripheral={n_per} name-invisible={n_invis}")
print(f"  share bands: {n_band}")
print("  top10:", [(r[0][:30], r[2], r[5]) for r in rows[:10]])
for r in rows:
    if r[0] == "CHAMBER OF COMMERCE OF THE U.S.A.":
        print(f"  worked example — U.S. Chamber: {r[8]}/{r[9]} blocks = {r[10]}% share, band={r[11]}")

# ---------- 2. quarterly trend (filings, clients, canonical spend of tagged clients) ----------
q_trend = """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='CRYPTO' AND lim.dataset='senate'),
ded AS (
  SELECT sf.*, coalesce(e.entity_id,'unresolved:'||sf.client_name) AS ceid
  FROM senate_filings sf
  JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
cq AS (SELECT DISTINCT ceid, filing_year, filing_period FROM ded),
spend AS (
  SELECT cq.filing_year, cq.filing_period, round(sum(v.canonical_spend))::BIGINT AS canonical_spend_tagged_clients
  FROM cq JOIN v_client_canonical_spend v
    ON v.client_entity_id=cq.ceid AND v.filing_year=cq.filing_year AND v.filing_period=cq.filing_period
  GROUP BY 1,2)
SELECT d.filing_year, d.filing_period,
       count(DISTINCT d.filing_uuid) AS crypto_filings,
       count(DISTINCT d.ceid) AS crypto_clients,
       s.canonical_spend_tagged_clients
FROM ded d LEFT JOIN spend s ON s.filing_year=d.filing_year AND s.filing_period=d.filing_period
GROUP BY 1,2,s.canonical_spend_tagged_clients
ORDER BY 1, CASE d.filing_period WHEN 'first_quarter' THEN 1 WHEN 'second_quarter' THEN 2
            WHEN 'third_quarter' THEN 3 ELSE 4 END
"""
sql_csv("crypto_quarterly_trend.csv", q_trend)

# ---------- 3. issue-code scatter (the 'hidden under taxation' evidence) ----------
sql_csv("crypto_issue_code_scatter.csv", """
WITH crypto_docs AS (
  SELECT DISTINCT lim.doc_id, lf.issue_code
  FROM lobbying_issue_mentions lim JOIN lobbying_freetext lf USING (doc_id)
  WHERE lim.tag='CRYPTO')
SELECT coalesce(issue_code,'(none)') AS issue_code, count(*) AS crypto_docs,
       round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct_of_crypto
FROM crypto_docs GROUP BY 1 ORDER BY crypto_docs DESC, issue_code""")

# ---------- 4. vocabulary ----------
sql_csv("crypto_keywords.csv", """
SELECT keyword, count(DISTINCT record_key) AS filings
FROM lobbying_issue_mentions WHERE tag='CRYPTO' GROUP BY 1 ORDER BY filings DESC, keyword""")

# ---------- 5. registrant firms ----------
sql_csv("crypto_registrant_firms.csv", """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='CRYPTO' AND lim.dataset='senate'),
ded AS (
  SELECT sf.* FROM senate_filings sf JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT registrant_name,
       count(DISTINCT filing_uuid) AS crypto_filings,
       count(DISTINCT client_id) AS clients,
       round(sum(coalesce(income, expenses)))::BIGINT AS reported_amount_ranking_signal
FROM ded
WHERE upper(trim(registrant_name)) != upper(trim(client_name))  -- outside firms only
GROUP BY 1 ORDER BY crypto_filings DESC, registrant_name LIMIT 60""")

# ---------- 6. press attention (say side) ----------
sql_csv("crypto_press_quarterly.csv", r"""
WITH pr AS (
  SELECT pr_id, date,
         (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
         regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')),
           '\b(crypto|cryptocurrency|cryptocurrencies|stablecoin|stablecoins|digital asset|digital assets|bitcoin|blockchain|central bank digital currency|cbdc)\b') AS is_crypto
  FROM press_releases WHERE date >= '2022-01-01')
SELECT quarter, count(*) AS all_releases,
       sum(CASE WHEN is_crypto THEN 1 ELSE 0 END) AS crypto_releases,
       round(100.0*sum(CASE WHEN is_crypto THEN 1 ELSE 0 END)/count(*),2) AS crypto_share_pct
FROM pr GROUP BY 1 ORDER BY 1""")

# ---------- 7. record samples for QA (top players' highest-amount tagged filing) ----------
sql_csv("crypto_record_samples_qa.csv", """
WITH tagged AS (
  SELECT lim.record_key AS filing_uuid, any_value(lim.keyword) AS keyword_example
  FROM lobbying_issue_mentions lim WHERE lim.tag='CRYPTO' AND lim.dataset='senate' GROUP BY 1),
ranked AS (
  SELECT sf.client_name, sf.registrant_name, sf.filing_uuid, t.keyword_example,
         sf.filing_year, sf.filing_period, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         row_number() OVER (PARTITION BY sf.client_name ORDER BY coalesce(sf.income, sf.expenses) DESC NULLS LAST, sf.filing_uuid) rn,
         count(*) OVER (PARTITION BY sf.client_name) n
  FROM senate_filings sf JOIN tagged t USING (filing_uuid))
SELECT client_name, registrant_name, filing_year, filing_period, amount,
       keyword_example, filing_uuid AS show_record_key
FROM ranked WHERE rn=1 ORDER BY n DESC, client_name LIMIT 25""")

# ---------- 8/9. LD-203 giving (per-entity + recipients) from tool JSON ----------
g = loadj(os.path.join(S, "crypto_giving.json"))
res = g["results"]
crypto_filings_by_upper = {}
for r in rows:  # from players export
    crypto_filings_by_upper[r[0].upper()] = r[2]
pe = res.get("per_entity", [])
wcsv("crypto_ld203_giving_by_org.csv",
     ["ld203_filer_org", "disclosed_giving_total", "items", "crypto_filings_senate_note"],
     [[e["registrant_name"], e["total"], e["items"],
       crypto_filings_by_upper.get(e["registrant_name"].upper(), "")] for e in pe])
wcsv("crypto_ld203_top_recipients.csv",
     ["recipient_raw", "items", "total"],
     [[r["recipient"], r["items"], r["total"]] for r in res.get("recipients", [])])
wcsv("crypto_ld203_by_year.csv", ["filing_year", "total"],
     [[r["filing_year"], r["total"]] for r in res.get("by_year", [])])
print("  ld203 totals:", res["totals"])

# ---------- 10. FEC Super-PAC reconciliation ----------
f = loadj(os.path.join(S, "crypto_fec.json"))
recon = f.get("reconciliation", [])

def sjoin(items, n=4):
    outp = []
    for it in items[:n]:
        if isinstance(it, dict):
            outp.append(str(it.get("name") or it.get("fec_name") or it.get("player") or json.dumps(it)))
        else:
            outp.append(str(it))
    return "; ".join(outp)

wcsv("crypto_fec_superpac_vs_ld203.csv",
     ["player", "match_confidence", "fec_superpac_contributions", "fec_items",
      "ld203_disclosed_giving", "delta_fec_minus_ld203", "fec_contributor_names", "committees", "sample_transaction_ids"],
     [[r["player"], r["confidence"], r["fec_superpac"], r["fec_items"], r["ld203"],
       r["delta"], sjoin(r.get("fec_names", [])), sjoin(r.get("committees", []), 5),
       sjoin(r.get("tids", []))] for r in recon])
wcsv("crypto_fec_unmatched_network_donors.csv", ["fec_contributor_name", "total", "items"],
     [[r["name"], r["total"], r["items"]] for r in f.get("unmatched_network_donors", [])])
comm = f.get("committees", [])
wcsv("crypto_fec_committees.csv", ["committee_id", "name", "type", "cycles"],
     [[c["committee_id"], c["name"], c.get("committee_type_full", ""), "; ".join(map(str, c.get("cycles", [])))] for c in comm])
print("  fec api_key_source:", f.get("api_key_source"), "| committees:", [c["committee_id"] for c in comm])

print("\nDONE — crypto CSVs in", OUT)
