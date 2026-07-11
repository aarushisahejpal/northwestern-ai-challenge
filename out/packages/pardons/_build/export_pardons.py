"""Pardons package exporter (2026-07-10) — presidential pardons / executive clemency.
Reads db/lda_full.duckdb (read-only) + the LD-203 tool JSON in scratchpad,
writes CSV flat files to out/packages/pardons/data/.
Run from the gain-investigation repo root.

Discipline: senate-primary (never sum chambers); filings deduped on
(registrant_id, client_id, filing_year, filing_period) latest-by-posted;
registrations (filing_type R*) excluded from dollar work; client spend only
via v_client_canonical_spend (P1); per-item dollars are ranking signals.
Facet: PARDONS tag in lobbying_issue_mentions (industry_lexicon.json v1.1).
Termination flag: declared senate filing_type family ^[1-4](T|TY|@|@Y)$
(corpus-profile §3 termination_signal) — never inferred from absence.
"""
import duckdb, json, csv, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
S = r"C:\Users\rcalv\AppData\Local\Temp\claude\c--Users-rcalv-Projects\c08688e9-9d41-4a86-a380-4a5b809157f4\scratchpad"
OUT = os.path.join(REPO, "out", "packages", "pardons", "data")
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

# ---------- client-class hand triage (2026-07-10, from the 54-player map) ----------
# Classes: seeker         = individual person as client, buying a pardon/clemency engagement
#          seeker_vehicle = organization client whose tagged engagement seeks executive
#                           relief/pardon (beneficiary named in text where declared)
#          advocacy       = policy organization lobbying on clemency/pardon policy or the
#                           pardon power itself (both directions; includes cannabis-pardon pushes)
#          unclear        = tagged but purpose not classifiable from the filings alone
# Beneficiary notes quote ONLY what the filings themselves declare — no outside facts.
CLASS = {
    "ANNE PRAMAGGIORE": ("seeker", ""),
    "CHANGPENG ZHAO": ("seeker", "'Executive relief.'"),
    "DR. SHALLFDEEN AMUWO": ("seeker", "'Commutation of sentencing'"),
    "FRED DAIBES": ("seeker", "'Executive relief' (ledger L021)"),
    "GREG E. LINDBERG": ("seeker", "'Executive pardon.'"),
    "JOSH SMITH": ("seeker", "'Client is requesting a presidential pardon.'"),
    "JOSEPH SCHWARTZ": ("seeker", "'Seeking a federal pardon.' (ledger L034)"),
    "KOMAL PATEL": ("seeker", ""),
    "MATT GEOUGE": ("seeker", "'Pardon Request'"),
    "PHILLIP FREDERICK CAMINO": ("seeker", ""),
    "RAYMOND LIDDY": ("seeker", "'Legal/ pardon'"),
    "RICHARD SCRUSHY": ("seeker", "'Granting of Pardon'"),
    "RYAN AND WADE LALONE": ("seeker", "'Pardon application consulting and support'"),
    "SANTIAGO ALVAREZ": ("seeker", "'Advocating for pardon for Santiago Alvarez'"),
    "SELIM ZHERKA": ("seeker", "'pardon application submitted on October 22, 2025'"),
    "TORENCE HATCH": ("seeker", "'Seeking a presidential pardon. White House issues.' (ledger L034)"),
    "WILLIAM TIERNEY": ("seeker", ""),
    "YENER VAHIT BELLI": ("seeker", "'Lobbying for pardon/commutation of sentence.'"),
    "BINANCE HOLDINGS LIMITED": ("seeker_vehicle", "'digital assets and cryptocurrency; and executive relief'"),
    "FAHMY HUDOME INTL., INC. ON BEHALF OF RICHARD SCRUSHY": ("seeker_vehicle", "Richard Scrushy (named in client string)"),
    "JUNO EMPIRE INC": ("seeker_vehicle", "'the Pardon of Jorge Ferrer' (named in filing text)"),
    "ORIGIN PROPERTY GROUP": ("seeker_vehicle", "'Potential Presidential pardon of Marco Bitran, founder' (named in filing text)"),
    "MAGMA POWER LLC": ("seeker_vehicle", "beneficiary not stated in filing text"),
    "HEALTHICITY": ("seeker_vehicle", "beneficiary not stated in filing text"),
    "DIAMOND STREET PROPERTIES LLC": ("seeker_vehicle", "'pardons for federal crimes of those they feel have served their time' — no named beneficiary"),
    "VERITASEUM INC.,": ("seeker_vehicle", "SEC/DOJ matters in same text; beneficiary not stated"),
    "STATE OF LOC NATION GLOBAL PUBLIC BENEFIT CORPORATION": ("unclear", "HR 40 / faith-recognition text; pardon term incidental"),
}
ADVOCACY = {
    "AMERICAN CONSERVATIVE UNION", "AMNESTY INTERNATIONAL USA",
    "AMERICAN CIVIL LIBERTIES UNION", "AMERICANS FOR PROSPERITY",
    "BRENNAN CENTER FOR JUSTICE AT NEW YORK UNIVERSITY SCHOOL OF LAW",
    "CALIFORNIA CANNABIS INDUSTRY ASSOCIATION", "CAMPAIGN LEGAL CENTER, INC.",
    "COMMON CAUSE", "CONFERENCE OF PROVINCIALS OF NORTH AMERICA",
    "DEMOCRACY DEFENDERS ACTION", "DISABILITY RIGHTS EDUCATION & DEFENSE INC",
    "DUE PROCESS INSTITUTE", "FWD.US",
    "LAWYERS' COMMITTEE FOR CIVIL RIGHTS UNDER LAW",
    "LEADERSHIP CONFERENCE ON CIVIL AND HUMAN RIGHTS", "MOVEON.ORG CIVIC ACTION",
    "NATIONAL ASSOCIATION FOR THE ADVANCEMENT OF COLORED PEOPLE",
    "NATIONAL ASSOCIATION OF ASSISTANT UNITED STATES ATTORNEYS",
    "NATIONAL ASSOCIATION OF CRIMINAL DEFENSE LAWYERS (NACDL)",
    "NATIONAL COUNCIL OF JEWISH WOMEN", "NDN COLLECTIVE",
    "NATIONAL CANNABIS ROUNDTABLE",
    "PROTECT DEMOCRACY UNITED (FORMERLY KNOWN AS UNITED TO PROTECT DEMOCRACY)",
    "PRISON FELLOWSHIP MINISTRIES", "STUDENTS FOR SENSIBLE DRUG POLICY",
    "THE ALEPH INSTITUTE, INC.", "THE IMMIGRATION HUB LLC",
}
def classify(player):
    u = player.upper().strip()
    if u in CLASS:
        return CLASS[u]
    if u in ADVOCACY:
        return ("advocacy", "")
    return ("unclear", "not in the 2026-07-10 hand triage — re-triage on a corpus refresh")

# ---------- 1. players (senate-side, entity-resolved, hand-classed) ----------
q_players = """
WITH pardon_docs AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='PARDONS' AND lim.dataset='senate'),
resolved AS (
  SELECT coalesce(e.canonical_name, sf.client_name) AS player,
         coalesce(e.entity_id, 'unresolved:'||sf.client_name) AS entity_id,
         sf.filing_uuid, sf.filing_year
  FROM pardon_docs c
  JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.client_name IS NOT NULL),
players AS (
  SELECT entity_id, any_value(player) AS player,
         count(DISTINCT filing_uuid) AS pardons_filings_senate,
         min(filing_year) AS first_year, max(filing_year) AS last_year
  FROM resolved GROUP BY 1),
spend AS (
  SELECT client_entity_id, round(sum(canonical_spend))::BIGINT AS total_all_issue_spend
  FROM v_client_canonical_spend GROUP BY 1)
SELECT p.player, p.entity_id, p.pardons_filings_senate, p.first_year, p.last_year,
       s.total_all_issue_spend
FROM players p LEFT JOIN spend s ON s.client_entity_id=p.entity_id
ORDER BY p.pardons_filings_senate DESC, s.total_all_issue_spend DESC NULLS LAST
"""
cur = con.execute(q_players)
pcols = [d[0] for d in cur.description]
prows = cur.fetchall()
out_rows = []
for r in prows:
    cls, note = classify(r[0])
    out_rows.append(list(r) + [cls, note])
wcsv("pardons_players.csv", pcols + ["client_class", "class_note"], out_rows)
from collections import Counter
cc = Counter(r[6] for r in out_rows)
print("  class counts:", dict(cc))

# rosters for the money tools / re-runs (gitignored out/)
seekers = sorted(r[0] for r in out_rows if r[6] in ("seeker", "seeker_vehicle"))
advocacy = sorted(r[0] for r in out_rows if r[6] == "advocacy")
open(os.path.join(REPO, "out", "pardons_roster_seekers.txt"), "w", encoding="utf-8").write("\n".join(seekers) + "\n")
open(os.path.join(REPO, "out", "pardons_roster_advocacy.txt"), "w", encoding="utf-8").write("\n".join(advocacy) + "\n")
print(f"  rosters: {len(seekers)} seekers, {len(advocacy)} advocacy")

# ---------- 2. raw-filing index per player (click-through) ----------
q_filings = """
WITH pardon_docs AS (
  SELECT record_key AS filing_uuid, string_agg(DISTINCT keyword, '; ') AS matched_keywords
  FROM lobbying_issue_mentions WHERE tag='PARDONS' AND dataset='senate' GROUP BY 1)
SELECT coalesce(e.canonical_name, sf.client_name) AS player,
       sf.filing_year, sf.filing_period, sf.filing_type,
       sf.registrant_name,
       coalesce(sf.income, sf.expenses)::BIGINT AS reported_amount,
       c.matched_keywords,
       sf.filing_uuid,
       'https://lda.senate.gov/filings/public/filing/'||sf.filing_uuid||'/print/' AS url
FROM pardon_docs c
JOIN senate_filings sf ON sf.filing_uuid=c.filing_uuid
LEFT JOIN (SELECT DISTINCT raw_name, entity_id FROM entity_aliases
           WHERE kind='client' AND dataset='senate') ea ON ea.raw_name=sf.client_name
LEFT JOIN entities e ON e.entity_id=ea.entity_id
WHERE sf.client_name IS NOT NULL
ORDER BY player, sf.filing_year, sf.filing_period, sf.registrant_name
"""
sql_csv("pardons_player_filings.csv", q_filings)

# ---------- 3. quarterly trend ----------
q_trend = """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='PARDONS' AND lim.dataset='senate'),
ded AS (
  SELECT sf.*, coalesce(e.entity_id,'unresolved:'||sf.client_name) AS ceid
  FROM senate_filings sf
  JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT d.filing_year, d.filing_period,
       count(DISTINCT d.filing_uuid) AS pardons_filings,
       count(DISTINCT d.ceid) AS pardons_clients
FROM ded d
GROUP BY 1,2
ORDER BY 1, CASE d.filing_period WHEN 'first_quarter' THEN 1 WHEN 'second_quarter' THEN 2
            WHEN 'third_quarter' THEN 3 ELSE 4 END
"""
sql_csv("pardons_quarterly_trend.csv", q_trend)

# trend click-through: the deduped filings behind each quarter
q_trend_filings = """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='PARDONS' AND lim.dataset='senate'),
ded AS (
  SELECT sf.*, coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf
  JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1),
kw AS (
  SELECT record_key AS filing_uuid, string_agg(DISTINCT keyword, '; ') AS matched_keywords
  FROM lobbying_issue_mentions WHERE tag='PARDONS' AND dataset='senate' GROUP BY 1)
SELECT d.filing_year, d.filing_period, d.player, d.registrant_name,
       coalesce(d.income, d.expenses)::BIGINT AS reported_amount, k.matched_keywords, d.filing_uuid
FROM ded d LEFT JOIN kw k ON k.filing_uuid=d.filing_uuid ORDER BY 1,2,3
"""
sql_csv("pardons_trend_filings.csv", q_trend_filings)

# ---------- 4. issue-code scatter ----------
q_scatter = """
WITH pardon_docs AS (
  SELECT DISTINCT lim.doc_id, lf.issue_code
  FROM lobbying_issue_mentions lim JOIN lobbying_freetext lf USING (doc_id)
  WHERE lim.tag='PARDONS')
SELECT coalesce(issue_code,'(none)') AS issue_code, count(*) AS pardons_docs,
       round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct_of_pardons
FROM pardon_docs GROUP BY 1 ORDER BY pardons_docs DESC
"""
sql_csv("pardons_issue_code_scatter.csv", q_scatter)

# ---------- 5. vocabulary ----------
q_keywords = """
SELECT keyword, count(DISTINCT record_key) AS filings
FROM lobbying_issue_mentions WHERE tag='PARDONS' GROUP BY 1 ORDER BY filings DESC
"""
sql_csv("pardons_keywords.csv", q_keywords)

# ---------- 6. registrant firms ----------
q_registrants = """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='PARDONS' AND lim.dataset='senate'),
ded AS (
  SELECT sf.* FROM senate_filings sf JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  WHERE sf.filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY sf.registrant_id, sf.client_id, sf.filing_year, sf.filing_period
                             ORDER BY sf.posted DESC, sf.filing_uuid DESC)=1)
SELECT registrant_name,
       count(DISTINCT filing_uuid) AS pardons_filings,
       count(DISTINCT client_id) AS clients,
       round(sum(coalesce(income, expenses)))::BIGINT AS reported_amount_ranking_signal
FROM ded
WHERE upper(trim(registrant_name)) != upper(trim(client_name))  -- outside firms only
GROUP BY 1 ORDER BY pardons_filings DESC LIMIT 40
"""
sql_csv("pardons_registrant_firms.csv", q_registrants)

# ---------- 7. seeker engagements w/ declared termination (the signature table) ----------
# Engagement grain = (registrant_id, client_id) pair among tagged filings. A quarter is
# tagged if ANY amendment version in it was tagged; dollars come from the deduped survivor.
# Termination is DECLARED only: senate filing_type ~ '^[1-4](T|TY|@|@Y)$' anywhere in the
# pair's filings (corpus-profile §3) — absence of filings is never read as termination.
q_engagements = """
WITH tagged AS (
  SELECT DISTINCT lim.record_key AS filing_uuid
  FROM lobbying_issue_mentions lim WHERE lim.tag='PARDONS' AND lim.dataset='senate'),
pairs AS (
  SELECT DISTINCT sf.registrant_id, sf.client_id,
         any_value(sf.registrant_name) OVER (PARTITION BY sf.registrant_id) AS registrant_name
  FROM senate_filings sf JOIN tagged t ON t.filing_uuid=sf.filing_uuid),
pf AS (   -- every senate filing of those pairs
  SELECT sf.*, (t.filing_uuid IS NOT NULL) AS is_tagged,
         coalesce(e.canonical_name, sf.client_name) AS player
  FROM senate_filings sf
  JOIN pairs p ON p.registrant_id=sf.registrant_id AND p.client_id=sf.client_id
  LEFT JOIN tagged t ON t.filing_uuid=sf.filing_uuid
  LEFT JOIN entity_aliases ea ON ea.raw_name=sf.client_name AND ea.kind='client' AND ea.dataset='senate'
  LEFT JOIN entities e ON e.entity_id=ea.entity_id),
ded AS (  -- amendment-deduped quarterlies, carrying quarter-level taggedness
  SELECT *, bool_or(is_tagged) OVER (PARTITION BY registrant_id, client_id, filing_year, filing_period) AS q_tagged
  FROM pf WHERE filing_type NOT LIKE 'R%'
  QUALIFY row_number() OVER (PARTITION BY registrant_id, client_id, filing_year, filing_period
                             ORDER BY posted DESC, filing_uuid DESC)=1),
term AS (  -- declared terminations anywhere in the pair
  SELECT registrant_id, client_id,
         max(filing_year||'-'||CASE filing_period WHEN 'first_quarter' THEN 'Q1' WHEN 'second_quarter' THEN 'Q2'
             WHEN 'third_quarter' THEN 'Q3' WHEN 'fourth_quarter' THEN 'Q4' ELSE filing_period END) AS termination_quarter
  FROM pf WHERE regexp_matches(filing_type, '^[1-4](T|TY|@|@Y)$')
  GROUP BY 1,2)
SELECT any_value(d.player) AS player, any_value(d.registrant_name) AS registrant_name,
       min(CASE WHEN d.q_tagged THEN d.filing_year||'-'||CASE d.filing_period WHEN 'first_quarter' THEN 'Q1'
           WHEN 'second_quarter' THEN 'Q2' WHEN 'third_quarter' THEN 'Q3' ELSE 'Q4' END END) AS first_tagged_quarter,
       max(CASE WHEN d.q_tagged THEN d.filing_year||'-'||CASE d.filing_period WHEN 'first_quarter' THEN 'Q1'
           WHEN 'second_quarter' THEN 'Q2' WHEN 'third_quarter' THEN 'Q3' ELSE 'Q4' END END) AS last_tagged_quarter,
       count(DISTINCT CASE WHEN d.q_tagged THEN d.filing_year||d.filing_period END) AS tagged_quarters,
       sum(CASE WHEN d.q_tagged THEN coalesce(d.income, d.expenses) END)::BIGINT AS reported_total_tagged_quarters,
       CASE WHEN any_value(t.termination_quarter) IS NOT NULL THEN 'yes' ELSE 'no' END AS terminated,
       any_value(t.termination_quarter) AS termination_quarter,
       max(CASE WHEN d.q_tagged THEN d.filing_uuid END) AS sample_filing_uuid
FROM ded d LEFT JOIN term t ON t.registrant_id=d.registrant_id AND t.client_id=d.client_id
GROUP BY d.registrant_id, d.client_id
HAVING count(DISTINCT CASE WHEN d.q_tagged THEN d.filing_year||d.filing_period END) > 0
ORDER BY reported_total_tagged_quarters DESC NULLS LAST
"""
cur = con.execute(q_engagements)
ecols = [d[0] for d in cur.description]
erows = cur.fetchall()
# attach class + a declared-text sample per engagement; keep seeker/vehicle rows
txt_by_uuid = dict(con.execute("""
    SELECT lf.record_key, any_value(substr(lf.txt,1,220))
    FROM lobbying_freetext lf
    JOIN lobbying_issue_mentions lim ON lim.doc_id=lf.doc_id AND lim.tag='PARDONS'
    WHERE lf.dataset='senate' GROUP BY 1""").fetchall())
eng_rows = []
for r in erows:
    cls, note = classify(r[0])
    if cls not in ("seeker", "seeker_vehicle"):
        continue
    declared = " ".join((txt_by_uuid.get(r[8]) or "").split())
    eng_rows.append(list(r) + [cls, declared])
eng_rows.sort(key=lambda x: -(x[5] or 0))
wcsv("pardons_engagements.csv", ecols + ["client_class", "declared_text_sample"], eng_rows)
mkt_total = sum(r[5] or 0 for r in eng_rows)
n_term = sum(1 for r in eng_rows if r[6] == "yes")
print(f"  seeker engagements={len(eng_rows)} market_total=${mkt_total:,} terminated={n_term}")

# ---------- 8. press attention (say side) ----------
# Press-side vocabulary adds the verb forms (pardoned/pardoning) the filings never use.
q_press = r"""
WITH pr AS (
  SELECT pr_id, date,
         (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
         regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')),
           '\b(pardon|pardons|pardoned|pardoning|clemency|clemencies|commutation|commutations)\b') AS is_pardon
  FROM press_releases WHERE date >= '2022-01-01')
SELECT quarter, count(*) AS all_releases,
       sum(CASE WHEN is_pardon THEN 1 ELSE 0 END) AS pardon_releases,
       round(100.0*sum(CASE WHEN is_pardon THEN 1 ELSE 0 END)/count(*),2) AS pardon_share_pct
FROM pr GROUP BY 1 ORDER BY 1
"""
sql_csv("pardons_press_quarterly.csv", q_press)

# press click-through: every matching release with URL + citation key
q_press_rel = r"""
SELECT (substr(date,1,4) || '-Q' || CAST(ceil(CAST(substr(date,6,2) AS INT)/3.0) AS INT)) AS quarter,
       date, member_name, party, state, substr(coalesce(title,''),1,140) AS title, url,
       src_file, src_line
FROM press_releases
WHERE date >= '2022-01-01'
  AND regexp_matches(lower(coalesce(title,'')||' '||coalesce(text,'')),
      '\b(pardon|pardons|pardoned|pardoning|clemency|clemencies|commutation|commutations)\b')
ORDER BY date
"""
sql_csv("pardons_press_releases.csv", q_press_rel)

# ---------- 9. record samples for QA ----------
q_samples = """
WITH tagged AS (
  SELECT lim.record_key AS filing_uuid, any_value(lim.keyword) AS keyword_example
  FROM lobbying_issue_mentions lim WHERE lim.tag='PARDONS' AND lim.dataset='senate' GROUP BY 1),
ranked AS (
  SELECT sf.client_name, sf.registrant_name, sf.filing_uuid, t.keyword_example,
         sf.filing_year, sf.filing_period, coalesce(sf.income, sf.expenses)::BIGINT AS amount,
         row_number() OVER (PARTITION BY sf.client_name ORDER BY coalesce(sf.income, sf.expenses) DESC NULLS LAST) rn,
         count(*) OVER (PARTITION BY sf.client_name) n
  FROM senate_filings sf JOIN tagged t USING (filing_uuid))
SELECT client_name, registrant_name, filing_year, filing_period, amount,
       keyword_example, filing_uuid AS show_record_key
FROM ranked WHERE rn=1 ORDER BY n DESC LIMIT 25
"""
sql_csv("pardons_record_samples_qa.csv", q_samples)

# ---------- 10. LD-203 giving (roster orgs' org-level giving; caveat: NOT pardon-attributable) ----------
g = loadj(os.path.join(S, "pardons_giving.json"))
res = g["results"]
pe = res.get("per_entity", [])
wcsv("pardons_ld203_by_org.csv",
     ["ld203_filer_org", "disclosed_giving_total", "items"],
     [[e["registrant_name"], e["total"], e["items"]] for e in pe])
wcsv("pardons_ld203_recipients.csv",
     ["recipient_raw", "items", "total"],
     [[r["recipient"], r["items"], r["total"]] for r in res.get("recipients", [])])
wcsv("pardons_ld203_by_year.csv", ["filing_year", "total"],
     [[r["filing_year"], r["total"]] for r in res.get("by_year", [])])
print("  ld203 totals:", res["totals"])

print("\nDONE — pardons CSVs in", OUT)
