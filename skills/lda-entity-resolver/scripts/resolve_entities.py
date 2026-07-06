#!/usr/bin/env python3
"""Build cross-dataset entity tables for the GAIN lobbying database.

Creates three tables inside an existing loader-built DuckDB:

  entities           one row per resolved entity (registrant / client / foreign_entity)
  entity_aliases     every raw name variant -> entity, with a sample raw-record pointer
  registrant_crosswalk
                     senate registrant+client engagement -> matched house filings,
                     via the House <senateID> compound key
                     "<senate_registrant_id>-<senate_client_id>" (verified against real
                     records 2026-07-06; sampled pairs agree on names). ID matches are
                     labeled confidence='id'; there is no fuzzy tier in this pass —
                     name-only candidates are reported, never silently merged.

Normalization (deterministic, in `norm_name` below): uppercase, strip whitespace,
drop parenthetical qualifiers ("MUBADALA INVESTMENT COMPANY (OWNS 24% OF CATURUS)"
-> "MUBADALA INVESTMENT COMPANY"), collapse punctuation to spaces, strip legal
suffixes (LLC/INC/LTD/...) repeatedly from the tail. The normalized key is stored on
every alias row so any grouping decision can be audited in SQL.

Senate-side entities carry their LDA numeric ids; House-side organizations (no UUIDs)
attach to senate entities only through the compound-key crosswalk, otherwise they
stay unresolved rather than fuzzy-merged (ambiguity is a report, not a merge).

Usage:
  python resolve_entities.py --db db/lda_pilot.duckdb            # build tables
  python resolve_entities.py --db db/lda_pilot.duckdb --report   # QA report only
"""

import argparse
import json
import os
import re
import sys
import tempfile

import duckdb

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LEGAL_SUFFIXES = {
    "LLC", "L L C", "INC", "INCORPORATED", "LTD", "LIMITED", "LLP", "L L P",
    "LP", "L P", "PLC", "CO", "CORP", "CORPORATION", "COMPANY", "PC", "PLLC",
    "SA", "S A", "AG", "GMBH", "NV", "N V", "BV", "B V", "PTY", "USA", "US",
}


def norm_name(raw):
    """Deterministic normalization key. Documented behavior; see module docstring."""
    if not raw:
        return None
    s = raw.upper().strip()
    s = re.sub(r"\([^)]*\)", " ", s)          # parenthetical qualifiers
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()  # punctuation -> spaces
    words = s.split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words) or None


DDL = """
CREATE OR REPLACE TABLE entities (
  entity_id TEXT, kind TEXT, canonical_name TEXT, norm_key TEXT,
  senate_id TEXT, n_aliases INTEGER, n_records INTEGER, sample_record TEXT);

CREATE OR REPLACE TABLE entity_aliases (
  entity_id TEXT, kind TEXT, raw_name TEXT, norm_key TEXT, dataset TEXT,
  senate_id TEXT, n_records INTEGER, sample_record TEXT);

CREATE OR REPLACE TABLE registrant_crosswalk (
  senate_registrant_id TEXT, senate_client_id TEXT,
  senate_registrant_name TEXT, senate_client_name TEXT,
  n_senate_filings INTEGER, n_house_filings INTEGER,
  sample_senate_uuid TEXT, sample_house_filing_id TEXT, confidence TEXT);
"""

# One source per (kind, dataset): raw name, senate numeric id when the dataset has
# one, and a raw-record pointer sample. Foreign entities have no LDA id -> norm key
# only.
SOURCES = {
    ("registrant", "senate"): """
      SELECT registrant_name AS raw_name, registrant_id AS senate_id,
             count(*) AS n_records, min(filing_uuid) AS sample_record
      FROM senate_filings WHERE registrant_name IS NOT NULL GROUP BY 1, 2""",
    ("client", "senate"): """
      SELECT client_name AS raw_name, client_id AS senate_id,
             count(*) AS n_records, min(filing_uuid) AS sample_record
      FROM senate_filings WHERE client_name IS NOT NULL GROUP BY 1, 2""",
    ("registrant", "house"): """
      SELECT organization_name AS raw_name, NULL AS senate_id,
             count(*) AS n_records, min(filing_id) AS sample_record
      FROM house_filings WHERE organization_name IS NOT NULL GROUP BY 1, 2""",
    ("client", "house"): """
      SELECT client_name AS raw_name, NULL AS senate_id,
             count(*) AS n_records, min(filing_id) AS sample_record
      FROM house_filings WHERE client_name IS NOT NULL GROUP BY 1, 2""",
    ("foreign_entity", "senate"): """
      SELECT name AS raw_name, NULL AS senate_id,
             count(*) AS n_records, min(filing_uuid) AS sample_record
      FROM senate_foreign_entities WHERE name IS NOT NULL GROUP BY 1, 2""",
}

ALIAS_COLS = ["entity_id", "kind", "raw_name", "norm_key", "dataset",
              "senate_id", "n_records", "sample_record"]


def build(con):
    for stmt in DDL.split(";"):
        if stmt.strip():
            con.execute(stmt)

    # Normalize in Python (no numpy/UDF dependency); stage via NDJSON + COPY,
    # same pattern as the loader's Sink.
    rows = []
    for (kind, dataset), sql in SOURCES.items():
        for raw_name, senate_id, n_records, sample in con.execute(sql).fetchall():
            key = norm_name(raw_name)
            if key:
                rows.append(dict(zip(ALIAS_COLS, (
                    None, kind, raw_name, key, dataset,
                    senate_id, n_records, sample))))
    fd, tmp = tempfile.mkstemp(suffix=".ndjson")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        con.execute(
            f"COPY entity_aliases FROM '{tmp.replace(chr(92), '/')}' (FORMAT json)")
    finally:
        os.unlink(tmp)

    # Entity id: senate numeric id where any alias in the (kind, norm_key) group
    # carries one (senate ids are authoritative), else the norm key. Kind is part of
    # the id so a firm that is both registrant and client stays two entities (they
    # play different roles; the crosswalk join is what links engagements).
    con.execute("""
      INSERT INTO entities
      WITH grouped AS (
        SELECT kind, norm_key, min(senate_id) AS senate_id,
               arg_max(raw_name, n_records) AS canonical_name,
               count(*) AS n_aliases, sum(n_records) AS n_records,
               min(sample_record) AS sample_record
        FROM entity_aliases GROUP BY 1, 2)
      SELECT kind || ':' || coalesce(senate_id, norm_key), kind, canonical_name,
             norm_key, senate_id, n_aliases, n_records, sample_record
      FROM grouped""")

    con.execute("""
      UPDATE entity_aliases a SET entity_id = (
        SELECT e.entity_id FROM entities e
        WHERE e.kind = a.kind AND e.norm_key = a.norm_key)""")

    # Engagement crosswalk on the verified compound key.
    con.execute("""
      INSERT INTO registrant_crosswalk
      WITH s AS (
        SELECT registrant_id, client_id,
               any_value(registrant_name) AS registrant_name,
               any_value(client_name) AS client_name,
               count(*) AS n_senate_filings, min(filing_uuid) AS sample_senate_uuid
        FROM senate_filings GROUP BY 1, 2),
      h AS (
        SELECT split_part(senate_reg_id, '-', 1) AS registrant_id,
               split_part(senate_reg_id, '-', 2) AS client_id,
               count(*) AS n_house_filings, min(filing_id) AS sample_house_filing_id
        FROM house_filings WHERE senate_reg_id LIKE '%-%' GROUP BY 1, 2)
      SELECT s.registrant_id, s.client_id, s.registrant_name, s.client_name,
             s.n_senate_filings, coalesce(h.n_house_filings, 0),
             s.sample_senate_uuid, h.sample_house_filing_id,
             CASE WHEN h.registrant_id IS NOT NULL THEN 'id' END
      FROM s LEFT JOIN h USING (registrant_id, client_id)""")


def report(con):
    print("# Entity crosswalk QA report\n")
    for kind, in con.execute("SELECT DISTINCT kind FROM entities ORDER BY 1").fetchall():
        n_e, n_a = con.execute(
            "SELECT count(*), sum(n_aliases) FROM entities WHERE kind=?", [kind]).fetchone()
        print(f"{kind}: {n_e:,} entities from {n_a:,} raw name variants")
    total, matched = con.execute("""
      SELECT count(*), count(sample_house_filing_id) FROM registrant_crosswalk""").fetchone()
    print(f"\nengagements (senate registrant+client pairs): {total:,}; "
          f"matched to house via compound senateID: {matched:,} ({matched/total:.1%})")
    print("\nAmbiguous clusters (same norm key, >1 senate id — NOT merged, listed for audit):")
    rows = con.execute("""
      SELECT norm_key, count(DISTINCT senate_id) AS n_ids,
             string_agg(DISTINCT senate_id, ', ') AS ids
      FROM entity_aliases
      WHERE senate_id IS NOT NULL
      GROUP BY norm_key HAVING count(DISTINCT senate_id) > 1
      ORDER BY n_ids DESC LIMIT 15""").fetchall()
    for r in rows:
        print(f"  {r[0][:60]:60s} ids: {r[2][:80]}")
    if not rows:
        print("  none")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="db/lda_pilot.duckdb")
    ap.add_argument("--report", action="store_true",
                    help="QA report only (tables must already exist)")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=args.report)
    if not args.report:
        build(con)
    report(con)
    con.close()


if __name__ == "__main__":
    main()
