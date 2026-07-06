# Investigation Ledger

Single source of truth for what has been checked, what is open, which entities matter, and which
threads went cold. **Write protocol:** sub-agents never edit this file — they return candidate rows;
only the orchestrating session (or a human) commits them. Read at session start; write at any status
change and at session end.

**Status state machine:** `open → triaged → investigating → verified | dead`. Any lead may move to
`parked` (cold) with a reason and a revisit trigger. **Cold ≠ dead:** dead = refuted or judged not
newsworthy (reason recorded); cold = promising but blocked/deprioritized, reconsidered at every
triage checkpoint. New leads arriving mid-stream enter as `open` and are considered at the next
triage checkpoint.

**Named-actor rule:** a lead with no specific actor, date, and record ID cannot pass triage.

## Leads

All L001–L009 sourced from the 2026-Q1 sweep (queries/sweep_2026.sql, run 2026-07-04 against
db/lda_2026.duckdb; DB rebuild: build_db.py --data-root <data> --years 2026).

| id | hypothesis (one line) | lens | named actors | status | owner | evidence so far (record IDs) | next action | updated |
|---|---|---|---|---|---|---|---|---|
| L001 | Senate vs House income mismatch — CHECKED: the 2× pattern is duplicate/amendment double-counting on both sides, not misreporting; residual deltas after dedup are ≤$40K | senate-house-discrepancy | Mercury/AITEO (house filings 301849863+301849872, both $110K); S-3/Pattern (senate uuids fdbd2b74…, 63497109… identical, 22s apart); residuals: Global Connection/RAI $20K vs $60K, Cormac/BM Tech $50K vs $20K | parked | Claude | sweep#H1b (dedup); artifact check 2026-07-04 | Revisit at full-corpus scale: chronic cross-chamber mis-reporters may still be a story; dedup rule now standard (CLAUDE.md) | 2026-07-04 |
| L002 | Korea Zinc spent $960K on US lobbying in Q1 2026 alone (top-6 client) amid its control battle / critical-minerals positioning | spend-anomaly + foreign | Korea Zinc Company, Ltd. | open | — | sweep#S1a (960000, 2 filings) | Pull its filings via SQL, show_record each; what issues/agencies; who are the lobbyists | 2026-07-04 |
| L003 | Opaque entities each spending ~$1M in a single quarter: who are they and for whom? | spend-anomaly | Innovairrs & Co. ($1M/1 filing); Five Rivers Conservation Group LLC ($990K/2); Fay Law Group ($840K/1); Coretsu Inc. ($760K/6) | triaged | Claude | sweep#S1a; triage 2026-07-05 (DECISIONS.md) | show_record each filing; check registrant vs client roles, addresses, incorporation trail | 2026-07-05 |
| L004 | RESOLVED as artifact: the "quiet bills" are HR7567=FY26 Farm Bill, HR4552=FY26 THUD approps, S2296=FY26 NDAA (identified from filers' own activity text, no outside data) — press discusses them by NAME (94 "farm bill" / 133 NDAA text mentions) while filings cite NUMBERS (5 / 1 matched), so number-based say-vs-pay fabricates "silence" for famous bills | say-vs-pay | bills HR7567, HR4552, S2296; comparators HR6938/HR7148 = consolidated approps vehicles | dead | Claude | l004_quiet_bills.sql#L004a-g; uuid 7e61b5d2-5200-4d78-9499-9cce289c4994 (names all three bills); dedup also cut C1b totals ~40% (chamber double-count) | Lens fixes → lead-scanner skill: (1) alias matching (number + popular name), (2) senate-primary dollar attribution; live thread continues as L010 | 2026-07-05 |
| L005 | ACG Advocacy's revolving-door bench (ex-Senate LD Jamie Susskind; ex-US IP-enforcement coordinator Chris Israel) lobbying for AI-adjacent clients incl. National Association of Voice Actors | revolving-door | Jamie Susskind, Chris Israel, ACG Advocacy, NAVA, Plastics Industry Assoc | open | — | sweep#S2a; uuids 9baff501-b702-49e4-9138-8615e6ced5af, cc72c180-84f3-40cf-bbbe-0d4bda1f377f | Dedup S2a (multi-activity rows); which offices lobbied; whose staff were they (complete the truncated positions) | 2026-07-04 |
| L006 | UAE sovereign wealth (Mubadala entities) sits behind multiple 2026 US lobbying engagements | foreign-influence | Mubadala Investment Co; Caturus; GlobalFoundries; Ridge Path Strategies | open | — | sweep#S3; uuids 49595367-fa66-4dc6-8249-36c59395cca1, 7b017b92-fc36-4419-bf27-4153bd025b1b | Full foreign_entities pull for AE; cross-ref FARA (outside data, disclose); what's being lobbied | 2026-07-04 |
| L007 | Early-2026 LD-203s show lobbyists concentrating honoree spending on House Financial Services leadership (Rep. Mike Flood $46K/11 items, Rep. French Hill $25K/5) | contribution-flows | Rep. Mike Flood, Rep. French Hill; contributors mostly SELF (lobbyist-personal) | open | — | sweep#S4; senate_contribution_items | Only 140 LD-203s exist yet (semiannual) — pull item detail + payees; revisit when mid-year reports land | 2026-07-04 |
| L008 | Registrants filing quarterlies with zero money disclosed across ALL filings (Larkin Hoffman 15/15; Paul Hastings 10/10; Aux Initiatives 12/12) — gap or the <$5K convention? | data-quality | Larkin Hoffman; Paul Hastings LLP; Aux Initiatives LLC; Northern Compass Group | open | — | sweep#S5 | Check raw filings for expense-method/termination nuances before calling it a gap; compare their House-side numbers | 2026-07-04 |
| L009 | Press-volume outliers: CNMI delegate Kimberlyn King-Hinds posting 60+ releases/month (scraper artifact?); Durbin's March surge (84) | anomaly (messaging) | Kimberlyn King-Hinds, Richard Durbin | open | — | sweep#P3; supporting: S2296's sole press "mention" is a King-Hinds page titled "October 2025" (congress_press/2026-01.jsonl:17) — likely scraper junk | Sample 5 releases each via show_record — artifact check first; low priority | 2026-07-05 |
| L010 | The pipe-materials war: DIPRA (iron-pipe trade assoc) paid Bradley Arant $540K in Q1 2026 alone — with ex-Rep. Martha Roby on the account — to shape "materials provisions, domestic sourcing" across THUD approps, NDAA, Ag/E&W approps, TSCA, and water bills; iron side (+ McWane $140K) outspends the entire visible opposing coalition (Plastics Industry Assoc ~$100K, Diamond Plastic $20K, Hobas $20K, Copper Dev $110K); the only press mentions are incidental earmark announcements that *specify ductile iron* as the material | say-vs-pay (provision-level; descends from L004) | DIPRA; Bradley Arant Boult Cummings; Martha Roby (former Member, US House); McWane Inc.; Plastics Industry Association; Copper Development Association | open | Claude | uuid 7e61b5d2-5200-4d78-9499-9cce289c4994 ($540K, activity text); 6817ab80-c4d5-4eb7-8493-5af807874661, fc5d7964-4c2d-425c-8012-b0b50caeb955 (McWane); 590f0248/c7c2091b/fa4e3cf3/a8b88b9d/a5ed3b1c (opposition); press congress_press/2026-03.jsonl:3394 (earmark specifying ductile iron); l004_quiet_bills.sql#L004h-k; l010_pipe_war.sql#L010a-b | 2025 baseline for DIPRA spend once pilot DB builds (is $540K a spike?); DIPRA member companies + Roby's committee history (outside data, disclose); then draft finding | 2026-07-05 |

## Entities checked

| entity (entity_id) | verdict | records examined | date |
|---|---|---|---|
| — | — | — | — |

## Queries run

| date | SQL (file in queries/) | one-line result |
|---|---|---|
| 2026-07-04 | sweep_2026.sql#S1a-S1c | Top client Qualcomm $1.2M; busiest codes BUD/HCR/DEF/TAX; big-4 registrants ~380 filings each |
| 2026-07-04 | sweep_2026.sql#S2a-S2b | 40+ ex-Hill staffers on 2026 registrations; covered_position free text rich but messy (dupes, truncation) |
| 2026-07-04 | sweep_2026.sql#S3 | 198 foreign entities incl. Mubadala (AE), Gunvor (CH), Dallbogg (BG) |
| 2026-07-04 | sweep_2026.sql#S4 | Only 140 LD-203s so far (semiannual); Flood $46K / Hill $25K top honorees |
| 2026-07-04 | sweep_2026.sql#S5 | 15 registrants with 100% money-undisclosed quarterlies |
| 2026-07-04 | sweep_2026.sql#H1 | 20 org+client pairs with Senate≠House income; house=2×senate dominates → artifact check needed |
| 2026-07-04 | sweep_2026.sql#H2/C1 | Bills both lobbied+pressed: HR1, HR7148, HR6938; lobbied-but-silent: HR7567, HR4552, S2296 |
| 2026-07-04 | sweep_2026.sql#P3 | Member release-rate outliers: Durbin 84/mo, King-Hinds 62/mo |
| 2026-07-04 | sweep_2026.sql#H1b | After amendment/duplicate dedup, H1's 2× pattern vanishes; max residual delta $40K |
| 2026-07-04 | sweep_2026.sql#C1b | Dollar-weighted say-vs-pay: quiet bills carry $5.2–6.5M attributed each — lead survives |
| 2026-07-05 | l004_quiet_bills.sql#L004a-e | Senate-primary dedup cuts quiet-bill totals to $3.9–4.2M (C1b double-counted chamber copies); top clients per bill listed |
| 2026-07-05 | l004_quiet_bills.sql#L004f-g | Bills self-identify in activity text (Farm Bill / THUD / NDAA); press uses names not numbers (94 vs 5 "farm bill") → L004 framing is an artifact |
| 2026-07-05 | l004_quiet_bills.sql#L004h-k | DIPRA: $540K single filing, no house copy (house dump ~60% coverage), 5 incidental pipe press releases, opposition fragmented |
| 2026-07-05 | l004_quiet_bills.sql#L004j | House 2026-Q1 dump = 12,656 filings vs senate 21,145 Q1s (17K posted Apr 15+) — partial deadline-week snapshot; house absence ≠ signal |
| 2026-07-05 | l010_pipe_war.sql#L010a-b | McWane adds $140K iron-side (Balch & Bingham + Wessel); only DIPRA's filing text names ductile/materials provisions |

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
| L001 | 2× mismatch verified as duplicate/amendment artifact; residual deltas ≤$40K too small to chase on one quarter | Full corpus loaded: re-run H1b at scale looking for chronic cross-chamber mis-reporters | 2026-07-04 |
