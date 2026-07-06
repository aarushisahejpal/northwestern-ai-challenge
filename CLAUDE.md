# GAIN Agentic Investigation Challenge — workspace guide

Submission workspace for Northwestern's GAIN Agentic Investigation Challenge: an agentic
investigation of congressional lobbying filings (Senate + House LDA) and congressional press
releases, 2022–2026 Q1, asking who is paying whom to shape policy. **Deadline: 2026-07-15.**
README.md is the submission map (skills → findings → traces); this file is the working guide.

## Layout

```
gain-investigation/
├── README.md            ← submission map (six required elements; fill in as work happens)
├── CLAUDE.md            ← this file
├── LEDGER.md            ← investigation state: leads / entities checked / queries run / cold threads
├── DECISIONS.md         ← human-judgment log (required by the traces deliverable)
├── skills/              ← the submitted Agent Skills, each self-contained (SKILL.md + scripts/)
│   ├── lda-corpus-loader/     build_db.py (raw corpus → DuckDB) + show_record.py (citation → raw record)
│   ├── lda-entity-resolver/   cross-dataset entity table (Senate↔House crosswalk)
│   ├── investigation-ledger/  ledger templates + ledger_lint.py
│   ├── lead-scanner/          lens SQL library + scanning discipline
│   └── finding-verifier/      pre-lock claim re-derivation protocol
├── queries/             ← lens SQL (sweep_2026.sql + run_sweep.py); cited by aggregate claims
├── findings/            ← one locked finding per file (locked = verification passed)
├── traces/              ← session JSONL exports + INDEX.md + rendered/ HTML
├── tests/               ← smoke_test.py + fixtures/ (tiny excerpts of real public records)
├── data/                ← raw corpus (gitignored; layout per the challenge data manual)
└── db/                  ← built DuckDB files (gitignored; rebuilt from raw via loader)
```

## Commands (Windows dev box: `.venv/Scripts/python`; POSIX: `.venv/bin/python`)

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python tests/smoke_test.py                                  # green before anything else
.venv/Scripts/python skills/lda-corpus-loader/scripts/build_db.py \
    --data-root data/ --db db/lda.duckdb [--years 2025 2026] [--sample 2025-Q1]
.venv/Scripts/python skills/lda-corpus-loader/scripts/show_record.py <citation-key>
.venv/Scripts/python queries/run_sweep.py db/lda_2026.duckdb [BLOCK-PREFIX]
.venv/Scripts/python skills/investigation-ledger/scripts/ledger_lint.py LEDGER.md
```

Citation keys: Senate `filing_uuid` · House numeric XML filename (e.g. `301817772`) ·
press `src_file:src_line` (e.g. `congress_press/2026-01.jsonl:12`).

## Load-bearing conventions

- **Never cite the database.** Record-level claims cite citation keys resolvable via
  `show_record.py`. Aggregate claims (spikes, rankings, counts) cite three things: the exact SQL
  (a labeled block in `queries/`), the one-command DB rebuild, and ≥3 sampled underlying records.
- **Raw corpus access goes through `show_record.py` only.** Never grep or open raw corpus files
  directly — 409K XMLs will eat your context and your citations won't be reproducible.
- **Every DB row carries a raw-record pointer** (`src_file` + `src_line`/`src_index`, or XML
  path). If you add a table, preserve this invariant.
- **Ledger discipline (single-writer).** Read `LEDGER.md` at session start; commit updates at
  session end and on any status change. Sub-agents return candidate rows; only the orchestrating
  session writes. Statuses: `open → triaged → investigating → verified | dead`, plus `parked`
  (cold, with revisit trigger). Run `ledger_lint.py` after edits.
- **Named-actor rule.** A lead with no specific actor, date, and record ID cannot pass triage.
  "Spend on issue X spiked" is a dataset summary; name who, when, and which filings.
- **DECISIONS.md** gets a row for every human intervention (triage picks, kills, editorial and
  legal-flag calls) with the trace file it happened in.
- **Traces.** Every working session is exported to `traces/YYYY-MM-DD_<skill-or-phase>_<lead>.jsonl`
  (session JSONL lives under `~/.claude/projects/<project-slug>/`) and indexed in `traces/INDEX.md`.
- **Findings lock only after verification.** A fresh session (no drafting context) re-derives
  every claim from cited records per `skills/finding-verifier/SKILL.md`, then the lock is logged
  in `DECISIONS.md`. The findings report is assembled from locked findings only.
- **Model/budget tiers.** Extraction and filtering stay in Python/SQL. Cheap models scan and rank
  (returning record IDs + one-line hypotheses, never quoted record text). Frontier models
  deep-read lead-attached records (cap ~30 records/session) and verify findings.
- **Self-contained language.** Submitted artifacts (SKILL.md files, findings, README) must stand
  alone — no references to internal planning docs or prior processes.

## Data facts that bite (verified against real records 2026-07-04)

- House quarterly XML uses `<alis><ali_info>` with `<issueAreaCode>` — NOT the `ali_Code` flat
  list the data manual describes (that may still apply to LD-1 registrations; unverified).
- Agencies lobbied are one comma-separated `<federal_agencies>` string per ali_info; splitting
  it is entity-resolver work.
- House forms pad with empty `<lobbyist>` slots — skip rows with no first and no last name.
- Senate registrant objects carry `house_registrant_id` — the clean Senate↔House crosswalk key.
- Senate LD-203 contributions are semiannual; early-year files are legitimately tiny.
- **Never sum filings without deduping.** Registrants file duplicates (identical Senate Q1s
  posted 22 seconds apart) and amendments (Senate `filing_type` codes like `1A`; House refilings
  under new filing_ids). Any per-period aggregate keeps only the latest filing per
  registrant+client+period on both sides — see `queries/sweep_2026.sql#H1b` for the pattern.
  Verified 2026-07-04; the un-deduped version fabricated a "House reports 2× Senate" pattern.
- **Never sum senate + house datasets.** LD-2 quarterlies are filed with both chambers, so the
  two datasets are largely copies of the same filings. Dollar attribution is senate-primary
  (richer metadata); use house only to reconcile or fill gaps. Verified 2026-07-05 — the
  cross-dataset version (sweep#C1b) inflated per-bill totals ~40%.
- **House XML dumps are partial snapshots.** House 2026-Q1 holds 12,656 filings vs 21,145
  senate Q1s (the deadline-week flood is missing). Senate is the completeness reference for
  recent quarters; a filing absent house-side is expected noise, not a story.
- **Press and filings name bills differently.** Members write "the Farm Bill" / "NDAA"; filings
  cite H.R./S. numbers. Number-only matching fabricates "lobbied but publicly silent" bills
  (killed L004 that way). Say-vs-pay comparisons need alias matching or provision-level framing.
- **The Senate↔House join key is house `<senateID>` = `"<senate_registrant_id>-<senate_client_id>"`**
  (compound, engagement-level; verified 2026-07-06). Do NOT join senate `house_registrant_id`
  to house `<houseID>` — formats don't overlap (zero matches). Use `registrant_crosswalk`
  (entity-resolver) or the split_part pattern in `queries/sweep_2026.sql#H1c`.
- **`<houseID>` is NOT a resolvable filing_id/filename, and can collide with an unrelated
  one.** Verified 2026-07-06: a Mercury/PRVO Plinarsko Društvo quarterly filing carries
  `<houseID>301740622</houseID>`, but filing `301740622.xml` in this corpus is a completely
  different, unrelated registration (Cornerstone Government Affairs / National Association
  of Home Builders). `<houseID>` appears to be a persistent House-Clerk identifier for the
  registrant-client relationship (what the House disclosure portal's own search surfaces) —
  a different ID namespace from `filing_id` (the numeric filename), even though both are
  9-digit numbers that can coincidentally match an unrelated document. Never cite a
  `<houseID>` value as a `show_record.py` key; only the filename (`filing_id`) is a valid
  citation key on the House side.
- **Senate `client_id` is registrant-scoped, not global** — Comcast alone has 10+ client ids.
  Group clients by resolved entity (`entities`/`entity_aliases`, norm-key based), never by
  client_id. Registrant ids ARE global.
- Everything self-reported: strip whitespace everywhere, expect missing income/expenses, and
  treat gaps as potentially reportable rather than as noise.
- Windows: scripts force UTF-8 stdout (press text has curly quotes; pipes default to cp1252).

## Session discipline for Claude sessions in this repo

1. Start: read this file, `LEDGER.md`, and the tail of `DECISIONS.md`. Don't re-derive state.
2. Work one lead or one phase per session where practical (keeps traces reviewable).
3. End: update `LEDGER.md` (+ lint), log any human decisions, export the session trace, update
   `traces/INDEX.md`, commit.

Internal planning context (not part of the submission, not for citation in submitted artifacts):
`../_Plan.md` in the parent folder holds the phased plan and decision register.
