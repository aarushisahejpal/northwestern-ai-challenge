#!/usr/bin/env python3
"""FEC enrichment: the Super-PAC money leg of an industry money map.

The industry map has three legs. `industry_map.py` says WHO the players are; the
resolver's `v_client_canonical_spend` (P1) says what they SPEND to lobby; and
`ld203_giving.py` says who they give to *within LD-203*. But LD-203 is
registrant-filed FECA/honorary/inaugural giving — by law it does NOT see
Super-PAC money, which is exactly where an industry like crypto puts its headline
political money (the Fairshake network, ~$100M+ scale). So an industry map built
on LD-203 alone understates the political spend by an order of magnitude. This
tool closes that gap: it takes the entity-resolved player roster and reports, per
player, its FEC-disclosed contributions INTO the industry's Super-PAC network,
reconciled against the LD-203 giving map — the delta (the Super-PAC money LD-203
can't see) is the reportable surface.

STRATEGY — pull the PAC, then match the roster (not 500 per-player queries).
A crypto Super PAC has a bounded, itemized donor list (Fairshake's 2026 cycle:
~53 receipts). So this pulls every itemized receipt of each network committee
ONCE (a couple of pages per cycle), caches it, aggregates by contributor, and
matches roster names against that donor list locally. Cheap, complete, and it
also surfaces network donors that weren't on the roster.

SCOPE HONESTY — the mirror of ld203_giving's "LD-203 ≠ FEC". FEC + LD-203
together are still NOT "total political spending": 501(c)(4) dark money and
state-level money are out of both. Say "FEC-disclosed + LD-203-disclosed", never
"total". And FEC name-matching is fuzzy: matches are reported as CANDIDATES with
the raw FEC contributor name shown for eyeballing — never silently merged (same
discipline as lda-entity-resolver's "ambiguity is a report, not a merge").

API KEY — resolved WITHOUT ever hardcoding, caching, or printing it:
  1. env var DATA_GOV_API_KEY (preferred) or FEC_API_KEY;
  2. a gitignored one-line keyfile out/.fec_api_key (read internally, never
     echoed — /out/ is gitignored so it can't be committed or traced);
  3. else api.data.gov's public DEMO_KEY (real data, shared-IP rate-limited pool).
The key is stripped from every cached request and from --json output; only the
source LABEL is ever shown. README §4 discloses the source + fetch date, not the key.

CACHE — every raw response is written to out/fec_cache/ (gitignored via /out/),
wrapped with its endpoint, params (key stripped), and fetch timestamp. The cache
IS the evidence, the way scraped press text is primary and the live URL secondary
(FEC records can be amended). A finding cites the FEC transaction_id + committee_id
+ the openFEC endpoint + the cache fetch date. Re-runs read the cache (free);
--refresh forces a re-fetch.

Usage:
  # default: the crypto Super-PAC network, reconciled against the crypto roster
  python fec_enrich.py --names-file out/crypto_roster.txt
  # one committee explicitly (skip name resolution), one player probe:
  python fec_enrich.py --committee-id C00835959 --names-file out/crypto_roster.txt
    --names-file PATH   entity roster (one name/line) — the industry_map.py output
    --committee-seed S  committee search term(s) to resolve (default: the crypto
                        network — Fairshake / Defend American Jobs / Protect Progress)
    --committee-id ID   use these committee id(s) directly, skip name resolution
    --cycle Y [Y ...]   two-year transaction period(s) (default: 2024 2026)
    --db PATH           DuckDB for the LD-203 reconciliation side (default db/lda_full.duckdb)
    --cache-dir PATH    raw-response cache (default out/fec_cache)
    --refresh           bypass cache, re-fetch from the API
    --min-match N       min FEC $ for a roster match to be shown (default 0)
    --top N             rows in each ranked section (default 25)
    --json              machine-readable output (key stripped)
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb

# Reuse the sibling money tool's normalization + LD-203 resolution so the two
# halves of the money map speak the same entity language (a drift here would
# silently mis-reconcile). norm_name is kept in sync with the resolver.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ld203_giving import (  # noqa: E402
    norm_name, resolve_registrants, matched_registrant_names, giving,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

OPEN_FEC_BASE = "https://api.open.fec.gov/v1"

# The crypto Super-PAC network (the industry whose money leg this closes). Seeds
# are RESOLVED live against the API and filtered to Super PACs — the ids are not
# trusted from memory (a name like "Protect Progress" also matches an unrelated
# non-qualified PAC "Protect Our Progress"). Widely reported: Fairshake C00835959.
CRYPTO_NETWORK_SEEDS = ["Fairshake", "Defend American Jobs", "Protect Progress"]

# Single-token subset matches on these are too generic to trust as a candidate
# (a roster "…BANK" must not soak up every bank in the PAC's receipts).
GENERIC_TOKENS = {
    "BANK", "GROUP", "CAPITAL", "FUND", "FUNDS", "DIGITAL", "GLOBAL", "HOLDINGS",
    "PARTNERS", "FINANCIAL", "TRUST", "MANAGEMENT", "TECHNOLOGIES", "TECHNOLOGY",
    "LABS", "MARKETS", "SERVICES", "AMERICA", "AMERICAS", "NATIONAL", "ASSOCIATION",
    "SYSTEMS", "NETWORK", "FOUNDATION", "INTERNATIONAL", "CORPORATION", "COMPANY",
    "US", "USA", "INC", "THE", "AND", "OF", "FOR",
}


# ------------------------------------------------------------------- HTTP + cache

KEYFILE = Path("out/.fec_api_key")


def api_key():
    """Resolve the api.data.gov key WITHOUT ever hardcoding, caching, or printing
    it. Precedence:
      1. env var DATA_GOV_API_KEY / FEC_API_KEY (the documented, preferred path);
      2. a gitignored one-line keyfile out/.fec_api_key (read internally, never
         echoed — /out/ is gitignored so it can't be committed or traced);
      3. api.data.gov's public DEMO_KEY (real data, but a shared-IP ~30 req/hr
         pool — fine for a smoke test, unreliable for a full run).
    Only the SOURCE LABEL (never the value) is returned for display."""
    for var in ("DATA_GOV_API_KEY", "FEC_API_KEY"):
        v = os.environ.get(var)
        if v and v.strip():
            return v.strip(), var
    if KEYFILE.exists():
        v = KEYFILE.read_text(encoding="utf-8").strip()
        if v:
            return v, str(KEYFILE)
    print(f"  ⚠ no key in env (DATA_GOV_API_KEY/FEC_API_KEY) or {KEYFILE} — falling "
          "back to DEMO_KEY (real data, but a shared-IP rate-limited pool). Set a "
          "real key for a full run.", file=sys.stderr)
    return "DEMO_KEY", "DEMO_KEY"


def _cache_slug(path, params):
    """Compact, deterministic cache filename: a short readable hint + a hash of
    the full param set (so a long pagination cursor doesn't blow past Windows'
    260-char MAX_PATH). api_key is never a param here."""
    ep = path.strip("/").replace("/", "_")
    hint = "_".join(str(params[k]) for k in
                    ("committee_id", "two_year_transaction_period", "q") if k in params)
    hint = "".join(c if (c.isalnum() or c in ".-") else "_" for c in hint)[:40]
    h = hashlib.sha1(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:10]
    return f"{ep}__{hint}__{h}"[:110]


def http_get(path, params, key, cache_dir, refresh=False, max_retries=5):
    """GET an openFEC endpoint with caching + 429 backoff. Returns (response_json,
    from_cache). The api_key is added only to the live request; it is stripped
    from the cache key and from the stored params."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cf = cache_dir / (_cache_slug(path, params) + ".json")
    if cf.exists() and not refresh:
        return json.loads(cf.read_text(encoding="utf-8"))["response"], True

    qp = dict(params)
    qp["api_key"] = key
    url = OPEN_FEC_BASE + path + "?" + urllib.parse.urlencode(qp, doseq=True)
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "gain-investigation/fec_enrich"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = 5 * (2 ** attempt)
                print(f"  · 429 rate-limited; backing off {wait}s "
                      f"(attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(wait)
                continue
            body = e.read().decode("utf-8", "replace")[:200]
            raise SystemExit(f"openFEC {e.code} on {path}: {body}")
        except urllib.error.URLError as e:
            raise SystemExit(f"network error reaching openFEC ({path}): {e.reason}")
    else:
        raise SystemExit(f"openFEC still rate-limited after {max_retries} tries: {last_err}")

    cf.write_text(json.dumps({
        "_endpoint": OPEN_FEC_BASE + path,
        "_params": params,                       # api_key deliberately NOT stored
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
        "response": data,
    }, indent=2), encoding="utf-8")
    return data, False


# ----------------------------------------------------------- committee resolution

def resolve_committees(seeds, key, cache_dir, refresh):
    """Resolve seed names -> Super-PAC committees. Filters to independent-
    expenditure-only committees (type 'O') so a decoy non-qualified PAC with a
    similar name is excluded. Records the raw lookup for citation."""
    found, seen = [], set()
    for seed in seeds:
        data, _ = http_get("/committees/", {"q": seed, "per_page": 20},
                           key, cache_dir, refresh)
        for r in data.get("results", []):
            cid = r.get("committee_id")
            if cid in seen:
                continue
            is_superpac = r.get("committee_type") == "O"
            # keep exact super-PAC matches; also keep a committee explicitly named
            # like the seed even if type differs, but flag it
            name = (r.get("name") or "").upper()
            if is_superpac and seed.upper().replace(" ", "") in name.replace(" ", ""):
                seen.add(cid)
                found.append({
                    "committee_id": cid, "name": r.get("name"),
                    "committee_type_full": r.get("committee_type_full"),
                    "affiliated": r.get("affiliated_committee_name"),
                    "cycles": r.get("cycles"), "matched_seed": seed,
                })
    return found


# ----------------------------------------------------------------- receipt pulls

RECEIPT_FIELDS = ("contributor_name", "contributor_employer", "contributor_occupation",
                  "contribution_receipt_amount", "contribution_receipt_date",
                  "is_individual", "entity_type", "memo_code", "is_memo",
                  "line_number", "receipt_type",
                  "transaction_id", "sub_id", "committee_id",
                  "two_year_transaction_period",
                  "contributor_city", "contributor_state")


def pull_receipts(committee_id, cycle, key, cache_dir, refresh, max_pages=60):
    """Every itemized Schedule A receipt for a committee in a cycle, via keyset
    pagination (last_index / last_contribution_receipt_date). Small for a Super
    PAC — a couple of pages. Each page cached."""
    receipts = []
    base = {"committee_id": committee_id, "two_year_transaction_period": cycle,
            "per_page": 100, "sort": "contribution_receipt_date"}
    last_index = last_date = None
    for page in range(max_pages):
        params = dict(base)
        if last_index is not None:
            params["last_index"] = last_index
            if last_date is not None:
                params["last_contribution_receipt_date"] = last_date
        data, cached = http_get("/schedules/schedule_a/", params, key, cache_dir, refresh)
        res = data.get("results", [])
        for r in res:
            receipts.append({f: r.get(f) for f in RECEIPT_FIELDS})
        li = (data.get("pagination") or {}).get("last_indexes") or {}
        if len(res) < 100 or not li.get("last_index"):
            break
        last_index = li.get("last_index")
        last_date = li.get("last_contribution_receipt_date")
        if not cached:
            time.sleep(0.4)                      # be polite between live pages
    return receipts


# ------------------------------------------------------------------ aggregation

def is_individual_receipt(r):
    """True iff the contributor is a natural person. The authoritative signal is
    entity_type == 'IND'. Do NOT trust openFEC's `is_individual` boolean — it flags
    many CORPORATE Super-PAC receipts True (Ripple Labs Inc.'s $25M gifts come back
    is_individual=True / entity_type='ORG'), which would misroute a company's own
    treasury money into the personal-gift bucket and drop it from the map."""
    et = (r.get("entity_type") or "").upper()
    if et == "IND":
        return True
    if et:                                   # any other populated type = organization
        return False
    # entity_type missing: fall back to the "LAST, FIRST" name shape
    n = r.get("contributor_name") or ""
    return ("," in n and n.split(",")[0].isupper()
            and " " not in n.split(",")[0].strip())


def is_memo(r):
    """FEC memo entry: its amount is already counted in another itemized line, so
    it must be EXCLUDED from any sum (openFEC's standard rule). The dominant case
    here is LLC-attribution memos — an LLC's contribution re-listed against the
    individuals behind it (a16z's $5M receipt SA11AI.4392 re-attributed to
    Andreessen as SA11AI.4392.0, memo_code='X'). Summing them double-counts and
    manufactures a phantom 'individual giving' shadow equal to the corporate line.
    (Note: openFEC responses carry no `is_memo` field, so memo_code='X' is the
    operative filter; the is_memo branch is inert forward-compat.)"""
    return r.get("memo_code") == "X" or bool(r.get("is_memo"))


def line_category(r):
    """Schedule A line_number → what the row actually is. Only line 11* is DONOR
    MONEY; the rest are non-contribution receipts that must not be attributed to a
    donor. Verified against the Fairshake pull:
      11*  contribution   — the real gift (incl. crypto in-kind on 11AI)
      12   transfer       — from an affiliated committee (Fairshake → its sisters,
                            $113M; already entered the network as an 11* gift)
      15/16 refund/offset  — refunds/offsets RECEIVED (positive receipts, not gifts)
      17   other_receipt  — the #1 crypto trap: when the PAC SELLS donated crypto,
                            the sale proceeds are re-filed here (Coinbase's $59.9M
                            'COINBASE COMMERCE (EXCHANGE)' rows = the same coins
                            being liquidated, NOT a second donation)."""
    ln = (r.get("line_number") or "")
    if ln.startswith("11"):
        return "contribution"
    if ln.startswith("12"):
        return "transfer"
    if ln.startswith(("15", "16")):
        return "refund_offset"
    if ln.startswith("17"):
        return "other_receipt"
    return "other"


def aggregate_contributors(receipts):
    """Group DONOR CONTRIBUTIONS (line 11*, non-memo) by normalized contributor
    name. Individuals kept separate from organizations (a company's Super-PAC
    funding must not be summed with its employees' personal gifts — method
    decision #2). Returns (orgs, indivs, excluded) where `excluded` summarizes the
    non-contribution receipts (transfers / crypto-sale proceeds / refunds) by
    category, so the money dropped from donor attribution stays transparent."""
    orgs, indivs = {}, {}
    excluded = {}
    seen_tx = set()
    for r in receipts:
        if is_memo(r):                       # exclude memo lines from all totals
            continue
        # Amendment/duplicate guard. The openFEC API already reflects the latest
        # amendment (verified: zero duplicate transaction_ids in the Fairshake pull,
        # and itemized contributions reconcile to FEC's published `contributions`
        # total <0.01%), unlike the bulk data which ships every amendment version.
        # This DISTINCT is defense-in-depth so the tool stays correct if reused on a
        # committee where the API returns a repeated transaction_id. sub_id is the
        # row-unique key; transaction_id is filer-assigned and is what an amendment
        # re-reports.
        tx = (r.get("committee_id"), r.get("transaction_id"))
        if r.get("transaction_id") is not None:
            if tx in seen_tx:
                continue
            seen_tx.add(tx)
        cat = line_category(r)
        amt = r.get("contribution_receipt_amount") or 0
        if cat != "contribution":            # transfers / sale proceeds / refunds
            x = excluded.setdefault(cat, {"total": 0.0, "items": 0, "names": set()})
            x["total"] += amt
            x["items"] += 1
            nm = (r.get("contributor_name") or "").strip()
            if nm and len(x["names"]) < 8:
                x["names"].add(nm)
            continue
        name = (r.get("contributor_name") or "").strip()
        if not name:
            continue
        bucket = indivs if is_individual_receipt(r) else orgs
        key = norm_name(name) if bucket is orgs else name.upper()
        e = bucket.setdefault(key, {
            "norm": key, "names": set(), "total": 0.0, "items": 0,
            "employers": set(), "committees": set(), "tids": []})
        e["names"].add(name)
        e["total"] += amt
        e["items"] += 1
        if r.get("contributor_employer"):
            e["employers"].add(r["contributor_employer"].strip())
        if r.get("committee_id"):
            e["committees"].add(r["committee_id"])
        if len(e["tids"]) < 6 and r.get("transaction_id"):
            e["tids"].append({"transaction_id": r["transaction_id"],
                              "committee_id": r.get("committee_id"),
                              "amount": amt, "date": r.get("contribution_receipt_date")})
    return orgs, indivs, excluded


# --------------------------------------------------------------- roster + matching

def load_roster(path):
    """norm_key -> {display, lines[]}. A player can carry several spellings that
    normalize apart (the entity-resolution ceiling, cleanup C / P6); each becomes
    its own key, documented as a known limitation rather than silently merged."""
    roster = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        k = norm_name(s)
        if not k:
            continue
        r = roster.setdefault(k, {"display": s, "lines": []})
        r["lines"].append(s)
        # prefer a shorter, Title/Mixed-case line as the display label
        if len(s) < len(r["display"]) or (s != s.upper() and r["display"] == r["display"].upper()):
            r["display"] = s
    return roster


def _tokens(norm_key):
    return set(norm_key.split()) if norm_key else set()


def match_key(fec_norm, roster):
    """Match a FEC contributor's normalized name to a roster key. Returns
    (roster_key, confidence) or (None, None). Exact first; then a proper
    token-subset either direction (guarded against generic single tokens).
    Matches are CANDIDATES — the caller shows the raw names for eyeballing."""
    if fec_norm in roster:
        return fec_norm, "exact"
    ft = _tokens(fec_norm)
    if not ft:
        return None, None
    best = None
    for rk in roster:
        rt = _tokens(rk)
        if not rt:
            continue
        smaller, larger = (ft, rt) if len(ft) <= len(rt) else (rt, ft)
        if not smaller < larger:                 # require PROPER subset
            continue
        distinctive = smaller - GENERIC_TOKENS
        if not distinctive:
            continue
        if len(smaller) == 1:
            tok = next(iter(smaller))
            if tok in GENERIC_TOKENS or len(tok) < 5:
                continue
        # prefer the match sharing the most tokens
        score = len(smaller)
        if best is None or score > best[2]:
            best = (rk, "candidate", score)
    return (best[0], best[1]) if best else (None, None)


def build_player_fec(orgs, roster):
    """Attach FEC org contributions to roster players. player_key -> aggregate of
    all FEC contributor rows that matched it (may be several: 'COINBASE',
    'COINBASE COMMERCE …')."""
    players = {}
    unmatched = []
    for fec_norm, agg in orgs.items():
        rk, conf = match_key(fec_norm, roster)
        if rk is None:
            unmatched.append(agg)
            continue
        p = players.setdefault(rk, {
            "roster_key": rk, "display": roster[rk]["display"],
            "roster_lines": roster[rk]["lines"], "total": 0.0, "items": 0,
            "fec_names": [], "confidence": "exact", "tids": [], "committees": set()})
        p["total"] += agg["total"]
        p["items"] += agg["items"]
        p["fec_names"].append({"name": sorted(agg["names"])[0], "amount": agg["total"],
                               "confidence": conf})
        if conf == "candidate" and p["confidence"] == "exact":
            p["confidence"] = "candidate"
        p["committees"] |= agg["committees"]
        for t in agg["tids"]:
            if len(p["tids"]) < 8:
                p["tids"].append(t)
    return players, unmatched


def build_individuals_by_employer(indivs, roster):
    """Individual gifts whose EMPLOYER matches a roster player — reported
    separately, never summed into the corporate figure (method decision #2)."""
    out = {}
    for agg in indivs.values():
        emp_norms = {norm_name(e) for e in agg["employers"] if e}
        matched = None
        for en in emp_norms:
            if not en:
                continue
            rk, _ = match_key(en, roster)
            if rk:
                matched = rk
                break
        if not matched:
            continue
        o = out.setdefault(matched, {"display": roster[matched]["display"],
                                     "total": 0.0, "items": 0, "who": set()})
        o["total"] += agg["total"]
        o["items"] += agg["items"]
        o["who"] |= agg["names"]
    return out


# ----------------------------------------------------------- LD-203 reconciliation

def ld203_total_for(con, names):
    """Disclosed LD-203 giving for a roster player, via the sibling tool's exact
    resolution + amendment de-dup. Returns (total, items, client_only_flag)."""
    ents, keys, unresolved, client_only = resolve_registrants(con, names, exact=True)
    if not keys:
        return 0.0, 0, bool(client_only)
    reg_names = matched_registrant_names(con, keys)
    if not reg_names:
        return 0.0, 0, bool(client_only)
    res = giving(con, reg_names, [], None, 1, 1)
    return (res["totals"]["total"] or 0.0), (res["totals"]["items"] or 0), False


def verify_totals(committees, cycles, receipts, key, cache_dir, refresh):
    """Reconcile the itemized line-11 non-memo CONTRIBUTIONS pulled here against
    each committee's FEC-published `contributions` total (the 'reconcile against
    published numbers' sanity gate, mirroring the loader's count check). This must
    reconcile to `contributions`, NOT `receipts`: `receipts` also includes the
    line-12 transfers, line-17 crypto-sale proceeds, and interest that are not
    donor money — matching `receipts` (as an earlier version did) merely certifies
    you inherited FEC's gross-up. A complete pull with correct line/memo handling
    matches `contributions` to well under 1% on a closed cycle; the raw receipts
    figure is shown alongside so the contributions-vs-receipts gap (the crypto
    liquidation + transfers) is visible."""
    from collections import defaultdict
    mine = defaultdict(float)
    for r in receipts:
        if is_memo(r) or line_category(r) != "contribution":
            continue
        mine[(r.get("committee_id"), r.get("two_year_transaction_period"))] += \
            r.get("contribution_receipt_amount") or 0
    rows = []
    for c in committees:
        for cyc in cycles:
            data, _ = http_get(f"/committee/{c['committee_id']}/totals/",
                               {"cycle": cyc}, key, cache_dir, refresh)
            res = data.get("results", [])
            rows.append({
                "committee_id": c["committee_id"], "name": c["name"], "cycle": cyc,
                "itemized_contributions": mine.get((c["committee_id"], cyc), 0.0),
                "fec_contributions": (res[0].get("contributions") if res else None),
                "fec_receipts": (res[0].get("receipts") if res else None)})
    return rows


def reconcile(con, players):
    """Per matched player: FEC Super-PAC $ vs LD-203 disclosed $, and the delta
    (the Super-PAC money LD-203 can't see). Ranked by that delta."""
    rows = []
    for p in players.values():
        ld_total, ld_items, client_only = ld203_total_for(con, p["roster_lines"])
        rows.append({
            "player": p["display"], "confidence": p["confidence"],
            "fec_superpac": p["total"], "fec_items": p["items"],
            "ld203": ld_total, "ld203_items": ld_items,
            "delta": p["total"] - ld_total,
            "ld203_client_only": client_only,
            "fec_names": p["fec_names"], "committees": sorted(p["committees"]),
            "tids": p["tids"],
        })
    rows.sort(key=lambda x: x["delta"], reverse=True)
    return rows


# ----------------------------------------------------------------- presentation

def money(v):
    return f"${v:,.0f}" if v is not None else "·"


def render(committees, cycles, recon, indiv, unmatched, roster_n, key_src,
           cache_dir, top, totals=None, excluded=None):
    L = ["=" * 84,
         "FEC ENRICHMENT — Super-PAC money leg  ·  reconciled against LD-203 giving",
         "=" * 84]
    L.append(f"cycles: {', '.join(str(c) for c in cycles)}   ·   roster players: "
             f"{roster_n}   ·   api key: {key_src}   ·   cache: {cache_dir}")
    L.append("")
    L.append("── NETWORK COMMITTEES (resolved live via /committees) " + "─" * 30)
    for c in committees:
        L.append(f"    {c['committee_id']}  {c['committee_type_full']:<38} {c['name']}"
                 + (f"   (aff: {c['affiliated']})" if c.get("affiliated") and c["affiliated"] != "NONE" else ""))
    if not committees:
        L.append("    ⚠ no Super-PAC committee resolved from the seeds — pass --committee-id")
    L.append("")

    if totals:
        L.append("── PULL SANITY CHECK: itemized line-11 contributions vs FEC-published totals " + "─" * 6)
        L.append(f"    {'committee':<22}{'cyc':>5}{'my contributions':>19}{'FEC contribs':>15}{'Δ%':>7}{'(FEC receipts)':>17}")
        for t in totals:
            fc = t["fec_contributions"] or 0
            pct = (100 * (t["itemized_contributions"] - fc) / fc) if fc else float("nan")
            L.append(f"    {t['name'][:21]:<22}{t['cycle']:>5}"
                     f"{money(t['itemized_contributions']):>19}{money(fc):>15}{pct:>6.1f}%"
                     f"{money(t['fec_receipts']):>17}")
        L.append("    (reconciles to FEC `contributions`, NOT `receipts` — receipts also carry line-12")
        L.append("     transfers + line-17 crypto-sale proceeds/interest that are not donor money)")
        L.append("")

    L.append("── RECONCILIATION: FEC Super-PAC giving vs LD-203 disclosed giving " + "─" * 18)
    L.append("   (ranked by delta = the Super-PAC money LD-203 can't see; matches are")
    L.append("    CANDIDATES — the FEC contributor name is shown; verify per transaction id)")
    L.append("")
    L.append(f"    {'PLAYER':<34}{'FEC SUPER-PAC':>15}{'LD-203':>13}{'DELTA':>15}  conf")
    L.append(f"    {'-'*34}{'-'*15}{'-'*13}{'-'*15}  ----")
    for r in recon[:top]:
        L.append(f"    {r['player'][:33]:<34}{money(r['fec_superpac']):>15}"
                 f"{money(r['ld203']):>13}{money(r['delta']):>15}  {r['confidence']}")
    L.append("")

    # the spot-check the acceptance asks for: FEC >> LD-203
    dwarfs = [r for r in recon if r["fec_superpac"] > 0
              and r["fec_superpac"] >= 10 * max(r["ld203"], 1)]
    if dwarfs:
        L.append("── SPOT-CHECK — players whose FEC Super-PAC giving DWARFS their LD-203 " + "─" * 13)
        for r in dwarfs[:8]:
            ld = money(r["ld203"]) if r["ld203"] else "$0 (invisible in LD-203)"
            L.append(f"    {r['player'][:40]:<41} FEC {money(r['fec_superpac']):>14}   vs LD-203 {ld}")
            fn = "; ".join(f"{n['name'][:28]} {money(n['amount'])}" for n in r["fec_names"][:3])
            L.append(f"        via FEC contributor(s): {fn}")
            if r["tids"]:
                t = r["tids"][0]
                L.append(f"        e.g. tid {t['transaction_id']} → committee {t['committee_id']} "
                         f"{money(t['amount'])} {t['date']}")
        L.append("")

    if indiv:
        L.append("── INDIVIDUAL gifts whose EMPLOYER matches a player (kept SEPARATE) " + "─" * 17)
        L.append("   (corporate treasury money ≠ its executives' personal gifts — not summed above)")
        for rk, o in sorted(indiv.items(), key=lambda kv: kv[1]["total"], reverse=True)[:top]:
            who = ", ".join(sorted(o["who"])[:3])
            L.append(f"    {o['display'][:34]:<35}{money(o['total']):>14}  {o['items']:>3}×  ({who[:40]})")
        L.append("")

    if unmatched:
        um = sorted(unmatched, key=lambda a: a["total"], reverse=True)
        L.append("── TOP NETWORK DONORS (line-11 contributions) NOT ON THE ROSTER (context) " + "─" * 9)
        L.append("   (real contributors the roster didn't name — triage into the industry map or leave out)")
        for a in um[:12]:
            L.append(f"    {sorted(a['names'])[0][:44]:<45}{money(a['total']):>14}  {a['items']:>3}×")
        L.append("")

    if excluded:
        L.append("── EXCLUDED NON-CONTRIBUTION RECEIPTS (not donor money; kept out of every total) " + "─" * 2)
        lab = {"transfer": "line-12 transfers from affiliated committees (already gave as line-11)",
               "other_receipt": "line-17 other receipts — crypto-sale proceeds when the PAC "
                                "liquidates donated coin, + interest",
               "refund_offset": "line-15/16 refunds/offsets received"}
        for cat, x in sorted(excluded.items(), key=lambda kv: kv[1]["total"], reverse=True):
            eg = "; ".join(sorted(x["names"])[:3])
            L.append(f"    {money(x['total']):>14}  {x['items']:>3}×  {lab.get(cat, cat)}")
            L.append(f"                       e.g. {eg[:66]}")
        L.append("    (excluding these is what makes the per-player totals reconcile to FEC `contributions`,")
        L.append("     not `receipts` — e.g. Coinbase's $59.9M line-17 'COINBASE COMMERCE' rows are the")
        L.append("     same donated coin being sold, not a second gift)")
        L.append("")

    L.append("* Matches are CANDIDATES: FEC contributor names don't align to LDA names, so the")
    L.append("  norm-key/token match is a report to eyeball, never a silent merge (cleanup C / P6).")
    L.append("* FEC Super-PAC contributions are corporate treasury money; individual gifts are kept")
    L.append("  separate. Scope is FEC-disclosed + LD-203-disclosed — NOT 'total political spending'")
    L.append("  (501(c)(4) dark money and state money are out of both).")
    L.append("* Player totals count LINE-11 CONTRIBUTIONS only — line-12 transfers, line-17 crypto-")
    L.append("  sale proceeds, and line-15/16 refunds are excluded (see above), so figures reconcile to")
    L.append("  FEC `contributions`, not `receipts`. Itemized (>$200) electronic filings — a floor,")
    L.append("  since sub-$200 giving is aggregated/unattributable (negligible for large checks).")
    L.append("  The API reflects the latest amendment, so no version double-counts.")
    L.append("* The cache IS the evidence: cite the FEC transaction_id + committee_id + endpoint +")
    L.append(f"  the cache fetch date. Raw responses: {cache_dir}")
    L.append("* Pair with ld203_giving.py (LD-203 giving) and v_client_canonical_spend (P1 spend).")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names-file", required=True)
    ap.add_argument("--committee-seed", action="append", default=None)
    ap.add_argument("--committee-id", action="append", default=None)
    ap.add_argument("--cycle", nargs="+", type=int, default=[2024, 2026])
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--cache-dir", default="out/fec_cache")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--min-match", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--verify-totals", action="store_true",
                    help="reconcile the itemized non-memo pull against each "
                         "committee's FEC-published receipts total (sanity gate)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    key, key_src = api_key()
    cache_dir = Path(args.cache_dir)
    roster = load_roster(args.names_file)

    # 1. committees
    if args.committee_id:
        committees = [{"committee_id": cid, "name": "(explicit)",
                       "committee_type_full": "(not resolved)", "affiliated": None}
                      for cid in args.committee_id]
    else:
        seeds = args.committee_seed or CRYPTO_NETWORK_SEEDS
        committees = resolve_committees(seeds, key, cache_dir, args.refresh)
    if not committees:
        raise SystemExit("no committees to pull — pass --committee-id or fix --committee-seed")

    # 2. money-in: every itemized receipt of each committee × cycle
    receipts = []
    for c in committees:
        for cyc in args.cycle:
            print(f"  · pulling {c['committee_id']} receipts, cycle {cyc} …", file=sys.stderr)
            receipts += pull_receipts(c["committee_id"], cyc, key, cache_dir, args.refresh)

    # 3. aggregate (line-11 contributions only) + 4. match roster + 5. reconcile
    orgs, indivs, excluded = aggregate_contributors(receipts)
    players, unmatched = build_player_fec(orgs, roster)
    if args.min_match:
        players = {k: v for k, v in players.items() if v["total"] >= args.min_match}
    indiv = build_individuals_by_employer(indivs, roster)

    con = duckdb.connect(args.db, read_only=True)
    recon = reconcile(con, players)
    con.close()

    totals = (verify_totals(committees, args.cycle, receipts, key, cache_dir, args.refresh)
              if args.verify_totals else None)

    if args.json:
        print(json.dumps({
            "cycles": args.cycle, "api_key_source": key_src,
            "committees": committees, "roster_players": len(roster),
            "pull_sanity_totals": totals,
            "excluded_non_contributions": {
                k: {"total": v["total"], "items": v["items"],
                    "examples": sorted(v["names"])} for k, v in (excluded or {}).items()},
            "reconciliation": recon,
            "individuals_by_employer": [
                {"player": v["display"], "total": v["total"], "items": v["items"],
                 "who": sorted(v["who"])} for v in indiv.values()],
            "unmatched_network_donors": [
                {"name": sorted(a["names"])[0], "total": a["total"], "items": a["items"]}
                for a in sorted(unmatched, key=lambda a: a["total"], reverse=True)[:20]],
        }, indent=2, default=str))
    else:
        print(render(committees, args.cycle, recon, indiv, unmatched,
                     len(roster), key_src, cache_dir, args.top, totals, excluded))


if __name__ == "__main__":
    main()
