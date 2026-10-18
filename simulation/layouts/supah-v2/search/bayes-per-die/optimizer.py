"""Constrained Gaussian-process placement search, measured with pinned HotSpot.

The surrogate only proposes layouts. Every retained observation is a simulation;
finalists must pass the unmodified all-workload judge at both 64 and 128 grids.
Uses NumPy already present in the simulation image; no API/model service needed.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

import fast
from optimize import compact, key, score, write_json
from verify_submission import parse_submission

DIES = sorted(fast.SPEC["dies"])
AMBIENT = fast.SPEC["thermal_model"]["ambient_c"]
TARGETS = [("skewed_compute", "G"), ("tensor_training", "G"), ("memory_stream", "H")]
SCREEN = [w for w, _ in TARGETS]


def vector(layout):
    return np.array([layout[d] for d in DIES]).ravel()


def placement(x):
    return {d: np.round(x[2*i:2*i+2], 3).tolist() for i, d in enumerate(DIES)}


def kernel(a, b, length, additive=False):
    if additive:
        return sum(kernel(a[:, i:i+2], b[:, i:i+2], length)
                   for i in range(0, a.shape[1], 2)) / (a.shape[1] / 2)
    distance = np.sqrt(np.maximum(0, (a*a).sum(1)[:, None] +
                                  (b*b).sum(1)[None, :] - 2*a@b.T)) / length
    z = np.sqrt(5) * distance
    return (1 + z + z*z/3) * np.exp(-z)


class GaussianProcess:
    """Matérn-5/2 GP; select length and regularization by leave-one-out error."""
    def __init__(self, additive=False):
        self.additive = additive

    def fit(self, x, y):
        self.x = np.asarray(x)
        y = np.asarray(y)
        self.mean = y.mean(axis=0)
        self.scale = np.maximum(y.std(axis=0), 0.25)
        z = (y - self.mean) / self.scale
        best = None
        for length in (0.35, 0.7, 1.4, 2.8, 5.6):
            k = kernel(self.x, self.x, length, self.additive)
            for noise in (0.0025, 0.04):
                inverse = np.linalg.solve(k + np.eye(len(x))*noise, np.eye(len(x)))
                alpha = inverse @ z
                diagonal = np.diag(inverse).reshape((-1,) + (1,)*(z.ndim-1))
                error = float(np.mean((alpha / diagonal)**2))
                if best is None or error < best[0]:
                    best = error, length, noise, inverse, alpha
        error, self.length, self.noise, self.inverse, self.alpha = best
        diagonal = np.diag(self.inverse).reshape((-1,) + (1,)*(z.ndim-1))
        self.loo_rmse_c = float(np.sqrt(np.mean((self.alpha/diagonal*self.scale)**2)))
        return self

    def predict(self, x):
        k = kernel(np.asarray(x), self.x, self.length, self.additive)
        mean = self.mean + self.scale * (k @ self.alpha)
        variance = np.maximum(0, 1 - np.sum((k @ self.inverse)*k, axis=1))
        std = np.sqrt(variance).reshape((-1,) + (1,)*self.scale.ndim) * self.scale
        return mean, std


def observations(records, workload, kind, grid=64, per_die=False):
    unique = {}
    for r in records:
        if not r.get("passed") or r.get("grid") != grid or workload not in r.get("peaks", {}):
            continue
        sub = r["submission"]
        if sub.get("wire_routes_grid"):
            continue  # A placement-only model cannot distinguish explicit routes.
        temperatures = [r["peaks"][workload][d] for d in sorted(r["peaks"][workload]) if d.startswith(kind)]
        unique[key(sub)] = (vector(sub["placements_mm"]), temperatures if per_die else max(temperatures))
    return [v[0] for v in unique.values()], [v[1] for v in unique.values()]


def cheap_legal(x):
    """Only a prefilter; the organizer's router decides actual legality."""
    boxes = []
    for i, d in enumerate(DIES):
        a, b = x[2*i:2*i+2]
        w, h = fast.SPEC["dies"][d]["size_mm"]
        edge = fast.SPEC["edge_clearance_mm"]
        W, H = fast.SPEC["interposer_mm"]
        if a < edge or b < edge or a+w > W-edge or b+h > H-edge:
            return False
        boxes.append((a, b, a+w, b+h))
    gap = fast.SPEC["minimum_die_gap_mm"]
    return all(a[2]+gap <= b[0] or b[2]+gap <= a[0] or
               a[3]+gap <= b[1] or b[3]+gap <= a[1]
               for i, a in enumerate(boxes) for b in boxes[i+1:])


def candidates(anchors, rng, count, radius):
    pool = []
    for _ in range(count*12):
        x = vector(anchors[int(rng.integers(len(anchors)))])
        step = float(rng.choice([0.15, 0.4, 0.8, 1.5, 3.0])) * radius
        mode = rng.random()
        if mode < 0.15:
            x += np.tile(rng.normal(0, step, 2), len(DIES))
        elif mode < 0.3:
            # Collective expansion/contraction can escape a single-die route limit.
            centers = x.reshape(-1, 2) + np.array([fast.SPEC["dies"][d]["size_mm"] for d in DIES])/2
            x += ((centers - [26, 21]) * rng.normal(0, step/15, 2)).ravel()
        elif mode < 0.55:
            groups = [["G0", "H0", "H3"], ["G1", "H1", "H0"],
                      ["G2", "H2", "H1"], ["G3", "H3", "H2"],
                      ["G0", "G3", "H3"], ["G1", "G2", "H1"],
                      ["G0", "G1", "H0"], ["G2", "G3", "H2"],
                      ["G0", "G3", "H0", "H3"], ["G1", "G2", "H1", "H2"]]
            delta = rng.normal(0, step, 2)
            for d in groups[int(rng.integers(len(groups)))]:
                i = DIES.index(d)
                x[2*i:2*i+2] += delta
        else:
            for i in rng.choice(len(DIES), size=int(rng.choice([1, 1, 2, 4])), replace=False):
                x[2*i:2*i+2] += rng.normal(0, step, 2)
        x = np.round(x, 3)
        if cheap_legal(x):
            pool.append(x)
        if len(pool) >= count:
            break
    if not pool:
        raise RuntimeError("No geometrically feasible proposals")
    return np.array(pool)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--history", nargs="*", type=Path, default=[])
    parser.add_argument("--evals", type=int, default=80)
    parser.add_argument("--pool", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--radius", type=float, default=1.0)
    parser.add_argument("--kernel", choices=("full", "additive"), default="full")
    parser.add_argument("--grid", type=int, choices=(64, 128), default=64)
    parser.add_argument("--per-die", action="store_true", help="model individual die peaks before taking the maximum")
    args = parser.parse_args()
    if min(args.evals, args.pool, args.workers, args.radius) <= 0:
        parser.error("budgets and radius must be positive")
    layout, paths = parse_submission(args.start, fast.SPEC)
    if paths or not fast.legal(layout)[0]:
        parser.error("start must be a legal automatically routed placement")
    args.output.mkdir(parents=True, exist_ok=False)
    ref = json.loads((fast.HILL / f"reference_{args.grid}.json").read_text())
    reference = {"gpu": ref["worst_gpu_c"], "hbm": ref["worst_hbm_c"]}
    manifest = {k: ([str(p) for p in v] if isinstance(v, list) else str(v) if isinstance(v, Path) else v)
                for k, v in vars(args).items()}
    manifest.update(kind=f"{args.grid}-grid surrogate-assisted exploration; not a verified score",
                    model="Matern-5/2 GP; cross-validated length/noise; lower confidence bound",
                    code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    hotspot_sha256=hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
                    inputs_sha256={n: hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest()
                                   for n in ("challenge_spec.json", "workloads.json")},
                    history_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.history})
    write_json(args.output / "experiment.json", manifest)
    records = [json.loads(line) for p in args.history for line in p.read_text().splitlines() if line.strip()]
    seen = {key(r["submission"]) for r in records}
    rng = np.random.default_rng(args.seed)
    evaluated = []
    started = time.monotonic()
    best = float("inf")
    with (args.output / "search.jsonl").open("w") as log:
        for iteration in range(args.evals):
            diagnostics = []
            prediction = None
            if iteration:
                ranked = sorted(evaluated, key=lambda r: r["screen_score"])
                anchors = [ranked[0]["submission"]["placements_mm"]]*3
                anchors += [r["submission"]["placements_mm"] for r in ranked[:4]]
                pool = candidates(anchors, rng, args.pool, args.radius)
                lower = []
                means = []
                beta = 1.5 if iteration % 5 == 0 else 0.35
                for workload, kind in TARGETS:
                    x, y = observations(records, workload, kind, args.grid, args.per_die)
                    gp = GaussianProcess(additive=args.kernel == "additive").fit(x, y)
                    mean, std = gp.predict(pool)
                    denominator = reference["gpu" if kind == "G" else "hbm"]-AMBIENT
                    bound = (mean-beta*std-AMBIENT)/denominator
                    lower.append(bound.max(axis=1) if args.per_die else bound)
                    means.append(mean)
                    diagnostics.append({"workload": workload, "kind": kind, "samples": len(y),
                                        "length_mm": gp.length, "noise": gp.noise,
                                        "loo_rmse_c": gp.loo_rmse_c})
                acquisition = np.max(lower, axis=0)
                for index in np.argsort(acquisition):
                    sub = {"placements_mm": placement(pool[index])}
                    identity = key(sub)
                    if identity not in seen and fast.legal(sub["placements_mm"])[0]:
                        layout = sub["placements_mm"]
                        prediction = [m[index].tolist() for m in means]
                        break
                else:
                    raise RuntimeError("No new legal proposal; increase --pool or --radius")
            sub = {"placements_mm": layout}
            result = fast.estimate(layout, args.grid, workers=args.workers, workloads=SCREEN)
            if not result["passed"]:
                raise RuntimeError(result)
            value = score(result, reference)
            record = {"evaluation": iteration, "submission": sub, "screen_score": value,
                      "prediction_c": prediction, "models": diagnostics,
                      "elapsed_seconds": round(time.monotonic()-started, 2), **compact(result)}
            log.write(json.dumps(record) + "\n")
            log.flush()
            evaluated.append(record)
            records.append(record)
            seen.add(key(sub))
            if value < best:
                best = value
                write_json(args.output / "submission.json", sub)
            write_json(args.output / "summary.json", {
                "kind": "screening estimate; requires all-workload verification at 64 and 128",
                "evaluations": len(evaluated), "seed_score": evaluated[0]["screen_score"],
                "best_score": best, "elapsed_seconds": round(time.monotonic()-started, 2)})
            print(f"{iteration+1}/{args.evals}: screen={value:.6f} best={best:.6f} "
                  f"GPU={result['gpu']:.2f} HBM={result['hbm']:.2f}", flush=True)


if __name__ == "__main__":
    main()
