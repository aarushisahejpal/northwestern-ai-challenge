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
│   ├── lda-corpus-loader/     [build] raw corpus → DuckDB + show_record.py (citation → raw record)
│   ├── lda-entity-resolver/   [build] adds entity tables + v_client_canonical_spend to the DB
│   ├── lead-scanner/          [investigate] lens SQL + bill/giving/industry/FEC/turnover tools → leads
│   ├── finding-verifier/      [investigate] pre-lock claim re-derivation protocol
│   ├── source-document-reader/ [investigate] external primary-source PDF → page-anchored citable text
│   ├── outside-context-scan/  [investigate] exploratory novelty / contemporaneous web research
│   ├── investigation-ledger/  [any]  leads/decisions state; read at session start, commit at end
│   ├── dataset-primer/        [any]  orient on a NEW dataset before building against it → reference/ brief
│   └── industry-review-packager/ [investigate] spec-driven generate/regenerate of an industry review
│                              package (CSVs + dashboard + README + zip); also hosts the shared viz/
│                              templates every dashboard build reads
├── reference/           ← dataset orientation briefs (produced by dataset-primer; working aid, not a submission artifact)
├── queries/             ← lens SQL + internal design notes (see "Query library & derived tables"); cited by aggregate claims
├── findings/            ← one locked finding per file (locked = verification passed)
├── traces/              ← session JSONL exports + INDEX.md + rendered/ HTML
├── tests/               ← smoke_test.py + fixtures/ (tiny excerpts of real public records)
├── out/                 ← tool outputs: rosters, review packages, API caches — COMMITTED
│                          as of 2026-07-11 (Rob; reversal of the 4cae303 gitignored-out/
│                          convention). Exception: out/.fec_api_key stays ignored forever.
├── data/                ← raw corpus (gitignored; layout per the challenge data manual)
└── db/                  ← built DuckDB files (gitignored; rebuilt from raw via loader)
```

## Skills — build the corpus, then investigate it

Skills fall in two phases. The **`lda-*` prefix marks the build layer** — the only skills that MODIFY
the DuckDB; everything else is read-only over it. (Script filenames carry the same signal: `lda_*`
needs the built DB, `fec_*` needs the external openFEC API, untokened scripts are corpus-agnostic.)

**Build the corpus** (run in order; re-run after a corpus rebuild):
1. `lda-corpus-loader` — parse raw JSON/XML/JSONL → DuckDB; `show_record.py` resolves any citation key
   back to its raw record. In-place table adds: `backfill_press_issues.py`, `add_lobbying_freetext.py`.
2. `lda-entity-resolver` — add `entities` / `entity_aliases` / `registrant_crosswalk` +
   `v_client_canonical_spend`; its P6 member layer (`build_members.py`) adds `members_all` /
   `member_terms` / `member_committees` from external sources (congress-legislators + FEC
   committee files), and `member_resolve.py` is the shared person/committee resolver the
   giving map's member rollup imports.
   - Then `lead-scanner`'s `lda_industry_map.py --build-tags` writes the `lobbying_issue_mentions`
     serving table — a research-driven enrichment, so it runs here, after the two above.

**Investigate the corpus** (read-only over the DB + outside sources; run anytime after the build):
- `lead-scanner` — SQL-first lens library + bill cross-check / giving map / industry map / FEC
  enrichment / quarterly turnover tracker → candidate leads.
- `finding-verifier` — independently re-derive every claim before a finding locks.
- `outside-context-scan` — exploratory web research (novelty / contemporaneous), never a verifier.
- `source-document-reader` — turn an external primary-source PDF into page-anchored, citable text.
- `industry-review-packager` — one command per industry spec → the full review package (data CSVs +
  dashboard + README skeleton + zip), reconciliation mismatches failing the build; regenerate after
  a corpus refresh. Facet packages need `lda_industry_map.py --build-tags` first.

**Cross-cutting** (either phase): `investigation-ledger` (leads/decisions state — read at session
start, commit at end) and `dataset-primer` (orient on a NEW external dataset before building against
it → a `reference/` brief).

The build layer's binding to *this* corpus is `reference/corpus-profile.md`.

## Commands (Windows dev box: `.venv/Scripts/python`; POSIX: `.venv/bin/python`)

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python tests/smoke_test.py                                  # green before anything else
.venv/Scripts/python skills/lda-corpus-loader/scripts/build_db.py \
    --data-root data/ --db db/lda.duckdb [--years 2025 2026] [--sample 2025-Q1]
.venv/Scripts/python skills/lda-corpus-loader/scripts/show_record.py <citation-key>
.venv/Scripts/python skills/lda-entity-resolver/scripts/resolve_entities.py --db db/lda_full.duckdb  # entities/aliases/crosswalk (+ --report)
.venv/Scripts/python skills/lda-entity-resolver/scripts/build_members.py --db db/lda_full.duckdb  # members_all/member_terms/member_committees (P6; external sources, cached to out/)
.venv/Scripts/python skills/lda-entity-resolver/scripts/member_resolve.py "Emmer for Congress"  # resolve a filed person/committee string (+ --date --json)
.venv/Scripts/python skills/lda-corpus-loader/scripts/backfill_press_issues.py --db db/lda_full.duckdb  # (re)build press_issue_mentions in place
.venv/Scripts/python skills/lda-corpus-loader/scripts/add_lobbying_freetext.py --db db/lda_full.duckdb  # build lobbying_freetext + FTS in place
.venv/Scripts/python skills/lda-corpus-loader/scripts/embed_corpus.py --db db/lda_full.duckdb  # build the semantic layer in place (optional deps: pip install -r requirements-embed.txt)
.venv/Scripts/python skills/lead-scanner/scripts/lda_semantic_search.py --query "..." [--compare-bm25] [--like <key>]  # semantic discovery search
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py --build-tags  # (re)build lobbying_issue_mentions from industry_lexicon.json
.venv/Scripts/python skills/lead-scanner/scripts/lda_turnover.py [2025Q4]  # quarterly turnover beat: terminations/hires/swaps/in-house (+ --json)
.venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb [BLOCK-PREFIX]
.venv/Scripts/python skills/investigation-ledger/scripts/ledger_lint.py LEDGER.md
```

Citation keys: Senate `filing_uuid` · House numeric XML filename (e.g. `301817772`) ·
press `src_file:src_line` (e.g. `congress_press/2026-01.jsonl:12`) — all stable identifiers
from the source systems, valid regardless of which DB below they were queried through.

**Corpus versions** (all built the same way, differing only by `--years`; see
`skills/lda-corpus-loader/scripts/build_db.py`):
- `db/lda_full.duckdb` — 2022–2026, all years. **Canonical/primary as of 2026-07-06.**
  Start new investigative work here. Prebuilt copy (semantic layer included, so no
  local build or embedding run needed):
  https://dhrumil-public.s3.us-west-2.amazonaws.com/gain-investigation/lda_full.duckdb
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
  produced **L026–L027**.
- `p3_turnover.sql` (`P3a`–`P3e`) — the citeable form of the quarterly turnover tracker
  (`lda_turnover.py`): declared-termination trend, terminations/new engagements/swaps/in-house
  moves/firm churn for a target quarter.
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
- `lobbying_freetext` (+ FTS index) — Senate activity descriptions + House `specific_issues` unioned
  into one BM25-searchable doc surface, each row keeping a `show_record.py` `record_key`. The
  loader-owned, vocabulary-free **search/discovery** layer (P4); built in `build_db.py`'s index step,
  rebuilt in place by `add_lobbying_freetext.py`. FTS uses `stemmer='none'` and is discovery-only.
- `lobbying_issue_mentions` — lobbying free-text tagged to **industry facets** (e.g. `CRYPTO`) via the
  curated `skills/lead-scanner/scripts/industry_lexicon.json`; the deterministic, cited **serving**
  table (mirror of `press_issue_mentions`, on the lobbying side). Built by `lda_industry_map.py --build-tags`;
  feeds the entity-resolved industry player list (P4). Discovery (FTS/keyness) proposes vocabulary;
  only curated keywords tag.
- `lobbying_text_embeddings` (+ `lobbying_text_map`) — the **semantic** discovery surface: one vector
  per distinct `lobbying_freetext` text (388K), model name stamped per row (2026-07-14 build:
  `nomic-ai/nomic-embed-text-v1.5`), map table preserving the raw-record pointers. Built in place by
  `embed_corpus.py`; queried by `lead-scanner`'s `lda_semantic_search.py` (`--query`/`--like`/
  `--compare-bm25`). Discovery-only, same posture as FTS — catches synonyms/paraphrase BM25 can't;
  never cited by findings.

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
- **Exploratory outside-data checks follow a fixed protocol in two modes, separate from
  finding-verifier's rigor** — a *live scan* (novelty + news-landscape, recency welcome,
  no date gate) and a *contemporaneous scan* (what the record looked like at a past event,
  enforced via GDELT DOC 2.0 + WebSearch date operators), picked by which question the
  lead asks. Run as separate bounded passes (~3 queries each), distilled to a conclusion
  before it reaches the ledger. Full protocol in `skills/outside-context-scan/SKILL.md`.
  The mode fork was added 2026-07-07 after a SECURE-2.0 salience read pulled present-day
  retrospectives instead of Dec-2022 coverage; it generalizes the earlier 2026-07-06 fix
  (searching "GlobalFoundries news 2026" for a 2024 event). Kept out of
  `skills/finding-verifier/SKILL.md` since "verifier" implies a rigor this exploratory
  research doesn't have and shouldn't claim.
- **Onboarding an unfamiliar dataset follows `skills/dataset-primer`.** Before building against a
  data source you haven't vetted (FEC, court, CMS, a state portal), run its five-axis scan against
  the nine-category data-quality checklist and write a task-tailored brief to `reference/`. Check
  `reference/` for an existing brief first and refresh it rather than re-researching. The brief's
  traps are hypotheses to test against a real sample, not facts to trust — same bounded,
  non-verification posture as `outside-context-scan`. Seed example: `reference/fec-campaign-finance.md`
  (the FEC brief behind `skills/lead-scanner/scripts/fec_enrich.py`, L031).
- **Self-contained language.** Submitted artifacts (SKILL.md files, findings, README) must stand
  alone — no references to internal planning docs or prior processes.

## Data facts that bite

**Single source of truth: [`reference/corpus-profile.md`](reference/corpus-profile.md)** — the corpus
binding layer (sources & roles, citation keys, dedup key, mirror-source rules, entity join keys, and
every verified gotcha with its date). Read it before writing a query or adding a table; update a corpus
fact there, not here. The traps that have actually cost us a fabricated pattern, one line each (full
fact + why + verification date in the profile):

- **Never sum the two chambers** — the same quarterly is filed with both, so summing double-counts;
  senate is primary, house is reconcile/fill-gap only (cross-dataset sums inflated per-bill ~40%).
  Profile §1, §3.
- **Never sum filings without deduping on `filing_period` — not the type code.** A `filing_type`
  filter silently drops amendments and fabricated a cross-chamber "mis-reporter" pattern twice.
  Profile §3; pattern in `queries/sweep_2026.sql#H1c`.
- **`<houseID>` is NOT a citation key** — a different id namespace from `filing_id`, and can
  numerically collide with an unrelated document. Only the XML filename is a valid House key. Profile §2.
- **`client_id` is registrant-scoped, not global** (Comcast has 10+) — group clients by resolved
  entity, never by `client_id`; registrant ids ARE global. Profile §4.
- **Press and filings name bills differently** — number-only matching fabricates "lobbied but
  publicly silent" bills (killed L004). Bridge via `bill_aliases.json`. Profile §8.

Everything is self-reported: strip whitespace, expect missing income/expenses, treat gaps as
potentially reportable. Windows: scripts force UTF-8 stdout. (Profile §8.)

## Session discipline for Claude sessions in this repo

1. Start: read this file, `LEDGER.md`, and the tail of `DECISIONS.md`. Don't re-derive state.
2. Work one lead or one phase per session where practical (keeps traces reviewable).
3. End: update `LEDGER.md` (+ lint), log any human decisions, export the session trace, update
   `traces/INDEX.md`, commit.

Internal planning context (not part of the submission, not for citation in submitted artifacts):
`../_Plan.md` in the parent folder holds the phased plan, decision register, and (§9, added
2026-07-06) the story-bucket-driven tool roadmap with the P1–P7 priorities.

**Branch state (2026-07-06):** `main` is the single source of truth. The press-issue-coupling work
(`queries/press_issue_coupling.sql`/`.md`, `skills/lda-corpus-loader/scripts/backfill_press_issues.py`,
`queries/corpus_additions_roadmap.md`, leads L026–L027) and the `source-document-reader` skill split
were both merged into `main` on 2026-07-06. New roadmap work (P1/P2 per `_Plan.md` §9) branches off
`main`.

**2026-07-06 reset:** `LEDGER.md`/`DECISIONS.md` were emptied and the prior pilot-scale content
moved to `archive/*_pilot-triage_2026-07-06.md`, so a session working the newly-built full corpus
(`db/lda_full.duckdb`) starts with a clean, unbiased view rather than inheriting pilot-era lead
framing. This was a deliberate one-time QA reset, not a standing practice — don't repeat it on a
future corpus rebuild without being asked. The archived files are historical reference only; do
not read them into context unless specifically asked to reconcile or restore something from them
(e.g. `findings/L010_pipe_materials_war.md` is untouched and still a real, independently-verified
finding regardless of this reset — it just isn't re-listed as a lead in the fresh ledger).
