---
name: lead-scanner
description: SQL-first tools for turning a lobbying/disclosure corpus into leads. (1) A lens library — say-vs-pay, revolving door, spend anomalies, cross-chamber discrepancies, contribution flows, foreign influence, disclosure gaps — emitting candidate leads as record IDs. (2) A bill cross-check: bill number or named alias → every filing and press release touching it, cited. (3) A disclosed-giving map (LD-203) for an entity or industry roster. (4) An industry map: finds an industry hidden in the free-text, tags it from a curated versioned lexicon, emits an entity-resolved player roster; an FTS/keyness/semantic loop proposes new vocabulary for human triage. (5) FEC/openFEC Super-PAC enrichment of that roster, reconciled against LD-203. (6) A quarterly turnover tracker — declared terminations, new engagements, firm swaps, in-house moves, churn. Use when generating or refreshing the lead pipeline, running a bill-level lobbying check, mapping an industry's who/how-much/who-they-give-to, or reporting a quarter's turnover.
model: inherit  # deliberate: the bill cross-check gets pulled into live investigation turns; an override would re-model the rest of the calling turn — run sweep sessions cheap via /model at session start
---

# Lead Scanner

Six capabilities, one discipline: extraction and filtering stay in SQL; the model only ranks and
phrases hypotheses; output is record IDs + one-liners, never quoted record text.

1. **A lens library** — SQL-first scans that turn the corpus into candidate lead rows.
2. **A bill cross-check** (`scripts/lda_bill_lookup.py`) — a bill *number* or *named alias* → every
   filing and press release that touches it, each with a citation key.
3. **A disclosed-giving map** (`scripts/lda_ld203_giving.py`) — a registrant entity or roster → its
   disclosed political giving (totals, recipients, per-entity split).
4. **An industry map** (`scripts/lda_industry_map.py` + `scripts/lda_freetext_discovery.py` +
   `scripts/lda_semantic_search.py`) — find an industry hidden in the free-text, tag it
   deterministically, emit an entity-resolved player list.
5. **An external campaign-finance enrichment** (`scripts/fec_enrich.py`) — take that roster and add
   the Super-PAC money leg from FEC/openFEC, reconciled against the disclosed-giving map.
6. **A quarterly turnover tracker** (`scripts/lda_turnover.py`) — diff a quarter against the corpus:
   declared terminations, new engagements, firm swaps, in-house moves, firm churn scoreboard.

## How this skill is bound to a corpus

The *method* is corpus-agnostic; the *facts* are not. Three layers hold the corpus-specific parts so
this SKILL.md never has to:

- **`reference/corpus-profile.md`** — the binding layer. Table/view names, citation-key formats, the
  dedup key (`period_invariant_key`), the mirror-source rule (`mirror_sources` / `primary_for_dollars`),
  and attribution grain (`attribution_grain`). Every caveat below names the profile field that carries
  the fact. Point the tools at a new corpus by refilling that file.
- **The JSON lexicons beside the scripts** — `industry_lexicon.json`, `bill_aliases.json`: versioned,
  cited, user-updatable vocabularies. The "what the investigator has found" layer; each carries a
  `_meta.discipline` block. Grow them as you learn; don't restate them here.
- **The `reference/` dataset briefs** — external-dataset traps (e.g. `fec-campaign-finance.md` for the
  FEC leg), produced by `dataset-primer`.

**Naming convention:** `lda_*` scripts require the built DuckDB (the LDA corpus); `fec_*` requires the
external openFEC API; untokened scripts are corpus-agnostic. A script's filename tells you what it
needs. Each corpus-bound script also declares its required profile fields in its header.

Requires a DuckDB built by `lda-corpus-loader` (cross-dataset lenses also use `lda-entity-resolver`'s
entity tables). Raw records are opened only through `show_record.py` — never grep the raw corpus.

**Where results go:** these tools *generate* leads; they don't record findings. Current runs live in
the LEDGER (the crypto industry-map + money legs are L029–L031). Generated rosters/intermediates go to
the gitignored repo-root `out/`, never into `skills/`.

## Bill cross-check — `scripts/lda_bill_lookup.py`

**The problem it solves.** Press releases and members name bills ("the Farm Bill", "NDAA", "Inflation
Reduction Act"); filings cite `H.R.`/`S.` numbers. Matching on number alone finds the money but misses
the messaging (and fabricates "lobbied but publicly silent" bills — the trap that killed L004);
matching on name alone finds the messaging but misses the money. This bridges both directions:

- **Number side** — exact match on `bill_mentions` (numbers pre-extracted from filings + press at load).
- **Name side** — whole-word regex on press text (and, on request, filing free-text), driven by the
  alias crosswalk.

A query by *number* also pulls the name-cited press; a query by *name* reaches the number-cited
filings. Every row carries a `show_record.py` key.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_bill_lookup.py HR5376
.venv/Scripts/python skills/lead-scanner/scripts/lda_bill_lookup.py "Inflation Reduction Act"
.venv/Scripts/python skills/lead-scanner/scripts/lda_bill_lookup.py "Farm Bill"   # phrase-primary; no stable number
.venv/Scripts/python skills/lead-scanner/scripts/lda_bill_lookup.py --list-aliases
```

Useful flags: `--dataset`, `--json`, `--scan-freetext`, `--top`/`--limit`. The alias crosswalk is
`scripts/bill_aliases.json`; its `_meta` explains the discipline (why ambiguous acronyms and reused
low numbers like `H.R.1` are phrase-primary, not number-matched). Add a bill by adding an entry there.

### Reading the output — caveats

- **Per-item dollars rank, they don't total.** A filing naming several bills attributes its whole
  income to each (`attribution_grain` = filing-level, profile §3). For exact client dollars, use the
  `canonical_spend_view` (profile §4). 
- **Never sum `mirror_sources`; read `primary_for_dollars`.** The same quarterly is filed with both
  chambers, so summing double-counts; one chamber is the mirror and under-counts recent quarters
  (profile §1, §3). Filings are amendment/duplicate-deduped on `period_invariant_key`.
- **Press counts are raw and vintage-sensitive.** The press corpus grows over its window (profile §1),
  and a bill's attention concentrates in its brief legislative moment — so only compare "loudness"
  across bills of the *same* vintage, and read the by-year facet. Use shares, not raw counts.
- Citeable aggregate form: `queries/p2_bill_crosscheck.sql` (`P2a`–`P2d`).

## Disclosed-giving map — `scripts/lda_ld203_giving.py`

**The problem it solves.** An industry map has two halves: *what it spends to lobby* (the
`canonical_spend_view`) and *who it gives money to*. This answers the second from the disclosed-giving
records: resolve an entity (or a whole roster) to its filer name(s), and report total disclosed giving,
a breakdown by contribution type, top recipients, and a per-entity split — every sample row carrying a
`show_record.py`-resolvable key.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py "coinbase"      # one entity
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py --names-file out/roster.txt  # a roster
.venv/Scripts/python skills/lead-scanner/scripts/lda_ld203_giving.py "payward" --loose  # recover resolver-split variants
```

Useful flags: `--type`, `--since`, `--exact`, `--top`/`--limit`, `--json`.

### Reading the output — caveats

- **Attribution boundary (do not overstate).** These reports are filed by *registrants*, never by
  clients (`external_money` = `ld203`, profile §6). So this is the giving of an in-house registrant,
  trade association, or firm — **not** attributable to an outside firm's individual clients. The tool
  flags a client-only query as such.
- **Scope is the disclosed-giving regime, not FEC.** It captures lobbyist/registrant-reported
  contributions — **not** Super-PAC money (that's the FEC leg, tool 5). Say "disclosed giving," never
  "total political spending" (profile §6: LD-203 ≠ FEC).
- **Totals are amendment-de-duplicated** on the contribution identity; the raw figure is shown
  alongside so the amendment delta is visible. Treat totals as a ranking signal; verify items via
  `show_record.py`.
- **Recipients are raw payee/honoree strings**, only lightly normalized — **not** entity-resolved
  (candidates/PACs are a separate namespace). Read the top-recipients list as an approximation.
- **Entity resolution is the ceiling.** Precise mode inherits the resolver's entity boundaries; where
  it split a company's variants (profile §4 known ceiling), precise mode under-counts and `--loose`
  recovers them at the cost of precision — eyeball its matched-name list.
- Citeable aggregate form: `queries/ld203_giving.sql` (`G1a`–`G1d`).

## Industry map — `scripts/lda_industry_map.py` + `scripts/lda_freetext_discovery.py`

**The problem it solves.** Both money halves need the same thing first: the comprehensive list of *who
the players are*, and you cannot get that by guessing company names. An industry scatters across many
issue codes (the code is not the industry), and diversified filers lobby on it without its name in
theirs. So you map it by the **vocabulary the filers use** in the free-text (`freetext_surface`,
profile §5) — what they say they lobby on — not by issue code and not by name. (In this corpus's
crypto run, most client-side players had no crypto term in their name and were found only this way —
LEDGER L030.)

Two stages, discovery split from serving: keep the *cited* layer deterministic; put the heavy
machinery only in a *discovery* loop that feeds a human-approved vocabulary.

### Serving + map — `scripts/lda_industry_map.py`

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py --build-tags   # (re)build the serving table
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py crypto         # the map for a facet → out/<facet>_roster.txt
.venv/Scripts/python skills/lead-scanner/scripts/lda_industry_map.py crypto --recall-check  # players a name-LIKE scan would MISS
```

- `--build-tags` scans `freetext_surface` with the curated vocabulary in `scripts/industry_lexicon.json`
  and materializes `lobbying_issue_mentions` — one row per (doc, tag, keyword) with the raw-record
  pointer preserved: the deterministic tag→exact-word→record chain a finding cites (the mirror of
  `press_issue_mentions` on the lobbying side).
- The map resolves every tagged filing's registrant + client through `lda-entity-resolver` into a
  player list, and writes a **client-side** roster to `out/` that feeds the two money tools
  **unchanged**: `lda_ld203_giving.py --names-file <roster>` and the `canonical_spend_view`.

Useful flags: `--min-docs N`, `--facet ID`, `--top`, `--json`. The vocabulary lives in
`scripts/industry_lexicon.json`; its `_meta` explains the discipline (a facet gets its own tag, not an
ALI code; ambiguous terms are recorded `display_only` and not matched; add a term only after triaging
it, and bump the version).

### Discovery — `scripts/lda_freetext_discovery.py`

Proposes vocabulary; never tags a finding. Reads `freetext_surface` + its FTS index.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_freetext_discovery.py            # keyness candidates
.venv/Scripts/python skills/lead-scanner/scripts/lda_freetext_discovery.py --emergence
.venv/Scripts/python skills/lead-scanner/scripts/lda_freetext_discovery.py --untagged 'fintech OR "digital dollar"'
.venv/Scripts/python skills/lead-scanner/scripts/lda_freetext_discovery.py --search 'stablecoin "market structure"'
```

- **keyness** (default): Monroe log-odds of uni/bi-grams in the facet-tagged docs vs a background
  sample, hiding lexicon terms → a candidate list. **emergence**: per-year doc frequency. **--untagged**:
  the recall gap (docs that FTS-match a seed but carry no tag). **--search**: a BM25 precision check.
- Discipline: a discovered term is a **candidate**, never auto-added. `--search` it, eyeball raw docs
  via `show_record.py`, then a **human** adds it to `industry_lexicon.json` with a source and bumps the
  version. Nothing in discovery writes to the DB or the lexicon.

### Semantic discovery — `scripts/lda_semantic_search.py`

The embedding-side complement to FTS/keyness, for what exact-form search structurally misses:
synonyms and paraphrase ("pharmacy middlemen taking a cut of drug prices" finds the PBM filings;
"restrictions on Chinese network equipment" finds RESTRICT-Act filings that never say "router").
Reads the `lobbying_text_embeddings` layer `lda-corpus-loader`'s `embed_corpus.py` builds; same
discipline as the rest of discovery — proposes, never tags.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_semantic_search.py --query "pharmacy middlemen taking a cut of drug prices"
.venv/Scripts/python skills/lead-scanner/scripts/lda_semantic_search.py --query "..." --compare-bm25   # side-by-side vs FTS
.venv/Scripts/python skills/lead-scanner/scripts/lda_semantic_search.py --like <filing_uuid|house_id>  # neighbors of a filing
```

- `--query` embeds the question with the same model that embedded the corpus (read from the table;
  needs the optional torch/sentence-transformers deps). `--like` averages a record's stored vectors —
  **no model, no extra deps** — the cheap "who else lobbies on what this filing lobbies on" probe for
  lead expansion. `--compare-bm25` prints the FTS top-k alongside for the same query.
- Every hit shows cosine score, filing count, an example `show_record.py` key, and resolved senate
  client names. Search is brute-force cosine in DuckDB — sub-second at 388K vectors, no index to
  maintain.
- **Caveats:** results are semantic *neighbors*, not matches — expect on-theme noise in the tail;
  triage like any discovery output (eyeball raw docs, then curate keywords into the lexicon). Scores
  are model-relative (don't compare across models/rebuilds). If the embeddings table is missing or
  partial (`--limit` smoke run), the tool says so — rebuild with `embed_corpus.py`.

### Reading the output — caveats

- **Recall-first, then triage.** With `--min-docs 1` the map includes any client whose free-text names
  a facet term once, so incidental mentions appear in the tail — by design (recall is the point). A
  human triages; a finding names *specific* players with evidence, never "the whole list." Raise
  `--min-docs` for a higher-confidence core.
- **Spend is all-issue.** The player list joins each client's **total** `canonical_spend_view` (a
  size/ranking signal), not facet-only dollars — `attribution_grain` is filing-level (profile §3).
- **Entity resolution is the ceiling** (profile §4) — a documented limitation, not a silent gap.
- **Serving stays deterministic + cited.** FTS/keyness only *discover*; findings cite the
  `lobbying_issue_mentions` keyword→exact-word→record chain. Citeable form: `queries/p4_industry_map.sql`.

## External campaign-finance enrichment — `scripts/fec_enrich.py`

**The problem it solves.** The disclosed-giving map (tool 3) is the *disclosed lobbyist-side* giving —
but by law it does **not** capture Super-PAC money, which is where an industry often puts its headline
political money. So an industry map built on disclosed giving alone understates the spend by an order
of magnitude. This closes the gap: take the roster and report each player's FEC-disclosed contributions
**into the industry's Super-PAC network** (openFEC), reconciled against the disclosed-giving map — the
**delta** is the Super-PAC money the disclosed-giving regime can't see.

**Strategy — pull the PAC, then match the roster.** A Super PAC has a bounded, itemized donor list, so
this pulls every itemized receipt of each network committee once, caches it, aggregates by contributor,
and matches roster names locally — cheap, complete, and it surfaces network donors not on the roster.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/fec_enrich.py --names-file out/crypto_roster.txt
.venv/Scripts/python skills/lead-scanner/scripts/fec_enrich.py --names-file out/crypto_roster.txt --verify-totals
```

Useful flags: `--cycle`, `--committee-seed`/`--committee-id`, `--verify-totals`, `--min-match`, `--top`,
`--refresh`, `--json`.

**The dataset traps live in the brief, not here.** FEC data has a specific set of ways it will silently
double-count or mis-classify — count only the contribution line (not sale-proceeds, transfers, or
refunds); drop attribution memos (`memo_code='X'`); classify individuals by `entity_type=='IND'` (not
openFEC's `is_individual` flag); reconcile to a committee's published **contributions** total, not
`receipts`; treat the itemized (>$200) sum as a floor. Each rule, why it matters, and the reconciled
figures that stress-tested it against a real sample are in **`reference/fec-campaign-finance.md`**; the
concrete run is LEDGER L031. The tool implements every rule and shows an "excluded receipts" block for
transparency.

### The API key — env or gitignored keyfile, never in the repo

Resolved WITHOUT hardcoding/caching/printing: env `DATA_GOV_API_KEY` (or `FEC_API_KEY`) → a gitignored
one-line keyfile `out/.fec_api_key` → else the public `DEMO_KEY`. Only the source *label* is shown;
every cached request has the key stripped. README §4 discloses the source + fetch date, not the key.

### Reading the output — caveats

- **Matches are CANDIDATES, never silent merges.** FEC contributor names don't align to filing names,
  so the norm-key/token match (shared with `lda_ld203_giving.py`) is a *report to eyeball* — the raw
  FEC name is shown next to the roster player with a confidence label. A human confirms. Tightening
  names is roadmap cleanup C / P6.
- **Scope is FEC-disclosed + disclosed-giving — never "total political spending."** 501(c)(4) dark
  money and state-level money are out of both.
- **The cache IS the evidence.** Every raw response is written to `out/fec_cache/` (gitignored) with
  its endpoint, params (key stripped), and fetch timestamp. A finding cites the FEC `transaction_id` +
  `committee_id` + the openFEC endpoint + the cache fetch date. There is no `queries/*.sql` citeable
  form — FEC data is external, not in the DB; the cache + live-resolved committee ids are the artifact.
- **Pair with the other two legs:** `lda_ld203_giving.py` (disclosed giving) and the
  `canonical_spend_view` (lobbying spend) — together the who / how-much / who-they-give-to money map.

## Quarterly turnover tracker — `scripts/lda_turnover.py`

**The problem it solves.** The recurring "who moved" beat: each quarter, who *ended* representation,
who *hired*, which clients *swapped* firms or took the work *in-house*, and which firms churned the
most. Point-in-time spend rankings can't see any of this — turnover is a diff, not a total.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/lda_turnover.py            # latest quarter in DB
.venv/Scripts/python skills/lead-scanner/scripts/lda_turnover.py 2025Q4
.venv/Scripts/python skills/lead-scanner/scripts/lda_turnover.py 2025Q4 --json > out/turnover_2025Q4.json
```

Useful flags: `--top`, `--window` (swap window in quarters), `--json`. Five sections: summary
(vs prior quarter AND same quarter prior year), terminations ranked by trailing-4-quarter income,
new engagements, in-house moves + firm swaps (with the client's canonical spend for size), and a
firm churn scoreboard (engagements lost/signed per registrant).

### Reading the output — caveats

- **Terminations are DECLARED, never inferred** (`termination_signal`, profile §3): the tool reads
  the termination filing-type family, not absence-between-quarters — late posting and partial mirror
  dumps fabricate exits. Senate-only lens (the mirror source carries no termination signal).
- **A termination is not always an exit.** `re_engaged` flags pairs that file again later (a pause);
  `new_this_q` / `term_same_q` flag one-quarter engagements (hired and terminated inside the quarter).
- **"New" is grouped by resolved client entity, never `client_id`** — a re-registration re-issues
  `client_id` and would otherwise fabricate a hire (profile §4). Income NULL on a new engagement
  usually means registration-only so far.
- **Seasonality:** Q4 terminations run 22–43% above that year's other quarters (year-end cleanup) —
  compare a Q4 to prior Q4s. The **latest** quarter in the DB is a floor (terminations post with a
  lag); the tool warns when the target is the newest quarter.
- **Client-size dollars come from the `canonical_spend_view`** (profile §4); engagement-level
  trailing income dedups on `period_invariant_key` with a T treated as the terminal state.
- Citeable aggregate form: `queries/p3_turnover.sql` (`P3a`–`P3e`).

## Lenses — `queries/*.sql` run via `queries/run_sweep.py`

Each lens = a set of labeled SQL blocks in `queries/` + a scanning prompt that turns anomaly rows into
candidate ledger rows (`id | hypothesis | lens | named actors | evidence record IDs | next action`).
Blocks are delimited `-- ==== LABEL ====` and run with:

```bash
.venv/Scripts/python queries/run_sweep.py db/lda_full.duckdb [BLOCK-PREFIX] [queries/<file>.sql]
```

The lens files: `sweep_2026.sql` (point-in-time full-corpus sweep), `emergence_and_flows.sql`
(rate-of-change / fan-out / individual-as-client / giving flows), `press_issue_coupling.sql`
(lobbying-vs-messaging share coupling), and per-lead deep-dive files kept for reproducibility.

## Budget rules

- Extraction and filtering stay in SQL; the scanning model only ranks and phrases hypotheses.
- Output is record IDs + one-liners — never quoted record text into the orchestrating context.
- Raw records are accessed only via `lda-corpus-loader`'s `show_record.py`.
- A candidate lead needs a named actor, a date, and a record ID before it can pass triage — a bill
  showing heavy lobbying *and* member press attention is a starting point, not yet a lead.
