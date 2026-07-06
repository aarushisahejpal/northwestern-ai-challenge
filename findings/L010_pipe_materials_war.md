# Finding: The pipe-materials war — DIPRA's Q1 2026 spending spike

**Status:** draft, pending independent verification (finding-verifier not yet run)
**Lead:** L010 (descends from L004)
**Legal flag:** none
**Date drafted:** 2026-07-05

## Headline

In Q1 2026, the Ductile Iron Pipe Research Association (DIPRA) — joined by member
company McWane Inc. — nearly doubled its own recent-quarter lobbying spend to push
"materials provisions" and "domestic sourcing" language favoring iron pipe into five
separate FY26 appropriations bills, a TSCA reauthorization, and the NDAA, deploying
former U.S. Representative Martha Roby as a named lobbyist. The iron side outspent its
entire visible plastic/copper-pipe opposition roughly 2.7-to-1 that quarter, while the
only public trace of the fight is an unrelated press release that happens to describe
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

**C2 — The spike is DIPRA-specific, not industry-wide.** McWane Inc., a DIPRA member,
shows no comparable increase in the same quarter: Balch & Bingham LLP billed McWane a
flat $90,000 every single quarter from Q1 2025 through Q1 2026 with zero variance; The
Wessel Group Incorporated billed $40K/$50K/$50K/$40K in 2025 and $50K in Q1 2026 (normal
quarter-to-quarter noise, no spike).
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

**C5 — The iron side outspent its visible opposition ~2.7x in the same quarter.**
Iron side: DIPRA $540,000 + McWane $140,000 (Balch $90K + Wessel $50K) = $680,000.
Opposition, same quarter: Diamond Plastic Corp $20,000 (Water Strategies), Hobas Pipe USA
$20,000 (Water Strategies), Copper Development Association $110,000 (Kinghorn, Hilbert &
Associates), Plastics Industry Association $20,000 (Venture Government Strategies) +
$40,000 (ACG Advocacy) + $40,000 (The Vogel Group) = $250,000 total (one additional
Plastics Industry Association self-filed registration disclosed no income and is
excluded from the total). $680,000 / $250,000 ≈ 2.7x.
- Citations: `fa4e3cf3-c8dd-48ba-a2ff-dd9054a09aa9` (Diamond Plastic, $20K),
  `a8b88b9d-c07a-456f-87cf-a31af4e9511a` (Hobas, $20K),
  `a5ed3b1c-3236-4550-809a-317bea5dc533` (Copper Development, $110K),
  `8b821804-9d30-4223-9dba-e307dbe6fcc8` (Plastics Industry/Venture, $20K),
  `c7c2091b-75cc-434f-865d-840062444a89` (Plastics Industry/ACG, $40K),
  `590f0248-3492-47aa-b0b3-29f08f2f18e6` (Plastics Industry/Vogel, $40K).
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

## Verification

_Pending — to be run per `skills/finding-verifier/SKILL.md` by a fresh session/agent
with no drafting-context access, then logged in `DECISIONS.md` on pass._
