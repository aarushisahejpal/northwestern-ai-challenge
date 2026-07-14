# AIPAC Lobbying Review (research package)

**Status: unverified research output for team review and QA** — generated 2026-07-08.
Nothing here is a locked finding; every number traces to a CSV in `data/`, and every CSV row
traces to raw records via `show_record.py` (AIPAC filing UUIDs are in `data/aipac_quarterlies.csv`).

**Start here:** open `aipac_dashboard.html` (self-contained, offline, light/dark). For hands-on
work, `data/aipac_activities.csv` is the most readable single file — AIPAC's own quarterly
descriptions of what it lobbied on, in their words, with citation keys.

## Headline findings (candidate, unverified)

1. **A textbook in-house operation.** AIPAC self-files (registrant = client): 17 straight
   quarterlies 2022–2026Q1, no amendments, no outside firms. Spend is a slow ratchet:
   $690K (2022-Q1) → $974K peak (2025-Q4); $3.76M in 2025, +38% vs 2022 (~9%/yr).
2. **The budget is insensitive to the news cycle.** After October 7, 2023, the Israel-topic share
   of ALL congressional member press releases jumps 2.6% → 20.3% in one quarter (~8×) and stays
   elevated (3–11%) through 2026Q1 — while AIPAC's quarterly spend moves +6.6% and never breaks
   its trend (`data/aipac_press_coupling.csv`). Lobbying budgets look like planned infrastructure,
   not reactive spending — the interesting *absence* of coupling.
3. **Who is lobbied:** both chambers on every filing, then DOD (50 mentions), DHS (35), State,
   Treasury, NSC (34 each) — and the **Energy Department (34)**, riding with the Iran-sanctions /
   civil-nuclear portfolio (`data/aipac_gov_entities.csv`).
4. **What they lobby:** every activity coded BUD/FOR/DEF; 314 distinct bills named — Iran
   sanctions acts, security-assistance appropriations, U.S.–Israel defense-partnership bills,
   antisemitism resolutions (`data/aipac_bills.csv`, hints extracted from AIPAC's own text).
5. **Who else lobbies the same bills:** on AIPAC's distinctive bills (≤200 engagements
   corpus-wide), the top co-lobbyists are **J Street (146 shared bills) and FDD Action (146)** —
   opposite camps at identical coverage — then Hadassah (55), Republican Jewish Coalition (53),
   Friends Committee on National Legislation (46), CUFI (30), ACLU (29), MoveOn (25), Amnesty
   (20). Filing on the same bill maps the battlefield, not the alliance.
6. **The wider Israel-policy field** (exploratory free-text scan): ADL leads by volume
   (29 filings), then RJC, J Street, FDD Action — plus non-obvious entries: **Chevron
   (18 filings — Eastern-Mediterranean gas leases)** and the Estate of Esther Klieman
   (terror-victim litigation) (`data/israel_policy_players.csv`).
7. **Disclosed giving is bipartisan, tilted Republican ~63:37 by dollars.** $7.65M LD-203
   2022–2025 (amendment-deduped from $10.0M raw), 100% FECA, election-year cadence
   ($2.9M/$1.1M/$2.7M/$1.0M). Member-matched giving splits **$3.77M to 194 Republicans vs
   $2.21M to 119 Democrats** (+$15K to 1 Independent); top member recipients alternate parties —
   Weber (R-TX) $37.9K, Morelle (D-NY) $37.1K, Fleischmann (R-TN) / Torres (D-NY) / Cammack
   (R-FL) $35K each (`data/aipac_ld203_recipients.csv`, now with party/state columns; party from
   the corpus `members` table, retired members hand-mapped and flagged `manual`). **Not included
   by law:** AIPAC-affiliated Super-PAC spending (United Democracy Project) lives in FEC data —
   same disclosure boundary as crypto's Fairshake; an FEC pull is the natural follow-up.

## What's in the package

| File | What it is |
|---|---|
| `aipac_dashboard.html` | Interactive dashboard — spend-vs-press coupling, targets, bills, co-lobbyists, field map, giving |
| `data/aipac_quarterlies.csv` | The 17 filings with amounts and citation keys |
| `data/aipac_activities.csv` | **Most readable file** — their own activity text per quarter/issue code |
| `data/aipac_gov_entities.csv` | Who is lobbied (agency mentions) |
| `data/aipac_lobbyists.csv` | The 12-person in-house team (no covered positions listed) |
| `data/aipac_bills.csv` + `aipac_bills_fanin.csv` | 314 bills; how crowded each is corpus-wide |
| `data/aipac_bill_colobbyists.csv` | Who else lobbies the distinctive bills |
| `data/israel_policy_players.csv` | The wider field (exploratory scan, ≥2 filings) |
| `data/aipac_press_coupling.csv` | Quarterly spend vs Israel-topic press share |
| `data/aipac_ld203_*.csv` | Disclosed giving: recipients (with party/state + source columns, member name variants merged), by-year, sample records |
| `data/aipac_press_releases.csv`, `aipac_gov_entity_filings.csv`, `aipac_bill_filings.csv`, `aipac_colobby_filings.csv`, `aipac_israel_player_filings.csv`, `aipac_lobbyist_filings.csv`, `aipac_giving_items.csv` | **Raw-record indexes** behind every dashboard widget's click-through (each row links to the filing/contribution on lda.senate.gov) |

## How to QA a number

`.venv/Scripts/python skills/lda-corpus-loader/scripts/show_record.py <filing_uuid> --data-root "../data/data" --db db/lda_full.duckdb`
— e.g. `ad4e8e54-def8-4563-97c5-0ac5a0ca16a3` is the 2026-Q1 filing ($844,410). Press-side
counts reproduce from a whole-word regex over `press_releases`
(israel/israeli/gaza/hamas/hezbollah/antisemitism/iron dome/west bank/palestinian/abraham
accords/golan heights/jerusalem).

## Method & caveats

- Senate-primary; AIPAC's house mirrors are not added. No amendments existed to dedup.
- **"Co-lobbying" = filing on the same bill; direction of advocacy is not in disclosure data.**
  The ≤200-engagement distinctiveness filter keeps NDAA/approps mega-bills from drowning the map.
- The Israel-field scan is an **exploratory regex**, not the curated lexicon pipeline. Before any
  citation in a finding, promote the vocabulary to `industry_lexicon.json` (human triage) and
  rebuild the serving table.
- Press releases are member releases — Congress's "say" side, not AIPAC's own messaging.
- LD-203 is registrant-filed disclosed giving; recipient strings lightly normalized; UDP
  Super-PAC money is outside this regime (FEC).

## Reproduce

The exporter SQL is embedded in this package's build script (`_build/export_aipac.py` in this package holds the session);
key aggregates re-derive with the patterns in `queries/p2_bill_crosscheck.sql` (bill joins),
`queries/ld203_giving.sql` (giving), and a `senate_gov_entities`/`senate_activities` join
filtered on `registrant_name LIKE '%AMERICAN ISRAEL PUBLIC AFFAIRS%'`.
