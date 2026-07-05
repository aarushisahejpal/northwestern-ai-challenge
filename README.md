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
| `skills/lda-corpus-loader/` | Parses all three raw datasets into a queryable DB; every row keeps a raw-record pointer; includes `show_record.py` | TBD |
| `skills/lda-entity-resolver/` | Cross-dataset entity table + alias map (Senate↔House crosswalk) | TBD |
| `skills/investigation-ledger/` | Lead/entity/thread tracking templates + schema lint | TBD |
| `skills/lead-scanner/` | Lens library: SQL-first anomaly scans that emit candidate leads | TBD |
| `skills/finding-verifier/` | Fresh-agent re-derivation of every claim in a finding before it locks | TBD |

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
| — | — | — |

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
