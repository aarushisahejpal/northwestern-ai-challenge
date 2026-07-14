# The GENIUS Act — Who Lobbied the Stablecoin Bill

*Generated 2026-07-13 · unverified research output for team review.*

Who lobbied Washington on the GENIUS Act (S.1582), the 2025 stablecoin regulatory framework signed into law — mapped from the filings' own free-text, a bill-scoped slice inside the broader crypto industry.

This package maps the federal lobbying field around the GENIUS Act (S.1582, the Guiding and Establishing National Innovation for U.S. Stablecoins Act), the stablecoin regulatory framework signed into law in July 2025 — the single most distinctive crypto legislative vehicle in the corpus window. It is a bill-scoped SLICE of the broader crypto industry map (facet CRYPTO): every filing here also carries the CRYPTO tag, but the reverse is not true — this package is deliberately narrower, built from filings that name the bill itself (its popular name, its full official name, or an S.1582/S.1582 citation), not the wider stablecoin/crypto vocabulary.

170 client-side players sit on the map, 94.7% (161) with no crypto-related term anywhere in their name — the same 'hidden industry' pattern the crypto map demonstrated, here at bill scale. The recall win runs beyond the usual fintech suspects: American Airlines shows up eight times across four straight quarters ('Issues related to credit cards. S.1582 - GENIUS Act.') — its co-branded card economics ride on the same payment-rail rules the bill rewrites. Labor unions (IBEW, AFT) appear too, monitoring the bill's spillover into retirement-plan exposure rather than lobbying for it — a second population sharing the vocabulary, the same two-audience pattern the pardons package documented for a different bill-adjacent field.

Filings tagging the bill more than doubled from its first tracked quarter to its passage quarter (64 in 2025-Q1 to a peak of 156 in 2025-Q3, the quarter it was signed into law), then eased off — a clean legislative-calendar shape. It rarely travels alone: HR3633 (the CLARITY Act, digital-asset market structure) is the tightest companion, co-cited in 289 of the roster's filings across 97 clients, with HR2392 (a rival stablecoin bill) and the earlier S.394/S.919 stablecoin vehicles close behind.

## What is in scope

Scope = filings whose free-text matches the curated `GENIUS` vocabulary (industry_lexicon.json). Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated on (registrant, client, year, quarter) keeping the latest by posting date; registrations are excluded from dollar work. Client spend comes only from the double-count-corrected canonical spend view.

## Files

| file | rows | what it is |
|---|---|---|
| data/genius_act_bills.csv | 40 |  |
| data/genius_act_issue_code_scatter.csv | 19 |  |
| data/genius_act_keywords.csv | 4 |  |
| data/genius_act_ld203_by_org.csv | 88 |  |
| data/genius_act_ld203_by_year.csv | 4 |  |
| data/genius_act_ld203_member_rollup.csv | 15 |  |
| data/genius_act_ld203_recipients.csv | 400 |  |
| data/genius_act_player_filings.csv | 631 |  |
| data/genius_act_players.csv | 170 |  |
| data/genius_act_press_quarterly.csv | 17 |  |
| data/genius_act_press_releases.csv | 106 |  |
| data/genius_act_quarterly_trend.csv | 5 |  |
| data/genius_act_record_samples_qa.csv | 25 |  |
| data/genius_act_registrant_firms.csv | 40 |  |
| data/genius_act_spend_quarters.csv | 2156 |  |
| data/genius_act_trend_filings.csv | 577 |  |

## Caveats that matter

- Recall boundary: only filings whose free-text uses the curated GENIUS Act vocabulary (industry_lexicon.json facet GENIUS) appear — 'genius act', the bill's full official name, and the S.1582/S.1582 citation forms. A filing that discusses the same stablecoin legislation without naming the bill (e.g. only 'stablecoin regulation') is invisible here by design (precision over recall); those generic terms were checked and excluded as ambiguous (could mean the CLARITY Act or a state proposal) — see the lexicon's display_only block.
- Known cross-Congress collision, left in and documented: bill numbers reset every Congress, and this corpus spans two (118th 2023-2024, 119th 2025-2026). One 2023 filing (CCOF, California Certified Organic Farmers) matches 'S. 1582' but is the 118th Congress's unrelated 'Opportunities in Organic Act' — it lands in the peripheral tier (1 filing, no name hit), exactly where a single-mention false positive should surface for a human to triage, not a silent gap.
- 'genius act' and the statute's full official name are shared with the broader CRYPTO facet (a bill-scoped sub-facet, not a separate vocabulary) — every player and filing here is also part of the crypto industry map; this package is that map's GENIUS-Act-specific slice, not a disjoint population.
- Player 'total lobbying spend' is ALL-ISSUE canonical spend (v_client_canonical_spend) — a size signal, not GENIUS-Act-only dollars. Filing-level disclosure cannot split dollars by issue.
- Senate filings are primary; house versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated on filing_period, latest by posted; registrations excluded from dollar work (the CCOF false positive is a registration and does not appear in the trend/spend charts for this reason).
- The bills co-occurrence table (HR3633/HR2392/S394/S919/...) counts every bill mentioned ANYWHERE in a GENIUS-tagged filing, not bills mentioned in the same sentence — a large generic vehicle like HR1 can appear simply because a diversified client's filing touches many issues at once. Read the crypto/stablecoin-specific bills (HR3633, HR2392, S394, S919) as the genuine companions; treat the broader tail with more caution.
- LD-203 'disclosed giving' is the lobbyist/registrant-side regime only, organization-level, and never GENIUS-Act-attributable — a diversified filer's giving reflects its whole portfolio. Super-PAC money legally lives in FEC data and is not in this package.
- Everything is self-reported disclosure data. 'Disclosed' never means 'total': 501(c)(4) dark money and state lobbying are outside every number here.

## How to QA a number

1. Every chart is click-through to the raw filings behind it; every filing links to its public record on lda.senate.gov; press rows carry `src_file:src_line` keys.
2. Chart-vs-list reconciliation ran at build time and a mismatch fails the build (trend counts, per-player filing counts, press counts, spend sums).
3. The SQL behind each widget is embedded in the dashboard (hover ⋯ → View query info) — it is the exact string the generator executed.

## Regenerate

```
python skills/industry-review-packager/scripts/lda_package_industry.py \
    skills/industry-review-packager/specs/genius-act.json
```

This is unverified research output for team review. Headline numbers are candidates with record anchors, not locked findings.

Known false positive, left in and documented rather than silently dropped: one 2023 filing (CCOF, California Certified Organic Farmers) matches 'S. 1582' but is actually the 118th Congress's 'Opportunities in Organic Act' — bill numbers reset every Congress, and this corpus spans two of them (118th 2023-2024, 119th 2025-2026). It lands in the peripheral tier (1 filing, no name hit) exactly where a single-mention false positive should surface for human triage — the map's built-in behavior, not a special case.
