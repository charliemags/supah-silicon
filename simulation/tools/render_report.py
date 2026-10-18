"""Draw a verified floorplan from a saved report without repeating the solver.

Each die's color is its peak across all workloads, not a spatial heat map.
"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle

import fast
from interconnect import route_segments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    submission = json.loads(args.submission.read_text())
    report = json.loads(args.report.read_text())
    if not report.get("passed"):
        parser.error("report must pass the judge")
    digest = hashlib.sha256(args.submission.read_bytes()).hexdigest()
    if report.get("provenance", {}).get("submission_sha256") != digest:
        parser.error("report does not describe this exact submission")
    spec_digest = hashlib.sha256((fast.HILL / "challenge_spec.json").read_bytes()).hexdigest()
    if report["provenance"]["files_sha256"]["challenge_spec.json"] != spec_digest:
        parser.error("report uses a different challenge specification")
    layout = submission["placements_mm"]
    valid, reason, routing = fast.legal(layout, submission.get("wire_routes_grid"))
    if not valid:
        parser.error(reason)
    peaks = {die: max(case["per_die_peak_c"][die] for case in report["workloads"].values())
             for die in layout}
    fig, ax = plt.subplots(figsize=(10, 8), dpi=160)
    fig.patch.set_facecolor("#f4f5f7")
    ax.set_facecolor("#e4e7eb")
    cmap = plt.get_cmap("inferno")
    norm = Normalize(vmin=75, vmax=106)
    for die, (x, y) in layout.items():
        width, height = fast.SPEC["dies"][die]["size_mm"]
        ax.add_patch(Rectangle((x, y), width, height, facecolor=cmap(norm(peaks[die])),
                               edgecolor="#17233a", linewidth=1.4))
        ax.text(x+width/2, y+height/2, f"{die} · {fast.SPEC['dies'][die]['kind']}\n{peaks[die]:.2f} °C",
                ha="center", va="center", fontsize=10, fontweight="bold",
                color="#101928" if peaks[die] > 93 else "white")
    for link, route in routing["routes"].items():
        for (x0, y0), (x1, y1) in route_segments(route, fast.SPEC["port_rule"]["route_grid_pitch_mm"]):
            ax.plot([x0, x1], [y0, y1], color="#197a9e" if link.startswith("P") else "#7f4c9b",
                    linewidth=2.2 if link.startswith("P") else 1.4)
    x, y, width, height = fast.SPEC["thermal_model"]["cooling_contact_rect_mm"]
    ax.add_patch(Rectangle((x, y), width, height, fill=False, linestyle="--", edgecolor="#51677d"))
    ax.set(xlim=(0, 52), ylim=(0, 42), xlabel="Interposer x (mm)", ylabel="Interposer y (mm)", aspect="equal")
    ax.set_title(f"Supah Silicon · {args.submission.parent.name}\n"
                 f"Simulated {report['grid']} × {report['grid']} · score {report['score']:.6f}",
                 loc="left", fontsize=15, pad=16)
    colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, shrink=.78, pad=.025)
    colorbar.set_label("Each die's worst temperature across five workloads (°C)")
    fig.text(.08, .025, "4 GPU + 4 HBM · cyan: 600 GB/s links · purple: 300 GB/s links\n"
             "Dashed boundary: fixed cooling contact. Colors summarize die peaks; this is not a spatial heat map.",
             fontsize=9, color="#35465b")
    fig.tight_layout(rect=(0, .07, 1, 1))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output)
    plt.close(fig)
    print(args.output)


if __name__ == "__main__":
    main()
