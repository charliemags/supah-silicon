"""Fast thermal estimate: same HotSpot physics and sources as the judge, coarser mesh.
Exploration only. Official scores come only from `hills eval`."""
import json, sys, tempfile, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
HILL = Path(os.environ.get("CRYO_HILL", str(Path(__file__).resolve().parents[2] / ".cache/challenge"))).expanduser().resolve()
if not (HILL / "challenge_spec.json").is_file():
    raise RuntimeError("Challenge simulator not found. Run ./simulation/run setup or set CRYO_HILL.")
sys.path.insert(0, str(HILL))
from generate_workloads import generate
from geometry import validate_layout
from run_simulations import create_hotspot_files, die_peaks, parse_grid
from verify_submission import verify

SPEC = json.loads((HILL / "challenge_spec.json").read_text())
PORTABLE = generate(SPEC)
VENDOR = HILL / "vendor/HotSpot"
HOTSPOT = Path(os.environ.get("CRYO_HOTSPOT", str(VENDOR / "hotspot"))).expanduser().resolve()
REF64 = json.loads((HILL / "reference_64.json").read_text())

def legal(layout, paths=None):
    """Return (ok, reason, routing)."""
    try:
        routing = validate_layout(SPEC, layout, wire_routes_grid=paths or {})
        return True, None, routing
    except Exception as e:  # validate_layout raises on any rule break
        return False, str(e)[:200], None

def estimate(layout, grid=32, workers=2, workloads=None, paths=None, timeout=1800):
    if grid not in (16, 32, 64, 128, 256):
        raise ValueError("grid must be 16, 32, 64, 128 or 256")
    if workers < 1 or timeout <= 0:
        raise ValueError("workers and timeout must be positive")
    ok, reason, routing = legal(layout, paths)
    if not ok:
        return {"passed": False, "reason": reason}
    wls = list(PORTABLE["workloads"]) if workloads is None else workloads
    if not wls or len(wls) != len(set(wls)) or set(wls) - set(PORTABLE["workloads"]):
        raise ValueError("workloads must be a nonempty, unique selection of benchmark workloads")
    with tempfile.TemporaryDirectory(prefix="fast_") as t:
        rd = Path(t)
        budgets = create_hotspot_files(SPEC, PORTABLE, layout, routing, rd, grid, VENDOR)
        def sim(w):
            args = [str(HOTSPOT), "-c", "benchmark.config", "-f", "chiplets.flp",
                    "-p", f"{w}.ptrace", "-materials_file", str(VENDOR / "examples/example3/example.materials"),
                    "-model_type", "grid", "-detailed_3D", "on", "-grid_layer_file", "stack.lcf",
                    "-grid_steady_file", f"{w}.grid", "-steady_file", f"{w}.steady"]
            p = subprocess.run(args, cwd=rd, text=True, capture_output=True, timeout=timeout)
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
    power = {w: {k: budgets[w][k] for k in ("base_w", "phy_w", "wire_w", "total_w")} for w in wls}
    return {"passed": True, "grid": grid, "gpu": gpu, "hbm": hbm, "peaks": peaks,
            "grids": grids, "power": power}

if __name__ == "__main__":
    submission = json.loads(Path(sys.argv[1]).read_text())
    lay = submission["placements_mm"]
    g = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    t = time.time(); r = estimate(lay, g, paths=submission.get("wire_routes_grid"))
    r.pop("grids", None)
    print(json.dumps({k: r[k] for k in r if k != "peaks"}), f"{time.time()-t:.1f}s")
    raise SystemExit(0 if r["passed"] else 2)
