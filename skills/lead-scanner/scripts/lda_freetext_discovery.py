#!/usr/bin/env python3
"""Free-text discovery loop (P4): propose vocabulary for an industry facet by
mining the lobbying free-text, so a human can triage terms into
industry_lexicon.json. This is the DISCOVERY half of the discovery/serving split
(roadmap §1b): it never tags a finding — it only ranks candidate terms. The cited
SERVING layer stays the deterministic keyword tagger (lda_industry_map.py ->
lobbying_issue_mentions).

Requires: the built DuckDB (lda-corpus-loader). Corpus binding —
reference/corpus-profile.md: `freetext_surface` (+ FTS). Proposes vocabulary for
industry_lexicon.json; never writes the DB or the lexicon.

Reads lobbying_freetext (+ its FTS index) built by lda-corpus-loader's
add_lobbying_freetext.py. Three complementary signals, each reproducible:

  keyness   (default): Monroe log-odds-with-informative-prior of uni/bi-grams in
            the facet's currently-tagged docs vs a background sample. Surfaces
            phrases that co-occur with the facet but AREN'T yet lexicon phrases —
            the candidate list. Terms already covered by the lexicon are hidden.
  --emergence: per-year document frequency for the top candidates (and current
            phrases), to catch vocabulary entering the lexicon (stablecoin, GENIUS
            Act) as it appears.
  --untagged SEED: docs that FTS-match SEED but carry NO facet tag (the recall
            gap) — ranked terms the current lexicon is blind to.
  --search  QUERY: interactive BM25 test of a candidate term over the free-text
            (no rebuild) — verify a term's precision before adding it.

Usage:
  python lda_freetext_discovery.py                       # crypto keyness candidates
  python lda_freetext_discovery.py --emergence
  python lda_freetext_discovery.py --untagged 'token OR wallet OR "digital dollar"'
  python lda_freetext_discovery.py --search 'stablecoin "market structure"'

    --db PATH        DuckDB (default db/lda_full.duckdb)
    --lexicon PATH   industry_lexicon.json (default beside this script)
    --facet ID       facet id (default crypto)
    --top N          candidates / rows shown (default 40)
    --bg N           background sample size for keyness (default 120000)

A discovered term is a CANDIDATE, never auto-added: --search it, eyeball a few raw
docs (show_record.py), then a human adds it to industry_lexicon.json with a source
and bumps the version. Nothing here writes to the DB or the lexicon.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Lobbying-boilerplate + generic stopwords: these dominate every filing's free-text
# and would swamp any keyness ranking, so they are dropped before counting.
STOP = set("""
a an the and or of to in on for with by from as at is are be been being this that
these those it its their his her our your they them we you he she i not no any all
some more most other such than then so if but into over under about above below up
down out off only own same too very can will just should now
issues issue related relating regarding concerning pertaining matters matter act
bill bills legislation legislative law laws house senate congress congressional
federal policy policies regulation regulations regulatory rule rules proposed
implementation support supporting oppose monitor monitoring general provisions
provision including include includes potential various affecting affect impact
efforts effort discussion discussions administration agency agencies department
committee reform reforms amendment amendments section funding appropriations
program programs national united states government public private sector industry
company companies inc llc corp corporation service services related
""".split())

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.\-]{1,28}[a-z0-9]")


def tokens(text):
    toks = [t for t in TOKEN_RE.findall(text.lower())
            if t not in STOP and not t.replace(".", "").isdigit()]
    return toks


def ngrams(toks):
    for t in toks:
        yield t
    for a, b in zip(toks, toks[1:]):
        if a not in STOP and b not in STOP:
            yield a + " " + b


def load_lexicon(path, facet_id):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    facet = next((f for f in data["facets"] if f["id"] == facet_id), None)
    if not facet:
        sys.exit(f"no facet '{facet_id}'; have "
                 f"{', '.join(f['id'] for f in data['facets'])}")
    return data["_meta"], facet


def covered(term, phrase_words):
    """A candidate is 'covered' if every token of it is already a lexicon phrase
    token (so it adds no new vocabulary) — those are hidden from the candidate list."""
    return all(w in phrase_words for w in term.split())


# ------------------------------------------------------------------- signals

def facet_doc_ids(con, tag):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT doc_id FROM lobbying_issue_mentions WHERE tag=?",
        [tag]).fetchall()]


def counts_for(con, doc_ids=None, sample=None):
    """n-gram document-frequency Counter over a doc set (by ids) or a random
    background sample. Document-frequency (a term counts once per doc) so a single
    verbose filing can't dominate."""
    if doc_ids is not None:
        con.execute("CREATE OR REPLACE TEMP TABLE _d(id BIGINT)")
        con.executemany("INSERT INTO _d VALUES (?)", [(i,) for i in doc_ids])
        rows = con.execute("SELECT lf.txt FROM lobbying_freetext lf "
                           "JOIN _d ON _d.id = lf.doc_id").fetchall()
    else:
        rows = con.execute("SELECT txt FROM lobbying_freetext "
                           f"USING SAMPLE {int(sample)} ROWS (reservoir, 42)").fetchall()
    c = Counter()
    for (txt,) in rows:
        c.update(set(ngrams(tokens(txt or ""))))
    return c, len(rows)


def keyness(target, n_target, bg, n_bg, phrase_words, top):
    """Monroe et al. log-odds-with-informative-Dirichlet-prior z-scores. Ranks
    terms most over-represented in the target vs background. Candidate terms only
    (>= 8 target docs, not already lexicon-covered)."""
    vocab = set(t for t, c in target.items() if c >= 8)
    a0 = sum(bg.values()) + len(bg)
    out = []
    for t in vocab:
        if covered(t, phrase_words):
            continue
        yw = target[t]
        yb = bg.get(t, 0)
        ai = bg.get(t, 0) + 1  # informative prior from background
        # log-odds-ratio with prior, and its variance (Monroe 2008 eq. 20-22)
        l_t = math.log((yw + ai) / (n_target + a0 - yw - ai))
        l_b = math.log((yb + ai) / (n_bg + a0 - yb - ai))
        delta = l_t - l_b
        var = 1.0 / (yw + ai) + 1.0 / (yb + ai)
        z = delta / math.sqrt(var)
        out.append((z, t, yw, yb))
    out.sort(reverse=True)
    return out[:top]


def emergence(con, tag, terms, top):
    """Per-year document frequency of terms within the facet-tagged docs."""
    ids = facet_doc_ids(con, tag)
    con.execute("CREATE OR REPLACE TEMP TABLE _d(id BIGINT)")
    con.executemany("INSERT INTO _d VALUES (?)", [(i,) for i in ids])
    rows = con.execute("""
        SELECT lf.doc_id, lf.dataset, lf.record_key, lf.txt FROM lobbying_freetext lf
        JOIN _d ON _d.id = lf.doc_id""").fetchall()
    # map doc -> year via the filing tables
    yr = {}
    for ds, rk, y in con.execute("""
            SELECT 'senate', filing_uuid, filing_year FROM senate_filings
            UNION ALL SELECT 'house', filing_id, report_year FROM house_filings"""
                                 ).fetchall():
        yr[(ds, rk)] = y
    years = sorted({y for y in yr.values() if y})
    per = {t: Counter() for t in terms}
    for doc_id, ds, rk, txt in rows:
        y = yr.get((ds, rk))
        if not y:
            continue
        toks = set(ngrams(tokens(txt or "")))
        for t in terms:
            if t in toks:
                per[t][y] += 1
    return years, per


def fts_search(con, query, top):
    con.execute("LOAD fts;")
    return con.execute(f"""
        SELECT dataset, record_key, issue_code, left(txt, 88) AS snippet, score
        FROM (SELECT *, fts_main_lobbying_freetext.match_bm25(doc_id, ?) AS score
              FROM lobbying_freetext) WHERE score IS NOT NULL
        ORDER BY score DESC LIMIT ?""", [query, top]).fetchall()


def untagged_terms(con, tag, seed, bg, n_bg, phrase_words, top):
    """Docs FTS-matching seed but NOT facet-tagged -> keyness of that residual, the
    vocabulary the current lexicon misses."""
    con.execute("LOAD fts;")
    ids = [r[0] for r in con.execute(f"""
        SELECT doc_id FROM (
          SELECT doc_id, fts_main_lobbying_freetext.match_bm25(doc_id, ?) s
          FROM lobbying_freetext) WHERE s IS NOT NULL
        AND doc_id NOT IN (SELECT doc_id FROM lobbying_issue_mentions WHERE tag=?)
        """, [seed, tag]).fetchall()]
    if not ids:
        return [], 0
    tgt, n = counts_for(con, doc_ids=ids)
    return keyness(tgt, n, bg, n_bg, phrase_words, top), n


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="db/lda_full.duckdb")
    ap.add_argument("--lexicon",
                    default=str(Path(__file__).with_name("industry_lexicon.json")))
    ap.add_argument("--facet", default="crypto")
    ap.add_argument("--emergence", action="store_true")
    ap.add_argument("--untagged")
    ap.add_argument("--search")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--bg", type=int, default=120000)
    args = ap.parse_args()

    meta, facet = load_lexicon(args.lexicon, args.facet)
    tag = facet["tag"]
    phrase_words = set(w for p in facet["phrases"] for w in p.lower().split())
    con = duckdb.connect(args.db, read_only=True)

    if args.search:
        print(f"FTS/BM25 search over lobbying_freetext: {args.search!r}\n")
        for ds, rk, code, snip, sc in fts_search(con, args.search, args.top):
            print(f"  {sc:5.2f}  [{ds:6} {code or '·':4}] {rk[:16]:16}  {snip}")
        con.close()
        return

    print(f"lobbying free-text discovery · facet {facet['id']} (tag {tag}) · "
          f"lexicon v{meta['version']}")
    bg, n_bg = counts_for(con, sample=args.bg)

    if args.untagged:
        cands, n = untagged_terms(con, tag, args.untagged, bg, n_bg,
                                  phrase_words, args.top)
        print(f"\nUNTAGGED-SET MINING · docs matching {args.untagged!r} but NOT "
              f"{tag}-tagged: {n:,} docs")
        print("candidate terms the current lexicon misses (z-score, target/bg docs):")
        for z, t, yw, yb in cands:
            print(f"  {z:6.1f}  {t:32}  {yw:>5} / {yb:>5}")
        con.close()
        return

    tgt_ids = facet_doc_ids(con, tag)
    tgt, n_tgt = counts_for(con, doc_ids=tgt_ids)
    cands = keyness(tgt, n_tgt, bg, n_bg, phrase_words, args.top)
    print(f"\nKEYNESS · {n_tgt:,} {tag}-tagged docs vs {n_bg:,} background docs")
    print("candidate vocabulary NOT yet in the lexicon (log-odds z, target/bg docs):")
    print("  triage: --search a term to check precision, then a human adds it to "
          "industry_lexicon.json")
    for z, t, yw, yb in cands:
        print(f"  {z:6.1f}  {t:32}  {yw:>5} / {yb:>5}")

    if args.emergence:
        terms = [t for _, t, _, _ in cands[:15]]
        years, per = emergence(con, tag, terms, args.top)
        print(f"\nEMERGENCE · per-year doc frequency of top candidates "
              f"(years {years[0]}-{years[-1]}):")
        print("  " + " " * 32 + "  " + "  ".join(f"{y}" for y in years))
        for t in terms:
            print(f"  {t:32}  " + "  ".join(f"{per[t].get(y,0):>4}" for y in years))
    con.close()


if __name__ == "__main__":
    main()
