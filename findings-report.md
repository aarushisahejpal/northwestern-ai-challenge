# Findings Report

Two findings were produced by running the included Agent Skills against the challenge
corpus. Both passed independent fresh-agent verification (protocol:
`skills/finding-verifier/SKILL.md`) before being locked (`DECISIONS.md`, 2026-07-15).
Full claim-by-claim detail, citations to specific filings, caveats, and appended
verification blocks live in each finding file.

## 1. The pipe-materials war — DIPRA's Q1 2026 spending spike
**File:** `findings/L010_pipe_materials_war.md`

In Q1 2026 the Ductile Iron Pipe Research Association nearly doubled its recent-quarter
lobbying spend ($315K/quarter 2025 average → $540K) to push "materials provisions" and
"domestic sourcing" language favoring iron pipe into five FY26 appropriations bills, a
TSCA reauthorization, and the NDAA — deploying former U.S. Rep. Martha Roby as a named
lobbyist — while the visible plastic/copper-pipe opposition spent a fraction of that, and
the only public trace of the fight is an unrelated grant announcement. Every dollar figure
cites a `filing_uuid` resolvable via `show_record.py`; the finding explicitly bounds what
it does NOT claim (no causation, no undocumented membership assertions).
**Investigative relevance:** a concrete, dated, single-quarter case of a materials
industry writing its preference into must-pass bills with no public counter-narrative.

## 2. Full-corpus Senate lobbying trends, 2022–2026 Q1
**File:** `findings/chris_full_corpus_trends_2022-2026.md` (authored by Chris Cioffi;
ported with provenance header; fresh-agent verified 8/8)

Highlights, each traced to raw filings: generative-AI firms arrive as a K Street client
class (Anthropic, OpenAI, a16z: $0 in 2022 → ~$3M each by 2025); tariff lobbying grows
+215% and — unlike the 2025 tax-bill issues — keeps climbing into 2026; Continental
Strategy grows ~65x on a real, verified client roster; a headline-sized "SAP America
spending collapse" is exposed as a single $130M data-entry quarter (amended to $640K one
day later); and a suspiciously exact $20,000,000-per-quarter filer (LOC Nation) is
flagged — independently corroborated by this repo's own pipeline (leads L025/L027).
**Investigative relevance:** dated markers of new influence industries, a live
trade-policy lobbying surge, and two cautionary data-integrity catches any journalist
citing this corpus needs.

## Cross-validation note
The two submitted pipelines (SQL and R) share no code but compute the same spend
discipline; where they diverged ($50K on one termination filing), the divergence was
traced to the single filing, ruled on by the team's domain expert, implemented, and both
pipelines now agree to the dollar (`DECISIONS.md`, 2026-07-15).
