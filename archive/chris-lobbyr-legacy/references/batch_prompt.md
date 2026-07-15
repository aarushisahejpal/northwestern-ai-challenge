# Phase A batch prompt template

Used to launch one subagent per ~200-row batch (model: Haiku). Substitute `{BATCH_CSV_PATH}`
and `{OUTPUT_JSONL_PATH}` per batch.

---

You are classifying rows of a CSV of federal lobbying disclosure filings, all tagged with
the issue area "Taxation/Internal Revenue Code". Read the input CSV at this exact path using
the Read tool:

`{BATCH_CSV_PATH}`

Each row has: row_id, registrant.name (who's lobbying), client.name (who's paying),
registrant.description, client.general_description (what the client does),
filing_type_display (e.g. "Registration" or a quarterly report type), and a column literally
named `processed_Taxation/Internal Revenue Code` (the free-text description of the specific
tax lobbying activity on that filing).

For EVERY row, produce five fields. These are DRAFT/CANDIDATE labels -- a later consolidation
pass will merge similar labels across all batches into a final controlled vocabulary, so
don't worry about matching other batches' exact wording, just be accurate and specific for
this row.

1. `activity_summary`: fewer than 10 words, mechanism-focused, no active verbs, no vague
   filler -- see the full rule text and examples in `column_spec.md`.
2. `candidate_theme`: narrow issue label, never "Other"/"General tax".
3. `candidate_actor`: organization type + in-house vs. outside firm.
4. `posture`: "offense" / "defense" / "monitoring".
5. `cluster_reasoning_draft`: 1-2 sentences referencing at least two of organization type,
   in-house/outside, posture, named mechanism, what the client does.

Process all rows in the batch. Write output as JSONL (one JSON object per line, keys:
row_id, activity_summary, candidate_theme, candidate_actor, posture,
cluster_reasoning_draft) to this exact path using the Write tool:

`{OUTPUT_JSONL_PATH}`

**IMPORTANT**, learned the hard way from real batch failures:
- Every JSON object must be on its OWN line -- never write `}{` (concatenated objects, no
  newline).
- Write `row_id` as the same type consistently (prefer a JSON string, `"row_id": "42"`) --
  some batches wrote it as a bare number, which silently breaks a string-keyed join
  downstream.
- Use the exact key name `candidate_theme` (one batch typo'd `candidate_team`).
- Every row_id from the input must appear exactly once in the output, in order, with no
  empty fields.
- After writing, verify the file exists and has the expected line count (e.g. via `wc -l` or
  reading it back) before reporting success -- don't just claim success from having called
  Write once. One batch in the original run reported success but the file didn't exist at
  all; another reported success with a line silently missing a record.
