# Data dictionary — turnover package

Every CSV is written by `_build/export_turnover.py` from `db/lda_full.duckdb` (read-only), by
calling the P3 tool's own query functions (`skills/lead-scanner/scripts/lda_turnover.py`).

**File naming:** quarter-scoped files carry the report quarter tag — `turnover_<QTAG>_*.csv`
with `<QTAG>` = `2025Q4`, `2026Q1`, … (one set per `export_turnover.py <QTAG>` run; the
dashboard picks up every exported quarter as a switchable view). The two corpus-wide files
(`turnover_quarterly_trend.csv`, `turnover_trend_top.csv`) are unsuffixed and identical across
runs. Section headings below use the unsuffixed stem; "target quarter" means the file's QTAG.

Common column meanings:

- **quarter** — `YYYY-QN`, from `filing_year` + `filing_period` (senate LD-2 quarters).
- **filing_uuid / term_uuid / hire_uuid / cite_uuid** — Senate `filing_uuid`, the citation key;
  resolve offline with `show_record.py <uuid>` or open the paired `*lda_public_url`
  (`https://lda.senate.gov/filings/public/filing/<uuid>/print/`).
- **registrant / client** — as filed (registrant) and the resolver's canonical client name where
  resolved (`entities`/`entity_aliases`); pair identity everywhere is
  registrant_id × resolved client entity (never `client_id`).
- Dollar columns are amendment-deduped quarterly `income` (dedup on `filing_period`, latest by
  `posted`), except `client_q_canonical_spend` which reads `v_client_canonical_spend`.

## turnover_<QTAG>_summary.csv (1 row)
| column | meaning |
|---|---|
| quarter | target quarter of the report (2025-Q4) |
| terminations / new_engagements | distinct pairs with a declared termination / a first-ever filing in the target quarter |
| swap_rows | term→hire pairs within ±1 quarter (a client may have several) |
| swap_clients | distinct clients across those rows |
| inhouse_moves | swap rows whose new (or old) registrant resolves to the client itself |
| prev_q_* / yoy_q_* | same counts for the previous quarter and the same quarter a year earlier |
| top_termination_* | row 1 of turnover_terminations.csv |

## turnover_quarterly_trend.csv (P3a)
`quarter, terminations, new_engagements` per quarter 2022-Q1–2026-Q1. 2022-Q1 `new_engagements`
is the corpus edge (every pair is "new") — the dashboard suppresses it.

## turnover_<QTAG>_terminations.csv (P3b; all target-quarter terminations)
| column | meaning |
|---|---|
| trail4_income | the pair's deduped income over the 4 quarters ending at the target quarter — "the book that ended" |
| n_quarters | deduped activity quarters the pair ever filed |
| first_seen | the pair's first quarter (any filing type, incl. registration) |
| new_this_q | True = the engagement also STARTED in the target quarter (one-quarter engagement) |
| re_engaged | count of the pair's quarters AFTER the target quarter (came back — a pause, not an exit) |
| term_uuid | one termination filing of the pair in the target quarter (min uuid when several versions) |

## turnover_<QTAG>_new_engagements.csv (P3c; all target-quarter first-ever pairs)
| column | meaning |
|---|---|
| q_income | deduped income of the pair's target-quarter activity filing (blank = registration-only so far) |
| cite_uuid | the activity filing if present, else the first filing (the LD-1 registration) |
| registration_only | True = no activity filing yet |
| terminated_same_q | True = the pair also filed a termination in the target quarter |

## turnover_<QTAG>_new_engagement_filings.csv
Every target-quarter filing (all types, incl. RR/amendments) of every new pair — the click-through
behind the "new engagements" widget.

## turnover_<QTAG>_swaps.csv (P3d; all term→hire pairs)
| column | meaning |
|---|---|
| hire_dq | new engagement's first quarter minus the target quarter (−1/0/+1) |
| move | `to-inhouse` / `from-inhouse` when a registrant norm-key equals the client's (P1 bridge); blank = firm→firm |
| client_q_canonical_spend | the client's `v_client_canonical_spend` in the target quarter (size context) |
| term_uuid / hire_uuid (+ *_lda_url) | the two sides of the move |

## turnover_<QTAG>_firm_churn.csv (P3e; every registrant with churn)
`n_lost` = distinct client entities with a declared termination in the target quarter;
`lost_trail4_income` = summed trailing-4-quarter income of those engagements; `n_new` = first-ever
engagements signed; `net = n_new − n_lost`.

## turnover_trend_top.csv
Per quarter × kind (`term`/`hire`), the top 30 rows by `income_trail4_or_firstq`
(trail-4 income for terminations, first-quarter income for hires) — the trend click-through.
The target quarter's `term` list reconciles with turnover_<QTAG>_terminations.csv at export.

## turnover_<QTAG>_term_history.csv
For each of the 16 displayed termination bars: every deduped quarterly row of the engagement.
`in_trail4_window=True` rows sum to `bar_trail4_income` — asserted at export.

## turnover_<QTAG>_churn_clients.csv
For each of the 14 displayed scoreboard firms: its `lost` clients (with trailing income and the
termination filing) and `signed` clients (with first-quarter income; blank = registration-only).
List lengths reconcile with the scoreboard counts at export.

## turnover_<QTAG>_queryinfo_sql.json
`{"target_quarter", "sql": {widget → SQL}}` — captured from the actual export execution via a
recording connection (not copied by hand). These are the texts shown in the dashboard's
"View query info" modals. Citeable labeled equivalents: `queries/p3_turnover.sql` P3a–P3e.
