"""Run the unmodified pinned judge and save a local verification report."""
import argparse
import hashlib
import json
from pathlib import Path

import fast
from verify_high_accuracy import judge


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument("--grid", type=int, choices=(64, 128), default=64)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = judge(args.submission, fast.VENDOR / "hotspot", args.grid,
                   fast.HILL / f"reference_{args.grid}.json")
    result["provenance"] = {
        "verification": "local unmodified organizer judge; not a signed leaderboard submission",
        "submission_sha256": sha(args.submission),
        "files_sha256": {name: sha(fast.HILL / name) for name in (
            "challenge_spec.json", "workloads.json", "verify_high_accuracy.py",
            "geometry.py", "interconnect.py", "run_simulations.py")},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "passed", "grid", "score", "worst_gpu_c", "worst_hbm_c") if k in result}), flush=True)
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
