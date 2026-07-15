#!/usr/bin/env python3
"""Semantic (embedding) discovery search over lobbying free-text.

DISCOVERY ONLY — same posture as the FTS/BM25 layer this complements: results
propose vocabulary (for industry_lexicon.json) and leads; findings cite records
via the deterministic keyword serving tables, never via embedding similarity.
Every hit resolves to raw filings via show_record.py <record_key>.

Reads the tables embed_corpus.py builds (lobbying_text_embeddings +
lobbying_text_map). Search runs entirely in DuckDB (brute-force cosine over
FLOAT[dim] arrays — sub-second at 388K vectors); the embedding model is only
loaded to embed --query text, so --like needs no model at all.

Usage:
  python lda_semantic_search.py --query "pharmacy middlemen taking a cut of drug prices"
  python lda_semantic_search.py --query "..." --compare-bm25       # side-by-side vs FTS
  python lda_semantic_search.py --like <filing_uuid|house_id>      # neighbors of a filing
  python lda_semantic_search.py --query "..." -k 25 --db db/lda_full.duckdb
"""

import argparse
import sys
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

REPO = Path(__file__).resolve().parents[3]
DEFAULT_DB = REPO / "db" / "lda_full.duckdb"

# One row per distinct text, with the doc rows folded in: how many filings use
# this text, an example citable key, and the client names behind it (senate).
HIT_SQL = """
WITH scored AS (
  SELECT e.txt_hash, array_cosine_similarity(e.vector, CAST(? AS FLOAT[{dim}])) AS score
  FROM lobbying_text_embeddings e
  ORDER BY score DESC LIMIT {k}
)
SELECT s.score,
       any_value(f.txt) AS txt,
       count(DISTINCT f.record_key) AS n_filings,
       min(f.record_key) AS example_key,
       string_agg(DISTINCT sf.client_name, '; ') AS clients
FROM scored s
JOIN lobbying_text_map m USING (txt_hash)
JOIN lobbying_freetext f USING (doc_id)
LEFT JOIN senate_filings sf ON f.dataset = 'senate' AND sf.filing_uuid = f.record_key
GROUP BY s.txt_hash, s.score
ORDER BY s.score DESC
"""


def query_vector(con, args):
    if args.like:
        # Mean of the record's own stored vectors — no model load needed.
        rows = con.execute("""
            SELECT DISTINCT e.txt_hash, e.vector
            FROM lobbying_text_embeddings e
            JOIN lobbying_text_map m USING (txt_hash)
            JOIN lobbying_freetext f USING (doc_id)
            WHERE f.record_key = ?""", [args.like]).fetchall()
        if not rows:
            sys.exit(f"record {args.like!r} has no embedded text (not found in "
                     "lobbying_freetext, or embed_corpus.py ran with --limit)")
        import numpy as np
        v = np.mean([r[1] for r in rows], axis=0)
        v /= np.linalg.norm(v) or 1.0
        return v.tolist()
    model_name = con.execute(
        "SELECT any_value(model) FROM lobbying_text_embeddings").fetchone()[0]
    sys.path.insert(0, str(REPO / "skills" / "lda-corpus-loader" / "scripts"))
    from embed_corpus import load_model, encode
    model, cfg, _ = load_model(model_name)
    return encode(model, cfg, [args.query], is_query=True)[0].tolist()


def show_bm25(con, query, k):
    con.execute("LOAD fts")
    rows = con.execute("""
        SELECT max(s) AS score, txt, count(DISTINCT record_key), min(record_key)
        FROM (SELECT fts_main_lobbying_freetext.match_bm25(doc_id, ?) AS s, *
              FROM lobbying_freetext) WHERE s IS NOT NULL
        GROUP BY txt ORDER BY score DESC LIMIT ?""", [query, k]).fetchall()
    print(f"\n--- BM25 (existing FTS discovery layer) top-{k} ---")
    for score, txt, n, key in rows:
        print(f"  {score:6.2f}  [{n} filing(s), e.g. {key}]  {' '.join(txt.split())[:110]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--query", help="free-text concept to search for")
    ap.add_argument("--like", metavar="RECORD_KEY",
                    help="find filings similar to this one (senate filing_uuid "
                         "or house xml filename); no model load required")
    ap.add_argument("-k", type=int, default=15)
    ap.add_argument("--compare-bm25", action="store_true",
                    help="also show what BM25 returns for --query")
    args = ap.parse_args()
    if bool(args.query) == bool(args.like):
        ap.error("exactly one of --query / --like")

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        con.execute("SELECT 1 FROM lobbying_text_embeddings LIMIT 1")
    except duckdb.CatalogException:
        sys.exit("no embeddings in this DB — run "
                 "skills/lda-corpus-loader/scripts/embed_corpus.py first")

    dim = con.execute("SELECT any_value(dim) FROM lobbying_text_embeddings").fetchone()[0]
    qv = query_vector(con, args)
    rows = con.execute(HIT_SQL.format(dim=dim, k=args.k), [qv]).fetchall()

    label = args.query or f"like:{args.like}"
    print(f"--- semantic top-{args.k} for {label!r} "
          f"(discovery only; resolve keys via show_record.py) ---")
    for score, txt, n, key, clients in rows:
        c = f"  <{clients[:60]}>" if clients else ""
        print(f"  {score:.3f}  [{n} filing(s), e.g. {key}]{c}")
        print(f"         {' '.join(txt.split())[:110]}")
    if args.compare_bm25 and args.query:
        show_bm25(con, args.query, args.k)


if __name__ == "__main__":
    main()
