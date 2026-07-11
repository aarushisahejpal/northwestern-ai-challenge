# Crypto Lobbying — State of the Industry (research package)

**Status: unverified research output for team review and QA** — generated 2026-07-08 from a
from-scratch re-derivation (serving table rebuilt from lexicon v1.0, roster regenerated, both
money legs re-run). Nothing here is a locked finding; every number below traces to a CSV in
`data/`, and every CSV row traces to raw records via `show_record.py`.

**Start here:** open `crypto_dashboard.html` in any browser (self-contained, works offline,
light/dark). For hands-on exploration, the CSVs in `data/` open directly in Excel/Sheets
(UTF-8 BOM). `data/crypto_players.csv` is the master table.

## Headline findings (candidate, unverified)

1. **The industry is invisible to a name search.** 508 client-side organizations lobbied on
   crypto 2022–2026Q1 (senate-side, entity-resolved); **466 of them (92%) have no crypto term in
   their name** — PayPal, Visa, Mastercard, Robinhood, Fidelity/FMR, Citigroup, CME Group,
   American Bankers Association. They were found only by what their filings *say* they lobby on
   (43-phrase curated vocabulary over the filing free-text).
2. **Only 43.7% of crypto lobbying text sits under the "Financial Institutions" issue code.**
   The rest scatters across banking (23.8%), taxation (8.4%), science/tech, computers,
   commodities, agriculture and 40+ more codes (`data/crypto_issue_code_scatter.csv`) — exactly
   the "hidden under issues related to taxation" problem the reporter asked about.
3. **2025 is the breakout year.** Crypto-tagged filings were flat ~230/quarter through 2022–2024,
   then rose every quarter of 2025 to 391 (2025-Q4); distinct clients 177 → 287 (+62% YoY).
   2026-Q1 holds the plateau (372/268). Timing matches the GENIUS Act (stablecoins) and
   market-structure (FIT21/CLARITY) pushes.
4. **Who they give to (disclosed LD-203) — split by who it's FROM.** Every recipient is split into
   giving from the 105 hand-triaged crypto-NATIVE orgs ($6.37M total 2022–25; $5.0M of it the
   Trump-Vance inaugural cluster; Galaxy Digital $1.08M is a top giver the old roster missed) vs
   giving from the 162 DIVERSIFIED core players — banks, card networks, asset managers with a
   sustained crypto lobbying record ($110.7M org-level) — in
   `data/crypto_ld203_recipients_split.csv`. The member-level answer: **Sen. Pat Toomey (R-PA)
   $53.8K — all crypto-native, $0 from the diversified slice**; Sen. Cynthia Lummis (R-WY) roughly
   even ($45.5K / $56K); Sen. Bernie Moreno (R-OH) all-native ($16K / $0); while the financial-
   committee leadership is funded overwhelmingly by the incumbents — Rep. French Hill (R-AR)
   $37.5K native vs **$858K** diversified, Rep. Bill Huizenga (R-MI) $4K / $761K, Rep. Andy Barr
   (R-KY) $9K / $734K, Rep. Tom Emmer (R-MN) $76K / $584K, Sen. Tim Scott (R-SC) $23K / $530K.
   Attribution caveat: LD-203 is organization-level — a bank PAC's gift to a Financial Services
   member is not necessarily crypto-motivated; the split shows *who funds whom*, not why.
   Party/state brackets come from the corpus `members` table; members who have since left
   Congress (Toomey, McHenry, Sherrod Brown…) are hand-mapped and flagged `manual` in the CSV.
5. **LD-203 understates the political money ~60×.** The same players' contributions into the
   Fairshake Super-PAC network (FEC, itemized): Coinbase **$106.6M**, Ripple **$96.5M**,
   a16z **$94.5M**, Jump Crypto **$25M** — vs $1.7M/$0/$0/$0 in LD-203. Different legal regimes;
   they never sum, and any story must say "disclosed lobbying giving" vs "Super-PAC contributions."

## What's in the package

| File | What it is |
|---|---|
| `crypto_dashboard.html` | Interactive dashboard (bubble player map, trends, issue scatter, giving, FEC-vs-LD-203) — every chart has a "Table view". **Rev 2026-07-09** (Rob's review): map bubbles sized by total lobbying DOLLARS (all issues) instead of filing counts — selection still by sustained crypto filings so a giant all-issue budget alone doesn't buy a spot; click a bubble to list that player's raw filings (LD-2 reports and LD-1 registrations grouped separately), each linking to lda.senate.gov; name-invisibility stat tile removed. **Rev 2026-07-10**: every widget carries a hover ⋯ menu → “View query info” showing the ACTUAL SQL (or tool pipeline) that produced its numbers, extracted at build time from the export scripts so it cannot drift — shown as a modal, with every referenced table/column defined in DATA_DICTIONARY.md. **Rev 2026-07-10 (2)**: EVERY widget is now click-through to its underlying records — trend quarters, issue codes, spend bars, giving recipients, FEC players, and press quarters each open a panel listing the actual filings/items/releases behind the clicked mark, with public links (lda.senate.gov filing + contribution pages, FEC receipts browser, release URLs); every list reconciles to its chart figure at export time |
| `DATA_DICTIONARY.md` | **Data dictionary (added 2026-07-10)**: every database table/view the widget queries reference (columns pulled live from the DB schema + curated meanings, incl. the traps — dedup keys, income-vs-expenses, registrant-scoped client_id) and every CSV in `data/`, column by column. Regenerate: `_build/export_data_dictionary.py` |
| `data/crypto_players.csv` | **Master table**: 508 entity-resolved players, crypto filings, tier (core/active/peripheral), name-visibility flag, total canonical spend |
| `data/crypto_player_filings.csv` | **Raw-filing index (added 2026-07-09)**: every crypto-tagged senate filing behind every player — year/quarter, registrant, reported amount, `filing_uuid`, and a public `lda.senate.gov` URL per filing; per-player counts reconcile with `crypto_players.csv` |
| `data/crypto_quarterly_trend.csv` | Filings / clients / canonical spend of active clients, per quarter |
| `data/crypto_issue_code_scatter.csv` | Where crypto hides: issue-code distribution of tagged text |
| `data/crypto_keywords.csv` | Which of the 43 lexicon phrases carried the signal |
| `data/crypto_registrant_firms.csv` | Top outside lobbying firms on crypto filings |
| `data/crypto_press_quarterly.csv` | Crypto share of congressional member press releases |
| `data/crypto_ld203_recipients_split.csv` | **Recipients split by giver type** (crypto-native vs diversified core), person/org name variants merged, party brackets + source |
| `data/crypto_ld203_member_variant_audit.csv` | **QA audit trail for the member merge**: every raw recipient string (as filed) that rolled into each member row, per slice — verify any merged number by summing its rows (e.g. Emmer's $76.4K native = 5 filed spellings; the old single-string view showed only the largest, $50K) |
| `data/crypto_ld203_*.csv` | Disclosed giving at three roster tiers: full recall roster / core (≥8 filings) / hand-triaged pure-play — recipients, by-org, by-year |
| `data/crypto_fec_*.csv` | Fairshake-network reconciliation (FEC vs LD-203), committees, unmatched network donors |
| `data/crypto_trend_filings.csv` | **Trend click-through**: the filings behind each quarter, in the chart's own dedup semantics — per-quarter counts reconcile with the chart |
| `data/crypto_issue_code_filings.csv` | **Scatter click-through**: senate filings behind each issue code's crypto-tagged blocks, with per-filing block counts |
| `data/crypto_spend_quarters.csv` | **Money click-through**: every player's quarter-by-quarter `v_client_canonical_spend` rows — per-player sums reconcile with the spend bars |
| `data/crypto_ld203_items.csv` | **Giving click-through**: the amendment-deduped LD-203 items behind every displayed recipient row — sums reconcile with the chart; each item links to the filed report |
| `data/crypto_press_releases.csv` | **Press click-through**: every crypto-matching release with URL + `src_file:src_line` citation key — per-quarter counts reconcile with the chart |
| `data/crypto_record_samples_qa.csv` | Spot-check anchors: one top filing per major player with its `show_record.py` key |

## How to QA a number

1. Pick any row in `data/crypto_record_samples_qa.csv` (or any `show_record_key`).
2. From the repo root:
   `.venv/Scripts/python skills/lda-corpus-loader/scripts/show_record.py <key> --data-root "../data/data" --db db/lda_full.duckdb`
3. Confirm the filing's activity text contains the keyword, and the client/amount match the CSV.
4. Aggregates: the citeable SQL patterns are `queries/p4_industry_map.sql` (P4a–P4e) and
   `queries/ld203_giving.sql`; the dedup rule is `queries/sweep_2026.sql#H1c`.

## Method & caveats (the ones that bite)

- **Senate-primary; never sum the two chambers** (the same quarterly is filed with both).
  Filings amendment-deduped on `filing_period`, latest by `posted`. Registrations excluded from
  dollar work.
- **Recall-first roster.** Any client whose free-text names a lexicon phrase once is included;
  incidental mentions (AARP consumer-protection filings, unions) sit in the peripheral/low tiers
  *by design*. A story names specific players, never "the whole list."
- **Spend is all-issue.** Filing-level disclosure cannot split dollars by issue. Player spend =
  total canonical lobbying spend (`v_client_canonical_spend`, in-house/outside double-count
  corrected). For pure-plays ≈ crypto money; for Visa et al. it is not.
- **LD-203 giving is organization-level and registrant-filed** — not issue-attributable, never
  client-attributable for outside firms, and legally excludes Super-PAC money.
- **FEC matches are candidates.** FEC contributor names ≠ filing names; matches carry confidence
  labels and need human confirmation. FEC pull counts line-11 contributions only (sale proceeds,
  transfers, memo/attribution shadows excluded); raw responses cached in `out/fec_cache/`
  (key never stored). Run used DEMO_KEY + cache.
- **Entity resolution is the ceiling.** Kraken/Payward, a16z, Foris/Crypto.com file under several
  names; the dashboard combines known families with a note, the CSVs keep per-variant rows.
- **"Disclosed" never means "total".** 501(c)(4) dark money and state lobbying are outside every
  number here.

## Reproduce

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py --build-tags
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py crypto --top 60 --json
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py --names-file out/crypto_roster.txt --top 100 --json
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py --names-file out/crypto_roster_pureplay.txt --top 60 --json
.venv/Scripts/python skills/lead-scanner/scripts/fec_enrich.py --names-file out/crypto_roster.txt --json
```

Rosters used: `out/crypto_roster.txt` (full, 535 names incl. house-side variants),
`out/crypto_roster_core.txt` (222), `out/crypto_roster_pureplay.txt` (105, hand-triaged).
Ledger context: L029–L031 (this package re-derives them from scratch, 2026-07-08).
