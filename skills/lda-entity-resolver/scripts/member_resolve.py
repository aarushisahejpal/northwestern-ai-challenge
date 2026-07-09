#!/usr/bin/env python3
"""Shared member + political-committee resolver (P6). Importable + CLI.

Given a raw recipient/honoree string as filed (LD-203 strings splinter: "Rep. Tom
Emmer" / "REP. THOMAS EARL EMMER JR" / "Emmer for Congress" / "Lummis Victory
Committee"), resolve it to the member(s) of Congress it names or supports:

    from member_resolve import MemberResolver
    r = MemberResolver("db/lda_full.duckdb")
    rep = r.resolve("Emmer for Congress", when="2024-05-01")
    # rep["kind"]    -> 'committee'
    # rep["matches"] -> [{bioguide_id, name, chamber, state, party, tier,
    #                     confidence, via, cmte_id, ...}]

Tiers (Rob's mapping rules, DECISIONS 2026-07-09 — rollup, never conflation):
    direct              the string names the member personally
    campaign-committee  FEC designation A/P (principal/authorized)
    leadership-pac      FEC designation D, via sponsor candidate ids
    jfc                 joint fundraising committee — one match PER PARTICIPANT,
                        always flagged shared/unallocated (dollars are NEVER split
                        or summed into a member by this layer; participant lists
                        may be partial — see build_members.py)
Party committees (DSCC/NRSC/DCCC/NRCC/DNC/RNC) and caucus institutions are their
own recipients: kind='party-committee', never member-mapped.

Ambiguity is a report, not a merge: multiple candidate members come back as
multiple matches with confidence='ambiguous'; callers must not pick silently.
Every match carries `confidence` + `source` (the audit convention from the
2026-07-08 Emmer reconciliation). Party annotation is date-aware via member_terms
(Sinema is (D-AZ) for a 2022-06 item, (I-AZ) for 2023).

Person-match semantics are the proven 2026-07-08 package matcher (title-strip,
suffix-strip, last-name key, nickname/initial-aware firsts), promoted from
out/packages/*/_build/enhance_giving.py, plus two labeled extensions:
    confidence='inverted'  "EMMER, TOM"-style comma-inverted names
    kind='compound'        multi-recipient strings ("A; B; NRSC") resolved per part

Requires the tables from build_members.py (members_all / member_terms /
member_committees). Curated additions: member_aliases.json beside this script.

CLI:
  python skills/lda-entity-resolver/scripts/member_resolve.py "Emmer for Congress"
    [--date 2023-05-01] [--db db/lda_full.duckdb] [--json]
"""

import argparse
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SUFFIXES = {"JR", "SR", "II", "III", "IV", "JR.", "SR."}
TITLE_RE = re.compile(
    r"^(THE\s+)?(SEN\.?|SENATOR|REP\.?|REPRESENTATIVE|CONGRESSMAN|CONGRESSWOMAN|"
    r"HON\.?|HONORABLE|SPEAKER|LEADER|DR\.?|MR\.?|MRS\.?|MS\.?)\s+", re.I)

# Party committees + caucus institutions: their own recipients, never member-mapped.
PARTY_COMMITTEES = {
    "DSCC": "DSCC", "DEMOCRATICSENATORIALCAMPAIGNCOMMITTEE": "DSCC",
    "DCCC": "DCCC", "DEMOCRATICCONGRESSIONALCAMPAIGNCOMMITTEE": "DCCC",
    "NRSC": "NRSC", "NATIONALREPUBLICANSENATORIALCOMMITTEE": "NRSC",
    "NRCC": "NRCC", "NATIONALREPUBLICANCONGRESSIONALCOMMITTEE": "NRCC",
    "DNC": "DNC", "DEMOCRATICNATIONALCOMMITTEE": "DNC",
    "RNC": "RNC", "REPUBLICANNATIONALCOMMITTEE": "RNC",
    "CBCF": "CBC Foundation", "CONGRESSIONALBLACKCAUCUSFOUNDATION": "CBC Foundation",
    "CONGRESSIONALBLACKCAUCUSFOUNDATIONINC": "CBC Foundation",
    "CBCINSTITUTE": "CBC Institute",
    "CONGRESSIONALBLACKCAUCUS": "Congressional Black Caucus",
    "CONGRESSIONALHISPANICCAUCUS": "Congressional Hispanic Caucus",
    "CHCI": "CHCI", "CONGRESSIONALHISPANICCAUCUSINSTITUTE": "CHCI",
    "CONGRESSIONALHISPANICCAUCUSINSTITUTEINC": "CHCI",
}

# Gate for the committee prefix-match fallback: only strings that look like a
# committee may prefix-match one (a bare "TIM SCOTT" must not resolve to
# "TIM SCOTT FOR AMERICA").
CMTE_HINT = re.compile(r"\b(PAC|COMMITTEE|VICTORY|FUND|CAMPAIGN|LEADERSHIP|"
                       r"FOR (CONGRESS|SENATE|AMERICA|PRESIDENT))\b")


def norm_cmte(raw):
    # keep identical to build_members.py:norm_cmte
    if not raw:
        return None
    s = raw.upper()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9]+", "", s)
    return s or None


def _load_lexicon():
    lex = json.loads((Path(__file__).parent / "member_aliases.json")
                     .read_text(encoding="utf-8"))
    pairs = {tuple(p) for p in lex["nickname_pairs"]}
    lex["_nickset"] = pairs | {(b, a) for a, b in pairs}
    return lex


class MemberResolver:
    def __init__(self, db="db/lda_full.duckdb", con=None):
        self.lex = _load_lexicon()
        self.nickset = self.lex["_nickset"]
        own = con is None
        if own:
            con = duckdb.connect(db, read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            missing = {"members_all", "member_terms", "member_committees"} - tables
            if missing:
                raise RuntimeError(
                    f"missing tables {sorted(missing)} — run "
                    "skills/lda-entity-resolver/scripts/build_members.py first")
            self.members = [dict(zip([d[0] for d in con.description], r))
                            for r in con.execute("SELECT * FROM members_all").fetchall()]
            self.terms = con.execute(
                "SELECT bioguide_id, party_letter, from_date, to_date "
                "FROM member_terms ORDER BY from_date").fetchall()
            self.cmtes = [dict(zip([d[0] for d in con.description], r))
                          for r in con.execute("SELECT * FROM member_committees")
                          .fetchall()]
        finally:
            if own:
                con.close()

        self.by_bio = {m["bioguide_id"]: m for m in self.members}
        self.terms_by_bio = {}
        for bio, pl, f, t in self.terms:
            self.terms_by_bio.setdefault(bio, []).append((pl, f, t))

        # person index: keyed on the FINAL word of the last name (handles
        # "Wasserman Schultz"); each entry carries the full token set. Tokens are
        # A-Z only — congress-legislators writes nicknames INSIDE the first-name
        # field as 'Nicole (Nikki)', so punctuation must not survive tokenizing.
        def words(s):
            return re.findall(r"[A-Z]+", (s or "").upper())

        self.by_last = {}
        for m in self.members:
            last_words = words(m["last_name"])
            if not last_words:
                continue
            toks = set(last_words)
            for f in (m["first_name"], m["nickname"], m["middle_name"],
                      m["name"], m["aka_names"]):
                toks.update(words(f))
            for extra in self.lex["member_aliases"].get(m["bioguide_id"], []):
                toks.update(words(extra))
            # firsts: legal first + nickname(s) + the display name's first word
            firsts = set(words(m["first_name"])[:1]) | set(words(m["nickname"]))
            if m["first_name"] and "(" in m["first_name"]:
                firsts.update(words(m["first_name"])[1:])
            firsts.update(words(m["name"])[:1])
            firsts -= set(last_words)
            self.by_last.setdefault(last_words[-1], []).append(
                {"m": m, "toks": toks, "last_words": last_words,
                 "firsts": firsts})

        # committee index: exact normalized name (+ curated aliases) -> rows
        self.cmte_by_norm = {}
        for c in self.cmtes:
            if c["cmte_name_norm"]:
                self.cmte_by_norm.setdefault(c["cmte_name_norm"], []).append(c)
        self.cmte_by_id = {}
        for c in self.cmtes:
            self.cmte_by_id.setdefault(c["cmte_id"], []).append(c)
        self.cmte_alias = {norm_cmte(k): v
                           for k, v in self.lex["committee_aliases"].items()}
        self._norm_list = sorted(self.cmte_by_norm)  # for the prefix fallback

    # ------------------------------------------------------------ party by date

    def party_at(self, bioguide_id, when=None):
        """(party_letter, source). Dated when the date falls inside a service
        period; 'nearest-term' when outside (e.g. a gift after departure);
        'latest-term' when no date given."""
        segs = self.terms_by_bio.get(bioguide_id)
        if not segs:
            m = self.by_bio.get(bioguide_id)
            return ((m and m["party"] or "?")[:1], "members_all")
        if when is None:
            return segs[-1][0], "latest-term"
        if isinstance(when, str):
            when = _date.fromisoformat(when[:10])
        for pl, f, t in segs:
            if f <= when <= t:
                return pl, "term-dated"
        nearest = min(segs, key=lambda s: min(abs((when - s[1]).days),
                                              abs((when - s[2]).days)))
        return nearest[0], "nearest-term"

    # ------------------------------------------------------------ person match

    def _tok_eq(self, a, b):
        a, b = a.strip("."), b.strip(".")
        if a == b:
            return True
        if len(a) == 1 and b.startswith(a):
            return True
        if len(b) == 1 and a.startswith(b):
            return True
        return (a, b) in self.nickset

    def _person(self, raw):
        """The 2026-07-08 package matcher, generalized. Returns (entries, how)."""
        r = raw.strip().upper()
        m_title = TITLE_RE.match(r)
        titled = bool(m_title)
        title_chamber = None
        if titled:
            tword = re.sub(r"[^A-Z]", "", m_title.group(2))
            title_chamber = ("Senate" if tword.startswith("SEN") else
                             "House" if tword.startswith(("REP", "CONGRESS"))
                             else None)
        core = r
        while True:
            stripped = TITLE_RE.sub("", core)
            if stripped == core:
                break
            core = stripped
        core = re.sub(r"[^A-Z\s.]", " ", core)
        toks = [t for t in core.split() if t and t.strip(".") not in SUFFIXES]
        if not (2 <= len(toks) <= 4):
            return [], None
        entries = self.by_last.get(toks[-1], [])
        cands = []
        for e in entries:
            if not all(w in toks for w in e["last_words"]):
                continue
            rest = [t for t in toks if t not in e["last_words"]]
            rule_a = all(any(self._tok_eq(t, mt) for mt in e["toks"]) for t in rest)
            rule_b = bool(rest) and any(self._tok_eq(rest[0], f) for f in e["firsts"])
            if rule_a or rule_b:
                cands.append(e)
        if len(cands) == 1:
            return cands, "name"
        if len(cands) > 1 and title_chamber:
            # a SEN./REP. title disambiguates same-name pairs across chambers
            # (Sen. Robert Menendez vs Rep. Robert Menendez his son)
            hit = [e for e in cands if e["m"]["chamber"] == title_chamber]
            if len(hit) == 1:
                return hit, "title-chamber"
        if titled and entries and len(cands) != 1:
            # the proven fallback (single-letter middle initials over-match
            # rule_a — 'GLENN' hits 'Bennie G. Thompson' — so a titled string
            # falls back to a unique first-initial among same-last members)
            hit = [e for e in entries
                   if any(f[:1] == toks[0][:1] for f in e["firsts"])]
            if len(hit) == 1:
                return hit, "title-initial"
        if len(cands) > 1:
            return cands, "ambiguous"
        # comma-inverted "EMMER, TOM" (labeled extension; not in the 2026-07-08
        # matcher, so retrofit audits list these rows separately)
        if raw.count(",") == 1 and not titled:
            ln, _, first = raw.upper().partition(",")
            inv = f"{first.strip()} {ln.strip()}"
            if inv.strip() != raw.strip().upper():
                sub, how = self._person(inv)
                if len(sub) == 1 and how in ("name", "title-initial"):
                    return sub, "inverted"
        return [], None

    # ------------------------------------------------------------ public API

    def _match(self, m, tier, confidence, source, via=None, cmte_id=None, when=None):
        pl, psrc = self.party_at(m["bioguide_id"], when)
        return {"bioguide_id": m["bioguide_id"], "name": m["name"],
                "chamber": m["chamber"], "state": m["state"],
                "party": pl, "party_source": psrc, "tier": tier,
                "confidence": confidence, "source": source,
                "via": via, "cmte_id": cmte_id}

    def resolve(self, raw, when=None, split_compound=True):
        """Resolve one filed string. Returns a report dict:
        {query, kind: member|committee|party-committee|compound|unresolved,
         matches: [...], ambiguous: bool, parts: [...] (compound only)}"""
        rep = {"query": raw, "kind": "unresolved", "matches": [],
               "ambiguous": False}
        if not raw or raw.strip().upper() in ("", "N/A", "NA", "NONE"):
            return rep
        key = norm_cmte(raw)

        if key in PARTY_COMMITTEES:
            rep.update(kind="party-committee",
                       display=PARTY_COMMITTEES[key])
            return rep

        # exact committee-name match (or curated alias)
        rows = self.cmte_by_norm.get(key) or self.cmte_by_id.get(
            self.cmte_alias.get(key) or "")
        how = "committee-exact"
        if not rows and key and len(key) >= 10 and ";" not in raw \
                and CMTE_HINT.search(raw.upper()):
            # unique-prefix fallback, gated on committee-looking strings only
            pref = [n for n in self._norm_list
                    if n.startswith(key) or key.startswith(n)]
            if len({self.cmte_by_norm[n][0]["cmte_id"] for n in pref}) == 1:
                rows, how = self.cmte_by_norm[pref[0]], "committee-prefix"
        if rows:
            for c in rows:
                m = self.by_bio.get(c["bioguide_id"])
                if not m:
                    continue
                tier = c["tier"] + ("-shared, unallocated" if c["tier"] == "jfc"
                                    else "")
                conf = c["confidence"] if how == "committee-exact" else "prefix"
                rep["matches"].append(self._match(
                    m, tier, conf, f"{how}/{c['link_source']}",
                    via=c["cmte_name"], cmte_id=c["cmte_id"], when=when))
            if rep["matches"]:
                rep["kind"] = "committee"
                return rep

        # person
        cands, how = self._person(raw)
        if cands:
            conf = {"name": "matched", "title-initial": "title-initial",
                    "title-chamber": "title-chamber", "inverted": "inverted",
                    "ambiguous": "ambiguous"}[how]
            for e in cands:
                rep["matches"].append(self._match(e["m"], "direct", conf,
                                                  "person-name", when=when))
            rep["kind"] = "member"
            rep["ambiguous"] = how == "ambiguous"
            return rep

        # compound multi-recipient strings: "A; B; NRSC" or titled comma lists
        if split_compound:
            parts = None
            if ";" in raw:
                parts = [p for p in raw.split(";") if p.strip()]
            elif raw.count(",") >= 2 and \
                    len(re.findall(r"\b(SEN|REP|SENATOR|REPRESENTATIVE|HONORABLE)\b",
                                   raw.upper())) >= 2:
                parts = [p for p in raw.split(",") if p.strip()]
            if parts and len(parts) >= 2:
                sub = [self.resolve(p.strip(), when=when, split_compound=False)
                       for p in parts]
                if any(s["matches"] or s["kind"] == "party-committee" for s in sub):
                    rep["kind"] = "compound"
                    rep["parts"] = sub
                    for s in sub:
                        for mt in s["matches"]:
                            mt = dict(mt)
                            if mt["tier"] == "direct":
                                mt["tier"] = "multi-honoree, unallocated"
                            mt["confidence"] = "compound:" + mt["confidence"]
                            rep["matches"].append(mt)
                    return rep
        return rep


def bracket(match):
    return f"({match['party']}-{match['state']})"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", help="a filed recipient/honoree/committee string")
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--date", help="item date (YYYY-MM-DD) for party-as-of annotation")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    r = MemberResolver(args.db)
    rep = r.resolve(args.query, when=args.date)
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return
    print(f"query: {rep['query']!r}" + (f"   as-of {args.date}" if args.date else ""))
    print(f"kind:  {rep['kind']}" + ("   (AMBIGUOUS — report, not a merge)"
                                     if rep["ambiguous"] else ""))
    if rep["kind"] == "party-committee":
        print(f"  -> {rep['display']} — its own recipient, never member-mapped")
    for m in rep["matches"]:
        via = f"  via {m['via']} [{m['cmte_id']}]" if m["via"] else ""
        print(f"  -> {m['name']} {bracket(m)} {m['chamber']}  tier={m['tier']}  "
              f"confidence={m['confidence']}  source={m['source']}"
              f"  party_source={m['party_source']}{via}")
    if not rep["matches"] and rep["kind"] == "unresolved":
        print("  (unresolved — left as filed; add a curated entry to "
              "member_aliases.json if this should map)")


if __name__ == "__main__":
    main()
