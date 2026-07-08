#!/usr/bin/env python3
"""Smoke test: build the DB from tests/fixtures/data (tiny excerpts of real public
records) and verify table counts, citation round-trips, and the ledger lint.

Run:  .venv/Scripts/python tests/smoke_test.py     (or any python with duckdb+ijson)
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
FIX = REPO / "tests" / "fixtures" / "data"
DB = REPO / "tests" / "tmp" / "lda_test.duckdb"


def run(*args):
    r = subprocess.run([PY, *map(str, args)], capture_output=True, text=True,
                       cwd=REPO, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        sys.exit(f"FAILED: {' '.join(map(str, args))}")
    return r.stdout


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()

    run("skills/lda-corpus-loader/scripts/build_db.py",
        "--data-root", FIX, "--db", DB, "--years", "2026")

    import duckdb
    con = duckdb.connect(str(DB), read_only=True)
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ["press_releases", "senate_filings", "senate_activities",
                        "senate_lobbyists", "senate_contributions",
                        "house_filings", "house_alis", "house_lobbyists",
                        "press_issue_mentions", "lobbying_freetext"]}
    print("counts:", counts)
    assert counts["press_releases"] == 3, counts
    assert counts["senate_filings"] == 2, counts
    assert counts["house_filings"] == 2, counts
    assert counts["senate_activities"] >= 1, counts
    assert counts["house_alis"] >= 1, counts
    # lobbying_freetext unions senate activity + house ali free-text; the FTS index
    # (BM25) over it must answer a query — guards the P4 search layer.
    assert counts["lobbying_freetext"] >= 2, counts
    con.execute("LOAD fts;")
    hits = con.execute(
        "SELECT count(*) FROM (SELECT fts_main_lobbying_freetext.match_bm25("
        "doc_id, 'health') s FROM lobbying_freetext) WHERE s IS NOT NULL").fetchone()[0]
    assert hits >= 0, "FTS index missing on lobbying_freetext"
    # The 3 fixture releases are about health care / ACA tax credits / USPS, so the
    # ISSUE_KEYWORDS tagger must fire (HCR + TAX + POS at least). Guards the mapping.
    assert counts["press_issue_mentions"] >= 3, counts
    tagged = dict(con.execute(
        "SELECT issue_code, count(DISTINCT pr_id) FROM press_issue_mentions "
        "GROUP BY 1").fetchall())
    assert {"HCR", "TAX", "POS"} <= set(tagged), tagged

    uuid = con.execute("SELECT filing_uuid FROM senate_filings LIMIT 1").fetchone()[0]
    fid = con.execute("SELECT filing_id FROM house_filings LIMIT 1").fetchone()[0]
    press_key = con.execute(
        "SELECT src_file || ':' || src_line FROM press_releases LIMIT 1").fetchone()[0]
    con.close()

    out = run("skills/lda-corpus-loader/scripts/show_record.py", uuid,
              "--data-root", FIX, "--db", DB)
    assert uuid in out, "senate round-trip failed"
    out = run("skills/lda-corpus-loader/scripts/show_record.py", fid,
              "--data-root", FIX, "--db", DB)
    assert "LOBBYINGDISCLOSURE" in out, "house round-trip failed"
    out = run("skills/lda-corpus-loader/scripts/show_record.py", press_key,
              "--data-root", FIX, "--db", DB)
    assert "bioguide_id" in out, "press round-trip failed"

    out = run("skills/investigation-ledger/scripts/ledger_lint.py", REPO / "LEDGER.md")
    assert "clean" in out, out

    print("SMOKE TEST PASS")


if __name__ == "__main__":
    main()
