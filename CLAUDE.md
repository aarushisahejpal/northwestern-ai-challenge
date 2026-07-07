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
├── archive/             ← reset snapshots of LEDGER.md/DECISIONS.md (see note below); not submitted
├── skills/              ← the submitted Agent Skills, each self-contained (SKILL.md + scripts/)
│   ├── lda-corpus-loader/     build_db.py (raw corpus → DuckDB) + show_record.py (citation → raw record)
│   ├── lda-entity-resolver/   cross-dataset entity table (Senate↔House crosswalk)
│   ├── investigation-ledger/  ledger templates + ledger_lint.py
│   ├── lead-scanner/          lens SQL library + scanning discipline
│   ├── finding-verifier/      pre-lock claim re-derivation protocol
│   └── outside-context-scan/  exploratory novelty/news-landscape research (not verification)
├── queries/             ← lens SQL + internal design notes (see "Query library & derived tables"); cited by aggregate claims
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
.venv/Scripts/python skills/lda-entity-resolver/scripts/resolve_entities.py --db db/lda_full.duckdb  # entities/aliases/crosswalk (+ --report)
.venv/Scripts/python skills/lda-corpus-loader/scripts/backfill_press_issues.py --db db/lda_full.duckdb  # (re)build press_issue_mentions in place
.venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb [BLOCK-PREFIX]
.venv/Scripts/python skills/investigation-ledger/scripts/ledger_lint.py LEDGER.md
```

Citation keys: Senate `filing_uuid` · House numeric XML filename (e.g. `301817772`) ·
press `src_file:src_line` (e.g. `congress_press/2026-01.jsonl:12`) — all stable identifiers
from the source systems, valid regardless of which DB below they were queried through.

**Corpus versions** (all built the same way, differing only by `--years`; see
`skills/lda-corpus-loader/scripts/build_db.py`):
- `db/lda_full.duckdb` — 2022–2026, all years. **Canonical/primary as of 2026-07-06.**
  Start new investigative work here.
- `db/lda_pilot.duckdb` — 2025 + 2026-Q1 only. Kept solely to reproduce
  `findings/L010_pipe_materials_war.md`'s citations exactly as verified; not for new work.
- `db/lda_2026.duckdb` — 2026-Q1 only. Superseded by both of the above; safe to delete
  locally, nothing cites it that the other two can't also resolve.

## Query library & derived tables

`queries/` holds the lens SQL (cited by aggregate claims) plus internal design notes:
- `sweep_2026.sql` (+ `run_sweep.py`) — the point-in-time full-corpus sweep (say-vs-pay H-blocks,
  contribution flows, gaps S5); `#H1c` is the canonical `filing_period`-deduped cross-chamber pattern.
- `emergence_and_flows.sql` — **current primary generation lens** (rate-of-change / emergence /
  fan-out / individual-as-client / LD-203 flows); produced leads **L020–L025**.
- `press_issue_coupling.sql` (+ `.md`) — press issue-frequency & lobbying–messaging share-coupling;
  produced **L026–L027**. **Lives on `feature/press-issue-frequency` only — see Branch state below.**
- `l003/l004/l006/l010_*.sql` — per-lead deep-dive SQL, kept for reproducibility.
- `corpus_additions_roadmap.md` — design notes for not-yet-built extensions (FTS/keyness term
  discovery, Congress.gov bill-status & FEC joins, NER entity graph). **Internal; not a submission
  artifact, not cited by any finding.**

Key derived tables the loader materializes (both carry raw-record pointers; both resolvable via
`show_record.py`):
- `bill_mentions` — bill numbers (`H.R. 1234` / `S. 567`) regexed from House `specific_issues`,
  Senate activity descriptions, AND press text — the highest-precision cross-dataset join key.
- `press_issue_mentions` — press releases tagged to ALI issue codes via the curated `ISSUE_KEYWORDS`
  dict in `build_db.py` (rebuilt in place by `backfill_press_issues.py`); ~80% of releases carry ≥1 tag.

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
- **Exploratory outside-data checks (novelty/news-landscape) follow a fixed protocol,
  separate from finding-verifier's rigor** — anchor the search window to the actual event
  date (not "today"), run novelty and landscape checks as separate bounded passes (~3
  queries each), distill to a conclusion before it reaches the ledger. Full protocol in
  `skills/outside-context-scan/SKILL.md`. Established 2026-07-06 after searching
  "GlobalFoundries news 2026" for a 2024 event; deliberately kept out of
  `skills/finding-verifier/SKILL.md` since "verifier" implies a rigor this exploratory
  research doesn't have and shouldn't claim.
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
- **Never sum filings without deduping — and the dedup key must be the period-invariant
  field, not the type code, applied identically on both chambers.** Registrants file
  duplicates (identical Senate Q1s posted 22 seconds apart) and amendments (Senate
  `filing_type` codes like `1A`/`2A`/`3A`/`4A`; House refilings under new filing_ids).
  Filtering senate to `filing_type LIKE 'Q%'` SILENTLY DROPS amendments — this bit twice:
  2026-07-04's un-deduped version fabricated a "House reports 2× Senate" pattern, and
  2026-07-06's H1c/H1d v1 (which filtered/partitioned by `filing_type`) fabricated a
  "chronic 10x cross-chamber mis-reporter" pattern that was actually senate's
  PRE-amendment figure vs house's POST-amendment figure (house wasn't affected because its
  directory-based period bucketing already folds originals+amendments together). Caught
  by a human cross-checking the live House portal, not by any internal check — a reminder
  that "the query ran and produced clean-looking numbers" is not verification. The correct
  pattern: dedup keyed on `filing_period` (constant across original+amendment, e.g.
  "second_quarter" for both `Q2` and `2A`), NOT `filing_type`, picking latest by `posted`/
  `filing_id` — see `queries/sweep_2026.sql#H1c` (current, fixed version) for the pattern.
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
`../_Plan.md` in the parent folder holds the phased plan, decision register, and (§9, added
2026-07-06) the story-bucket-driven tool roadmap with the P1–P7 priorities.

**Branch state (2026-07-06):** `main` holds the corpus loader, entity resolver, emergence lenses,
and leads L020–L025. The **press-issue-coupling work is on `feature/press-issue-frequency`, not yet
merged** — that branch adds `queries/press_issue_coupling.sql`/`.md`,
`skills/lda-corpus-loader/scripts/backfill_press_issues.py`, `queries/corpus_additions_roadmap.md`,
and leads L026–L027. If you're not on that branch those files/leads won't be present; decide the
merge before Phase 5 packaging so the submission is assembled from one tree.

**2026-07-06 reset:** `LEDGER.md`/`DECISIONS.md` were emptied and the prior pilot-scale content
moved to `archive/*_pilot-triage_2026-07-06.md`, so a session working the newly-built full corpus
(`db/lda_full.duckdb`) starts with a clean, unbiased view rather than inheriting pilot-era lead
framing. This was a deliberate one-time QA reset, not a standing practice — don't repeat it on a
future corpus rebuild without being asked. The archived files are historical reference only; do
not read them into context unless specifically asked to reconcile or restore something from them
(e.g. `findings/L010_pipe_materials_war.md` is untouched and still a real, independently-verified
finding regardless of this reset — it just isn't re-listed as a lead in the fresh ledger).
