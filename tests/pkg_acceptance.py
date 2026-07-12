"""Acceptance + regression harness for the industry-review-packager skill.

Default run (fast, no DB writes):
    .venv/Scripts/python tests/pkg_acceptance.py
  1. critical-minerals package integrity — required files present, internal
     chart-vs-click-through reconciliation re-verified from the shipped CSVs,
     BATT Coalition variants present on the map, roster round-trips exist.
  2. lexicon guard — CRYPTO / PARDONS serving-table slices at their frozen
     row counts (the v1.2 CRITMIN addition must not disturb them).

Full regression (regenerates packages into a temp root; several minutes):
    .venv/Scripts/python tests/pkg_acceptance.py --regen pardons
    .venv/Scripts/python tests/pkg_acceptance.py --regen pardons crypto healthcare
  Regenerates each named package with lda_package_industry.py into its own
  scratch root and compares data CSVs against the committed package:
    byte-identical, or content-identical under canonicalization (sorted rows;
    matched_keywords order normalized; shared columns when the skill's
    standardized shape is a superset of the legacy one). Files in a package's
    TIE_EXEMPT set (legacy exports without deterministic tiebreakers: QA
    samples, LIMIT-boundary lists, roster-derived giving) pass on row-count +
    column equality. Passthrough files are skipped (not skill outputs).
"""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "industry-review-packager"
FAIL = []


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


def rd(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def dictrd(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- test 1
def test_critical_minerals():
    print("\n== 1. critical-minerals package (acceptance test 1 — serves L024)")
    pkg = REPO / "out" / "packages" / "critical-minerals"
    data = pkg / "data"
    required = ["critmin_players.csv", "critmin_player_filings.csv",
                "critmin_quarterly_trend.csv", "critmin_trend_filings.csv",
                "critmin_issue_code_scatter.csv", "critmin_keywords.csv",
                "critmin_registrant_firms.csv", "critmin_press_quarterly.csv",
                "critmin_press_releases.csv", "critmin_record_samples_qa.csv",
                "critmin_spend_quarters.csv", "critmin_bills.csv",
                "critmin_ld203_by_org.csv", "critmin_ld203_recipients.csv",
                "critmin_ld203_by_year.csv", "critmin_ld203_member_rollup.csv"]
    missing = [f for f in required if not (data / f).exists()]
    check("all 16 data CSVs present", not missing, str(missing))
    check("dashboard present", (pkg / "critical-minerals_dashboard.html").exists())
    check("README present", (pkg / "README.md").exists())
    check("zip present", bool(list(pkg.glob("critical-minerals_package_*.zip"))))
    check("roster present", (REPO / "out" / "critical-minerals_roster.txt").exists())
    if missing:
        return
    # reconciliation re-verified from the shipped files (the build gates on
    # these; re-checking proves the shipped artifact, not just the build log)
    players = dictrd(data / "critmin_players.csv")
    pf = dictrd(data / "critmin_player_filings.csv")
    per = {}
    for r in pf:
        per.setdefault(r["player"], set()).add(r["filing_uuid"])
    bad = [p["player"] for p in players
           if int(p["critmin_filings_senate"]) != len(per.get(p["player"], ()))]
    check("players == raw-filing index per player", not bad, f"{len(bad)} mismatches")
    tr = dictrd(data / "critmin_quarterly_trend.csv")
    tf = dictrd(data / "critmin_trend_filings.csv")
    perq = {}
    for r in tf:
        k = (r["filing_year"], r["filing_period"])
        perq[k] = perq.get(k, 0) + 1
    bad = [r for r in tr if int(r["critmin_filings"]) != perq.get((r["filing_year"], r["filing_period"]), 0)]
    check("trend == click-through per quarter", not bad, f"{len(bad)} mismatches")
    pq = dictrd(data / "critmin_press_quarterly.csv")
    prl = dictrd(data / "critmin_press_releases.csv")
    perq = {}
    for r in prl:
        perq[r["quarter"]] = perq.get(r["quarter"], 0) + 1
    bad = [r for r in pq if int(r["critmin_releases"]) != perq.get(r["quarter"], 0)]
    check("press == release list per quarter", not bad, f"{len(bad)} mismatches")
    # L024: the BATT Coalition variants must be on the map
    names = " | ".join(p["player"].upper() for p in players)
    check("BATT variants on the map",
          "BATTERY MATERIALS AND TECHNOLOGY COALITION" in names
          and "BATTERY ADVOCACY FOR TECHNOLOGY TRANSFORMATION" in names)
    # money-tool round-trip: giving leg produced rows for the roster
    by_year = dictrd(data / "critmin_ld203_by_year.csv")
    check("giving leg round-trips (by_year rows)", len(by_year) >= 3)


# ---------------------------------------------------------------- test 2
def test_lexicon_guard():
    print("\n== 2. lexicon v1.2 guard — CRYPTO/PARDONS slices frozen")
    try:
        import duckdb
    except ImportError:
        check("duckdb importable", False)
        return
    db = REPO / "db" / "lda_full.duckdb"
    if not db.exists():
        print("  [skip] db/lda_full.duckdb not present")
        return
    con = duckdb.connect(str(db), read_only=True)
    for tag, want_rows, want_filings in (("CRYPTO", 30922, 9768), ("PARDONS", 576, 366)):
        n, f = con.execute(
            "SELECT count(*), count(DISTINCT record_key) FROM lobbying_issue_mentions "
            "WHERE tag=?", [tag]).fetchone()
        check(f"{tag} slice frozen", (n, f) == (want_rows, want_filings),
              f"rows={n} filings={f} (want {want_rows}/{want_filings})")
    n = con.execute("SELECT count(DISTINCT record_key) FROM lobbying_issue_mentions "
                    "WHERE tag='CRITMIN'").fetchone()[0]
    check("CRITMIN slice exists", n > 10000, f"{n} filings")
    con.close()


# ------------------------------------------------------------ regression
# Files whose LEGACY export had no deterministic tiebreaker (tie membership /
# tie order can differ from the committed baseline): pass on rows+columns.
TIE_EXEMPT = {
    "pardons": {"pardons_record_samples_qa.csv"},
    "crypto": {"crypto_record_samples_qa.csv", "crypto_registrant_firms.csv",
               "crypto_trend_filings.csv"},
    "healthcare": {"hc_record_samples_qa.csv", "hc_players.csv",
                   # roster-derived: 7-way tie at 51 filings for the last 3
                   # top-150 roster slots changes giving membership
                   "hc_ld203_by_org.csv", "hc_ld203_recipients.csv",
                   "hc_ld203_by_year.csv"},
}


def canon(cols, rows):
    if "matched_keywords" in cols:
        i = cols.index("matched_keywords")
        rows = [r[:i] + ["; ".join(sorted(r[i].split("; ")))] + r[i + 1:] for r in rows]
    if "title" in cols:
        # legacy pardons press export truncated titles to 140 chars
        i = cols.index("title")
        rows = [r[:i] + [r[i][:140]] + r[i + 1:] for r in rows]
    if "declared_text_sample" in cols:
        # convenience sample column; legacy export picked it with any_value()
        # (nondeterministic) — the skill now uses min(), so exclude from compare
        i = cols.index("declared_text_sample")
        rows = [r[:i] + r[i + 1:] for r in rows]
    return sorted(map(tuple, rows))


def regen_and_compare(pkg_id):
    print(f"\n== regression: {pkg_id} (regenerating — takes a few minutes)")
    spec = SKILL / "specs" / f"{pkg_id}.json"
    s = json.loads(spec.read_text(encoding="utf-8"))
    passthrough = set(s.get("passthrough", []))
    with tempfile.TemporaryDirectory(prefix=f"pkg_regen_{pkg_id}_") as td:
        r = subprocess.run([sys.executable,
                            str(SKILL / "scripts" / "lda_package_industry.py"),
                            str(spec), "--out-root", td,
                            "--skip-dashboard", "--skip-zip"],
                           capture_output=True, text=True, encoding="utf-8",
                           cwd=str(REPO))
        check(f"{pkg_id}: generator exit 0", r.returncode == 0, r.stderr[-300:])
        if r.returncode != 0:
            return
        base = REPO / "out" / "packages" / pkg_id / "data"
        regen = Path(td) / pkg_id / "data"
        exempt = TIE_EXEMPT.get(pkg_id, set())
        n_byte = n_content = n_exempt = 0
        for f in sorted(base.glob("*.csv")):
            g = regen / f.name
            if f.name in passthrough:
                continue
            if not g.exists():
                check(f"{pkg_id}: {f.name} regenerated", False, "missing")
                continue
            if f.read_bytes() == g.read_bytes():
                n_byte += 1
                continue
            bc, br = rd(f)
            rc, rr = rd(g)
            shared = [c for c in bc if c in rc]
            bi = [bc.index(c) for c in shared]
            ri = [rc.index(c) for c in shared]
            eq = canon(shared, [[row[i] for i in bi] for row in br]) == \
                canon(shared, [[row[i] for i in ri] for row in rr])
            if eq:
                n_content += 1
            elif f.name in exempt and len(br) == len(rr) and set(bc) <= set(rc):
                n_exempt += 1
            else:
                cb = canon(shared, [[row[i] for i in bi] for row in br])
                cr2 = canon(shared, [[row[i] for i in ri] for row in rr])
                diffs = [(a, b) for a, b in zip(cb, cr2) if a != b][:1]
                check(f"{pkg_id}: {f.name} reconciles", False,
                      f"rows {len(br)} vs {len(rr)}"
                      + (f"; first diff B={[str(v)[:28] for v in diffs[0][0]]} "
                         f"R={[str(v)[:28] for v in diffs[0][1]]}" if diffs else ""))
        new = [g.name for g in regen.glob("*.csv") if not (base / g.name).exists()]
        check(f"{pkg_id}: baseline reconciles",
              not FAIL or all(pkg_id not in x for x in FAIL),
              f"{n_byte} byte-identical, {n_content} content-identical, "
              f"{n_exempt} tie-exempt (rows+cols), additions: {new}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regen", nargs="*", default=None,
                    help="also regenerate + compare these packages (pardons/crypto/healthcare)")
    args = ap.parse_args()
    test_critical_minerals()
    test_lexicon_guard()
    for pkg in (args.regen or []):
        regen_and_compare(pkg)
    print()
    if FAIL:
        print(f"FAILED: {len(FAIL)} check(s): {FAIL}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
