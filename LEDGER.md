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
| L026 | Medicare/Medicaid say-vs-pay divergence: congressional press attention-share on MMM more than doubles in 2025 (2.4% -> 5.7% of tagged releases, 2025 Q2) during the reconciliation Medicaid-cut fight, while MMM lobbying-money share FALLS every year (9.09% -> 7.55% of Q2 spend, 2022->2025, filing_period-deduped) — the loud press voices (Dem leadership) are entirely different actors from the steady paid healthcare-industry clients | press-issue coupling P3 (share divergence, r_concurrent -0.72) | Richard J. Durbin; Hakeem S. Jeffries; Elizabeth Warren; Katherine M. Clark; Ben Ray Luján (press); American Health Care Assoc.; American College of Clinical Pharmacy; Virginia Hospital & Healthcare Assoc. (paid) | triaged | orchestrator | press 2025 Q2: Durbin 35 / Jeffries 29 / Warren 27 / Clark 22 releases mention MMM; congress_press/2025/2025-05.jsonl:1719 (Lujan, "Largest Medicaid cuts", 05-12); congress_press/2025/2025-06.jsonl:1046 (Warren, "GOP Pushes Massive Medicaid Cuts", 06-09). paid 2025 Q2: d8300083-1e6c-46c0-81f9-a236a6dccd29 (Amer. College of Clinical Pharmacy $450k); 37945083-130b-484d-8948-16ae9e1f26bf (American Health Care Assoc./BGR $150k); b3f18357-a244-4942-a896-ace3ef854621 (Virginia Hospital & Healthcare Assoc. $220k) | deep-read a sample of the 2025 Q2 MMM releases to confirm the message is anti-cut (not industry-aligned); is the money-share decline a real reallocation or a denominator effect; editorial framing of "messaging vs money" | 2026-07-06 |
| L027 | Trade/tariffs coupling: press attention-share and lobbying-money share on TRD are both flat 2022-2024 then jump together in 2025 (press 1.2%->3.8%, spend ~4.0%->5.5%) — the tightest positive coupling (r_concurrent +0.88), but the mechanically-obvious 2025 Trump-tariff story | press-issue coupling P2 (concurrent, r +0.88) | Cleo Fields; Richard J. Durbin; Jeanne Shaheen (press); Nippon Steel Corp.; Brown-Forman Corp.; Qualcomm Inc. (paid) | parked | orchestrator | press 2025 Q2: Durbin 22 / Shaheen 22 / Jeffries 15 mention TRD; congress_press/2025/2025-04.jsonl:287 (Cleo Fields on Trump's Tariffs). paid 2025 Q2: 744e3154-0c29-4753-9138-c048c07377b1 (Nippon Steel/Akin Gump $1.2M); d696cbea-4042-4cb8-b3a3-8b87f551cd8f (Qualcomm $500k); e75b7652-4644-458c-9138-ed3e95c133d3 (Brown-Forman $320k) | logged to satisfy the "citable coupling" deliverable; not pursued as novel (widely-reported tariff cycle). one paid-side $20M "LOC Nation" filing looks like a misreport — excluded | 2026-07-06 |
| L028 | P2 cross-check surfaced a say-vs-pay contrast on SECURE 2.0: heavy, specific retirement/annuity-industry lobbying (1,436 senate / 1,416 house filings NAME it in their own activity text — Athene, Fidelity/FMR, American Benefits Council, HR Policy Association) vs. thin coverage in members' OWN press releases (~54 name it corpus-wide, top voice Van Hollen x4). **Outside-context-scan 2026-07-07 reframes this to a known story, not a novel lead:** "near-silent" holds only for congressional member press releases — SECURE 2.0 was HIGH news-salience (CNBC + heavy trade/law-firm coverage; "largest retirement legislation since 2006") and the industry-lobbying angle was contemporaneously reported (InvestmentNews: annuities "top IRI's lobbying agenda"; Retirement Income Journal; Cato). Valid as a P2 tooling demo; parked as a lead. **Second, corpus-internal reason the "near-silent" read was unreliable (added 2026-07-07):** the ~54 press count is corpus-wide, and it DID capture the peak advocacy (2022-03 House passage = 17 releases; 2022-12 enactment = 10) — but the bill's whole life (introduced 2021 as H.R.2954, passed 2022) sits in the corpus's thinnest period (press starts 2022-01-01 so 2021 advocacy is unseen; 2022 = ~40% of 2025's release volume), so raw counts understate a 2022-vintage bill vs. a persistent 2025-era one like the IRA. | P2 bill cross-check (free-text name match, say-vs-pay) + outside-context-scan | Athene Holding (Brownstein Hyatt); CHRO Association / HR Policy Association (Tributary LLP); American Benefits Council; FMR LLC / Fidelity (paid) · Chris Van Hollen; John B. Larson; Brendan F. Boyle (press) | parked | unassigned | 50349204-4f47-471a-8c08-21f29a66a872 (Athene 2025 Q1 $280k, activity names "SECURE 2.0"); a855ea99-d047-4ffa-872c-afe8c3ec4c63 (Athene 2024 Q3 $240k); ec2ec9f3-db85-4b04-a55b-ba726d84884c (CHRO/HR Policy Assoc. 2022 Q4 $930k); press congress_press/2026-01.jsonl:2133 (Larson). Scan sources: cnbc.com/2022/12/23/secure-2point0-clears-congress; investmentnews.com/…/bill-allowing-more-types-of-annuities…tops-iris-lobbying-agenda/238709; cato.org/regulation/spring-2023/where-are-retirement-tontines | closed as a known story unless a specific, unreported company-level ask surfaces (note the adjacent, UNRELATED beat: Athene's 2024-25 pension-risk-transfer ERISA class actions — AT&T/Lockheed/Bristol Myers — a different lead if pursued) | 2026-07-07 |

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
| 2026-07-06 | press_issue_coupling.sql#P0 | press vocabulary sanity: 44 ALI codes tagged, 80% of releases; HCR/BUD/VET/LAW/AGR/DEF/IMM on top, low-precision codes (INS/GAM/SPO/COM) at the bottom |
| 2026-07-06 | press_issue_coupling.sql#P2 | share-based coupling ranking (raw counts confounded by 4x corpus growth); positive: TRD +0.88, ENV +0.86, CAW +0.84; negative: MMM -0.72, LBR -0.57 (shaky), RET -0.44 |
| 2026-07-06 | press_issue_coupling.sql#P3 | say-vs-pay divergences; MMM 2025 Q2 is the top loud-press/quiet-spend row (press pctl 1.0, spend pctl 0.0) -> L026 |
| 2026-07-06 | press_issue_coupling.sql#P4/P4b | named actors behind MMM 2025 Q2 both sides (Durbin/Jeffries/Warren/Clark press; healthcare-industry clients paid) |
| 2026-07-07 | p2_bill_crosscheck.sql#P2a–P2d + skills/lead-scanner/scripts/bill_lookup.py (HR5376 by number & by alias; Farm Bill phrase-primary; 12-alias say-vs-pay scan) | IRA press: 53 releases cite H.R.5376 vs 3,189 that NAME it (3,157 name-only) — quantifies the L004 say-vs-pay gap number-only matching missed; Farm Bill: 0 number matches but 11,641 senate / 11,460 house / 1,498 press name it; SECURE 2.0 = heavy-lobby/quiet-press outlier → L028 |

## Cold threads

| lead id | parked reason | revisit trigger | date parked |
|---|---|---|---|
| L025 | data-quality signal, noisy; needs per-record confirmation to separate real surges from misreports | if a say-vs-pay lead lands on one of these engagements, or if pursuing a standalone data-quality finding | 2026-07-06 |
| L027 | strongest positive coupling but a widely-reported 2025 Trump-tariff cycle — mechanically obvious, logged only to evidence the coupling deliverable | if a specific member loud on tariffs turns out to be paid-side coupled (donors/registrants), or if a non-2025 trade coupling appears | 2026-07-06 |
| L028 | outside-context-scan (2026-07-07) shows SECURE 2.0 was high news-salience and the retirement/annuity industry-lobbying angle was contemporaneously reported (InvestmentNews / Retirement Income Journal / Cato); "near-silent" holds only for members' own press releases, so there's no novel say-vs-pay story here. Retained as a P2 tooling demo (the cross-check correctly surfaced a real filing-vs-messaging contrast). | if a specific, unreported company-level ask emerges — e.g. a tie between a named client's SECURE 2.0 engagement and Athene's separate 2024-25 pension-risk-transfer ERISA litigation | 2026-07-07 |
