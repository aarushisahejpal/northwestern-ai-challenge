# Corpus Profile — Congressional LDA + Press (2022–2026 Q1)

> **What this file is.** The *binding layer* between the corpus-agnostic skills and this specific
> corpus. A skill's SKILL.md describes a method and names the profile field that carries a
> corpus-specific fact (e.g. "read `primary_for_dollars`, never sum the mirror"); this file supplies
> the value for *this* corpus. To point the same skills at a different corpus, copy this file, refill
> the fields against the new data, and update the lexicons — the SKILL.md files do not change.
>
> **This is the single source of truth for "facts that bite."** Where CLAUDE.md, the loader/resolver
> SKILLs, and the lead-scanner SKILL previously each restated the don't-sum-chambers / dedup-key /
> citation-key rules, they now point here. Update a corpus fact in one place: here.
>
> Every fact below was verified against real corpus records (dates noted). A fact with no date is a
> convention, not a verified observation.

---

## Field reference (what the skills cite)

The abstractions a SKILL.md references by name, and this corpus's binding for each:

| Field | This corpus | Section |
|---|---|---|
| `sources` | `senate` (LDA JSON), `house` (LDA XML), `press` (JSONL) | §1 |
| `mirror_sources` | `senate` ⇄ `house` (LD-2 filed with both chambers) | §1, §3 |
| `primary_for_dollars` | `senate` (richer metadata; house = reconcile/fill-gap only) | §3 |
| `completeness_reference` | `senate` for recent quarters (house dumps are partial) | §1, §3 |
| `period_invariant_key` | `filing_period` (constant across original + amendment) | §3 |
| `dedup_pick` | latest by `posted`, then `filing_id` | §3 |
| `attribution_grain` | filing-level (income attributes whole to every item a filing names) | §3 |
| `citation_keys` | senate `filing_uuid` · house XML filename · press `src_file:src_line` | §2 |
| `termination_signal` | senate `filing_type` matching `^[1-4](T|TY|@|@Y)$` (declared, never inferred) | §3 |
| `entity_tables` | `entities` / `entity_aliases` / `registrant_crosswalk` | §4 |
| `canonical_spend_view` | `v_client_canonical_spend` | §4 |
| `freetext_surface` | `lobbying_freetext` (+ FTS, `stemmer='none'`, discovery-only) | §5 |
| `external_money` | `ld203` (in-DB, registrant-filed) · `fec` (external, openFEC) | §6 |
| `lexicons` | `industry_lexicon.json`, `bill_aliases.json` (user-updatable) | §7 |

---

## 1. Sources & roles

Three raw sources, unioned into one DuckDB by `lda-corpus-loader`:

| Source | Format | Role | Coverage |
|---|---|---|---|
| `senate` | Senate LDA JSON | **Primary** for dollar attribution (richest metadata); completeness reference for recent quarters | 2022 – 2026 Q1 |
| `house` | House LDA XML | **Mirror** of senate for LD-2 quarterlies; use only to reconcile / fill gaps | 2022 – 2026 Q1, **partial** dumps (see §3) |
| `press` | Congressional press releases JSONL | The "messaging" side (say-vs-pay); **not** a filing source | Starts **2022-01-01**, grows ~4× to 2025 (≈19.7k → 48.3k releases/yr) |

**Corpus builds** (identical loader, differ only by `--years`):
- `db/lda_full.duckdb` — 2022–2026, all years. **Canonical.** Start new work here.
- `db/lda_pilot.duckdb` — 2025 + 2026-Q1 only. Kept solely to reproduce `findings/L010`'s citations.
- `db/lda_2026.duckdb` — 2026-Q1 only. Superseded; safe to delete.

## 2. Citation keys

Every DB row carries a raw-record pointer; `show_record.py` is the **only** sanctioned path from a
key to a raw record. Never grep the raw corpus directly.

| Source | Citation key | Example |
|---|---|---|
| `senate` | `filing_uuid` | `0b112e4f-0586-434f-9707-37730209d735` |
| `house` | numeric XML **filename** (the `filing_id`) | `301817772` |
| `press` | `src_file:src_line` | `congress_press/2026-01.jsonl:12` |

- **`<houseID>` is NOT a citation key.** It is a persistent House-Clerk id for the registrant-client
  relationship, a *different namespace* from `filing_id`, and can numerically collide with an
  unrelated document (verified 2026-07-06: a Mercury filing's `<houseID>301740622` collides with an
  unrelated Cornerstone/NAHB registration `301740622.xml`). Only the filename is a valid House key.

## 3. Aggregation rules (the double-counting traps)

- **Never sum `mirror_sources`.** LD-2 quarterlies are filed with **both** chambers, so `senate` and
  `house` are largely copies of the same filings. Dollar attribution is `senate`-primary; use `house`
  only to reconcile or fill gaps. *Verified 2026-07-05: the cross-dataset sum inflated per-bill totals
  ~40%.*
- **Never sum filings without deduping — and dedup on `period_invariant_key`, not the type code.**
  Registrants file duplicates (identical Senate Q1s 22 seconds apart) and amendments (Senate
  `filing_type` `1A`/`2A`/…; House refilings under new `filing_id`). Filtering `filing_type LIKE 'Q%'`
  **silently drops amendments.** Dedup on `filing_period` (constant across original + amendment, e.g.
  "second_quarter" for both `Q2` and `2A`), pick latest by `posted`/`filing_id`. Apply *identically*
  on both chambers. Canonical pattern: `queries/sweep_2026.sql#H1c`. *This bit twice (2026-07-04,
  2026-07-06): both times a type-code filter fabricated a cross-chamber "mis-reporter" pattern.*
- **`house` dumps are partial snapshots.** House 2026-Q1 holds 12,656 filings vs 21,145 senate Q1s
  (deadline-week flood missing). A filing absent house-side is expected noise, not a story. `senate`
  is the completeness reference for recent quarters.
- **`attribution_grain` is filing-level.** A filing that names several bills/issues attributes its
  **whole** income to each, so per-item dollars are a **ranking signal, not a total**. For exact
  client dollars, use `v_client_canonical_spend` (§4). *This is why press/bill "loudness" counts are
  read as facets, and only compared within the same press vintage (§1) — raw counts across vintages
  are not comparable.*
- **Terminations are DECLARED, never inferred.** The end of an engagement is a senate
  `filing_type` in the termination family `^[1-4](T|TY|@|@Y)$` — "N Quarter - Termination
  [Amendment][(No Activity)]"; 18,292 filings corpus-wide, with the exact `termination_date` in
  the raw record (not loaded; resolve via `show_record.py`). Never infer termination from
  absence-between-quarters — late posting and partial house dumps fabricate exits. Detect by
  **existence** of a T-family filing in the (pair, quarter) group while dollars still dedup on
  `filing_period`, so a later amendment can't hide the termination; house `form` is only LD1/LD2
  (no termination signal — senate-only lens). Terminations are seasonal: each Q4 2022–2025 runs
  22–43% above that year's other quarters (compare Q4 to prior Q4s). And pair "newness" must be
  grouped by resolved client entity, not `client_id` — a re-registration re-issues `client_id`
  and fabricates a "new" engagement (Checkmate/Gunvor 2025-Q4). *Verified 2026-07-10 (P3 build);
  cited form `queries/p3_turnover.sql` P3a–P3e.*

## 4. Entity resolution

Built by `lda-entity-resolver` (`resolve_entities.py`). House orgs have no UUIDs and no standardized
casing; they attach to senate entities only through the compound-key crosswalk, never fuzzy-merged.

| Table / view | Grain |
|---|---|
| `entities` | one resolved entity (registrant / client / foreign_entity), grouped by deterministic norm-key |
| `entity_aliases` | one raw name variant per dataset, with a sample raw-record pointer |
| `registrant_crosswalk` | one senate registrant+client engagement, matched to house (`confidence='id'`) |
| `v_client_canonical_spend` | one (client, year, quarter); the **P1** double-count fix |

- **The Senate↔House join key is house `<senateID>` = `"<senate_registrant_id>-<senate_client_id>"`**
  (compound, engagement-level; verified 2026-07-06). Join on both parts. Do **not** join senate
  `house_registrant_id` to house `<houseID>` — formats don't overlap (zero matches).
- **`client_id` is registrant-scoped, not global** — Comcast alone carries 10+ client ids. Group
  clients by resolved entity, never by `client_id`. Registrant ids **are** global.
- **Canonical client spend (P1).** A client lobbying in-house files as its own registrant and reports
  its **total** spend; outside firms it hires also file, reporting income already inside that total.
  Summing overstates (~12% corpus-wide for 2025). `v_client_canonical_spend` uses
  `greatest(inhouse, outside)`, never their sum, with every component exposed for audit. **Always
  aggregate client spend from this view**, never by summing filings directly.
- **Known ceiling:** where the resolver split one company's name variants (Payward/Kraken, a16z's
  several spellings), a player can under-count or appear twice. Documented limitation, not a silent
  gap (roadmap cleanup C / P6).
- **`entity_aliases` carries ONE ROW PER registrant-scoped `senate_id` per `raw_name`**, on the
  (kind='client', dataset='senate') slice — 41,532 rows vs 31,743 distinct name→entity pairs
  (avg 1.31x; ACLU alone is 8 rows). No raw_name maps to more than one entity_id, so
  `GROUP BY`/`count(DISTINCT ...)`/`QUALIFY` paths downstream of the join are safe — but any
  **per-row join with a naked `count(*)` or `sum()` fans out** and silently inflates. Caught by the
  pardons package's reconciliation checks (2026-07-10, player-filings index 198→360 rows) and again
  in the healthcare package's activity-share `acts` CTE (2026-07-11, PhRMA's `all_activities` read
  21,398 instead of 887 — a 24x inflation that also flipped 9 players across the 50%/20% share
  boundaries). Fix: join through a deduped subquery, never the raw table —
  `LEFT JOIN (SELECT DISTINCT raw_name, entity_id FROM entity_aliases WHERE kind='client' AND
  dataset='senate') ea ON ea.raw_name=sf.client_name`.

### 4b. People + political committees (P6 member layer)

Built by `lda-entity-resolver/scripts/build_members.py` from external sources (congress-legislators
+ FEC cm/ccl/cn bulk + one openFEC leadership-PAC sweep; briefs: `reference/congress-legislators.md`,
`reference/fec-campaign-finance.md`). Resolved at query time by the shared
`member_resolve.py` (imported by `lda_ld203_giving.py`'s member rollup).

| Table | Grain |
|---|---|
| `members_all` | one member serving in the corpus window (current AND departed), keyed `bioguide_id` |
| `member_terms` | one (term x party-affiliation period) — the party-as-of-date source |
| `member_committees` | one (committee, supported member), tier = campaign-committee / leadership-pac / jfc |

- **LD-203 recipient strings splinter per member** (five Emmer spellings understated him 35% until
  member-keyed merging, 2026-07-08); merge on `bioguide_id` via `member_resolve.py`, never on the
  raw string.
- **Rollup, never conflation:** committee tiers report separately; JFC / multi-honoree dollars stay
  `shared, unallocated`. Party committees + caucus institutions are never member-mapped.
- **Ambiguity is a report, not a merge** — same-name pairs (the Menendezes; Dan vs Sanford D.
  Bishop) return multiple matches; `SEN.`/`REP.` titles disambiguate by chamber (verified
  2026-07-09; the old package matcher conflated both pairs).
- These tables' raw-record pointer is the cached external download (`src_file` + fetch date in
  `out/congress_legislators_cache/` / `out/fec_cache/`), not a corpus record.

## 5. Free-text / discovery surface

- **`lobbying_freetext`** (+ FTS) — Senate activity descriptions + House `specific_issues` unioned into
  one BM25-searchable doc surface, each row keeping a `record_key` + `sub_index` (still resolvable via
  `show_record.py`). Built with `stemmer='none'`; **discovery-only**.
- The *cited serving* layer is the deterministic keyword tagger `lobbying_issue_mentions` (built from
  `industry_lexicon.json`), the mirror of `press_issue_mentions` on the lobbying side. Discovery
  (FTS/keyness) only *proposes* vocabulary; only curated keywords tag. This split keeps findings
  auditable while vocabulary discovery scales.

## 6. External money regimes

| Regime | Where it lives | Attribution boundary |
|---|---|---|
| `ld203` | **In the project DB** (Senate LD-203 contribution reports, loaded by `build_db.py`) | **Registrant-filed**, never client-attributable. Semiannual; early-year files legitimately tiny. **LD-203 ≠ FEC** — say "disclosed LD-203 giving," never "total." |
| `fec` | **External** (openFEC API), fetched live + cached to `out/fec_cache/` (committed since 2026-07-11 — the cache is the citeable evidence; only `out/.fec_api_key` stays gitignored) | Committee-filed receipts. A *different universe* from LD-203 — look for gaps, not equality. Full traps in `reference/fec-campaign-finance.md`. |

The two are complementary halves of an industry's "who do they give to" — LD-203 is the disclosed
lobbyist-side slice; FEC carries the Super-PAC money LD-203 cannot see.

## 7. Lexicons & crosswalks (user-updatable)

The "what the user has found" layer — versioned dictionaries the investigator grows as they learn,
without touching any SKILL.md. Each carries a `_meta` block with its discipline and version.

| File | Teaches |
|---|---|
| `skills/lead-scanner/scripts/industry_lexicon.json` | industry → distinctive free-text phrases (the CRYPTO facet, etc.); tags `lobbying_issue_mentions` |
| `skills/lead-scanner/scripts/bill_aliases.json` | named bill → H.R./S. number crosswalk; bridges press names ↔ filing numbers |

Discipline (both): **precision over recall**; a discovered term is a *candidate* until a human adds it
with a source and bumps the version. See each file's `_meta.discipline`.

## 8. Everything else self-reported

- Strip whitespace everywhere; expect missing income/expenses; treat gaps as **potentially
  reportable**, not noise.
- House XML uses `<alis><ali_info>` with `<issueAreaCode>` (not the manual's `ali_Code` flat list);
  `<federal_agencies>` is one comma-separated string per ali_info; House forms pad with empty
  `<lobbyist>` slots (skip rows with no first and no last name). *Verified 2026-07-04.*
- **Press and filings name bills differently** — members write "the Farm Bill" / "NDAA"; filings cite
  H.R./S. numbers. Number-only matching fabricates "lobbied but publicly silent" bills (killed L004).
  Bridge via `bill_aliases.json` (§7).
- Windows: scripts force UTF-8 stdout (press text has curly quotes; pipes default to cp1252).
