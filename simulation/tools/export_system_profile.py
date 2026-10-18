"""Carry verified package results into Track 1 without inventing system metrics."""
import argparse
import json
from pathlib import Path


PROXIES = {
    "memory_stream": ["record scans", "retrieval candidate reads"],
    "attention_decode": ["AI decoding and active context reads"],
    "mixed_serving": ["concurrent interactive and background work"],
    "tensor_training": ["dense compute stress test; not evidence of a Supah training workload"],
    "skewed_compute": ["uneven compute stress test"],
}


def export(report):
    if not report.get("passed") or not report.get("hotspot_sha256") or not report.get("provenance"):
        raise ValueError("Expected a successful evaluate.py report with provenance")
    if report.get("grid") not in (64, 128) or set(report.get("workloads", {})) != set(PROXIES):
        raise ValueError("Expected all five benchmark workloads at grid 64 or 128")
    return {
        "schema_version": 1,
        "status": "synthetic package simulation; not a measured Supah appliance",
        "source_grid": report["grid"],
        "source_provenance": report["provenance"],
        "hotspot_sha256": report["hotspot_sha256"],
        "benchmark_score": report["score"],
        "workloads": {name: {
            "supah_activity_hypotheses": PROXIES[name],
            "simulated_package_power_w": case["total_w"],
            "simulated_gpu_peak_c": case["gpu_peak_c"],
            "simulated_hbm_peak_c": case["hbm_peak_c"],
            "task_duration_s": None, "tasks_per_second": None,
            "joules_per_task": None,
        } for name, case in report["workloads"].items()},
        "system_measurements_needed": [
            "Representative Supah/Muni request traces, with sensitive content removed",
            "Time and bytes moved in ingest, filtering, retrieval, ranking and inference",
            "Model and context sizes, memory capacity, concurrency and output quality",
            "Idle and wall power, storage/network power, cooling overhead and utilization",
            "Latency distributions and failure/recovery requirements",
        ],
        "interpretation": "The fixed synthetic cooler and package power do not establish appliance cooling cost, PUE or task energy.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = export(json.loads(args.report.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
