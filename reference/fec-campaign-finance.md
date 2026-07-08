# FEC Campaign Finance — Dataset Orientation Brief

> **What this is.** The orientation brief for FEC campaign-finance data, produced by
> `skills/dataset-primer`. It informed `skills/lead-scanner/scripts/fec_enrich.py` (the crypto
> Super-PAC money leg, LEDGER L031) and stands as the reference for any future FEC work. It captures
> (a) how the FEC contribution data actually works, (b) the data-cleanliness / reporting-standard
> traps to test *before* trusting any rollup, and (c) the curated open-source libraries, guides, and
> datasets to reference. Read it top-to-bottom before writing a query. Every trap below is a
> hypothesis to test against a real sample — not a fact to trust.

---

## 0. The task this brief was written against

Enrich the crypto player roster (`out/crypto_roster.txt`, from the P4 industry-map tool) with
**FEC Schedule A receipts** and reconcile them against **LD-203 disclosed giving** (`ld203_giving`
table).

Concretely:
1. Resolve **Fairshake + affiliated committees** (Defend American Jobs, Protect Progress, …) via the
   openFEC `/committees` endpoint.
2. Pull **who gave money *into* those committees** (Schedule A / receipts).
3. Reconcile that against `ld203_giving` — the goal is to surface the **Super-PAC money that LD-203
   cannot see**, not to make the two ledgers equal.

### Non-negotiable framing
- **LD-203 ≠ FEC.** LD-203 is registrant-filed, semiannual, self-reported lobbyist/PAC giving. FEC
  Schedule A is committee-filed receipts. They are **different universes**; you are looking for
  *overlap and gaps*, not equality. Report FEC figures as **"disclosed," never "total."**
- **Most of the crypto corporate money is NOT in the individual-contributions file.** See §2 — this
  is the single biggest structural trap.

---

## 1. Access & credentials

- **API-first via openFEC** (RESTful, JSON). Requires an `api.data.gov` key.
- **Key handling (hard rule):** read the key from an **environment variable**. Never commit it, never
  write it into a trace/ledger, never echo it into logs.
- **Rate limit:** ~1,000 calls/hour per key; 100 results/page — page accordingly and be polite.
- **Cache raw JSON** to a **gitignored** `out/fec_cache/` so re-runs don't re-hit the API and results
  are reproducible. `/out/` is already in `.gitignore`.
- Live API + interactive Swagger: <https://api.open.fec.gov/>
- Endpoints in play: `/committees` (resolve Fairshake + affiliates), `/committee/{id}/history`
  (affiliation lineage), `/schedules/schedule_a` (receipts in), `/committee/{id}/totals`
  (published-total reconciliation).

---

## 2. The structural gotcha that bites first: IND vs ORG

FEC bulk data splits receipts into separate files, and the API mirrors the same entity distinction:

| File / entity | What it holds |
|---|---|
| `indiv` (entity type **IND**) | Contributions from **individuals** |
| `pas2` | Committee → candidate contributions |
| `oth` / `itoth` (**ORG/COM/PAC/CCM**) | **Everything else — corporations, LLCs, and PACs giving to a committee** |

**Fairshake's Coinbase / Ripple / a16z checks are corporate/LLC contributions → they land in `oth`,
not `indiv`.** If you filter Schedule A to individuals only, you will *silently drop the exact players
you care about.* Confirm this against the official file descriptions and pull a sample that includes
ORG contributor rows before writing the loader.

---

## 3. Data-quality issues to actively test (before trusting any rollup)

Test each against a **small real Fairshake sample** first:

| Issue | Why it distorts the reconciliation | Reference |
|---|---|---|
| **Memo-code double-counting** (`memo_cd` = `X`) | Conduit/earmark pass-throughs (e.g. ActBlue) appear as memo rows. Drop them → you lose donor identity; keep them → you double-count topline totals. **Decide per question, document which.** | IRE PDF; FEC conduits page |
| **Amended filings / duplicate transactions** | Bulk data ships *every* amendment version; you must keep only the latest to avoid dup transactions. Confirm how the **API** handles this for your endpoints. | FEC "About data"; rebuilding-a-data-file |
| **IND vs ORG split** | Corporate crypto money is in `oth`, not `indiv` — easy to miss entirely (see §2). | File descriptions |
| **$200 itemization threshold** | Sub-threshold giving is aggregated and un-attributable to a named entity. Fine for Fairshake (large checks) but state it as a floor. | Individual-contributions file description |
| **Free-text name / employer / occupation** | "Coinbase" vs "Coinbase Global, Inc." vs "Coinbase Inc" — the core **entity-resolution** problem when matching FEC contributors to the roster. | DIME methodology; Medium post |
| **Committee affiliation / linkage** | Fairshake ↔ Defend American Jobs ↔ Protect Progress must all be resolved or you miss money. | openFEC `/committees`; ProPublica writeup |
| **Refunds / redesignations / negative amounts** | Net vs gross totals differ; naive `SUM()` overstates. | IRE PDF; file descriptions |
| **Paper-report precedence** | If electronic data and the paper report disagree, the paper report is authoritative — flag, don't silently trust. | FEC "About data" |

---

## 4. Curated resources

### Tier 1 — Primary / authoritative (ground truth; read first)
- **About campaign finance data (FEC)** — data overview, update cadence, paper-precedence rule.
  <https://www.fec.gov/campaign-finance-data/about-campaign-finance-data/>
- **Contributions by individuals — file description (FEC)** — column-by-column dictionary.
  <https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/>
- **Browse data index (FEC)** — links to the `oth`, committee-master (`cm`), and other file
  descriptions. Confirm the IND/ORG split here. <https://www.fec.gov/data/browse-data/>
- **openFEC API docs / live Swagger** — primary access path. <https://api.open.fec.gov/>
- **openFEC GitHub** — issues/README document quirks the polished docs don't.
  <https://github.com/fecgov/openFEC>
- **Contributions received through conduits (FEC)** — authoritative memo-entry / earmark rules (the
  #1 double-counting trap). <https://www.fec.gov/help-candidates-and-committees/filing-reports/contributions-received-through-conduits/>

### Tier 2 — Open-source libraries & tools
- **libfec** (Alex Garcia) — modern CLI, parses `.fec` → CSV/JSON/**SQLite**; good fit for a DuckDB
  pipeline. <https://github.com/asg017/libfec>
- **fecfile (PyPI)** — pure-Python `.fec` parser; itemizations grouped by schedule.
  <https://pypi.org/project/fecfile/>
- **Fech** (NYT, Ruby) — battle-tested; its docs enumerate the malformed-data cases (bad quotes, row
  drift). <https://nytimes.github.io/Fech/>
- **OpenSecrets parsefec** — the actual loader OpenSecrets used; reference for DB-load edge cases.
  <https://github.com/opensecrets/parsefec>
- The openFEC service ships an OpenAPI/Swagger spec, so a plain `requests` client is fine — no
  third-party wrapper strictly required.

### Tier 3 — Practitioner guides & cleaned academic datasets (the "gotchas" knowledge)
- **IRE — "Finding & Analyzing / Mining FEC Data" (PDF)** — best hands-on gotchas doc: memo codes,
  amendments, conduits. <https://s3.amazonaws.com/ire16/campaign-finance/MiningFECData.pdf>
- **Knight Lab — "Tackling federal election campaign finance data" (NICAR16)** — Northwestern's own
  writeup. <https://knightlab.northwestern.edu/2016/03/13/nicar16-tackling-federal-election-campaign-finance-data/>
- **ProPublica — "Untangling a Web of FEC Data"** — how a serious newsroom models committees/filings;
  directly relevant to Fairshake-affiliate resolution.
  <https://www.propublica.org/nerds/untangling-a-web-of-fec-data>
- **Medium (A. Liguori) — "5 things I learned exploring FEC individual contributions"** — quick,
  concrete surprises. <https://medium.com/@alyssa.liguori/5-things-i-learned-exploring-the-fecs-individual-campaign-contributions-data-40d2072ffee9>
- **DIME — Database on Ideology, Money & Elections (Stanford / Adam Bonica)** — 130M+ contributions,
  **already entity-resolved** with contributor IDs. Two uses: (a) a benchmark to sanity-check your own
  name resolution, (b) its methodology papers are the state of the art on the FEC
  contributor-disambiguation problem. Do **not** ingest it as a data source. <https://data.stanford.edu/dime>
- **Northwestern Library — campaign-finance data guide** — curated index for more.
  <https://libguides.northwestern.edu/campaign/data>

---

## 5. Recommended sequence

1. Read the FEC file descriptions (individual + `oth` + committee-master) and the conduits page.
   Confirm the **IND/ORG split** and **memo-code** semantics.
2. Skim the IRE PDF and the ProPublica writeup for the gotchas that survive into the API.
3. Resolve Fairshake + affiliates via `/committees` and `/committee/{id}/history`.
4. Pull a **small** Fairshake sample via `/schedules/schedule_a`; stress-test every row in the §3
   table against real data before trusting the loader.
5. Reconcile vs `ld203_giving`; label FEC figures **"disclosed," not "total."**

---

## 6. Repo conventions the FEC work honors
- Generated rosters/intermediates → repo-root **`out/`** (gitignored). Never write outputs into
  `skills/`.
- Raw API JSON → **`out/fec_cache/`** (gitignored), for reproducibility. The cache + committee/
  transaction IDs are the citeable form — FEC data is external, not in the DB.
- API key from **env var only** — never committed, never traced, never logged.
- Log the work in `LEDGER.md` / `DECISIONS.md` per existing ledger conventions (done: L031).
- FEC data-provenance + disclosure note lives in **README §4**.
