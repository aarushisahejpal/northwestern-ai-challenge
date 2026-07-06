# Press issue-frequency & lobbying–messaging coupling — method + findings

Companion to `queries/press_issue_coupling.sql`. Covers two data-manual gaps:
press **keyword/frequency analysis** (who talks about an issue, how often, when the
volume shifts) and the cross-dataset **temporal lobbying–messaging coupling** question
(does press volume on an issue track lobbying spend on that issue?).

## What was built

- **`press_issue_mentions(pr_id, issue_code, keyword, src_file, src_line)`** — press
  releases tagged with ALI issue codes, the press-side analogue of `bill_mentions`.
  Generated in `build_db.py`'s `load_press()` via `extract_issues()`, so a full rebuild
  reproduces it. Every row keeps the raw-record pointer (`src_file:src_line`, resolvable
  with `show_record.py`), same discipline as every other table.
- **`v_press_issue_quarter`** — distinct releases per (issue_code, filing_year,
  filing_period), on the *same* grain as `v_spend_by_issue_quarter` so the two join
  directly.
- **`backfill_press_issues.py`** — populates the table into an already-built DB from the
  stored `press_releases.text` + pointers (reusing the same `extract_issues`), so the
  full corpus need not be re-parsed from the 8 GB raw tree. Byte-identical to a rebuild.

Corpus-wide result: **399,229 mention rows across 44 issue codes; 113,133 / 141,332
releases (80%) carry at least one tag.**

## Keyword → ALI-code mapping (the load-bearing choice)

The vocabulary lives in `ISSUE_KEYWORDS` in `build_db.py` (single source of truth).
Principles: **precision over recall** — distinctive phrases, not bare topic words
(`"border security"` not `"border"`, `"national defense"` not `"defense"`); whole-word
boundaries; case-insensitive; interior whitespace flexible (matches across line breaks);
**each keyword maps to exactly one code** (asserted at build time) so every hit is
unambiguously attributable; a mention is deduped per release (one row per
`pr_id`/`code`/`keyword`), so volume metrics use `COUNT(DISTINCT pr_id)`.

Coverage is the ~44 codes congressional press actually discusses, not all 79 ALI codes.
The per-code keyword lists are in the source; the sanity distribution (`P0`) has HCR,
BUD, VET, LAW, AGR, DEF, IMM on top and the low-precision codes (INS, GAM, SPO, COM)
correctly at the bottom.

### Shaky / ambiguous mappings — caveats for downstream readers

These determine every count, so they are documented, not hidden (also in
`SHAKY_MAPPINGS` in `build_db.py`):

| mapping | why it's shaky |
|---|---|
| `tariff` / `tariffs` → **TRD** (not TAR) | ALI's `TAR` is narrowly "miscellaneous tariff bills"; filers file broad tariff/trade-war policy under `TRD`. Mapping press "tariffs" to TRD keeps the say-vs-pay join meaningful, but it is a deliberate reading, not a literal code match. |
| health cluster **HCR / MED / MMM / PHA / ALC** | Boundaries blur in prose. ACA "tax credits" tag both HCR *and* TAX; `prescription drug` → PHA but reads as HCR; `medicare`/`medicaid` → MMM; `opioid`/`fentanyl` → ALC though often framed as LAW or HCR. |
| tech cluster **CPI / SCI / TEC** | `artificial intelligence` → SCI, `semiconductor` → CPI, `broadband`/`spectrum` → TEC. Real releases blur these; treat as one loose "tech" bucket when reading trends. |
| `social security` → **RET** | No dedicated Social-Security ALI code exists; RET (Retirement) is closest but it is arguably WEL (Welfare). |
| `federal reserve` → **BAN**; `background check` → **FIR** | Fed could be MON; background-check assumes a firearms context (could be employment). |
| **INS** is flood/auto/property only | `insurance premiums` is overwhelmingly health-context, so it is deliberately *not* mapped to INS; INS is a weak, low-volume code. |
| **COM / SPO / GAM / ANI** | Low-precision breadth codes — included for completeness but noisy; small n. |

## Method: correlate SHARES, not raw counts (the confound that matters)

The raw press corpus **≈ quadruples** over 2022→2025 (~5.3k → ~24k releases/quarter) and
lobbying dollars drift up too. So *any* code with steady relative attention shows a high
raw-count correlation with spend that is **pure corpus growth**, not coupling. The
defensible metric is each code's **share** of that quarter's total (press-attention share
vs money share); shares cancel the common trend. `P2` correlates the two share series at
three shifts — concurrent, press-leads-spend (t→t+1), spend-leads-press (t−1→t). With
~17 quarters this is **exploratory, not inferential**.

### Headline results (share-based, `P2`)

- **Positive coupling** (attention share and money share move together): **TRD 0.88**,
  ENV 0.86, CAW 0.84, TRA 0.69, TEC 0.67, FIN 0.63, AVI 0.55.
- **Negative coupling** (they move *opposite* — a say-vs-pay divergence):
  **MMM −0.72**, LBR −0.57 *(but LBR bundles antitrust — shaky)*, RET −0.44,
  HCR −0.38, BUD −0.38, IMM −0.32.

## The two candidate leads (both citable, named actors on both sides)

**L027 — TRD (trade/tariffs): a real, *concurrent* coupling, but the obvious one.**
Attention and money share are flat 2022–2024, then both jump in 2025 (Trump-tariff era):
press share 1.2% → 3.8% (2025 Q2), spend share ~4.0% → 5.5%. Press side = Democratic
members reacting to tariffs (Durbin, Shaheen, Jeffries, Blumenthal, Warren); paid side =
Nippon Steel via Akin Gump ($1.2M, `744e3154-…`), Brown-Forman, Qualcomm. This is the
mechanically-dominant coupling — logged, but treated like a known category rather than a
novel find. (Watch one paid-side outlier: a lone $20M "LOC Nation" filing that looks like
a misreport — not cited.)

**L026 — MMM (Medicare/Medicaid): a real, strong *absence* of coupling.** The novel one.
Press-attention share is stable ~2–3% through 2024, then **more than doubles to 5.7% in
2025 Q2** — the top "loud press / quiet spend" divergence in `P3` — driven by a
coordinated Democratic messaging campaign against the reconciliation Medicaid cuts
(Durbin 35 releases, Jeffries 29, Warren 27, Katherine Clark 22 in 2025 Q2). Meanwhile
the lobbying-money **share falls every year** (9.09% → 7.55% of Q2 spend, 2022→2025, on
the *properly deduped* filing_period basis — robust to the naive view's known
double-counting). The paid side is steady healthcare-industry clients (hospital &
nursing-home associations, pharmacy college) — entirely different actors from the loud
press voices, moving on a different clock (industry logic, not the political calendar).

## Caveats a future reader needs

- `v_spend_by_issue_quarter` attributes filing-level income to *each* activity code, so
  multi-issue filings are counted under several codes and amendments are not deduped —
  read the **shape** of the trend, not the dollar level. Where a lead's magnitude matters
  (the MMM share decline), it was re-derived with the `filing_period` dedup and agreed in
  direction.
- Correlations rest on ~17 quarters — directional/exploratory only.
- The keyword tagger has no word-sense disambiguation; the shaky mappings above are the
  main false-signal risk (LBR's antitrust bundle, the health/tech clusters).
- Press coverage is not uniform: member scraping and volume grow over time — the reason
  the analysis is share-based rather than count-based.
