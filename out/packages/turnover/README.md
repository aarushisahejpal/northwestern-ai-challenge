# Lobbying Turnover — Quarterly Beat Report (research package)

Team-review package produced by the **P3 quarterly turnover tracker**
(`skills/lead-scanner/scripts/lda_turnover.py`). It diffs a report quarter against the full
Senate LDA corpus (2022–2026 Q1, `db/lda_full.duckdb`): who **ended** representation, who
**hired**, which clients **swapped firms or moved in-house**, and which **firms churned** the most.

**Two report quarters are loaded — 2025-Q4 (last complete quarter) and 2026-Q1 (newest,
a floor: terminations post with a lag).** The dashboard has a quarter switcher at the top;
the newest quarter opens by default, and `#2025-Q4` / `#2026-Q1` in the URL deep-links a quarter.

**Status: unverified research output.** Rows are candidate material for triage, not findings.
Every number traces to raw filings via the CSVs in `data/` — each row carries a `filing_uuid`
and a public `lda.senate.gov` URL.

## Headline rows (candidate, unverified)

**2025-Q4** — the biggest churn quarter in the corpus window:
- 1,432 declared terminations (vs 1,316 in 2024-Q4) and 1,213 first-ever engagements
  (vs 864 — +40% YoY). Q4 terminations run 22–43% above other quarters every year
  (year-end cleanup), so Q4 compares to prior Q4s.
- Biggest book that ended: TL Management closed a 16-quarter, $2.46M-trailing engagement with
  Stonington Global. Also: U.S. Steel ↔ Hogan Lovells ($980K), Scott Sheffield ↔ Brownstein
  ($650K — the L022 engagement).
- 270 clients changed representation; 14 moved in-house (Clearspeed, Madrigal, Fervo, Impulse
  Space…). Firm scoreboard: Ballard 25 lost / 41 signed; Strategies 360 lost 26, signed none.

**2026-Q1** (floor — the newest quarter in the DB):
- 1,075 declared terminations so far (vs 1,208 in 2025-Q1) and 1,831 new engagements
  (vs 2,590 in 2025-Q1 — the post-election signing wave cooling).
- **The biggest terminated book is a pardon engagement**: Joseph Schwartz ended a 4-quarter,
  $960K engagement with J M Burkman & Associates ("Seeking a federal pardon." — L034); Torence
  Hatch's $600K one-quarter Burkman pardon engagement also terminated this quarter.
- Biggest new engagement: Innovairre & Co. hired Checkmate at $1.0M in its first quarter.
- 139 clients changed representation (177 term→hire pairs, 9 in-house — the ±1-quarter window
  can only reach backward from the newest quarter).

**Candidate lead L034 (unverified, legal-sensitivity flag)**: individuals paying six figures to
seek pardons, with the engagements closed by termination filings — Roger Ver ($600K + $70K),
Torence Hatch ($600K), Joseph Schwartz ($960K + $100K). Whether the asks landed is the open
verification step (LEDGER L034). The full clemency-lobbying map is its own package:
`out/packages/pardons/`.

## What's in the package

- `turnover_dashboard.html` — the visual (both quarters, switchable). Every widget has (a) a
  **table view**, (b) a **⋯ → View query info** modal with the SQL that actually ran, and (c) a
  **click-through** listing the underlying filings, each linking to its raw record on
  `lda.senate.gov`.
- Quarter-scoped CSVs, one set per report quarter (`<QTAG>` = `2025Q4` / `2026Q1`):
  - `data/turnover_<QTAG>_summary.csv` — the KPI numbers (target vs prior quarter vs prior-year quarter).
  - `data/turnover_<QTAG>_terminations.csv` — every termination with engagement history + URLs (P3b).
  - `data/turnover_<QTAG>_new_engagements.csv` — every new engagement + URLs (P3c).
  - `data/turnover_<QTAG>_new_engagement_filings.csv` — every target-quarter filing behind each new pair.
  - `data/turnover_<QTAG>_swaps.csv` — every term→hire pair, in-house moves labeled, both URLs (P3d).
  - `data/turnover_<QTAG>_firm_churn.csv` — every registrant's lost/signed scoreboard (P3e).
  - `data/turnover_<QTAG>_term_history.csv` — the quarterly rows behind each displayed termination
    bar (they sum to the bar; reconciled at export).
  - `data/turnover_<QTAG>_churn_clients.csv` — displayed firms' lost + signed client lists.
  - `data/turnover_<QTAG>_queryinfo_sql.json` — the SQL captured from the actual export execution.
- Corpus-wide (quarter-independent): `data/turnover_quarterly_trend.csv` (P3a),
  `data/turnover_trend_top.csv` (per-quarter top terminations + hires, trend click-through).
- `DATA_DICTIONARY.md` — column definitions for every CSV.

## How to QA a number

1. Switch to the quarter in question, click the widget's bar/quarter — the panel lists the
   underlying filings; open any `lda.senate.gov` link to read the raw record (or use
   `show_record.py <uuid>` offline).
2. Open **⋯ → View query info** on the widget for the SQL that produced it, then re-run it
   against `db/lda_full.duckdb` (read-only). Citeable labeled blocks: `queries/p3_turnover.sql` P3a–P3e.
3. Cross-check against the tool:
   `.venv/Scripts/python skills/lead-scanner/scripts/lda_turnover.py 2026Q1 --json`
   — the dashboard is built by calling the same functions, and the export asserts the two agree.

## Method & caveats (the ones that bite)

- **Terminations are DECLARED, never inferred**: senate `filing_type` termination family
  (`1T–4T`, `TY`/`@` variants). Absence-between-quarters is NOT termination — late posting and
  partial House dumps would fabricate exits. House carries no termination signal (senate-only lens).
- **A termination is not always an exit**: `re_engaged` rows file again later; one-quarter
  engagements are hired-and-terminated inside the quarter. Both flagged.
- **"New" is grouped by resolved client entity, never `client_id`** — a re-registration re-issues
  `client_id` (worked example: Checkmate/Gunvor 2025-Q4 would otherwise read as both terminated
  and new). A renamed firm keeps one scoreboard identity via registrant_id (worked example:
  Ballard Partners → "Ballard Partners, LLC" across 2025→2026).
- **Dollars**: engagement rows use the pair's amendment-deduped quarterly income
  (`filing_period` dedup, latest by posted); client-size figures use `v_client_canonical_spend`
  (in-house vs outside never summed).
- **The newest quarter in the DB is a floor** — terminations post with a lag; 2026-Q1 counts
  will rise until the next corpus refresh, and its ±1-quarter swap window can only reach backward.
- **Turnover is evidence of movement, not motive.** Who ended/hired/swapped is in the disclosure;
  why is not.

## Reproduce

```bash
.venv/Scripts/python out/packages/turnover/_build/export_turnover.py 2025Q4   # one CSV set per quarter
.venv/Scripts/python out/packages/turnover/_build/export_turnover.py 2026Q1   # (+ reconciliation checks)
.venv/Scripts/python out/packages/_build/viz_build.py turnover                # the dashboard (all exported quarters)
```

DB rebuild (if needed): `lda-corpus-loader/build_db.py` → `lda-entity-resolver/resolve_entities.py`.
