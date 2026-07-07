# Corpus & analysis — ideas for additions (internal design note)

**Status: design notes, not built except where marked done. Not a submission artifact; not
cited by any finding.** Started 2026-07-06 as a press-issue-tagging scaling roadmap on the
branch `feature/press-issue-frequency`, broadened the same day into a general place to record
ideas for extending this corpus/analysis so a future session can see what's already been
proposed rather than re-deriving it. Each numbered section below is independent — read the one
you care about, skip the rest.

Sections:
1. Press issue-tagging — scaling the keyword tagger past hand-curation
2. Congress.gov bill-status join (outside data)
3. FEC contribution cross-reference (outside data)
4. Comparative-messaging event clustering
5. NER + entity graph

**How these map to the tool roadmap (added 2026-07-06):** `../_Plan.md` §9 folds every section
below into the story-bucket-driven P1–P7 priorities — these ideas are the *engine* layer (§1 → P4
free-text clustering + P5 text-reuse; §2 → P2 bill cross-check + P7 outcome timeline; §3 → P7; §4
stays parked; §5 stretch/amplifies P6). Two are also **partly solved already** by a teammate's
public R repo (`github.com/ChrisCioffi/lobbyR_IRE`): `flag_client_registrant_conflict()` = the P1
rollup double-count fix, `flag_dupes()` = an independent check on our existing `filing_period`
dedup, and its "Taxation" issue-filter → text-analysis workflow is a reference for §1 / P4. Reuse
the *logic* (R → our Python/DuckDB); disclose in README §4 with a COI note (the teammate is also the
tool's author) and a license check before copying.

---

## 1. Press issue-tagging — scaling roadmap

Companion to `queries/press_issue_coupling.sql` / `.md`, which describe what exists today.

### The problem this addresses

Today the press tagger is a hand-curated keyword dict — `ISSUE_KEYWORDS` in
`skills/lda-corpus-loader/scripts/build_db.py` → `press_issue_mentions`. It is precise,
transparent, and reproducible (every tag resolves to the exact word + raw record), but it
does not **scale**: keeping up with new/emerging vocabulary and synonyms means a human
reading the corpus and editing the dict.

The key reframe: the part that must stay hand-controlled is the **serving** layer (the tags
that findings cite), because auditability is what the challenge grades — "aggregate claims
need cited SQL + sampled records," which a black-box classifier can't satisfy. What doesn't
scale is **discovery** (finding the terms). So the design principle is:

> **Split discovery from serving. Keep serving deterministic and cited; put the heavier
> machinery (search, statistics, embeddings, LLMs) only in a discovery loop that feeds a
> human-approved vocabulary.**

### Options (spectrum, each grounded in this repo's constraints)

#### 1a. Make the DB searchable — DuckDB FTS (BM25) over `press_releases.text`
Testing a candidate term becomes a query instead of a code edit + rebuild. Decouples
*explore* (ad-hoc) from *serve* (the stable materialized tag table). Cheapest, no new deps,
keeps every convention. Sketch:
```sql
-- PRAGMA create_fts_index('press_releases', 'pr_id', 'text');  -- once
SELECT member_name, title, src_file||':'||src_line
FROM (SELECT *, fts_main_press_releases.match_bm25(pr_id, 'stablecoin "digital asset"') s
      FROM press_releases) WHERE s IS NOT NULL ORDER BY s DESC;
```

#### 1b. Automated term discovery — offline, ranked candidates (pure Python/SQL, reproducible)
A job that *proposes* terms for a human/cheap model to triage; never auto-commits. Three
complementary signals:
- **Keyness / log-odds per code** (Monroe log-odds-with-informative-prior): rank n-grams in
  the code-X subset vs background; surfaces phrases co-occurring with a code that aren't yet
  keywords.
- **Emergence spikes**: n-gram frequency by quarter, flag rate-of-change outliers — the same
  emergence philosophy as `queries/emergence_and_flows.sql`, applied to vocabulary. Catches
  new issues entering the lexicon (`GLP-1`, `de minimis`, `stablecoin`) as they appear.
- **Untagged-set mining**: ~20% of releases get no tag today; keyword-extract/cluster just
  that set to find whole topics the vocabulary is blind to.

#### 1c. Embeddings for semantic discovery — DuckDB VSS (HNSW), in-DB
Embed each release once (cheap at 141K), store vectors with the raw-record pointers,
nearest-neighbor a code's *description* against releases to surface semantically-related ones
with zero keyword overlap. Use in the **discovery** role; still tag with transparent
keywords. Reproducible if the model + version are pinned and vectors stored in the DB.

#### 1d. LLM zero-shot for the ambiguous slice — fits the budget tiers
Classify only the *ambiguous/untagged* releases with a cheap model (CLAUDE.md: "cheap models
scan and rank, returning record IDs"). Store the label with `method` / `model_version` /
`confidence` columns so it is separable from deterministic keyword tags and auditable. Good
for discovery/triage; weaker as the *cited* serving layer (non-deterministic; can't be the
sole basis for a locked finding without record-level re-derivation).

### Recommended layered pipeline

| Layer | Method | Property it protects |
|---|---|---|
| **Serve** (findings cite this) | curated `ISSUE_KEYWORDS` → `press_issue_mentions` | reproducible, auditable, tag → exact word + record |
| **Explore** (interactive) | DuckDB FTS/BM25 (+ VSS for semantic) | test a term in one query, no code change |
| **Discover** (offline, ranked candidates) | keyness + quarterly emergence + untagged mining; embeddings/LLM optional | keeps vocabulary current at scale |
| **Govern** | version the dict; record which vocab version produced a tag set | findings stay reproducible across vocab changes |

### Data-side scale notes
- Tag **incrementally** (only new releases) as the corpus grows quarterly, rather than
  re-running the full backfill. `backfill_press_issues.py` currently DELETEs + repopulates;
  an incremental mode would tag only `pr_id`s absent from `press_issue_mentions`.
- FTS/VSS indexes update alongside the corpus; rebuild on load.

### Concrete next steps (low-risk — neither touches the serving path)
1. Add the **FTS index** over `press_releases` (in `build_db.py` VIEWS/index step) + a small
   `queries/explore_press.sql` with BM25 search blocks.
2. Add a **keyness discovery query** that emits a ranked candidate-term list per ALI code
   from `press_issue_mentions` + `press_releases`, for triage into `ISSUE_KEYWORDS`.

### Open decisions before building
- Do embeddings/LLM stay strictly discovery-only, or is an LLM-tagged column acceptable in
  the serving table if clearly flagged `method='llm'`? (Reproducibility vs recall trade-off.)
- Vocabulary versioning mechanism: a `vocab_version` string in the dict + stamped onto
  `press_issue_mentions` rows, vs. relying on git history of `build_db.py`.

---

## 2. Congress.gov bill-status join (outside data)

**Status: not started.**

### The problem this addresses
`bill_mentions` extracts bill NUMBERS (H.R./S.) from filing/press text (see CLAUDE.md: press
and filings name bills differently — this table already bridges that). What it doesn't carry
is bill STATUS — introduced, passed committee, floor vote, passed chamber, enacted — so every
say-vs-pay finding so far can say "who lobbied on X" but not "...and X passed/died." This is
data_manual.md's House starting point: "extract and join against Congress.gov bill and vote
data," never attempted.

### Approach
For every distinct bill in `bill_mentions`, query the Congress.gov API for status + roll-call
votes, cache raw responses (don't re-fetch unchanged bills), and build a `bill_status` table
keyed on the same normalized bill key `bill_mentions` already uses. Join back against the
existing say-vs-pay lenses (H2/C1/C1b in `queries/sweep_2026.sql`) — the natural finding shape
is "$Y was spent lobbying on a bill that [passed/stalled/died in committee]."

### Prerequisite
Free API key from https://api.congress.gov/sign-up/ — not yet obtained.

### Why this priority
Cheapest of the outside-data ideas: no new extraction pipeline, just an API client + join on
data already sitting in the DB. Directly deepens every existing bill-level lead rather than
creating a new one from scratch.

### Disclosure
Would need a row in README.md's "Outside data used" table (§4) per the existing convention
(see the FARA bulk-data row for the pattern) — exact endpoint + fetch date.

---

## 3. FEC contribution cross-reference (outside data)

**Status: not started.**

### The problem this addresses
data_manual.md's Senate starting point: "`contribution_items[].payee` vs. `honoree` reveals
who lobbyists and their PACs are funding. Join to FEC for validation" — never attempted. Only
the raw LD-203 data (`senate_contribution_items`) exists so far, unvalidated against anything.

### Approach
Pull FEC's committee/candidate/contribution data (openFEC API) for the payees/honorees/
contributors named in `senate_contribution_items`; cache raw responses; build a joined table.
The reportable surface is DISCREPANCIES — a contribution FEC shows that isn't in the LD-203
data, or an amount mismatch — not simple confirmation that the two sources agree.

### Prerequisite
Free API key from https://api.data.gov/signup/ — not yet obtained.

### Why this priority
Same shape of work as #2 (API client + join), ranked slightly below it because the existing
LD-203 contribution data is already reasonably rich on its own, so FEC's marginal validation
value is more modest than the bill-status enrichment's.

### Disclosure
Same as #2 — a new README §4 row when this lands.

---

## 4. Comparative-messaging event clustering

**Status: not started; explicitly parked twice already (2026-07-04 pilot phase; 2026-07-06
manual-coverage review) for being harder to design than it looks — worth a real attempt, but
"still not worth the design cost" is a legitimate outcome here, not a failure.**

### The problem this addresses
data_manual.md's press starting point: "same event, different party framing — pull all
releases from a +/- 7-day window around a news event and cluster."

### The actual hard part
Not the clustering — identifying "a news event" worth clustering around in the first place.
Candidates considered so far, none built:
- Floor vote dates (would pair naturally with idea #2 above, if the Congress.gov roll-call
  data lands first — not a hard dependency, just a good source if available).
- A spike in same-day release volume across many members, as a proxy for "something happened"
  independent of any outside data.

### Approach once an event source is picked
For a handful of candidate events, pull all releases in a +/-7 day window, group by
`press_releases.party`, and compare framing. Doesn't need embeddings or a full clustering
model to start — a keyword/tone comparison may be enough to tell if there's a real finding
before investing in anything heavier.

### Why this priority
Ranked below the two outside-data joins: those are close to mechanical (API + join), this one
needs real design work on event detection with no guaranteed payoff, and it's the one gap
that's already been deliberately set aside twice.

---

## 5. NER + entity graph

**Status: not started; the manual's most ambitious ask, likely the biggest lift of anything
in this document.**

### The problem this addresses
data_manual.md's press starting point ("NER over `text` to pull companies, agencies, and
bills") and, combined with the lobbying-side data, the cross-dataset "Entity graph" idea:
press-release NER → companies/orgs → Senate/House LDA registrants & clients → government
entities lobbied → committees → members. Never attempted; only bill-NUMBER extraction (regex,
not NER) exists today.

### Approach — deliberately scoped down, not full-corpus
Given the deadline, don't run NER across all 141K+ press releases as a first move — cost/time
sink with no guaranteed payoff. Scope to a targeted subset first (e.g. releases mentioning
organizations already in the `entities`/`entity_aliases` tables built by `lda-entity-resolver`,
via cheap substring pre-filtering before anything NLP-heavy). Prefer a lightweight approach
(matching the entity-resolver's own `canonical_name` values as aliases against press text)
before reaching for a real NER model or an LLM extraction pass; if model-based extraction is
needed, that's cheap-model scan-and-rank work per CLAUDE.md's model/budget tiers, not a
frontier-model job. Link matches to the existing `entities`/`registrant_crosswalk` tables to
build the graph; report coverage/confidence honestly rather than claiming full-corpus coverage
that wasn't actually achieved.

### Why this priority
Last on purpose: biggest lift, least certain to finish in the time remaining, and the one
place where having #2-#4 already done genuinely helps (more structured data to link the graph
to). A partial, well-documented graph over a deliberately scoped subset is a better outcome
than an unreliable full-corpus attempt.
