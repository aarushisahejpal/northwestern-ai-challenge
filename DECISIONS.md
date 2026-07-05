# Decision Log — human-judgment moments

Required by the brief: interaction traces must show "the moments where human judgment intervened."
Every human intervention — triage selections, lead kills, editorial calls, legal-flag decisions,
scope changes — gets a row. Referenced from README §3 and from each finding's verification block.

| date | decision | rationale | who | trace file |
|---|---|---|---|---|
| 2026-07-04 | Deadline confirmed: 2026-07-15. Timeboxes set in `_Plan.md` §7. | From registration materials. | Rob | pre-repo (plan session) |
| 2026-07-04 | Pilot corpus = 2025 full year + 2026-Q1, all three datasets. Full-corpus extension only where verified leads need history. | Time slices align with the on-disk partitioning (zero filtering code); ~25% of corpus; 5 quarters supports temporal lenses; manual publishes 2025 ground-truth counts for sanity checks. | Rob + Claude | pre-repo (plan session) |
| 2026-07-04 | Scoring assumed on the overall submission + findings, not per skill. | Team judgment call; five-skill structure retained without merge pressure. | Rob | pre-repo (plan session) |
| 2026-07-04 | Repo layout adopted (this repo); layout choice delegated to Claude. | Skills self-contained under `skills/` per Agent Skills spec to avoid a repackaging step at deadline. | Rob → Claude | pre-repo (plan session) |
| 2026-07-04 | Manual-coverage audit (prompted by Rob): `bill_mentions` table added to Layer 1; anomaly lens widened to cover press-side baselines/language shifts; comparative-messaging event clustering parked with revisit condition. | Every data-manual starting point now has a named home in the plan or an explicit parking rationale. | Rob + Claude | pre-repo (plan session) |
