#!/usr/bin/env python3
"""Print the raw record behind any citation key, straight from the raw corpus.

This is the one-step path from a cited claim to its source record — for evaluators
reviewing findings, and the ONLY sanctioned way agents access raw corpus records.

Key formats:
  Senate filing/contribution : the filing_uuid, e.g. 4f33e46d-4018-4899-8926-c03bb9977ae2
  House filing               : the numeric XML filename, e.g. 301817772
  Press release              : src_file:src_line, e.g. congress_press/2026-01.jsonl:12

Usage:
  python show_record.py <key> [--data-root data/] [--db db/lda.duckdb]

With the DB present, Senate lookups use the stored raw-record pointer (fast).
Without it, the year files are scanned (slow but dependency-free beyond ijson).
"""

import argparse
import json
import re
import sys
from pathlib import Path

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

# Records contain curly quotes etc.; Windows pipes default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def show_press(data_root, key):
    src, _, line_no = key.rpartition(":")
    path = data_root / src
    if not path.exists():
        sys.exit(f"press source file not found: {path}")
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if i == int(line_no):
                print(json.dumps(json.loads(line), indent=2, ensure_ascii=False))
                return
    sys.exit(f"line {line_no} not found in {path}")


def show_house(data_root, key):
    house = data_root / "house"
    for d in sorted(house.iterdir()):
        p = d / f"{key}.xml"
        if p.exists():
            print(f"# {p.relative_to(data_root).as_posix()}")
            print(p.read_text(encoding="utf-8", errors="replace"))
            return
    sys.exit(f"no {key}.xml under {house}/*/")


def _stream_index(path, index):
    import ijson
    with open(path, "rb") as f:
        for i, rec in enumerate(ijson.items(f, "item")):
            if i == index:
                return rec
    return None


def show_senate(data_root, key, db_path):
    # Fast path: use the DB's raw-record pointer.
    if db_path and db_path.exists():
        import duckdb
        con = duckdb.connect(str(db_path), read_only=True)
        for table in ("senate_filings", "senate_contributions"):
            row = con.execute(
                f"SELECT src_file, src_index FROM {table} WHERE filing_uuid = ?",
                [key]).fetchone()
            if row:
                rec = _stream_index(data_root / row[0], row[1])
                if rec and rec.get("filing_uuid") != key:
                    sys.exit(f"pointer mismatch for {key} — rebuild the DB "
                             f"(expected at {row[0]}[{row[1]}])")
                print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))
                return
    # Slow path: scan every senate year file.
    import ijson
    for path in sorted((data_root / "senate").glob("*/*/*.json")):
        with open(path, "rb") as f:
            for rec in ijson.items(f, "item"):
                if rec.get("filing_uuid") == key:
                    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))
                    return
    sys.exit(f"filing_uuid {key} not found in senate data")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key")
    ap.add_argument("--data-root", type=Path, default=Path("data"))
    ap.add_argument("--db", type=Path, default=Path("db/lda.duckdb"))
    args = ap.parse_args()

    if not args.data_root.exists():
        sys.exit(f"data root not found: {args.data_root}")
    if UUID_RE.match(args.key):
        show_senate(args.data_root, args.key.lower(), args.db)
    elif args.key.isdigit():
        show_house(args.data_root, args.key)
    elif ".jsonl:" in args.key:
        show_press(args.data_root, args.key)
    else:
        sys.exit("unrecognized key format — see --help")


if __name__ == "__main__":
    main()
