#!/usr/bin/env bash
# Supah-Silicon: simulate layouts and draw their temperature maps, using the organizers' own tools.
#
#   ./simulation/run.sh                                   # reference vs our best layout
#   ./simulation/run.sh simulation/layouts/p2/submission.json my_layout.json
#
# Needs: Linux on an Intel/AMD processor (or WSL, Docker, or a GitHub Codespace), Python 3 and git.
# Output: simulation/output/<time>/temperature_maps.png plus results.json, and a score table printed here.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SIM="${CHIPLET_SIM:-$HERE/.organizer-simulator}"
GRID="${GRID:-64}"

# 1. Get the organizers' simulator (power workloads, rule checker, pinned HotSpot) once.
if [ ! -d "$SIM" ]; then
  echo "Downloading the organizers' simulator..."
  git clone --depth 1 https://github.com/Czaja107/chiplet-thermal-simulator "$SIM"
fi
python3 -c "import numpy, matplotlib" 2>/dev/null || python3 -m pip install --quiet numpy matplotlib

# 2. Choose layouts: the organizers' reference is always included for comparison.
if [ "$#" -eq 0 ]; then set -- "$HERE/layouts/p2/submission.json"; fi
OUT="$HERE/output/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
python3 - "$SIM" "$OUT/layouts.json" "$@" <<'PY'
import json, sys, pathlib
sim, out, files = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
layouts = {"reference": json.loads((sim / "random_layout.json").read_text())["random_layout"]}
for f in files:
    p = pathlib.Path(f)
    layouts[p.parent.name if p.name == "submission.json" else p.stem] = json.loads(p.read_text())
json.dump(layouts, open(out, "w"), indent=1)
print("Layouts:", ", ".join(layouts))
PY

# 3. Check the rules first (instant), then simulate all five workloads.
for f in "$@"; do python3 "$SIM/verify_submission.py" "$f" > /dev/null && echo "Rules OK: $f"; done
echo "Simulating on a ${GRID}x${GRID} grid (a few minutes per layout on a small machine)..."
( cd "$SIM" && python3 run_simulations.py --hotspot vendor/HotSpot/hotspot --grid "$GRID" \
    --layouts "$OUT/layouts.json" --output "$OUT" > "$OUT/run.log" 2>&1 )

# 4. Print the score table.
python3 - "$OUT/results.json" <<'PY'
import json, sys
res = json.load(open(sys.argv[1]))
print(f"\n{'layout':<22}{'hottest GPU':>13}{'hottest HBM':>13}{'score':>9}")
for name, r in res["objectives"].items():
    s = r.get("leaderboard_score")
    print(f"{name:<22}{r['worst_gpu_c']:>11.2f} C{r['worst_hbm_c']:>11.2f} C{s:>9.4f}" if s is not None
          else f"{name:<22}{r['worst_gpu_c']:>11.2f} C{r['worst_hbm_c']:>11.2f} C{'n/a':>9}")
print("\nLower score is better. 1.0 = the organizers' reference layout.")
PY
echo "Pictures and full results: $OUT"
ls "$OUT"/*.png 2>/dev/null || true
