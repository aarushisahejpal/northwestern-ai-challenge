#!/usr/bin/env python3
"""Build the member + political-committee resolution layer (P6).

Adds three tables to the DuckDB alongside entities/entity_aliases — the people-name
half of entity resolution, plus the committees that exist to support those people:

  members_all       one row per member of Congress serving in the corpus window
                    (current AND departed), keyed on bioguide_id, with name parts,
                    nickname, latest chamber/state/party, and FEC candidate ids.
  member_terms      party-per-date grain: one row per (term x party-affiliation
                    period), so a mid-term switcher (Sinema D->I Dec-2022) annotates
                    correctly for any item date.
  member_committees candidate-support committees mapped to the member(s) they
                    support, tier-labeled: campaign-committee (FEC designation A/P),
                    leadership-pac (D), jfc (J, one row PER PARTICIPATING member).

Sources (external; cached raw, gitignored; traps in reference/congress-legislators.md):
  - unitedstates/congress-legislators (public domain): legislators-current.json +
    legislators-historical.json -> out/congress_legislators_cache/
  - FEC bulk committee master (cm), candidate-committee linkage (ccl), and candidate
    master (cn) per cycle -> out/fec_cache/bulk/  (no API key needed)
  - openFEC /committees?designation=D for leadership-PAC sponsors (the ONE link the
    bulk files don't carry: ccl has ~24 D rows/cycle vs ~850 D committees in cm).
    Key: env DATA_GOV_API_KEY / FEC_API_KEY, else gitignored out/.fec_api_key, else
    DEMO_KEY (skips the sweep if it would exceed DEMO_KEY's ~30 req/hr budget).
    Raw pages cached to out/fec_cache/leadership_pacs/.

Mapping rules (Rob, DECISIONS 2026-07-09 — rollup, never conflation):
  - A committee MAPS to its member with a tier label; it never merges into the member.
  - JFC participants: one row per ccl-linked candidate; where a J committee has no
    candidate linkage, a CONSERVATIVE name-inference runs (committee name contains
    exactly one member's first+last, else exactly one member's unique last name).
    Every row carries link_source + confidence so inference is auditable.
  - Party committees (DSCC/NRSC/DCCC/NRCC/DNC/RNC) and caucus institutions are NOT
    member-mapped — they are their own recipients (handled in member_resolve.py).
  - Leadership-PAC sponsors resolve via sponsor_candidate_ids -> the member's FEC
    ids; sponsors with an unmatched id (e.g. a presidential run's P-id) fall back to
    a candidate-master name+state match, confidence 'inferred'.

Usage:
  python skills/lda-entity-resolver/scripts/build_members.py --db db/lda_full.duckdb
    --cycles 2022 2024 2026       FEC cycles to load (default: the corpus window)
    --since-end 2021-01-01        keep members whose service ended on/after this
    --refresh                     re-download cached sources
    --offline                     cache/bulk only; skip the openFEC sweep
    --check                       print the Emmer/Sinema sanity probes after build

Curated additions live in member_aliases.json (versioned) beside this script.
Every row carries its source file (the raw-record-pointer invariant; these are
external tables, so the pointer is the cached download + fetch date).
"""

import argparse
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LEGISLATORS_BASE = "https://unitedstates.github.io/congress-legislators/"
FEC_BULK_BASE = "https://www.fec.gov/files/bulk-downloads/"
OPEN_FEC_BASE = "https://api.open.fec.gov/v1"
KEYFILE = Path("out/.fec_api_key")

PARTY_LETTER = {"Democrat": "D", "Republican": "R", "Independent": "I"}


def party_letter(p):
    return PARTY_LETTER.get(p, (p or "?")[:1].upper())


# ------------------------------------------------------------------ downloads

def fetch(url, dest, refresh=False):
    dest = Path(dest)
    if dest.exists() and not refresh:
        return dest, False
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gain-investigation research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        dest.write_bytes(r.read())
    return dest, True


def bulk_rows(zip_path):
    """Yield pipe-split rows from a one-file FEC bulk zip (headerless, latin-1)."""
    z = zipfile.ZipFile(zip_path)
    with z.open(z.namelist()[0]) as f:
        for line in io.TextIOWrapper(f, encoding="latin-1"):
            yield line.rstrip("\n").split("|")


def api_key():
    """Same resolution order as fec_enrich.py: env -> gitignored keyfile -> DEMO_KEY.
    Never printed, never cached, never committed."""
    import os
    for var in ("DATA_GOV_API_KEY", "FEC_API_KEY"):
        v = os.environ.get(var)
        if v:
            return v, f"env:{var}"
    if KEYFILE.exists():
        v = KEYFILE.read_text(encoding="utf-8").strip()
        if v:
            return v, "keyfile"
    return "DEMO_KEY", "DEMO_KEY"


def openfec_page(path, cache_file, key, refresh=False, **params):
    """One cached openFEC GET. The api_key is added to the live request only and is
    never written into the cache (same discipline as fec_enrich.py)."""
    cache_file = Path(cache_file)
    if cache_file.exists() and not refresh:
        return json.loads(cache_file.read_text(encoding="utf-8")), True
    qp = dict(params)
    qp["api_key"] = key
    url = OPEN_FEC_BASE + path + "?" + urllib.parse.urlencode(qp, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gain-investigation research"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    data["_fetched"] = date.today().isoformat()
    data["_params"] = params  # api_key deliberately NOT stored
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(0.3)
    return data, False


# ------------------------------------------------------------------ legislators

def load_members(cache_dir, since_end, refresh):
    members, terms = [], []
    for fname, is_current in (("legislators-current.json", True),
                              ("legislators-historical.json", False)):
        path, fresh = fetch(LEGISLATORS_BASE + fname,
                            Path(cache_dir) / "congress_legislators_cache" / fname, refresh)
        print(f"  {fname}: {'downloaded' if fresh else 'cache'}")
        for p in json.loads(path.read_text(encoding="utf-8")):
            tt = p.get("terms") or []
            if not tt:
                continue
            if not is_current and max(t["end"] for t in tt) < since_end:
                continue
            nm, ids = p["name"], p["id"]
            last_term = max(tt, key=lambda t: t["end"])
            aka = sorted({v for o in (p.get("other_names") or [])
                          for k, v in o.items() if k in ("first", "middle", "last") and v})
            # party-per-date grain: party_affiliations periods when present (the
            # mid-term-switch trap), else the term's single party
            segs = []
            for t in tt:
                chamber = "Senate" if t["type"] == "sen" else "House"
                for pa in (t.get("party_affiliations")
                           or [{"start": t["start"], "end": t["end"], "party": t.get("party")}]):
                    segs.append((chamber, t.get("state"), pa.get("party"),
                                 pa.get("start", t["start"]), pa.get("end", t["end"])))
            latest_party = max(segs, key=lambda s: s[4])[2]
            members.append({
                "bioguide_id": ids["bioguide"],
                "name": nm.get("official_full") or " ".join(
                    x for x in (nm.get("first"), nm.get("last")) if x),
                "first_name": nm.get("first"), "middle_name": nm.get("middle"),
                "last_name": nm.get("last"), "suffix": nm.get("suffix"),
                "nickname": nm.get("nickname"),
                "aka_names": "|".join(aka) or None,
                "state": last_term.get("state"),
                "chamber": "Senate" if last_term["type"] == "sen" else "House",
                "party": latest_party,
                "is_current": is_current,
                "served_from": min(t["start"] for t in tt),
                "served_to": max(t["end"] for t in tt),
                "fec_candidate_ids": ",".join(ids.get("fec") or []) or None,
                "src_file": fname,
            })
            for chamber, state, party, s, e in segs:
                terms.append((ids["bioguide"], chamber, state, party,
                              party_letter(party), s, e, fname))
    return members, terms


# ------------------------------------------------------------------ committees

def norm_cmte(raw):
    """Normalization key for committee-name matching (same spirit as the entity
    resolver's norm_name: uppercase, drop parentheticals, alnum only)."""
    if not raw:
        return None
    s = raw.upper()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9]+", "", s)
    return s or None


def load_fec_bulk(cache_dir, cycles, refresh):
    """cm (names/designations), ccl (candidate links), cn (candidate names)."""
    cm, ccl, cn = {}, [], {}
    for cyc in cycles:
        yy = str(cyc)[2:]
        for pfx in ("cm", "ccl", "cn"):
            url = f"{FEC_BULK_BASE}{cyc}/{pfx}{yy}.zip"
            path, fresh = fetch(url, Path(cache_dir) / "fec_cache" / "bulk" / f"{pfx}{yy}.zip",
                                refresh)
            if fresh:
                print(f"  {pfx}{yy}.zip: downloaded")
        for r in bulk_rows(Path(cache_dir) / "fec_cache" / "bulk" / f"cm{yy}.zip"):
            if len(r) < 15:
                continue
            e = cm.setdefault(r[0], {"name": r[1], "dsgn": r[8], "tp": r[9],
                                     "cand_id": r[14], "cycles": set(),
                                     "src": f"cm{yy}.zip"})
            e["cycles"].add(cyc)
            e["name"], e["dsgn"], e["tp"] = r[1], r[8], r[9]  # latest cycle wins
            if r[14]:
                e["cand_id"] = r[14]
        for r in bulk_rows(Path(cache_dir) / "fec_cache" / "bulk" / f"ccl{yy}.zip"):
            if len(r) >= 7 and r[0] and r[3]:
                ccl.append({"cand_id": r[0], "cmte_id": r[3], "dsgn": r[5],
                            "cycle": cyc, "src": f"ccl{yy}.zip"})
        for r in bulk_rows(Path(cache_dir) / "fec_cache" / "bulk" / f"cn{yy}.zip"):
            if len(r) >= 5 and r[0]:
                cn[r[0]] = {"name": r[1], "office_state": r[4], "src": f"cn{yy}.zip"}
    return cm, ccl, cn


def sweep_leadership_pacs(cache_dir, cycles, refresh):
    """openFEC /committees?designation=D -> sponsor_candidate_ids per committee.
    The one candidate-support link the bulk files don't carry."""
    key, key_src = api_key()
    print(f"  openFEC key source: {key_src}")
    sponsors, page, pages = {}, 1, None
    cdir = Path(cache_dir) / "fec_cache" / "leadership_pacs"
    while pages is None or page <= pages:
        cache_file = cdir / f"designation_D_{'_'.join(map(str, cycles))}_p{page}.json"
        if key == "DEMO_KEY" and not cache_file.exists() and page > 8:
            print("  ! DEMO_KEY budget: stopping the D sweep early — set "
                  "DATA_GOV_API_KEY for full leadership-PAC coverage")
            break
        try:
            data, cached = openfec_page("/committees/", cache_file, key,
                                        refresh=refresh, designation="D",
                                        cycle=list(cycles), per_page=100, page=page)
        except Exception as e:  # keep the build usable offline/limited
            print(f"  ! openFEC sweep stopped at page {page}: {e}")
            break
        pages = data["pagination"]["pages"]
        for c in data["results"]:
            sids = c.get("sponsor_candidate_ids") or []
            if sids:
                sponsors[c["committee_id"]] = {"name": c["name"], "sponsor_ids": sids,
                                               "src": cache_file.name}
        page += 1
    return sponsors


def load_nick_pairs():
    lex = json.loads((Path(__file__).parent / "member_aliases.json")
                     .read_text(encoding="utf-8"))
    pairs = {tuple(p) for p in lex["nickname_pairs"]}
    return pairs | {(b, a) for a, b in pairs}, lex


def first_eq(a, b, nickset):
    a, b = (a or "").upper().strip("."), (b or "").upper().strip(".")
    if not a or not b:
        return False
    if a == b or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return True
    return (a, b) in nickset


def build_committees(members, cm, ccl, sponsors, cn, nickset):
    """member_committees rows: (cmte_id, tier, bioguide, link_source, confidence)."""
    TIER = {"P": "campaign-committee", "A": "campaign-committee",
            "D": "leadership-pac", "J": "jfc"}
    fec2bio = {}
    for m in members:
        for fid in (m["fec_candidate_ids"] or "").split(","):
            if fid:
                fec2bio[fid] = m["bioguide_id"]
    by_bio = {m["bioguide_id"]: m for m in members}

    rows = {}  # (cmte_id, bioguide) -> row; first (highest-trust) source wins

    def add(cmte_id, bio, tier, cand_id, source, confidence, src_file):
        info = cm.get(cmte_id)
        if info is None or bio not in by_bio:
            return
        rows.setdefault((cmte_id, bio), {
            "cmte_id": cmte_id, "cmte_name": info["name"],
            "cmte_name_norm": norm_cmte(info["name"]), "tier": tier,
            "bioguide_id": bio, "member_name": by_bio[bio]["name"],
            "cand_id": cand_id,
            "cycles": ",".join(map(str, sorted(info["cycles"]))),
            "cmte_dsgn": info["dsgn"], "cmte_tp": info["tp"],
            "link_source": source, "confidence": confidence, "src_file": src_file})

    # 1. ccl candidate links (authoritative): A/P campaign committees, the few
    #    ccl-linked D rows, and J participants
    for l in ccl:
        bio = fec2bio.get(l["cand_id"])
        tier = TIER.get(l["dsgn"])
        if bio and tier:
            add(l["cmte_id"], bio, tier, l["cand_id"], "fec-ccl", "linked", l["src"])

    # 2. cm.CAND_ID (principal campaign committees carry their candidate directly)
    for cid, info in cm.items():
        if info["cand_id"] and info["dsgn"] in TIER:
            bio = fec2bio.get(info["cand_id"])
            if bio:
                add(cid, bio, TIER[info["dsgn"]], info["cand_id"],
                    "fec-cm-candid", "linked", info["src"])

    # 3. leadership-PAC sponsors from the openFEC sweep
    n_cn_inferred, unmatched_sponsors = 0, []
    for cid, sp in sponsors.items():
        for sid in sp["sponsor_ids"]:
            bio = fec2bio.get(sid)
            if bio:
                add(cid, bio, "leadership-pac", sid, "openfec-sponsor", "linked",
                    sp["src"])
                continue
            # sponsor id not among the member's congressional FEC ids (e.g. a
            # presidential run) -> candidate-master name+state fallback
            cand = cn.get(sid)
            if not cand:
                unmatched_sponsors.append((cid, sid, sp["name"]))
                continue
            ln, _, rest = cand["name"].partition(",")
            first = (rest.split() or [""])[0]
            # presidential candidacies carry office_state 'US' — treat as wildcard
            hits = [m for m in members
                    if (m["last_name"] or "").upper() == ln.strip().upper()
                    and first_eq(first, m["first_name"], nickset)
                    and cand["office_state"] in (m["state"], "", "US")]
            if len(hits) == 1:
                add(cid, hits[0]["bioguide_id"], "leadership-pac", sid,
                    "cn-name-inference", "inferred", cand["src"])
                n_cn_inferred += 1
            else:
                unmatched_sponsors.append((cid, sid, sp["name"]))

    # 4. conservative name-inference for J committees with no candidate linkage
    #    ("LUMMIS VICTORY COMMITTEE" carries no ccl row). First+last of exactly one
    #    member, else the unique last name of exactly one member. Word-boundary
    #    matching on the raw name; every row flagged 'inferred'.
    linked_j = {cid for (cid, _b), r in rows.items() if r["tier"] == "jfc"}
    n_j_inferred = 0
    last_index = {}
    for m in members:
        last_index.setdefault((m["last_name"] or "").upper(), []).append(m)
    for cid, info in cm.items():
        if info["dsgn"] != "J" or cid in linked_j:
            continue
        words = set(re.findall(r"[A-Z]+", info["name"].upper()))
        last_hits = [m for ln, ms in last_index.items() if ln and ln in words
                     for m in ms]
        full_hits = [m for m in last_hits
                     if {w for w in ((m["first_name"] or "").upper(),
                                     (m["nickname"] or "").upper()) if w} & words]
        pick = (full_hits if len(full_hits) == 1
                else last_hits if len(last_hits) == 1 else [])
        if pick:
            add(cid, pick[0]["bioguide_id"], "jfc", None, "name-inference",
                "inferred", info["src"])
            n_j_inferred += 1

    print(f"  member_committees: {len(rows)} rows "
          f"({n_cn_inferred} cn-inferred sponsors, {n_j_inferred} name-inferred JFCs, "
          f"{len(unmatched_sponsors)} leadership-PAC sponsors unmatched -> not mapped)")
    return list(rows.values()), unmatched_sponsors


# ------------------------------------------------------------------ db

DDL = """
CREATE OR REPLACE TABLE members_all (
  bioguide_id TEXT, name TEXT, first_name TEXT, middle_name TEXT, last_name TEXT,
  suffix TEXT, nickname TEXT, aka_names TEXT, state TEXT, chamber TEXT, party TEXT,
  is_current BOOLEAN, served_from DATE, served_to DATE, fec_candidate_ids TEXT,
  src_file TEXT);

CREATE OR REPLACE TABLE member_terms (
  bioguide_id TEXT, chamber TEXT, state TEXT, party TEXT, party_letter TEXT,
  from_date DATE, to_date DATE, src_file TEXT);

CREATE OR REPLACE TABLE member_committees (
  cmte_id TEXT, cmte_name TEXT, cmte_name_norm TEXT, tier TEXT,
  bioguide_id TEXT, member_name TEXT, cand_id TEXT, cycles TEXT,
  cmte_dsgn TEXT, cmte_tp TEXT, link_source TEXT, confidence TEXT, src_file TEXT);
"""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--cache-dir", default="out")
    ap.add_argument("--cycles", nargs="+", type=int, default=[2022, 2024, 2026])
    ap.add_argument("--since-end", default="2021-01-01",
                    help="keep members whose service ended on/after this date")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--offline", action="store_true",
                    help="bulk/cache only; skip the openFEC leadership-PAC sweep")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    print("== congress-legislators ==")
    members, terms = load_members(args.cache_dir, args.since_end, args.refresh)
    print(f"  members_all: {len(members)} in-window members "
          f"({sum(m['is_current'] for m in members)} current) · "
          f"member_terms: {len(terms)} party-period rows")

    print("== FEC committee crosswalk ==")
    cm, ccl, cn = load_fec_bulk(args.cache_dir, args.cycles, args.refresh)
    print(f"  cm: {len(cm)} committees · ccl: {len(ccl)} links · cn: {len(cn)} candidates")
    sponsors = {} if args.offline else sweep_leadership_pacs(
        args.cache_dir, args.cycles, args.refresh)
    if not args.offline:
        print(f"  leadership PACs with sponsors (openFEC): {len(sponsors)}")
    nickset, _lex = load_nick_pairs()
    cmte_rows, unmatched = build_committees(members, cm, ccl, sponsors, cn, nickset)

    con = duckdb.connect(args.db)
    # fold the press-corpus display names in as aliases (joined on bioguide_id):
    # the corpus writes e.g. 'Nikki Budzinski' where the legislators file has
    # first='Nicole (Nikki)' — both spellings should resolve
    try:
        press = dict(con.execute(
            "SELECT bioguide_id, name FROM members WHERE name IS NOT NULL")
            .fetchall())
        n_alias = 0
        for m in members:
            pn = press.get(m["bioguide_id"])
            if pn and pn != m["name"] and pn not in (m["aka_names"] or ""):
                m["aka_names"] = "|".join(filter(None, [m["aka_names"], pn]))
                n_alias += 1
        print(f"  press-corpus name aliases folded in: {n_alias}")
    except duckdb.CatalogException:
        pass  # corpus members table not built in this DB
    for stmt in DDL.split(";"):
        if stmt.strip():
            con.execute(stmt)
    cols_m = ["bioguide_id", "name", "first_name", "middle_name", "last_name",
              "suffix", "nickname", "aka_names", "state", "chamber", "party",
              "is_current", "served_from", "served_to", "fec_candidate_ids", "src_file"]
    con.executemany(
        f"INSERT INTO members_all VALUES ({','.join('?' * len(cols_m))})",
        [[m[c] for c in cols_m] for m in members])
    con.executemany("INSERT INTO member_terms VALUES (?,?,?,?,?,?,?,?)", terms)
    cols_c = ["cmte_id", "cmte_name", "cmte_name_norm", "tier", "bioguide_id",
              "member_name", "cand_id", "cycles", "cmte_dsgn", "cmte_tp",
              "link_source", "confidence", "src_file"]
    con.executemany(
        f"INSERT INTO member_committees VALUES ({','.join('?' * len(cols_c))})",
        [[r[c] for c in cols_c] for r in cmte_rows])

    print("== written ==")
    for t in ("members_all", "member_terms", "member_committees"):
        print(f"  {t}: {con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]} rows")
    print("  tiers:", con.execute(
        "SELECT tier, count(*), sum((confidence='inferred')::int) "
        "FROM member_committees GROUP BY 1 ORDER BY 1").fetchall())

    if args.check:
        print("== sanity probes ==")
        print("  Emmer committees:", con.execute(
            "SELECT cmte_name, tier, confidence FROM member_committees "
            "WHERE member_name LIKE '%Emmer%' ORDER BY tier").fetchall())
        print("  Sinema terms:", con.execute(
            "SELECT party_letter, from_date, to_date FROM member_terms "
            "WHERE bioguide_id='S001191' AND chamber='Senate' ORDER BY from_date")
            .fetchall())
        print("  Toomey/McHenry/Brown present:", con.execute(
            "SELECT name, is_current, served_to FROM members_all WHERE bioguide_id IN "
            "('T000461','M001156','B000944')").fetchall())
    con.close()


if __name__ == "__main__":
    main()
