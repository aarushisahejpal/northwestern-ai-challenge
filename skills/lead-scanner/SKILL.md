---
name: lead-scanner
description: SQL-first tools for turning the lobbying database into leads. (1) A lens library — say-vs-pay, revolving door, spend anomalies, Senate/House discrepancies, contribution flows, foreign influence, disclosure gaps — run as scans that emit candidate lead rows with record IDs, never quoted record text. (2) A bill cross-check that, given a bill number OR a named alias ("Inflation Reduction Act", "Farm Bill"), returns every Senate filing, House filing, and press release touching it, each with a show_record.py-resolvable citation key. Use when generating or refreshing the lead pipeline, or to run a rapid bill-level "who's been quietly lobbying this?" check.
---

# Lead Scanner

Two things live here:

1. **A lens library** — SQL-first scans that turn the lobbying corpus into candidate lead
   rows (record IDs + one-line hypotheses).
2. **A bill cross-check** (`scripts/bill_lookup.py`) — given a bill *number* or a *named
   alias*, list every Senate filing, House filing, and press release that touches it, each
   with a citation key resolvable by `lda-corpus-loader`'s `show_record.py`.

Requires `db/lda_full.duckdb` (built by `lda-corpus-loader`); cross-dataset lenses also use the
resolver's entity tables. Raw records are only ever opened through `show_record.py` — never grep
the raw corpus directly.

## Bill cross-check — `scripts/bill_lookup.py`

**The problem it solves.** Press releases and members name bills ("the Farm Bill", "NDAA",
"Inflation Reduction Act"); LDA filings cite `H.R.`/`S.` numbers. So matching a bill on its
number alone finds the money but misses the messaging, and matching on its name alone finds the
messaging but misses the money — and a number-only "who lobbied this?" scan fabricates
"lobbied but publicly silent" bills. This tool bridges the two directions:

- **Number side** — exact match on `bill_mentions` (H.R./S. numbers pre-extracted from Senate
  activity text, House `specific_issues`, and press text at load time).
- **Name side** — whole-word regex on press text (and, on request or for phrase-primary bills,
  on filing free-text), driven by a curated alias crosswalk.

A query by *number* also pulls the name-cited press (say-vs-pay); a query by *name* reaches the
number-cited filings. Every row it prints carries a `show_record.py` key.

### One-command demo

```bash
# by number
.venv/Scripts/python skills/lead-scanner/scripts/bill_lookup.py HR5376
# by name — resolves to the same HR5376 result, plus the ~3,000 releases that
# name the law but never cite its number
.venv/Scripts/python skills/lead-scanner/scripts/bill_lookup.py "Inflation Reduction Act"
# a bill with no reliable number (H.R.2 is reassigned every Congress) — found by name
.venv/Scripts/python skills/lead-scanner/scripts/bill_lookup.py "Farm Bill"
.venv/Scripts/python skills/lead-scanner/scripts/bill_lookup.py --list-aliases
```

Useful flags: `--dataset senate,house,press` (subset), `--json` (machine-readable),
`--scan-freetext` (also name-match filing free-text for a numbered bill), `--top`/`--limit`.

### The alias crosswalk — `scripts/bill_aliases.json`

A small, versioned, cited dictionary of named bills → H.R./S. number(s), same
precision-over-recall discipline as the loader's issue-keyword vocabulary:

- **`names`** are for display and reverse lookup; **`phrases`** are the *only* strings used for
  free-text matching. Ambiguous acronyms stay out of `phrases` (e.g. `IRA` also means individual
  retirement account; bare `PACT Act` also names an older animal-cruelty law).
- **`bills`** are normalized numbers (`HR5376`, `S2938`). `bill_mentions` has **no Congress
  dimension**, so a low, reused number (`H.R.1`, `H.R.2`, `S.1`) denotes a different bill each
  Congress and is left out on purpose — those bills are **phrase-primary** (e.g. the Farm Bill).
  The tool additionally warns whenever a matched number spans filings from more than one Congress.
- Every entry cites its congress.gov page; recurring vehicles (NDAA) list one number per fiscal
  year with its Public Law. Add an entry to teach the tool a new bill.

### Reading the output — the load-bearing caveats

- **Attributed income is filing-level.** A filing naming several bills attributes its full income
  to each, so per-bill dollars are a *ranking signal, not exact totals*. For exact client dollars,
  feed the client into `lda-entity-resolver`'s `v_client_canonical_spend`.
- **Senate and House are reported separately, never summed** — LD-2 quarterlies are filed with
  both chambers, so summing double-counts. House XML is a partial snapshot that under-counts
  recent quarters; treat it as reconcile/fill-gap, not a second independent total.
- Senate filings are amendment/duplicate-deduped on `filing_period` (not `filing_type`).
- The citeable aggregate form of these counts is `queries/p2_bill_crosscheck.sql` (blocks `P2a`–
  `P2d`), for findings that must cite the exact SQL.

## Lenses — `queries/*.sql` run via `queries/run_sweep.py`

Each lens = a set of labeled SQL blocks in `queries/` + a scanning prompt that turns anomaly
rows into candidate ledger rows (`id | hypothesis | lens | named actors | evidence record IDs |
next action`). Blocks are delimited `-- ==== LABEL ====` and run with:

```bash
.venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb [BLOCK-PREFIX] [queries/<file>.sql]
```

The lens files: `sweep_2026.sql` (point-in-time full-corpus sweep — say-vs-pay, contribution
flows, gaps), `emergence_and_flows.sql` (rate-of-change / fan-out / individual-as-client / LD-203
flows), `press_issue_coupling.sql` (lobbying-vs-messaging share coupling), and per-lead deep-dive
files kept for reproducibility. `p2_bill_crosscheck.sql` is the bill cross-check's citeable form.

## Budget rules

- Extraction and filtering stay in SQL; the scanning model only ranks and phrases hypotheses.
- Output is record IDs + one-liners — never quoted record text into the orchestrating context.
- Raw records are accessed only via `lda-corpus-loader`'s `show_record.py`.
- A candidate lead needs a named actor, a date, and a record ID before it can pass triage — a
  bill showing heavy lobbying *and* member press attention is a starting point, not yet a lead.
