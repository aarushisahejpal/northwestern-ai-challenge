# Findings Report

The submission's two locked findings, combined verbatim below (identical to the files in
`findings/`). Both passed independent fresh-agent verification before lock (`DECISIONS.md`,
2026-07-15). Every citation key resolves to a raw record via
`python skills/lda-corpus-loader/scripts/show_record.py <key> --db db/lda_full.duckdb --data-root data/`.

---

# Finding: The pipe-materials war — DIPRA's Q1 2026 spending spike

**Status:** independently verified, PASS (2026-07-06, second fresh-agent pass) — LOCKED as a submitted finding (team sign-off, DECISIONS.md 2026-07-15)
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

## Re-verification (fix check)

_Run 2026-07-06 by a fresh agent, checking only the 4 required fixes from the FAIL
verdict above (not re-deriving C1/C3/C4/C6 or re-running SQL, per instructions). Data
root: `../data/data` (the `data/` folder in this working copy was empty of corpus files;
resolved the real root by locating `senate/2026/filings/filings_2026.json` on disk). DB:
`db/lda_pilot.duckdb`. Every record below was pulled directly via `show_record.py`._

1. **Headline no longer implies McWane joined/co-escalated — yes.** Current text reads
   "...while McWane Inc., a fellow ductile-iron-pipe manufacturer, showed no comparable
   increase in its own separate lobbying spend that quarter," and separately hedges the
   2.7x figure ("though only Copper Development Association's share of that total shows
   a clear textual connection to the same fight"). No "joined"/"member" language remains.

2. **C2 no longer asserts DIPRA membership as fact — yes.** C2 now reads "this corpus
   does not document a formal DIPRA-McWane membership relationship" and cites the empty
   `affiliated_organizations` field plus no shared topic in McWane's activity text.
   Independently re-pulled all five DIPRA filings (`4c7a4352…`, `aef5c0b9…`, `d7728fe3…`,
   `5adf05eb…`, `7e61b5d2…`) — every one shows `"affiliated_organizations": []`.
   Independently pulled McWane's 2026-Q1 Balch (`6817ab80…`) and Wessel (`fc5d7964…`)
   filings — activity text covers Buy America/domestic-procurement, Fighting Trade
   Cheats Act, PFAS/Clean-Air-Water, and infrastructure-manufacturing policy; no mention
   of DIPRA, ductile iron, TSCA, the NDAA, or any of DIPRA's five named appropriations
   bills. Text is accurate, not just present.

3. **C5 no longer presents $250K/2.7x as undifferentiated fact — yes.** Independently
   pulled all three PIA filings counted in the $250K (Venture `8b821804…` $20K, ACG
   `c7c2091b…` $40K, Vogel `590f0248…` $40K = $100K) — none mention pipe, materials
   provisions, TSCA, the NDAA, or any DIPRA bill; text is general plastics-industry,
   recycling, trade, and tax advocacy, confirming C5's "no demonstrated textual nexus"
   claim. Pulled Copper Development (`a5ed3b1c…`, $110K) — activity text includes "Copper
   pipe and tube advocacy" and "Innovative materials and material selection," supporting
   the "clear textual connection" claim. Pulled Diamond Plastic (`fa4e3cf3…`) and Hobas
   (`a8b88b9d…`, $20K each) — text is "modern pipe construction methods, standards, and
   projects" plus generic appropriations-tracking, matching the "adjacent but generic"
   characterization. Pulled the excluded self-filed PIA registration (`2e31d978…`) —
   `income` is null but `expenses` is `"150000.00"`, and its activity text (H.R.1 tax
   reconciliation, CIRCLE Act, GRAS regulation, recycling bills) has no pipe mention,
   confirming C5's revised claim that it was excluded on substance, not on a null-income
   technicality.

4. **Caveats disclose both issues — yes.** The two new caveats ("McWane is not documented
   in this corpus as a DIPRA member..." and "Most of the counted 'opposition' total is not
   shown to be about this specific fight...") are present, and both match the
   independently-verified record facts above (empty `affiliated_organizations`; PIA's
   $100K lacking topical connection).

**Overall: PASS.** All four required fixes were made, and each was independently
re-derived from the underlying filing records (not just checked for presence of the
right words) and confirmed accurate.

---

# Finding: Full-corpus Senate lobbying trends, 2022–2026 Q1 (ported from Chris Cioffi's findings report)

**Status:** author-verified AND fresh-agent verified — **PASS, 8/8 claims** (2026-07-14,
finding-verifier protocol; verification block appended at the end of this file, including
three hedges to carry when citing). LOCKED as a submitted finding (team sign-off, DECISIONS.md 2026-07-15).
**Author:** Chris Cioffi. Ported verbatim from `ChrisCioffi/agentic_investigation`
`skills/lobbying-issue-theme-clustering/FINDINGS.md` (sections reproduced unchanged; only this
provenance header added).
**Produced with:** `skills/lobbying-quarterly-filings/` (migrated into this repo) —
`get_local_senate_filings()` per year + `flag_dupes()` + `flag_client_registrant_conflict()`.
The original report's TAX-theme section used the `lobbying-issue-theme-clustering` skill,
which is NOT part of this submission, and is deliberately not ported (except the
double-counting-trap subsection below, whose fix and root-cause trace live in this repo at
`skills/lobbying-quarterly-filings/scripts/lobbyr_clean.R` (`normalize_entity_name()`) and
`skills/lobbying-quarterly-filings/references/data_quality_notes.md`).
**Legal flag:** none
**Cross-corroboration note (added at port):** the "STATE OF LOC NATION" $20M×3 suspicious
filings flagged below were independently flagged by this repo's own pipeline (leads
L025/L027, `traces/INDEX.md`) — two toolchains, same anomaly.

---

### (from the TAX section) A real double-counting trap

**A real double-counting trap, caught by hand -- and fixed, not just flagged.** "Business
Roundtable" appears under five spellings in this data -- "BUSINESS ROUNDTABLE", "THE BUSINESS
ROUNDTABLE", "THE BUSINESS ROUNDTABLE, INC.", "BUSINESS ROUNDTABLE INC", and "BUSINESS
ROUNDTABLE (THE)" -- across its own $7.59M self-filed report *and* separate outside-firm
filings (Ballard Partners, CGCN Group, Fierce Government Relations, Invariant, Mehlman
Consulting, PricewaterhouseCoopers, S-3 Group, Duberstein Group, Williams & Jensen, and
others; ~$60K-120K each). The root cause turned out to be more specific than "inconsistent
spelling across filings": Business Roundtable's *own* self-filed row has `registrant.name` =
"THE BUSINESS ROUNDTABLE, INC." but `client.name` = "BUSINESS ROUNDTABLE INC" -- **not
identical even within its own single filing**, in any of the 5 years on file. Since
`flag_client_registrant_conflict()`'s self-lobbying detection requires those two fields to
match, and the original normalization only stripped punctuation/case (not words like
"The"/"Inc."), the check never fired for this entity at all, in any year. This has now been
fixed (`normalize_entity_name()` in `scripts/lobbyr_clean.R` -- strips a conservative,
whole-word legal-suffix list) and verified: all outside-firm Business Roundtable filings are
now correctly recognized as double-counting and removed, while the true self-filed row is
kept, and the several genuinely distinct regional/topical Business Roundtables (Gulf South, Ohio,
Colorado, Arizona, American Turkish, Small Business Roundtable) are correctly left untouched. This was never unique to Business Roundtable
-- re-running the fixed function against the full multi-year corpus (see the next section)
caught 13,269 additional double-counting rows corpus-wide that the original logic had
silently missed. Full root-cause trace and validation methodology in
`references/data_quality_notes.md` *[in this repo: `skills/lobbying-quarterly-filings/references/data_quality_notes.md`]*.

---

## Full-corpus lobbying trends, 2022-2026 (Q1)

**Data**: Every Senate quarterly filing on disk, all years and all 79 lobbying issue areas
(ALI codes) present in the corpus -- not a single-issue slice like the TAX section above. *[porter's note: refers to the original report's TAX-quarter section, which is not part of this submission; only its double-counting-trap subsection is reproduced above — see the provenance header]*
2022, 2023, 2024: full years. 2025: full year. **2026: Q1 only** (the most recent quarter on
disk as of this report) -- every 2026 figure below is a single-quarter number, never
compared to a full-year figure without saying so explicitly.

**Methodology**: Loaded per-year via `get_local_senate_filings(years = y, tidy_result =
FALSE)` for y in 2022:2026 (bounds `pivot_wider()` cardinality per year rather than one
5-year combined pivot), id-like columns coerced to `character` before `bind_rows()` (some
years encode `client.client_id` etc. as integer, others as character), then cleaned via the
same `flag_dupes()` + `flag_client_registrant_conflict()` pipeline as the TAX section.*[porter's note: same cleaning pipeline as reproduced in the trap subsection above]* **418,098
raw filings -> 303,820 after cleaning.** *[porter's note: these figures were computed under the pipeline's pre-2026-07-15 rule, which dropped ALL termination filings; per the team decision logged in DECISIONS.md (2026-07-15), termination-filing income now counts when it is the quarter's only record, so a re-run with the current pipeline yields slightly HIGHER totals — the figures here are conservative]* Filings/distinct clients by year: 2022 (67,805 /
17,847), 2023 (69,352 / 18,255), 2024 (71,136 / 18,630), 2025 (77,894 / 20,900), 2026 Q1-only
(17,633 / 16,461). Issue-level columns were identified by matching against the actual ALI
code lookup (`list_ali_codes()`), not a hand-maintained exclusion list -- an early version of
this analysis misclassified ~127 real metadata columns (`registrant_country`, `client.state`,
etc.) as "issues" by using too short an exclusion list; re-deriving from the real code list
caught it. "Amount" = `coalesce(expenses, income)` per filing, same convention as the TAX
section, with the same multi-issue-filing double-counting caveat (a filing touching 3 issues
counts its full dollar amount toward each of the 3).

**Updated from an earlier pass of this report** (which had 317,089 cleaned filings) after
fixing a real bug in `flag_client_registrant_conflict()`'s entity matching -- see the TAX
section's "double-counting trap" finding above and `references/data_quality_notes.md` *[in this repo: `skills/lobbying-quarterly-filings/references/data_quality_notes.md`]* for the
full root-cause trace. The fix catches **13,269 additional double-counting rows corpus-wide**
that the original punctuation/case-only name matching silently missed -- this was never
unique to Business Roundtable. All figures below reflect the corrected, 303,820-filing
cleaned set; the overall trends and rankings are essentially unchanged from the earlier pass
(same winners, same losers, dollar totals modestly smaller), which is itself a useful
sanity check that the bug was a real but bounded double-counting leak, not something that was
distorting the corpus's big-picture shape.

Every finding below was checked against the underlying raw filings before being written down
-- several numbers that looked like blockbuster findings turned out to be name-variant
artifacts or single-quarter outliers once traced back to source, and are flagged as such
rather than reported at face value.

### Which issue area grew the most, 2022 -> 2025 (full years)?

There's no single "most growth" answer -- it depends on whether a journalist means dollars or
lobbying-client breadth, and absolute or relative terms. All four framings:

| Framing | Winner | 2022 | 2025 | Change |
|---|---|---|---|---|
| Absolute $ growth | **Trade (domestic/foreign)** | $1,282.2M | $1,521.8M | **+$239.6M** (+18.7%) |
| Relative $ growth (min $250k base) | **Tariff (miscellaneous tariff bills)** | $65.6M | $206.5M | **+215%** |
| Absolute client growth | **Budget/Appropriations** | 4,557 clients | 5,549 clients | **+992 clients** (+21.8%) |
| Relative client growth | **Tariff (miscellaneous tariff bills)** | 127 clients | 362 clients | **+185%** |

Runners-up by absolute dollars: Taxation/Internal Revenue Code (+$214.9M, +10.0%),
Budget/Appropriations (+$198.8M, +12.5%), Energy/Nuclear (+$171.6M, +22.9%), Agriculture
(+$156.2M, +49.2%). Tariff shows up as the runaway winner on every *relative* measure --
consistent with a live, escalating trade-policy story rather than steady-state lobbying.

### Which issue area grew the least (or shrank), 2022 -> 2025?

| Framing | "Loser" | 2022 | 2025 | Change |
|---|---|---|---|---|
| Absolute $ decline | **Disaster Planning/Emergencies** | $267.3M | $131.1M | **-$136.1M** (-50.9%) |
| Relative $ decline (min $250k base) | **Unemployment** | $93.8M | $11.4M | **-87.8%** |
| Absolute client decline | **Transportation** | 1,882 clients | 1,748 clients | **-134 clients** (-7.1%) |
| Relative client decline | **Civil Rights/Civil Liberties** | 274 clients | 193 clients | **-29.6%** |

Disaster Planning/Emergencies and Unemployment both read as pandemic-era wind-down stories:
2022 was still close to COVID-era emergency-relief and expanded-unemployment-benefit
legislative activity, and by 2025 most of that had lapsed or been resolved, so the lobbying
spend around it largely evaporated. Civil Rights/Civil Liberties losing nearly 30% of its
distinct lobbying clients in three years is worth a follow-up call to some of the
organizations that dropped off the list -- this dataset shows *that* it happened, not *why*.

### Emerging industries: who showed up in the lobbying corps for the first time?

The 79 ALI issue-area codes are all long-established umbrella categories (Trade, Defense,
Energy, etc.) -- none of them are literally brand-new, so "emerging industries" shows up
much more clearly at the **client level**: real companies with **$0 in lobbying spend in
2022** that appear as real, meaningfully-sized lobbying clients by 2025.

**Generative AI arrived as a K Street client class that didn't meaningfully exist in 2022.**
Anthropic PBC ($0 -> $3.12M), OpenAI Opco, LLC ($0 -> $2.99M), and a16z Capital Management ($0
-> $3.48M) all first appear as lobbying clients in this window -- a concrete, dated marker of
when frontier AI labs and their investors started actively lobbying Congress.

**A parallel wave of foreign trade/critical-minerals/EV-supply-chain entrants**, plausibly
tariff- and industrial-policy-driven: Nippon Steel ($0 -> $3.42M -- during its high-profile
bid for U.S. Steel), Korea Zinc ($0 -> $2.53M), Hanwha Q Cells America (solar, $0 -> $3.10M),
Gotion Inc. (EV batteries, $0 -> $2.46M), and SK Americas ($0 -> $5.77M). None of these
companies is new to the world -- they're new to *this dataset*, meaning 2022 was the first
time each had no federally-disclosed U.S. lobbying presence and 2025 is the first time they
did. (Tencent America was in an earlier pass of this list, but doesn't belong there -- properly
name-normalized, it already had $800K in 2022 lobbying spend, growing to $4.04M by 2025; it's
a real grower, not a first-time entrant, and was dropped once that was caught.)

### Registrants and clients that upped their spending

**Important correction made during this analysis**: a naive name-based ranking initially
showed "Ballard Partners" appearing from $0 (2022) straight to $69.6M (2025) as a brand-new
registrant -- but tracing it back, "BALLARD PARTNERS, LLC" (2022-2024, 2026) and "BALLARD
PARTNERS" (2025 only, no "LLC" suffix) are the same real firm; it simply dropped the suffix
in its 2025 filings. This is a different problem from the Business Roundtable bug above (that
one was registrant-name-vs-client-name mismatch within a single filing; this one is one
registrant's own name drifting across years) -- but the same fix applies: the table below is
computed with `normalize_entity_name()` (the same helper `flag_client_registrant_conflict()`
now uses, applied here to roll up one registrant/client's totals across its own name history)
so this mistake isn't repeated.

**Top registrant increases, 2022 -> 2025 (name-normalized):**

| Registrant | 2022 | 2025 | Change |
|---|---|---|---|
| Ballard Partners | $15.70M | $68.07M | **+$52.37M** (+334%) |
| Miller Strategies | $4.98M | $28.32M | +$23.34M (+469%) |
| BGR Government Affairs | $27.42M | $49.91M | +$22.49M (+82%) |
| Continental Strategy | $0.31M | $20.84M | +$20.52M (+6,600%) |
| Mercury Public Affairs | $5.48M | $21.01M | +$15.53M (+283%) |
| Business Roundtable | $20.41M | $33.50M | +$13.09M (+64%) |
| Cornerstone Government Affairs | $25.28M | $37.82M | +$12.54M (+50%) |
| General Motors (self-filed) | $10.05M | $21.39M | +$11.34M (+113%) |

Both of the two most extreme movers were individually verified against raw filings, not just
trusted at face value: **Miller Strategies** grew from 44 distinct clients (2022) to 127
(2025) -- a genuinely broad, blue-chip roster (SpaceX, OpenAI, Oracle, Morgan Stanley, General
Motors, Charter Communications, Dow Chemical, SoftBank, several city governments) rather than
one large client inflating the total. **Continental Strategy**, up more than 60x, grew from
11 filings/handful of clients in 2022 to 318 filings in 2025 across a large, real, named
client list (American Association of Homecare, Applied Materials, Anthropic, American Sugar
Refineries, and dozens more) -- a genuine scale-up of a Florida/DC lobbying shop, not a
duplication artifact.

**Top client increases, 2022 -> 2025 (name-normalized):** Business Roundtable (+$13.09M,
+64%), General Motors (+$11.34M, +113%), PhRMA (+$9.61M, +34%), Meta Platforms (+$6.95M,
+36%), UnitedHealth Group (+$5.34M, +94%).

### Registrants and clients whose spending diminished

**Top registrant/client decreases, 2022 -> 2025:** SAP America (-$128.7M, -97%), National
Association of Realtors (-$27.4M, -34%), Alzheimer's Association (-$10.75M, -73%), Chamber of
Commerce of the USA (-$9.1M, -12%), Biotechnology Innovation Organization (-$7.66M, -58%).
(These five are unchanged by the cleaning fix -- none of them had a self-filed-report /
outside-firm double-counting relationship, so their totals were already correct.)

**A blockbuster-looking number that turned out to be a single-quarter outlier, caught by
hand.** SAP America's headline "$132.35M -> $3.62M, a 97% cut" does not reflect a real
spending pullback. Tracing the 2022 filings individually: SAP America self-filed $1.04M,
$610K, and $610K in three of 2022's four quarters -- completely in line with 2023-2025's
run rate -- but its **Q2 2022** filing alone reports **$130.09M** in expenses
(`filing_document_url` links directly to that filing). That one anomalous quarter, not a
genuine multi-year decline, is responsible for the entire "$128.7M drop." The real story, once
that outlier is set aside, is that SAP America's lobbying spend has been flat, not
collapsing -- exactly the kind of number a journalist should trace to source before citing,
which is why `filing_document_url` is in every fact-check table this project produces.

### The 2025 tax bill: what spiked, and has it tapered off in 2026?

Comparing each issue's **Q1 dollar total** across years isolates a same-quarter,
apples-to-apples comparison: baseline = average of Q1 2022/2023/2024, "spike" = Q1 2025 vs.
that baseline, "taper" = Q1 2026 vs. Q1 2025.

The core tax-and-budget cluster shows the expected shape -- a real but modest bump around the
reconciliation bill's passage, already easing off one quarter later:

| Issue | Q1 baseline (avg '22-'24) | Q1 2025 | Q1 2026 | Spike | Taper |
|---|---|---|---|---|---|
| Taxation/Internal Revenue Code | $528.7M | $620.0M | $567.7M | +17.3% | **-8.4%** |
| Agriculture | $91.8M | $119.9M | $113.7M | +30.6% | **-5.2%** |
| Law Enforcement/Crime/Criminal Justice | $72.2M | $95.1M | $87.0M | +31.6% | **-8.5%** |
| Railroads | $31.7M | $37.9M | $17.3M | +19.5% | **-54.5%** |

Railroads posted by far the sharpest snap-back -- Q1 2026 spend is less than half its Q1 2025
level and below its pre-2025 baseline, consistent with a issue that surged for one
bill-passage cycle and genuinely receded once it was resolved.

**But tariffs are the counter-example -- they did not taper, they kept climbing.** Tariff
(miscellaneous tariff bills) spiked +153% in Q1 2025 ($16.4M baseline -> $41.5M) and then
climbed *another* 37.2% in Q1 2026, to $57.0M -- the opposite of the "spike then recede"
pattern the tax bill produced. Apparel/Clothing Industry/Textiles is the one issue that
matches the full "spiked hard, then genuinely tapered" pattern almost exactly (+61.4% in Q1
2025, then -44.8% in Q1 2026) -- plausibly downstream of the same tariff fight, but resolved
faster and on a much smaller base ($1.5M baseline). The honest answer to "what spiked in 2025
and has now tapered off": **the tax-and-budget-adjacent issues did (Taxation, Agriculture, Law
Enforcement, Railroads most sharply), but trade/tariff issues have not** -- they're still an
active, escalating story a full year later, not a one-time bill-passage spike.

### Three more questions a journalist might ask

**Q: Is there a filing in this dataset that looks too big to be real?**
Yes -- worth a direct call before anyone cites it. **"STATE OF LOC NATION GLOBAL PUBLIC
BENEFIT CORPORATION"**, lobbied by registrant "LOC Community Association," reports exactly
**$20,000,000 in expenses in each of Q2, Q3, and Q4 2025** ($60M for the year) -- a
suspiciously round, suspiciously repeated figure from two obscure, hard-to-place entity names
that otherwise don't show up anywhere else in the corpus. That would place this single
client/registrant pair's 2025 spend on par with the Chamber of Commerce's entire annual
self-filed total. It may be entirely legitimate, but the combination of an exact repeated
round number and unfamiliar entity names is exactly the profile worth fact-checking against
the source filings (`filing_document_url`) before repeating the number in print.

**Q: Which single K Street firm's business grew the fastest, and is the growth durable or a
blip?** Continental Strategy, LLC (see above) -- 11 filings/small client roster in 2022 to
318 filings across dozens of named, verifiable clients in 2025, sustained (not reversed) into
2026 ($8.16M in Q1 2026 alone, on pace with a full 2025 of $20.8M). This reads as a real,
durable scale-up of one firm's book of business, not a one-quarter fluke.

**Q: Beyond AI, which entirely new client shows up lobbying on the most distinct issue areas
in its very first year in the data?** Worth a follow-up pull the next time this dataset is
refreshed -- this section focused on total-dollar new entrants; cross-referencing "new since
2022" clients against breadth-of-issue-area (the same lens the Business Roundtable/Altria
findings above used for the TAX-only slice *[porter's note: the Altria breadth finding lives in the original report's TAX section, not ported here]*) across the full 79-issue corpus is a natural
next step once a similar per-issue-per-client breadth table is built for all years, not just
one quarter.

---

# Verification block (finding-verifier protocol, 2026-07-14)

**Verdict: PASS — 8/8 claims verified.** Fresh agent, no drafting-session context, re-derived
each claim against `db/lda_full.duckdb` + raw corpus with 4 record spot-checks via
`show_record.py`. Full verdict table below; three hedges to carry when citing this finding:

1. **"First appearance" framing (AI clients):** Anthropic, OpenAI, and a16z all first appear
   as lobbying clients in **2023**, ramping to ~$3M-scale by 2025. Accurate framing: "absent
   in 2022, ramping from 2023" — not "first appears in 2025." (2025 self-filed totals verified
   to the dollar: Anthropic $3.12M exact, OpenAI $2.99M exact, a16z $3.53M vs claimed $3.48M.)
2. **Snapshot vintage (conservative bias):** the report's pipeline snapshot predates
   late-posted Q4-2025 filings. Current DB: Continental Strategy 2025 = **$26.0M / 349
   filings** (claim: $20.8M / 318 — reproduces exactly at a 2026-01-19/20 posting cutoff);
   Tariff FY2025 = **$218.9M** (claim: $206.5M). The claims *understate* both trends.
3. **LOC Nation field label:** the exact $20,000,000 per quarter (Q2/Q3/Q4 2025 — confirmed)
   sits in the **income** field (registrant fee), not `expenses`; the pipeline's
   `coalesce(expenses, income)` convention makes the amounts correct as stated.

Corroboration found beyond the claims: SAP America's anomalous Q2-2022 $130.09M filing
(`8753c1ce-20ee-403f-8fe5-de2264487a9a`) was **amended one day later to $640K**
(2A, posted 2022-07-21) — strong evidence of a data-entry error, supporting the report's
single-quarter-artifact reading.

| Claim | Verdict | Verifier numbers | Note |
|---|---|---|---|
| C1 Anthropic $0→$3.12M | verified | 2022: $0; 2025 self-filed $3.12M (exact) | first-appearance hedge (2023) |
| C2 OpenAI $0→$2.99M | verified | 2022: $0; 2025 self-filed $2.99M (exact) | first-appearance hedge (2023) |
| C3 a16z $0→$3.48M | verified | 2022: $0; 2025 self-filed $3.53M (Δ1.4%) | self-filed since 2023 |
| C4 Tariff surge, no taper | verified | FY22 $68.2M → FY25 $218.9M (+221%); Q1 avg $17.1M → $42.3M → $60.3M | Δ≤6%; 2026 climb confirmed |
| C5 SAP single-quarter artifact | verified | Q2-2022 raw $130.09M; 2025 $3.62M | next-day amendment to $640K strengthens |
| C6 Continental Strategy growth | verified | 2022 $0.40M/11 → 2025 $26.03M/349 | stale-snapshot caveat; claim understates |
| C7 LOC Nation $20M ×3 | verified | Q2=Q3=Q4 2025 exactly $20,000,000 | field is income, not expenses |
| C8 Business Roundtable name mismatch | verified | mismatch in 100% of self-filed filings, 2022–2026 | — |

Spot-checked records: `8753c1ce-20ee-403f-8fe5-de2264487a9a` (SAP Q2-2022),
`f77a4908-5b4f-41d6-a9c7-acc85dee6946` (LOC Nation Q4-2025),
`ba2fc44f-6b7a-42c0-abc8-a833ef824d69` (Anthropic Q3-2025),
`86980775-2940-4b00-a39d-c6624db22a0f` (Business Roundtable Q1-2022).

Lock decision: pending human sign-off in `DECISIONS.md` (per protocol step 6).
