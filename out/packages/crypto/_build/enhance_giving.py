"""Giving-split + party-annotation enhancement (2026-07-08; crypto re-cut 2026-07-11).
- Crypto (2026-07-11, Rob-approved >=5% intensity gate): recipients split THREE ways —
  crypto-NATIVE (105 pure-play) vs DIVERSIFIED-FORWARD (147 core players with >=5% crypto
  activity share) vs AMBIENT (15 core players below the gate: AARP, U.S. Chamber, Amazon…).
  Slice inputs are EXHAUSTIVE runs (--top 999999): the 2026-07-08 build consumed only each
  run's top-400 recipient rows, silently dropping sub-cutoff name variants from the member
  merge (the diversified pool's top-400 carried $61.9M of $110.7M); per-member diversified
  numbers therefore RECOVER variants vs the archived CSV — corrections, printed below.
- Healthcare: recipients split into HEALTH-FOCUSED (>=50% health activities, 113) vs MIXED (<50%, 37) slices.
- AIPAC: party brackets + D/R member split from the deep (top-400) run.
Party source: `members` table in the DB (press-corpus, current members) + one manual entry
(Pat Toomey, R-PA, retired Jan 2023 — not in the table). Source recorded per row.

Usage: python enhance_giving.py [crypto] [healthcare] [aipac]   (no args = all)
"""
import duckdb, json, csv, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"c:\Users\rcalv\Projects\Northwestern Project\gain-investigation"
S = os.path.join(REPO, "out", "packages", "_build", "inputs")  # durable tool-JSON copies
ONLY = set(a.lower() for a in sys.argv[1:])

def want(pkg):
    return not ONLY or pkg in ONLY

def loadj(name):
    txt = open(os.path.join(S, name), encoding="utf-8").read()
    return json.loads(txt[txt.find("{"):])

# ---------- party lookup ----------
con = duckdb.connect(os.path.join(REPO, "db", "lda_full.duckdb"), read_only=True)
members = con.execute("SELECT name, party, state, chamber FROM members").fetchall()
SUFFIXES = {"JR", "SR", "II", "III", "IV", "JR.", "SR."}
PLETTER = {"Democrat": "D", "Republican": "R", "Independent": "I"}

def name_tokens(n):
    toks = [t.strip(' ."(),') for t in n.upper().replace(",", " ").split()]
    return [t for t in toks if t and t not in SUFFIXES]

mem_by_last = {}
for name, party, state, chamber in members:
    toks = name_tokens(name)
    if not toks: continue
    last = toks[-1]
    mem_by_last.setdefault(last, []).append({"key": "M:" + re.sub(r"[^A-Z]", "", name.upper()),
                                             "name": name, "toks": set(toks), "first": toks[0],
                                             "party": PLETTER.get(party, "?"),
                                             "state": state, "chamber": chamber, "source": "members-table"})
# Members who served in the 2022–2026 window but have since left Congress — the press-corpus
# members table only carries current members. Hand-verified; party_source records 'manual'.
RETIRED = [
    ("Pat Toomey", ["PAT", "PATRICK"], "TOOMEY", "R", "PA", "Senate"),
    ("Patrick McHenry", ["PAT", "PATRICK"], "MCHENRY", "R", "NC", "House"),
    ("Sherrod Brown", ["SHERROD"], "BROWN", "D", "OH", "Senate"),
    ("Kyrsten Sinema", ["KYRSTEN"], "SINEMA", "I", "AZ", "Senate"),
    ("Debbie Stabenow", ["DEBBIE", "DEBORAH"], "STABENOW", "D", "MI", "Senate"),
    ("Mitt Romney", ["MITT", "WILLARD"], "ROMNEY", "R", "UT", "Senate"),
    ("Joe Manchin", ["JOE", "JOSEPH"], "MANCHIN", "I", "WV", "Senate"),
    ("Ben Cardin", ["BEN", "BENJAMIN"], "CARDIN", "D", "MD", "Senate"),
    ("Bob Casey", ["BOB", "ROBERT"], "CASEY", "D", "PA", "Senate"),
    ("Jon Tester", ["JON", "JONATHAN"], "TESTER", "D", "MT", "Senate"),
    ("Kevin McCarthy", ["KEVIN"], "MCCARTHY", "R", "CA", "House"),
    ("Anna Eshoo", ["ANNA"], "ESHOO", "D", "CA", "House"),
    ("Mike Braun", ["MIKE", "MICHAEL"], "BRAUN", "R", "IN", "Senate"),
    ("Richard Burr", ["RICHARD", "RICH"], "BURR", "R", "NC", "Senate"),
    ("Richard Shelby", ["RICHARD", "RICH"], "SHELBY", "R", "AL", "Senate"),
    ("Rob Portman", ["ROB", "ROBERT"], "PORTMAN", "R", "OH", "Senate"),
    ("Roy Blunt", ["ROY"], "BLUNT", "R", "MO", "Senate"),
    ("Patrick Leahy", ["PAT", "PATRICK"], "LEAHY", "D", "VT", "Senate"),
    ("Ben Sasse", ["BEN", "BENJAMIN"], "SASSE", "R", "NE", "Senate"),
]
for name, firsts, last, party, state, chamber in RETIRED:
    if any(m["name"].upper() == name.upper() for m in mem_by_last.get(last, [])):
        continue
    mem_by_last.setdefault(last, []).append({
        "key": "M:" + re.sub(r"[^A-Z]", "", name.upper()), "name": name,
        "toks": set(firsts) | {last}, "first": firsts[0],
        "party": party, "state": state, "chamber": chamber, "source": "manual"})
TITLE_RE = re.compile(r"^(SEN\.?|SENATOR|REP\.?|REPRESENTATIVE|CONGRESSMAN|CONGRESSWOMAN|HON\.?|SPEAKER|LEADER)\s+", re.I)
NICK = [("TOM", "THOMAS"), ("CHUCK", "CHARLES"), ("JIM", "JAMES"), ("PAT", "PATRICK"), ("MIKE", "MICHAEL"),
        ("BILL", "WILLIAM"), ("BOB", "ROBERT"), ("RICH", "RICHARD"), ("RICK", "RICHARD"), ("DAN", "DANIEL"),
        ("JOE", "JOSEPH"), ("TONY", "ANTHONY"), ("RANDY", "RANDALL"), ("KAT", "KATHERINE"), ("TED", "EDWARD"),
        ("STEVE", "STEVEN"), ("STEVE", "STEPHEN"), ("DAVE", "DAVID"), ("GREG", "GREGORY"), ("RON", "RONALD"),
        ("DON", "DONALD"), ("KEN", "KENNETH"), ("MITCH", "MITCHELL"), ("BEN", "BENJAMIN"), ("SAM", "SAMUEL"),
        ("MARC", "MARCUS"), ("HANK", "HENRY"), ("TIM", "TIMOTHY"), ("ANDY", "ANDREW"), ("DEB", "DEBRA")]
NICKSET = set(NICK) | set((b, a) for a, b in NICK)

def tok_eq(a, b):
    a, b = a.strip("."), b.strip(".")
    if a == b: return True
    if len(a) == 1 and b.startswith(a): return True
    if len(b) == 1 and a.startswith(b): return True
    return (a, b) in NICKSET

def member_match(recipient):
    """Match a recipient string to exactly one member. Title prefix optional (LD-203 items
    often omit it); the last token must equal a member's last name, and the first token must
    match either the member's first name (initial/nickname-aware) or any member name token."""
    r = recipient.strip().upper()
    core = re.sub(r"[^A-Z\s.]", "", TITLE_RE.sub("", r))
    toks = [t for t in core.split() if t and t.strip(".") not in SUFFIXES]
    if not (2 <= len(toks) <= 4):
        return None
    last = toks[-1]
    cands = []
    for m in mem_by_last.get(last, []):
        rule_a = all(any(tok_eq(t, mt) for mt in m["toks"]) for t in toks[:-1])
        rule_b = tok_eq(toks[0], m["first"])  # middle names unrestricted
        if rule_a or rule_b:
            cands.append(m)
    if len(cands) == 1:
        return cands[0]
    if TITLE_RE.match(r):
        hit = [m for m in mem_by_last.get(last, []) if m["first"][0] == toks[0][0]]
        if len(hit) == 1:
            return hit[0]
    return None

def party_for(recipient):
    m = member_match(recipient)
    if m:
        return f"({m['party']}-{m['state']})", m["source"]
    return None, None

# ---------- helpers ----------
FIX = {"Pac": "PAC", "Dccc": "DCCC", "Nrsc": "NRSC", "Nrcc": "NRCC", "Dscc": "DSCC", "Chci": "CHCI",
       "Jd": "JD", "Ii": "II", "Iii": "III", "Aipac": "AIPAC", "Rep": "Rep.", "Sen": "Sen.", "Jr": "Jr.",
       "Cbc": "CBC", "Jfc": "JFC"}
def tcase(s):
    if not s or s != s.upper(): return s
    return " ".join(FIX.get(w.strip(".,;"), w) for w in s.title().split())

ORG_ALIASES = {"DEMOCRATICSENATORIALCAMPAIGNCOMMITTEE": "DSCC",
               "DEMOCRATICCONGRESSIONALCAMPAIGNCOMMITTEE": "DCCC",
               "NATIONALREPUBLICANSENATORIALCOMMITTEE": "NRSC",
               "NATIONALREPUBLICANCONGRESSIONALCOMMITTEE": "NRCC"}
def norm_key(recipient):
    r = TITLE_RE.sub("", recipient.strip().upper())
    k = re.sub(r"[^A-Z0-9]", "", r)
    k = re.sub(r"(INC|LLC)$", "", k)
    return ORG_ALIASES.get(k, k)

def is_trump(recipient):
    u = recipient.upper()
    return "TRUMP" in u

def recips(j):
    return j["results"].get("recipients", [])

def split_table_n(slices):
    """N-slice generalization of split_table (2026-07-11): slices = [(name, recipient
    rows), ...]. Person recipients keyed on the matched MEMBER (merges filed spellings);
    Trump variants merged. Returns rows with per-slice totals/items dicts."""
    names = [n for n, _ in slices]
    table = {}
    for sname, items in slices:
        for it in items:
            raw = it["recipient"].strip()
            if raw.upper() == "N/A": continue
            m = member_match(raw)
            if is_trump(raw):
                key, disp, party, psrc = "TRUMPMERGED", "Trump-Vance Inaugural / Trump (name variants combined)", "", ""
            elif m:
                key = m["key"]
                title = "Sen." if m["chamber"] == "Senate" else "Rep."
                party, psrc = f"({m['party']}-{m['state']})", m["source"]
                disp = f"{title} {m['name']} {party}"
            else:
                key, disp, party, psrc = norm_key(raw), tcase(raw), "", ""
            row = table.setdefault(key, {"disp": disp, "party": party, "psrc": psrc,
                                         "tot": {n: 0.0 for n in names},
                                         "items": {n: 0 for n in names}, "variants": set()})
            row["tot"][sname] += it["total"]; row["items"][sname] += it["items"]
            row["variants"].add(raw)
    out = []
    for key, row in table.items():
        out.append({"display": row["disp"], "party": row["party"], "party_source": row["psrc"],
                    "tot": row["tot"], "items": row["items"], "n_variants": len(row["variants"])})
    out.sort(key=lambda r: -sum(r["tot"].values()))
    return out

def split_table(slice_a, slice_b, a_name, b_name):
    """Join two recipient lists; person recipients keyed on the matched MEMBER (merges
    'Rep. French Hill' / 'Rep. James French Hill' spellings); Trump variants merged."""
    table = {}
    for src, items in ((a_name, slice_a), (b_name, slice_b)):
        for it in items:
            raw = it["recipient"].strip()
            if raw.upper() == "N/A": continue
            m = member_match(raw)
            if is_trump(raw):
                key, disp, party, psrc = "TRUMPMERGED", "Trump-Vance Inaugural / Trump (name variants combined)", "", ""
            elif m:
                key = m["key"]
                title = "Sen." if m["chamber"] == "Senate" else "Rep."
                party, psrc = f"({m['party']}-{m['state']})", m["source"]
                disp = f"{title} {m['name']} {party}"
            else:
                key, disp, party, psrc = norm_key(raw), tcase(raw), "", ""
            row = table.setdefault(key, {"disp": disp, "party": party, "psrc": psrc,
                                         a_name: 0.0, b_name: 0.0,
                                         a_name + "_items": 0, b_name + "_items": 0, "variants": set()})
            row[src] += it["total"]; row[src + "_items"] += it["items"]
            row["variants"].add(raw)
    out = []
    for key, row in table.items():
        out.append({"display": row["disp"], "party": row["party"], "party_source": row["psrc"],
                    "a": row[a_name], "b": row[b_name],
                    "a_items": row[a_name + "_items"], "b_items": row[b_name + "_items"],
                    "n_variants": len(row["variants"])})
    out.sort(key=lambda r: -(r["a"] + r["b"]))
    return out

def wcsv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)
    print("[csv]", os.path.basename(path), len(rows))

def variant_audit(path, slices):
    """QA audit trail: every raw recipient row that member-merged, so a reviewer can
    verify each merge. slices = [(slice_name, recipient_rows), ...]"""
    rows = []
    for sname, items in slices:
        for it in items:
            raw = it["recipient"].strip()
            if raw.upper() == "N/A": continue
            m = member_match(raw)
            if not m: continue
            title = "Sen." if m["chamber"] == "Senate" else "Rep."
            rows.append([f"{title} {m['name']} ({m['party']}-{m['state']})", m["source"], sname,
                         raw, it["total"], it["items"]])
    rows.sort(key=lambda r: (r[0], r[2], -r[4]))
    wcsv(path, ["member (merged row in the split CSV)", "party_source", "giver_slice",
                "raw_recipient_string_as_filed", "total", "items"], rows)

# ---------- crypto (three-tier: native / diversified-forward >=5% share / ambient <5%) ----------
if want("crypto"):
    nat = loadj("crypto_giving_pureplay.json")          # unchanged 2026-07-08 input (its 387 recipient rows ARE exhaustive)
    fwd = loadj("crypto_giving_div_forward.json")       # >=5% crypto activity share, exhaustive
    amb = loadj("crypto_giving_div_ambient.json")       # <5%, exhaustive
    div_full = loadj("crypto_giving_div_full.json")     # the un-split diversified slice, exhaustive — gate-integrity baseline

    # GATE INTEGRITY: forward + ambient must partition the old diversified-core slice
    # EXACTLY, per raw recipient string (the gate moves givers between slices; it must
    # never create, lose, or move a dollar between recipients).
    rdd = {r["recipient"]: r["total"] for r in recips(div_full)}
    rff = {r["recipient"]: r["total"] for r in recips(fwd)}
    raa = {r["recipient"]: r["total"] for r in recips(amb)}
    bad = [k for k, v in rdd.items() if abs(rff.get(k, 0) + raa.get(k, 0) - v) > 0.01]
    extra = [k for k in set(rff) | set(raa) if k not in rdd]
    assert not bad and not extra, f"gate partition broken: {len(bad)} mismatched / {len(extra)} extra raw recipients"
    print(f"crypto gate partition: EXACT over {len(rdd)} raw recipient strings — "
          f"forward {fwd['results']['totals']['total']:,.0f} + ambient {amb['results']['totals']['total']:,.0f}"
          f" = diversified {div_full['results']['totals']['total']:,.0f}")
    print("crypto native totals:", nat["results"]["totals"]["total"])

    crypto_split = split_table_n([("native", recips(nat)), ("forward", recips(fwd)), ("ambient", recips(amb))])
    wcsv(os.path.join(REPO, "out", "packages", "crypto", "data", "crypto_ld203_recipients_split.csv"),
         ["recipient", "party", "party_source", "from_crypto_native", "native_items",
          "from_diversified_forward", "forward_items", "from_ambient_lowshare", "ambient_items",
          "name_variants_combined"],
         [[r["display"], r["party"], r["party_source"],
           r["tot"]["native"], r["items"]["native"], r["tot"]["forward"], r["items"]["forward"],
           r["tot"]["ambient"], r["items"]["ambient"], r["n_variants"]]
          for r in crypto_split[:400]])
    variant_audit(os.path.join(REPO, "out", "packages", "crypto", "data", "crypto_ld203_member_variant_audit.csv"),
                  [("crypto_native", recips(nat)), ("diversified_forward", recips(fwd)),
                   ("ambient_lowshare", recips(amb))])

    # REGRESSION vs the archived two-slice CSV: the native column must be stable row for
    # row; forward+ambient vs the old diversified column may only GROW, and only by
    # recovered sub-cutoff variants (the old build merged each run's top-400 rows only).
    arch = os.path.join(REPO, "out", "packages", "crypto", "_archive",
                        "data_2026-07-11_pre-intensity", "crypto_ld203_recipients_split.csv")
    old_rows = {r["recipient"]: r for r in csv.DictReader(open(arch, encoding="utf-8-sig"))}
    n_common = n_nat_diff = n_div_same = n_div_up = n_div_down = 0
    ups = []
    for r in crypto_split[:400]:
        o = old_rows.get(r["display"])
        if not o:
            continue
        n_common += 1
        if abs(float(o["from_crypto_native"] or 0) - r["tot"]["native"]) > 0.01:
            n_nat_diff += 1
            print(f"   NATIVE CHANGED (must be zero): {r['display']!r} "
                  f"{o['from_crypto_native']} -> {r['tot']['native']}")
        old_div = float(o["from_diversified_core"] or 0)
        new_div = r["tot"]["forward"] + r["tot"]["ambient"]
        if abs(new_div - old_div) <= 0.01:
            n_div_same += 1
        elif new_div > old_div:
            n_div_up += 1
            ups.append((r["display"], old_div, new_div))
        else:
            n_div_down += 1
            print(f"   DIVERSIFIED SHRANK (must be zero): {r['display']!r} "
                  f"{old_div:,.0f} -> {new_div:,.0f}")
    assert n_nat_diff == 0 and n_div_down == 0, "regression vs archived split failed"
    print(f"crypto vs archived split ({n_common} common rows): native stable on ALL; "
          f"diversified identical on {n_div_same}, grew on {n_div_up} (recovered sub-cutoff variants)")
    for disp, o, n in sorted(ups, key=lambda x: -(x[2] - x[1]))[:12]:
        print(f"   recovered variants: {disp[:52]:54} {o:>12,.0f} -> {n:>12,.0f}  (+{n - o:,.0f})")
    print("\ncrypto top split rows:")
    for r in crypto_split[:14]:
        print(f"   {r['display'][:52]:54} native={r['tot']['native']:>11,.0f}  "
              f"fwd={r['tot']['forward']:>11,.0f}  amb={r['tot']['ambient']:>11,.0f}")

# ---------- healthcare ----------
if want("healthcare"):
    foc = loadj("hc_giving_focused.json")
    mix = loadj("hc_giving_mixed.json")
    print("\nhc focused totals:", foc["results"]["totals"]["total"], "| mixed totals:", mix["results"]["totals"]["total"])
    hc_split = split_table(recips(foc), recips(mix), "focused", "mixed")
    wcsv(os.path.join(REPO, "out", "packages", "healthcare", "data", "hc_ld203_recipients_split.csv"),
         ["recipient", "party", "party_source", "from_health_focused", "focused_items",
          "from_mixed_diversified", "mixed_items", "name_variants_combined"],
         [[r["display"], r["party"], r["party_source"], r["a"], r["a_items"], r["b"], r["b_items"], r["n_variants"]]
          for r in hc_split[:400]])
    variant_audit(os.path.join(REPO, "out", "packages", "healthcare", "data", "hc_ld203_member_variant_audit.csv"),
                  [("health_focused", recips(foc)), ("mixed_diversified", recips(mix))])
    print("hc top split rows:")
    for r in hc_split[:10]:
        print(f"   {r['display'][:58]:60} focused={r['a']:>12,.0f}  mixed={r['b']:>12,.0f}")

# ---------- AIPAC ----------
if want("aipac"):
    ap = loadj("aipac_giving_deep.json")
    arec = recips(ap)
    grouped = {}
    for it in arec:
        raw = it["recipient"].strip()
        if raw.upper() == "N/A": continue
        m = member_match(raw)
        if m:
            key = m["key"]
            title = "Sen." if m["chamber"] == "Senate" else "Rep."
            disp, br, src = f"{title} {m['name']} ({m['party']}-{m['state']})", f"({m['party']}-{m['state']})", m["source"]
        else:
            key, disp, br, src = norm_key(raw), tcase(raw), "", ""
        g = grouped.setdefault(key, {"disp": disp, "br": br, "src": src, "total": 0.0, "items": 0})
        g["total"] += it["total"]; g["items"] += it["items"]
    rows = []
    psum = {}
    for g in sorted(grouped.values(), key=lambda g: -g["total"]):
        rows.append([g["disp"], g["br"], g["src"], g["total"], g["items"]])
        if g["br"]:
            p = g["br"][1]  # D/R/I
            psum.setdefault(p, [0.0, 0])
            psum[p][0] += g["total"]; psum[p][1] += 1
    wcsv(os.path.join(REPO, "out", "packages", "aipac", "data", "aipac_ld203_recipients.csv"),
         ["recipient", "party", "party_source", "total", "items"], rows)
    print("\nAIPAC party split over member-matched recipients (top-400 recipient rows):")
    for p, (tot, n) in sorted(psum.items()):
        print(f"   {p}: {tot:,.0f} across {n} members")
    json.dump({"psum": {p: {"total": v[0], "n": v[1]} for p, v in psum.items()}},
              open(os.path.join(S, "aipac_party_split.json"), "w"))
print("done")
