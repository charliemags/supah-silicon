"""Bounded placement search with checkpointing and all-workload finalist screening.

Every result is an exploration estimate. Use evaluate.py with the pinned Linux
binary for local judge verification, including the 128-grid finalist check.
"""
import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import fast
from climb import propose
from verify_submission import parse_submission


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def score(result, reference):
    ambient = fast.SPEC["thermal_model"]["ambient_c"]
    return max((result[k] - ambient) / (reference[k] - ambient) for k in ("gpu", "hbm"))


def key(submission):
    return json.dumps(submission, sort_keys=True, separators=(",", ":"))


def compact(result):
    return {k: v for k, v in result.items() if k != "grids"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("start", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new directory for this experiment")
    parser.add_argument("--evals", type=int, default=80, help="search evaluations, including seed")
    parser.add_argument("--max-proposals", type=int, default=20000)
    parser.add_argument("--grid", type=int, choices=(16, 32, 64, 128), default=64)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--finalists", type=int, default=3)
    parser.add_argument("--screen", nargs="+", default=["skewed_compute", "memory_stream"])
    parser.add_argument("--step", type=float, default=0.35)
    parser.add_argument("--temperature", type=float, default=0.002)
    parser.add_argument("--focus", nargs="+", help="die IDs to move during 70%% of proposals")
    args = parser.parse_args()
    if min(args.evals, args.max_proposals, args.workers, args.finalists) < 1 or args.step <= 0 or args.temperature < 0:
        parser.error("budgets, workers and step must be positive; temperature must be nonnegative")
    if set(args.screen) - set(fast.PORTABLE["workloads"]):
        parser.error("unknown screening workload")
    if args.focus and set(args.focus) - set(fast.SPEC["dies"]):
        parser.error("unknown focus die")
    layout, paths = parse_submission(args.start, fast.SPEC)
    valid, reason, _ = fast.legal(layout, paths)
    if not valid:
        parser.error(f"invalid starting layout: {reason}")
    # Refuse to mix runs or silently overwrite another experiment.
    args.output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(args.seed)
    manifest = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    manifest.update(kind="exploration; not an official score",
                    hotspot_sha256=hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
                    inputs_sha256={name: hashlib.sha256((fast.HILL / name).read_bytes()).hexdigest()
                                   for name in ("challenge_spec.json", "workloads.json")})
    write_json(args.output / "experiment.json", manifest)
    reference_layout, reference_paths = parse_submission(fast.HILL / "examples/baseline/submission.json", fast.SPEC)
    reference = fast.estimate(reference_layout, args.grid, workers=args.workers, paths=reference_paths)
    if not reference["passed"]:
        raise RuntimeError(f"Reference failed: {reference}")
    write_json(args.output / "reference.json", compact(reference))
    current = {"placements_mm": layout}
    if paths:
        current["wire_routes_grid"] = paths
    seen = set()
    records = []
    current_score = math.inf
    best_score = math.inf
    proposals = 0
    started = time.monotonic()
    with (args.output / "search.jsonl").open("w") as log:
        while len(records) < args.evals and proposals < args.max_proposals:
            if not records:
                candidate = current
            else:
                fraction = len(records) / args.evals
                step = args.step * (0.15 ** fraction)
                if args.focus and rng.random() < 0.7:
                    placement = {d: list(xy) for d, xy in current["placements_mm"].items()}
                    die = rng.choice(args.focus)
                    placement[die] = [round(x + rng.gauss(0, step), 3) for x in placement[die]]
                else:
                    placement = propose(current["placements_mm"], step, rng)
                # Moving dies invalidates old route endpoints. Re-route automatically.
                candidate = {"placements_mm": placement}
            proposals += 1
            identity = key(candidate)
            if identity in seen:
                continue
            seen.add(identity)
            valid, _, _ = fast.legal(candidate["placements_mm"], candidate.get("wire_routes_grid"))
            if not valid:
                continue
            result = fast.estimate(candidate["placements_mm"], args.grid, workers=args.workers,
                                   workloads=args.screen, paths=candidate.get("wire_routes_grid"))
            value = score(result, reference)
            temperature = max(1e-8, args.temperature * (1 - len(records) / args.evals))
            accepted = value <= current_score or rng.random() < math.exp(min(0, (current_score-value)/temperature))
            record = {"evaluation": len(records), "submission": candidate,
                      "screen_score": value, "accepted": accepted,
                      "elapsed_seconds": round(time.monotonic()-started, 2), **compact(result)}
            records.append(record)
            log.write(json.dumps(record) + "\n")
            log.flush()
            if accepted:
                current, current_score = candidate, value
            if value < best_score:
                best_score = value
                write_json(args.output / "screen-best.json", candidate)
            print(f"{len(records)}/{args.evals}: screen={value:.6f} best={best_score:.6f} "
                  f"GPU={result['gpu']:.2f} HBM={result['hbm']:.2f}", flush=True)
    # Include the starting design so a screening regression is never promoted.
    shortlist = [records[0]]
    for record in sorted(records, key=lambda r: r["screen_score"]):
        if all(key(record["submission"]) != key(r["submission"]) for r in shortlist):
            shortlist.append(record)
        if len(shortlist) >= args.finalists + 1:
            break
    finalists = []
    for index, record in enumerate(shortlist):
        submission = record["submission"]
        result = fast.estimate(submission["placements_mm"], args.grid, workers=args.workers,
                               paths=submission.get("wire_routes_grid"))
        value = score(result, reference)
        item = {"candidate": index, "submission": submission, "all_workload_proxy_score": value, **compact(result)}
        finalists.append(item)
        write_json(args.output / f"candidate-{index}.json", submission)
        write_json(args.output / f"candidate-{index}-estimate.json", item)
        print(f"Finalist {index}: all-workload estimate={value:.6f}", flush=True)
    best = min(finalists, key=lambda r: r["all_workload_proxy_score"])
    write_json(args.output / "submission.json", best["submission"])
    write_json(args.output / "summary.json", {
        "kind": "all-workload exploration result; verify at 64 and 128 with evaluate.py",
        "grid": args.grid, "evaluations": len(records), "proposals": proposals,
        "seed_score": finalists[0]["all_workload_proxy_score"],
        "best_score": best["all_workload_proxy_score"], "best_candidate": best["candidate"],
        "elapsed_seconds": round(time.monotonic()-started, 2),
    })


if __name__ == "__main__":
    main()
