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
| L003 | Opaque entities each spending ~$1M in a single quarter: who are they and for whom? | spend-anomaly | Innovairrs & Co. ($1M/1 filing); Five Rivers Conservation Group LLC ($990K/2); Fay Law Group ($840K/1); Coretsu Inc. ($760K/6) | open | — | sweep#S1a | show_record each filing; check registrant vs client roles, addresses, incorporation trail | 2026-07-04 |
| L004 | Bills heavily lobbied but publicly near-silent — survives dollar-weighting: HR7567 $6.5M attributed/5 press, HR4552 $6.0M/1, S2296 $5.2M/1 (vs HR6938 $12M/108) | say-vs-pay | bills HR7567, HR4552, S2296 + their lobbying clients (TBD) | open | — | sweep#C1b (dollar-weighted, 286/219/202 distinct filings) | Identify bills via Congress.gov (disclose as outside data); list top clients lobbying each; why the silence | 2026-07-04 |
| L005 | ACG Advocacy's revolving-door bench (ex-Senate LD Jamie Susskind; ex-US IP-enforcement coordinator Chris Israel) lobbying for AI-adjacent clients incl. National Association of Voice Actors | revolving-door | Jamie Susskind, Chris Israel, ACG Advocacy, NAVA, Plastics Industry Assoc | open | — | sweep#S2a; uuids 9baff501-b702-49e4-9138-8615e6ced5af, cc72c180-84f3-40cf-bbbe-0d4bda1f377f | Dedup S2a (multi-activity rows); which offices lobbied; whose staff were they (complete the truncated positions) | 2026-07-04 |
| L006 | UAE sovereign wealth (Mubadala entities) sits behind multiple 2026 US lobbying engagements | foreign-influence | Mubadala Investment Co; Caturus; GlobalFoundries; Ridge Path Strategies | open | — | sweep#S3; uuids 49595367-fa66-4dc6-8249-36c59395cca1, 7b017b92-fc36-4419-bf27-4153bd025b1b | Full foreign_entities pull for AE; cross-ref FARA (outside data, disclose); what's being lobbied | 2026-07-04 |
| L007 | Early-2026 LD-203s show lobbyists concentrating honoree spending on House Financial Services leadership (Rep. Mike Flood $46K/11 items, Rep. French Hill $25K/5) | contribution-flows | Rep. Mike Flood, Rep. French Hill; contributors mostly SELF (lobbyist-personal) | open | — | sweep#S4; senate_contribution_items | Only 140 LD-203s exist yet (semiannual) — pull item detail + payees; revisit when mid-year reports land | 2026-07-04 |
| L008 | Registrants filing quarterlies with zero money disclosed across ALL filings (Larkin Hoffman 15/15; Paul Hastings 10/10; Aux Initiatives 12/12) — gap or the <$5K convention? | data-quality | Larkin Hoffman; Paul Hastings LLP; Aux Initiatives LLC; Northern Compass Group | open | — | sweep#S5 | Check raw filings for expense-method/termination nuances before calling it a gap; compare their House-side numbers | 2026-07-04 |
| L009 | Press-volume outliers: CNMI delegate Kimberlyn King-Hinds posting 60+ releases/month (scraper artifact?); Durbin's March surge (84) | anomaly (messaging) | Kimberlyn King-Hinds, Richard Durbin | open | — | sweep#P3 | Sample 5 releases each via show_record — artifact check first; low priority | 2026-07-04 |

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

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
| L001 | 2× mismatch verified as duplicate/amendment artifact; residual deltas ≤$40K too small to chase on one quarter | Full corpus loaded: re-run H1b at scale looking for chronic cross-chamber mis-reporters | 2026-07-04 |
