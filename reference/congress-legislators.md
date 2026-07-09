# congress-legislators (+ FEC committee linkage) — Dataset Orientation Brief

> **What this is.** Orientation brief for the `unitedstates/congress-legislators` dataset (and the
> FEC committee-master/linkage bulk files it joins to), produced by `skills/dataset-primer` in
> targeted mode. Written against the P6 build (person + political-committee resolver:
> `members_all` / `member_committees` / `member_resolve.py`). Every trap below is a hypothesis to
> test against a real sample — not a fact to trust.

---

## 0. The task this brief was written against

Build the member-resolution layer that LD-203 giving maps need:
1. `members_all` — every member serving in the 2022–2026 corpus window (current AND departed),
   keyed on **bioguide_id**, with nicknames, state, chamber, FEC candidate ids, and **party per
   term with dates** (mid-term switches must annotate correctly by date).
2. `member_committees` — committee → member(s) crosswalk, tier-labeled: campaign committee
   (designation A/P), leadership PAC (D), joint-fundraising committee (J).
3. `member_resolve.py` — shared resolver every tool imports; replaces the hand-typed retiree +
   nickname lists in the 2026-07-08 package build scripts.

### Non-negotiable framing
- **Rollup, never conflation.** A committee MAPS to its member with a tier label; direct and
  indirect support never silently sum.
- **Ambiguity is a report, not a merge.** Common last names (Scott, Brown) return candidates with
  confidence labels.

---

## 1. Access & licensing

- **congress-legislators** (unitedstates project): public domain (CC0 1.0). Stable raw downloads at
  `https://unitedstates.github.io/congress-legislators/legislators-current.yaml` and
  `legislators-historical.yaml`. **JSON variants exist at the same path with `.json`** — use those
  (no new pyyaml dependency). Cache raw downloads to gitignored `out/congress_legislators_cache/`
  with a fetch date; the cache is the citeable form.
- **FEC committee master + candidate-committee linkage** (bulk, no API key):
  `https://www.fec.gov/files/bulk-downloads/{yyyy}/cm{yy}.zip` and `ccl{yy}.zip` per 2-year cycle
  (pull 2022, 2024, 2026). Pipe-delimited, headerless; column dictionaries at fec.gov
  ("Committee master file description", "Candidate-committee linkage file description"). Cache to
  `out/fec_cache/bulk/`. openFEC API (key handling per `reference/fec-campaign-finance.md`) is the
  spot-check path, not the build path — bulk needs no key and is fully reproducible.

## 2. Structural traps (the ones most likely to bite THIS build)

1. **Party switches live inside a term, in `party_affiliations`.** A term has one `party` field,
   but switchers (Sinema D→I, Dec 2022) carry a `party_affiliations` list of dated periods covering
   the term. If you read only `terms[].party` you will annotate a 2022-06 Sinema item as the party
   of the *whole term* (whatever the file recorded last). Explode party periods into dated rows;
   fall back to the term's party only when `party_affiliations` is absent. **Verify on Sinema's
   actual entry before trusting the shape.**
2. **`id.fec` is a LIST, and may be incomplete.** One member ↔ several FEC candidate ids across
   cycles (House→Senate moves get a new id: H- vs S-prefix). Join committees through *all* of them.
   Members with no FEC id (rare, appointed/never-filed) simply get no committee rows — report,
   don't invent.
3. **The ccl linkage file covers all three tiers** — designations A/P (authorized/principal
   campaign committees), **D (leadership PAC)**, and **J (joint fundraiser)** are all linked to
   CAND_ID (verified against the FEC file description 2026-07-09). So member→committee comes from
   ccl joined to cm for names; no per-member API crawl. **Verify against known examples** (an Emmer
   leadership PAC; a Victory-Committee JFC) before trusting coverage. Note ccl is per-cycle:
   a JFC row appears in each cycle it was active; a candidate's ccl rows exist even in cycles
   they didn't run (linkage carries forward) — dedupe on (CAND_ID, CMTE_ID, tier).
4. **JFC participant lists via ccl are one row per participating candidate** — exactly the
   "attribute to every participant, unallocated" shape P6 wants. But ccl only links *candidates*;
   a JFC whose participants are party committees or leadership PACs (no candidate) will have no
   member rows — such JFCs stay unmapped (correct behavior, same as party committees).
5. **Name fields are display names, not legal names.** `first` may be a recognizable-name choice;
   `nickname` is a separate field; `official_full` only exists for members serving since 2012;
   `other_names` records legal name changes with dates. Build the alias set from ALL of:
   first/nickname/other_names + curated additions (versioned JSON).
6. **Committee names in cm are as-registered, ALL-CAPS, punctuation-variable** ("EMMER FOR
   CONGRESS" vs an LD-203 string "Emmer for Congress Committee"). Normalize both sides with the
   same key function; exact-normalized match first, then conservative prefix match — never fuzzy.

## 3. Data-quality checklist (instantiated)

| Category | Answer for this dataset |
|---|---|
| Coverage boundaries | legislators: complete back to 1789; split current/historical is arbitrary — **union both files, filter to terms overlapping the corpus window** (use term end ≥ 2021-01-01 for slack). ccl/cm: per-cycle files; pull every cycle in window. |
| Grain / double-counting | legislators: one entry per person, terms nested. ccl: one row per (candidate, committee, cycle) — dedupe across cycles or committees repeat. |
| Entity resolution | bioguide_id is the person key (watch `bioguide_previous`); FEC CAND_ID is the campaign key (several per person); CMTE_ID is stable. |
| Versioning / amendments | Files are maintained live on GitHub; cache the fetch with a date. cm/ccl regenerate; committees can change name mid-cycle (cm reflects latest). |
| Time semantics | Term `start`/`end` are service dates; `party_affiliations` periods are the party-as-of-date source. ccl `FEC_ELECTION_YR` is the cycle, not a service date. |
| Denominators | n/a here. |
| Suppression / privacy | None; public-domain civic data. |
| Authoritative vs derived | Bioguide (Congress) is authoritative for service; congress-legislators is the maintained derived form everyone uses — treat as source, spot-check oddities against bioguide.congress.gov. FEC bulk files are authoritative for committees. |
| Join keys / crosswalks | `id.fec[]` ↔ ccl.CAND_ID ↔ cm.CMTE_ID. Party committees (DSCC/NRSC/DCCC/NRCC) and caucus institutions are deliberately NOT member-mapped. |

## 4. Tiered resources

- **Tier 1**: repo + schema README <https://github.com/unitedstates/congress-legislators>; FEC cm/ccl
  file descriptions <https://www.fec.gov/campaign-finance-data/committee-master-file-description/>,
  <https://www.fec.gov/campaign-finance-data/candidate-committee-linkage-file-description/>.
- **Tier 2**: the dataset ships JSON/CSV variants — no parser needed. openFEC `/committees`
  (sponsor_candidate_ids field) as spot-check.
- **Tier 3**: `reference/fec-campaign-finance.md` (key handling, cache conventions, entity-match
  discipline) — the sibling brief this one extends.

## 5. Recommended sequence

1. Download both legislator JSON files; verify Sinema's `party_affiliations` shape and Emmer's
   `id.fec` list on the raw entries.
2. Download cm/ccl for 2022/2024/2026; verify a known campaign committee ("EMMER FOR CONGRESS"),
   a leadership PAC (D linked to Emmer), and a JFC (J with multiple candidate rows).
3. Build `members_all` + `member_terms` (party periods) + `member_committees`; run the P6
   acceptance tests (Emmer round-trip, Toomey/McHenry/Brown historical, Sinema by date, JFC
   participants, package regression) before wiring into any tool.

## 6. Conventions

- Raw downloads → `out/congress_legislators_cache/` and `out/fec_cache/bulk/` (gitignored).
- Curated nickname/alias additions → versioned `member_aliases.json` beside the resolver script.
- README §4 outside-data rows: congress-legislators (CC0, fetch date), FEC bulk cm/ccl (fetch date).
