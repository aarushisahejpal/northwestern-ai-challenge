# Transportation Lobbying — State of the Industry

*Generated 2026-07-13 · unverified research output for team review.*

Who lobbies Washington on moving people and goods: airlines, railroads, truckers and shippers, ports and maritime, and road/highway infrastructure — and who gives money to whom.

This package maps federal lobbying on transportation — the movement of people and goods — using the ALI issue-code lens (the healthcare pattern): filings whose senate activities carry TRA (Transportation, general), AVI (Aviation/Airlines/Airports), RRR (Railroads), TRU (Trucking/Shipping), MAR (Marine/Maritime/Boating/Fisheries), or ROD (Roads/Highway). Two adjacent codes were checked and excluded: AUT (Automotive Industry) is dominated by vehicle manufacturers, dealers and parts suppliers (GM, Ford, Toyota, NADA) lobbying on CAFE/EV-mandate/NHTSA vehicle regulation — a manufacturing sector, not a carriage one; AER (Aerospace) is dominated by launch and defense-satellite contractors (ULA, Boeing, SpaceX, Lockheed, RTX) lobbying on lunar programs, launch services and export licensing — the aerospace/defense-space industrial base, not transportation. Both calls are logged in DECISIONS.md with sample activity text.

The interesting split in this field is PURE-PLAY carriers (airlines, railroads, truckers, ports) versus SIDE-DESK diversified filers who touch transportation policy incidentally to a much larger, non-transportation lobbying operation (Amazon-class shippers, insurers, materials suppliers who ride ROD's highway-funding code). The players export's activity-share column (tagged senate activity blocks / all of the client's senate activity blocks, computed on ACTIVITY rows, never filings — the same fix the healthcare package needed for its self-filer distortion) is how the two are told apart.

Headline scope: 43,778 amendment-deduped tagged senate filings and 3,962 entity-resolved client organizations, 2022–2026 Q1 — a stable installed base (~2,000–2,250 distinct clients every quarter, no growth or collapse trend), not a surge industry. Canonical spend of tagged clients in the most recent full year (2025): $1.24B. Pure-play carrier trade groups sit at 100% activity share (Airlines for America, Aircraft Owners & Pilots Association, Owner-Operator Independent Drivers Association, American Maritime Partnership, Brotherhood of Locomotive Engineers); large individual carriers run lower because they lobby on much more than transportation (FedEx 35.1% share on 178 tagged filings, UPS 25.4% on 25). Side-desk diversified filers with large all-issue budgets but low transportation share include the U.S. Chamber of Commerce ($311.6M all-issue spend, 8.8% share), National Association of Realtors, Business Roundtable, Amazon, and AARP. The two most-cited bills are the Infrastructure Investment and Jobs Act (H.R.3684, 404 clients/2,199 filings) and the FAA Reauthorization Act of 2023 (H.R.3935, 294 clients/1,677 filings) — both squarely transportation legislation, a sanity check that the code set is on target. Full detail: data/trans_players.csv, data/trans_bills.csv.

Say-vs-pay here is a steady, high-baseline pattern, not a spike: member press share of transportation-tagged releases runs 5.3%-9.4% every quarter 2022-2026Q1 with no single dramatic outlier (unlike the healthcare package's 2025-Q4 press record) — but this reads on TRA/AVI/RRR/ROD vocabulary only; TRU and MAR have no press keywords at all (see caveats), so the true say-side share is understated. Disclosed LD-203 giving of the roster's top-150 organizations totals $136.01M 2022-2025 (2022 $36.77M / 2023 $29.84M / 2024 $35.56M / 2025 $33.84M); the #2 member recipient by attributable dollars is Rep. Sam Graves (R-MO, $737,550), who chairs the House Transportation & Infrastructure Committee — an expected validation of the roster, not a novel claim.

## What is in scope

Scope = filings whose senate activities carry issue codes TRA, AVI, RRR, TRU, MAR, ROD. Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated on (registrant, client, year, quarter) keeping the latest by posting date; registrations are excluded from dollar work. Client spend comes only from the double-count-corrected canonical spend view.

## Files

| file | rows | what it is |
|---|---|---|
| data/trans_bills.csv | 60 | Bills named in tagged filings' free-text, ranked by distinct clients. |
| data/trans_code_trend.csv | 102 | Per-quarter, per-code filing counts (which of the 6 codes is driving a quarter). |
| data/trans_ld203_by_org.csv | 84 | Disclosed LD-203 giving by the roster's registrant organizations. |
| data/trans_ld203_by_year.csv | 4 | Disclosed LD-203 giving by year. |
| data/trans_ld203_member_rollup.csv | 15 | Disclosed LD-203 giving rolled up to members of Congress (P6 resolver; rollup, never conflation — JFC/multi-honoree dollars stay unallocated). |
| data/trans_ld203_recipients.csv | 400 | Disclosed LD-203 giving by recipient (raw filed string). |
| data/trans_players.csv | 3962 | Entity-resolved player map: tagged filings, activity-share (pure-play vs side-desk), first/last year, total all-issue canonical spend. |
| data/trans_press_coupling.csv | 17 | Say-vs-pay: share of member press releases tagged to these 6 codes vs canonical spend of tagged clients, by quarter. See the caveat on thin press vocabulary for TRU/MAR. |
| data/trans_press_releases.csv | 9570 | The individual tagged press releases behind trans_press_coupling.csv — one row per release, with its URL and src_file:src_line citation key; backs the press widget's per-quarter click-through. |
| data/trans_quarterly_trend.csv | 17 | Quarterly tagged filings, distinct clients, and canonical spend of tagged clients, 2022-2026Q1. |
| data/trans_record_samples_qa.csv | 25 | One largest-filing sample per client, for spot-checking against raw records via show_record.py. |
| data/trans_registrant_firms.csv | 60 | Outside lobbying firms (registrant != client) ranked by tagged filings. |

## Caveats that matter

- Two adjacent ALI codes were deliberately excluded after checking their actual client rosters and free-text: AUT (Automotive Industry — vehicle manufacturing/dealers, a distinct sector) and AER (Aerospace — dominated by space-launch/defense-satellite contractors). Include them and you get a different, larger, and less coherent 'transportation' story.
- Press-coupling vocabulary is THIN and UNEVEN across the 6 codes: the press tagger's curated keyword dictionary (ISSUE_KEYWORDS in build_db.py) has phrases for TRA, AVI, RRR, and ROD, but NONE for TRU (trucking/shipping) or MAR (maritime) — those two codes contribute zero rows to trans_press_coupling.csv. The press share therefore understates say-side attention to trucking and maritime specifically; it is not a full picture of Congress's public transportation messaging.
- Activity share is computed on ACTIVITY rows (tagged senate activity blocks / all of a client's senate activity blocks), never filings — a self-filer's single quarterly can list a dozen issue codes, so filing-level share is a self-filer artifact (the same trap the healthcare package's entity_aliases fan-out bug exposed and fixed 2026-07-11).
- Player 'total lobbying spend' is ALL-ISSUE canonical spend (v_client_canonical_spend) — a size signal, not transportation-specific dollars. Per-item filing dollars are a ranking signal only (filing-level attribution grain).
- LD-203 giving is registrant-filed and organization-level, not attributable to transportation specifically for diversified filers, and is NOT FEC (no Super-PAC money here).
- Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated on (registrant, client, year, filing_period), latest by posted; registrations excluded from dollar work.
- This dashboard has per-filing click-through on the press widget only (click a quarter to see the matching releases, with links) — this lens's exporter doesn't produce per-filing indices for players/trend the way the facet lens or legacy bespoke crypto/healthcare dashboards do. Every number is still reconciled at build time and fully explorable via the CSVs in data/ and show_record.py.

## How to QA a number

1. This package's dashboard's press-coupling widget clicks through to the individual matching releases (with links); the other widgets (players, trend, registrants) are reconciled aggregate charts + full table views only, without per-filing click-through. Every CSV row still carries a citation key — senate `filing_uuid`, press `src_file:src_line` — resolvable via show_record.py.
2. Chart-vs-list reconciliation ran at build time and a mismatch fails the build (trend counts, per-player filing counts, press counts).
3. The SQL behind each widget is embedded in the dashboard (hover ⋯ → View query info) — it is the exact string the generator executed.

## Regenerate

```
python skills/industry-review-packager/scripts/lda_package_industry.py \
    skills/industry-review-packager/specs/transportation.json
```

This is unverified research output for a skill QA test, not a submission deliverable — a QA test of the industry-review-packager skill (commit 224122c) on a new industry, run 2026-07-13.

This package's dashboard uses a NEW generic issue_codes-lens assembly (assemble_codes()/codes_page.js), added to the skill in this same session so any future codes-lens package gets a dashboard for free. It has per-filing click-through on the press widget only (backed by x_press_releases_codes()): this lens's exporter doesn't produce the player_filings/trend_filings indices that back click-through elsewhere, so the players and trend widgets stay a reconciled aggregate chart plus a full table view instead.
