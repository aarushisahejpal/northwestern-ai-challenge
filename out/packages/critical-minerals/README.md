# Critical Minerals & Battery Materials — the Lobbying Field

*Generated 2026-07-11 · unverified research output for team review.*

Who lobbies Washington on critical minerals, rare earths, and the battery-materials supply chain — the field where the BATT Coalition (a coalition whose ultimate members are not disclosed in its filings) sits, mapped from the filings' own free-text 2022–2026Q1.

This package maps the federal lobbying field around critical minerals, rare earths, and the battery-materials supply chain — an industry that, like crypto, scatters across many disclosure issue codes (Natural Resources, Energy, Trade, Defense, Taxation, Manufacturing) and is therefore invisible to issue-code filtering alone. The map is built from what filers SAY they lobby on: 19 curated, collision-checked phrases (from 'critical minerals' and 'rare earths' to the statutory terms '45X', '30D', and 'foreign entity of concern') matched whole-word against the filings' own activity text.

One seed question this map serves: the Battery Advocacy for Technology Transformation (BATT) Coalition stood up ~$800K/yr of lobbying from a zero base in mid-2024 without disclosing its ultimate members. This package places BATT inside its field — the same-vocabulary co-filers (automakers, miners, chemical, defense and electronics companies, most with no battery/mineral term in their name) that a reporter would canvass to establish who funds and benefits from the coalition's asks. BATT files under two client-name spellings ('THE BATTERY ADVOCACY FOR TECHNOLOGY TRANSFORMATION (BATT) COALITION' via Strategic Marketing Innovations, and 'SMI ON BEHALF OF THE…' via Cannon|Pearce), which the entity resolver keeps as separate players — a documented name-resolution ceiling. A third similarly-named player, the 'BATTERY MATERIALS AND TECHNOLOGY COALITION' (via Venn Strategies, filing since 2022, $2.2M reported), appears to be a DISTINCT coalition in the same space — the field held an earlier battery-materials coalition before BATT emerged, and the two should not be conflated.

## What is in scope

Scope = filings whose free-text matches the curated `CRITMIN` vocabulary (industry_lexicon.json). Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated on (registrant, client, year, quarter) keeping the latest by posting date; registrations are excluded from dollar work. Client spend comes only from the double-count-corrected canonical spend view.

## Files

| file | rows | what it is |
|---|---|---|
| data/critmin_bills.csv | 60 |  |
| data/critmin_issue_code_scatter.csv | 53 |  |
| data/critmin_keywords.csv | 19 |  |
| data/critmin_player_filings.csv | 6692 |  |
| data/critmin_players.csv | 851 |  |
| data/critmin_press_quarterly.csv | 17 |  |
| data/critmin_press_releases.csv | 1514 |  |
| data/critmin_quarterly_trend.csv | 17 |  |
| data/critmin_record_samples_qa.csv | 25 |  |
| data/critmin_registrant_firms.csv | 60 |  |
| data/critmin_spend_quarters.csv | 9004 |  |
| data/critmin_trend_filings.csv | 6006 |  |

## Caveats that matter

- Recall-first map: any client whose filing free-text names one of the 19 curated phrases is included; incidental one-off mentions sit in the peripheral tier by design. A story names specific players from the CSVs, never 'the whole list.'
- Spend figures are each player's TOTAL federal lobbying spend across all issues (canonical, double-count-corrected) — a size signal. Filing-level disclosure cannot split dollars by issue.
- Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated on filing_period, latest by posted; registrations excluded from dollar work.
- 'Energy storage' includes non-battery storage (hydrogen, pumped hydro) — a documented recall/precision trade recorded in the lexicon; the mineral and battery-materials phrases are the high-precision core.
- The BATT Coalition files under two client-name spellings which remain separate players on the map (the entity resolver's documented name-variant ceiling); the similarly-named 'Battery Materials and Technology Coalition' (Venn Strategies, filing since 2022) appears to be a DISTINCT organization in the same space — do not conflate the two.
- LD-203 'disclosed giving' is the lobbyist-side regime only, organization-level, and never minerals-attributable. Super-PAC money legally lives in FEC data — the two never sum.
- Everything is self-reported disclosure data. 'Disclosed' never means 'total': 501(c)(4) dark money and state lobbying are outside every number here.

## How to QA a number

1. Every chart is click-through to the raw filings behind it; every filing links to its public record on lda.senate.gov; press rows carry `src_file:src_line` keys.
2. Chart-vs-list reconciliation ran at build time and a mismatch fails the build (trend counts, per-player filing counts, press counts, spend sums).
3. The SQL behind each widget is embedded in the dashboard (hover ⋯ → View query info) — it is the exact string the generator executed.

## Regenerate

```
python skills/industry-review-packager/scripts/lda_package_industry.py \
    skills/industry-review-packager/specs/critical-minerals.json
```

This is unverified research output for team review. Headline numbers are candidates with record anchors, not locked findings; the candidate angles live in the investigation ledger (L024).
