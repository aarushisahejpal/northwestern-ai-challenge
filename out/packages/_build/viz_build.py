"""Assemble the package dashboards from CSVs + viz templates.

Usage: python viz_build.py [crypto] [aipac] [healthcare] [pardons]
(no args = all; naming packages rebuilds only those, leaving the others'
shipped HTML untouched)
"""
import csv, json, os, re, sys, urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
# This file lives at <repo>/out/packages/_build/ — derive the repo root from
# that instead of hardcoding one machine's checkout path.
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
S = os.path.join(HERE, "inputs")   # durable copies of the 2026-07-08 tool JSONs
# Shared viz templates live in the committed industry-review-packager skill as of
# 2026-07-11 (one copy; this legacy builder and the skill's generator both read it).
VIZ = os.path.join(REPO, "skills", "industry-review-packager", "viz")
GENDATE = os.environ.get("PKG_GENDATE", "2026-07-09")
# PKG_PACKAGES_ROOT lets the packager skill assemble a package into a different
# root (e.g. a regression-regen dir). Packages NOT being rebuilt still read their
# CSVs from the default root (fallback in rd()), so single-package rebuilds work.
PKROOT_DEFAULT = os.path.join(REPO, "out", "packages")
PKROOT = os.environ.get("PKG_PACKAGES_ROOT", PKROOT_DEFAULT)
ONLY = set(sys.argv[1:])

def rd(pkg, name):
    p = os.path.join(PKROOT, pkg, "data", name)
    if not os.path.exists(p) and PKROOT != PKROOT_DEFAULT:
        p = os.path.join(PKROOT_DEFAULT, pkg, "data", name)
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def num(v):
    if v in (None, "", "None"): return None
    return float(v)

def q_label(year, period):
    return f"{year}-Q{ {'first_quarter':1,'second_quarter':2,'third_quarter':3,'fourth_quarter':4}[period] }".replace(" ", "")

FIX = {"Pac":"PAC","Dccc":"DCCC","Nrsc":"NRSC","Nrcc":"NRCC","Dscc":"DSCC","Chci":"CHCI","Cbc":"CBC",
       "Jd":"JD","Ii":"II","Iii":"III","Llc":"LLC","Llp":"LLP","Aipac":"AIPAC","Usa":"USA","Us":"U.S.",
       "Rep":"Rep.","Sen":"Sen.","Jr":"Jr.","Dc":"DC","Rjc":"RJC","Cufi":"CUFI","Zoa":"ZOA","Adl":"ADL",
       "Ajc":"AJC","Aclu":"ACLU","Fdd":"FDD","Aha":"AHA","Ama":"AMA","Ahip":"AHIP","Aarp":"AARP","Phrma":"PhRMA",
       "Tl":"TL","Bgr":"BGR","Ssh":"SSH","Fz":"FZ","Nepa":"NEPA","Tsg":"TSG","Lsn":"LSN","Erl":"ERL",
       "Ncta":"NCTA","Rai":"RAI","Cgcn":"CGCN","Fgs":"FGS","Acg":"ACG","Sbl":"SBL","Hsa":"HSA","Cm":"CM"}
def tcase(s):
    if not s or s != s.upper():
        return s
    words = s.title().split()
    return " ".join(FIX.get(w.strip(".,;"), w) for w in words)

SHORTS = {
    "PHARMACEUTICAL RESEARCH AND MANUFACTURERS OF AMERICA": "PhRMA",
    "AMERICAN HOSPITAL ASSOCIATION": "Am. Hospital Assn",
    "AMERICAN MEDICAL ASSOCIATION": "AMA",
    "AMERICA'S HEALTH INSURANCE PLANS (AHIP)": "AHIP",
    "CHAMBER OF COMMERCE OF THE U.S.A.": "U.S. Chamber",
    "NATIONAL ASSOCIATION OF REALTORS": "Realtors (NAR)",
    "BLUE CROSS BLUE SHIELD ASSOCIATION": "BCBSA",
    "AMERICAN COUNCIL OF LIFE INSURERS": "ACLI",
    "BIOTECHNOLOGY INNOVATION ORGANIZATION": "BIO",
    "AMAZON.COM SERVICES LLC": "Amazon",
    "BUSINESS ROUNDTABLE": "Biz Roundtable",
    "LOCKHEED MARTIN CORPORATION": "Lockheed",
    "GENERAL MOTORS COMPANY": "GM",
    "AMERICAN ISRAEL PUBLIC AFFAIRS COMMITTEE": "AIPAC",
    "INTERNATIONAL BUSINESS MACHINES CORPORATION (IBM)": "IBM",
    "AMERICAN ASSOCIATION FOR JUSTICE": "Assn for Justice",
    "MASTERCARD WORLDWIDE": "Mastercard",
    "FORIS DAX, INC. D/B/A CRYPTO.COM": "Crypto.com",
    "AH CAPITAL MANAGEMENT, LLC (DBA ANDREESSEN HOROWITZ)": "a16z",
    "A16Z CAPITAL MANAGEMENT, L.L.C. (D/B/A ANDREESSEN HOROWITZ)": "a16z",
    "PAYWARD INC. (FORMERLY KNOWN AS PAYWARD INTERACTIVE, INC. D/B/A KRAKEN)": "Kraken",
    "BLOCKCHAIN ASSOCIATION": "Blockchain Assn",
    "CRYPTO COUNCIL FOR INNOVATION": "Crypto Council",
    "DEFI EDUCATION FUND": "DeFi Ed. Fund",
    "NATIONAL ASSOCIATION OF BROADCASTERS": "Broadcasters",
    "AMERICAN BANKERS ASSOCIATION": "Am. Bankers Assn",
    "SECURITIES INDUSTRY AND FINANCIAL MARKETS ASSOCIATION": "SIFMA",
    "INVESTMENT COMPANY INSTITUTE": "ICI",
    "MANAGED FUNDS ASSOCIATION": "MFA",
    "INTERCONTINENTAL EXCHANGE, INC.": "ICE",
}
SUFFIX = re.compile(r"\b(incorporated|inc|llc|l\.l\.c|corp|corporation|company|co|ltd|lp|pllc|plc|n\.?a)\b\.?,?", re.I)
CONTAINS_SHORTS = [("SECURITIES INDUSTRY AND FINANCIAL", "SIFMA"), ("ELECTRONIC TRANSACTIONS", "ETA"),
                   ("DIGITAL CHAMBER", "Digital Chamber"), ("CHAMBER OF DIGITAL", "Digital Chamber"),
                   ("ANCHOR LABS", "Anchorage"), ("ANDREESSEN", "a16z"), ("AH CAPITAL", "a16z"),
                   ("PAYWARD", "Kraken"), ("CRYPTO.COM", "Crypto.com"), ("BLUE CROSS", "BCBSA"),
                   ("AMERICA'S HEALTH INSURANCE", "AHIP"), ("PHARMACEUTICAL CARE MANAGEMENT", "PCMA"),
                   ("FEDERATION OF AMERICAN HOSPITALS", "Fed. Am. Hospitals")]
def shorten(name):
    key = name.upper().strip()
    if key in SHORTS: return SHORTS[key]
    for sub, short in CONTAINS_SHORTS:
        if sub in key: return short
    n = re.sub(r"\(.*?\)", "", name)
    n = n.split(" d/b/a ")[-1] if " d/b/a " in n.lower() else n
    n = n.split(",")[0]
    n = SUFFIX.sub("", n).strip(" ,.")
    n = re.sub(r"\s+", " ", n)
    if len(n) > 17:
        w = n.split()
        n = " ".join(w[:2])
        if len(n) > 17: n = w[0][:16]
    return n

def build(pkg, title, subtitle, extra_sources, data, page_js, gendate=None):
    if ONLY and pkg not in ONLY:
        print(f"[skip] {pkg} (not in {sorted(ONLY)})")
        return
    tpl = open(os.path.join(VIZ, "template.html"), encoding="utf-8").read()
    css = open(os.path.join(VIZ, "shared.css"), encoding="utf-8").read()
    lib = open(os.path.join(VIZ, "lib.js"), encoding="utf-8").read()
    page = open(os.path.join(VIZ, page_js), encoding="utf-8").read()
    html = (tpl.replace("__TITLE__", title).replace("__SUBTITLE__", subtitle)
            .replace("__GENDATE__", gendate or GENDATE).replace("__EXTRA_SOURCES__", extra_sources)
            .replace("__CSS__", css).replace("__LIB__", lib)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__PAGE__", page))
    out_dir = os.path.join(PKROOT, pkg)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{pkg}_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[html] {out}  ({len(html)//1024} KB)")

CODE_NAMES = {"FIN":"Financial institutions & securities","BAN":"Banking","TAX":"Taxation","SCI":"Science & technology",
    "CPI":"Computer industry","CDT":"Commodities trading","AGR":"Agriculture","ACC":"Accounting","GOV":"Government issues",
    "TRD":"Trade","LAW":"Law enforcement & crime","SMB":"Small business","TEC":"Telecommunications","CSP":"Consumer safety",
    "HOM":"Homeland security","ENG":"Energy & nuclear","RET":"Retirement","URB":"Urban development","MON":"Money & gold standard",
    "BUD":"Budget & appropriations","FOR":"Foreign relations","DEF":"Defense","(none)":"(no code recorded)",
    "CIV":"Civil rights & civil liberties","IND":"Indian/Native American affairs","CON":"Constitution",
    "IMM":"Immigration","EDU":"Education","ALC":"Alcohol & drug abuse","REL":"Religion","JUD":"Judiciary",
    "MED":"Medical research","FAM":"Family issues","WEL":"Welfare","VET":"Veterans","LBR":"Labor"}

# ============================ CRYPTO ============================
players_csv = rd("crypto", "crypto_players.csv")
pure = set(x.strip().upper() for x in open(os.path.join(REPO, "out", "crypto_roster_pureplay.txt"), encoding="utf-8"))
players = []
for r in players_csv:
    sp = num(r["total_all_issue_spend"])
    players.append({"name": r["player"], "filings": int(r["crypto_filings_senate"]),
                    "tier": r["tier"], "spend": sp, "vis": r["player"].upper().strip() in pure,
                    # 2026-07-11 intensity metric (healthcare-parity activity share)
                    "share": num(r["crypto_activity_share_pct"]),
                    "band": r["crypto_share_band"],
                    "cblocks": int(r["crypto_activity_blocks"]) if r["crypto_activity_blocks"] else None,
                    "ablocks": int(r["all_activity_blocks"]) if r["all_activity_blocks"] else None})
top_players = sorted(players, key=lambda p: -p["filings"])[:60]
# ... plus core players (sustained, >=8 filings) with a top-15 all-issue budget:
# the scatter's ambient-giant region (bottom-right) exists precisely to place the
# U.S. Chamber ($311.6M, 3.4% share, 14 filings — rank 114 by filings) and AARP
# correctly; a filings-only cut silently hides them
for p in sorted([p for p in players if p["tier"] == "core" and p["spend"]],
                key=lambda p: -p["spend"])[:15]:
    if p not in top_players:
        top_players.append(p)
for p in top_players:
    p["short"] = shorten(p["name"])
# combine known resolver-split name families for the display list (per-variant rows stay in the CSV)
FAMILIES = [(("FORIS", "CRYPTO.COM"), "Crypto.com (Foris entities, combined)"),
            (("PAYWARD", "KRAKEN"), "Kraken (Payward entities, combined)"),
            (("A16Z", "AH CAPITAL", "ANDREESSEN"), "a16z / Andreessen Horowitz (combined)"),
            (("COINBASE",), "Coinbase (combined)"),
            (("BINANCE", "BAM TRADING"), "Binance / Binance.US (combined)")]
def family_of(name):
    u = name.upper()
    for keys, label in FAMILIES:
        if any(k in u for k in keys):
            return label
    return None
merged = {}
for p in players:
    if not (p["vis"] and p["spend"]):
        continue
    fam = family_of(p["name"])
    key = fam or p["name"]
    m = merged.setdefault(key, {"name": key, "spend": 0, "filings": 0})
    m["spend"] += p["spend"]
    m["filings"] += p["filings"]
native_spend = sorted(merged.values(), key=lambda p: -p["spend"])[:12]
# the diversified money list carries the 2026-07-11 intensity gate: >=5% crypto
# activity share, so ambient giants (U.S. Chamber 3.4%, AARP 2.5%) stay off the
# money bars — they remain on the player map (bottom-right) and in every CSV
divers_spend = sorted([p for p in players if not p["vis"] and p["spend"] and p["tier"] == "core"
                       and (p["share"] or 0) >= 5],
                      key=lambda p: -p["spend"])[:12]
trend = rd("crypto", "crypto_quarterly_trend.csv")
tq = [q_label(r["filing_year"], r["filing_period"]) for r in trend]
scatter = rd("crypto", "crypto_issue_code_scatter.csv")[:12]
press = rd("crypto", "crypto_press_quarterly.csv")
recip = rd("crypto", "crypto_ld203_pureplay_recipients.csv")
split = rd("crypto", "crypto_ld203_recipients_split.csv")
# three-tier split (2026-07-11 intensity gate): a=native, b=crypto-forward
# diversified (>=5% activity share), c=ambient (<5% — context only: never drawn
# as a bar in a crypto chart; carried into tooltip, click panel, table, CSV)
split_rows = [{"name": r["recipient"], "a": num(r["from_crypto_native"]) or 0,
               "b": num(r["from_diversified_forward"]) or 0,
               "c": num(r["from_ambient_lowshare"]) or 0,
               "party": r["party"]} for r in split]
giv_top = sorted(split_rows, key=lambda r: -(r["a"] + r["b"]))[:10]
member_rows = [r for r in split_rows if r["party"]]
giv_members_native = sorted(member_rows, key=lambda r: -r["a"])[:10]
giv_members_div = sorted(member_rows, key=lambda r: -r["b"])[:10]
fecr = rd("crypto", "crypto_fec_superpac_vs_ld203.csv")
FECN = {"AH Capital Management, LLC (dba Andreessen Horowitz)": "a16z / Andreessen Horowitz",
        "Cornerstone Government Affairs obo Circle Internet Financial, Inc.": "Circle Internet Financial",
        "PAYWARD INC. (FORMERLY KNOWN AS PAYWARD INTERACTIVE, INC. D/B/A KRAKEN)": "Payward / Kraken",
        "JUMP CRYPTO HOLDINGS LLC": "Jump Crypto", "UNISWAP LABS": "Uniswap Labs",
        "MULTICOIN CAPITAL": "Multicoin Capital", "BLOCKCHAIN (US), INC.": "Blockchain.com"}
fec = sorted([{"name": FECN.get(r["player"], r["player"]), "fec": num(r["fec_superpac_contributions"]) or 0,
               "ld203": num(r["ld203_disclosed_giving"]) or 0, "conf": r["match_confidence"]}
              for r in fecr], key=lambda d: -d["fec"])[:8]
# per-player raw-filing links (embedded for the players shown on the map; the
# full 500+-player index ships as data/crypto_player_filings.csv)
PQ2 = {"first_quarter": "Q1", "second_quarter": "Q2", "third_quarter": "Q3",
       "fourth_quarter": "Q4", "mid_year": "MY", "year_end": "YE"}
# money-widget bars -> the underlying player entities (family rows span several)
fam_members = {}
for p in players:
    if p["vis"] and p["spend"]:
        fam = family_of(p["name"])
        if fam:
            fam_members.setdefault(fam, []).append(p["name"])
bar_players = {}
for p in native_spend:
    bar_players[p["name"]] = fam_members.get(p["name"], [p["name"]])
for p in divers_spend:
    bar_players[p["name"]] = [p["name"]]

map_names = {p["name"] for p in top_players} | {m for ms in bar_players.values() for m in ms}
player_filings = {}
for r in rd("crypto", "crypto_player_filings.csv"):
    if r["player"] not in map_names:
        continue
    label = f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}"
    amt = num(r["reported_amount"])
    is_reg = 1 if r["filing_type"].startswith("R") else 0  # LD-1 registration vs LD-2 report
    player_filings.setdefault(r["player"], []).append(
        [r["filing_uuid"], label, tcase(r["registrant_name"]) or r["registrant_name"], amt, is_reg,
         r["matched_keywords"]])
# chronological order (the CSV sorts filing_period alphabetically: Q1, Q4, Q2, Q3)
Q_ORDER = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "MY": 5, "YE": 6}
for lst in player_filings.values():
    lst.sort(key=lambda f: (f[1][:4], Q_ORDER.get(f[1][5:7], 9), f[2]))

# ---- underlying-record embeds for the other widgets (Rob 2026-07-10) ----
PARTY_L = {"Democrat": "D", "Republican": "R", "Independent": "I"}

# trend: quarter -> its amendment-deduped filings (counts reconcile with the chart)
trend_filings = {}
for r in rd("crypto", "crypto_trend_filings.csv"):
    q = q_label(r["filing_year"], r["filing_period"])
    trend_filings.setdefault(q, []).append(
        [r["filing_uuid"], r["player"],
         tcase(r["registrant_name"]) or r["registrant_name"], num(r["reported_amount"]),
         r["matched_keywords"]])

# scatter: issue code -> senate filings behind its blocks (top 150 by amount)
_shown_codes = {r["issue_code"] for r in scatter}
scatter_filings = {}
for r in rd("crypto", "crypto_issue_code_filings.csv"):
    c = r["issue_code"]
    if c not in _shown_codes:
        continue
    e = scatter_filings.setdefault(c, {"senBlocks": 0, "nFilings": 0, "rows": []})
    e["senBlocks"] += int(r["n_crypto_blocks_in_filing"])
    e["nFilings"] += 1
    if len(e["rows"]) < 150:
        e["rows"].append(
            [r["filing_uuid"], r["player"],
             tcase(r["registrant_name"]) or r["registrant_name"],
             f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}",
             num(r["reported_amount"]), int(r["n_crypto_blocks_in_filing"]),
             r["matched_keywords"]])

# money: bar label -> quarter-by-quarter v_client_canonical_spend rows
_sq = {}
for r in rd("crypto", "crypto_spend_quarters.csv"):
    _sq.setdefault(r["player"], []).append(
        [f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}",
         r["player"], num(r["inhouse_amount"]) or 0, num(r["outside_amount"]) or 0,
         num(r["canonical_spend"]) or 0, r["method"]])
spend_quarters = {}
for bar, members in bar_players.items():
    rows_ = [row for m in members for row in _sq.get(m, [])]
    rows_.sort(key=lambda x: (x[0][:4], Q_ORDER.get(x[0][5:7], 9), x[1]))
    spend_quarters[bar] = rows_

# giving: displayed recipient row -> the LD-203 items behind it (three slices)
_SLICE_KEY = {"crypto_native": "native", "diversified_forward": "forward",
              "ambient_lowshare": "ambient"}
giving_items = {}
for r in rd("crypto", "crypto_ld203_items.csv"):
    e = giving_items.setdefault(r["display_row"],
                                {"native": [], "forward": [], "ambient": []})
    e[_SLICE_KEY[r["giver_slice"]]].append(
        [r["filing_uuid"], tcase(r["ld203_filer_org"]) or r["ld203_filer_org"],
         r["date"], num(r["amount"]), r["contribution_type"],
         int(r["n_amendment_versions"])])

# press: quarter -> the matching releases (counts reconcile with the chart)
press_releases = {}
for r in rd("crypto", "crypto_press_releases.csv"):
    press_releases.setdefault(r["quarter"], []).append(
        [r["date"], r["member_name"], PARTY_L.get(r["party"], (r["party"] or "?")[:1]),
         r["state"], (r["title"] or "")[:110], r["url"]])

# fec: player row -> matched names + committees + tids + filtered FEC-browser links
_fec_cids = [row["committee_id"] for row in rd("crypto", "crypto_fec_committees.csv")]
_fec_base = ("https://www.fec.gov/data/receipts/?data_type=processed&"
             + "&".join(f"committee_id={c}" for c in _fec_cids)
             + "&contributor_name=")
fec_detail = {}
for r in fecr:
    disp = FECN.get(r["player"], r["player"])
    conts = [c.strip() for c in (r["fec_contributor_names"] or "").split(";") if c.strip()]
    fec_detail[disp] = {
        "conf": r["match_confidence"], "committees": r["committees"],
        "tids": r["sample_transaction_ids"],
        "links": [[c, _fec_base + urllib.parse.quote(c)] for c in conts]}
_lex = json.loads(open(os.path.join(REPO, "skills", "lead-scanner", "scripts", "industry_lexicon.json"), encoding="utf-8").read())
_cfacet = next(f for f in _lex["facets"] if f["tag"] == "CRYPTO")
vocab_rows = [{"kw": r["keyword"], "n": int(r["filings"])} for r in rd("crypto", "crypto_keywords.csv")]
crypto_data = {
    "kpis": [
        {"label": "Client orgs lobbying on crypto, 2025-Q4", "value": "287", "note": "vs 177 in 2024-Q4 (+62%)"},
        {"label": "Crypto-tagged filings, 2025-Q4", "value": "391", "note": "flat ~240/qtr through 2022–2024"},
        {"label": "Top-4 players' Super-PAC money (FEC)", "value": "$322.6M", "note": "vs $1.7M in disclosed LD-203 — different regimes"},
    ],
    "players": top_players,
    "vocab": {"version": _lex["_meta"]["version"], "phrases": vocab_rows,
              "rejected": [{"term": k, "why": w} for k, w in _cfacet.get("display_only", {}).items()]},
    "playerFilings": player_filings,
    "trendFilings": trend_filings,
    "scatterFilings": scatter_filings,
    "spendQuarters": spend_quarters,
    "barPlayers": bar_players,
    "givingItems": giving_items,
    "pressReleases": press_releases,
    "fecDetail": fec_detail,
    "trend": {"q": tq, "filings": [int(r["crypto_filings"]) for r in trend],
              "clients": [int(r["crypto_clients"]) for r in trend],
              "spend": [num(r["canonical_spend_tagged_clients"]) for r in trend]},
    "issueScatter": [{"code": r["issue_code"], "name": CODE_NAMES.get(r["issue_code"], ""),
                      "docs": int(r["crypto_docs"]), "pct": num(r["pct_of_crypto"])} for r in scatter],
    "nativeSpend": [{"name": p["name"], "spend": p["spend"], "filings": p["filings"]} for p in native_spend],
    "diversSpend": [{"name": p["name"], "spend": p["spend"], "filings": p["filings"]} for p in divers_spend],
    "givingTop": giv_top,
    "givingMembersNative": giv_members_native,
    "givingMembersDiv": giv_members_div,
    "givingRecipientsRaw": [{"name": r["recipient"], "party": r["party"],
                             "a": num(r["from_crypto_native"]) or 0,
                             "b": num(r["from_diversified_forward"]) or 0,
                             "c": num(r["from_ambient_lowshare"]) or 0} for r in split[:40]],
    "fec": fec,
    "press": {"q": [r["quarter"] for r in press], "share": [num(r["crypto_share_pct"]) for r in press],
              "n": [int(r["crypto_releases"]) for r in press], "all": [int(r["all_releases"]) for r in press]},
    "queryInfo": None,  # filled below (extracted from the export scripts)
    "findings": [
        {"id": "L029", "status": "open", "title": "LD-203 giving map — committee-targeting concentration",
         "hypothesis": "Disclosed LD-203 giving from the crypto roster concentrates on the members who write crypto rules — Sen. Cynthia Lummis, Rep. French Hill (House Financial Services chair), Rep. Tom Emmer, Sen. Pat Toomey — atop a ~$5.0M cluster to the Trump-Vance inaugural (Coinbase/Paradigm/Crypto.com/Kraken each ~$1M; Galaxy Digital $1.08M found on re-derivation).",
         "actors": "Coinbase; Kraken/Payward; Paradigm; Crypto.com; Sen. Lummis; Rep. French Hill; Rep. Emmer; Sen. Toomey; Trump-Vance Inaugural Committee",
         "next": "Separate the novel committee-targeting angle from the already-known inaugural-giving category (set aside in Entities checked); teammate triage of the pure-play slice."},
        {"id": "L030", "status": "open", "title": "P4 player map — the name-invisible crypto lobby",
         "hypothesis": "493 of 535 client-side crypto players (92%) carry no crypto term in their name — found only by what they say they lobby on: PayPal, Block, Robinhood, Visa, Mastercard, Fidelity/FMR, Citigroup, CME Group, American Bankers Assoc., Western Union.",
         "actors": "Coinbase; Robinhood; PayPal; Visa; Mastercard; Fidelity/FMR; Citigroup",
         "next": "Human-triage the recall-first player list (raise --min-docs / drop incidental mentions); separate the diversified-filer angle from the pure-play crypto lobby."},
        {"id": "L031", "status": "open", "title": "FEC money-leg completion — Super-PAC dwarfs disclosed giving",
         "hypothesis": "FEC-disclosed Super-PAC contributions (Fairshake network) dwarf the same players' LD-203 disclosed giving by 1-2 orders of magnitude: Coinbase $106.59M FEC vs $1.70M LD-203; Ripple $96.5M vs $0; a16z $94.5M vs $0; Jump Crypto $25M vs $0.",
         "actors": "Coinbase; Ripple Labs; a16z/AH Capital Management; Jump Crypto; Fairshake / Defend American Jobs / Protect Progress Super PACs",
         "next": "Human-triage the candidate FEC↔LDA entity matches (raise confidence to exact where resolvable); decide FEC-vs-LD-203 framing for a finding."},
    ],
    "caveats": [
        "Recall-first map: any client whose filing free-text names one of " + str(len(_cfacet["phrases"])) + " curated crypto phrases (lexicon v" + _lex["_meta"]["version"] + ") is included; incidental one-off mentions sit in the peripheral tier by design. A story names specific players from the CSVs, never 'the whole list.'",
        "Spend figures are each player's TOTAL federal lobbying spend across all issues (canonical, double-count-corrected) — a size signal. Filing-level disclosure cannot split dollars by issue. The crypto activity share (crypto-tagged senate activity blocks ÷ all the client's senate activity blocks) is the intensity companion: it says how much of the filer's declared attention is crypto, never how its dollars split.",
        "The ≥5% activity-share gate (diversified money list, giving split) is an EDITORIAL cut, chosen to track the healthcare package's precedent (the U.S. Chamber reads 5.4% health there and was classed a side-desk, not a player). The 15 gated-out ambient givers and their $38.8M stay in every CSV, the giving tooltip/click-through, and the table views — excluded from crypto-titled charts, never from the data.",
        "Share is computed per resolved entity: known resolver-split families (Mastercard ×3 entities at 58/18/9%, Visa ×2, a16z, Kraken/Payward) each carry their own share; the spend bars combine families, the map plots entities. Per-variant rows are in data/crypto_players.csv.",
        "Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated; share denominators exclude LD-1 registrations.",
        "LD-203 'disclosed giving' is the lobbyist-side regime only, and it is organization-level: the giver split shows WHO funds a recipient, never why. Super-PAC money (Fairshake network) legally lives in FEC data — the two never sum.",
        "FEC↔lobbying name matches are candidates for human confirmation (shown with confidence labels). Entity resolution is the ceiling: a few companies (Kraken/Payward, a16z) file under multiple names and are recovered manually.",
        "Everything is self-reported disclosure data. 'Disclosed' never means 'total': 501(c)(4) dark money and state lobbying are outside every number here."
    ]
}

# ---- per-widget query info (debugging aid, Rob 2026-07-10) ----
# The SQL shown in the dashboard is EXTRACTED FROM THE EXPORT SCRIPTS' SOURCE at
# build time, so it can't drift from what actually produced the CSVs.
def _read(p):
    return open(p, encoding="utf-8").read()

def _grab(src, pattern):
    m = re.search(pattern, src, re.S)
    return m.group(1).strip() if m else "(extraction failed — read the source file)"

_exc = _read(os.path.join(REPO, "out", "packages", "crypto", "_build", "export_crypto.py"))
_exf = _read(os.path.join(REPO, "out", "packages", "crypto", "_build", "export_player_filings.py"))
_giv = _read(os.path.join(REPO, "skills", "lead-scanner", "scripts", "lda_ld203_giving.py"))
_res = _read(os.path.join(REPO, "skills", "lda-entity-resolver", "scripts", "resolve_entities.py"))

_name_vis = _grab(_exc, r'NAME_VIS = r"(.*)"')
q_players_sql = _grab(_exc, r'q_players = f"""(.*?)"""').replace("{NAME_VIS}", _name_vis)
q_trend_sql = _grab(_exc, r'q_trend = """(.*?)"""')
q_scatter_sql = _grab(_exc, r'sql_csv\("crypto_issue_code_scatter\.csv", """(.*?)"""\)')
q_press_sql = _grab(_exc, r'sql_csv\("crypto_press_quarterly\.csv", r"""(.*?)"""\)')
q_filings_sql = _grab(_exf, r'\nQ = """(.*?)"""')
_recip = _grab(_giv, r'RECIP = "(.*)"')
q_ld203_base = "WITH " + (_grab(_giv, r'\nBASE = """(.*?)"""')
                          .replace("{recip}", _recip)
                          .replace("{where}", "-- (+ optional --type / --since filters)"))
q_canon_view = _grab(_res, r'CANONICAL_SPEND_VIEW = """(.*?)"""')

_DB = ("DB: db/lda_full.duckdb (read-only). Rebuild the DB: lda-corpus-loader/build_db.py → "
       "lda-entity-resolver/resolve_entities.py → lead-scanner/lda_industry_map.py --build-tags.")

def _qi(title, note, blocks=()):
    return {"title": title, "note": note, "dict": "DATA_DICTIONARY.md",
            "blocks": [{"label": l, "text": t} for l, t in blocks]}

crypto_data["queryInfo"] = {
    "vocab": {"title": "Vocabulary — where the phrase list and counts come from",
              "note": "The phrase list IS skills/lead-scanner/scripts/industry_lexicon.json (CRYPTO facet; versioned, with rejected terms recorded in display_only). Counts come from the serving table that lda_industry_map.py --build-tags materializes from it.",
              "sql": "SELECT keyword, count(DISTINCT record_key) AS filings\nFROM lobbying_issue_mentions\nWHERE tag='CRYPTO' AND dataset='senate'\nGROUP BY keyword ORDER BY filings DESC"},
    "kpis": _qi("Header stats — where each number comes from",
        "287 / 391 = the 2025-Q4 row (vs 2024-Q4) of the quarterly-trend query below "
        "(→ data/crypto_quarterly_trend.csv). $322.6M = sum of the top-4 rows of "
        "data/crypto_fec_superpac_vs_ld203.csv — an openFEC API pull, not DB SQL (see the "
        "FEC widget's query info). " + _DB,
        [("quarterly-trend SQL · _build/export_crypto.py → data/crypto_quarterly_trend.csv",
          q_trend_sql)]),
    "players": _qi("Player map — the queries behind it",
        "Dots = data/crypto_players.csv (SQL 1: crypto-tagged senate filings resolved to "
        "client entities; spend column sums v_client_canonical_spend; the acts CTE computes "
        "the crypto ACTIVITY SHARE — crypto-tagged senate free-text blocks ÷ all the "
        "client's senate blocks, registrations excluded — mirroring the healthcare "
        "package's activity-share semantics). Click-through filing "
        "lists = data/crypto_player_filings.csv (SQL 2; one lda.senate.gov URL per "
        "filing_uuid: https://lda.senate.gov/filings/public/filing/<uuid>/print/). " + _DB,
        [("SQL 1 — players · _build/export_crypto.py → data/crypto_players.csv", q_players_sql),
         ("SQL 2 — raw-filing index · _build/export_player_filings.py → data/crypto_player_filings.csv",
          q_filings_sql)]),
    "trend": _qi("Quarterly trend — the query behind it",
        "→ data/crypto_quarterly_trend.csv. Amendments deduped on (registrant_id, client_id, "
        "filing_year, filing_period) keeping latest-by-posted; registrations (R*) excluded; "
        "spend via v_client_canonical_spend. " + _DB,
        [("SQL · _build/export_crypto.py → data/crypto_quarterly_trend.csv", q_trend_sql)]),
    "scatter": _qi("Issue-code scatter — the query behind it",
        "→ data/crypto_issue_code_scatter.csv: crypto-tagged free-text blocks grouped by the "
        "ALI issue code the registrant filed them under. " + _DB,
        [("SQL · _build/export_crypto.py → data/crypto_issue_code_scatter.csv", q_scatter_sql)]),
    "money": _qi("Spend lists — the queries behind them",
        "Per-player totals come from the players query (SQL 1) whose spend column sums "
        "v_client_canonical_spend — the rollup-corrected client-spend view (SQL 2): per "
        "(client, quarter) canonical = greatest(in-house, outside), never their sum. "
        "Left list restricted to the hand-triaged roster out/crypto_roster_pureplay.txt; "
        "right list gated to diversified core players with ≥5% crypto activity share "
        "(the 2026-07-11 intensity gate — ambient giants like the U.S. Chamber stay on the "
        "map and in the CSVs, not on these bars); known name families (Foris/Crypto.com, "
        "Payward/Kraken, a16z) combined for display. " + _DB,
        [("SQL 1 — players · _build/export_crypto.py → data/crypto_players.csv", q_players_sql),
         ("SQL 2 — CREATE VIEW v_client_canonical_spend · skills/lda-entity-resolver/scripts/resolve_entities.py",
          q_canon_view)]),
    "giving": _qi("LD-203 giving — how these numbers are produced",
        "Produced by tool runs, not one SQL: skills/lead-scanner/scripts/lda_ld203_giving.py "
        "--json --top 999999 (exhaustive recipient lists) for three rosters — "
        "out/crypto_roster_pureplay.txt (105 crypto-native), out/crypto_roster_div_forward.txt "
        "(147 diversified core with ≥5% crypto activity share) and "
        "out/crypto_roster_div_ambient.txt (15 below the gate; forward+ambient partition the "
        "old 162-name diversified roster exactly, asserted per raw recipient string at build "
        "time by _build/enhance_giving.py). Slices are then member-merged by "
        "_build/enhance_giving.py (name variants → one member; every merge auditable in "
        "data/crypto_ld203_member_variant_audit.csv; the earlier build merged only each "
        "run's top-400 recipient rows, so per-member diversified figures here RECOVER "
        "sub-cutoff variants — a correction, itemized in the audit CSV). Citeable SQL "
        "blocks: queries/ld203_giving.sql G1a–G1d. The tool's core de-dup CTE is below — "
        "LD-203 amendments collapse on the full contribution identity; _reg holds the "
        "resolved LD-203 filer names for the roster.",
        [("amendment-dedup CTE · skills/lead-scanner/scripts/lda_ld203_giving.py", q_ld203_base)]),
    "fec": _qi("FEC vs LD-203 — pipeline (external openFEC API, not DB SQL)",
        "FEC side: skills/lead-scanner/scripts/fec_enrich.py --names-file out/crypto_roster.txt "
        "--verify-totals. Committees resolved live from /v1/committees (Fairshake C00835959, "
        "Defend American Jobs C00836221, Protect Progress C00848440); receipts from "
        "/v1/schedules/schedule_a per committee (paginated per_page=100), keeping LINE-11 "
        "contributions only — memo_code='X' attribution rows and line-17 crypto-sale proceeds "
        "excluded; individuals split from corporate treasury on entity_type='IND'. Raw JSON "
        "cached in out/fec_cache/ (the citeable evidence, incl. transaction ids). Sanity gate: "
        "line-11 sums reconcile to FEC published 'contributions' (never 'receipts'). LD-203 "
        "side: same pipeline as the giving widget. → data/crypto_fec_superpac_vs_ld203.csv"),
    "press": _qi("Press share — the query behind it",
        "→ data/crypto_press_quarterly.csv: whole-word regex over member press releases "
        "(title + text), share per quarter. " + _DB,
        [("SQL · _build/export_crypto.py → data/crypto_press_quarterly.csv", q_press_sql)]),
}
# click-through provenance, per widget (the lists reconcile to the chart numbers
# at export time — _build/export_player_filings.py / export_widget_underlying.py)
_CLICK = {
    "players": "CLICK-THROUGH: click a dot to list its raw filings (full index: data/crypto_player_filings.csv).",
    "trend": "CLICK-THROUGH: click a quarter to list exactly the deduped filings it counts (data/crypto_trend_filings.csv — per-quarter counts reconcile with this chart at export time).",
    "scatter": "CLICK-THROUGH: click a code bar to list the senate filings behind its blocks (data/crypto_issue_code_filings.csv; top 150 by amount embedded).",
    "money": "CLICK-THROUGH: click a bar for its quarter-by-quarter v_client_canonical_spend rows (data/crypto_spend_quarters.csv — per-player sums reconcile with the bars) plus its crypto-tagged filings.",
    "giving": "CLICK-THROUGH: click a recipient bar for the amendment-deduped LD-203 items behind it (data/crypto_ld203_items.csv — item sums reconcile with the chart), each linking to the filed report on lda.senate.gov.",
    "fec": "CLICK-THROUGH: click a player row for its matched FEC contributor names, sample transaction ids, and filtered FEC receipts-browser links.",
    "press": "CLICK-THROUGH: click a quarter to list the matching releases (data/crypto_press_releases.csv — counts reconcile with this chart).",
    "kpis": "Click-throughs live on the widgets themselves: the trend chart lists each quarter's filings; the FEC chart lists the transactions side.",
}
for _k, _s in _CLICK.items():
    crypto_data["queryInfo"][_k]["note"] = _s + " " + crypto_data["queryInfo"][_k]["note"]

# ============================ AIPAC ============================
aq = rd("aipac", "aipac_quarterlies.csv")
coup = rd("aipac", "aipac_press_coupling.csv")
gov = rd("aipac", "aipac_gov_entities.csv")
bills = rd("aipac", "aipac_bills.csv")
colob = rd("aipac", "aipac_bill_colobbyists.csv")
ispl = rd("aipac", "israel_policy_players.csv")
agrec = rd("aipac", "aipac_ld203_recipients.csv")
agy = rd("aipac", "aipac_ld203_by_year.csv")
lob = rd("aipac", "aipac_lobbyists.csv")
acts = rd("aipac", "aipac_activities.csv")

def bill_hint(bill):
    # find a name for the bill in AIPAC's own activity text: "H.R.1422/S.556 - Enhanced Iran Sanctions Act"
    pretty = re.sub(r"^([A-Z]+?)(\d+)$", lambda m: {"HR":"H.R.","S":"S.","HRES":"H.Res.","SRES":"S.Res.",
                    "HCONRES":"H.Con.Res.","SCONRES":"S.Con.Res.","HJRES":"H.J.Res.","SJRES":"S.J.Res."}.get(m.group(1), m.group(1)) + m.group(2), bill)
    pat = re.compile(re.escape(pretty).replace(r"\.", r"\.?\s?") + r"[^-–]*[-–]\s*([A-Z][^;.\n]{4,70})")
    for a in acts:
        m = pat.search(a["description"])
        if m:
            return m.group(1).strip().rstrip(",")
    return ""

top_bills = []
for r in bills[:12]:
    top_bills.append({"bill": r["bill"], "n": int(r["aipac_filings"]), "hint": bill_hint(r["bill"])})

# ---- underlying-record embeds (2026-07-12, same "see the actual filings"
# pattern as crypto/pardons/healthcare; AIPAC's own volume is small — no caps
# needed) ----
ap_press_releases = {}
for r in rd("aipac", "aipac_press_releases.csv"):
    ap_press_releases.setdefault(r["quarter"], []).append(
        [r["date"], r["member_name"], PARTY_L.get(r["party"], (r["party"] or "?")[:1]),
         r["state"], (r["title"] or "")[:110], r["url"]])
ap_quarter_filing = {q_label(r["filing_year"], r["filing_period"]): r["show_record_key"] for r in aq}

ap_gov_entity_filings = {}
for r in rd("aipac", "aipac_gov_entity_filings.csv"):
    ap_gov_entity_filings.setdefault(r["entity_name"], []).append(
        [r["filing_uuid"], f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}",
         num(r["reported_amount"])])

top_bill_codes = {b["bill"] for b in top_bills}
ap_bill_filings = {}
for r in rd("aipac", "aipac_bill_filings.csv"):
    if r["bill"] not in top_bill_codes:
        continue
    ap_bill_filings.setdefault(r["bill"], []).append(
        [r["filing_uuid"], f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}",
         num(r["reported_amount"])])

top_colobby_clients = {r["client"] for r in colob[:15]}
ap_colobby_filings = {}
for r in rd("aipac", "aipac_colobby_filings.csv"):
    if r["client"] not in top_colobby_clients:
        continue
    ap_colobby_filings.setdefault(r["client"], []).append(
        [r["filing_uuid"], r["bill"], tcase(r["registrant_name"]) or r["registrant_name"],
         f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}", num(r["reported_amount"])])

top_israel_players = {r["player"] for r in ispl if "AMERICAN ISRAEL PUBLIC AFFAIRS" not in r["player"].upper()}
ap_israel_player_filings = {}
for r in rd("aipac", "aipac_israel_player_filings.csv"):
    if r["player"] not in top_israel_players:
        continue
    ap_israel_player_filings.setdefault(r["player"], []).append(
        [r["filing_uuid"], f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}",
         tcase(r["registrant_name"]) or r["registrant_name"], num(r["reported_amount"])])

ap_lobbyist_filings = {}
for r in rd("aipac", "aipac_lobbyist_filings.csv"):
    key = tcase(r["first_name"] + " " + r["last_name"])
    ap_lobbyist_filings.setdefault(key, []).append(
        [r["filing_uuid"], f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}"])

top_recip_names = {r["recipient"] for r in agrec[:15]}
ap_giving_recip_items, ap_giving_year_items = {}, {}
for r in rd("aipac", "aipac_giving_items.csv"):
    row = [r["filing_uuid"], tcase(r["recipient_raw"]) or r["recipient_raw"], r["date"],
           num(r["amount"]), r["contribution_type"], int(r["n_amendment_versions"])]
    if r["recipient_display"] in top_recip_names:
        ap_giving_recip_items.setdefault(r["recipient_display"], []).append(row)
    ap_giving_year_items.setdefault(r["filing_year"], []).append(row)

aipac_data = {
    "kpis": [
        {"label": "2025 lobbying spend (in-house)", "value": "$3.76M", "note": "+38% vs 2022; steady ~9%/yr climb"},
        {"label": "Quarterly filings 2022–2026Q1", "value": "17 / 17", "note": "no amendments, no gaps — a clean self-filer"},
        {"label": "Disclosed LD-203 giving 2022–25", "value": "$7.65M", "note": "100% FECA contributions, both parties"},
        {"label": "Bills named in filings", "value": str(len(bills)), "note": "Iran sanctions, aid approps, U.S.–Israel defense"},
    ],
    "coupling": {"q": [r["quarter"] for r in coup], "amount": [num(r["aipac_reported_amount"]) for r in coup],
                 "share": [num(r["israel_share_pct"]) for r in coup], "rel": [int(r["israel_releases"]) for r in coup],
                 "all": [int(r["all_releases"]) for r in coup]},
    "quarterFiling": ap_quarter_filing,
    "pressReleases": ap_press_releases,
    "govEntities": [{"name": r["entity_name"], "n": int(r["mentions"])} for r in gov],
    "govEntityFilings": ap_gov_entity_filings,
    "nBills": len(bills),
    "topBills": top_bills,
    "billFilings": ap_bill_filings,
    "billsTable": [{"bill": r["bill"], "n": int(r["aipac_filings"]), "y0": r["first_year"], "y1": r["last_year"]} for r in bills[:60]],
    "coLobby": [{"name": tcase(r["client"]), "raw": r["client"], "bills": int(r["shared_distinctive_bills"]),
                 "filings": int(float(r["filings_on_those_bills"]))} for r in colob[:15]],
    "coLobbyFilings": ap_colobby_filings,
    "israelPlayers": [{"name": tcase(r["player"]), "raw": r["player"], "n": int(r["israel_filings"]),
                       "spend": num(r["total_all_issue_spend"])}
                      for r in ispl if "AMERICAN ISRAEL PUBLIC AFFAIRS" not in r["player"].upper()][:18],
    "israelPlayerFilings": ap_israel_player_filings,
    "givingRecipients": [{"name": r["recipient"], "total": num(r["total"]), "items": int(r["items"])} for r in agrec[:15]],
    "givingRecipientItems": ap_giving_recip_items,
    "givingByYear": [{"y": r["filing_year"], "total": num(r["total"])} for r in agy],
    "givingYearItems": ap_giving_year_items,
    "givingTotal": 7652150,
    "partySplit": json.load(open(os.path.join(S, "aipac_party_split.json")))["psum"],
    "lobbyists": [{"name": tcase(r["first_name"] + " " + r["last_name"]), "filings": int(r["filings"]),
                   "years": f"{r['first_year']}–{r['last_year']}"} for r in lob],
    "lobbyistFilings": ap_lobbyist_filings,
    "queryInfo": None,  # filled below
    "findings": [
        {"id": "L032", "status": "open", "title": "AIPAC review package — ratchet budget vs. Oct-7 press spike",
         "hypothesis": "AIPAC's lobbying budget is a planned ratchet insensitive to news shocks: Israel-topic share of member press releases jumps 2.6%→20.3% in 2023-Q4 (~8x, Oct-7) while AIPAC's own quarterly spend moves only +6.6% and never breaks its steady ~9%/yr climb. Disclosed LD-203 giving ($7.65M, 2022-25) is strikingly bipartisan; the co-lobby field on AIPAC's distinctive bills spans both camps at near-identical coverage (J Street 146 shared bills, FDD Action 146). The exploratory Israel-policy free-text scan flags non-obvious entries (Chevron — Eastern-Med gas leases; terror-victim litigation estates) alongside the expected advocacy orgs.",
         "actors": "AIPAC; J Street; FDD Action; Chevron U.S.A.; Rep. Randy Weber; Rep. Joseph Morelle; Rep. Ritchie Torres",
         "next": "Teammate triage of the synthesis package; FEC leg on AIPAC-affiliated Super-PAC spending (United Democracy Project) — same LD-203≠FEC boundary as crypto's Fairshake; promote the Israel-policy scan vocabulary to industry_lexicon.json before citing the field list in a story."},
    ],
    "caveats": [
        "AIPAC self-files (in-house registrant): quarterly amounts are its own reported lobbying spend, not payments to outside firms. No outside-firm engagements appear for AIPAC in this window.",
        "'Co-lobbying a bill' means filing on the same bill — allies and opponents both appear; direction of advocacy is not in the disclosure data.",
        "The Israel-policy field scan is an exploratory whole-word text search (israel/gaza/antisemitism/etc.), not the curated lexicon pipeline; treat the list as a triage candidate set.",
        "Press releases are congressional members' releases — the 'say' side of Congress, not AIPAC's own communications.",
        "LD-203 disclosed giving is the lobbyist-side regime; AIPAC-affiliated Super-PAC spending (e.g. United Democracy Project) lives in FEC data and is not included here.",
        "Senate-primary, amendment-deduplicated; every table row traces to a filing UUID in the CSVs."
    ]
}

# ---- per-widget query info (debugging aid, matching the crypto/pardons dashboards) ----
_exa = _read(os.path.join(REPO, "out", "packages", "aipac", "_build", "export_aipac.py"))
_exau = _read(os.path.join(REPO, "out", "packages", "aipac", "_build", "export_aipac_underlying.py"))
_ap_aipac = _grab(_exa, r'AIPAC = "(.*)"')
_ap_israel_re = _grab(_exa, r'ISRAEL_RE = r"(.*)"')
_ap_qord = _grab(_exa, r'QORD = "(.*)"')


def _resolve_ap(sql):
    return sql.replace("{AIPAC}", _ap_aipac).replace("{ISRAEL_RE}", _ap_israel_re).replace("{QORD}", _ap_qord)


q_ap_quarterlies_sql = _resolve_ap(_grab(_exa, r'wcsv\("aipac_quarterlies\.csv", f"""(.*?)"""\)'))
q_ap_gov_sql = _resolve_ap(_grab(_exa, r'wcsv\("aipac_gov_entities\.csv", f"""(.*?)"""\)'))
q_ap_bills_sql = _resolve_ap(_grab(_exa, r'wcsv\("aipac_bills\.csv", f"""(.*?)"""\)'))
q_ap_colobby_sql = _resolve_ap(_grab(_exa, r'wcsv\("aipac_bill_colobbyists\.csv", f"""(.*?)"""\)'))
q_ap_israel_sql = _resolve_ap(_grab(_exa, r'wcsv\("israel_policy_players\.csv", f"""(.*?)"""\)'))
q_ap_press_coupling_sql = _resolve_ap(_grab(_exa, r'wcsv\("aipac_press_coupling\.csv", f"""(.*?)"""\)'))
q_ap_lobbyists_sql = _resolve_ap(_grab(_exa, r'wcsv\("aipac_lobbyists\.csv", f"""(.*?)"""\)'))
q_ap_press_sql = _resolve_ap(_grab(_exau, r'Q_PRESS = f"""(.*?)"""'))
q_ap_gov_filings_sql = _resolve_ap(_grab(_exau, r'Q_GOV = f"""(.*?)"""'))
q_ap_bill_filings_sql = _resolve_ap(_grab(_exau, r'Q_BILLS = f"""(.*?)"""'))
q_ap_colobby_filings_sql = _resolve_ap(_grab(_exau, r'Q_COLOBBY = f"""(.*?)"""'))
q_ap_israel_filings_sql = _resolve_ap(_grab(_exau, r'Q_ISRAEL = f"""(.*?)"""'))
q_ap_lobbyist_filings_sql = _resolve_ap(_grab(_exau, r'Q_LOB = f"""(.*?)"""'))
q_ap_items_sql = _grab(_exau, r'Q_ITEMS = """(.*?)"""')

_APDB = ("DB: db/lda_full.duckdb (read-only). AIPAC = registrant_name ILIKE "
         "'%AMERICAN ISRAEL PUBLIC AFFAIRS%' — a clean self-filer (registrant==client, "
         "no amendments in window). Rebuild: lda-corpus-loader/build_db.py → "
         "lda-entity-resolver/resolve_entities.py.")

aipac_data["queryInfo"] = {
    "kpis": _qi("Header stats — where each number comes from",
        "$3.76M / 17 filings / bills count are AIPAC's own quarterly filings (data/"
        "aipac_quarterlies.csv); $7.65M is the LD-203 giving total (data/aipac_ld203_recipients.csv, "
        "exhaustive --top 999999 run). " + _APDB,
        [("AIPAC quarterlies SQL · export_aipac.py → data/aipac_quarterlies.csv", q_ap_quarterlies_sql)]),
    "coupling": _qi("Budget vs. press cycle — the queries behind it",
        "Top panel = AIPAC's own reported quarterly amount (one filing per quarter — click links "
        "straight to it). Bottom panel = share of ALL member press releases matching the Israel/Gaza "
        "regex that quarter; click-through releases in data/aipac_press_releases.csv. " + _APDB,
        [("SQL · export_aipac.py → data/aipac_press_coupling.csv", q_ap_press_coupling_sql),
         ("raw-release index · export_aipac_underlying.py → data/aipac_press_releases.csv", q_ap_press_sql)]),
    "govEntities": _qi("Who is lobbied — the query behind it",
        "→ data/aipac_gov_entities.csv: senate_gov_entities mentions on AIPAC's own filings. "
        "Click-through filings = data/aipac_gov_entity_filings.csv. " + _APDB,
        [("SQL 1 — mentions · export_aipac.py → data/aipac_gov_entities.csv", q_ap_gov_sql),
         ("SQL 2 — raw-filing index · export_aipac_underlying.py → data/aipac_gov_entity_filings.csv",
          q_ap_gov_filings_sql)]),
    "bills": _qi("Bills — the query behind it",
        "→ data/aipac_bills.csv: bill_mentions on AIPAC's own filings, ranked by filing count. "
        "Click-through filings = data/aipac_bill_filings.csv. " + _APDB,
        [("SQL 1 — bills · export_aipac.py → data/aipac_bills.csv", q_ap_bills_sql),
         ("SQL 2 — raw-filing index · export_aipac_underlying.py → data/aipac_bill_filings.csv",
          q_ap_bill_filings_sql)]),
    "coLobby": _qi("Co-lobbyists — the query behind it",
        "→ data/aipac_bill_colobbyists.csv: other clients filing on AIPAC's DISTINCTIVE bills "
        "(≤200 lobbying engagements corpus-wide, so mega-bills like the NDAA don't drown the "
        "signal). Click-through filings = data/aipac_colobby_filings.csv (top 15 shown here). " + _APDB,
        [("SQL 1 — co-lobbyists · export_aipac.py → data/aipac_bill_colobbyists.csv", q_ap_colobby_sql),
         ("SQL 2 — raw-filing index · export_aipac_underlying.py → data/aipac_colobby_filings.csv",
          q_ap_colobby_filings_sql)]),
    "israelPlayers": _qi("The wider Israel-policy field — the query behind it",
        "→ data/israel_policy_players.csv: EXPLORATORY whole-word regex scan over senate filing "
        "free-text (not the curated lexicon pipeline) — ≥2 matching filings. Click-through filings "
        "= data/aipac_israel_player_filings.csv (top 18 shown here). " + _APDB,
        [("SQL 1 — players · export_aipac.py → data/israel_policy_players.csv", q_ap_israel_sql),
         ("SQL 2 — raw-filing index · export_aipac_underlying.py → data/aipac_israel_player_filings.csv",
          q_ap_israel_filings_sql)]),
    "giving": _qi("LD-203 giving — how these numbers are produced",
        "Produced by skills/lead-scanner/scripts/lda_ld203_giving.py \"american israel public "
        "affairs committee\" --top 999999 --json (exhaustive recipient list — a --top 400 cut "
        "silently drops long-tail recipients), then member-merged by enhance_giving.py (first-seen-"
        "wins per normalized key — see giving_match.py's first_seen_display()). Item-level query "
        "below buckets every de-duplicated item to BOTH its recipient display row and its filing "
        "year, so both bars on this widget click through to the same underlying set. " + _APDB,
        [("SQL — de-duped items · export_aipac_underlying.py → data/aipac_giving_items.csv", q_ap_items_sql)]),
    "lobbyists": _qi("The in-house team — the query behind it",
        "→ data/aipac_lobbyists.csv: senate_lobbyists rows on AIPAC's filings (one row per "
        "filing×activity in the raw table — de-duped to one per filing here). Click-through "
        "filings = data/aipac_lobbyist_filings.csv. " + _APDB,
        [("SQL 1 — lobbyists · export_aipac.py → data/aipac_lobbyists.csv", q_ap_lobbyists_sql),
         ("SQL 2 — raw-filing index · export_aipac_underlying.py → data/aipac_lobbyist_filings.csv",
          q_ap_lobbyist_filings_sql)]),
}
_APCLICK = {
    "coupling": "CLICK-THROUGH: click a quarter bar for its filing; click a point on the press line for that quarter's matching releases.",
    "govEntities": "CLICK-THROUGH: click a bar to list AIPAC's filings naming that entity.",
    "bills": "CLICK-THROUGH: click a bar to list AIPAC's filings naming that bill.",
    "coLobby": "CLICK-THROUGH: click a bar to list that client's filings on the shared bills.",
    "israelPlayers": "CLICK-THROUGH: click a bar to list that player's Israel-topic filings.",
    "giving": "CLICK-THROUGH: click any bar (recipients or by-year) for the amendment-deduped LD-203 items behind it, each linking to the filed report on lda.senate.gov.",
    "lobbyists": "CLICK-THROUGH: click a bar to list that lobbyist's filings.",
    "kpis": "Click-throughs live on the widgets themselves.",
}
for _k, _s in _APCLICK.items():
    aipac_data["queryInfo"][_k]["note"] = _s + " " + aipac_data["queryInfo"][_k]["note"]

# ============================ HEALTHCARE ============================
hpl = rd("healthcare", "hc_players.csv")
htr = rd("healthcare", "hc_quarterly_trend.csv")
hct = rd("healthcare", "hc_code_trend.csv")
hpr = rd("healthcare", "hc_press_coupling.csv")
hbl = rd("healthcare", "hc_bills.csv")
hgo = rd("healthcare", "hc_ld203_by_org.csv")
hgr = rd("healthcare", "hc_ld203_recipients.csv")
hsplit = rd("healthcare", "hc_ld203_recipients_split.csv")
hsplit_rows = [{"name": r["recipient"], "a": num(r["from_health_focused"]) or 0,
                "b": num(r["from_mixed_diversified"]) or 0, "party": r["party"]} for r in hsplit]
hgiv_top = sorted(hsplit_rows, key=lambda r: -(r["a"] + r["b"]))[:10]
hgiv_members = sorted([r for r in hsplit_rows if r["party"]], key=lambda r: -(r["a"] + r["b"]))[:12]
hc_focused_set = set(x.strip().upper() for x in open(os.path.join(REPO, "out", "healthcare_roster_focused.txt"), encoding="utf-8") if x.strip())
hq = [q_label(r["filing_year"], r["filing_period"]) for r in htr]
hcodes = {"HCR": {}, "MMM": {}, "PHA": {}, "MED": {}}
for r in hct:
    ql = q_label(r["filing_year"], r["filing_period"])
    if r["general_issue_code"] in hcodes:
        hcodes[r["general_issue_code"]][ql] = int(r["filings"])
hplayers = []
for r in hpl:
    sp = num(r["total_all_issue_spend"])
    if not sp: continue
    share = num(r["health_activity_share_pct"]) or 0
    filings = int(r["health_filings"])
    if share < 10 and filings < 30:
        continue  # not meaningfully a health player; stays in the CSV
    cls = 0 if share >= 50 else (1 if share >= 20 else 2)
    hplayers.append({"name": r["player"], "short": shorten(r["player"]), "spend": sp,
                     "share": share, "filings": filings, "cls": cls})
    if len(hplayers) >= 55: break
HINTS = {"HR5376": "Inflation Reduction Act (drug pricing)", "HR3": "drug-price negotiation (117th)",
         "HR1": "2025 reconciliation (Medicaid changes)"}

# ---- underlying-record embeds (2026-07-12, Rob's ask: every widget should let
# the user see the actual underlying filings/records with links, same pattern
# as the crypto/pardons dashboards) ----
HC_CAP = 150  # healthcare's per-quarter/per-player volume is ~10x crypto's; cap
              # embedded rows per bucket like crypto's scatter widget does (full
              # lists always ship in the CSV — this bounds the HTML embed size)
hpf_names = {p["name"] for p in hplayers}
hc_player_filings_all = {}
for r in rd("healthcare", "hc_player_filings.csv"):
    if r["player"] not in hpf_names:
        continue
    label = f"{r['filing_year']} {PQ2.get(r['filing_period'], r['filing_period'])}"
    hc_player_filings_all.setdefault(r["player"], []).append(
        [r["filing_uuid"], label, tcase(r["registrant_name"]) or r["registrant_name"],
         num(r["reported_amount"]), r["health_codes"]])
hc_player_filings_total = {k: len(v) for k, v in hc_player_filings_all.items()}
hc_player_filings = {}
for name, lst in hc_player_filings_all.items():
    lst.sort(key=lambda f: -(f[3] or 0))
    hc_player_filings[name] = sorted(lst[:HC_CAP], key=lambda f: (f[1][:4], Q_ORDER.get(f[1][5:7], 9)))

hc_trend_totals, hc_trend_filings = {}, {}
for r in rd("healthcare", "hc_trend_filings.csv"):
    q = q_label(r["filing_year"], r["filing_period"])
    hc_trend_totals[q] = hc_trend_totals.get(q, 0) + 1
    lst = hc_trend_filings.setdefault(q, [])
    if len(lst) < HC_CAP:
        lst.append([r["filing_uuid"], r["player"], tcase(r["registrant_name"]) or r["registrant_name"],
                    num(r["reported_amount"]), r["health_codes"]])

hc_code_trend_totals, hc_code_trend_filings = {}, {}  # quarter -> {code: [[uuid, player, reg, amt], ...]}
for r in rd("healthcare", "hc_code_trend_filings.csv"):
    q = q_label(r["filing_year"], r["filing_period"])
    code = r["general_issue_code"]
    hc_code_trend_totals[(q, code)] = hc_code_trend_totals.get((q, code), 0) + 1
    e = hc_code_trend_filings.setdefault(q, {"HCR": [], "MMM": [], "PHA": [], "MED": []})
    if code in e and len(e[code]) < HC_CAP:
        e[code].append([r["filing_uuid"], r["player"],
                        tcase(r["registrant_name"]) or r["registrant_name"], num(r["reported_amount"])])

hc_press_totals, hc_press_releases = {}, {}
for r in rd("healthcare", "hc_press_releases.csv"):
    hc_press_totals[r["quarter"]] = hc_press_totals.get(r["quarter"], 0) + 1
    lst = hc_press_releases.setdefault(r["quarter"], [])
    if len(lst) < HC_CAP:
        lst.append([r["date"], r["member_name"], PARTY_L.get(r["party"], (r["party"] or "?")[:1]),
                    r["state"], (r["title"] or "")[:110], r["url"]])

top_bill_names = {r["bill"] for r in hbl[:12]}
hc_bill_totals, hc_bill_filings = {}, {}
for r in rd("healthcare", "hc_bill_filings.csv"):
    if r["bill"] not in top_bill_names:
        continue
    hc_bill_totals[r["bill"]] = hc_bill_totals.get(r["bill"], 0) + 1
    lst = hc_bill_filings.setdefault(r["bill"], [])
    if len(lst) < HC_CAP:
        lst.append([r["filing_uuid"], r["player"], tcase(r["registrant_name"]) or r["registrant_name"],
                    num(r["reported_amount"])])

top_org_raw = {r["ld203_filer_org"] for r in hgo[:10]}
hc_giving_org_items = {}
for r in rd("healthcare", "hc_giving_org_items.csv"):
    if r["ld203_filer_org"] not in top_org_raw:
        continue
    hc_giving_org_items.setdefault(r["ld203_filer_org"], []).append(
        [r["filing_uuid"], tcase(r["recipient"]) or r["recipient"], r["date"], num(r["amount"]),
         r["contribution_type"], int(r["n_amendment_versions"])])

hc_giving_recipient_items = {}
for r in rd("healthcare", "hc_giving_recipient_items.csv"):
    e = hc_giving_recipient_items.setdefault(r["display_row"], {"health_focused": [], "mixed_diversified": []})
    e[r["giver_slice"]].append(
        [r["filing_uuid"], tcase(r["ld203_filer_org"]) or r["ld203_filer_org"], r["date"],
         num(r["amount"]), r["contribution_type"], int(r["n_amendment_versions"])])

hc_data = {
    "kpis": [
        {"label": "Health-coded filings per quarter", "value": "~4,000", "note": "stable 2022–24; 2025 peak 4,384 (+9%)"},
        {"label": "Canonical spend of health-active clients, 2025", "value": "$1.69B", "note": "all-issue spend of clients filing on health that quarter"},
        {"label": "Peak press share, 2025-Q4", "value": "28.8%", "note": "of ALL member releases — Medicaid + ACA-subsidy fight"},
        {"label": "Disclosed LD-203 giving (top-150 orgs)", "value": "$107.8M", "note": "2022–25; AHA is the top giver at $9.7M"},
    ],
    "players": hplayers,
    "playerFilings": hc_player_filings,
    "playerFilingsTotal": hc_player_filings_total,
    "trendFilings": hc_trend_filings,
    "trendFilingsTotal": hc_trend_totals,
    "codeTrendFilings": hc_code_trend_filings,
    "codeTrendFilingsTotal": {f"{q}|{c}": n for (q, c), n in hc_code_trend_totals.items()},
    "pressReleases": hc_press_releases,
    "pressReleasesTotal": hc_press_totals,
    "billFilings": hc_bill_filings,
    "billFilingsTotal": hc_bill_totals,
    "givingOrgItems": hc_giving_org_items,
    "givingRecipientItems": hc_giving_recipient_items,
    "trend": {"q": hq, "filings": [int(r["health_filings"]) for r in htr],
              "clients": [int(r["health_clients"]) for r in htr],
              "spend": [num(r["canonical_spend_hc_clients"]) for r in htr]},
    "codeTrend": {"q": hq, "HCR": [hcodes["HCR"].get(q) for q in hq], "MMM": [hcodes["MMM"].get(q) for q in hq],
                  "PHA": [hcodes["PHA"].get(q) for q in hq], "MED": [hcodes["MED"].get(q) for q in hq]},
    "press": {"q": [r["quarter"] for r in hpr], "share": [num(r["health_press_share_pct"]) for r in hpr],
              "n": [int(r["health_releases"]) for r in hpr], "all": [int(r["all_releases"]) for r in hpr]},
    "topBills": [{"bill": r["bill"], "clients": int(r["clients"]), "filings": int(r["filings"]),
                  "hint": HINTS.get(r["bill"], "")} for r in hbl[:12]],
    "givingOrgs": [{"name": tcase(r["ld203_filer_org"]), "raw": r["ld203_filer_org"],
                    "total": num(r["disclosed_giving_total"]),
                    "focused": r["ld203_filer_org"].strip().upper() in hc_focused_set} for r in hgo[:10]],
    "givingTop": hgiv_top,
    "givingMembers": hgiv_members,
    "givingTotal": 107769783,
    "queryInfo": None,  # filled below
    "findings": [
        {"id": "L033", "status": "open", "title": "Healthcare review package — installed base, not a surge industry",
         "hypothesis": "The largest standing lobbying operation in the corpus is a stable installed base (~4,000 filings / ~2,950 clients every quarter 2022-24, 2025 peak +9% on the reconciliation Medicaid fight), not a breakout like crypto. Health press share sets a corpus record 28.8% of all member releases in 2025-Q4. Activity-level share (not filing-level, which is a self-filer artifact) separates pure-plays PhRMA (68.8%)/AHA (51%)/AHIP (71.6%) from side-desk giants AARP (23.4%)/Amazon (5.2%)/U.S. Chamber (5.4%). LD-203 giving of the top-150 health orgs is $107.8M 2022-25, AHA the top giver at $9.7M; HR1-2025 is the most crowded bill (792 distinct clients).",
         "actors": "PhRMA; American Hospital Association; American Medical Association; AHIP; AARP; Altria",
         "next": "Teammate triage of the synthesis package; candidate deep-dives: the 2025-Q4 28.8% press record vs. the flat filing base (extends L026), AHA's $9.7M giving map, the HR1-2025 crowd."},
        {"id": "L026", "status": "triaged", "title": "Medicare/Medicaid say-vs-pay divergence",
         "hypothesis": "Congressional press attention-share on MMM more than doubles in 2025 (2.4%→5.7% of tagged releases, Q2) during the reconciliation Medicaid-cut fight, while MMM lobbying-money share FALLS every year (9.09%→7.55% of Q2 spend, 2022→2025) — the loud press voices (Durbin, Jeffries, Warren, Clark, Luján) are entirely different actors from the steady paid healthcare-industry clients (American Health Care Assoc., American College of Clinical Pharmacy, Virginia Hospital & Healthcare Assoc.).",
         "actors": "Richard J. Durbin; Hakeem Jeffries; Elizabeth Warren; American Health Care Association; American College of Clinical Pharmacy",
         "next": "Deep-read a sample of the 2025-Q2 MMM press releases to confirm the message is anti-cut (not industry-aligned); determine whether the money-share decline is a real reallocation or a denominator effect; editorial framing of 'messaging vs. money.'"},
    ],
    "caveats": [
        "Scope = filings whose activities carry ALI issue codes HCR (health), MMM (Medicare/Medicaid), PHA (pharmacy) or MED (medical research). Unlike crypto, healthcare is code-visible, so the issue-code lens is primary.",
        "Spend is each client's TOTAL canonical lobbying spend (all issues) in quarters where it filed on health — an upper-bound size signal, since filing-level disclosure cannot split dollars by issue.",
        "Health-activity share separates pure-plays from diversified giants: a self-filer's single quarterly filing lists dozens of issues, so shares are computed on activity rows, not filings.",
        "LD-203 giving is organization-level: solid for pure-play trade groups (AHA, AMA, ADA), inflated for diversified filers (AARP, Altria) whose giving is not health-specific.",
        "Senate-primary, amendment-deduplicated; registrations excluded from dollar work.",
        "Recipient names are lightly-normalized filing strings, not entity-resolved."
    ]
}

# ---- per-widget query info (debugging aid, matching the crypto/pardons dashboards) ----
_exh = _read(os.path.join(REPO, "out", "packages", "healthcare", "_build", "export_healthcare.py"))
_exhu = _read(os.path.join(REPO, "out", "packages", "healthcare", "_build", "export_healthcare_underlying.py"))
_hc_codes = _grab(_exh, r'CODES = "(.*)"')
_hc_filings_cte = _grab(_exh, r'HC_FILINGS = f"""\n(.*?)"""').replace("{CODES}", _hc_codes)
_hc_qord = _grab(_exh, r'QORD = "(.*)"')


def _resolve_hc(sql):
    sql = sql.replace("{HC_FILINGS}", _hc_filings_cte).replace("{CODES}", _hc_codes)
    return re.sub(r"\{QORD\.replace\('filing_period','([^']+)'\)\}",
                  lambda m: _hc_qord.replace("filing_period", m.group(1)), sql)


q_hc_players_sql = _resolve_hc(_grab(_exh, r'_, players = wcsv\("hc_players\.csv", f"""(.*?)"""\)'))
q_hc_trend_sql = _resolve_hc(_grab(_exh, r'wcsv\("hc_quarterly_trend\.csv", f"""(.*?)"""\)'))
q_hc_code_sql = _resolve_hc(_grab(_exh, r'wcsv\("hc_code_trend\.csv", f"""(.*?)"""\)'))
q_hc_bills_sql = _resolve_hc(_grab(_exh, r'wcsv\("hc_bills\.csv", f"""(.*?)"""\)'))
q_hc_press_sql = _resolve_hc(_grab(_exh, r'wcsv\("hc_press_coupling\.csv", f"""(.*?)"""\)'))
q_hc_players_filings_sql = _resolve_hc(_grab(_exhu, r"Q_PLAYERS = f\"\"\"(.*?)\"\"\""))
q_hc_trend_filings_sql = _resolve_hc(_grab(_exhu, r"Q_TREND = f\"\"\"(.*?)\"\"\""))
q_hc_code_filings_sql = _resolve_hc(_grab(_exhu, r"Q_CODE = f\"\"\"(.*?)\"\"\""))
q_hc_press_filings_sql = _resolve_hc(_grab(_exhu, r"Q_PRESS = f\"\"\"(.*?)\"\"\""))
q_hc_bill_filings_sql = _resolve_hc(_grab(_exhu, r"Q_BILLS = f\"\"\"(.*?)\"\"\""))
q_hc_org_items_sql = _grab(_exhu, r'Q_ORG_ITEMS = """(.*?)"""')
q_hc_recip_items_sql = _grab(_exhu, r'Q_RECIP_ITEMS = """(.*?)"""')

_HCDB = ("DB: db/lda_full.duckdb (read-only). Scope = senate_activities.general_issue_code IN "
         "('HCR','MMM','PHA','MED') — no curated lexicon needed (healthcare is ALI-code-visible, "
         "unlike crypto). Rebuild: lda-corpus-loader/build_db.py → lda-entity-resolver/resolve_entities.py.")

hc_data["queryInfo"] = {
    "kpis": _qi("Header stats — where each number comes from",
        "~4,000 / $1.69B / 28.8% / $107.8M are the 2025 rows of the quarterly-trend and "
        "press-coupling queries below plus the giving totals (data/hc_ld203_by_org.csv, top "
        "150 roster). " + _HCDB,
        [("quarterly-trend SQL · export_healthcare.py → data/hc_quarterly_trend.csv", q_hc_trend_sql)]),
    "players": _qi("Player map — the queries behind it",
        "Bubbles = data/hc_players.csv (SQL 1: health-coded senate filings resolved to client "
        "entities; the acts CTE computes health-activity share on ACTIVITY rows, not filings — "
        "a self-filer's single quarterly filing lists dozens of issues, so filing-level share "
        "would read ~100% for every mega-filer). Click-through filing lists = "
        "data/hc_player_filings.csv (SQL 2; one lda.senate.gov URL per filing_uuid). " + _HCDB,
        [("SQL 1 — players · export_healthcare.py → data/hc_players.csv", q_hc_players_sql),
         ("SQL 2 — raw-filing index · export_healthcare_underlying.py → data/hc_player_filings.csv",
          q_hc_players_filings_sql)]),
    "trend": _qi("Quarterly trend — the query behind it",
        "→ data/hc_quarterly_trend.csv. Amendments deduped on (registrant_id, client_id, "
        "filing_year, filing_period) keeping latest-by-posted; registrations excluded; spend via "
        "v_client_canonical_spend. " + _HCDB,
        [("SQL · export_healthcare.py → data/hc_quarterly_trend.csv", q_hc_trend_sql),
         ("raw-filing index · export_healthcare_underlying.py → data/hc_trend_filings.csv",
          q_hc_trend_filings_sql)]),
    "codeTrend": _qi("Issue mix — the query behind it",
        "→ data/hc_code_trend.csv: amendment-deduped filings joined to senate_activities, grouped "
        "by (quarter, general_issue_code) — a filing carrying 2 of the 4 codes counts once in "
        "EACH code's line. " + _HCDB,
        [("SQL · export_healthcare.py → data/hc_code_trend.csv", q_hc_code_sql),
         ("raw-filing index · export_healthcare_underlying.py → data/hc_code_trend_filings.csv",
          q_hc_code_filings_sql)]),
    "press": _qi("Press share — the query behind it",
        "→ data/hc_press_coupling.csv: filings tagged via press_issue_mentions.issue_code IN "
        "('HCR','MMM','PHA','MED'), share per quarter of ALL member releases. " + _HCDB,
        [("SQL · export_healthcare.py → data/hc_press_coupling.csv", q_hc_press_sql),
         ("raw-release index · export_healthcare_underlying.py → data/hc_press_releases.csv",
          q_hc_press_filings_sql)]),
    "bills": _qi("Bills — the query behind it",
        "→ data/hc_bills.csv: bill_mentions joined to health-coded filings, ranked by distinct "
        "clients lobbying each bill. " + _HCDB,
        [("SQL · export_healthcare.py → data/hc_bills.csv", q_hc_bills_sql),
         ("raw-filing index · export_healthcare_underlying.py → data/hc_bill_filings.csv",
          q_hc_bill_filings_sql)]),
    "giving": _qi("LD-203 giving — how these numbers are produced",
        "Produced by skills/lead-scanner/scripts/lda_ld203_giving.py --json --top 999999 "
        "(exhaustive recipient lists — a --top 400 cut silently drops long-tail recipients, the "
        "same truncation trap already fixed once for crypto) against two rosters — "
        "out/healthcare_roster_focused.txt (health-focused, ≥50% health activities) and "
        "out/healthcare_roster_mixed.txt (mixed/diversified, <50%) — then member-merged by "
        "enhance_giving.py the same way as crypto's giving split. Left bars (orgs) query the "
        "top-150 roster directly, item-level via Q_ORG_ITEMS. Right bars (recipients/members) "
        "bucket items to the exact display row enhance_giving.py's first-seen-wins merge picked "
        "(a raw variant like 'DSCC' and 'Democratic Senatorial Campaign Committee' both roll up "
        "into one displayed row — see giving_match.py's first_seen_display()). " + _HCDB,
        [("SQL 1 — org items · export_healthcare_underlying.py → data/hc_giving_org_items.csv",
          q_hc_org_items_sql),
         ("SQL 2 — recipient/member items · export_healthcare_underlying.py → data/hc_giving_recipient_items.csv",
          q_hc_recip_items_sql)]),
}
_HCLICK = {
    "players": "CLICK-THROUGH: click a bubble to list its health-coded filings (full index: data/hc_player_filings.csv).",
    "trend": "CLICK-THROUGH: click a quarter to list exactly the deduped filings it counts (data/hc_trend_filings.csv).",
    "codeTrend": "CLICK-THROUGH: click a quarter to list the filings behind each code that quarter (data/hc_code_trend_filings.csv).",
    "press": "CLICK-THROUGH: click a quarter to list the matching releases (data/hc_press_releases.csv).",
    "bills": "CLICK-THROUGH: click a bar to list the filings naming that bill (data/hc_bill_filings.csv).",
    "giving": "CLICK-THROUGH: click any bar for the amendment-deduped LD-203 items behind it, each linking to the filed report on lda.senate.gov.",
    "kpis": "Click-throughs live on the widgets themselves.",
}
for _k, _s in _HCLICK.items():
    hc_data["queryInfo"][_k]["note"] = _s + " " + hc_data["queryInfo"][_k]["note"]

# ============================ PARDONS ============================
ppl = rd("pardons", "pardons_players.csv")
ptr = rd("pardons", "pardons_quarterly_trend.csv")
psc = rd("pardons", "pardons_issue_code_scatter.csv")
pkw = rd("pardons", "pardons_keywords.csv")
prg = rd("pardons", "pardons_registrant_firms.csv")
pen = rd("pardons", "pardons_engagements.csv")
ppr = rd("pardons", "pardons_press_quarterly.csv")
ppf = rd("pardons", "pardons_player_filings.csv")
prl = rd("pardons", "pardons_press_releases.csv")

PCLS = {"seeker": 0, "seeker_vehicle": 1, "advocacy": 2, "unclear": 3}
pplayers = [{"name": r["player"], "short": shorten(tcase(r["player"]) or r["player"]),
             "filings": int(r["pardons_filings_senate"]), "spend": num(r["total_all_issue_spend"]),
             "cls": PCLS[r["client_class"]], "note": r["class_note"],
             "y0": r["first_year"], "y1": r["last_year"]} for r in ppl]

PQ2P = {"first_quarter": "Q1", "second_quarter": "Q2", "third_quarter": "Q3",
        "fourth_quarter": "Q4", "mid_year": "MY", "year_end": "YE"}
p_player_filings = {}
for r in ppf:
    lab = f"{r['filing_year']} {PQ2P.get(r['filing_period'], r['filing_period'])} ({r['filing_type']})"
    p_player_filings.setdefault(r["player"], []).append(
        [r["filing_uuid"], lab, tcase(r["registrant_name"]) or r["registrant_name"],
         num(r["reported_amount"]), 1 if r["filing_type"].startswith("R") else 0,
         r.get("matched_keywords") or ""])

p_trend_filings = {}
for r in rd("pardons", "pardons_trend_filings.csv"):
    q = q_label(r["filing_year"], r["filing_period"])
    p_trend_filings.setdefault(q, []).append(
        [r["filing_uuid"], r["player"],
         tcase(r["registrant_name"]) or r["registrant_name"], num(r["reported_amount"]),
         r.get("matched_keywords") or ""])

p_press_releases = {}
for r in prl:
    p_press_releases.setdefault(r["quarter"], []).append(
        [r["date"], r["member_name"], {"Democrat": "D", "Republican": "R", "Independent": "I"}.get(r["party"], (r["party"] or "")[:1]),
         r["state"], (r["title"] or "")[:110], r["url"]])

p_engagements = [{"player": e["player"], "reg": tcase(e["registrant_name"]) or e["registrant_name"],
                  "q0": e["first_tagged_quarter"], "q1": e["last_tagged_quarter"],
                  "nq": int(e["tagged_quarters"]), "total": num(e["reported_total_tagged_quarters"]),
                  "term": e["terminated"] == "yes", "termQ": e["termination_quarter"],
                  "cls": e["client_class"], "text": (e["declared_text_sample"] or "")[:220],
                  "uuid": e["sample_filing_uuid"]} for e in pen]
p_mkt = round(sum(e["total"] or 0 for e in p_engagements))
p_nterm = sum(1 for e in p_engagements if e["term"])
p_nseek = sum(1 for p in pplayers if p["cls"] in (0, 1))
p_pre_avg = sum(int(r["pardons_filings"]) for r in ptr[:11]) / 11.0   # 2022Q1–2024Q3
p_post_avg = sum(int(r["pardons_filings"]) for r in ptr[11:]) / max(1, len(ptr[11:]))

pardons_data = {
    "kpis": [
        {"label": "Paid pardon-seeker market, disclosed billings", "value": f"${p_mkt/1e6:.2f}M",
         "note": f"{len(p_engagements)} engagements · {p_nseek} seeker clients · {p_nterm} declared-terminated"},
        {"label": "Pardon/clemency-tagged filings 2022–2026Q1", "value": "366",
         "note": f"{len(pplayers)} client organizations & individuals (senate-primary)"},
        {"label": "Tagged filings per quarter", "value": f"~{p_pre_avg:.0f} → ~{p_post_avg:.0f}",
         "note": "2022–2024Q3 baseline vs 2024-Q4 onward (22 in 2024-Q4 alone)"},
        {"label": "Pardon press peak, 2025-Q1", "value": "156 releases",
         "note": "1.13% of ALL member releases — ~10× the 2022–24 norm; 2026-Q1: 132"},
    ],
    "players": pplayers,
    "playerFilings": p_player_filings,
    "engagements": p_engagements,
    "trend": {"q": [q_label(r["filing_year"], r["filing_period"]) for r in ptr],
              "filings": [int(r["pardons_filings"]) for r in ptr],
              "clients": [int(r["pardons_clients"]) for r in ptr]},
    "trendFilings": p_trend_filings,
    "pressReleases": p_press_releases,
    "scatter": [{"code": r["issue_code"], "name": CODE_NAMES.get(r["issue_code"], ""),
                 "docs": int(r["pardons_docs"]), "pct": num(r["pct_of_pardons"])} for r in psc[:14]],
    "keywords": [{"kw": r["keyword"], "filings": int(r["filings"])} for r in pkw],
    "registrants": [{"name": tcase(r["registrant_name"]) or r["registrant_name"],
                     "filings": int(r["pardons_filings"]), "clients": int(r["clients"]),
                     "amt": num(r["reported_amount_ranking_signal"])} for r in prg],
    "press": {"q": [r["quarter"] for r in ppr], "share": [num(r["pardon_share_pct"]) for r in ppr],
              "n": [int(r["pardon_releases"]) for r in ppr], "all": [int(r["all_releases"]) for r in ppr]},
    "queryInfo": None,  # filled below
    "findings": [
        {"id": "L034", "status": "open", "title": "Turnover-lens paid pardon-seeking market — termination-closure timing",
         "hypothesis": "The P3 turnover tracker surfaces a paid pardon-seeking market closed out by termination filings: Roger Ver pays Drake Ventures (Roger Stone's firm) $600K + Sterling Green $70K; Torence Hatch (Boosie Badazz) pays J M Burkman & Associates $600K; Joseph Schwartz pays Burkman $960K + Merkava Strategies $100K. Outside-context-scan confirms the asks' outcomes are checkable against public record: Schwartz was PARDONED ~2025-11-21 (his termination follows by weeks); Ver was NOT pardoned (a $49.9M deferred-prosecution deal instead). The case list itself is scooped by NOTUS/WaPo/NBC coverage — the candidate-novel angle is the systematic termination-closure timing, not the market's existence.",
         "actors": "Roger Ver; Torence Hatch (Boosie Badazz); Joseph Schwartz; J M Burkman & Associates; Drake Ventures LLC (Roger Stone)",
         "next": "Hatch's outcome is still unresolved (sentencing was set for Jan-2026; his termination posted 2026-Q1 — pardoned, sentenced, or dropped?). Editorial/legal-sensitivity review still required (living persons). Frame any finding around termination-closure timing, not market existence."},
        {"id": "L035", "status": "open", "title": "Pardons industry map — the paid seeker market, sized and field-mapped",
         "hypothesis": "27 seeker engagements (after a same-day fix for registration-only tag credit) total $6.21M disclosed billings, 10 declared-terminated. 'Executive relief' resolves corpus-wide to exactly Binance Holdings + Changpeng Zhao + Fred Daibes (L021). Outside-context-scan confirms the beat is covered (NOTUS is effectively this map as a case list) — but coverage has NOT named several small-dollar engagements: Origin Property Group/Marco Bitran, Juno Empire/Jorge Ferrer, Alvarez, Belli, Camino, Healthicity, Magma Power, and Selim Zherka (LegiStorm trade-press only). No outlet has published the field-level quantification (37-code scatter, seeker-vs-advocacy split, termination-closure timing).",
         "actors": "Changpeng Zhao; Binance Holdings; Fred Daibes; Selim Zherka; Marco Bitran; Jorge Ferrer; The Vogel Group; J M Burkman & Associates",
         "next": "Teammate triage; outcome checks still pending for Bitran, Ferrer, Alvarez, Tierney, Patel, Pramaggiore, Scrushy, Hatch. Editorial/legal-sensitivity review required — living persons named throughout (same flag as L021/L034)."},
        {"id": "L021", "status": "triaged", "title": "Fred Daibes — 'Executive relief' via an ex-Trump aide",
         "hypothesis": "Fred Daibes (convicted in the Sen. Menendez bribery case) pays $1M to lobby for 'Executive relief' (clemency); the registered lobbyist is Keith Schiller, former Director of Oval Office Operations under Trump. Daibes is one of exactly three clients corpus-wide who use the 'executive relief' euphemism (with Binance/Zhao — see L035), so he sits directly in this package's player map.",
         "actors": "Fred Daibes; Javelin Advisors LLC; Keith Schiller",
         "next": "Editorial/legal-sensitivity review (living person, active clemency ask); verify Schiller's covered-position status; check the NULL-income quarters for continued engagement."},
    ],
    "caveats": [
        "Recall boundary: only engagements whose filing free-text uses the 8-phrase pardon/clemency vocabulary appear. Engagements that never say the word are invisible — Roger Ver's Drake Ventures ($600K) and Sterling Green engagements (ledger L034) declare 'US government prosecution of Roger Ver' and are NOT on this map; the quarterly-turnover lens caught them instead. The two lenses are complements.",
        "Engagement dollars are the pair's full reported billing for quarters where the tagged language appears — filing-level disclosure cannot split dollars by issue (Binance's engagements also cover digital-asset lobbying). Several engagements report no income at all (self-reported data); the market total is a floor.",
        "Player bubble 'total lobbying spend' is ALL-ISSUE canonical spend (v_client_canonical_spend) — a size signal, not pardon dollars. For the ACLU or FWD.us it is almost entirely non-pardon work.",
        "Termination is DECLARED only (senate filing_type termination family, corpus-profile §3), never inferred from a missing quarterly. A termination filing marks the engagement closing — whether the pardon was granted is an outside-record question this data cannot answer.",
        "Client classes (seeker / vehicle / advocacy) were hand-triaged 2026-07-10 from the filings' own text; class notes quote only what the filings declare. Living persons with active clemency asks: editorial/legal review before naming anyone in a story (same flag as ledger L021/L034).",
        "LD-203 giving for this roster ships in the CSVs but is deliberately NOT charted: it is organization-level, dominated by the advocacy orgs' non-pardon activity (the largest items are one org's fundraising-gala honoree costs), and never pardon-attributable.",
        "Senate-primary; never sum the two chambers. Filings amendment-deduped on filing_period, latest by posted; registrations excluded from dollar work."
    ]
}

_exp = _read(os.path.join(REPO, "out", "packages", "pardons", "_build", "export_pardons.py"))
q_p_players = _grab(_exp, r'q_players = """(.*?)"""')
q_p_eng = _grab(_exp, r'q_engagements = """(.*?)"""')
q_p_trend = _grab(_exp, r'q_trend = """(.*?)"""')
q_p_scatter = _grab(_exp, r'q_scatter = """(.*?)"""')
q_p_kw = _grab(_exp, r'q_keywords = """(.*?)"""')
q_p_reg = _grab(_exp, r'q_registrants = """(.*?)"""')
q_p_press = _grab(_exp, r'q_press = r"""(.*?)"""')
q_p_filings = _grab(_exp, r'q_filings = """(.*?)"""')

_PDB = ("DB: db/lda_full.duckdb (read-only). Serving table: lobbying_issue_mentions tag='PARDONS' "
        "(industry_lexicon.json v1.1, 8 curated phrases). Rebuild: lda-corpus-loader/build_db.py → "
        "lda-entity-resolver/resolve_entities.py → lead-scanner/lda_industry_map.py --build-tags.")

pardons_data["queryInfo"] = {
    "kpis": _qi("Header stats — where each number comes from",
        "Market $ = sum of reported_total_tagged_quarters over data/pardons_engagements.csv "
        "(seeker + vehicle classes only). 366 filings = distinct tagged record_keys "
        "(senate+house) in lobbying_issue_mentions; the per-quarter split is the trend query. "
        "Press peak = the 2025-Q1 row of data/pardons_press_quarterly.csv. " + _PDB,
        [("engagements SQL · _build/export_pardons.py → data/pardons_engagements.csv", q_p_eng)]),
    "players": _qi("Player map — the queries behind it",
        "Bubbles = data/pardons_players.csv (SQL below; client_class/class_note added from the "
        "hand-triage dict in the export script — every class auditable there). Click-through "
        "filing lists = data/pardons_player_filings.csv (one lda.senate.gov URL per filing). " + _PDB,
        [("SQL 1 — players · _build/export_pardons.py → data/pardons_players.csv", q_p_players),
         ("SQL 2 — raw-filing index · → data/pardons_player_filings.csv", q_p_filings)]),
    "engagements": _qi("Seeker engagements — the query behind them",
        "→ data/pardons_engagements.csv. Engagement grain = (registrant, client) pair among "
        "tagged filings; a quarter counts as tagged if ANY amendment version was tagged; dollars "
        "from the deduped survivor; termination from the declared filing_type family "
        "^[1-4](T|TY|@|@Y)$ anywhere in the pair — never inferred. Seeker/vehicle classes only "
        "(advocacy orgs' quarterlies are not pardon engagements). " + _PDB,
        [("SQL · _build/export_pardons.py → data/pardons_engagements.csv", q_p_eng)]),
    "trend": _qi("Quarterly trend — the query behind it",
        "→ data/pardons_quarterly_trend.csv. Amendments deduped on (registrant_id, client_id, "
        "filing_year, filing_period) keeping latest-by-posted; registrations (R*) excluded. " + _PDB,
        [("SQL · _build/export_pardons.py → data/pardons_quarterly_trend.csv", q_p_trend)]),
    "scatter": _qi("Issue-code scatter — the query behind it",
        "→ data/pardons_issue_code_scatter.csv: tagged free-text blocks grouped by the ALI issue "
        "code the registrant filed them under. " + _PDB,
        [("SQL · _build/export_pardons.py → data/pardons_issue_code_scatter.csv", q_p_scatter)]),
    "keywords": _qi("Vocabulary — the query behind it",
        "→ data/pardons_keywords.csv: distinct filings per curated lexicon phrase (whole-word "
        "matches recorded in lobbying_issue_mentions). Discovery→curation: "
        "lda_freetext_discovery.py proposes; a human adds to industry_lexicon.json (v1.1, "
        "2026-07-10, precision checks in the facet's display_only notes). " + _PDB,
        [("SQL · _build/export_pardons.py → data/pardons_keywords.csv", q_p_kw)]),
    "registrants": _qi("Registrant firms — the query behind it",
        "→ data/pardons_registrant_firms.csv: outside firms only (registrant ≠ client), "
        "amendment-deduped, reported amounts are ranking signals. " + _PDB,
        [("SQL · _build/export_pardons.py → data/pardons_registrant_firms.csv", q_p_reg)]),
    "press": _qi("Press share — the query behind it",
        "→ data/pardons_press_quarterly.csv: whole-word regex over member press releases "
        "(title + text). The press regex adds verb forms (pardoned/pardoning) filings never "
        "use; click-through releases in data/pardons_press_releases.csv with src_file:src_line "
        "citation keys. " + _PDB,
        [("SQL · _build/export_pardons.py → data/pardons_press_quarterly.csv", q_p_press)]),
}
_PCLICK = {
    "players": "CLICK-THROUGH: click a bubble to list its tagged filings (full index: data/pardons_player_filings.csv).",
    "engagements": "CLICK-THROUGH: click a bar for the engagement's tagged filings and its declared free-text.",
    "trend": "CLICK-THROUGH: click a quarter to list exactly the deduped filings it counts (data/pardons_trend_filings.csv).",
    "press": "CLICK-THROUGH: click a quarter to list the matching releases (data/pardons_press_releases.csv).",
}
for _k, _s in _PCLICK.items():
    pardons_data["queryInfo"][_k]["note"] = _s + " " + pardons_data["queryInfo"][_k]["note"]

build("crypto", "Crypto Lobbying — State of the Industry",
      "Who lobbies Washington on crypto, how fast it grew, where it hides in the disclosure forms, and who the industry gives money to.",
      " and openFEC (cached raw responses)", crypto_data, "crypto_page.js")
build("aipac", "AIPAC Lobbying Review",
      "AIPAC's federal lobbying 2022–2026Q1: budget, targets, bills, the wider Israel-policy lobbying field, disclosed political giving, and how its spending relates to the congressional news cycle.",
      "", aipac_data, "aipac_page.js")
build("healthcare", "Healthcare Lobbying — State of the Industry",
      "The largest standing lobbying operation in Washington: who the players are, what kind of health issues they file on, which bills they crowd onto, and who the industry gives money to.",
      "", hc_data, "hc_page.js")
build("pardons", "Presidential Pardons — the Lobbying Around Executive Clemency",
      "Two markets share one vocabulary: individuals paying lobbying firms to seek presidential pardons ('Executive relief'), and policy organizations lobbying on clemency itself — mapped from the filings' own free-text 2022–2026Q1.",
      "", pardons_data, "pardons_page.js", gendate="2026-07-13")

# ============================ TURNOVER (P3 beat report) ============================
# Guarded: only prepped/built when its data exists and it's requested (or no ONLY).
# Multi-quarter: every turnover_<QTAG>_summary.csv in data/ becomes a switchable
# report quarter in the one dashboard (export_turnover.py writes one set per run).
_tdir = os.path.join(REPO, "out", "packages", "turnover", "data")
if os.path.isdir(_tdir) and ((not ONLY) or ("turnover" in ONLY)):
    import glob as _glob
    _qtags = sorted(os.path.basename(f).split("_")[1] for f in
                    _glob.glob(os.path.join(_tdir, "turnover_*_summary.csv")))
    ttr = rd("turnover", "turnover_quarterly_trend.csv")
    ttop = rd("turnover", "turnover_trend_top.csv")
    _latest_lbl = ttr[-1]["quarter"]
    ttop_map = {}
    for r in ttop:
        e = ttop_map.setdefault(r["quarter"], {"term": [], "hire": []})
        e[r["kind"]].append([r["filing_uuid"], tcase(r["client"]), tcase(r["registrant"]),
                             num(r["income_trail4_or_firstq"])])
    _tq_lbls = [r["quarter"] for r in ttr]
    _new_vals = [int(r["new_engagements"]) for r in ttr]
    if _tq_lbls and _tq_lbls[0] == "2022-Q1":
        _new_vals[0] = None   # corpus edge: every pair is "new" in the first quarter

    _M = lambda v: "$" + (f"{v/1e6:.2f}M" if v >= 1e6 else f"{v/1e3:.0f}K")
    N_T = 16

    def _prep_quarter(QT):
        tsum = rd("turnover", f"turnover_{QT}_summary.csv")[0]
        TQL = tsum["quarter"]                     # e.g. "2025-Q4"
        tterm = rd("turnover", f"turnover_{QT}_terminations.csv")
        tnew = rd("turnover", f"turnover_{QT}_new_engagements.csv")
        tswap = rd("turnover", f"turnover_{QT}_swaps.csv")
        tchurn = rd("turnover", f"turnover_{QT}_firm_churn.csv")
        thist = rd("turnover", f"turnover_{QT}_term_history.csv")
        tcc = rd("turnover", f"turnover_{QT}_churn_clients.csv")
        thf = rd("turnover", f"turnover_{QT}_new_engagement_filings.csv")
        tqi = json.load(open(os.path.join(_tdir, f"turnover_{QT}_queryinfo_sql.json"),
                             encoding="utf-8"))
        _key = lambda r: r["client"] + " — " + r["registrant"]
        terms16 = [{"key": _key(r), "client": tcase(r["client"]), "registrant": tcase(r["registrant"]),
                    "regShort": tcase(r["registrant"]), "trail4": num(r["trail4_income"]),
                    "nq": int(r["n_quarters"]), "first": r["first_seen"],
                    "reeng": int(r["re_engaged"]) > 0, "newq": r["new_this_q"] == "True",
                    "uuid": r["term_uuid"]} for r in tterm[:N_T]]
        hist_map = {}
        for r in thist:
            hist_map.setdefault(r["client"] + " — " + r["registrant"], []).append(
                [r["quarter"], num(r["income"]), r["filing_uuid"], r["filing_type"],
                 r["in_trail4_window"] == "True"])
        hires16 = [{"key": _key(r), "client": tcase(r["client"]), "registrant": tcase(r["registrant"]),
                    "regShort": tcase(r["registrant"]), "income": num(r["q_income"]),
                    "uuid": r["cite_uuid"], "regOnly": r["registration_only"] == "True",
                    "termSameQ": r["terminated_same_q"] == "True"} for r in tnew[:N_T]]
        h16 = {h["key"] for h in hires16}
        hf_map = {}
        for r in thf:
            k = r["client"] + " — " + r["registrant"]
            if k in h16:
                hf_map.setdefault(k, []).append(
                    [r["filing_uuid"], r["filing_type"], num(r["reported_income"])])
        swap_rows_t = [{"client": tcase(r["client"]), "old_firm": tcase(r["old_firm"]),
                        "new_firm": tcase(r["new_firm"]), "dq": int(r["hire_dq"]), "move": r["move"],
                        "spend": num(r["client_q_canonical_spend"]),
                        "term_uuid": r["term_uuid"], "hire_uuid": r["hire_uuid"]} for r in tswap]
        inhouse = [r for r in swap_rows_t if r["move"]]
        firm_swaps = [r for r in swap_rows_t if not r["move"]]
        def group_moves(rows):   # one display bar per client; every move in the click panel
            g = {}
            for r in rows:
                e = g.setdefault(r["client"], {"client": r["client"], "spend": 0, "moves": []})
                e["spend"] = max(e["spend"], r["spend"] or 0)
                e["moves"].append({k: r[k] for k in ("old_firm", "new_firm", "dq", "move",
                                                     "term_uuid", "hire_uuid")})
            return sorted(g.values(), key=lambda e: (-e["spend"], e["client"]))
        inhouse_g = group_moves(inhouse)
        swaps_g = group_moves(firm_swaps)
        churn14 = [{"name": tcase(r["registrant"]), "lost": int(r["n_lost"]),
                    "lost4": num(r["lost_trail4_income"]) or 0, "signed": int(r["n_new"]),
                    "net": int(r["net"])} for r in tchurn[:14]]
        cc_map = {}
        for r in tcc:
            e = cc_map.setdefault(tcase(r["registrant"]), {"lost": [], "signed": []})
            e[r["kind"]].append([r["filing_uuid"], tcase(r["client"]), num(r["amount"])])

        is_latest = TQL == _latest_lbl
        _top_t = tterm[0]
        _yq = int(tsum["yoy_q_terminations"])
        q_blob = {
            "label": TQL, "isLatest": is_latest,
            "nTerm": int(tsum["terminations"]), "nNew": int(tsum["new_engagements"]),
            "nSwaps": int(tsum["swap_rows"]), "nFirmSwaps": len(firm_swaps),
            "nSwapClients": len(swaps_g), "nFirms": len(tchurn),
            "kpis": [
                {"label": f"Engagements terminated, {TQL}", "value": f"{int(tsum['terminations']):,}",
                 "note": (f"vs {_yq:,} a year earlier"
                          + (" — Q4 is seasonally the churn quarter; compare Q4s to Q4s"
                             if TQL.endswith("Q4") else
                             " (same quarter — Q4s run seasonally high, so compare like quarters)")
                          + ("; a floor — terminations post with a lag" if is_latest else ""))},
                {"label": f"New engagements, {TQL}", "value": f"{int(tsum['new_engagements']):,}",
                 "note": f"first-ever filings, client-entity-grouped; vs {int(tsum['yoy_q_new']):,} a year earlier"},
                {"label": "Clients that changed representation", "value": f"{int(tsum['swap_clients']):,}",
                 "note": f"{int(tsum['swap_rows']):,} term→hire pairs within ±1 quarter · {int(tsum['inhouse_moves'])} moved in-house"},
                {"label": "Biggest book that ended", "value": _M(num(_top_t["trail4_income"])),
                 "note": f"{tcase(_top_t['client'])} ended {_top_t['n_quarters']} quarters with {tcase(_top_t['registrant'])}"},
            ],
            "terms": terms16, "termHistory": hist_map,
            "hires": hires16, "hireFilings": hf_map,
            "inhouse": inhouse_g, "swapsTop": swaps_g[:14],
            "swapsTable": (inhouse + firm_swaps)[:40],
            "churn": churn14, "churnClients": cc_map,
            "caveats": [
                "Terminations are DECLARED: the registrant's own termination filing (senate filing types 1T–4T, TY/@ variants). A client going quiet between quarters is NOT counted — late posting and partial House dumps would fabricate exits.",
                "Senate-only lens: the House mirror of an LD-2 carries no termination signal, so House data adds nothing here and is never summed on top.",
                "A termination is not always an exit: RE-ENGAGED rows file again later (a pause), and one-quarter engagements are hired-and-terminated inside the quarter. Both are flagged, not hidden.",
                "'New' is grouped by resolved client entity, never by client_id — a re-registration re-issues client_id and would otherwise fabricate a hire (the Gunvor case is the worked example).",
                "Engagement dollars are the pair's own deduped quarterly income (amendments collapse on filing_period, latest by posted). Client-size dollars come from v_client_canonical_spend and are never a direct sum of filings.",
                (f"{TQL} is the NEWEST quarter in the DB — terminations post with a lag, so every count here is a floor until the next corpus refresh; the ±1-quarter swap window can only reach backward (no later quarter exists yet)."
                 if is_latest else
                 f"The newest quarter in the DB is a floor — terminations post with a lag. {TQL} is a complete quarter; its ±1-quarter swap window reaches one quarter past it."),
                "Turnover is evidence of movement, not motive. The disclosure says who ended, hired, or swapped — the why (fee disputes, mergers, a completed ask, a lost policy fight) needs reporting beyond these records.",
            ],
        }
        _TDB = ("DB: db/lda_full.duckdb (read-only). Rebuild: lda-corpus-loader/build_db.py → "
                "lda-entity-resolver/resolve_entities.py. Tool: skills/lead-scanner/scripts/lda_turnover.py "
                f"{QT} (this dashboard calls the tool's own query functions — the SQL below is captured "
                "from the actual execution, not copied by hand). Citeable blocks: queries/p3_turnover.sql P3a–P3e.")
        _tsql = tqi["sql"]
        def _tqi_entry(title, note, blocks):
            return {"title": title, "note": note, "dict": "DATA_DICTIONARY.md",
                    "blocks": [{"label": l, "text": _tsql[k].strip()} for l, k in blocks]}
        q_blob["queryInfo"] = {
            "kpis": _tqi_entry(f"Header stats ({TQL}) — where each number comes from",
                "Counts come from the tool's counts_for() run at the target, previous, and prior-year "
                f"quarters (→ data/turnover_{QT}_summary.csv); the 'biggest book' tile is row 1 of the "
                f"terminations query (→ data/turnover_{QT}_terminations.csv). " + _TDB,
                [("SQL — counts_for(target quarter) · lda_turnover.py → data/turnover_" + QT + "_summary.csv", "kpis")]),
            "trend": _tqi_entry("Quarterly trend — the query behind it",
                "CLICK-THROUGH: click a quarter for its top terminations and hires (data/turnover_trend_top.csv "
                "— the target quarter's list reconciles with the terminations query at export). "
                "→ data/turnover_quarterly_trend.csv. 2022-Q1 'new engagements' is suppressed (corpus edge). " + _TDB,
                [("SQL 1 — per-quarter counts (P3a) → data/turnover_quarterly_trend.csv", "trend"),
                 ("SQL 2 — per-quarter top terminations + hires → data/turnover_trend_top.csv", "trend_top")]),
            "terms": _tqi_entry(f"Terminations ({TQL}) — the query behind it",
                "CLICK-THROUGH: click a bar for the quarterly income rows that sum to it "
                f"(data/turnover_{QT}_term_history.csv — reconciled at export) plus the termination filing. "
                f"→ data/turnover_{QT}_terminations.csv (all {int(tsum['terminations']):,} rows, each with "
                "its lda.senate.gov URL). " + _TDB,
                [("SQL 1 — terminations with history (P3b) · lda_turnover.terminations()", "terms"),
                 ("SQL 2 — per-bar quarterly audit rows → data/turnover_" + QT + "_term_history.csv", "hist")]),
            "hires": _tqi_entry(f"New engagements ({TQL}) — the query behind it",
                "CLICK-THROUGH: click a bar for every target-quarter filing of that pair "
                f"(data/turnover_{QT}_new_engagement_filings.csv). → data/turnover_{QT}_new_engagements.csv. "
                "Grouped by resolved client entity (re-registrations are not 'new'). " + _TDB,
                [("SQL 1 — first-ever engagements (P3c) · lda_turnover.new_engagements()", "hires"),
                 ("SQL 2 — the pairs' target-quarter filings → data/turnover_" + QT + "_new_engagement_filings.csv", "hire_filings")]),
            "swaps": _tqi_entry(f"Swaps & in-house moves ({TQL}) — the query behind it",
                "CLICK-THROUGH: click a bar for both filings of each move (termination + first filing). "
                f"→ data/turnover_{QT}_swaps.csv. move='to-inhouse'/'from-inhouse' when a registrant "
                "norm-key equals the client's (the P1 bridge); client size joins v_client_canonical_spend. " + _TDB,
                [("SQL — swaps within ±1 quarter (P3d) · lda_turnover.swaps()", "swaps")]),
            "churn": _tqi_entry(f"Firm scoreboard ({TQL}) — the query behind it",
                "CLICK-THROUGH: click a firm for its lost and signed client lists "
                f"(data/turnover_{QT}_churn_clients.csv — list lengths reconcile with the scoreboard at export). "
                f"→ data/turnover_{QT}_firm_churn.csv. " + _TDB,
                [("SQL 1 — per-firm lost/signed counts (P3e) · lda_turnover.firm_churn()", "churn"),
                 ("SQL 2 — displayed firms' client lists → data/turnover_" + QT + "_churn_clients.csv", "churn_clients")]),
        }
        return q_blob

    _blobs = [_prep_quarter(QT) for QT in _qtags]
    turnover_data = {
        "order": [b["label"] for b in _blobs],
        "default": _blobs[-1]["label"],          # newest exported quarter opens first
        "quarters": {b["label"]: b for b in _blobs},
        "trend": {"q": _tq_lbls, "term": [int(r["terminations"]) for r in ttr], "nw": _new_vals},
        "trendTop": ttop_map,
        "pardon": [
            {"uuid": "5b3aebcf-ed3d-4298-8d87-35775c78853d", "text": "Roger Ver — Drake Ventures, 2025-Q1, $600,000",
             "tail": "activity text: \u201cUS government prosecution of Roger Ver. Tax policy regarding cryptocurrency\u2026\u201d"},
            {"uuid": "5b852e1d-1a1f-405a-9ed4-2cb646756a0a", "text": "Roger Ver — Drake Ventures termination, 2025-Q4",
             "tail": "the engagement closes (4TY, no activity)"},
            {"uuid": "cebc74a7-42e0-4ca4-953f-3485a924046e", "text": "Roger Ver — Sterling Green termination, 2025-Q3",
             "tail": "second firm on the same ask (\u201ccriminal justice reform\u2026 ending the exit tax\u201d), $70K total"},
            {"uuid": "1f0b6bd9-acc4-4aa0-9ec6-44646d9b4445", "text": "Torence Hatch (Boosie Badazz) — J M Burkman & Associates, 2025-Q4, $600,000",
             "tail": "activity text: \u201cSeeking a presidential pardon. White House issues\u201d — one quarter"},
            {"uuid": "f9c3a194-3f90-4802-934b-f4c4753d39f0", "text": "Torence Hatch — Burkman termination, 2026-Q1",
             "tail": "terminated the quarter after it began"},
            {"uuid": "e741a1c5-7644-4f1e-8590-db11669460c9", "text": "Joseph Schwartz — J M Burkman & Associates, 2025-Q2, $960,000",
             "tail": "activity text: \u201cSeeking a federal pardon.\u201d — 2026-Q1's biggest terminated book"},
            {"uuid": "b6e2b16d-d90e-4716-b127-f4ea262ae00f", "text": "Joseph Schwartz — Burkman termination, 2026-Q1",
             "tail": "Burkman's two pardon-seekers total ~$1.56M"},
            {"uuid": "63371c13-f31b-472b-a63d-319dbc4a8bee", "text": "Joseph Schwartz — Merkava Strategies registration, 2025-Q4",
             "tail": "a second firm on the same ask: \u201cPetitioning for a pardon/clemency\u201d (+$100K)"},
        ],
    }

    build("turnover", "Lobbying Turnover — Quarterly Beat Report",
          "Who ended representation, who hired, which clients swapped firms or took the work in-house, "
          "and which firms churned the most — a quarter-diff of the Senate LDA corpus by the quarterly "
          "turnover tracker. Terminations are the registrants' own termination filings, never inferred "
          "from silence. Pick the report quarter below; the newest quarter opens by default.",
          "", turnover_data, "turnover_page.js", gendate="2026-07-11")

# ============================ OTHER FINDINGS (not in a package) ============================
# 2026-07-13: leads from LEDGER.md that never became one of the five industry
# packages above (crypto/aipac/healthcare/pardons/critical-minerals) — either a
# one-off thread in a field with no package, or something the team parked/closed.
other_findings_data = {
    "kpis": [
        {"label": "Leads outside any package", "value": "6", "note": "L020, L022, L023, L025, L027, L028"},
        {"label": "Still open/triaged", "value": "3", "note": "L020 TP-Link · L022 Sheffield · L023 Vantive"},
        {"label": "Parked (cold, not dead)", "value": "2", "note": "L025 data-quality spike · L027 tariffs coupling"},
        {"label": "Closed as a known story", "value": "1", "note": "L028 SECURE 2.0 — scooped by trade/news coverage"},
    ],
    "findings": [
        {"id": "L020", "status": "triaged", "title": "TP-Link — a China-founded router maker facing a proposed US ban",
         "hypothesis": "TP-Link Systems Inc. ramps lobbying ~5x and fans out from one firm to three across 2024-2026 (Akin Gump → + Mercury Public Affairs → + Vernonburg Group), coinciding with the proposed router-ban legislative push.",
         "actors": "TP-Link Systems Inc.; Akin Gump; Mercury Public Affairs; Vernonburg Group",
         "next": "Confirm the router-ban legislative timeline; scan the press corpus for member statements on TP-Link/router security (say-vs-pay)."},
        {"id": "L022", "status": "triaged", "title": "Scott Sheffield — a personal FTC-consent-order lobbying retainer",
         "hypothesis": "Scott Sheffield (Pioneer founder, named in the FTC/Exxon consent order) personally retains Brownstein Hyatt Farber Schreck to lobby 'Issues related to the FTC', starting exactly the quarter the FTC acted.",
         "actors": "Scott Sheffield (individual); Brownstein Hyatt Farber Schreck; Norman Brownstein; William Moschella",
         "next": "Confirm the FTC action date (May 2024) against the Q2-2024 filing start; editorial-sensitivity review (named individual)."},
        {"id": "L023", "status": "triaged", "title": "Vantive — a Baxter spinoff's $2.5M White House Ballroom gift",
         "hypothesis": "Vantive (spun off from Baxter in 2025) writes $2.5M to the White House Ballroom Project while standing up a six-firm federal lobbying operation in its first independent year.",
         "actors": "Vantive US Healthcare LLC; Trust for the National Mall; Ballard; Checkmate; Akin Gump; Todd Strategy; Nickles Group; Porterfield Fettig & Sears",
         "next": "Editorial-sensitivity review (a sitting President's project); confirm the Baxter spin-off date; map what Vantive actually lobbied on (dialysis/ESRD payment policy?). Healthcare-ADJACENT (a dialysis spinoff) but found via a different lens (contribution fan-out, not the ALI issue-code lens) and never folded into the shipped healthcare package's roster or story."},
        {"id": "L025", "status": "parked", "title": "MedSecurean / Indian Pharmaceutical Alliance — a 60x single-quarter income spike",
         "hypothesis": "A class of LD-2 single-quarter income overstatements the gap-lens misses: MedSecurean.com / Indian Pharmaceutical Alliance reports $900K in 2025-Q4 vs. a $15K baseline (60x) — looks like a data-quality artifact (misreport), not a confirmed real surge.",
         "actors": "MedSecurean.com; Indian Pharmaceutical Alliance; Robert K Weidner / RPLCC",
         "next": "Parked: needs per-record confirmation to separate a real surge from a misreport; low priority. Revisit if a say-vs-pay lead lands on one of these engagements, or if pursuing a standalone data-quality finding."},
        {"id": "L027", "status": "parked", "title": "Trade/tariffs press-vs-money coupling",
         "hypothesis": "Press attention-share and lobbying-money share on TRD are both flat 2022-2024 then jump together in 2025 (the tightest positive coupling measured, r +0.88) — but this is the mechanically-obvious 2025 Trump-tariff story, not a novel angle.",
         "actors": "Cleo Fields; Richard J. Durbin; Jeanne Shaheen; Nippon Steel Corp.; Brown-Forman Corp.; Qualcomm Inc.",
         "next": "Parked: logged only to evidence the press/spend coupling deliverable, not pursued as novel. Revisit if a specific member loud on tariffs turns out to be paid-side coupled (donors/registrants), or a non-2025 trade coupling appears."},
        {"id": "L028", "status": "parked", "title": "SECURE 2.0 say-vs-pay — closed as a known story",
         "hypothesis": "Heavy, specific retirement/annuity-industry lobbying (1,436 senate filings name it) vs. thin coverage in members' OWN press releases looked like a say-vs-pay gap — but an outside-context-scan (live web + date-gated GDELT) shows SECURE 2.0 was high news-salience and the industry-lobbying angle (annuities topping IRI's agenda) was contemporaneously reported. 'Near-silent' holds only for congressional member press releases, which is not itself news.",
         "actors": "Athene Holding (Brownstein Hyatt); HR Policy Association (Tributary LLP); American Benefits Council; FMR LLC/Fidelity; Chris Van Hollen",
         "next": "Closed as a known story unless a specific, unreported company-level ask surfaces. Adjacent but UNRELATED beat if picked up separately: Athene's 2024-25 pension-risk-transfer ERISA class actions (AT&T/Lockheed/Bristol Myers)."},
    ],
    "entitiesChecked": [
        {"entity": "Korea Zinc Company, Ltd. (client, via Mercury/Ballard)",
         "verdict": "Set aside — largest emergent (E1) engagement in the 2026-07-06 sweep, but a well-publicised MBK/Young Poong takeover fight; mechanically top, not novel.",
         "records": "E1 top row; 12 filings 2024-2026", "date": "2026-07-06"},
        {"entity": "Trump-Vance Inaugural Committee corporate donors (JBS, Robinhood, Occidental, NVIDIA, Uber, X, et al.)",
         "verdict": "Set aside — top LD-203 honoree-concentration (F1) cluster is widely-reported corporate inaugural giving; a known category, not a novel angle (crypto's slice of it is still cited inside the crypto package as context).",
         "records": "F1 rows ($1-5M each)", "date": "2026-07-06"},
        {"entity": "IBEW / union LD-203 'N/A' honoree placeholders",
         "verdict": "Set aside — mechanical top of honoree concentration (a placeholder honoree field, not a real recipient).",
         "records": "F1 top row ($8M/N-A)", "date": "2026-07-06"},
    ],
    "caveats": [
        "This page exists so a lead doesn't get lost just because it never grew into a full industry package — it is a worklist, not a finding.",
        "Named-actor rule applies here too: every row has a specific actor, date, and record ID, resolvable via show_record.py.",
        "'Parked' ≠ dead: a parked lead is promising but blocked or deprioritized, reconsidered at every triage checkpoint; only a revisit trigger firing (or a human call) moves it off this page.",
        "L023 (Vantive) is healthcare-adjacent and L025 (MedSecurean/Indian Pharmaceutical Alliance) is pharma-adjacent, but neither was folded into the shipped healthcare package — they were found by a different lens (contribution fan-out / single-quarter spike) than that package's ALI issue-code scope, and remain unverified standalone threads.",
        "Full detail, evidence record IDs, and status history for every row: LEDGER.md in the repo root.",
    ],
}
build("other-findings", "Leads Not Yet in a Package",
      "Investigation-ledger leads that were triaged far enough to name an actor, a date, and a record ID, "
      "but sit outside the five shipped industry packages (crypto, AIPAC, healthcare, pardons, critical "
      "minerals) — a worklist, not a finding.",
      "", other_findings_data, "other_findings_page.js", gendate="2026-07-13")

print("done")
