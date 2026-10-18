"""Fast thermal estimate: same HotSpot physics and sources as the judge, coarser mesh.
Exploration only. Official scores come only from `hills eval`."""
import json, sys, tempfile, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
HILL = Path(os.environ.get("CRYO_HILL", "/home/claude/cryo/.autolab/hills/beat-the-hotspot"))
sys.path.insert(0, str(HILL))
from generate_workloads import generate
from geometry import validate_layout
from run_simulations import create_hotspot_files, die_peaks, parse_grid
from verify_submission import verify

SPEC = json.loads((HILL / "challenge_spec.json").read_text())
PORTABLE = generate(SPEC)
VENDOR = HILL / "vendor/HotSpot"
REF64 = json.loads((HILL / "reference_64.json").read_text())

def legal(layout, paths=None):
    """Return (ok, reason, routing)."""
    try:
        routing = validate_layout(SPEC, layout, wire_routes_grid=paths or {})
        return True, None, routing
    except Exception as e:  # validate_layout raises on any rule break
        return False, str(e)[:200], None

def estimate(layout, grid=32, workers=2, workloads=None):
    ok, reason, routing = legal(layout)
    if not ok:
        return {"passed": False, "reason": reason}
    wls = workloads or list(PORTABLE["workloads"])
    with tempfile.TemporaryDirectory(prefix="fast_") as t:
        rd = Path(t)
        create_hotspot_files(SPEC, PORTABLE, layout, routing, rd, grid, VENDOR)
        def sim(w):
            args = [str(VENDOR / "hotspot"), "-c", "benchmark.config", "-f", "chiplets.flp",
                    "-p", f"{w}.ptrace", "-materials_file", str(VENDOR / "examples/example3/example.materials"),
                    "-model_type", "grid", "-detailed_3D", "on", "-grid_layer_file", "stack.lcf",
                    "-grid_steady_file", f"{w}.grid", "-steady_file", f"{w}.steady"]
            p = subprocess.run(args, cwd=rd, text=True, capture_output=True)
            if p.returncode:
                raise RuntimeError(p.stderr[-500:])
            g = parse_grid(rd / f"{w}.grid", grid)
            return w, die_peaks(SPEC, layout, g), g
        with ThreadPoolExecutor(max_workers=workers) as pool:
            res = list(pool.map(sim, wls))
    peaks = {w: p for w, p, _ in res}
    grids = {w: g for w, _, g in res}
    gpu = max(v for p in peaks.values() for d, v in p.items() if d.startswith("G"))
    hbm = max(v for p in peaks.values() for d, v in p.items() if d.startswith("H"))
    return {"passed": True, "grid": grid, "gpu": gpu, "hbm": hbm, "peaks": peaks, "grids": grids}

if __name__ == "__main__":
    lay = json.loads(Path(sys.argv[1]).read_text())["placements_mm"]
    g = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    t = time.time(); r = estimate(lay, g)
    r.pop("grids", None)
    print(json.dumps({k: r[k] for k in r if k != "peaks"}), f"{time.time()-t:.1f}s")
