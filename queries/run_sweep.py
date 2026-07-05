#!/usr/bin/env python3
"""Run every labeled block in queries/sweep_2026.sql against a DB and print
results as compact tables. Blocks are delimited by '-- ==== LABEL ===='.

Usage: python queries/run_sweep.py db/lda_2026.duckdb [BLOCK-PREFIX]
Optional BLOCK-PREFIX runs only blocks whose label starts with it (e.g. S2).
"""

import re
import sys
from pathlib import Path

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "db/lda_2026.duckdb"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    sql = (Path(__file__).parent / "sweep_2026.sql").read_text(encoding="utf-8")
    blocks = re.split(r"-- ==== (.+?) ====", sql)[1:]  # label, body, label, body...
    con = duckdb.connect(db, read_only=True)
    for label, body in zip(blocks[::2], blocks[1::2]):
        if only and not label.strip().startswith(only):
            continue
        print(f"\n{'=' * 78}\n{label.strip()}\n{'=' * 78}")
        stmt = body.strip().rstrip(";")
        try:
            rel = con.execute(stmt)
            cols = [d[0] for d in rel.description]
            rows = rel.fetchall()
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        widths = [min(48, max(len(str(c)), *(len(str(r[i])) for r in rows)))
                  if rows else len(str(c)) for i, c in enumerate(cols)]
        print(" | ".join(str(c)[:w].ljust(w) for c, w in zip(cols, widths)))
        for r in rows:
            print(" | ".join(str(v)[:w].ljust(w) if v is not None else "·".ljust(w)
                             for v, w in zip(r, widths)))
        print(f"({len(rows)} rows)")
    con.close()


if __name__ == "__main__":
    main()
