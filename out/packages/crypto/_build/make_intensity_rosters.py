"""Split the diversified-core giving roster by crypto ACTIVITY SHARE (2026-07-11,
Rob-approved >=5% intensity gate on the giving split).

Reads out/crypto_roster_core_diversified.txt (the 162 core-minus-pure-play names the
2026-07-08 split used) and data/crypto_players.csv (which now carries
crypto_activity_share_pct), writes two disjoint rosters whose union is exactly the
input:

  out/crypto_roster_div_forward.txt   crypto-forward diversified: share >= 5%
  out/crypto_roster_div_ambient.txt   ambient / incidental:       share <  5%

The gate value (5%) follows the healthcare package's Chamber precedent (5.4% read as
"side-desk", not "player"). A roster name that fails to match a player row exactly is
matched on a normalized key; any name still unmatched FAILS the build (no silent
drops). Run from the repo root, AFTER export_crypto.py.
"""
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# This file lives at <repo>/out/packages/crypto/_build/ — derive the repo
# root from that instead of hardcoding one machine's checkout path.
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
DATA = os.path.join(REPO, "out", "packages", "crypto", "data")
GATE_PCT = 5.0

def norm(s):
    s = re.sub(r"\(.*?\)", " ", s.upper())
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(INCORPORATED|INC|LLC|L L C|CORP|CORPORATION|COMPANY|CO|LTD|LP|LLP|PLLC|NA|N A)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

players = {}
by_norm = {}
with open(os.path.join(DATA, "crypto_players.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        players[row["player"]] = row
        by_norm.setdefault(norm(row["player"]), row)

roster_path = os.path.join(REPO, "out", "crypto_roster_core_diversified.txt")
names = [ln.strip() for ln in open(roster_path, encoding="utf-8") if ln.strip()]

fwd, amb, unmatched = [], [], []
for name in names:
    row = players.get(name) or by_norm.get(norm(name))
    if row is None:
        unmatched.append(name)
        continue
    share = row["crypto_activity_share_pct"]
    band = row["crypto_share_band"]
    if share == "" or share is None:
        # no non-registration senate blocks — cannot pass an intensity gate
        amb.append((name, "n/a", band))
    elif float(share) >= GATE_PCT:
        fwd.append((name, share, band))
    else:
        amb.append((name, share, band))

if unmatched:
    print("FATAL — roster names with no player match (fix before shipping):")
    for n in unmatched:
        print("  ", n)
    sys.exit(1)

for out_name, rows in (("crypto_roster_div_forward.txt", fwd),
                       ("crypto_roster_div_ambient.txt", amb)):
    p = os.path.join(REPO, "out", out_name)
    with open(p, "w", encoding="utf-8") as f:
        for name, _s, _b in rows:
            f.write(name + "\n")
    print(f"[roster] {out_name}: {len(rows)} names")

assert len(fwd) + len(amb) == len(names), "split must partition the input roster"
print(f"\ngate = {GATE_PCT}% activity share · input {len(names)} names -> "
      f"forward {len(fwd)} / ambient {len(amb)}")
print("\nambient slice (gated out of the crypto giving story):")
for name, s, b in sorted(amb, key=lambda x: x[0]):
    print(f"  {name[:58]:60s} share={s}%")
