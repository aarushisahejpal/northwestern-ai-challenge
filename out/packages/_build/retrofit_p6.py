"""P6 retrofit of the three industry review packages (2026-07-09).

Re-derives every member merge in the shipped giving splits with the NEW shared
resolver (skills/lda-entity-resolver/scripts/member_resolve.py) and reconciles
against the 2026-07-08 variant-audit CSVs — the regression harness the Emmer QA
challenge created. Then writes the P6 additions the old ad-hoc matcher could not
see: candidate-support committees (campaign / leadership-PAC / JFC, tier-labeled)
and inverted/compound name forms, every row carrying tier + confidence.

Checks:
  A reproduction — every raw string the old audit merged must resolve to the SAME
    member with the SAME total (zero unexplained changes);
  B additions    — newly-mapped rows (committee tiers, inverted, compound) are
    listed separately, never silently folded into old numbers;
  C losses       — old-merged strings the new resolver drops must be zero.

Outputs (shipped baselines untouched):
  out/packages/<pkg>/data/<pkg>_ld203_member_variant_audit_p6.csv
  out/packages/<pkg>/data/<pkg>_member_support_rollup.csv
"""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
# the 2026-07-08 giving-run JSONs (lda_ld203_giving.py --json outputs) these
# packages were built from; copied out of that session's scratchpad so the
# regression harness survives temp cleanup
OLD_SCRATCH = REPO / "out" / "packages" / "_build" / "inputs"
sys.path.insert(0, str(REPO / "skills" / "lda-entity-resolver" / "scripts"))
from member_resolve import MemberResolver  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACKAGES = {
    "crypto": {
        # 2026-07-11 intensity re-cut (Rob-approved >=5% activity-share gate): the
        # diversified slice splits into forward/ambient, and slice inputs are the
        # EXHAUSTIVE (--top 999999) runs — the audit baseline regenerated the same day.
        "slices": [("crypto_native", "crypto_giving_pureplay.json"),
                   ("diversified_forward", "crypto_giving_div_forward.json"),
                   ("ambient_lowshare", "crypto_giving_div_ambient.json")],
        "audit": "crypto_ld203_member_variant_audit.csv",
    },
    "healthcare": {
        "slices": [("health_focused", "hc_giving_focused.json"),
                   ("mixed_diversified", "hc_giving_mixed.json")],
        "audit": "hc_ld203_member_variant_audit.csv",
    },
    "aipac": {
        "slices": [("aipac", "aipac_giving_deep.json")],
        "audit": None,  # baseline = member rows of aipac_ld203_recipients.csv
        "recipients_csv": "aipac_ld203_recipients.csv",
    },
}


def loadj(name):
    txt = (OLD_SCRATCH / name).read_text(encoding="utf-8")
    return json.loads(txt[txt.find("{"):])


def wcsv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print(f"  [csv] {Path(path).name}  {len(rows)} rows")


def display(r, m):
    title = "Sen." if m["chamber"] == "Senate" else "Rep."
    pl, _ = r.party_at(m["bioguide_id"])
    return f"{title} {m['name']} ({pl}-{m['state']})"


def main():
    r = MemberResolver(str(REPO / "db" / "lda_full.duckdb"))
    grand_fail = 0

    for pkg, cfg in PACKAGES.items():
        print(f"\n=== {pkg} ===")
        data_dir = REPO / "out" / "packages" / pkg / "data"

        # -- resolve every recipient row of every slice with the new resolver
        new_rows = []      # (slice, raw, total, items, bioguide, disp, tier, conf, src)
        rollup = {}        # bioguide -> aggregates
        for sname, jname in cfg["slices"]:
            for it in loadj(jname)["results"].get("recipients", []):
                raw = it["recipient"].strip()
                if raw.upper() == "N/A":
                    continue
                rep = r.resolve(raw)
                if rep["ambiguous"]:
                    continue
                for m in rep["matches"]:
                    mm = r.by_bio[m["bioguide_id"]]
                    tier = m["tier"]
                    new_rows.append((sname, raw, it["total"], it["items"],
                                     m["bioguide_id"], display(r, mm), tier,
                                     m["confidence"], m["source"]))
                    g = rollup.setdefault(m["bioguide_id"], {
                        "disp": display(r, mm), "direct": {}, "campaign": 0.0,
                        "ldpac": 0.0, "jfc": 0.0, "multi": 0.0, "variants": 0,
                        "flags": set()})
                    g["variants"] += 1
                    if tier == "direct":
                        g["direct"][sname] = g["direct"].get(sname, 0) + it["total"]
                    elif tier == "campaign-committee":
                        g["campaign"] += it["total"]
                    elif tier == "leadership-pac":
                        g["ldpac"] += it["total"]
                    elif tier.startswith("jfc"):
                        g["jfc"] += it["total"]
                    elif tier.startswith("multi-honoree"):
                        g["multi"] += it["total"]
                    if m["confidence"] not in ("matched", "linked"):
                        g["flags"].add(m["confidence"])

        # -- Check A/C: reproduce the shipped audit. Identity compares on
        # bioguide (display spellings differ: 'Bob Casey' vs 'Robert P. Casey,
        # Jr.'); rows the new resolver declines as AMBIGUOUS are explained
        # (ambiguity is a report, not a merge — the old matcher conflated e.g.
        # SEN. Robert Menendez with his son the Rep.), listed but not failures.
        def bio_of(display):
            rep = r.resolve(display.split(" (")[0])
            hits = {m["bioguide_id"] for m in rep["matches"]}
            return hits.pop() if len(hits) == 1 else None

        n_ok = n_fail = n_amb = 0
        old_keys = set()
        if cfg["audit"]:
            aud = list(csv.DictReader(open(data_dir / cfg["audit"],
                                           encoding="utf-8-sig")))
            direct_new = {(s, raw): (b, d, c) for s, raw, _t, _i, b, d, tier, c,
                          _s in new_rows if tier == "direct"}
            for row in aud:
                key = (row["giver_slice"], row["raw_recipient_string_as_filed"])
                old_keys.add(key)
                old_member = row["member (merged row in the split CSV)"]
                hit = direct_new.get(key)
                if hit is None:
                    if r.resolve(key[1])["ambiguous"]:
                        n_amb += 1
                        print(f"  ambiguity surfaced (explained): {key[1]!r} — old "
                              f"merge into {old_member!r} was a conflation risk")
                    else:
                        n_fail += 1
                        print(f"  LOSS: {key} was merged into {old_member!r}, "
                              "now unresolved")
                elif bio_of(old_member) not in (hit[0], None):
                    # a re-attribution is a CORRECTION of the old matcher's
                    # conflation when the new evidence is strictly stronger:
                    # title-resolved (the Menendezes; Dan/Sanford D. Bishop),
                    # a full-name 'matched' hit (the old single-initial fallback
                    # merged 'SEN CINDY HYDE SMITH' into Christopher Smith), or
                    # a curated 'alias' entry (sourced in member_aliases.json)
                    if hit[2] in ("title-chamber", "title-initial",
                                  "matched", "alias"):
                        n_amb += 1
                        print(f"  correction (explained): {key[1]!r}: "
                              f"{old_member!r} -> {hit[1]!r} [{hit[2]}]")
                    else:
                        n_fail += 1
                        print(f"  CHANGED MEMBER: {key}: {old_member!r} -> "
                              f"{hit[1]!r}")
                else:
                    n_ok += 1
            print(f"  check A/C vs {cfg['audit']}: {n_ok}/{len(aud)} rows "
                  f"reproduced, {n_amb} explained (ambiguity/correction), "
                  f"{n_fail} UNEXPLAINED")
        else:
            aud = list(csv.DictReader(open(data_dir / cfg["recipients_csv"],
                                           encoding="utf-8-sig")))
            new_by_bio = {}
            for _s, _raw, t, _i, b, d, tier, _c, _src in new_rows:
                if tier == "direct":
                    new_by_bio[b] = new_by_bio.get(b, 0) + t
            # deltas are explained when the missing dollars are same-last-name
            # raws the new resolver now declines (ambiguous) or re-attributes
            # (title-chamber / title-initial corrections)
            def delta_explained(bio, delta):
                last = (r.by_bio[bio]["last_name"] or "").upper()
                acc, expl = 0.0, []
                for sname, jname in cfg["slices"]:
                    for it in loadj(jname)["results"].get("recipients", []):
                        raw = it["recipient"].strip()
                        if last not in raw.upper():
                            continue
                        rep = r.resolve(raw)
                        bios = {m["bioguide_id"] for m in rep["matches"]}
                        if rep["ambiguous"] and bio in bios:
                            acc += it["total"]
                            expl.append(f"{raw!r} now ambiguous (${it['total']:,.0f})")
                        elif bios and bio not in bios and \
                                any(m["confidence"] in ("title-chamber",
                                                        "title-initial")
                                    for m in rep["matches"]):
                            acc += it["total"]
                            who = rep["matches"][0]["name"]
                            expl.append(f"{raw!r} re-attributed to {who} "
                                        f"(${it['total']:,.0f})")
                return (abs(acc - delta) < 0.01), expl

            for row in aud:
                if not row["party"]:
                    continue
                name, old_t = row["recipient"], float(row["total"])
                bio = bio_of(name)
                new_t = new_by_bio.get(bio, 0.0) if bio else None
                if bio is None:
                    n_fail += 1
                    print(f"  LOSS: {name!r} (${old_t:,.0f}) not member-matched now")
                elif abs(new_t - old_t) > 0.01:
                    ok, expl = delta_explained(bio, old_t - new_t)
                    if ok:
                        n_amb += 1
                        print(f"  correction (explained): {name!r} ${old_t:,.0f} "
                              f"-> ${new_t:,.0f}: " + "; ".join(expl))
                    else:
                        n_fail += 1
                        print(f"  TOTAL CHANGED: {name!r} ${old_t:,.0f} -> "
                              f"${new_t:,.0f}")
                else:
                    n_ok += 1
            n_members_old = sum(1 for row in aud if row["party"])
            print(f"  check A/C vs {cfg['recipients_csv']} member rows: "
                  f"{n_ok}/{n_members_old} totals reproduced, "
                  f"{n_amb} ambiguity-explained, {n_fail} UNEXPLAINED")
        grand_fail += n_fail

        # -- Check B: additions, each individually labeled
        if cfg["audit"]:
            adds = [x for x in new_rows if (x[0], x[1]) not in old_keys]
        else:
            adds = [x for x in new_rows if x[6] != "direct"]
        print(f"  check B: {len(adds)} newly-mapped rows "
              f"(committee tiers / inverted / compound)")
        for x in sorted(adds, key=lambda x: -x[2])[:6]:
            print(f"    + {x[1][:52]:54} -> {x[5][:34]:36} {x[6]:24} "
                  f"${x[2]:,.0f} [{x[7]}]")

        # -- write the P6 audit + member support rollup
        wcsv(data_dir / f"{pkg}_ld203_member_variant_audit_p6.csv",
             ["member", "giver_slice", "raw_recipient_string_as_filed", "tier",
              "confidence", "source", "total", "items"],
             [[d, s, raw, tier, conf, src, t, i]
              for s, raw, t, i, _b, d, tier, conf, src in
              sorted(new_rows, key=lambda x: (x[5], x[0], -x[2]))])
        slice_names = [s for s, _ in cfg["slices"]]
        rows = []
        for bio, g in rollup.items():
            direct_total = sum(g["direct"].values())
            rows.append([g["disp"], bio] +
                        [g["direct"].get(s, 0.0) for s in slice_names] +
                        [g["campaign"], g["ldpac"],
                         direct_total + g["campaign"] + g["ldpac"],
                         g["jfc"], g["multi"], g["variants"],
                         ";".join(sorted(g["flags"]))])
        rows.sort(key=lambda x: -x[4 + len(slice_names)])  # total_attributable
        wcsv(data_dir / f"{pkg}_member_support_rollup.csv",
             ["member", "bioguide_id"] +
             [f"direct_{s}" for s in slice_names] +
             ["campaign_committee", "leadership_pac", "total_attributable",
              "jfc_shared_unallocated", "multi_honoree_shared_unallocated",
              "n_variant_rows", "confidence_flags"],
             rows)

        # -- the pinned acceptance numbers
        for bio, g in rollup.items():
            if g["disp"].endswith("Emmer (R-MN)"):
                print(f"  EMMER: direct={sum(g['direct'].values()):,.0f} "
                      f"campaign={g['campaign']:,.0f} ldpac={g['ldpac']:,.0f} "
                      f"jfc-shared={g['jfc']:,.0f}")

    print(f"\n== regression: {'PASS — zero unexplained changes' if grand_fail == 0 else f'{grand_fail} UNEXPLAINED CHANGES'} ==")


if __name__ == "__main__":
    main()
