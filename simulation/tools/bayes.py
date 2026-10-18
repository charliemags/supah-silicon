"""Bayesian optimization of die positions around a starting layout.

Each thermal evaluation is expensive (about 18 s for all five workloads), so instead of
random nudges this fits a Gaussian process to every result so far and picks the next
layout by expected improvement. Candidates are offsets of selected dies inside a box
around the start. Illegal candidates are filtered with the instant rule check before
they reach the model, so the solver only ever runs on legal layouts.

Every evaluation uses all five workloads, so the search score is the real objective at
the chosen grid. Results are exploration estimates; verify finalists with evaluate.py.

    CRYO_HOTSPOT=/path/to/native/hotspot python3 simulation/tools/bayes.py \
        simulation/layouts/supah-v1/submission.json --output simulation/experiments/bayes-1
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

import fast
from optimize import compact, score, write_json
from verify_submission import parse_submission


def matern52(a, b, length):
    d = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)) / length
    return (1 + math.sqrt(5) * d + 5 / 3 * d ** 2) * np.exp(-math.sqrt(5) * d)


class GP:
    """Zero-mean GP on standardized scores; length scale and noise chosen by marginal likelihood."""

    def fit(self, x, y):
        self.x, self.mu, self.sd = x, y.mean(), y.std() or 1.0
        z = (y - self.mu) / self.sd
        best = None
        for length in (0.3, 0.5, 0.8, 1.2, 2.0, 3.0):
            for noise in (1e-4, 1e-3, 1e-2, 1e-1):
                k = matern52(x, x, length) + noise * np.eye(len(x))
                try:
                    chol = np.linalg.cholesky(k)
                except np.linalg.LinAlgError:
                    continue
                alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, z))
                ll = -0.5 * z @ alpha - np.log(np.diag(chol)).sum()
                if best is None or ll > best[0]:
                    best = (ll, length, chol, alpha)
        _, self.length, self.chol, self.alpha = best
        return self

    def predict(self, xs):
        ks = matern52(xs, self.x, self.length)
        mean = ks @ self.alpha
        v = np.linalg.solve(self.chol, ks.T)
        var = np.clip(1 - (v ** 2).sum(0), 1e-12, None)
        return mean * self.sd + self.mu, np.sqrt(var) * self.sd


def expected_improvement(mean, sd, best):
    z = (best - mean) / sd
    cdf = 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))
    pdf = np.exp(-0.5 * z ** 2) / math.sqrt(2 * math.pi)
    return (best - mean) * cdf + sd * pdf


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("start", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new directory for this experiment")
    parser.add_argument("--dies", nargs="+", default=["G0", "H0", "H2", "H3", "G2"])
    parser.add_argument("--box", type=float, default=1.2, help="max offset from the start, mm")
    parser.add_argument("--evals", type=int, default=70, help="thermal evaluations, including the start")
    parser.add_argument("--init", type=int, default=8, help="random legal layouts before the model takes over")
    parser.add_argument("--pool", type=int, default=600, help="legal candidates scored by the model each step")
    parser.add_argument("--grid", type=int, choices=(16, 32, 64, 128), default=64)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    if set(args.dies) - set(fast.SPEC["dies"]):
        parser.error("unknown die")

    layout, _ = parse_submission(args.start, fast.SPEC)
    args.output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(args.seed)
    dims = len(args.dies) * 2
    write_json(args.output / "experiment.json",
               {**{k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "kind": "exploration; not an official score", "hotspot": str(fast.HOTSPOT)})

    def place(offset):
        new = {d: list(xy) for d, xy in layout.items()}
        for i, die in enumerate(args.dies):
            new[die] = [round(layout[die][0] + offset[2 * i], 3), round(layout[die][1] + offset[2 * i + 1], 3)]
        return new

    def legal_pool(n, centre=None, spread=None):
        found, tries = [], 0
        while len(found) < n and tries < n * 20:
            tries += 1
            if centre is None:
                x = rng.uniform(-args.box, args.box, dims)
            else:
                x = np.clip(centre + rng.normal(0, spread, dims), -args.box, args.box)
            if fast.legal(place(x))[0]:
                found.append(x)
        return np.array(found).reshape(-1, dims)

    reference_layout, reference_paths = parse_submission(fast.HILL / "examples/baseline/submission.json", fast.SPEC)
    reference = fast.estimate(reference_layout, args.grid, workers=args.workers, paths=reference_paths)
    write_json(args.output / "reference.json", compact(reference))

    xs, ys = [], []
    started = time.monotonic()
    log = (args.output / "search.jsonl").open("w")

    def evaluate(x, how):
        candidate = place(x)
        result = fast.estimate(candidate, args.grid, workers=args.workers)
        value = score(result, reference)
        xs.append(x)
        ys.append(value)
        log.write(json.dumps({"evaluation": len(ys) - 1, "how": how, "score": value,
                              "submission": {"placements_mm": candidate},
                              "elapsed_seconds": round(time.monotonic() - started, 1), **compact(result)}) + "\n")
        log.flush()
        if value <= min(ys):
            write_json(args.output / "submission.json", {"placements_mm": candidate})
        print(f"{len(ys)}/{args.evals} {how:6} score={value:.6f} best={min(ys):.6f} "
              f"GPU={result['gpu']:.2f} HBM={result['hbm']:.2f}", flush=True)

    evaluate(np.zeros(dims), "start")
    for x in legal_pool(args.init):
        evaluate(x, "random")
    while len(ys) < args.evals:
        gp = GP().fit(np.array(xs), np.array(ys))
        best_x = xs[int(np.argmin(ys))]
        # Half the pool explores the whole box, half refines around the best layout so far.
        pool = np.vstack([legal_pool(args.pool // 2), legal_pool(args.pool // 2, best_x, 0.25)])
        mean, sd = gp.predict(pool)
        evaluate(pool[int(np.argmax(expected_improvement(mean, sd, min(ys))))], "model")

    best = int(np.argmin(ys))
    write_json(args.output / "summary.json", {
        "kind": "all-workload exploration result; verify at 64 and 128 with evaluate.py",
        "grid": args.grid, "evaluations": len(ys), "start_score": ys[0],
        "best_score": ys[best], "best_evaluation": best,
        "elapsed_seconds": round(time.monotonic() - started, 1)})
    print(json.dumps({"start_score": ys[0], "best_score": ys[best], "best_evaluation": best}))


if __name__ == "__main__":
    main()
