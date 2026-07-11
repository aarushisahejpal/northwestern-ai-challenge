# Options memo — representing crypto money for diversified mega-filers

**For:** Rob · **Date:** 2026-07-11 · **Status:** design memo, read-only session — no dashboard,
export, or DB changes. All numbers below were computed live from `db/lda_full.duckdb` (read-only)
and the shipped package CSVs; probe-grade numbers are flagged where name-matching was approximate.
Nothing here is a finding; this is a display/method decision.

## The problem, restated with the worked example

The crypto map is recall-first: one matched lexicon phrase tags a filing. Correct for recall, but
the dashboard then attaches **organization-scale** numbers to that tag. The U.S. Chamber of
Commerce (`CHAMBER OF COMMERCE OF THE U.S.A.`, entity `client:146969`):

- **14 crypto-tagged filings** across 13 of 17 quarters → passes the ≥8 "core" tier and the
  sustained-filings map selection.
- Its bubble is sized by **$311.61M** total all-issue canonical spend — the largest object on the
  map (next: Visa $39.28M, ABA $34.73M, SIFMA $32.87M; Coinbase is $15.05M).
- But only **19 of its 555 senate activity blocks (3.4%)** are crypto-tagged. The worked filing
  `4d712cd3` (2024-Q4, $22.41M) is tagged by **one** "digital asset" mention in its TAX block
  (the IRS broker-reporting rule) — 1 of 29 blocks in that filing.
- In the giving view, its **$1.36M** disclosed LD-203 (907 items) sits inside the
  "diversified core" slice ($110.7M), i.e. inside a chart titled around crypto.

Two structurally different legs, per the healthcare precedent (DECISIONS 2026-07-08: filing-level
share is a self-filer artifact; the Chamber read 100% on filings, 5.4% on activity rows):

---

## Option A — Publish a crypto **activity-share** metric (healthcare parity) + an intensity badge

**What it is.** Mirror `export_healthcare.py`'s activity-share exactly, on the crypto side:
`crypto_activity_share_pct` = distinct crypto-tagged senate blocks / all senate activity blocks
for the resolved client (non-registration filings, senate-primary — numerator from
`lobbying_issue_mentions` tag='CRYPTO', denominator from `lobbying_freetext` dataset='senate').
Add the column to `crypto_players.csv`, the player table, and every click-through row; keep the
filing-count tier for selection but add a share **band badge**: `dedicated ≥25% · engaged 5–25% ·
ambient <5%`.

**Chamber worked example.** Chamber 3.4% (ambient) vs Coinbase 94.8%, Ripple 100%, Block 70.7%,
Robinhood 75.0%, PayPal 24.6%, Citigroup 16.4%, SIFMA 15.6%, Visa 10.4%, ABA 5.8%, AARP 2.5%,
ICI 2.2%. Two facts the metric surfaces that the current display hides: (1) the Chamber's
crypto-forward arm files separately as `U.S. CHAMBER OF COMMERCE - C_TEC AND CCMC` — 8 crypto
filings at **33.3%** share ($530K) — so the family's real crypto desk is visible at the sub-entity;
(2) the Chamber's main entity had **zero** crypto-tagged blocks in all four quarters of 2025 —
the industry's breakout year — returning in 2026-Q1 (stablecoins). "Core tier" currently flattens
all of that.

**Band evidence for thresholds** (all 508 mapped players, share computable for 499): ≥50%: 242
players / $214M all-issue spend; 25–50%: 47 / $128M; 10–25%: 64 / $420M; 5–10%: 53 / $275M;
1–5%: 69 / $946M; <1%: 24 / $529M. 15 current *core* players sit below 5% share — the
Chamber/AARP/ICI class the tiers can't separate today.

**Cost.** Low (~half-day): one CTE mirrored from the healthcare export into `export_crypto.py`,
one CSV column, dictionary + query-info regeneration. Reconciliation gate: numerator ties to the
existing per-player tagged-block counts (`crypto_issue_code_filings.csv` grain); denominator
countable in the query-info SQL.

**Constraint risks.** Low. It's a count ratio over disclosed records, no dollars involved. Two
method traps to state on-chart: (a) **share is entity-grain** — resolver-split families diverge
(Mastercard's three entities read 58.1% / 17.6% / 9.2%); compute share at the same combined-family
grain the dashboard displays, or badge the family by its dominant entity with the note. (b) the
denominator mirrors healthcare's semantics (no amendment dedup; ratio is robust to it, but say so).

---

## Option B — Two-axis player map: **spend × share scatter** instead of the one-size bubble

**What it is.** Replace (or toggle alongside) the bubble map with a scatter: x = total all-issue
canonical spend (log), y = crypto activity share (Option A's metric), mark size = crypto-tagged
filings, selection rule unchanged (sustained crypto filings — a giant budget still doesn't buy a
spot). Click-through panels already exist (player filings + spend quarters). Requires A.

**Chamber worked example.** The Chamber moves from *biggest object on the map* to the bottom-right
"ambient giant" corner: ($311.6M, 3.4%). Coinbase sits top-center (94.8%, $15.05M); the
Visa/Citi/SIFMA incumbents form a legible middle band (10–16%); PayPal/Block/Robinhood sit high
(25–75%). Nothing is hidden — the Chamber stays on the map with its real spend — but size no
longer asserts crypto-ness. The single number that justifies this: **93 of 499 mapped players sit
below 5% share yet carry $1.47B of the $2.51B total mapped spend (59%)** — the current
dollar-sized display is dominated by low-intensity money.

**Cost.** Moderate (~a day): one new widget in the house viz frame, dataviz-skill pass,
reconciliation of both axes to existing CSVs (spend already reconciles; share from A).

**Constraint risks.** None on the hard list — both axes are disclosed dollars / derived counts, no
model, nothing summed across regimes. Display risk only: 500+ points needs top-N labeling and the
same family-grain caveat as A.

---

## Option C — "Crypto-attention dollars" (spend × share) — **evaluated; do not publish**

**What it is.** A per-quarter model: `canonical_spend × that quarter's crypto block share`, summed.
It is a MODEL (uniform-attention-per-block assumption), not a disclosure.

**Chamber worked example.** 2024-Q4: $22.41M × (1/29) = **$772,759** modeled attention vs $22.41M
displayed today. Full window: **$11.23M** modeled vs $311.61M disclosed (~3.6%). Sanity property:
for pure-plays the model converges to disclosure (Coinbase $14.43M modeled vs $15.05M disclosed),
so it changes nothing where the current display is already right.

**Cost.** Trivial to compute; expensive to present safely — separate model-only CSV with a
`modeled_` prefix and an assumptions header, its own widget, never a sortable column next to
disclosed dollars.

**Constraint risks. Highest of the four — this is why I'd hold it.** Even labeled, "$11.2M Chamber
crypto spend" is the number a reader will quote, and the uniform-per-block assumption is known-false
(one TAX-block mention ≠ 1/29 of a $22.4M quarter's effort). It brushes directly against "no
allocation model blended with disclosed dollars" and "every displayed number reconciles to raw
records" — a modeled dollar reconciles to an *arithmetic*, not a record. Useful internally as a
triage ranking; as a published number it converts a recall tool into a fake precision claim.

---

## Option D — Giving leg: **intensity-gated three-tier giver split**, FEC promoted as the only issue-attributable money

**What it is.** LD-203 can never be issue-split (law, not data), so the only levers are who is in
the view and how it's framed. Re-cut the giver split using Option A's share table into three
tiers: **crypto-native** (the 105 hand-triaged, unchanged, $6.37M) · **crypto-forward
diversified** (diversified core with ≥5% activity share) · **ambient** (<5% — shown as a greyed
context band or dropped from the crypto package view, stated either way). Same legal posture as
the existing two-way split — it changes who appears under a crypto heading, not what the dollars
mean; "who funds whom, never why" caption stays.

**Chamber worked example (probe-grade name matching; diversified-core total reproduced $110.3M vs
README $110.7M, within 0.4%).** Bucketing the diversified core's LD-203 by giver share:
≥50%: $5.84M (5 orgs) · 25–50%: $11.54M (12) · 10–25%: $32.61M (18) · 5–10%: $21.49M (8) ·
1–5%: $38.83M (11). A ≥5% gate keeps **$71.5M (65%)** and moves **$38.8M** to the ambient band —
including **AARP ($7.96M)** and the **Chamber ($1.36M)**, which exit the crypto giving story.
(A ≥10% gate would keep $50.0M / 45%.)

**Plus one framing move, zero new data:** the FEC panel already shows the only clean,
issue-attributable crypto money — Fairshake is single-issue — and the probe confirms **all 12
nonzero Fairshake-network contributors are crypto-native; zero diversified-core mega-filers appear**
(no Visa, no banks, no Chamber). One caption line on the giving view — *"the issue-attributable
money (single-issue Super-PAC network, FEC) comes entirely from crypto-native orgs; the diversified
slice's giving is organization-level and not crypto-attributable"* — says the true thing the
charts currently make the reader infer. LD-203 ≠ FEC stays intact: framing, never summing.

**Recipient-side sub-options — evaluated, not recommended now:**
- *Committee-relevance flags* (e.g. "recipient sits on House Financial Services"): **the data does
  not exist in the DB.** P6's `member_committees` carries campaign-committee / leadership-PAC / JFC
  support tiers (869/693/742 rows), not congressional committee assignments. Building it means a
  new external source (congress-legislators committee-membership YAML is current-congress-only;
  historical assignments for departed members like Toomey are a known gap) → a dataset-primer +
  build session, not a package tweak.
- *Recipient press salience* (member's own crypto share of press releases): in-corpus and cheap,
  but coverage is patchy exactly where it matters — Emmer 39/291 releases (13.4%) and Lummis
  38/247 (15.4%) work, but French Hill has only 16 releases in the corpus, Hagerty 7, Torres 6.
  Usable as a tooltip annotation *with n shown*; not as a filter or ranking.
- *Timing vs crypto bill moments*: implies causation LD-203 can't support; skip.

**Cost.** Low–moderate (~half-day, after A): one roster cut from the share table, rerun
`lda_ld203_giving.py` per slice, `crypto_ld203_recipients_split.csv` gains a tier column, audit
CSVs + member rollup regenerate; the retrofit regression harness pattern (retrofit_p6.py) already
exists for verifying the re-cut reproduces current rows.

**Constraint risks.** Moderate-low. The 5% threshold is an editorial cut — disclose it on-chart and
in the README exactly as the 105-name hand-triage is disclosed today; band membership inherits the
family-grain caveat from A. No dollars change meaning; no regimes mix.

---

## Recommendation

**Build A + B + D's ≥5% gate as one package revision; hold C** (keep it, unlabeled and unshipped,
as an internal triage ranking only). A is the metric, B is the display that makes the metric do
the work, D reuses A's share table on the giving leg — one build, three fixes, and every published
number remains a disclosed count or disclosed dollars reconciling to raw records. The Chamber then
reads correctly everywhere: on the map as an ambient giant (3.4% share, $311.6M all-issue), in
giving as context outside the crypto story ($1.36M, ambient band), with its actual crypto desk
(C_TEC, 33.3%) visible — and Coinbase's numbers don't move at all.

Threshold to decide: the gate at **≥5%** (keeps $71.5M diversified giving) vs **≥10%** (keeps
$50.0M). I'd take 5% — it tracks the healthcare package's Chamber precedent (5.4% read as
"side-desk", not "player") and drops the AARP/Chamber class without amputating the genuine
bank/card-network crypto desks (ABA sits at 5.8%).

## Probe provenance (for re-derivation)

Share semantics mirror `out/packages/healthcare/_build/export_healthcare.py`'s `acts` CTE with the
numerator swapped to `lobbying_issue_mentions` tag='CRYPTO' (senate side, `filing_type NOT LIKE
'R%'`, DISTINCT-alias join per the entity_aliases fan-out trap, corpus-profile §4). Giving buckets
matched `crypto_ld203_core_by_org.csv` filer orgs to mapped players by normalized name
(pure-play filter = `out/crypto_roster_pureplay.txt`); 0 orgs unmatched, total within 0.4% of the
shipped split. Worked filing verified: `4d712cd3-e92c-4dc9-9d3f-9b3eb7773a40` = 29 senate activity
blocks, 1 crypto-tagged (sub_index 23, keyword "digital asset", TAX block). Fairshake check read
`crypto_fec_superpac_vs_ld203.csv` as shipped.
