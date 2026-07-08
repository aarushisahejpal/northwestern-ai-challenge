#!/usr/bin/env python3
"""Build the lobbying free-text search layer (lobbying_freetext + FTS index) in an
already-built DB, without a full corpus rebuild.

lobbying_freetext is derived entirely from senate_activities + house_alis, which are
already in the DB, so this reuses the SAME build_freetext_search() that build_db.py
runs in its index step, applied to the loaded tables. The result is identical to what
a from-scratch build_db.py would write; it just skips re-parsing the 8 GB raw corpus.

Idempotent (CREATE OR REPLACE TABLE + FTS overwrite=1). Safe to run repeatedly.

Usage:
  python add_lobbying_freetext.py --db db/lda_full.duckdb
"""

import argparse
import importlib.util
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent

# Import build_db as a module so the freetext/FTS logic has exactly one home.
_spec = importlib.util.spec_from_file_location("build_db", HERE / "build_db.py")
build_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_db)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=Path("db/lda.duckdb"))
    args = ap.parse_args()
    if not args.db.exists():
        sys.exit(f"db not found: {args.db}")

    con = duckdb.connect(str(args.db))
    print("Building lobbying_freetext + FTS index ...")
    n = build_db.build_freetext_search(con)
    by = con.execute("SELECT dataset, count(*) FROM lobbying_freetext "
                     "GROUP BY 1 ORDER BY 1").fetchall()
    con.close()
    print(f"Done: {n:,} free-text docs indexed  ("
          + ", ".join(f"{d}={c:,}" for d, c in by) + ").")
    print("FTS ready: fts_main_lobbying_freetext.match_bm25(doc_id, '<query>')")


if __name__ == "__main__":
    main()
