# Data Manual

This dataset is stored under `data/`. Together the files cover congressional communications and the lobbying activity aimed at Congress from 2022 through Q1 2026. This manual describes the current on-disk layout, how to load the data, and where to start digging.

## Data layout

The `data/` directory is decompressed.

```
data/
  congress_press/
    2022/2022-01.jsonl ... 2022-12.jsonl
    2023/2023-01.jsonl ... 2023-12.jsonl
    2024/2024-01.jsonl ... 2024-12.jsonl
    2025/2025-01.jsonl ... 2025-12.jsonl
    2026-01.jsonl
    2026-02.jsonl
    2026-03.jsonl
  senate/
    2022/ 2023/ 2024/ 2025/ 2026/
    constants/
  house/
    2022_Registrations_XML/
    2022_1stQuarter_XML/ ... 2022_4thQuarter_XML/
    2023_Registrations_XML/ ... 2023_4thQuarter_XML/
    2024_Registrations_XML/ ... 2024_4thQuarter_XML/
    2025_Registrations_XML/ ... 2025_4thQuarter_XML/
    2026_Registrations_XML/
    2026_1stQuarter_XML/
```

## At a glance

| Dataset | Path | Format | Coverage | On-disk size |
|---|---|---|---|---|
| Congress press releases | `data/congress_press/` | JSONL (51 decompressed files) | 2022 – 2026-03 | 504 MB |
| Senate LDA filings & contributions | `data/senate/` | JSON (arrays, nested) | 2022 – 2026 Q1 | 2.2 GB |
| House LDA registrations & reports | `data/house/` | XML (409,650 decompressed files) | 2022 – 2026 Q1 | 5.9 GB |

All three are public records. Expect self-reported data, missing fields, and inconsistent conventions — part of the investigative work is reconciling them.

---

## 1. Congress press releases — `data/congress_press/`

**Description.** Press releases scraped from the official `*.house.gov` and `*.senate.gov` member websites. Each record is one release with light member metadata and the full body text.

**Scale.** ~48K releases in 2025 alone (≈478 members represented); the full 2022–2026-Q1 corpus runs larger. Average release ~900 words → tens of millions of words of unstructured text.

**Format.** Newline-delimited JSON (JSONL). One record per line. The full years 2022 through 2025 are split into year directories; the 2026 Q1 files sit directly in `data/congress_press/`.

```
data/congress_press/
  2022/
    2022-01.jsonl ... 2022-12.jsonl
  2023/
    2023-01.jsonl ... 2023-12.jsonl
  2024/
    2024-01.jsonl ... 2024-12.jsonl
  2025/
    2025-01.jsonl ... 2025-12.jsonl
  2026-01.jsonl
  2026-02.jsonl
  2026-03.jsonl
```

**Record fields.** `url`, `title`, `date`, `date_source`, `source` (member press-release index page), `domain`, `scraper` (scraper ID), `member` (`bioguide_id`, `name`, `party`, `state`, `chamber`), `text` (full body, newline-preserved).

**Source.** [Congress Press](https://thescoop.org/congress-press/)

**Timeframe.** 2022-01 through 2026-03. The 2026 files currently include January through March at the root of `data/congress_press/`.

**Load it.**

```python
import json
from pathlib import Path

root = Path("data/congress_press")

# Single month
with open(root / "2026-01.jsonl") as f:
    for line in f:
        rec = json.loads(line)
        print(rec["member"]["name"], rec["title"])

# Full decompressed year
for path in sorted((root / "2025").glob("*.jsonl")):
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            # ...
```

**Starting points.**
- Keyword and frequency analysis: who talks about a given issue, how often, and when does the language shift.
- Comparative messaging: same event, different party framing — pull all releases from a +/- 7-day window around a news event and cluster.
- Member activity baselines: releases/month per member; outliers often correlate with primary campaigns, committee news, or scandal cycles.
- Entity extraction: NER over `text` to pull companies, agencies, and bills — the output bridges naturally to the lobbying datasets via `bioguide_id` and entity names.

---

## 2. Senate LDA data — `data/senate/`

**Description.** Lobbying Disclosure Act filings submitted to the Secretary of the Senate: registrations, quarterly activity reports, and semiannual contribution (LD-203) reports. This is the "who is lobbying whom, on what, for how much" dataset.

**Scale (2025).** 108,225 filings, 39,438 contribution reports (with ~149K line items across them), 5,470 registrants, 28,246 clients. Earlier years are comparable.

**Format.** JSON arrays, deeply nested. Each filing includes its registrant, client, lobbying activities (with ALI issue codes and lobbyists), and government entities lobbied. Contribution reports include a `pacs` and `contribution_items` list.

```
data/senate/
  2022/ 2023/ 2024/ 2025/ 2026/
    filings/filings_{year}.json          # array of filing objects
    contributions/contributions_{year}.json
  constants/
    countries.json
    filing_types.json                    # RR, Q1..Q4, MM (mid-year), YE (year-end), etc.
    government_entities.json             # agencies/chambers lobbied
    lobbying_activity_issues.json        # 3-letter ALI codes (BUD, TAX, HCR, …)
    states.json
    lobbyist_prefixes.json
    lobbyist_suffixes.json
    contribution_item_types.json
```

**Key fields.** Filing: `filing_uuid`, `filing_type`, `filing_period`, `filing_year`, `income`, `expenses`, `registrant` (nested), `client` (nested), `lobbying_activities[]` (each with `general_issue_code`, `description`, `lobbyists[]`, `government_entities[]`). Contributions: `filing_uuid`, `filer_type`, `registrant`, `lobbyist`, `pacs[]`, `contribution_items[]` (with `type`, `amount`, `payee`, `honoree`, `contributor_name`).

**Source.** [Senate LDA API](https://lda.senate.gov/api/v1/) (`filings`, `contributions` endpoints).

**Timeframe.** 2022-01-01 through 2026-03-31 (2026 is Q1 only).

**Load it.**

```python
import json

with open("data/senate/2025/filings/filings_2025.json") as f:
    filings = json.load(f)           # list of dicts

print(len(filings), "filings")
f0 = filings[0]
print(f0["registrant"]["name"], "→", f0["client"]["name"])
for act in f0["lobbying_activities"]:
    print(" ", act["general_issue_code"], act["description"][:80])

# Decode issue codes using the constants file
issues = {c["value"]: c["name"]
          for c in json.load(open("data/senate/constants/lobbying_activity_issues.json"))}
```

**Starting points.**
- Top-of-funnel aggregates: biggest spenders by client, most-active registrants, busiest issue codes per quarter.
- Revolving door: the `covered_position` field on each lobbyist flags prior government roles — mine it for text patterns ("Chief of Staff to Sen. …").
- Foreign influence: filter on `foreign_entities[]` across filings; cross-reference with FARA.
- Contribution flows: `contribution_items[].payee` vs. `honoree` reveals who lobbyists and their PACs are funding. Join to FEC for validation.
- Data-quality stories: Many filings lack income data, expenses, and state info. The gaps are themselves reportable.

---

## 3. House LDA data — `data/house/`

**Description.** The House Clerk's parallel set of LDA disclosures. Registrations (LD-1) and quarterly activity reports (LD-2). Same underlying disclosure regime as the Senate data, different distribution format and slightly different schema.

**Scale (2025).** ~7,762 registrations + ~100,760 quarterly records ≈ 108K records, comparable to the Senate side. The full extracted House tree contains 409,650 XML files.

**Format.** One XML document per filing. Each reporting period is stored in its own directory.

```
data/house/
  2022_Registrations_XML/
    *.xml
  2022_1stQuarter_XML/ ... 2022_4thQuarter_XML/
  2023_Registrations_XML/ ... 2023_4thQuarter_XML/
  2024_Registrations_XML/ ... 2024_4thQuarter_XML/
  2025_Registrations_XML/ ... 2025_4thQuarter_XML/
  2026_Registrations_XML/
  2026_1stQuarter_XML/
```

Root element is `<LOBBYINGDISCLOSURE1>` (registrations) or `<LOBBYINGDISCLOSURE2>` (quarterlies). Filenames are numeric House filing IDs (e.g. `301642857.xml`).

**Key fields.** `organizationName`, `clientName`, `senateID`, `houseID`, `lobbyists/lobbyist[]` (with `coveredPosition`, `lobbyistNew`), `alis/ali_Code[]` (ALI issue codes — up to 9 slots, often sparse), `specific_issues/description` (free text, often naming specific bills and agencies), `income`/`expenses`, `governmentEntities`, `foreignEntities`.

**Source.** [House Clerk Lobbying Disclosure](https://disclosurespreview.house.gov/).

**Timeframe.** 2022-01-01 through 2026-03-31 (2026 = Q1 + registrations).

**Load it.**

```python
from pathlib import Path
import xml.etree.ElementTree as ET

path = Path("data/house/2025_1stQuarter_XML")
for xml_path in sorted(path.glob("*.xml"))[:5]:
    root = ET.parse(xml_path).getroot()
    org = root.findtext("organizationName", "").strip()
    client = root.findtext("clientName", "").strip()
    issues = [a.text for a in root.findall(".//alis/ali_Code") if (a.text or "").strip()]
    print(xml_path.name, "|", org, "→", client, "|", issues)
```

Expect a fair amount of whitespace-only text inside elements; `.strip()` everything. Many quarterly filings carry the same `senateID` as a Senate filing — that's the bridge between the two lobbying datasets.

**Starting points.**
- Senate↔House reconciliation: fuzzy-match on `organizationName`/`clientName` and validate with the shared `senateID`/`houseID`. Discrepancies between the two filings for the same engagement are newsworthy.
- Bill-level lobbying maps: `specific_issues/description` often names bill numbers (`H.R. 1234`) — extract and join against Congress.gov bill and vote data.
- Entity-resolution challenge: the House data has no UUIDs and no standardized casing; building a clean entity table across Senate + House is itself a deliverable.

---

## Cross-dataset leads

The highest-value questions require more than one of these:

- **"Say vs. pay":** For a member (keyed by `bioguide_id` in the press corpus), correlate press-release topics with lobbying activity targeting their chamber/committee around the same quarter.
- **Temporal lobbying–messaging coupling:** When quarterly lobbying spend on an issue spikes, does the language in press releases shift? Good test for causal-adjacent narrative work.
- **Entity graph:** Press-release NER → companies/orgs → Senate/House LDA registrants & clients → government entities lobbied → committees → members. The cross-walks are the investigation.

## Useful external enrichments

- [Congress.gov bulk data / API](https://www.congress.gov/help/using-data-offsite) — bills, votes, committee assignments, cosponsorships. Joins via `bioguide_id`.
- [FEC](https://www.fec.gov/data/) — campaign finance to ground-truth lobbyist contributions.
- [FARA](https://efile.fara.gov/ords/fara/r/fara_ws/api/bulkdata) — foreign-agent filings, complements the `foreign_entities` fields.
- [Federal Register](https://www.federalregister.gov/developers/api/v1) — regulatory outcomes of lobbying on specific rules.
