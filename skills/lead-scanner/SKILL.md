---
name: lead-scanner
description: SQL-first tools for turning the lobbying database into leads. (1) A lens library — say-vs-pay, revolving door, spend anomalies, Senate/House discrepancies, contribution flows, foreign influence, disclosure gaps — run as scans that emit candidate lead rows with record IDs, never quoted record text. (2) A bill cross-check that, given a bill number OR a named alias ("Inflation Reduction Act", "Farm Bill"), returns every Senate filing, House filing, and press release touching it, each with a show_record.py-resolvable citation key. (3) An LD-203 giving map that, given a registrant entity or an industry roster, reports its disclosed political giving (totals, recipients, per-entity split) — the "who are they giving money to?" half of an industry map. (4) An industry map that finds an industry hidden in the lobbying free-text under many issue codes and vague categories (crypto scattered under "taxation" etc.), tags it with a curated vocabulary, and emits an entity-resolved player list — clients and registrants — that feeds the giving map and the canonical-spend view unchanged, plus a free-text discovery loop (FTS + keyness) that proposes new vocabulary for human triage. (5) An FEC enrichment that takes that player roster and reports each player's contributions into the industry's Super-PAC network (openFEC), reconciled against the LD-203 giving map — the delta being the Super-PAC money LD-203 can't see (crypto's Fairshake). Use when generating or refreshing the lead pipeline, running a rapid bill-level "who's been quietly lobbying this?" check, mapping an industry's disclosed contributions and its Super-PAC money, or building the who/how-much/who-they-give-to map of an industry.
---

# Lead Scanner

Three things live here:

1. **A lens library** — SQL-first scans that turn the lobbying corpus into candidate lead
   rows (record IDs + one-line hypotheses).
2. **A bill cross-check** (`scripts/bill_lookup.py`) — given a bill *number* or a *named
   alias*, list every Senate filing, House filing, and press release that touches it, each
   with a citation key resolvable by `lda-corpus-loader`'s `show_record.py`.
3. **An LD-203 giving map** (`scripts/ld203_giving.py`) — given a registrant *entity* or an
   *industry roster*, report its disclosed political giving (totals, top recipients, per-entity
   split), each sample row carrying a `show_record.py` key.
4. **An industry map** (`scripts/industry_map.py` + `scripts/freetext_discovery.py`) — find an
   industry hidden in the lobbying free-text, tag it deterministically, and emit an
   entity-resolved player list that feeds tools (2 is bills, 3 is giving) and the resolver's
   `v_client_canonical_spend` unchanged.
5. **An FEC enrichment** (`scripts/fec_enrich.py`) — take that roster and add the Super-PAC
   money leg: each player's contributions into the industry's Super-PAC network (openFEC),
   reconciled against the LD-203 giving map. The delta is the money LD-203 can't see.

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
- **Press counts are raw and vintage-sensitive.** The press corpus starts 2022-01-01 and grows
  ~4x by 2025 (≈19.7k→48.3k releases/yr), and a bill's press attention concentrates in its brief
  legislative window. So an early-vintage bill (its window in the thin 2022 corpus, any pre-2022
  advocacy unseen) shows far fewer name-matches than a 2025-era one — a 2022 bill's House-passage
  spike is real but small against a thin year. Read the **by-year facet** (who named it and when),
  and only compare press "loudness" across bills of the same vintage. (This is the same
  corpus-growth confound the press-issue-coupling work handles with shares, not raw counts.)
- The citeable aggregate form of these counts is `queries/p2_bill_crosscheck.sql` (blocks `P2a`–
  `P2d`), for findings that must cite the exact SQL.

## LD-203 giving map — `scripts/ld203_giving.py`

**The problem it solves.** An industry map has two halves: *what does the industry spend to
lobby* (answered by `lda-entity-resolver`'s `v_client_canonical_spend`) and *who does it give
money to*. This tool answers the second from the Senate LD-203 contribution reports: resolve an
entity (or a whole roster) to its LD-203 filer name(s), and report total disclosed giving,
a breakdown by contribution type, top recipients, and a per-entity split — every sample row
carrying a `show_record.py`-resolvable `filing_uuid`.

### One-command demo

```bash
# one entity (substring match, entity-resolved)
.venv/Scripts/python skills/lead-scanner/scripts/ld203_giving.py "coinbase"
# a whole industry — one line per entity; each matched exactly (canonical name or alias)
.venv/Scripts/python skills/lead-scanner/scripts/ld203_giving.py --names-file crypto_roster.txt
# recall mode: catch resolver-split name variants (Payward/Kraken's three spellings)
.venv/Scripts/python skills/lead-scanner/scripts/ld203_giving.py "payward" --loose
```

Useful flags: `--type feca,he,pic,ple,me` (subset by contribution kind — `pic`=presidential
inaugural, `he`=honorary), `--since 2024`, `--exact`, `--top`/`--limit`, `--json`.

### Reading the output — the load-bearing caveats

- **Attribution boundary (do not overstate).** LD-203 reports are filed by *registrants* and
  their lobbyists, never by clients. So this is the giving of an **in-house registrant, trade
  association, or firm** — it is **not** attributable to an outside firm's individual clients. A
  crypto client that lobbies only through a multi-client firm has no LD-203 giving of its own
  here; the tool flags such a query as `client-only`.
- **Scope is LD-203, not FEC.** It captures lobbyist/registrant-reported FECA contributions plus
  honorary, presidential-inaugural (`pic`), and library (`ple`) payments — **not Super-PAC money**
  (that lives in FEC data). For an industry whose headline election spending flows through Super
  PACs (e.g. crypto's Fairshake), LD-203 is the disclosed lobbyist-side slice, a fraction of the
  FEC total. Say "disclosed LD-203 giving," never "total political spending."
- **Totals are amendment-de-duplicated** on the contribution identity (registrant+lobbyist+year+
  type+amount+payee+honoree+date+contributor). The loader does not carry LD-203 `filing_type`
  (the raw record has it — `"YY"`/Year-End, mid-year, amendments), so this DISTINCT is a
  heuristic; the raw figure is shown alongside so the amendment delta is visible. Treat totals as
  a **ranking signal** and verify specific items via `show_record.py`.
- **Recipients are raw honoree/payee strings**, only lightly normalized for grouping — **not**
  entity-resolved (candidates/PACs are a separate namespace; the same inaugural committee appears
  as "TRUMP VANCE INAUGURAL COMMITTEE" and "DONALD TRUMP/ J.D. VANCE"). Read the top-recipients
  list as an approximation; cite individual items by `filing_uuid`.
- **Entity resolution is the ceiling.** The precise (default) mode inherits `lda-entity-resolver`'s
  entity boundaries: where the resolver split one company's name variants into separate entities
  (Payward/Kraken), precise mode under-counts. `--loose` matches filer names directly to recover
  them, trading precision for recall — eyeball its matched-name list for conflation. Tightening
  this is people/name-resolution work (roadmap cleanup C / P6).
- The citeable aggregate form is `queries/ld203_giving.sql` (blocks `G1a`–`G1d`), for findings
  that must cite the exact SQL. It complements `emergence_and_flows.sql#F1` (giver→one-honoree
  concentration) and `sweep_2026.sql#S4` (recipients across all givers): this tool is
  giver-centric and entity-resolved.

## Industry map — `scripts/industry_map.py` + `scripts/freetext_discovery.py`

**The problem it solves.** An industry map has two money halves (spend + giving, above), but both
need the same thing first: the **comprehensive list of who the players are**. You cannot get that
by guessing company names. An industry like crypto scatters across 15+ ALI issue codes
(FIN/BAN/TAX/SCI/CPI/CDT/AGR/…, only ~44% under FIN), and diversified filers — Robinhood, PayPal,
Fidelity, Visa, Mastercard, Citigroup — lobby on crypto without "crypto" in their name. So you
map it by the **vocabulary the filers use** in the lobbying free-text (what they say they lobby
on), not by issue code and not by name. The map's own output showed **493 of 535** crypto client
players have no crypto term in their name — found only this way.

Two stages, discovery split from serving (the roadmap principle: keep the *cited* layer
deterministic; put the heavy machinery only in a *discovery* loop that feeds a human-approved
vocabulary).

### Serving + map — `scripts/industry_map.py`

```bash
# once (or after the lexicon changes): build the deterministic serving table
.venv/Scripts/python skills/lead-scanner/scripts/industry_map.py --build-tags
# the map for a facet (default crypto); writes out/crypto_roster.txt (gitignored) for the money tools
.venv/Scripts/python skills/lead-scanner/scripts/industry_map.py crypto
# prove recall: the players a name-LIKE '%crypto%' scan would MISS
.venv/Scripts/python skills/lead-scanner/scripts/industry_map.py crypto --recall-check
```

- `--build-tags` scans `lobbying_freetext` (built by `lda-corpus-loader`'s `add_lobbying_freetext.py`)
  with the curated vocabulary in `scripts/industry_lexicon.json` and materializes
  **`lobbying_issue_mentions`** — one row per (doc, tag, keyword) with the raw-record pointer
  preserved. This is the mirror of the loader's `press_issue_mentions`, on the lobbying side, and
  the deterministic tag→exact-word→record chain a finding cites.
- The map resolves every tagged filing's registrant + client through `lda-entity-resolver`
  (`entities`/`entity_aliases`) into a player list, and writes a roster of **client-side** player
  names that feeds the two money tools **unchanged**:
  `ld203_giving.py --names-file <roster>` (who they give to) and `v_client_canonical_spend`
  (what they spend). Round-trip verified: Coinbase / Robinhood / Paradigm resolve straight through
  both.

Useful flags: `--min-docs N` (a player must appear in ≥N crypto free-text docs — raise it to drop
incidental one-filing mentions), `--facet ID`, `--top`, `--json`.

### The vocabulary — `scripts/industry_lexicon.json`

A versioned, cited, per-facet dictionary of distinctive **`phrases`**, same precision-over-recall
discipline as `bill_aliases.json`. The facet gets its **own tag** (`CRYPTO`), deliberately not
folded into an ALI code (crypto is not one code). Ambiguous terms are recorded in `display_only`
with the reason and **not** matched (bare `token`/`mining`/`wallet`/`coin`; bare `clarity act`,
which matched an unrelated athletic-training filing — the distinctive `digital asset market
clarity` is used instead). Add a term only after triaging it (below) and bump the version.

### Discovery — `scripts/freetext_discovery.py`

Proposes vocabulary; never tags a finding. Reads `lobbying_freetext` + its FTS index.

```bash
.venv/Scripts/python skills/lead-scanner/scripts/freetext_discovery.py            # keyness candidates
.venv/Scripts/python skills/lead-scanner/scripts/freetext_discovery.py --emergence
.venv/Scripts/python skills/lead-scanner/scripts/freetext_discovery.py --untagged 'fintech OR "digital dollar"'
.venv/Scripts/python skills/lead-scanner/scripts/freetext_discovery.py --search 'stablecoin "market structure"'
```

- **keyness** (default): Monroe log-odds of uni/bi-grams in the facet-tagged docs vs a background
  sample, hiding terms already in the lexicon → the candidate list (it surfaced the
  Lummis-Gillibrand Responsible Financial Innovation Act, "payment stablecoins", "anti-money
  laundering", "fintech"). **emergence**: per-year doc frequency of candidates. **--untagged**:
  the recall gap — terms in docs that FTS-match a seed but carry no facet tag. **--search**: a
  BM25 precision check of one candidate before you add it.
- Discipline: a discovered term is a **candidate**, never auto-added. `--search` it, eyeball a few
  raw docs via `show_record.py`, then a **human** adds it to `industry_lexicon.json` with a source
  and bumps the version. Nothing in discovery writes to the DB or the lexicon.

### Reading the output — the load-bearing caveats

- **Recall-first, then triage.** With `--min-docs 1` the map includes any client whose filing
  free-text names a crypto term once — so incidental mentions (AARP on crypto scams, AFL-CIO on a
  pension aside) appear in the tail. That is by design (recall is the point); a human triages the
  list, and a finding names *specific* players with evidence, never "the whole list." Raise
  `--min-docs` for a higher-confidence core.
- **Spend is all-issue.** The player list joins each client's **total** `v_client_canonical_spend`
  (a size/ranking signal), not crypto-only dollars — filing-level issue attribution is imprecise.
- **Entity resolution is the ceiling.** Where the resolver split a company's name variants
  (a16z's several spellings, Payward/Kraken — cleanup C / P6), a player can appear twice or
  under-count. A known, documented limitation, not a silent gap.
- **Serving stays deterministic + cited.** FTS/keyness only *discover*; findings cite the
  `lobbying_issue_mentions` keyword→exact-word→record chain. The citeable aggregate form is
  `queries/p4_industry_map.sql` (`P4a`–`P4e`).
- **Output convention.** Committed artifacts (the vocabulary `industry_lexicon.json`, the scripts,
  the SQL) live in the skill. Generated intermediates — the roster, and any discovery dump you
  redirect — go to the repo-root **`out/`** dir, which is gitignored and disposable, the same rule
  `db/` and `data/` follow. Nothing is ever written into `skills/`. The serving table itself lives
  in the (gitignored) DB. Discovery candidates print to stdout by design — they are for a human to
  read and triage, not to persist.

## FEC enrichment — `scripts/fec_enrich.py`

**The problem it solves.** The LD-203 giving map (tool 3) is the *disclosed lobbyist-side*
giving — but by law LD-203 does **not** capture Super-PAC money, which is exactly where an
industry like crypto puts its headline political money (the **Fairshake** network, ~$100M+
scale). So an industry map built on LD-203 alone understates the political spend by an order of
magnitude. This closes the gap: it takes the industry roster and reports each player's FEC-
disclosed contributions **into the industry's Super-PAC network**, reconciled against the LD-203
map — the **delta** (the Super-PAC money LD-203 can't see) is the reportable surface.

**Strategy — pull the PAC, then match the roster** (not one query per player). A crypto Super PAC
has a bounded, itemized donor list, so this pulls every itemized receipt of each network committee
once, caches it, aggregates by contributor, and matches roster names locally — cheap, complete,
and it also surfaces network donors that weren't on the roster.

### One-command demo

```bash
# the crypto Super-PAC network, reconciled against the crypto roster (industry_map.py output)
.venv/Scripts/python skills/lead-scanner/scripts/fec_enrich.py --names-file out/crypto_roster.txt
# add the published-total sanity gate; probe a single committee directly
.venv/Scripts/python skills/lead-scanner/scripts/fec_enrich.py --names-file out/crypto_roster.txt --verify-totals
.venv/Scripts/python skills/lead-scanner/scripts/fec_enrich.py --committee-id C00835959 --names-file out/crypto_roster.txt
```

Useful flags: `--cycle 2024 2026` (two-year transaction periods), `--committee-seed`/`--committee-id`,
`--verify-totals`, `--min-match`, `--top`, `--refresh` (bypass cache), `--json`.

### The API key — env or gitignored keyfile, never in the repo

The api.data.gov key is resolved WITHOUT ever hardcoding, caching, or printing it, in order:
env `DATA_GOV_API_KEY` (or `FEC_API_KEY`) → a gitignored one-line keyfile `out/.fec_api_key`
(read internally, never echoed) → else the public `DEMO_KEY` (real data, shared-IP rate-limited).
Only the source *label* is ever shown. Every cached request has the key stripped. README §4
discloses the source + fetch date, not the key.

### Reading the output — the load-bearing caveats

- **Count LINE-11 contributions only — the crypto in-kind→liquidation double-count.** A crypto
  gift is filed on Schedule A **line 11** (the real contribution, in-kind); when the PAC later
  *sells* the donated coin, the sale proceeds are re-filed on **line 17** ("Other Federal
  receipts") as a fresh non-memo row — Coinbase's $59.9M "COINBASE COMMERCE (EXCHANGE)" rows are
  the same coins being liquidated, **not** a second donation. Summing line-11+line-17 credits the
  donor twice (Coinbase $106.6M true → $166.5M inflated). The tool attributes donor money from
  line-11 rows only and excludes line-12 (inter-committee transfers, the $113M Fairshake→sister
  moves), line-15/16 (refunds received), and line-17 (sale proceeds + interest) — all shown in an
  "excluded non-contribution receipts" block for transparency. This was found by an independent
  review of FEC's transaction-code/Schedule-A-line docs, **not** by the tool's own sanity check
  (which had passed against the wrong field — see the memo bullet).
- **Reconcile to FEC `contributions`, not `receipts`.** The `--verify-totals` gate compares the
  itemized line-11 non-memo sum to each committee's FEC-published **`contributions`** total and
  matches to <0.01% on a closed cycle (Fairshake 2024: $217.42M vs $217.42M). Reconciling to
  `receipts` (as a first version did — $260.07M) is false confidence: `receipts` *includes* the
  line-17 sale proceeds and line-12 transfers, so matching it merely certifies you inherited FEC's
  gross-up.
- **Matches are CANDIDATES, never silent merges.** FEC contributor names don't align to LDA
  names, so the norm-key/token match (shared with `ld203_giving.py`) is a *report to eyeball* —
  the raw FEC contributor name is shown next to the roster player, with a confidence label
  (`exact` vs `candidate`). E.g. "UNIVERSAL NAVIGATION INC." resolves to roster "Uniswap Labs" and
  "MULTICOIN CAPITAL GP"/"…GROUP LLC" to "Multicoin Capital" — correct, but the name alone
  wouldn't tell you, so a human confirms. (The line-11 rule above also removed an earlier
  false positive — "THE GIVING BLOCK" name-matching "Block, Inc." — because it was a line-17
  sale-proceeds row, not a contribution.) Tightening names is cleanup C / P6.
- **Exclude FEC memo entries too.** On top of the line rule, openFEC Schedule A returns
  LLC-attribution memos (`memo_code='X'`) as separate rows whose amount is already in another
  line; summing them manufactures a phantom "individual giving" shadow equal to the corporate line
  (a16z's $94.5M LLC gift re-attributed to Andreessen/Horowitz as memos, which without the drop
  had also inflated Coinbase $166M→$299M). The tool drops `memo_code='X'` from every total.
  (openFEC responses carry no `is_memo` field, so `memo_code` is the operative filter.)
- **`is_individual` is NOT "a natural person."** openFEC flags many corporate Super-PAC receipts
  `is_individual=True` (Ripple Labs Inc.'s $25M gifts come back `is_individual=True`,
  `entity_type='ORG'`). The authoritative individual signal is `entity_type=='IND'`; the tool uses
  that, and keeps genuine individual gifts in a **separate** section (a company's treasury money is
  not its executives' personal gifts).
- **Scope is FEC-disclosed + LD-203-disclosed — never "total political spending."** 501(c)(4) dark
  money and state-level money are out of both. Same discipline as `ld203_giving.py`'s "LD-203 ≠ FEC".
- **Itemized (>$200) floor, net amounts, amendments.** Figures are itemized electronic-filing
  contributions (sub-$200 giving is aggregated + unattributable, so treat totals as a floor — here
  the itemized line-11 sum ≈ FEC's published `contributions` because the checks are large). Amounts
  sum as reported (nets any refund/redesignation negatives; none present in the Fairshake pull). The
  openFEC API reflects the latest amendment (unlike the bulk data), verified by zero duplicate transaction_ids
  and the `--verify-totals` reconciliation; a defensive transaction_id DISTINCT guards reuse on
  other committees. These are the FEC-data traps enumerated in `reference/fec-campaign-finance.md` §3 — each was
  stress-tested against the real Fairshake sample before the reconciliation was trusted (IND/ORG
  split, memo double-count, amendments, negatives, conduit-memo donor-identity, itemization floor).
- **The cache IS the evidence.** Every raw response is written to `out/fec_cache/` (gitignored)
  with its endpoint, params (key stripped), and fetch timestamp. A finding cites the FEC
  `transaction_id` + `committee_id` + the openFEC endpoint + the cache fetch date — the way scraped
  press text is primary and the live URL secondary (FEC records can be amended). There is no
  `queries/*.sql` citeable form here because FEC data is external, not in DuckDB; the cache plus the
  live-resolved committee ids are the reproducible artifact.
- **Pair with the other two legs:** `ld203_giving.py` (LD-203 giving) and `v_client_canonical_spend`
  (P1 lobbying spend) — together the who / how-much / who-they-give-to industry money map.

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
