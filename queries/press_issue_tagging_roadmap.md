# Press issue-tagging — scaling roadmap (internal design note)

**Status: design note, not built. Not a submission artifact; not cited by any finding.**
Parked 2026-07-06 from a discussion on the branch `feature/press-issue-frequency`.
Companion to `queries/press_issue_coupling.sql` / `.md`, which describe what exists today.

## The problem this addresses

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

## Options (spectrum, each grounded in this repo's constraints)

### 1. Make the DB searchable — DuckDB FTS (BM25) over `press_releases.text`
Testing a candidate term becomes a query instead of a code edit + rebuild. Decouples
*explore* (ad-hoc) from *serve* (the stable materialized tag table). Cheapest, no new deps,
keeps every convention. Sketch:
```sql
-- PRAGMA create_fts_index('press_releases', 'pr_id', 'text');  -- once
SELECT member_name, title, src_file||':'||src_line
FROM (SELECT *, fts_main_press_releases.match_bm25(pr_id, 'stablecoin "digital asset"') s
      FROM press_releases) WHERE s IS NOT NULL ORDER BY s DESC;
```

### 2. Automated term discovery — offline, ranked candidates (pure Python/SQL, reproducible)
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

### 3. Embeddings for semantic discovery — DuckDB VSS (HNSW), in-DB
Embed each release once (cheap at 141K), store vectors with the raw-record pointers,
nearest-neighbor a code's *description* against releases to surface semantically-related ones
with zero keyword overlap. Use in the **discovery** role; still tag with transparent
keywords. Reproducible if the model + version are pinned and vectors stored in the DB.

### 4. LLM zero-shot for the ambiguous slice — fits the budget tiers
Classify only the *ambiguous/untagged* releases with a cheap model (CLAUDE.md: "cheap models
scan and rank, returning record IDs"). Store the label with `method` / `model_version` /
`confidence` columns so it is separable from deterministic keyword tags and auditable. Good
for discovery/triage; weaker as the *cited* serving layer (non-deterministic; can't be the
sole basis for a locked finding without record-level re-derivation).

## Recommended layered pipeline

| Layer | Method | Property it protects |
|---|---|---|
| **Serve** (findings cite this) | curated `ISSUE_KEYWORDS` → `press_issue_mentions` | reproducible, auditable, tag → exact word + record |
| **Explore** (interactive) | DuckDB FTS/BM25 (+ VSS for semantic) | test a term in one query, no code change |
| **Discover** (offline, ranked candidates) | keyness + quarterly emergence + untagged mining; embeddings/LLM optional | keeps vocabulary current at scale |
| **Govern** | version the dict; record which vocab version produced a tag set | findings stay reproducible across vocab changes |

## Data-side scale notes
- Tag **incrementally** (only new releases) as the corpus grows quarterly, rather than
  re-running the full backfill. `backfill_press_issues.py` currently DELETEs + repopulates;
  an incremental mode would tag only `pr_id`s absent from `press_issue_mentions`.
- FTS/VSS indexes update alongside the corpus; rebuild on load.

## Concrete next steps (low-risk — neither touches the serving path)
1. Add the **FTS index** over `press_releases` (in `build_db.py` VIEWS/index step) + a small
   `queries/explore_press.sql` with BM25 search blocks.
2. Add a **keyness discovery query** that emits a ranked candidate-term list per ALI code
   from `press_issue_mentions` + `press_releases`, for triage into `ISSUE_KEYWORDS`.

## Open decisions before building
- Do embeddings/LLM stay strictly discovery-only, or is an LLM-tagged column acceptable in
  the serving table if clearly flagged `method='llm'`? (Reproducibility vs recall trade-off.)
- Vocabulary versioning mechanism: a `vocab_version` string in the dict + stamped onto
  `press_issue_mentions` rows, vs. relying on git history of `build_db.py`.
