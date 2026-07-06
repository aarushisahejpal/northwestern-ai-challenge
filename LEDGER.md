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

**Fresh start (2026-07-06, second attempt):** this ledger was reset a second time. The first
full-corpus attempt ran `queries/sweep_2026.sql` wholesale and, unsurprisingly, re-derived the same
top-line anomalies already documented in the pilot archive (a self-reported vanity filing at the top
of spend rankings; a foreign-owned semiconductor company's disclosed ownership) — re-running the
exact SQL that originally found those things just re-finds them, it isn't independent generation.
That attempt is archived at `archive/LEDGER_full-sweep-rediscovery_2026-07-06.md`. The prior pilot
pass is separately archived at `archive/LEDGER_pilot-triage_2026-07-06.md`. This ledger starts empty
again for a session designing its own exploratory queries rather than replaying `sweep_2026.sql`.

## Leads

All five below were generated 2026-07-06 from self-designed rate-of-change / emergence /
contribution-flow lenses (`queries/emergence_and_flows.sql`), NOT from `sweep_2026.sql`. Each is a
dimension the point-in-time sweep does not cover. Dollar figures are senate-primary and deduped on
`filing_period` (latest by `posted`, registrations excluded). Record IDs are Senate `filing_uuid`s,
resolvable via `show_record.py` once the raw corpus is re-materialised (see DECISIONS 2026-07-06).

| id | hypothesis (one line) | lens | named actors | status | owner | evidence so far (record IDs) | next action | updated |
|---|---|---|---|---|---|---|---|---|
| L020 | TP-Link (China-founded router maker facing a proposed US ban) ramps lobbying ~5x and fans out from one firm to three across 2024-2026 | E1+E2 emergence/fan-out | TP-Link Systems Inc.; Akin Gump; Mercury Public Affairs; Vernonburg Group | triaged | orchestrator | b4c72e93-8d8b-442b-83b6-1d1b1b718b34 (Akin Gump 25Q3 $410k, CPI/TEC "routers"); 02908bc6-edde-4067-a3a8-297a2b368cdc (Mercury 25Q4 $160k, added firm); 757e7f7a-10d3-480c-bc6f-0ac664ec0530 (Akin Gump 26Q1 $410k) | confirm the router-ban legislative timeline; scan press corpus for member statements on TP-Link / router security (say-vs-pay) | 2026-07-06 |
| L021 | Fred Daibes (convicted in the Sen. Menendez bribery case) pays $1M to lobby for "Executive relief" (clemency); the registered lobbyist is Keith Schiller, ex-Trump Director of Oval Office Operations | E3 individual-as-client | Fred Daibes (individual); Javelin Advisors LLC; Keith Schiller | triaged | orchestrator | b6506151-6b6d-4127-b543-83522f7b305a (2025 Q1, $1,000,000, issue LAW "Executive relief"; lobbyist Keith Schiller) | editorial/legal-sensitivity review (living person, active clemency ask); verify Schiller covered-position; check the NULL-income Q2-Q4 for continued engagement | 2026-07-06 |
| L022 | Scott Sheffield (Pioneer founder named in the FTC/Exxon consent order) personally retains Brownstein to lobby "Issues related to the FTC", starting exactly the quarter the FTC acted | E3 individual-as-client | Scott Sheffield (individual); Brownstein Hyatt Farber Schreck; Norman Brownstein; William Moschella | triaged | orchestrator | 1af97f4c-92a7-4a33-bae5-37005a293b30 (2024 Q2 $50k, first qtr, LBR "Issues related to the FTC"); a0b40806-b044-46a9-b049-3258519172ae (2024 Q3 $150k); 2b286ce4-5e44-4028-a890-95a67e6e31be (2025 Q4 $200k) | confirm FTC action date (May 2024) against the Q2-2024 start; editorial-sensitivity review | 2026-07-06 |
| L023 | Vantive (spun off from Baxter in 2025) writes $2.5M to the White House Ballroom Project while standing up a six-firm federal lobbying operation in its first independent year | F1+E2 contribution/fan-out | Vantive US Healthcare LLC; Trust for the National Mall; Ballard; Checkmate; Akin Gump; Todd Strategy; Nickles Group; Porterfield Fettig & Sears | triaged | orchestrator | c205e636-9a57-43e0-9e72-166ec938b826 (LD-203 item 0, $2,500,000, 2025-10-13, honoree "White House Ballroom Project", payee Trust for the National Mall); six 2025 registrants via E2 | editorial-sensitivity review (sitting President's project); confirm Baxter spin-off date; map what Vantive lobbied on (dialysis/ESRD payment policy?) | 2026-07-06 |
| L024 | A new opaque "Battery Advocacy for Technology Transformation (BATT) Coalition" stands up ~$800k/yr of lobbying on tax/critical minerals from a zero base in mid-2024; ultimate members undisclosed | E1 emergence | BATT Coalition; Strategic Marketing Innovations (SMI); Cannon-Pearce (Matt Pearce) | open | unassigned | b4fb015c-25b1-4d53-98d2-de133b35b75e (SMI 2024 Q3 $135k, first appearance, TAX/critical minerals); 1d5385d1-472d-4a12-bcd7-8e05833dcb56 (2025 Q2 $220k); 2791dc4e-303d-4785-ad17-4786bf0c95aa (2026 Q1 $170k) | identify who funds BATT (coalition site / FARA / press via outside-context-scan); who is Strategic Marketing Innovations? | 2026-07-06 |
| L025 | A class of LD-2 single-quarter income overstatements the gap-lens (sweep S5) misses: e.g. MedSecurean / Indian Pharmaceutical Alliance reports $900k in 2025 Q4 vs a $15k baseline (60x) | E4 single-quarter spike | MedSecurean.com; Indian Pharmaceutical Alliance; also Robert K Weidner / RPLCC | parked | unassigned | c48b53f8-8c92-43e1-9b51-b5160eb437da (2025 Q4 $900,000 vs $15k prior; same registrant's Lupin client same qtr = $42k) | per-record confirm real surge vs misreport; if systemic, a standalone data-quality finding; low priority | 2026-07-06 |

## Entities checked

Documents the "dig past the mechanically-dominant top result" discipline: entities that sat at the
top of a lens ranking but were set aside as already-obvious or non-novel, so the leads above come
from underneath them.

| entity (entity_id) | verdict | records examined | date |
|---|---|---|---|
| Korea Zinc Company, Ltd. (client, via Mercury/Ballard) | set aside — largest E1 emergent engagement but a well-publicised MBK/Young Poong takeover fight; mechanically top, not novel | E1 top row; 12 filings 2024-2026 | 2026-07-06 |
| Trump-Vance Inaugural Committee corporate donors (JBS, Robinhood, Occidental, NVIDIA, Uber, X, et al.) | set aside — F1 top cluster is widely-reported corporate inaugural giving; a known category | F1 rows ($1-5M each) | 2026-07-06 |
| IBEW / union LD-203 "N/A" honoree placeholders | set aside — mechanical top of honoree concentration (placeholder honoree, not a real recipient) | F1 top row ($8M/N-A) | 2026-07-06 |

## Queries run

| date | SQL (file in queries/) | one-line result |
|---|---|---|
| 2026-07-06 | emergence_and_flows.sql#E1 | emergent engagements 2024-25; Korea Zinc top (known), TP-Link / BATT / Sheffield / WuXi AppTec underneath |
| 2026-07-06 | emergence_and_flows.sql#E2 | per-client registrant roster (fan-out); Vantive = six firms in 2025 |
| 2026-07-06 | emergence_and_flows.sql#E3 | individuals as clients; Fred Daibes $1M "Executive relief", Scott Sheffield "Issues related to the FTC" |
| 2026-07-06 | emergence_and_flows.sql#E4 | single-quarter income spikes; MedSecurean/IPA $900k vs $15k baseline (likely misreport) |
| 2026-07-06 | emergence_and_flows.sql#F1 | LD-203 honoree concentration; Vantive $2.5M White House Ballroom Project stands out from the inaugural-donor cluster |

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
| L025 | data-quality signal, noisy; needs per-record confirmation to separate real surges from misreports | if a say-vs-pay lead lands on one of these engagements, or if pursuing a standalone data-quality finding | 2026-07-06 |
