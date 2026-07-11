# Presidential Pardons — the Lobbying Around Executive Clemency (research package)

**Status: unverified research output for team review and QA** — generated 2026-07-10 from the P4
industry-map pipeline (new `PARDONS` facet, `industry_lexicon.json` v1.1; serving table rebuilt —
the CRYPTO facet reproduced byte-identically as a regression check). Nothing here is a locked
finding; every number traces to a CSV in `data/`, and every CSV row traces to raw records via
`show_record.py` or a public lda.senate.gov link.

**Start here:** open `pardons_dashboard.html` in any browser (self-contained, works offline,
light/dark; every widget has a ⋯ query-info menu and click-through to its underlying records).
`data/pardons_players.csv` is the master table; `data/pardons_engagements.csv` is the money table.

## Headline findings (candidate, unverified)

1. **There is a paid pardon-seeking market, declared in the filings' own words.** 26 clients —
   individuals (Richard Scrushy, Changpeng Zhao, Joseph Schwartz, Torence Hatch, Fred Daibes,
   Greg Lindberg, Anne Pramaggiore, Selim Zherka…) and corporate vehicles (Origin Property Group
   → "Potential Presidential pardon of Marco Bitran"; Juno Empire → "the Pardon of Jorge Ferrer")
   — paid lobbying firms **$4.37M in disclosed billings across 21 engagements**, almost entirely
   from 2024-Q4 onward. **8 engagements already carry declared termination filings** (the filing
   marks the engagement closing — whether the ask landed is an outside-record question).
2. **"Executive relief" is the market's own euphemism.** The whole phrase appears in exactly three
   clients' filings corpus-wide: Binance Holdings, Changpeng Zhao, and Fred Daibes (L021). The
   Binance/Zhao cluster billed ~$1.67M across Baker & Hostetler and Checkmate Government Relations
   (dollars not splittable from their digital-asset lobbying — see caveats).
3. **Specialist sellers exist.** J M Burkman & Associates collected ~$1.56M from two seekers
   (Hatch $600K in one quarter, Schwartz $960K — L034); The Vogel Group runs a stable of four
   clemency clients (Tierney, Patel, Magma Power, Healthicity); Corcoran Partners, Javelin
   Advisors, Fahmy Hudome International and Daugherty Strategies each carry named seekers.
4. **The field doubled after the 2024 election.** ~6 tagged filings/quarter through 2022–2024Q3
   (mostly clemency-policy advocacy: Due Process Institute, ACLU, Amnesty, NDN Collective,
   Aleph Institute), then 22 in 2024-Q4 and a sustained ~15/quarter through 2026-Q1 — the
   seeker engagements are nearly all post-election.
5. **There is no "pardons" issue code, so the field is invisible to code filtering.** The tagged
   text scatters across 37 ALI codes: 43.3% Law Enforcement, 23.9% Government Issues, 10.5%
   Civil Rights, long tail — the same "hidden vocabulary" problem the crypto map demonstrated,
   at boutique scale (366 tagged filings vs crypto's 9,768).
6. **Congress barely said the word until 2025.** Pardon/clemency vocabulary sat at 0.02–0.3% of
   member press releases 2022–2024, then spiked ~10× to 156 releases (1.13%) in 2025-Q1 (Jan-6
   mass pardons, preemptive-pardon fight) and 132 (1.15%) in 2026-Q1. The say-side runs on the
   political calendar; the paid seeker market above is quiet and filing-side.

## What's in the package

| File | What it is |
|---|---|
| `pardons_dashboard.html` | Interactive dashboard: class-colored player map, seeker-engagement money bars (with declared-termination status), quarterly trend, issue-code scatter, vocabulary, firms, press coupling — every widget with query-info modal, click-through record lists (incl. the matched lexicon phrase per filing), and table view |
| `data/pardons_players.csv` | **Master table**: 54 entity-resolved players, tagged senate filings, hand-triaged `client_class` (18 seekers / 8 seeker-vehicles / 27 advocacy / 1 unclear) with class notes quoting the filings |
| `data/pardons_engagements.csv` | **The money table**: every seeker/vehicle engagement (client × firm), first→last tagged quarter, reported billings in tagged quarters, declared-termination flag + quarter, sample `filing_uuid`, the engagement's own declared free-text |
| `data/pardons_player_filings.csv` | Raw-filing index: all 198 tagged senate filings with registrant, amount, **matched lexicon phrase(s)**, `filing_uuid`, and a public lda.senate.gov URL; per-player counts reconcile with the master table |
| `data/pardons_quarterly_trend.csv` | Tagged filings / distinct clients per quarter (amendment-deduped) |
| `data/pardons_trend_filings.csv` | Trend click-through: the deduped filings behind each quarter (counts reconcile with the chart) |
| `data/pardons_issue_code_scatter.csv` | Where the text files: ALI issue-code distribution of tagged blocks |
| `data/pardons_keywords.csv` | Which of the 8 lexicon phrases carried the signal |
| `data/pardons_registrant_firms.csv` | Outside firms on tagged filings (Burkman, Vogel, Baker & Hostetler…) |
| `data/pardons_press_quarterly.csv` | Pardon share of congressional member press releases, per quarter |
| `data/pardons_press_releases.csv` | Press click-through: all 586 matching releases with URL + `src_file:src_line` citation key (counts reconcile with the chart) |
| `data/pardons_record_samples_qa.csv` | Spot-check anchors: one top filing per major player with its `show_record.py` key |
| `data/pardons_ld203_*.csv` | LD-203 giving of roster orgs — **deliberately not charted**: org-level, dominated by advocacy orgs' non-pardon activity (the largest items are one org's fundraising-gala honoree costs), never pardon-attributable |

## How to QA a number

1. Pick any row in `data/pardons_record_samples_qa.csv` (or any `filing_uuid`).
2. From the repo root:
   `.venv/Scripts/python skills/lda-corpus-loader/scripts/show_record.py <key> --data-root "../data/data" --db db/lda_full.duckdb`
   — or open the row's lda.senate.gov URL and Ctrl-F the `matched_keywords` phrase.
3. Confirm the filing's activity text contains the phrase, and the client/amount match the CSV.
4. Aggregates: the exact SQL behind every widget is in its ⋯ → "View query info" modal, extracted
   at build time from `_build/export_pardons.py`; the citeable patterns are
   `queries/p4_industry_map.sql` (P4a–P4e) and the dedup rule `queries/sweep_2026.sql#H1c`.

## Method & caveats (the ones that bite)

- **Recall boundary — the map only sees engagements that say the word.** 8 curated phrases
  (pardon/pardons/pardoning/clemency/clemencies/commutation/commutations/executive relief),
  whole-word, precision-checked (commute=transportation, amnesty=immigration, expungement=records
  relief, compassionate release=judicial mechanism all excluded — see the lexicon's
  `display_only` notes). Engagements that never use the vocabulary are invisible: **Roger Ver's
  Drake Ventures ($600K) and Sterling Green engagements (L034) declare "US government prosecution
  of Roger Ver" and are NOT in this map** — the quarterly-turnover lens caught them instead.
  The two lenses are complements, not substitutes.
- **Engagement dollars cannot be split by issue.** They are the pair's full reported billing for
  quarters where the tagged language appears (Binance's engagements also cover digital-asset
  work). Several engagements report no income at all; the $4.37M market total is a floor.
- **Termination is declared only** (senate `filing_type` termination family, corpus-profile §3),
  never inferred from a missing quarterly.
- **Two populations share the vocabulary by design.** Seekers vs clemency-POLICY advocacy (which
  itself spans clemency-expansion pushes and pardon-power-limiting constitutional amendments).
  The `client_class` column separates them; classes were hand-triaged 2026-07-10 from filing text
  and are auditable in the export script's `CLASS` dict.
- **Living persons with active clemency asks** — editorial/legal-sensitivity review before naming
  anyone in a story (same flag as L021/L034).
- **Senate-primary; never sum the two chambers.** Amendment-deduped on `filing_period`, latest by
  `posted`; registrations excluded from dollar work. All figures are self-reported disclosure
  data; "disclosed" never means "total".

## Reproduce

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py --build-tags   # lexicon v1.1
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py pardons --top 60
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py --names-file out/pardons_roster.txt --top 60 --json
.venv/Scripts/python out/packages/pardons/_build/export_pardons.py
.venv/Scripts/python out/packages/_build/viz_build.py pardons
```

Rosters: `out/pardons_roster.txt` (54 resolved players), `out/pardons_roster_seekers.txt` (26),
`out/pardons_roster_advocacy.txt` (27). Ledger context: L021 (Daibes), L034 (Ver/Hatch/Schwartz —
this package generalizes it to the full market), L035 (this package).
