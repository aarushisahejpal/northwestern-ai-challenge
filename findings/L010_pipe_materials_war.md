# Finding: The pipe-materials war — DIPRA's Q1 2026 spending spike

**Status:** revised after first verification FAIL (2026-07-06); re-verification pending before lock
**Lead:** L010 (descends from L004)
**Legal flag:** none
**Date drafted:** 2026-07-05

## Headline

In Q1 2026, the Ductile Iron Pipe Research Association (DIPRA) nearly doubled its own
recent-quarter lobbying spend to push "materials provisions" and "domestic sourcing"
language favoring iron pipe into five separate FY26 appropriations bills, a TSCA
reauthorization, and the NDAA, deploying former U.S. Representative Martha Roby as a
named lobbyist — while McWane Inc., a fellow ductile-iron-pipe manufacturer, showed no
comparable increase in its own separate lobbying spend that quarter. DIPRA plus McWane's
flat spend together outspent the plastic/copper-pipe registrants found in a targeted
search roughly 2.7-to-1, though only Copper Development Association's share of that
total shows a clear textual connection to the same fight (see C5 caveat below). The only
public trace of the fight is an unrelated press release that happens to describe
"ductile iron pipes" as the material used in a bipartisan water-infrastructure grant —
not the underlying appropriations/TSCA fight itself.

## Claims

**C1 — DIPRA's Q1 2026 filing is a real spike, not a normal quarter.**
DIPRA (via registrant Bradley Arant Boult Cummings LLP) reported quarterly income of
$350,000 / $310,000 / $310,000 / $290,000 across Q1–Q4 2025 (2025 average: $315,000),
then $540,000 in Q1 2026 — +54% over its highest 2025 quarter, +86% over the immediately
preceding quarter (Q4 2025), +71% over its 2025 average.
- Citations: `4c7a4352-89e7-459b-8806-103281faa317` (2025 Q1, $350K),
  `aef5c0b9-8ecc-4112-9f7b-179d79160396` (2025 Q2, $310K),
  `d7728fe3-0f18-444c-8969-85cbcc52d41d` (2025 Q3, $310K),
  `5adf05eb-9e01-431d-916c-ece830b296e1` (2025 Q4, $290K),
  `7e61b5d2-5200-4d78-9499-9cce289c4994` (2026 Q1, $540K).
- Aggregate SQL: `queries/l010_pipe_war.sql#L010c`. DB rebuild:
  `build_db.py --data-root data/ --db db/lda_pilot.duckdb --years 2025 2026`.

**C2 — The spike is DIPRA-specific, not industry-wide.** McWane Inc., a fellow
ductile-iron-pipe manufacturer, shows no comparable increase in the same quarter: Balch
& Bingham LLP billed McWane a flat $90,000 every single quarter from Q1 2025 through Q1
2026 with zero variance; The Wessel Group Incorporated billed $40K/$50K/$50K/$40K in
2025 and $50K in Q1 2026 (normal quarter-to-quarter noise, no spike). Note: this corpus
does not document a formal DIPRA-McWane membership relationship — DIPRA's own filings
carry an empty `affiliated_organizations` field in every quarter checked, and McWane's
own lobbying-activity text never mentions DIPRA, ductile iron, TSCA, the NDAA, or any of
DIPRA's five named appropriations bills (McWane's disclosed issues are Buy America/
domestic-procurement, the Fighting Trade Cheats Act, and chemical policy — related
industry ground, not the same fight). "Fellow manufacturer" here describes the same
product category, not a documented trade-association membership.
- Citations: `d8b5dec8-4f16-4acb-a0b3-b0a7c539e25e` (Balch, 2025 Q1, $90K) through
  `6817ab80-c4d5-4eb7-8493-5af807874661` (Balch, 2026 Q1, $90K); Wessel series
  `79346c8e-68d5-44dc-8f19-716e7d24a954` (2025 Q1) through
  `fc5d7964-4c2d-425c-8012-b0b50caeb955` (2026 Q1). Full series: `l010_pipe_war.sql#L010c`.

**C3 — DIPRA's own filing names the specific legislative targets.** The Q1 2026
lobbying-activity text (general_issue_code `MAN`) reads verbatim: "Water infrastructure
investment, domestic sourcing, and materials provisions." A second activity
(`BUD`) names, by bill number, the FY26 Agriculture (H.R.4121/S.2256), Commerce-Justice-
Science (H.R.5342/S.2354), Defense (H.R.4016/S.2572), Energy & Water (H.R.4553/S.3293),
Interior-Environment (H.R.4754/S.2431), and THUD (H.R.4552/S.2465) appropriations bills,
explicitly ties "materials provisions, domestic sourcing" to water infrastructure
funding, cites "Toxic Substances Control Act reauthorization, materials provisions," and
names the FY26 NDAA (H.R.3838/S.2296/S.1071), also for "materials provisions."
- Citation: `7e61b5d2-5200-4d78-9499-9cce289c4994` (senate_activities rows 0–1);
  bill list also in `bill_mentions` for the same filing_uuid.

**C4 — Martha Roby is a named, self-disclosed lobbyist on the account.** The same Q1
2026 filing lists three lobbyists: David Stewart, Ryan Robichaux, and Martha Roby,
covered position self-described as "Former Member of U.S. House of Representatives."
(Each name appears twice in the underlying activity rows — DIPRA reported two lobbying
activities for the quarter and repeated the same three-person roster on both; this is
not four distinct people.)
- Citation: `7e61b5d2-5200-4d78-9499-9cce289c4994` (senate_lobbyists rows).

**C5 — The iron side outspent registrants named for plastic/copper pipe interests
~2.7x in the same quarter, but only part of that total is textually tied to the same
fight.** Iron side: DIPRA $540,000 + McWane $140,000 (Balch $90K + Wessel $50K) =
$680,000. Plastic/copper-pipe-interest registrants, same quarter: Diamond Plastic Corp
$20,000 (Water Strategies), Hobas Pipe USA $20,000 (Water Strategies), Copper
Development Association $110,000 (Kinghorn, Hilbert & Associates), Plastics Industry
Association $20,000 (Venture Government Strategies) + $40,000 (ACG Advocacy) + $40,000
(The Vogel Group) = $250,000 total (one additional Plastics Industry Association
self-filed registration, `2e31d978`, discloses $150,000 in expenses but is excluded
because its activity text is unrelated to pipe — see caveat, not because it lacks
income). $680,000 / $250,000 ≈ 2.7x — arithmetically correct, but a topic check of the
underlying activity text shows only part of that $250,000 is actually about the same
fight: Copper Development Association's text ("Copper pipe and tube advocacy,"
"Innovative materials and material selection," $110,000) plausibly engages the same
materials-selection question DIPRA is lobbying on. Diamond Plastic/Hobas ($40,000,
"modern pipe construction methods, standards, and projects") are adjacent but generic.
Plastics Industry Association's $100,000 (Venture/ACG/Vogel) — 40% of the $250,000
total — has no demonstrated textual connection: its Q1 2026 activity text covers
general plastics-industry/manufacturing advocacy, recycling infrastructure, trade, and
tax issues, with no mention of pipe, materials provisions, TSCA, the NDAA, or any of
DIPRA's named bills. The ~2.7x figure should be read as an upper bound on the visible
opposition; the total demonstrably engaged in the same fight is closer to $110,000–
$150,000 (Copper Development, plus arguably Diamond Plastic/Hobas), not the full
$250,000.
- Citations: `fa4e3cf3-c8dd-48ba-a2ff-dd9054a09aa9` (Diamond Plastic, $20K),
  `a8b88b9d-c07a-456f-87cf-a31af4e9511a` (Hobas, $20K),
  `a5ed3b1c-3236-4550-809a-317bea5dc533` (Copper Development, $110K, "copper pipe and
  tube advocacy" / "innovative materials and material selection"),
  `8b821804-9d30-4223-9dba-e307dbe6fcc8` (Plastics Industry/Venture, $20K, general
  plastics-manufacturing/recycling advocacy — no pipe-materials text),
  `c7c2091b-75cc-434f-865d-840062444a89` (Plastics Industry/ACG, $40K, same),
  `590f0248-3492-47aa-b0b3-29f08f2f18e6` (Plastics Industry/Vogel, $40K, same);
  `2e31d978-e6e3-4664-b1a7-effb460fdd45` (excluded PIA self-filing, $150K expenses,
  activity text is H.R.1 tax reconciliation / CIRCLE Act / GRAS food-safety / recycling
  — unrelated to pipe, hence excluded on substance, not on a null-income technicality).
- Aggregate SQL: `queries/l010_pipe_war.sql#L010d`.

**C6 — Public/press footprint is incidental, not substantive.** The only located press
mention naming ductile iron pipe is a 2026-03-30 joint release from Reps. McBath and
Williams and Sens. Ossoff and Warnock announcing a $2,134,000 federal grant to replace
lead pipes in College Park, GA with "ductile iron pipes" — a description of the material
used in an already-passed funding bill, with no reference to DIPRA, the appropriations
riders, TSCA, or the NDAA materials-provisions push described in C3.
- Citation: `congress_press/2026-03.jsonl:3394`.

## Caveats / what this finding does NOT claim

- This does not establish that DIPRA's spending caused any specific bill outcome —
  only that the spend, the named legislative targets, and the lobbyist roster are as
  described, and that the timing (Q1 2026, the quarter appropriations riders were live)
  coincides with the spike.
- "Opposition" (C5) is limited to registrants whose LDA filings name plastic or copper
  pipe manufacturing/trade interests and were found via targeted client-name search: it
  is not a claim that no other opposition exists, only that no other opposition surfaced
  in the LDA corpus for Q1 2026 under these search terms.
- No outside data (e.g., committee markup records, floor amendment text) has been pulled
  to confirm whether the "materials provisions" DIPRA describes were actually adopted in
  any bill's final text — this finding is about lobbying activity and disclosure, not
  legislative outcome.
- **McWane is not documented in this corpus as a DIPRA member.** No filing carries an
  affiliation record between them (DIPRA's `affiliated_organizations` field is empty
  every quarter); "fellow manufacturer" reflects that both lobby on ductile iron pipe,
  not a sourced membership relationship. If a membership needs to be asserted, it
  requires an outside-data citation (e.g., DIPRA's own member listing), disclosed per
  README §4 — none has been pulled for this finding.
- **Most of the counted "opposition" total is not shown to be about this specific
  fight.** Of the $250,000 in C5, only Copper Development Association's $110,000 has
  activity text plausibly engaging DIPRA's materials-selection question; Plastics
  Industry Association's $100,000 (40% of the total) is, per its own disclosed activity
  text, about unrelated plastics-industry/recycling/trade/tax matters. Treat the $250K/
  2.7x figure as an upper bound on visible same-industry spend, not as evidence that
  quarter's full opposition coalition was contesting DIPRA's specific asks.

## Verification

_Run 2026-07-06 by a fresh verification agent per `skills/finding-verifier/SKILL.md`, no
drafting-session context. Data root used: the challenge corpus at `data/` (senate/house/
congress_press); DB: `db/lda_pilot.duckdb`. Every citation key below was independently
resolved via `show_record.py`; both aggregate SQL blocks (L010c, L010d) were re-run from
the file as-is and every dollar figure and ratio was recomputed by hand from the raw
`show_record.py` output, not copied from the draft's prose._

**C1 — verified.** All five `filing_uuid`s resolve to exactly the claimed records:
Bradley Arant Boult Cummings LLP / DIPRA, income $350K (Q1'25), $310K (Q2'25), $310K
(Q3'25), $290K (Q4'25), $540K (Q1'26) — figures match the JSON `income` field verbatim,
and `queries/l010_pipe_war.sql#L010c` reproduces the identical five rows. Recomputed
independently: 2025 avg = (350+310+310+290)/4 = $315,000 ✓; 540/350 = 1.5429 → +54% ✓;
540/290 = 1.8621 → +86% ✓; 540/315 = 1.7143 → +71% ✓. Arithmetic is exact, not rounded
favorably.

**C2 — verified**, with one unsupported premise flagged. The dollar series checks out
exactly: Balch & Bingham billed McWane $90,000 in every quarter Q1'25–Q1'26 (five
`filing_uuid`s spot-checked, all `"income": "90000.00"`, zero variance, confirmed against
`L010c`); Wessel Group billed $40K/$50K/$50K/$40K/$50K (spot-checked 2025-Q1 and 2026-Q1
records directly, both match). However, the premise "McWane Inc., a DIPRA member" carries
**no citation anywhere in the finding**, and the corpus does not support it: DIPRA's own
filings (checked all five, including the Q1 2026 filing cited for C3/C4) carry
`"affiliated_organizations": []` every quarter, and McWane's own lobbying-activity text
(pulled in full across all four McWane registrants/16 activity rows) never mentions
ductile iron, DIPRA, TSCA, the NDAA, or any of the five FY26 appropriations bills DIPRA
names — McWane's disclosed issues are Buy America/domestic-procurement, the Fighting
Trade Cheats Act, chemical policy, and "declining manufacturing base," which is
industry-adjacent but not the same fight. This doesn't break C2's own numeric claim (no
spike), but it undercuts calling McWane a documented "member" — that's asserted from
outside general knowledge, not from any record in this corpus, and should be hedged or
dropped.

**C3 — verified.** Opened `7e61b5d2-5200-4d78-9499-9cce289c4994` directly. The `MAN`
activity description is verbatim "Water infrastructure investment, domestic sourcing,
and materials provisions." The `BUD` activity text was checked bill-by-bill against the
claim: H.R.4121/S.2256 (Agriculture) ✓, H.R.5342/S.2354 (CJS) ✓, H.R.4016/S.2572
(Defense) ✓, H.R.4553/S.3293 (Energy & Water) ✓, H.R.4754/S.2431 (Interior-Environment) ✓,
H.R.4552/S.2465 (THUD) ✓, "Toxic Substances Control Act reauthorization, materials
provisions" ✓, FY26 NDAA H.R.3838/S.2296/S.1071 "materials provisions" ✓ — every bill
number and the quoted phrases are exact matches, not paraphrase.

**C4 — verified.** Same filing's `lobbying_activities[].lobbyists` and the DB's
`senate_lobbyists` table both confirm exactly three lobbyists — David Stewart, Ryan
Robichaux, Martha Roby — with Roby's `covered_position` verbatim "Former Member of U.S.
House of Representatives." Six `senate_lobbyists` rows = 3 lobbyists × 2 activity
indices, confirming the "appears twice, not four distinct people" clarification.

**C5 — overstated.** The dollar figures and ratio are arithmetically correct: every one
of the six cited `filing_uuid`s was opened and matches exactly (Diamond Plastic $20K,
Hobas $20K, Copper Development $110K, Plastics Industry via Venture $20K / ACG $40K /
Vogel $40K = $100K), `L010d` reproduces all seven rows including the correctly-excluded
null-income self-filed PIA registration, and 680,000 / 250,000 = 2.72 ≈ "~2.7x" is right.
But spot-checking the underlying **activity text** (not just the dollar amounts) shows
the "opposition" label is weaker than the framing implies: the excluded self-filed PIA
registration (`2e31d978-e6e3-4664-b1a7-effb460fdd45`) was rightly dropped, but not for
the reason given ("disclosed no income") — its `expenses` field actually shows $150,000
in self-filed lobbying spend, and the real reason to exclude it is substantive: its
activities are H.R.1 tax reconciliation, the CIRCLE Act, GRAS food-safety regulation, and
recycling bills, nothing about pipe. That same substantive check applied to the
*included* PIA filings shows the same problem: Venture/ACG/Vogel's Q1 2026 activity text
("general engagement... plastics industry and its role in U.S. manufacturing,"
recycling infrastructure, "trade issues," "taxation issues") never mentions pipe,
materials provisions, TSCA, the NDAA, or any of DIPRA's five appropriations bills — that
$100,000 (40% of the $250K "opposition" total) has no demonstrated textual nexus to the
fight described in C3. Diamond Plastic/Hobas (Water Strategies, $40K) are thin too —
"modern pipe construction methods, standards, and projects" plus generic
appropriations-tracking, not explicit opposition to materials-provisions language. Only
Copper Development Association's activity text ("Copper pipe and tube advocacy,"
"Innovative materials and material selection," $110K) plausibly engages the same
materials-selection fight. **Recommendation:** hedge the $250K/2.7x framing to disclose
that only ~$110–150K of the "opposition" total shows textual alignment with the specific
appropriations/TSCA/NDAA materials-provisions fight; the rest is same-industry client
spend of unconfirmed relevance. The existing caveat ("found via targeted client-name
search... not a claim that no other opposition exists") partially covers this but doesn't
disclose that most of the counted dollars aren't shown to be *about* this fight either.

**C6 — verified.** `congress_press/2026-03.jsonl:3394` resolves to the McBath/Williams/
Ossoff/Warnock release dated 2026-03-30, $2,134,000 grant, lead-pipe replacement in
College Park GA, "replace lead pipes with ductile iron pipes" — verbatim match. No
mention of DIPRA, appropriations, TSCA, or NDAA anywhere in the text, confirming the
claim that this is incidental, not a trace of the underlying fight.

### Headline check

The headline overreaches in one place and should be corrected before lock: **"joined by
member company McWane Inc." is not supported and is in tension with the finding's own
C2.** No record in this corpus documents McWane as a DIPRA member (DIPRA's
`affiliated_organizations` is empty in every filing checked), and C2 itself proves McWane
did *not* ramp spend and its own filings never name the same bills, TSCA, or the NDAA —
McWane's lobbying that quarter looks like ordinary, unrelated Buy America/trade-cheats
advocacy. "Joined by" reads as coordinated escalation; the data shows the opposite
(McWane sat this one out, dollar- and topic-wise). Recommend rewriting to something like
"...while McWane Inc., a fellow ductile-iron-pipe manufacturer, showed no comparable
increase in its own (separate) lobbying spend that quarter" — which is what C2 actually
supports. The "nearly doubled" framing (Q4'25 $290K → Q1'26 $540K = 1.86x) is a
defensible characterization of an 86% jump. The "~2.7-to-1" outspend claim is
arithmetically sound but, per the C5 verdict above, should carry the same hedge about
opposition-total composition — as currently written the headline presents it as clean
fact. The press-release sentence is honestly hedged ("not the underlying
appropriations/TSCA fight itself") and matches C6.

### Caveats sanity-check

The three existing caveats are honest and appropriately modest — they correctly disclaim
causation to bill outcomes, correctly scope "opposition" to a client-name search rather
than a completeness claim, and correctly note no outside legislative-outcome data was
pulled. They do **not**, however, disclose the two issues found above: (1) "DIPRA member"
for McWane is asserted, not documented in-corpus; (2) a meaningful share of the counted
"opposition" spend (PIA's $100K) has no demonstrated textual connection to the specific
fight, only to the same industry. Both should be added as caveats regardless of what
happens to the headline wording.

### Overall recommendation: **FAIL** (revise before lock)

C1, C3, C4, and C6 are cleanly verified — every citation resolves to exactly what's
claimed, and the aggregate arithmetic in C1 is exact. C2's numbers are verified but rest
on an uncited "DIPRA member" premise for McWane. C5's dollar figures and ratio are
correct but the "opposition" characterization is overstated for ~40% of the total. The
headline compounds both: it asserts McWane "joined" the push (contradicted by the
finding's own C2 data) and presents the 2.7x ratio without the composition caveat.

**What must change before this can pass:**
1. Either cite a source for "McWane Inc., a DIPRA member" (outside data, disclosed per
   README §4) or drop "member" and reframe as same-industry, non-affiliated.
2. Rewrite the headline clause "joined by member company McWane Inc." so it doesn't
   imply McWane co-escalated — C2 shows the opposite.
3. Add a caveat disclosing that only Copper Development Association's $110K (and
   arguably Diamond Plastic/Hobas's $40K) shows textual alignment with the
   materials-provisions/TSCA/NDAA fight; Plastics Industry Association's $100K does not,
   per its own disclosed activity text.
4. Once (1)–(3) are made, the underlying record-level work (C1, C3, C4, C6) and the SQL
   (L010c, L010d) need no further changes — they are solid.

---

**Post-FAIL revision (2026-07-06, same session that drafted the finding — NOT an
independent pass):** applied all four items above verbatim — headline reworded to drop
"joined by member company," C2 reframed as "fellow manufacturer" with the empty
`affiliated_organizations` / no-shared-topic finding stated explicitly, C5 rewritten to
disclose that only ~$110-150K of the $250K opposition total has textual nexus to the
fight (Plastics Industry Association's $100K flagged as unconnected per its own activity
text), and two new caveats added covering both issues. Because these edits were made by
the drafting session, not a fresh one, they do NOT themselves constitute the independent
re-verification the protocol requires — a second fresh-agent pass is dispatched to
confirm the fixes actually resolve the FAIL before this finding can lock.
