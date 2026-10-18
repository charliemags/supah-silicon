"""Simulated annealing over die positions, scored by the fast coarse-grid estimate.

Optional guidance: a JSON of target boxes per die (from the heat-map-reading AI).
Guidance is a soft pull toward each box (small weight), as in the VeoPlace paper's
best setting, so the search can still leave a box when the heat says so.

Every evaluated layout is appended to a JSONL log. Exploration only: official
numbers come from `hills eval`.
"""
import argparse, json, math, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import fast

GRID = 16
REF = None  # set in main: fast-grid reference temps for the organizer's layout
AMB = 25.0
DIES = ["G0", "G1", "G2", "G3", "H0", "H1", "H2", "H3"]


WLS = None


def proxy_score(r):
    if WLS:  # exact mode: only the GPU objective is measured; HBM checked separately
        return (r["gpu"] - AMB) / (REF[0] - AMB)
    return max((r["gpu"] - AMB) / (REF[0] - AMB), (r["hbm"] - AMB) / (REF[1] - AMB))


def box_penalty(layout, boxes):
    if not boxes:
        return 0.0
    pen = 0.0
    for d, (x0, y0, x1, y1) in boxes.items():
        x, y = layout[d]
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        pen += dx * dx + dy * dy
    return pen


def propose(layout, step, rng):
    new = {k: list(v) for k, v in layout.items()}
    r = rng.random()
    if r < 0.12:  # swap two dies of the same kind
        kind = rng.choice("GH")
        a, b = rng.sample([d for d in DIES if d[0] == kind], 2)
        new[a], new[b] = new[b], new[a]
    elif r < 0.25:  # shift everything together
        dx, dy = rng.gauss(0, step), rng.gauss(0, step)
        for d in new:
            new[d][0] += dx; new[d][1] += dy
    else:
        for d in rng.sample(DIES, rng.choice([1, 1, 2])):
            new[d][0] += rng.gauss(0, step)
            new[d][1] += rng.gauss(0, step)
    return {k: [round(v[0], 3), round(v[1], 3)] for k, v in new.items()}


def main():
    global REF
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("--evals", type=int, default=150)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--boxes", default=None)
    ap.add_argument("--lam", type=float, default=0.01)
    ap.add_argument("--log", required=True)
    ap.add_argument("--tag", default="plain")
    ap.add_argument("--step0", type=float, default=1.5)
    ap.add_argument("--step1", type=float, default=0.15)
    ap.add_argument("--t0", type=float, default=0.01)
    ap.add_argument("--mode", default="fast", choices=["fast", "exact"],
                    help="fast: grid 16, all workloads. exact: grid 64 (official mesh), GPU-deciding workloads only")
    a = ap.parse_args()
    global GRID, WLS
    if a.mode == "exact":
        GRID, WLS = 64, ["skewed_compute", "tensor_training"]
        REF = (fast.REF64["worst_gpu_c"], fast.REF64["worst_hbm_c"])
    else:
        WLS = None
        REF = tuple(json.loads((Path(__file__).parent / "ref16.json").read_text())[k] for k in ("gpu", "hbm"))
    rng = random.Random(a.seed)
    boxes = json.loads(Path(a.boxes).read_text()) if a.boxes else None
    cur = json.loads(Path(a.start).read_text())["placements_mm"]
    r = fast.estimate(cur, GRID, workloads=WLS)
    assert r["passed"], r
    cur_s = proxy_score(r); cur_obj = cur_s + a.lam * box_penalty(cur, boxes)
    best, best_s = cur, cur_s
    log = open(a.log, "a")
    def write(lay, res, s, acc):
        log.write(json.dumps({"tag": a.tag, "seed": a.seed, "t": time.time(), "layout": lay,
                              "gpu": res["gpu"], "hbm": res["hbm"], "proxy": s, "accepted": acc, "mode": a.mode}) + "\n"); log.flush()
    write(cur, r, cur_s, True)
    n = 1; tries = 0
    while n < a.evals:
        frac = n / a.evals
        step = a.step0 * (a.step1 / a.step0) ** frac
        temp = a.t0 * (1 - frac) + 1e-5
        cand = propose(cur, step, rng); tries += 1
        ok, _, _ = fast.legal(cand)
        if not ok:
            continue
        res = fast.estimate(cand, GRID, workloads=WLS); n += 1
        s = proxy_score(res); obj = s + a.lam * box_penalty(cand, boxes)
        acc = obj < cur_obj or rng.random() < math.exp(-(obj - cur_obj) / temp)
        write(cand, res, s, acc)
        if acc:
            cur, cur_obj = cand, obj
        if s < best_s:
            best, best_s = cand, s
            print(f"[{a.tag} {n}/{a.evals}] best proxy {best_s:.4f} gpu {res['gpu']:.2f} hbm {res['hbm']:.2f}", flush=True)
    print(json.dumps({"best_proxy": best_s, "layout": best, "legal_tries": tries, "evals": n}))
    out = Path(a.log).with_suffix(f".{a.tag}.s{a.seed}.best.json")
    out.write_text(json.dumps({"placements_mm": best}, indent=1))


if __name__ == "__main__":
    main()
