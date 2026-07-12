"""Generate DATA_DICTIONARY.md for the crypto package (2026-07-10, Rob's ask:
a reference to "see what all the rows and tables references are").

Two halves:
  1. the DuckDB tables/views the widget queries reference — column list pulled
     LIVE from the DB (DESCRIBE) so it can't drift, annotated from a curated map
     (a column missing an annotation is flagged, not hidden);
  2. every CSV in data/ — headers read from the files themselves, annotated the
     same way.

Run from the gain-investigation repo root; re-run whenever the schema or the
package CSVs change.
"""
import csv
import io
import os
import sys
from datetime import date

import duckdb

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
PKG = os.path.join(REPO, "out", "packages", "crypto")

# ---------------------------------------------------------------- DB tables

TABLES = {
 "senate_filings": (
  "One row per Senate LDA filing VERSION (LD-1 registrations + LD-2 quarterly activity "
  "reports, amendments included as separate rows). THE dollar source. Never sum rows "
  "without deduplicating on (registrant_id, client_id, filing_year, filing_period) "
  "keeping the latest `posted` — amendments double-count otherwise. Senate is the "
  "primary chamber; House versions of the same filings are copies, never added on top.",
  {
   "filing_uuid": "Senate's stable filing id — the citation key. Resolve internally via show_record.py, publicly at https://lda.senate.gov/filings/public/filing/<uuid>/print/",
   "filing_type": "Senate type code: Q1/Q2/Q3/Q4 quarterlies (suffix A = amendment), R* = LD-1 registrations, T-family (1T/2T/…/TY) = terminations. Never select dollars by type alone — dedup by filing_period",
   "filing_period": "first_quarter … fourth_quarter (registration rows carry the period registered). Part of the amendment-dedup key",
   "filing_year": "Reporting year of the filing",
   "income": "Reported lobbying income — used by OUTSIDE firms reporting what a client paid them",
   "expenses": "Reported lobbying expenses — used by SELF-FILING (in-house) registrants. A filing reports income OR expenses; use coalesce/greatest of the two, never their sum",
   "registrant_id": "Senate registrant id — GLOBAL (safe to group by)",
   "registrant_name": "Registrant (lobbying org) name as filed",
   "house_registrant_id": "House Clerk registrant id carried on the Senate filing. NOT joinable to House <houseID> (different namespace)",
   "client_id": "Senate client id — REGISTRANT-SCOPED, not global (Comcast has 10+). Never group clients by this; group by resolved entity",
   "client_name": "Client name as filed (spelling varies — resolve via entities/entity_aliases)",
   "client_state": "Client state as filed",
   "client_description": "Client self-description as filed",
   "posted": "Server timestamp the version was posted — the amendment tiebreaker (latest wins)",
   "src_file": "Raw-record pointer: source file in the corpus download",
   "src_index": "Raw-record pointer: index within src_file",
  }),
 "senate_contributions": (
  "One row per LD-203 semiannual contribution REPORT (header). Filed by registrants and "
  "by their individual lobbyists — giving attaches to REGISTRANTS, never to an outside "
  "firm's clients. Amendments appear as separate reports (dedup items on their full "
  "identity tuple).",
  {
   "filing_uuid": "Senate filing id of the LD-203 report (citation key, same namespaces as senate_filings)",
   "filer_type": "'organization' = the registrant's own report (org/PAC giving) · 'lobbyist' = an individual lobbyist's personal report",
   "filing_year": "Reporting year",
   "registrant_name": "Registrant the report belongs to",
   "lobbyist_name": "Individual lobbyist (lobbyist reports only)",
   "pacs": "PAC name(s) listed on the report",
   "src_file": "Raw-record pointer: source file",
   "src_index": "Raw-record pointer: index within src_file",
  }),
 "senate_contribution_items": (
  "One row per itemized contribution on an LD-203 report. The giving analyses use "
  "recipient = honoree if present, else payee. Amendment duplicates are collapsed on "
  "(registrant, lobbyist, year, type, amount, payee, honoree, date, contributor).",
  {
   "filing_uuid": "LD-203 report this item belongs to (joins senate_contributions)",
   "item_index": "Item position within the report",
   "contribution_type": "feca = FEC campaign contribution · he = honorary (event honoring a covered official) · me = meeting/event payment · pic = presidential inaugural committee · ple = presidential library",
   "amount": "Dollar amount as filed",
   "payee": "Who was paid (e.g. the event vendor or committee)",
   "honoree": "Covered official the payment honors — the analytic recipient when present",
   "contributor_name": "Contributor as filed",
   "date": "Contribution date as filed",
   "src_file": "Raw-record pointer: source file",
   "src_index": "Raw-record pointer: index within src_file",
  }),
 "lobbying_issue_mentions": (
  "SERVING table (P4 industry map): deterministic tags over the lobbying free-text from "
  "the curated industry lexicon (skills/lead-scanner/scripts/industry_lexicon.json). One "
  "row per (text block × matched keyword). tag='CRYPTO' rows define the crypto map; "
  "count DISTINCT record_key for filings.",
  {
   "doc_id": "Joins lobbying_freetext.doc_id (the tagged text block)",
   "dataset": "'senate' or 'house' side of the corpus (the crypto map is senate-side)",
   "record_key": "Citation key of the filing: Senate filing_uuid, or House XML filename",
   "sub_index": "Which activity/issue block within the filing",
   "tag": "Industry facet (e.g. CRYPTO) from the curated lexicon",
   "keyword": "The exact lexicon phrase that matched (auditable: search the raw text for it)",
   "src_file": "Raw-record pointer: source file",
   "src_index": "Raw-record pointer: index within src_file",
  }),
 "lobbying_freetext": (
  "The searchable free-text surface: Senate activity descriptions + House specific_issues "
  "unioned into one table (with a BM25 full-text index, discovery-only). What filers SAY "
  "they lobby on — the recall layer that finds players issue codes miss.",
  {
   "doc_id": "Stable id of the text block",
   "dataset": "'senate' or 'house'",
   "record_key": "Citation key of the filing the text came from",
   "sub_index": "Activity/issue block index within the filing",
   "issue_code": "The ALI general issue code the registrant filed this block under (FIN, TAX, …)",
   "txt": "The free text as filed",
   "src_file": "Raw-record pointer: source file",
   "src_index": "Raw-record pointer: index within src_file",
  }),
 "entities": (
  "Entity-resolver output: one row per resolved organization (registrants, clients, "
  "foreign entities) grouped by a deterministic normalized-name key. 'Player' names in "
  "this package are canonical_name values.",
  {
   "entity_id": "Stable resolver id for the entity",
   "kind": "'registrant' · 'client' · 'foreign_entity' (an org can appear as both registrant and client — deliberately separate rows)",
   "canonical_name": "Display name (the most frequent raw spelling)",
   "norm_key": "Deterministic normalization key (uppercase, punctuation/suffix-stripped) the grouping is built on",
   "senate_id": "Senate id when the dataset carries one",
   "n_aliases": "How many raw spellings grouped into this entity",
   "n_records": "How many filings carry those spellings",
   "sample_record": "One raw-record citation key, for spot-checking the grouping",
  }),
 "entity_aliases": (
  "One row per raw name variant per dataset — the audit trail for every entity grouping "
  "decision. Join filings to entities through raw_name.",
  {
   "entity_id": "The entity this spelling resolved to",
   "kind": "'registrant' · 'client' · 'foreign_entity'",
   "raw_name": "The spelling exactly as filed",
   "norm_key": "Its normalization key",
   "dataset": "'senate' or 'house'",
   "senate_id": "Senate id for this variant when present",
   "n_records": "Filings carrying this exact spelling",
   "sample_record": "One raw-record citation key",
  }),
 "press_releases": (
  "Congressional member press releases (the 'say' side), 2022–2026Q1. Citation key is "
  "src_file:src_line. Corpus volume roughly quadruples 2022→2025 — compare SHARES across "
  "years, not raw counts.",
  {
   "pr_id": "Row id within the DB (not a citation key)",
   "url": "Original release URL (may rot; the scraped text is the evidence)",
   "title": "Release title",
   "date": "Release date",
   "date_source": "Where the date was parsed from",
   "source": "Source collection label",
   "domain": "Publishing domain",
   "scraper": "Scraper that captured it",
   "bioguide_id": "Member's bioguide id (the person join key)",
   "member_name": "Member display name",
   "party": "Member party (at scrape time)",
   "state": "Member state",
   "chamber": "House / Senate",
   "text": "Full release text",
   "src_file": "Raw-record pointer: JSONL file",
   "src_line": "Raw-record pointer: line in that file (citation key = src_file:src_line)",
  }),
 "v_client_canonical_spend": (
  "VIEW (P1 rollup-correctness): per (client, quarter) lobbying spend with the in-house "
  "double-count removed. A self-filing client's in-house total already subsumes what its "
  "outside firms report — canonical = greatest(in-house, outside), NEVER their sum. This "
  "is the only sanctioned source for client spend aggregates.",
  {
   "client_entity_id": "Resolved client entity (joins entities.entity_id)",
   "client_name": "Canonical client name",
   "client_norm_key": "Client normalization key",
   "filing_year": "Year",
   "filing_period": "Quarter (first_quarter … fourth_quarter)",
   "has_inhouse_filing": "TRUE if the client self-filed (registrant norm_key == client norm_key) that quarter",
   "inhouse_amount": "Amount reported on the client's own in-house filing(s)",
   "outside_amount": "Sum of what outside firms reported for the client",
   "canonical_spend": "greatest(inhouse_amount, outside_amount) — the number to use",
   "naive_sum_all": "inhouse + outside (the WRONG number, kept for audit)",
   "double_count_delta": "least(inhouse, outside) — how much the naive sum overstates",
   "method": "Which branch produced canonical_spend (in-house total vs outside sum)",
   "n_filings": "Filings behind the quarter after amendment-dedup",
  }),
}

# ---------------------------------------------------------------- CSV files

FILE_DESC = {
 "crypto_players.csv": "MASTER TABLE — one row per entity-resolved client-side player with ≥1 crypto-tagged senate filing. 2026-07-11: carries the crypto ACTIVITY-SHARE intensity metric (healthcare-parity semantics) + share band; the ≥5% band edge is the giving/money-list gate.",
 "crypto_player_filings.csv": "Raw-filing index — one row per (player, crypto-tagged senate filing); per-player counts reconcile with crypto_players.csv. Added 2026-07-09.",
 "crypto_trend_filings.csv": "Trend-widget click-through: the filings behind each quarter of the trend chart, using the CHART'S semantics (amendments deduped, registrations excluded) — per-quarter counts reconcile with crypto_quarterly_trend.csv. Added 2026-07-10.",
 "crypto_issue_code_filings.csv": "Scatter-widget click-through: the senate filings behind each issue code's crypto-tagged text blocks (the chart counts BLOCKS across both chambers; sum of n_crypto_blocks_in_filing per code = the code's senate-side blocks). Added 2026-07-10.",
 "crypto_spend_quarters.csv": "Money-widget click-through: every mapped player's quarter-by-quarter v_client_canonical_spend rows — per-player sums reconcile with crypto_players.csv total_all_issue_spend. Added 2026-07-10.",
 "crypto_ld203_items.csv": "Giving-widget click-through: the amendment-deduped LD-203 items behind every DISPLAYED recipient row — per-row sums reconcile with crypto_ld203_recipients_split.csv; each item links to the filed contribution report. Added 2026-07-10.",
 "crypto_press_releases.csv": "Press-widget click-through: every crypto-matching member release with its URL and src_file:src_line citation key — per-quarter counts reconcile with crypto_press_quarterly.csv. Added 2026-07-10.",
 "crypto_quarterly_trend.csv": "One row per quarter: crypto-tagged filing/client counts and the canonical spend of that quarter's tagged clients.",
 "crypto_issue_code_scatter.csv": "Where crypto hides: crypto-tagged text blocks by the ALI issue code they were filed under.",
 "crypto_keywords.csv": "Which curated lexicon phrases carried the tagging signal.",
 "crypto_registrant_firms.csv": "Top OUTSIDE lobbying firms on crypto filings (self-filers excluded).",
 "crypto_press_quarterly.csv": "Crypto share of congressional member press releases per quarter.",
 "crypto_ld203_recipients_split.csv": "Giving recipients split THREE ways by giver type (2026-07-11 intensity gate): crypto-native / crypto-forward diversified (≥5% activity share) / ambient (<5%, context — not charted); person/Trump-inaugural name variants merged; top 400 rows. Built from EXHAUSTIVE per-slice runs — the 2026-07-08 build merged only each run's top-400 recipient rows, so diversified member figures here recover sub-cutoff variants (native column unchanged).",
 "crypto_ld203_member_variant_audit.csv": "QA audit for the member merge (regenerated 2026-07-11 at the three-slice grain, exhaustive inputs): every raw filed recipient string behind every merged member row, per giver slice.",
 "crypto_ld203_member_variant_audit_p6.csv": "P6 re-derivation of the audit with the shared member resolver — adds tier/confidence/source per row (committee tiers, inverted names, compounds).",
 "crypto_member_support_rollup.csv": "P6 member support rollup (regenerated 2026-07-11 at the three-slice grain): per member, direct giving per slice + tier-labeled committee support; JFC/multi-honoree money kept separate (never summed in).",
 "crypto_ld203_giving_by_org.csv": "Disclosed LD-203 giving per filer org — FULL recall roster.",
 "crypto_ld203_top_recipients.csv": "Top raw recipients — FULL recall roster.",
 "crypto_ld203_by_year.csv": "Disclosed LD-203 giving by year — FULL recall roster.",
 "crypto_ld203_core_by_org.csv": "As giving_by_org, restricted to the CORE roster (players with ≥8 crypto filings).",
 "crypto_ld203_core_by_year.csv": "As by_year, CORE roster.",
 "crypto_ld203_core_recipients.csv": "As top_recipients, CORE roster.",
 "crypto_ld203_pureplay_by_org.csv": "As giving_by_org, restricted to the hand-triaged 105-name crypto-NATIVE (pure-play) roster.",
 "crypto_ld203_pureplay_by_year.csv": "As by_year, pure-play roster.",
 "crypto_ld203_pureplay_recipients.csv": "As top_recipients, pure-play roster.",
 "crypto_fec_superpac_vs_ld203.csv": "The two disclosure regimes side by side: each player's FEC contributions INTO the Fairshake Super-PAC network vs its disclosed LD-203 giving.",
 "crypto_fec_committees.csv": "The Fairshake-network committees, resolved live from openFEC.",
 "crypto_fec_unmatched_network_donors.csv": "Network contributors that did NOT match any roster player (candidates for triage).",
 "crypto_record_samples_qa.csv": "Spot-check anchors: one top filing per major player, with the exact matched keyword.",
}

GLOSSARY = {
 "player": "Entity-resolved client organization name (entities.canonical_name; 'unresolved:<name>' when no entity matched)",
 "entity_id": "Resolver entity id (joins entities.entity_id)",
 "crypto_filings_senate": "DISTINCT crypto-tagged senate filings (LD-1 + LD-2, incl. amendments) naming this client",
 "first_year": "First year with a crypto-tagged filing",
 "last_year": "Latest year with a crypto-tagged filing",
 "total_all_issue_spend": "Client's TOTAL federal lobbying spend 2022–2026Q1 across ALL issues (sum of v_client_canonical_spend) — a size signal; dollars cannot be split by issue",
 "crypto_term_in_name": "'yes' if a crypto term appears in the org's own name (the 8% that a name search would find)",
 "tier": "core = ≥8 crypto filings · active = 3–7 · peripheral = ≤2 (in the audit_p6/rollup files: the support tier — direct / campaign-committee / leadership-pac / jfc-shared / multi-honoree)",
 "crypto_activity_blocks": "DISTINCT crypto-tagged senate free-text activity blocks for this client — the activity-share numerator (curated-lexicon tags; registrations excluded)",
 "all_activity_blocks": "ALL the client's senate free-text activity blocks — the activity-share denominator (non-registration filings; amendments on both sides of the ratio — same semantics as the healthcare package's activity share)",
 "crypto_activity_share_pct": "crypto_activity_blocks ÷ all_activity_blocks × 100 — the INTENSITY metric (added 2026-07-11): how much of the filer's declared lobbying attention is crypto. A count ratio, NEVER a dollar split. Entity-grain: resolver-split families (Mastercard ×3 at 58/18/9%) each carry their own share",
 "crypto_share_band": "Intensity band from the share: dedicated ≥25% · engaged 5–25% · ambient <5% · 'n/a (registrations only)' when the client has no non-registration senate blocks. The ≥5% line is the giving/money-list gate (editorial cut, disclosed on-chart)",
 "filing_year": "Reporting year",
 "filing_period": "Quarter (first_quarter … fourth_quarter)",
 "filing_type": "Senate filing type code (R* = LD-1 registration; Q* = LD-2 quarterly, suffix A = amendment)",
 "registrant_name": "Lobbying org (registrant) as filed",
 "reported_amount": "The filing's reported income-or-expenses figure — a per-filing ranking signal, NOT summable across rows (amendments; use v_client_canonical_spend for spend)",
 "filing_uuid": "Senate filing citation key (show_record.py / lda.senate.gov)",
 "lda_public_url": "Public raw record: https://lda.senate.gov/filings/public/filing/<uuid>/print/",
 "crypto_filings": "Crypto-tagged senate filings in scope",
 "crypto_clients": "Distinct resolved clients with a crypto-tagged filing that quarter",
 "canonical_spend_tagged_clients": "Sum of v_client_canonical_spend for that quarter's tagged clients (all-issue, rollup-corrected)",
 "issue_code": "ALI general issue code the text block was filed under",
 "crypto_docs": "Crypto-tagged text blocks under that code",
 "pct_of_crypto": "Share of all crypto-tagged text blocks",
 "keyword": "Curated lexicon phrase (industry_lexicon.json)",
 "filings": "Distinct filings the phrase tagged",
 "clients": "Distinct client ids on those filings",
 "reported_amount_ranking_signal": "Sum of reported income/expenses on the firm's crypto filings — ranking signal only (see reported_amount)",
 "quarter": "Calendar quarter (YYYY-Qn)",
 "all_releases": "All member press releases that quarter",
 "crypto_releases": "Releases whose title/text matches the crypto regex",
 "crypto_share_pct": "crypto_releases / all_releases × 100",
 "recipient": "Recipient display row (member-merged where a member matched; else lightly-normalized org string)",
 "recipient_raw": "Raw honoree/payee string as filed (lightly normalized for grouping, NOT entity-resolved)",
 "party": "(P-ST) bracket for member-matched recipients; empty for orgs",
 "party_source": "Where the party/state annotation came from (members-table vs manual hand-mapping in the 2026-07-08 build; member_terms in P6 files)",
 "from_crypto_native": "Disclosed LD-203 giving from the 105 hand-triaged crypto-native orgs",
 "native_items": "Item count behind that figure",
 "from_diversified_forward": "Disclosed LD-203 giving from the 147 CRYPTO-FORWARD diversified core players (≥8 crypto filings AND ≥5% crypto activity share) — the 2026-07-11 intensity gate",
 "forward_items": "Item count behind that figure",
 "from_ambient_lowshare": "Disclosed LD-203 giving from the 15 ambient core players BELOW the 5% share gate (AARP, U.S. Chamber, Amazon, Meta, Wells Fargo…) — context: shown in tooltip/click-through/table, never drawn as a bar in a crypto chart. forward + ambient partition the old diversified-core slice exactly (asserted per raw recipient at build time)",
 "ambient_items": "Item count behind that figure",
 "name_variants_combined": "How many distinct filed spellings merged into this row",
 "member (merged row in the split CSV)": "The member row the raw string was merged into (display name + party bracket)",
 "member": "Member display name (+ party bracket where present)",
 "giver_slice": "Which giver roster the money came from: crypto_native / diversified_forward (≥5% crypto activity share) / ambient_lowshare (<5%) — the 2026-07-11 three-tier cut; forward + ambient partition the old diversified_core exactly",
 "raw_recipient_string_as_filed": "The exact recipient string on the LD-203 item(s)",
 "total": "Dollar total (amendment-deduplicated)",
 "items": "Number of itemized contributions behind the total",
 "confidence": "Match confidence label (matched / title-chamber / title-initial / inverted / alias / linked / inferred / prefix / compound:*) — inferred rows need human confirmation; alias = curated full-string spelling from member_aliases.json (source recorded there)",
 "source": "Which resolution path produced the match (person-name / committee-exact / committee-prefix + FEC link source)",
 "bioguide_id": "Member's bioguide id (members_all key)",
 "direct_crypto_native": "Direct gifts (member named as honoree) from the crypto-native slice",
 "direct_diversified_forward": "Direct gifts from the crypto-forward diversified slice (≥5% crypto activity share)",
 "direct_ambient_lowshare": "Direct gifts from the ambient (<5% share) slice — context, not crypto-attributable",
 "campaign_committee": "Giving to the member's FEC-designated principal/authorized campaign committee(s)",
 "leadership_pac": "Giving to the member's leadership PAC (FEC designation D, sponsor-linked)",
 "total_attributable": "direct + campaign_committee + leadership_pac (the defensible member total)",
 "jfc_shared_unallocated": "Giving to joint-fundraising committees the member participates in — SHARED, never allocated or summed into the member",
 "multi_honoree_shared_unallocated": "Items honoring several members at once — shared, unallocated",
 "n_variant_rows": "Distinct (raw string × tier) rows behind this member",
 "confidence_flags": "Non-default confidence labels present (empty = all exact/linked)",
 "ld203_filer_org": "The LD-203 filer (registrant) the giving is filed under",
 "disclosed_giving_total": "Amendment-deduplicated disclosed LD-203 giving 2022–2025",
 "crypto_filings_senate_note": "The filer's crypto-tagged filing count where it is also a mapped player (context)",
 "match_confidence": "FEC↔LDA name-match confidence — candidates for human confirmation, never auto-merged",
 "fec_superpac_contributions": "Itemized line-11 contributions INTO the Fairshake network (memo rows and sale proceeds excluded), 2024+2026 cycles",
 "fec_items": "FEC transactions behind that figure",
 "ld203_disclosed_giving": "The player's disclosed LD-203 giving (the other regime)",
 "delta_fec_minus_ld203": "The Super-PAC money LD-203 legally cannot see",
 "fec_contributor_names": "FEC contributor name strings that matched the player",
 "committees": "Which network committees received the money",
 "sample_transaction_ids": "FEC transaction ids for spot-checking (cached raw in out/fec_cache/)",
 "committee_id": "FEC committee id",
 "name": "Committee name (FEC)",
 "type": "FEC committee type",
 "cycles": "Election cycles the committee reports in",
 "fec_contributor_name": "Contributor name as it appears in FEC data",
 "client_name": "Client as filed on the sampled filing",
 "amount": "Reported income/expenses on that filing (ranking signal)",
 "keyword_example": "One lexicon phrase found in the filing's activity text",
 "show_record_key": "Citation key for skills/lda-corpus-loader/scripts/show_record.py",
 "n_crypto_blocks_in_filing": "How many of the filing's free-text blocks under this issue code are crypto-tagged",
 "matched_keywords": "The exact curated lexicon phrase(s) (industry_lexicon.json) found in the filing's issue text — the reason the filing is tagged; Ctrl-F any of them on the linked lda.senate.gov page to see them in context",
 "has_inhouse_filing": "TRUE if the client self-filed (in-house) that quarter — see v_client_canonical_spend",
 "inhouse_amount": "Amount on the client's own in-house filing(s) that quarter",
 "outside_amount": "Sum of what outside firms reported for the client that quarter",
 "canonical_spend": "greatest(inhouse, outside) — the sanctioned spend figure (never the sum)",
 "method": "Which branch produced canonical_spend (in-house total vs outside sum)",
 "n_filings": "Filings behind the quarter after amendment-dedup",
 "display_row": "The dashboard giving-chart row this item rolls into (member-merged / variant-merged label)",
 "filer_type": "'organization' = the registrant's own LD-203 report · 'lobbyist' = an individual lobbyist's report",
 "contributor_name": "Contributor as filed on the LD-203 item",
 "date": "Date as filed",
 "contribution_type": "feca · he (honorary) · me (meeting/event) · pic (presidential inaugural) · ple (presidential library)",
 "n_amendment_versions": "How many filed versions carried this identical item (amendments collapse; the linked filing_uuid is one of them)",
 "member_name": "Member of Congress (press corpus display name)",
 "state": "Member state",
 "chamber": "House / Senate",
 "title": "Release title",
 "url": "Original release URL (may rot — the scraped text in the corpus is the evidence)",
 "src_file": "Raw-record pointer: source file in the corpus download",
 "src_line": "Raw-record pointer: line within src_file (citation key = src_file:src_line)",
}


def main():
    L = []
    w = L.append
    w("# Data dictionary — crypto lobbying package")
    w("")
    w(f"Generated {date.today().isoformat()} from the live database schema "
      "(`db/lda_full.duckdb`) and the CSV headers in `data/` — regenerate with "
      "`_build/export_data_dictionary.py` after any schema/export change.")
    w("")
    w("Two sections: **the database tables/views** referenced by the dashboard's "
      "queries (every widget's \"View query info\" shows the SQL; this file defines "
      "what the tables and columns mean), then **every CSV in `data/`**.")
    w("")
    w("Conventions that apply everywhere: dollar figures are self-reported disclosure "
      "data; senate is the primary chamber (House copies are never added on top); "
      "citation keys — Senate `filing_uuid` (resolves at "
      "`https://lda.senate.gov/filings/public/filing/<uuid>/print/`), press "
      "`src_file:src_line`; \"disclosed\" never means \"total\".")
    w("")
    w("## 1. Database tables & views (as referenced by the widget queries)")

    con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)
    missing = 0
    for tname, (desc, cols) in TABLES.items():
        n = con.execute(f"SELECT count(*) FROM {tname}").fetchone()[0]
        schema = con.execute(f"DESCRIBE {tname}").fetchall()
        w("")
        w(f"### `{tname}` — {n:,} rows")
        w("")
        w(desc)
        w("")
        w("| column | type | meaning |")
        w("|---|---|---|")
        for c in schema:
            note = cols.get(c[0])
            if note is None:
                note = "*(no annotation yet — flag it)*"
                missing += 1
                print(f"  ! unannotated DB column: {tname}.{c[0]}")
            w(f"| `{c[0]}` | {c[1]} | {note} |")
    con.close()

    w("")
    w("## 2. Package CSVs (`data/`)")
    data_dir = os.path.join(PKG, "data")
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".csv"):
            continue
        with io.open(os.path.join(data_dir, fname), encoding="utf-8-sig") as f:
            header = next(csv.reader(f))
        desc = FILE_DESC.get(fname)
        if desc is None:
            desc = "*(no file description yet — flag it)*"
            missing += 1
            print(f"  ! undescribed CSV: {fname}")
        w("")
        w(f"### `data/{fname}`")
        w("")
        w(desc)
        w("")
        w("| column | meaning |")
        w("|---|---|")
        for col in header:
            note = GLOSSARY.get(col)
            if note is None:
                note = "*(no annotation yet — flag it)*"
                missing += 1
                print(f"  ! unannotated CSV column: {fname}:{col}")
            w(f"| `{col}` | {note} |")

    out = os.path.join(PKG, "DATA_DICTIONARY.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"[md] DATA_DICTIONARY.md written ({len(L)} lines; "
          f"{'COMPLETE — every column annotated' if missing == 0 else f'{missing} gaps flagged'})")


if __name__ == "__main__":
    main()
