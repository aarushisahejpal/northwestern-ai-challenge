# Healthcare Lobbying — State of the Industry (research package)

**Status: unverified research output for team review and QA** — generated 2026-07-08.
Nothing here is a locked finding; every number traces to a CSV in `data/`, and rows trace to
raw records via `show_record.py` (`data/hc_record_samples_qa.csv` has ready-made anchors).

**Scope:** filings whose activities carry ALI issue codes **HCR** (health issues), **MMM**
(Medicare/Medicaid), **PHA** (pharmacy), or **MED** (medical research). Healthcare — unlike
crypto — is code-visible, so the issue-code lens is primary here.

**Start here:** open `healthcare_dashboard.html` (self-contained, offline, light/dark).
`data/hc_players.csv` is the master table for hands-on work.

## Headline findings (candidate, unverified)

1. **The largest standing lobbying operation in Washington, and remarkably stable.**
   ~4,000 health-coded filings and ~2,950 distinct clients *every quarter* for 2022–2024,
   then a visible 2025 rise (peak 4,384 filings / 3,202 clients, +9%) during the reconciliation
   Medicaid fight. Canonical spend of health-active clients: **$1.69B in 2025** (all-issue
   dollars of clients filing on health that quarter — an upper-bound size signal).
2. **Two species of big player.** Pure-plays whose lobbying is mostly health-coded — PhRMA
   ($136M spend, 67% health activities), American Hospital Association ($103M, 51%), AMA ($97M,
   49%), AHIP ($61M, 75%) — versus diversified giants where health is one desk: AARP (21%),
   Amazon (6%), U.S. Chamber (5%). `hc_players.csv` carries the activity-based share so the two
   are never conflated (filing-level shares mislead for self-filers — see caveats).
3. **Congress talks healthcare constantly, and 2025 set records.** Health codes tag 14–22% of all
   member press releases in a normal quarter, climbing through 2025 to **28.8% in 2025-Q4**
   (Medicaid cuts + ACA-subsidy-cliff fight). The filing base barely moves while press attention
   swings — the same money-vs-messaging divergence the ledger logged as L026 on MMM.
4. **The crowded bills:** HR1 (2025 reconciliation — 792 distinct clients), HR5376 (IRA drug
   pricing — 598), HR2617, HR2471 (omnibus vehicles), plus PBM/transparency bills (HR5378,
   S1339-family) (`data/hc_bills.csv`).
5. **Who healthcare gives to (disclosed LD-203) — split by giver type.** $107.8M from the top-150
   health lobbying orgs 2022–2025, election-year cadence ($28.3M/$23.8M/$32.4M/$23.3M), now split
   into HEALTH-FOCUSED givers (≥50% health activities: AHA $9.7M, Elevance $5.0M, American
   Optometric $4.0M, Eli Lilly $3.2M — $66.8M of the total) vs MIXED/diversified givers (AARP
   $8.0M, Altria $6.5M, J&J $4.0M, ADA/AMA/Abbott — $47.5M). Recipients draw from both:
   party committees run ~60:40 focused-to-mixed (DSCC $824K/$484K, NRSC $802K/$495K); top member
   recipients include Rep. Jason Smith (R-MO) $519K/$230K, Sen. Bob Casey (D-PA) $579K/$68K,
   Rep. Brett Guthrie (R-KY) $482K/$134K, Sen. Margaret Hassan (D-NH) $570K/$0
   (`data/hc_ld203_recipients_split.csv`, party brackets from the corpus `members` table, retired
   members hand-mapped). Spread across both parties — an access pattern, not a partisan bet; the
   split shows *who funds whom*, not whether the motive was a health issue.

## What's in the package

| File | What it is |
|---|---|
| `healthcare_dashboard.html` | Interactive dashboard — player map, trends, issue mix, press coupling, bills, giving |
| `data/hc_players.csv` | **Master table**: 400 clients, health filings, activity-based health share, canonical spend |
| `data/hc_quarterly_trend.csv` | Filings / clients / canonical spend per quarter |
| `data/hc_code_trend.csv` | Per-code quarterly filing counts (HCR/MMM/PHA/MED) |
| `data/hc_registrant_firms.csv` | Top outside firms on health filings |
| `data/hc_bills.csv` | Most-crowded bills |
| `data/hc_press_coupling.csv` | Health press share vs spend, quarterly |
| `data/hc_ld203_recipients_split.csv` | **Recipients split by giver type** (health-focused vs mixed), member name variants merged, party brackets + source |
| `data/hc_ld203_member_variant_audit.csv` | **QA audit trail for the member merge**: every raw recipient string that rolled into each member row, per slice |
| `data/hc_ld203_*.csv` | Disclosed giving: by org, recipients, by year |
| `data/hc_record_samples_qa.csv` | Spot-check anchors with `show_record.py` keys |
| `data/hc_player_filings.csv`, `hc_trend_filings.csv`, `hc_code_trend_filings.csv`, `hc_press_releases.csv`, `hc_bill_filings.csv`, `hc_giving_org_items.csv`, `hc_giving_recipient_items.csv` | **Raw-record indexes** behind every dashboard widget's click-through (each row links to the filing/contribution on lda.senate.gov); the dashboard embeds a capped sample (top 150 by $ per bucket) — these CSVs carry the full lists |

## How to QA a number

1. Take a `show_record_key` from `data/hc_record_samples_qa.csv`.
2. `.venv/Scripts/python skills/lda-corpus-loader/scripts/show_record.py <key> --data-root "../data/data" --db db/lda_full.duckdb`
3. Aggregates re-derive with: health scope = `senate_activities.general_issue_code IN
   ('HCR','MMM','PHA','MED')`; dedup on `(registrant_id, client_id, filing_year, filing_period)`
   latest-by-`posted` (`queries/sweep_2026.sql#H1c` pattern); spend only via
   `v_client_canonical_spend`; press side via `press_issue_mentions`.

## Method & caveats

- **Senate-primary, amendment-deduped, registrations excluded** from dollar work.
- **Spend is all-issue.** A client's quarterly dollars can't be split by issue at the filing
  grain; "$1.69B" means "the 2025 canonical spend of clients who filed on health," not
  "health-only dollars." Treat as an upper-bound size signal.
- **Health share is computed on activity rows, not filings.** A self-filer's single quarterly
  filing lists dozens of issue codes, so filing-level share reads ~100% for every mega-filer
  (the U.S. Chamber would look like a health pure-play). Activity share is the honest signal.
- **LD-203 giving is organization-level** — solid for pure-play trade groups, inflated for
  diversified filers (AARP's or Altria's giving is not health-specific). Recipient names are
  lightly-normalized filing strings, not entity-resolved.
- The dashboard's player map filters to meaningful health players (share ≥10% or ≥30 health
  filings); the CSV keeps everyone, including the GM/Lockheed one-off filers.

## Reproduce

Scope + exports re-run from the session build script (see `_build/export_healthcare.py`); tool runs:

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py --names-file out/healthcare_roster.txt --top 80 --json
```

`out/healthcare_roster.txt` = top-150 health clients by health-coded filings.
