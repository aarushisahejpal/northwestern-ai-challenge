# reference/ — corpus profile + dataset orientation briefs

Two kinds of file live here.

## Corpus profile — the binding layer the skills read

`corpus-profile.md` is the single source of truth for **this corpus's** "facts that bite" — the
table names, citation-key formats, dedup key, mirror-source / primary-for-dollars rules, and
attribution grain that the (corpus-agnostic) SKILL.md files reference by field name. To point the
same skills at a different corpus, copy this file and refill it; the SKILLs don't change. Update a
corpus fact in one place: here.

## Dataset orientation briefs — external-data traps

Task-tailored background on **external** datasets, produced by `skills/dataset-primer`. Each brief
answers "how does this data actually work, and what will silently corrupt my results?" for one data
source, on a fixed method (five search axes × a nine-category data-quality checklist).

**Working aids, not submission artifacts** — they may reference internal context and are not cited by
findings. Before researching a dataset you haven't worked before, check here first; refresh an
existing brief rather than re-researching from zero.

| Brief | Dataset | Informs |
|---|---|---|
| `fec-campaign-finance.md` | FEC campaign finance (openFEC API + bulk) | `skills/lead-scanner/scripts/fec_enrich.py`, LEDGER L031 |
