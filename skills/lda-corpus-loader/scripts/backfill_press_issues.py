#!/usr/bin/env python3
"""Populate press_issue_mentions in an already-built DB, without a full rebuild.

The issue tagging depends only on press_releases.text + its stored raw-record
pointer (pr_id, src_file, src_line) — all already in the DB. So rather than
re-parse the 8 GB raw corpus, this reuses the SAME extract_issues() that
build_db.py runs inside load_press, applied to the stored text. The result is
byte-identical to what a from-scratch `build_db.py` would have written (same
function, same text, same pointers), it just skips re-loading Senate/House.

Idempotent: recreates the table/view schema (IF NOT EXISTS / OR REPLACE), clears
press_issue_mentions, and repopulates. Safe to run repeatedly.

Usage:
  python backfill_press_issues.py --db db/lda_full.duckdb
"""

import argparse
import importlib.util
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent

# Import build_db as a module so the keyword mapping has exactly one home.
_spec = importlib.util.spec_from_file_location("build_db", HERE / "build_db.py")
build_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_db)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=Path("db/lda.duckdb"))
    ap.add_argument("--batch", type=int, default=20000, help="press rows per fetch")
    args = ap.parse_args()
    if not args.db.exists():
        sys.exit(f"db not found: {args.db}")

    con = duckdb.connect(str(args.db))

    # Ensure the table exists and the press view is defined (both idempotent).
    for stmt in build_db.DDL.split(";"):
        if "press_issue_mentions" in stmt and stmt.strip():
            con.execute(stmt)
    for stmt in build_db.VIEWS.split(";"):
        if "v_press_issue_quarter" in stmt and stmt.strip():
            con.execute(stmt)

    con.execute("DELETE FROM press_issue_mentions")

    total_press = con.execute("SELECT count(*) FROM press_releases").fetchone()[0]
    max_id = con.execute("SELECT max(pr_id) FROM press_releases").fetchone()[0] or 0
    sink = build_db.Sink(con)
    # Page by pr_id range and fully materialize each page (fetchall). The Sink's
    # batched COPY runs on `con`; holding an open cursor across it would invalidate
    # the cursor, so no result cursor may be live while rows are being added.
    n_docs = n_rows = 0
    lo = 0
    while lo <= max_id:
        rows = con.execute(
            "SELECT pr_id, text, src_file, src_line FROM press_releases "
            "WHERE pr_id > ? AND pr_id <= ?", [lo, lo + args.batch]).fetchall()
        for pr_id, text, src_file, src_line in rows:
            n_docs += 1
            for code, kw in build_db.extract_issues(text or ""):
                sink.add("press_issue_mentions",
                         (pr_id, code, kw, src_file, src_line))
                n_rows += 1
        lo += args.batch
        print(f"  {n_docs:,}/{total_press:,} releases -> {n_rows:,} mentions",
              end="\r", flush=True)
    sink.flush()
    print()

    codes = con.execute("SELECT count(DISTINCT issue_code) FROM press_issue_mentions").fetchone()[0]
    tagged = con.execute("SELECT count(DISTINCT pr_id) FROM press_issue_mentions").fetchone()[0]
    print(f"Done: {n_rows:,} mention rows across {codes} issue codes; "
          f"{tagged:,}/{total_press:,} releases tagged ({tagged/total_press:.0%}).")
    con.close()


if __name__ == "__main__":
    main()
