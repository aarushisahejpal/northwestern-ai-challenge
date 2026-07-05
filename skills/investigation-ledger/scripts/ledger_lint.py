#!/usr/bin/env python3
"""Schema lint for LEDGER.md — keeps the investigation ledger machine-checkable.

Checks:
  * All four sections present (Leads / Entities checked / Queries run / Cold threads)
  * Leads table has the required columns in order
  * Lead ids are unique and match L\\d+
  * Status values are from the allowed set
  * Cold-thread rows reference existing lead ids
  * Rows that are pure template placeholders ("—") are ignored

Exit code 0 = clean, 1 = violations (printed).
"""

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = ["## Leads", "## Entities checked", "## Queries run", "## Cold threads"]
LEAD_COLUMNS = ["id", "hypothesis (one line)", "lens", "named actors", "status",
                "owner", "evidence so far (record IDs)", "next action", "updated"]
STATUSES = {"open", "triaged", "investigating", "verified", "dead", "parked"}


def table_rows(text, heading):
    """Rows of the first pipe table after `heading`: list of cell lists."""
    m = re.search(re.escape(heading) + r".*?\n((?:\|.*\n)+)", text)
    if not m:
        return None, []
    lines = [l for l in m.group(1).strip().splitlines() if l.strip().startswith("|")]
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
    header = rows[0] if rows else []
    body = [r for r in rows[2:] if any(c not in ("", "—", "-") for c in r)]
    return header, body


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "LEDGER.md")
    if not path.exists():
        sys.exit(f"not found: {path}")
    text = path.read_text(encoding="utf-8")
    problems = []

    for s in REQUIRED_SECTIONS:
        if s not in text:
            problems.append(f"missing section: {s}")

    header, leads = table_rows(text, "## Leads")
    if header is not None and [h.lower() for h in header] != LEAD_COLUMNS:
        problems.append(f"Leads columns are {header!r}, expected {LEAD_COLUMNS!r}")

    ids = []
    for r in leads:
        if len(r) != len(LEAD_COLUMNS):
            problems.append(f"lead row has {len(r)} cells, expected {len(LEAD_COLUMNS)}: {r[:2]}")
            continue
        lead_id, status = r[0], r[4]
        if not re.fullmatch(r"L\d+", lead_id):
            problems.append(f"bad lead id: {lead_id!r}")
        if lead_id in ids:
            problems.append(f"duplicate lead id: {lead_id}")
        ids.append(lead_id)
        if status.lower() not in STATUSES:
            problems.append(f"{lead_id}: bad status {status!r} (allowed: {sorted(STATUSES)})")

    _, cold = table_rows(text, "## Cold threads")
    for r in cold:
        if r and r[0] not in ids and re.fullmatch(r"L\d+", r[0] or ""):
            problems.append(f"cold thread references unknown lead: {r[0]}")

    if problems:
        print(f"LEDGER LINT: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print(f"LEDGER LINT: clean ({len(ids)} leads, {len(cold)} cold threads)")


if __name__ == "__main__":
    main()
