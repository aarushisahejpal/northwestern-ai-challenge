# GAIN Agentic Investigation Challenge — Submission

> **Status: SKELETON.** This README is the submission map required by the challenge. Sections below
> match the six required elements verbatim; they are filled in as the work happens, not reconstructed
> at the deadline.

## What this is

An agentic investigation of congressional lobbying filings (Senate + House LDA) and congressional
press releases, 2022–2026 Q1, asking who is paying whom to shape policy. Built as re-runnable Agent
Skills plus verified findings.

## Quick start (evaluators)

```bash
pip install -r requirements.txt
python skills/lda-corpus-loader/scripts/build_db.py --data-root data/ --sample 2025-Q1   # smoke mode
python skills/lda-corpus-loader/scripts/show_record.py <citation-key>                    # view any cited record
```

Data layout under `data/` follows the challenge's data manual (`congress_press/`, `senate/`, `house/`).

## 1. Included skills

| Skill | What it does | How to run |
|---|---|---|
| `skills/lda-corpus-loader/` | Parses all three raw datasets into a queryable DB; every row keeps a raw-record pointer; includes `show_record.py` | `python skills/lda-corpus-loader/scripts/build_db.py --data-root data/ --db db/lda.duckdb [--years YYYY ...]` |
| `skills/lda-entity-resolver/` | Cross-dataset entity table + alias map (Senate↔House crosswalk); resolves the `<senateID>` compound key, groups clients by normalized name (Senate `client_id` is registrant-scoped, not global) | `python skills/lda-entity-resolver/scripts/resolve_entities.py --db db/lda.duckdb [--report]` |
| `skills/investigation-ledger/` | Lead/entity/thread tracking templates + schema lint | `python skills/investigation-ledger/scripts/ledger_lint.py LEDGER.md` |
| `skills/lead-scanner/` | (1) Lens library: SQL-first anomaly scans that emit candidate leads. (2) Bill cross-check: a bill number **or** named alias → every Senate/House filing + press release touching it. (3) LD-203 giving map: an entity/roster → its disclosed political giving. (4) Industry map: an industry hidden in the lobbying free-text → an entity-resolved player roster. (5) FEC enrichment: that roster → its Super-PAC contributions (openFEC), reconciled against LD-203 (the money LD-203 can't see) | Lenses: `python queries/run_sweep.py db/lda.duckdb [BLOCK-PREFIX] [queries/<file>.sql]`. Bill: `python skills/lead-scanner/scripts/lda_bill_lookup.py "Inflation Reduction Act"`. Giving: `lda_ld203_giving.py --names-file <roster>`. Industry: `lda_industry_map.py crypto`. FEC: `fec_enrich.py --names-file out/crypto_roster.txt` (needs `DATA_GOV_API_KEY`) |
| `skills/finding-verifier/` | Fresh-agent re-derivation of every claim in a finding before it locks | Protocol in `SKILL.md`, not yet automated end-to-end; delegates outside-source PDFs to `skills/source-document-reader` |
| `skills/source-document-reader/` | Turns an external primary-source PDF (court filing, SEC complaint) into page-anchored, citable text via render-to-image OCR that survives broken e-filing fonts; defines the external-document citation convention | `python skills/source-document-reader/scripts/ocr_pdf.py --pdf data/DOC.pdf --out data/DOC.ocr.txt [--grep TERM] [--dpi 300]` (needs the Tesseract engine — see `SKILL.md`) |
| `skills/outside-context-scan/` | Exploratory web research (novelty/prior-art + news-landscape checks) to triage a lead before drafting — distinct from finding-verifier's claim-locking rigor | Protocol in `SKILL.md`; uses WebSearch/WebFetch directly, no custom script |
| `skills/dataset-primer/` | Orients on an unfamiliar dataset before building against it: a bounded five-axis web scan (authoritative docs, tribal-knowledge gotchas, tooling, derived datasets, access mechanics) against a fixed nine-category data-quality checklist → a tiered, task-tailored reference brief cached in `reference/`. General-purpose research aid; sibling to outside-context-scan | Protocol in `SKILL.md`; uses WebSearch/WebFetch directly, no custom script. Example output: `reference/fec-campaign-finance.md` |
| `skills/lobbying-quarterly-filings/` | R port of the [lobbyR](https://github.com/Lobbying-DisclosuRe/lobbyr) package running entirely against the local `data/senate/` corpus (no API key, no network): loads Senate quarterly filings with keyword/client/registrant/period/amount filters, then `flag_dupes()` and `flag_client_registrant_conflict()` remove double-counting before any spend totals; top-spenders-over-time and by-ALI-issue-code rollups; Shiny explorer at repo root (`dashboard_app.R`) | In R: `source("skills/lobbying-quarterly-filings/scripts/local_senate_filings.R"); source(".../lobbyr_clean.R")` then `get_local_senate_filings(years = 2022:2026, issues = "...")` piped through `flag_dupes()` and `flag_client_registrant_conflict()`. Dashboard: `shiny::runApp("dashboard_app.R")` from repo root. See its `SKILL.md` |

**How the pieces fit together.** One corpus, three complementary layers: the DuckDB
pipeline (`lda-corpus-loader` → `lda-entity-resolver` → `lead-scanner`) is the canonical
citation-first path from raw filings to leads; the semantic layer (`embed_corpus.py` /
`lda_semantic_search.py`) is a discovery surface that proposes vocabulary for the audited
lexicon, never a citation source; and `lobbying-quarterly-filings` is an independent R
implementation of the same spend-hygiene method — its `flag_dupes()` /
`flag_client_registrant_conflict()` are the prior art that `lda-entity-resolver`'s
canonical-spend view reimplements in SQL (amendment dedup, in-house/outside rollup;
credited in that skill's SKILL.md), so any headline spend total can be cross-checked
across two codebases that share no code.

## 2. Which findings each skill supports

_Filled in as findings lock. See `findings/` (one file per locked finding)._

| Finding | Skills used | Trace files |
|---|---|---|
| `findings/L010_pipe_materials_war.md` — DIPRA's Q1-2026 spend spike pushing iron-pipe materials provisions (independently verified 2026-07-06, fresh-agent PASS; awaiting lock) | `lda-corpus-loader` (DB build + `show_record.py` citations), `lead-scanner` (L010 SQL lenses, `queries/l010_pipe_war.sql`), `finding-verifier` (two fresh-agent passes), `investigation-ledger` (lead L010, descends from L004) | `traces/2026-07-05_deep-dive_L004-L003.jsonl` (lead development; see `traces/INDEX.md`) |
| `findings/chris_full_corpus_trends_2022-2026.md` — full-corpus trends: AI's arrival on K Street (Anthropic/OpenAI/a16z $0→$3M each), tariff lobbying +215% and still climbing, Continental Strategy +6,600% (verified), the SAP America single-quarter outlier catch, the Business Roundtable double-counting trap (author-verified; pending fresh-agent pass) | `lobbying-quarterly-filings` (per-year loads + `flag_dupes()` + `flag_client_registrant_conflict()` + `normalize_entity_name()`; fix trace in its `references/data_quality_notes.md`) | authored in `ChrisCioffi/agentic_investigation` (session logs there predate this repo); LOC-Nation anomaly independently corroborated by leads L025/L027 (`traces/INDEX.md`) |

## 3. Where the relevant traces are

`traces/` — one JSONL per session, named `YYYY-MM-DD_<skill-or-phase>_<lead-id>.jsonl`.
`traces/INDEX.md` maps finding → skill invocations → trace files → human decisions.
`traces/rendered/` — HTML renderings for fast review.
Human-judgment moments are logged in `DECISIONS.md` and cross-referenced from the index.

## 4. Outside data used

_Disclosed as used. Candidates: Congress.gov (bills/votes/committees), FEC (campaign finance),
FARA (foreign agents), Federal Register._

| Source | Used for | Where cited |
|---|---|---|
| openFEC API (`api.open.fec.gov/v1`, api.data.gov key; fetched 2026-07-07) — endpoints `/committees` (committee resolution), `/schedules/schedule_a` (itemized receipts), `/committee/{id}/totals` (published-total reconciliation) | L031 (crypto Enterprise-Map money leg): each crypto player's contributions into the Fairshake Super-PAC network (committees `C00835959` Fairshake, `C00836221` Defend American Jobs, `C00848440` Protect Progress), reconciled against LD-203 giving — the Super-PAC money LD-203 can't see | `skills/lead-scanner/fec_enrich.py` (SKILL.md "FEC enrichment"); LEDGER L031 row; raw responses cached in `out/fec_cache/` (gitignored; the cache + committee/transaction ids are the citeable form — FEC data is external, not in the DB). API key read from env/gitignored keyfile — never committed or traced |
| unitedstates/congress-legislators (`legislators-current.json` + `legislators-historical.json`, unitedstates.github.io, public domain CC0; fetched 2026-07-09) | Member resolution layer (P6): `members_all`/`member_terms` — every member serving 2021+, name parts/nicknames, party per term with dates, FEC candidate ids | `skills/lda-entity-resolver/scripts/build_members.py`; raw JSON cached in `out/congress_legislators_cache/` (gitignored) |
| FEC bulk committee files (`cm`/`ccl`/`cn` per cycle 2022/2024/2026, fec.gov bulk-downloads; fetched 2026-07-09) + openFEC `/committees?designation=D` (leadership-PAC sponsor ids; key from env, never committed) | Candidate-support committee crosswalk (P6): `member_committees` — campaign committees / leadership PACs / JFC participants, tier-labeled | `skills/lda-entity-resolver/scripts/build_members.py`; raw files cached in `out/fec_cache/bulk/` + `out/fec_cache/leadership_pacs/` (gitignored) |
| FARA bulk data — `FARA_All_ForeignPrincipals.csv` (efile.fara.gov/bulk, fetched 2026-07-06, updated daily by DOJ) | L006 (UAE sovereign wealth): confirming zero FARA registrations for the Mubadala family and that ADIA's six historical registrations all terminated by 2022 | `archive/LEDGER_pilot-triage_2026-07-06.md` L006 row (pilot-scale ledger, archived 2026-07-06 — see CLAUDE.md); `queries/l006_mubadala.sql` header |
| SEC Litigation Release 26458 + complaint PDF; Tracxn team profile; innovairrs.com | L003 (Innovairrs identity link) — lead work, parked; allegations-only framing mandatory | `archive/LEDGER_pilot-triage_2026-07-06.md` L003 row + Cold threads (pilot-scale ledger, archived 2026-07-06 — see CLAUDE.md) |

## 5. Conflicts of interest

_One statement per team member — connections (employment, financial, family, prior work) to any
person or organization named in the findings, or "none known against the entities named."_

| Team member | Statement |
|---|---|
| Rob Calvey | _Pending — "none known against the entities named" or specifics._ |
| Chris Cioffi | Reports on congressional lobbying disclosures professionally; authored the lobbyR package adapted in `skills/lobbying-quarterly-filings/`. _Statement pending his own wording — entities-named check to confirm._ |
| Dhrumil Mehta | _Pending — "none known against the entities named" or specifics._ |
| Aarushi Sahejpal | Contributed to the open-source lobbyR R package (github.com/Lobbying-DisclosuRe/lobbyr), which `skills/lobbying-quarterly-filings/` adapts. No known connections to any registrant, client, or member named in the findings. |
| Eiman Siddiqui | _Pending — "none known against the entities named" or specifics._ |

## 6. Possible legal violations flagged

_Any finding whose `Legal flag:` field is not "none" is listed here for the evaluation panel._

| Finding | Flag | Provision |
|---|---|---|
| `findings/L010_pipe_materials_war.md` | none | — |
| `findings/chris_full_corpus_trends_2022-2026.md` | none | — |
