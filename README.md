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
| `skills/lead-scanner/` | Lens library: SQL-first anomaly scans that emit candidate leads | `python queries/run_sweep.py db/lda.duckdb [BLOCK-PREFIX] [queries/<file>.sql]` (lens SQL lives in `queries/`; formal skill packaging still TBD) |
| `skills/finding-verifier/` | Fresh-agent re-derivation of every claim in a finding before it locks | Protocol in `SKILL.md`, not yet automated end-to-end; delegates outside-source PDFs to `skills/source-document-reader` |
| `skills/source-document-reader/` | Turns an external primary-source PDF (court filing, SEC complaint) into page-anchored, citable text via render-to-image OCR that survives broken e-filing fonts; defines the external-document citation convention | `python skills/source-document-reader/scripts/ocr_pdf.py --pdf data/DOC.pdf --out data/DOC.ocr.txt [--grep TERM] [--dpi 300]` (needs the Tesseract engine — see `SKILL.md`) |
| `skills/outside-context-scan/` | Exploratory web research (novelty/prior-art + news-landscape checks) to triage a lead before drafting — distinct from finding-verifier's claim-locking rigor | Protocol in `SKILL.md`; uses WebSearch/WebFetch directly, no custom script |

## 2. Which findings each skill supports

_Filled in as findings lock. See `findings/` (one file per locked finding)._

| Finding | Skills used | Trace files |
|---|---|---|
| — | — | — |

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
| FARA bulk data — `FARA_All_ForeignPrincipals.csv` (efile.fara.gov/bulk, fetched 2026-07-06, updated daily by DOJ) | L006 (UAE sovereign wealth): confirming zero FARA registrations for the Mubadala family and that ADIA's six historical registrations all terminated by 2022 | `archive/LEDGER_pilot-triage_2026-07-06.md` L006 row (pilot-scale ledger, archived 2026-07-06 — see CLAUDE.md); `queries/l006_mubadala.sql` header |
| SEC Litigation Release 26458 + complaint PDF; Tracxn team profile; innovairrs.com | L003 (Innovairrs identity link) — lead work, parked; allegations-only framing mandatory | `archive/LEDGER_pilot-triage_2026-07-06.md` L003 row + Cold threads (pilot-scale ledger, archived 2026-07-06 — see CLAUDE.md) |

## 5. Conflicts of interest

_One statement per team member — connections (employment, financial, family, prior work) to any
person or organization named in the findings, or "none known against the entities named."_

| Team member | Statement |
|---|---|
| — | — |

## 6. Possible legal violations flagged

_Any finding whose `Legal flag:` field is not "none" is listed here for the evaluation panel._

| Finding | Flag | Provision |
|---|---|---|
| — | — | — |
