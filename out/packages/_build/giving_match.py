"""Shared LD-203 recipient-matching helpers (2026-07-12).

Kept in exact sync with out/packages/{healthcare,aipac}/_build/enhance_giving.py's
member_match()/norm_key() (verbatim copy of the matching rules — same drift risk
as resolve_entities.py's norm_name() sync note in lda_ld203_giving.py). Needed so
the widget-underlying exporters can key individual LD-203 items to the exact same
display row enhance_giving.py already produced in *_ld203_recipients*.csv, without
re-deriving a second, possibly-divergent grouping.
"""
import re

import duckdb


def load_members(db_path):
    con = duckdb.connect(db_path, read_only=True)
    members = con.execute("SELECT name, party, state, chamber FROM members").fetchall()
    con.close()
    return members


SUFFIXES = {"JR", "SR", "II", "III", "IV", "JR.", "SR."}
PLETTER = {"Democrat": "D", "Republican": "R", "Independent": "I"}
TITLE_RE = re.compile(r"^(SEN\.?|SENATOR|REP\.?|REPRESENTATIVE|CONGRESSMAN|CONGRESSWOMAN|HON\.?|SPEAKER|LEADER)\s+", re.I)
NICK = [("TOM", "THOMAS"), ("CHUCK", "CHARLES"), ("JIM", "JAMES"), ("PAT", "PATRICK"), ("MIKE", "MICHAEL"),
        ("BILL", "WILLIAM"), ("BOB", "ROBERT"), ("RICH", "RICHARD"), ("RICK", "RICHARD"), ("DAN", "DANIEL"),
        ("JOE", "JOSEPH"), ("TONY", "ANTHONY"), ("RANDY", "RANDALL"), ("KAT", "KATHERINE"), ("TED", "EDWARD"),
        ("STEVE", "STEVEN"), ("STEVE", "STEPHEN"), ("DAVE", "DAVID"), ("GREG", "GREGORY"), ("RON", "RONALD"),
        ("DON", "DONALD"), ("KEN", "KENNETH"), ("MITCH", "MITCHELL"), ("BEN", "BENJAMIN"), ("SAM", "SAMUEL"),
        ("MARC", "MARCUS"), ("HANK", "HENRY"), ("TIM", "TIMOTHY"), ("ANDY", "ANDREW"), ("DEB", "DEBRA")]
NICKSET = set(NICK) | set((b, a) for a, b in NICK)
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
ORG_ALIASES = {"DEMOCRATICSENATORIALCAMPAIGNCOMMITTEE": "DSCC",
               "DEMOCRATICCONGRESSIONALCAMPAIGNCOMMITTEE": "DCCC",
               "NATIONALREPUBLICANSENATORIALCOMMITTEE": "NRSC",
               "NATIONALREPUBLICANCONGRESSIONALCOMMITTEE": "NRCC"}
FIX = {"Pac": "PAC", "Dccc": "DCCC", "Nrsc": "NRSC", "Nrcc": "NRCC", "Dscc": "DSCC", "Chci": "CHCI",
       "Jd": "JD", "Ii": "II", "Iii": "III", "Aipac": "AIPAC", "Rep": "Rep.", "Sen": "Sen.", "Jr": "Jr.",
       "Cbc": "CBC", "Jfc": "JFC"}


def name_tokens(n):
    toks = [t.strip(' ."(),') for t in n.upper().replace(",", " ").split()]
    return [t for t in toks if t and t not in SUFFIXES]


def build_index(members):
    mem_by_last = {}
    for name, party, state, chamber in members:
        toks = name_tokens(name)
        if not toks:
            continue
        last = toks[-1]
        mem_by_last.setdefault(last, []).append({
            "key": "M:" + re.sub(r"[^A-Z]", "", name.upper()), "name": name,
            "toks": set(toks), "first": toks[0], "party": PLETTER.get(party, "?"),
            "state": state, "chamber": chamber, "source": "members-table"})
    for name, firsts, last, party, state, chamber in RETIRED:
        if any(m["name"].upper() == name.upper() for m in mem_by_last.get(last, [])):
            continue
        mem_by_last.setdefault(last, []).append({
            "key": "M:" + re.sub(r"[^A-Z]", "", name.upper()), "name": name,
            "toks": set(firsts) | {last}, "first": firsts[0],
            "party": party, "state": state, "chamber": chamber, "source": "manual"})
    return mem_by_last


def tok_eq(a, b):
    a, b = a.strip("."), b.strip(".")
    if a == b:
        return True
    if len(a) == 1 and b.startswith(a):
        return True
    if len(b) == 1 and a.startswith(b):
        return True
    return (a, b) in NICKSET


def member_match(mem_by_last, recipient):
    r = recipient.strip().upper()
    core = re.sub(r"[^A-Z\s.]", "", TITLE_RE.sub("", r))
    toks = [t for t in core.split() if t and t.strip(".") not in SUFFIXES]
    if not (2 <= len(toks) <= 4):
        return None
    last = toks[-1]
    cands = []
    for m in mem_by_last.get(last, []):
        rule_a = all(any(tok_eq(t, mt) for mt in m["toks"]) for t in toks[:-1])
        rule_b = tok_eq(toks[0], m["first"])
        if rule_a or rule_b:
            cands.append(m)
    if len(cands) == 1:
        return cands[0]
    if TITLE_RE.match(r):
        hit = [m for m in mem_by_last.get(last, []) if m["first"][0] == toks[0][0]]
        if len(hit) == 1:
            return hit[0]
    return None


def norm_key(recipient):
    r = TITLE_RE.sub("", recipient.strip().upper())
    k = re.sub(r"[^A-Z0-9]", "", r)
    k = re.sub(r"(INC|LLC)$", "", k)
    return ORG_ALIASES.get(k, k)


def is_trump(recipient):
    return "TRUMP" in recipient.upper()


def tcase(s):
    if not s or s != s.upper():
        return s
    return " ".join(FIX.get(w.strip(".,;"), w) for w in s.title().split())


def first_seen_display(mem_by_last, recipient_lists):
    """key -> disp, first-seen-wins across recipient_lists IN ORDER — matching
    enhance_giving.py's split_table()/AIPAC grouping (table.setdefault keeps the
    FIRST raw variant's display text for a merged key; later variants with the
    same key only add to its total). recipient_lists items need a 'recipient'
    field; pass them pre-sorted by total DESC (as the giving tool's SQL returns
    them) so the winning display text matches what's already shipped."""
    out = {}
    for items in recipient_lists:
        for it in items:
            raw = it["recipient"].strip()
            if raw.upper() == "N/A":
                continue
            key, disp = display_key(mem_by_last, raw)
            out.setdefault(key, disp)
    return out


def display_key(mem_by_last, raw):
    """The exact (key, display) pair enhance_giving.py's split_table()/AIPAC
    grouping assigns a raw recipient string to."""
    if is_trump(raw):
        return "TRUMPMERGED", "Trump-Vance Inaugural / Trump (name variants combined)"
    m = member_match(mem_by_last, raw)
    if m:
        title = "Sen." if m["chamber"] == "Senate" else "Rep."
        return m["key"], f"{title} {m['name']} ({m['party']}-{m['state']})"
    return norm_key(raw), tcase(raw)
