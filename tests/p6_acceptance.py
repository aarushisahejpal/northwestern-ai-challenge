#!/usr/bin/env python3
"""P6 acceptance tests (person + political-committee resolver), per the kickoff
brief. Unlike tests/smoke_test.py (offline fixtures), this needs the REAL built
DB with the member layer (build_members.py) plus the three industry packages'
baseline CSVs — it is the regression harness the 2026-07-08 Emmer QA challenge
created.

Run:  .venv/Scripts/python tests/p6_acceptance.py
"""

import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = str(REPO / "db" / "lda_full.duckdb")
sys.path.insert(0, str(REPO / "skills" / "lda-entity-resolver" / "scripts"))
from member_resolve import MemberResolver  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

r = MemberResolver(DB)
failures = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        failures.append(label)


# 1 — Emmer round-trip: the five filed spellings + "Emmer for Congress" all
#     resolve to his bioguide with the right tiers; totals reconcile to the
#     2026-07-08 variant-audit baseline ($76,400 direct + $500 campaign)
print("== 1. Emmer round-trip ==")
spellings = ["REP. THOMAS EARL EMMER JR", "REP. THOMAS EARL EMMER, JR",
             "REP. THOMAS EARL EMMER", "REP. TOM EMMER", "TOM EMMER"]
for s in spellings:
    rep = r.resolve(s)
    check(f"{s!r} -> E000294 direct",
          [m["bioguide_id"] for m in rep["matches"]] == ["E000294"]
          and rep["matches"][0]["tier"] == "direct")
rep = r.resolve("Emmer for Congress")
check("'Emmer for Congress' -> E000294 campaign-committee",
      [m["bioguide_id"] for m in rep["matches"]] == ["E000294"]
      and rep["matches"][0]["tier"] == "campaign-committee")
aud = REPO / "out/packages/crypto/data/crypto_ld203_member_variant_audit_p6.csv"
if aud.exists():
    agg = defaultdict(float)
    for row in csv.DictReader(open(aud, encoding="utf-8-sig")):
        if "Emmer" in row["member"] and row["giver_slice"] == "crypto_native":
            agg[row["tier"]] += float(row["total"])
    check("crypto-native totals reconcile to the variant-audit baseline",
          agg["direct"] == 76400.0 and agg["campaign-committee"] == 500.0,
          f"direct=${agg['direct']:,.0f} campaign=${agg['campaign-committee']:,.0f}")
else:
    check("crypto p6 audit CSV present (run out/packages/_build/retrofit_p6.py)", False)

# 2 — departed members resolve from legislators-historical with NO hand-mapping
print("== 2. departed members (no hand-typed list) ==")
for name, bio in (("Pat Toomey", "T000461"), ("Patrick McHenry", "M001156"),
                  ("Sherrod Brown", "B000944")):
    rep = r.resolve(name)
    m = r.by_bio.get(bio)
    check(f"{name!r} -> {bio} via legislators-historical",
          [x["bioguide_id"] for x in rep["matches"]] == [bio]
          and m["src_file"] == "legislators-historical.json"
          and not m["is_current"])

# 3 — party annotation is date-aware across a mid-term switch
print("== 3. Sinema party-per-date ==")
d1, _ = r.party_at("S001191", "2022-06-15")
d2, _ = r.party_at("S001191", "2023-03-01")
check("2022-06 item annotates (D-AZ)", d1 == "D", f"got {d1}")
check("2023 item annotates (I-AZ)", d2 == "I", f"got {d2}")

# 4 — a JFC string reports its participants, shared & unallocated
print("== 4. JFC participants ==")
rep = r.resolve("MCCARTHY VICTORY FUND")
check("'MCCARTHY VICTORY FUND' -> participant(s), jfc-shared unallocated",
      rep["kind"] == "committee" and rep["matches"]
      and all(m["tier"] == "jfc-shared, unallocated" for m in rep["matches"]),
      "; ".join(m["name"] for m in rep["matches"]))
rep = r.resolve("Lummis Victory Committee")
check("'Lummis Victory Committee' (no FEC candidate linkage) -> name-inferred, "
      "flagged", rep["kind"] == "committee"
      and rep["matches"][0]["tier"] == "jfc-shared, unallocated"
      and rep["matches"][0]["confidence"] == "inferred")

# 5 — the three packages' giving splits regenerate with zero unexplained changes
print("== 5. package regression (retrofit_p6.py) ==")
out = subprocess.run([sys.executable,
                      str(REPO / "out/packages/_build/retrofit_p6.py")],
                     capture_output=True, text=True, encoding="utf-8", cwd=REPO)
tail = (out.stdout or "").strip().splitlines()[-1] if out.stdout else out.stderr
check("retrofit regression: zero unexplained changes",
      out.returncode == 0 and "PASS" in tail, tail)

print()
if failures:
    sys.exit(f"{len(failures)} acceptance test(s) FAILED: {failures}")
print("ALL P6 ACCEPTANCE TESTS PASS")
