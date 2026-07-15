# Column spec (verbatim intent from the original request)

Five columns, added to the full original issue-area subset without altering, deleting, or
reordering any existing column or row:

1. **`activity_summary`** -- the specific lobbying mechanism/action in fewer than 10 words,
   built from the issue-area's free-text description + `client.general_description`. Not a
   generic phrase ("tax issues"); not an active verb ("seeks", "defends", "monitors") --
   straight to the concept/mechanism.
2. **`cluster_lobbying_activity_theme`** -- a narrow, mechanism-focused label answering "what
   issue is being targeted." Never "Other"/"General tax". Must be used by >=10 and <200 rows
   in the final data; merge under-sized candidates into the closest substantively similar
   label.
3. **`cluster_actor_theme`** -- "who is doing the lobbying and how are they represented":
   organization type + in-house vs. outside firm (`registrant.name == client.name` => in-house).
   Same >=10/<200 rule.
4. **`cluster`** -- a 4-6 word narrative title integrating the activity theme, actor pattern,
   and lobbying posture (offense/defense/monitoring, inferred from language cues). Same
   >=10/<200 rule.
5. **`cluster_reasoning`** -- 1-2 sentences explaining the row's placement, referencing at
   least two of: organization type, in-house vs. outside, posture, the specific legislative
   vehicle/mechanism named, what the client does.

No empty values allowed in any of the five columns.

## How `cluster` combines theme + actor + posture without breaking accuracy or cardinality

First attempt (wrong, caught by spot-checking real output, not assumed): derive one narrative
title per *theme*, using that theme's single most common actor pattern, applied to every row
in the theme. On the real 2026 Q1 TAX run this mislabeled 1,701 of 2,906 rows (58%) -- e.g. a
payments-company filing titled "Pharmaceutical/biotech company shaping Research credit..."
because pharma happened to be that theme's most common actor. Wrong is wrong regardless of
cardinality compliance.

Fixed design, in `build_cluster_and_reasoning.R`: for each theme, decide the finest grouping
that keeps every sub-bucket >=10 rows, using that row's *own* actor and posture, and apply
that same decision to every row in the theme (not a per-row cascade, which was tried and
also has a bug -- see the file's own comments for why a mixed per-row cascade leaves sparse
leftover buckets under 10):
1. `{actor} {posture verb} {theme}` if every (actor, posture) combination within that theme
   has >=10 rows,
2. else `Multiple actor types {posture verb} {theme}` if every posture within that theme has
   >=10 rows,
3. else the theme name alone (inherits the theme's own count, already >=10 by construction).

On the real run, level 1 never actually survives (the ~33-value actor vocabulary crossed with
3 postures is too fine-grained for any one theme's row count), but level 2 does for about a
third of rows -- so `cluster` ends up mostly at level 2/3, which is an honest reflection of
how much genuine actor-level texture this subset supports, not a design shortfall.

One more bug worth naming: the shortened theme name used inside `cluster` must stay 1:1 with
`cluster_lobbying_activity_theme` -- an earlier version stripped every parenthetical
qualifier for readability, which silently re-merged distinct final themes (all 14 "General
federal tax policy monitoring (X)" variants, and both Clean energy sub-themes) back into one
string each, right after the classifier had deliberately kept them separate. `shorten_theme()`
now only trims cosmetic wordiness, never a qualifier that carries real distinguishing content.

## Worked examples from the original request (for calibration)

Good `activity_summary` / `cluster_lobbying_activity_theme` specificity:
"Solar and wind energy production credits", "Carried interest preferential capital gains
treatment", "PPLI life insurance tax shelter rules", "Estate tax repeal for high-net-worth
estates", "Gold investment tax status parity", "Lower federal tobacco excise burden".

Good `cluster_actor_theme` examples: "Fortune 500 in-house team", "Tax-exempt client using
K-Street firm", "Industry trade association in-house", "Municipal government using firm",
"Sports betting company in-house team".

Good `cluster` narrative titles: "Private equity defending carried interest", "Hospitals
defending tax-exempt status", "Gold industry shaping tax rules", "Tobacco companies shaping
excise taxes", "Municipal governments seeking tax relief".
