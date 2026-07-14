---
name: industry-review-packager
description: Generate or regenerate a full industry review package (data CSVs + interactive dashboard + README skeleton + zip) from the built lobbying-disclosure DuckDB and one per-industry spec file. Use when an industry map needs to ship as a reviewable package, or when the corpus advances and existing packages need regeneration. One command per package; chart-vs-data reconciliation mismatches fail the build.
model: sonnet  # deterministic spec-driven builds + regression triage; the editorial copy lives in the spec, written before this skill runs — mid-tier is the right spend
---

# industry-review-packager

One command turns a per-industry **spec file** into a complete review package:

```
python skills/industry-review-packager/scripts/lda_package_industry.py \
    skills/industry-review-packager/specs/<pkg>.json
```

Output at `out/packages/<id>/`: `data/*.csv` (every row carries a citation key —
senate `filing_uuid`, press `src_file:src_line` — plus public lda.senate.gov URLs),
an interactive dashboard (`<id>_dashboard.html`, light/dark, per-widget "View
query info" showing the exact SQL executed; facet-lens and legacy `viz_build`
dashboards also click-through to raw records — see "Dashboards" below for the
one lens that doesn't), a README (generated only if none exists), and a dated zip.

Prerequisites: the built DuckDB (`lda-corpus-loader`), entity tables
(`lda-entity-resolver`), and — for facet-lens packages — the serving table
(`lead-scanner`'s `lda_industry_map.py --build-tags`). The `lda_` script prefix
marks this dependency.

## Two lenses

| lens | scope | example |
|---|---|---|
| `facet` | filings tagged in `lobbying_issue_mentions` for one curated `industry_lexicon.json` tag — for industries hidden in the free-text across many issue codes | crypto, pardons, critical-minerals |
| `issue_codes` | filings whose senate activities carry the spec'd ALI codes — for code-visible industries | healthcare (HCR/MMM/PHA/MED), transportation (TRA/AVI/RRR/TRU/MAR/ROD) |

## What the spec carries (human-owned) vs what the script does

The spec carries everything editorial: title/subtitle, **KPI copy** (values are
human-verified numbers — reconcile them against the fresh CSVs after a corpus
refresh), **caveat prose**, **per-widget card copy**, roster/class hand-triage
file paths, module flags, giving slices. The script only assembles. Lexicon
facets stay in `industry_lexicon.json` under its own discovery→human-triage
discipline; class triage lives in a versioned JSON beside the specs
(`specs/pardons_class_triage.json` is the pattern).

## Invariant core (written once, guards baked in)

Every export honors the corpus bindings in `reference/corpus-profile.md`:
senate-primary (never sum chambers); amendment dedup on
(registrant, client, year, `filing_period`) latest-by-posted; registrations
excluded from dollar work; client spend only via `v_client_canonical_spend`;
the **§4-safe `entity_aliases` join** (always through a `SELECT DISTINCT`
subquery — the naked join fans out and has shipped real defects twice);
terminations only from the declared `^[1-4](T|TY|@|@Y)$` filing-type family.
All ORDER BYs carry tiebreakers, so output is deterministic and
regression-diffable (several legacy exports were not — ties reshuffled per run).

Standard exports: players (entity-resolved; optional name-visibility tiers or
class triage), raw-filing index, quarterly trend + per-quarter click-through,
issue-code scatter, keywords, registrant firms, press quarterly + releases,
QA record samples, roster (own full-DB query — **never** derived from the
players export, which may be LIMITed on a different axis), LD-203 giving per
spec slice via `lda_ld203_giving.py` (the P6 member rollup rides along as
`*_ld203_member_rollup.csv`).

Optional modules (spec flags): `engagements` (pardons-style engagement/
termination table), `activity_share` (issue-code lens; share computed on
ACTIVITY rows, never filings), `spend_quarters` + `scatter_filings`
(click-through audit indexes), `bills`, `fec` (openFEC reconciliation via
`fec_enrich.py`; key from env only, cache-backed; falls back to passing the
baseline CSVs through).

## Reconciliation gates are BUILD FAILURES

Trend chart == click-through counts per quarter; per-player filing counts ==
raw-filing index; press chart == release list; spend bars == quarter sums;
giving by-year == deduped total. Any mismatch aborts with non-zero exit.
The headless-Edge render check (light + dark) also **fails on any page JS
error** via an injected `onerror` probe — a screenshot-size check alone passes
a half-rendered page (that exact failure happened during this skill's build).

## Dashboards

`build_dashboard()` dispatches on `lens.type` (not the spec's `assembly` field,
which only opts OUT to the legacy path — see below): `facet` lens →
`assemble_facet()` + `viz/facet_page.js`; `issue_codes` lens →
`assemble_codes()` + `viz/codes_page.js`. Both are generic, spec-copy-driven,
and reconciliation-safe; new packages of either lens get a working dashboard
for free. `page_js` in the spec overrides the default file if a package wants
a bespoke page (see `viz_build` below).

- **facet lens** (`viz/facet_page.js`) — player bubble map (click-through),
  optional engagements, quarterly trend (click-through), issue-code scatter,
  vocabulary, registrant firms, optional top-spenders, optional LD-203 giving,
  press share (click-through). Click-through is backed by this lens's own
  per-filing indices (`player_filings`/`trend_filings`/`press_releases` CSVs).
- **issue_codes lens** (`viz/codes_page.js`) — KPI tiles, player spend×activity-
  share scatter (log-x spend, y = activity share, size = tagged filings; a
  top-150-by-filings ∪ top-30-by-spend selection keeps the chart legible at
  this lens's scale while the table view stays the full roster), quarterly
  trend, per-code trend (one line per spec'd ALI code), registrant firms,
  optional bills, press-coupling (share + canonical spend), optional LD-203
  giving. **No per-filing click-through, except press** — this lens's
  exporter (`run()`) never produces the `player_filings`/`trend_filings`
  indices the facet lens has, so those widgets stay a reconciled aggregate
  chart + a full table view only (the same no-click-through precedent as the
  facet page's own registrants/keywords/giving widgets). Press IS backed by a
  per-filing index (`x_press_releases_codes()` → `{p}_press_releases.csv`),
  so the press-coupling chart clicks through to the actual releases, same as
  the facet lens. `write_readme()` is lens- and assembly-aware about this
  (`has_click_through` / `has_press_click_through` — never claims
  click-through a dashboard doesn't have).
- `assembly: "viz_build"` — the legacy bespoke assemblies
  (`out/packages/_build/viz_build.py` + `viz/crypto_page.js` / `hc_page.js`),
  kept for the crypto/healthcare dashboards' bespoke widgets (including
  click-through backed by bespoke fresh DB queries at dashboard-build time,
  beyond what the generic exporters produce). The shared templates
  (`template.html`, `shared.css`, `lib.js`, all page JS) live in this skill's
  `viz/` — every assembly path reads the same copies.

## Regeneration and regression

`out/` packages are committed, so a regeneration is directly diffable in git.
For a side-by-side regression, use `--out-root <scratch>` (one root **per
package** — the legacy viz_build assembly reads sibling packages' CSVs and
falls back to the default root only for files absent under the scratch root)
and compare with `tests/pkg_acceptance.py`. Known benign diff classes vs
pre-skill baselines: tie reordering (legacy exports lacked tiebreakers),
LIMIT-boundary tie membership (e.g. a 7-way tie at 51 filings for the last 3
healthcare roster slots), canonical-name label vintage on resolver-split
entities, and `matched_keywords` aggregation order. Passthrough files
(giving-split / P6 variant audits — products of the pre-P6 enhance/retrofit
pipeline) are copied from the baseline, not regenerated.

Scratch-mode safety: with a non-default `--out-root`, the roster is written
under `<out-root>/_rosters/` instead of overwriting the committed `out/` roster.
