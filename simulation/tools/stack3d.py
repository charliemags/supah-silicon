"""CRYO-GOBLIN 2.0: 3D-stacked what-if using the hill's own HotSpot build, workloads and cooler.

Not scored by the hill (the challenge is 2.5D only). Same power maps, same TIM/spreader/sink,
same ambient. Each HBM_i is stacked on GPU_i ("A": memory on top) or under it ("B": GPU on top).

Assumptions (all swept or stated, none calibrated to a real product):
- GPU die: 150 um silicon, as in the hill.
- HBM stack: one effective layer, 720 um thick (12-high class), vertical k swept.
- Bond layer between GPU and HBM: 10 um, k swept (microbump+underfill vs hybrid bond).
- Fill around the stacks in upper layers: mold-like (hill's gap resistivity) or silicon.
- Primary links become vertical: PHY energy only, no wire. Secondary links stay lateral;
  their PHY+wire heat is added to the GPU (conservative).
"""
import json, sys, re, subprocess, tempfile, itertools
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import fast
sys.path.insert(0, str(fast.HILL))
from run_simulations import _floorplan_line

SPEC, PORT, VENDOR = fast.SPEC, fast.PORTABLE, fast.VENDOR
W, H = SPEC["interposer_mm"]
TM = SPEC["thermal_model"]
R_SI = TM["thermal_resistivity_si_mK_per_W"]
R_GAP = TM["thermal_resistivity_gap_mK_per_W"]
N = SPEC["power_pixels_per_die_side"]
IC = SPEC["interconnect_model"]


def boxes_for(gpu_xy):
    """GPU boxes at given origins; each HBM centered on its GPU."""
    g, h = {}, {}
    for i in range(4):
        x, y = gpu_xy[f"G{i}"]
        gw, gh = SPEC["dies"][f"G{i}"]["size_mm"]
        hw, hh = SPEC["dies"][f"H{i}"]["size_mm"]
        g[f"G{i}"] = (x, y, x + gw, y + gh)
        cx, cy = x + gw / 2, y + gh / 2
        h[f"H{i}"] = (cx - hw / 2, cy - hh / 2, cx + hw / 2, cy + hh / 2)
    return g, h


def layer_flp(prefix, boxes, occ_resist, fill_resist, pixelate):
    """Floorplan covering the whole interposer: occupant blocks (16x16 pixels if powered) + fill tiles."""
    lines, units = [], []
    xs = sorted({0.0, W, *(q for b in boxes.values() for q in (b[0], b[2]))})
    ys = sorted({0.0, H, *(q for b in boxes.values() for q in (b[1], b[3]))})
    for j, (y0, y1) in enumerate(zip(ys, ys[1:])):
        for i, (x0, x1) in enumerate(zip(xs, xs[1:])):
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            if any(a < mx < c and b < my < d for a, b, c, d in boxes.values()):
                continue
            nm = f"{prefix}fill_{j}_{i}"
            lines.append(_floorplan_line(nm, x0, y0, x1 - x0, y1 - y0, 1.75e6, fill_resist)); units.append((nm, None, 0, 0))
    for name, (x0, y0, x1, y1) in boxes.items():
        if pixelate:
            dx, dy = (x1 - x0) / N, (y1 - y0) / N
            for r in range(N):
                for c in range(N):
                    nm = f"{prefix}{name}_y{r:02d}_x{c:02d}"
                    lines.append(_floorplan_line(nm, x0 + c * dx, y0 + r * dy, dx, dy, 1.75e6, occ_resist))
                    units.append((nm, name, r, c))
        else:
            nm = f"{prefix}{name}_blk"
            lines.append(_floorplan_line(nm, x0, y0, x1 - x0, y1 - y0, 1.75e6, occ_resist)); units.append((nm, None, 0, 0))
    return "".join(lines), units


def link_heat(workload, gbox):
    """Extra watts per die: vertical primaries (PHY only), lateral secondaries (PHY+wire, to GPU)."""
    util = SPEC["workloads"][workload]["link_utilization"]
    add = {f"G{i}": 0.0 for i in range(4)} | {f"H{i}": 0.0 for i in range(4)}
    for l in SPEC["links"]:
        bits = 8e9 * l["gb_s"] * util[l["id"]]
        phy = bits * IC["phy_energy_total_pj_per_bit"] * 1e-12
        if l["id"][0] == "P":
            add[l["from"]] += phy / 2; add[l["to"]] += phy / 2
        else:
            a = gbox[l["from"]]; b = gbox["G" + l["to"][1]]
            gap = max(b[0] - a[2], a[0] - b[2], 0) + max(b[1] - a[3], a[1] - b[3], 0)
            wire = bits * (gap + 2.0) * IC["wire_energy_pj_per_bit_per_mm"] * 1e-12
            add[l["from"]] += phy + wire
    return add


def run(gpu_xy, order="A", k_hbm=30.0, k_bond=1.5, fill="mold", grid=32, workloads=None):
    gbox, hbox = boxes_for(gpu_xy)
    fill_r = R_GAP if fill == "mold" else R_SI
    r_hbm, r_bond = 1 / k_hbm, 1 / k_bond
    g_lines, g_units = layer_flp("g_", gbox, R_SI, R_GAP if order == "A" else fill_r, True)
    h_lines, h_units = layer_flp("h_", hbox, r_hbm, fill_r if order == "A" else R_GAP, True)
    b_lines, _ = layer_flp("b_", hbox, r_bond, fill_r, False)
    ip_line = _floorplan_line("interposer", 0, 0, W, H, 1.75e6, R_SI)
    cx, cy, cw, ch = TM["cooling_contact_rect_mm"]; et = TM["outside_contact_resistivity_mK_per_W"]
    tim = "".join(_floorplan_line(n, x, y, w, h, 4.0e6, r) for n, x, y, w, h, r in (
        ("cooling_contact", cx, cy, cw, ch, TM["thermal_resistivity_tim_mK_per_W"]),
        ("pb", 0, 0, W, cy, et), ("pt", 0, cy + ch, W, H - cy - ch, et),
        ("pl", 0, cy, cx, ch, et), ("pr", cx + cw, cy, W - cx - cw, ch, et)))
    # bottom -> top; last layer touches the spreader/sink
    seq = [("interposer.flp", ip_line, "N", R_SI, TM["interposer_si_thickness_um"])]
    if order == "A":
        seq += [("gpu.flp", g_lines, "Y", R_SI, TM["die_si_thickness_um"]),
                ("bond.flp", b_lines, "N", r_bond, 10),
                ("hbm.flp", h_lines, "Y", r_hbm, 720)]
        gpu_layer, hbm_layer = 1, 3
    else:
        seq += [("hbm.flp", h_lines, "Y", r_hbm, 720),
                ("bond.flp", b_lines, "N", r_bond, 10),
                ("gpu.flp", g_lines, "Y", R_SI, TM["die_si_thickness_um"])]
        gpu_layer, hbm_layer = 3, 1
    seq += [("tim.flp", tim, "N", TM["thermal_resistivity_tim_mK_per_W"], TM["tim_thickness_um"])]
    wls = workloads or list(PORT["workloads"])
    out = {}
    with tempfile.TemporaryDirectory(prefix="goblin3d_") as t:
        rd = Path(t)
        lcf = ["# CRYO-GOBLIN 2.0 stack, bottom to top"]
        for i, (fn, txt, pw, res, th) in enumerate(seq):
            (rd / fn).write_text(txt)
            cp = "4.0e6" if fn == "tim.flp" else "1.75e6"
            lcf += [str(i), "Y", pw, cp, f"{res}", f"{th * 1e-6:.9g}", fn]
        (rd / "stack.lcf").write_text("\n".join(lcf) + "\n")
        cfg = (VENDOR / "examples/example3/example.config").read_text()
        for k, v in {"ambient": 273.15 + TM["ambient_c"], "init_temp": 273.15 + TM["ambient_c"],
                     "grid_rows": grid, "grid_cols": grid, "s_spreader": TM["spreader_side_mm"] / 1000,
                     "s_sink": TM["sink_side_mm"] / 1000, "r_convec": TM["cooling_resistance_K_per_W"]}.items():
            cfg, n = re.subn(rf"(?m)^(\s*-{k}\s+)\S+", lambda m: m.group(1) + str(v), cfg); assert n == 1, k
        (rd / "benchmark.config").write_text(cfg)
        for w in wls:
            maps = PORT["workloads"][w]["power_maps_w"]; add = link_heat(w, gbox)
            names, vals = [], []
            for units in ((g_units, h_units) if order == "A" else (h_units, g_units)):
                for nm, die, r, c in units:
                    names.append(nm)
                    vals.append(0.0 if die is None else maps[die][r][c] + add[die] / (N * N))
            (rd / f"{w}.ptrace").write_text("\t".join(names) + "\n" + "\t".join(f"{v:.9g}" for v in vals) + "\n")

        def sim(w):
            args = [str(VENDOR / "hotspot"), "-c", "benchmark.config", "-f", "gpu.flp", "-p", f"{w}.ptrace",
                    "-materials_file", str(VENDOR / "examples/example3/example.materials"), "-model_type", "grid",
                    "-detailed_3D", "on", "-grid_layer_file", "stack.lcf",
                    "-grid_steady_file", f"{w}.grid", "-steady_file", f"{w}.steady"]
            p = subprocess.run(args, cwd=rd, text=True, capture_output=True)
            if p.returncode:
                raise RuntimeError(p.stderr[-800:])
            layers, cur = [], []
            for line in (rd / f"{w}.grid").read_text().splitlines():
                if line.startswith("Layer "):
                    if cur: layers.append(np.array(cur).reshape(grid, grid)); cur = []
                elif line.strip():
                    cur.append(float(line.split()[1]))
            if cur: layers.append(np.array(cur).reshape(grid, grid))
            def peak(layer, boxes):
                m = layers[layer] - 273.15
                xx = (np.arange(grid) + 0.5) / grid * W; yy = H - (np.arange(grid) + 0.5) / grid * H
                return {n: round(float(m[np.ix_((yy >= b[1]) & (yy < b[3]), (xx >= b[0]) & (xx < b[2]))].max()), 2)
                        for n, b in boxes.items()}
            return w, peak(gpu_layer, gbox), peak(hbm_layer, hbox)
        with ThreadPoolExecutor(max_workers=2) as pool:
            for w, gp, hp in pool.map(sim, wls):
                out[w] = {"gpu": gp, "hbm": hp}
    gpu = max(v for r in out.values() for v in r["gpu"].values())
    hbm = max(v for r in out.values() for v in r["hbm"].values())
    return {"order": order, "k_hbm": k_hbm, "k_bond": k_bond, "fill": fill, "grid": grid,
            "gpu": gpu, "hbm": hbm, "per_workload": out}


if __name__ == "__main__":
    lay = json.loads(Path(sys.argv[1]).read_text())["placements_mm"]
    gxy = {d: lay[d] for d in lay if d[0] == "G"}
    r = run(gxy, order=sys.argv[2] if len(sys.argv) > 2 else "A")
    print(json.dumps({k: r[k] for k in r if k != "per_workload"}))
