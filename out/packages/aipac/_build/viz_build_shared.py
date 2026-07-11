"""Assemble the three package dashboards from CSVs + viz templates."""
import csv, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
S = r"C:\Users\rcalv\AppData\Local\Temp\claude\c--Users-rcalv-Projects\b38d9a1a-832d-4f28-a603-34febc77b3e7\scratchpad"
VIZ = os.path.join(S, "viz")
GENDATE = "2026-07-08"

def rd(pkg, name):
    p = os.path.join(REPO, "out", "packages", pkg, "data", name)
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
       "Ajc":"AJC","Aclu":"ACLU","Fdd":"FDD","Aha":"AHA","Ama":"AMA","Ahip":"AHIP","Aarp":"AARP","Phrma":"PhRMA"}
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

def build(pkg, title, subtitle, extra_sources, data, page_js):
    tpl = open(os.path.join(VIZ, "template.html"), encoding="utf-8").read()
    css = open(os.path.join(VIZ, "shared.css"), encoding="utf-8").read()
    lib = open(os.path.join(VIZ, "lib.js"), encoding="utf-8").read()
    page = open(os.path.join(VIZ, page_js), encoding="utf-8").read()
    html = (tpl.replace("__TITLE__", title).replace("__SUBTITLE__", subtitle)
            .replace("__GENDATE__", GENDATE).replace("__EXTRA_SOURCES__", extra_sources)
            .replace("__CSS__", css).replace("__LIB__", lib)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__PAGE__", page))
    out = os.path.join(REPO, "out", "packages", pkg, f"{pkg}_dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[html] {out}  ({len(html)//1024} KB)")

CODE_NAMES = {"FIN":"Financial institutions & securities","BAN":"Banking","TAX":"Taxation","SCI":"Science & technology",
    "CPI":"Computer industry","CDT":"Commodities trading","AGR":"Agriculture","ACC":"Accounting","GOV":"Government issues",
    "TRD":"Trade","LAW":"Law enforcement & crime","SMB":"Small business","TEC":"Telecommunications","CSP":"Consumer safety",
    "HOM":"Homeland security","ENG":"Energy & nuclear","RET":"Retirement","URB":"Urban development","MON":"Money & gold standard",
    "BUD":"Budget & appropriations","FOR":"Foreign relations","DEF":"Defense","(none)":"(no code recorded)"}

# ============================ CRYPTO ============================
players_csv = rd("crypto", "crypto_players.csv")
pure = set(x.strip().upper() for x in open(os.path.join(REPO, "out", "crypto_roster_pureplay.txt"), encoding="utf-8"))
players = []
for r in players_csv:
    sp = num(r["total_all_issue_spend"])
    players.append({"name": r["player"], "filings": int(r["crypto_filings_senate"]),
                    "tier": r["tier"], "spend": sp, "vis": r["player"].upper().strip() in pure})
top_players = sorted(players, key=lambda p: -p["filings"])[:60]
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
divers_spend = sorted([p for p in players if not p["vis"] and p["spend"] and p["tier"] == "core"],
                      key=lambda p: -p["spend"])[:12]
trend = rd("crypto", "crypto_quarterly_trend.csv")
tq = [q_label(r["filing_year"], r["filing_period"]) for r in trend]
scatter = rd("crypto", "crypto_issue_code_scatter.csv")[:12]
press = rd("crypto", "crypto_press_quarterly.csv")
recip = rd("crypto", "crypto_ld203_pureplay_recipients.csv")
split = rd("crypto", "crypto_ld203_recipients_split.csv")
split_rows = [{"name": r["recipient"], "a": num(r["from_crypto_native"]) or 0,
               "b": num(r["from_diversified_core"]) or 0, "party": r["party"]} for r in split]
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
crypto_data = {
    "kpis": [
        {"label": "Client orgs lobbying on crypto, 2025-Q4", "value": "287", "note": "vs 177 in 2024-Q4 (+62%)"},
        {"label": "Crypto-tagged filings, 2025-Q4", "value": "391", "note": "flat ~240/qtr through 2022–2024"},
        {"label": "Players with no crypto term in their name", "value": "466 of 508", "note": "found only via what filings SAY (free-text map)"},
        {"label": "Top-4 players' Super-PAC money (FEC)", "value": "$322.6M", "note": "vs $1.7M in disclosed LD-203 — different regimes"},
    ],
    "players": top_players,
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
                             "b": num(r["from_diversified_core"]) or 0} for r in split[:40]],
    "fec": fec,
    "press": {"q": [r["quarter"] for r in press], "share": [num(r["crypto_share_pct"]) for r in press],
              "n": [int(r["crypto_releases"]) for r in press], "all": [int(r["all_releases"]) for r in press]},
    "caveats": [
        "Recall-first map: any client whose filing free-text names one of 43 curated crypto phrases is included; incidental one-off mentions sit in the peripheral tier by design. A story names specific players from the CSVs, never 'the whole list.'",
        "Spend figures are each player's TOTAL federal lobbying spend across all issues (canonical, double-count-corrected) — a size signal. Filing-level disclosure cannot split dollars by issue.",
        "Senate filings are primary; House versions of the same filings are never added on top (they are copies). Filings are amendment-deduplicated.",
        "LD-203 'disclosed giving' is the lobbyist-side regime only. Super-PAC money (Fairshake network) legally lives in FEC data — the two never sum.",
        "FEC↔lobbying name matches are candidates for human confirmation (shown with confidence labels). Entity resolution is the ceiling: a few companies (Kraken/Payward, a16z) file under multiple names and are recovered manually.",
        "Everything is self-reported disclosure data. 'Disclosed' never means 'total': 501(c)(4) dark money and state lobbying are outside every number here."
    ]
}

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
    "govEntities": [{"name": r["entity_name"], "n": int(r["mentions"])} for r in gov],
    "nBills": len(bills),
    "topBills": top_bills,
    "billsTable": [{"bill": r["bill"], "n": int(r["aipac_filings"]), "y0": r["first_year"], "y1": r["last_year"]} for r in bills[:60]],
    "coLobby": [{"name": tcase(r["client"]), "bills": int(r["shared_distinctive_bills"]), "filings": int(float(r["filings_on_those_bills"]))} for r in colob[:15]],
    "israelPlayers": [{"name": tcase(r["player"]), "n": int(r["israel_filings"]), "spend": num(r["total_all_issue_spend"])}
                      for r in ispl if "AMERICAN ISRAEL PUBLIC AFFAIRS" not in r["player"].upper()][:18],
    "givingRecipients": [{"name": r["recipient"], "total": num(r["total"]), "items": int(r["items"])} for r in agrec[:15]],
    "givingByYear": [{"y": r["filing_year"], "total": num(r["total"])} for r in agy],
    "givingTotal": 7652150,
    "partySplit": json.load(open(os.path.join(S, "aipac_party_split.json")))["psum"],
    "lobbyists": [{"name": tcase(r["first_name"] + " " + r["last_name"]), "filings": int(r["filings"]),
                   "years": f"{r['first_year']}–{r['last_year']}"} for r in lob],
    "caveats": [
        "AIPAC self-files (in-house registrant): quarterly amounts are its own reported lobbying spend, not payments to outside firms. No outside-firm engagements appear for AIPAC in this window.",
        "'Co-lobbying a bill' means filing on the same bill — allies and opponents both appear; direction of advocacy is not in the disclosure data.",
        "The Israel-policy field scan is an exploratory whole-word text search (israel/gaza/antisemitism/etc.), not the curated lexicon pipeline; treat the list as a triage candidate set.",
        "Press releases are congressional members' releases — the 'say' side of Congress, not AIPAC's own communications.",
        "LD-203 disclosed giving is the lobbyist-side regime; AIPAC-affiliated Super-PAC spending (e.g. United Democracy Project) lives in FEC data and is not included here.",
        "Senate-primary, amendment-deduplicated; every table row traces to a filing UUID in the CSVs."
    ]
}

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
hc_data = {
    "kpis": [
        {"label": "Health-coded filings per quarter", "value": "~4,000", "note": "stable 2022–24; 2025 peak 4,384 (+9%)"},
        {"label": "Canonical spend of health-active clients, 2025", "value": "$1.69B", "note": "all-issue spend of clients filing on health that quarter"},
        {"label": "Peak press share, 2025-Q4", "value": "28.8%", "note": "of ALL member releases — Medicaid + ACA-subsidy fight"},
        {"label": "Disclosed LD-203 giving (top-150 orgs)", "value": "$107.8M", "note": "2022–25; AHA is the top giver at $9.7M"},
    ],
    "players": hplayers,
    "trend": {"q": hq, "filings": [int(r["health_filings"]) for r in htr],
              "clients": [int(r["health_clients"]) for r in htr],
              "spend": [num(r["canonical_spend_hc_clients"]) for r in htr]},
    "codeTrend": {"q": hq, "HCR": [hcodes["HCR"].get(q) for q in hq], "MMM": [hcodes["MMM"].get(q) for q in hq],
                  "PHA": [hcodes["PHA"].get(q) for q in hq], "MED": [hcodes["MED"].get(q) for q in hq]},
    "press": {"q": [r["quarter"] for r in hpr], "share": [num(r["health_press_share_pct"]) for r in hpr],
              "n": [int(r["health_releases"]) for r in hpr], "all": [int(r["all_releases"]) for r in hpr]},
    "topBills": [{"bill": r["bill"], "clients": int(r["clients"]), "filings": int(r["filings"]),
                  "hint": HINTS.get(r["bill"], "")} for r in hbl[:12]],
    "givingOrgs": [{"name": tcase(r["ld203_filer_org"]), "total": num(r["disclosed_giving_total"]),
                    "focused": r["ld203_filer_org"].strip().upper() in hc_focused_set} for r in hgo[:10]],
    "givingTop": hgiv_top,
    "givingMembers": hgiv_members,
    "givingTotal": 107769783,
    "caveats": [
        "Scope = filings whose activities carry ALI issue codes HCR (health), MMM (Medicare/Medicaid), PHA (pharmacy) or MED (medical research). Unlike crypto, healthcare is code-visible, so the issue-code lens is primary.",
        "Spend is each client's TOTAL canonical lobbying spend (all issues) in quarters where it filed on health — an upper-bound size signal, since filing-level disclosure cannot split dollars by issue.",
        "Health-activity share separates pure-plays from diversified giants: a self-filer's single quarterly filing lists dozens of issues, so shares are computed on activity rows, not filings.",
        "LD-203 giving is organization-level: solid for pure-play trade groups (AHA, AMA, ADA), inflated for diversified filers (AARP, Altria) whose giving is not health-specific.",
        "Senate-primary, amendment-deduplicated; registrations excluded from dollar work.",
        "Recipient names are lightly-normalized filing strings, not entity-resolved."
    ]
}

build("crypto", "Crypto Lobbying — State of the Industry",
      "Who lobbies Washington on crypto, how fast it grew, where it hides in the disclosure forms, and who the industry gives money to — mapped from what 500+ organizations SAY they lobby on, not what they're named.",
      " and openFEC (cached raw responses)", crypto_data, "crypto_page.js")
build("aipac", "AIPAC Lobbying Review",
      "AIPAC's federal lobbying 2022–2026Q1: budget, targets, bills, the wider Israel-policy lobbying field, disclosed political giving, and how its spending relates to the congressional news cycle.",
      "", aipac_data, "aipac_page.js")
build("healthcare", "Healthcare Lobbying — State of the Industry",
      "The largest standing lobbying operation in Washington: who the players are, what kind of health issues they file on, which bills they crowd onto, and who the industry gives money to.",
      "", hc_data, "hc_page.js")
print("done")
