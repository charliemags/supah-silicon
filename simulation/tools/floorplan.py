"""Draw clean floorplans (no heat) of chip layouts: dies, compute hot spots, routed wires, cooling area."""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
sys.path.insert(0, str(Path(__file__).parent))
import fast

SPEC = fast.SPEC
W, H = SPEC["interposer_mm"]
GPU_FILL, HBM_FILL = "#f2c9b4", "#c9dde8"
GPU_EDGE, HBM_EDGE = "#a8431c", "#2f6f8f"
LINK_COLORS = {"P": "#1d2226", "S": "#7a5aa6"}


def draw(ax, layout, title):
    ok, reason, routing = fast.legal(layout)
    assert ok, reason
    ax.add_patch(Rectangle((0, 0), W, H, facecolor="#eef0ec", edgecolor="#5b646b", lw=1.5))
    cx, cy, cw, ch = SPEC["thermal_model"]["cooling_contact_rect_mm"]
    ax.add_patch(Rectangle((cx, cy), cw, ch, fill=False, ls="--", lw=1.1, ec="#2f6f8f"))
    ax.text(cx + 0.4, cy + ch - 0.4, "well-cooled area (44 × 34 mm)", fontsize=7, color="#2f6f8f", va="top")
    for d, (x, y) in layout.items():
        w, h = SPEC["dies"][d]["size_mm"]
        g = d[0] == "G"
        ax.add_patch(Rectangle((x, y), w, h, facecolor=GPU_FILL if g else HBM_FILL,
                               edgecolor=GPU_EDGE if g else HBM_EDGE, lw=1.6, zorder=2))
        ax.text(x + w / 2, y + h / 2 + 0.9, d, ha="center", va="center", fontsize=12, weight="bold", zorder=4,
                color=GPU_EDGE if g else HBM_EDGE)
        ax.text(x + w / 2, y + h / 2 - 1.1, f"({x:.1f}, {y:.1f})", ha="center", va="center", fontsize=7, color="#3a3f44", zorder=4)
        if g:
            hx, hy = SPEC["dies"][d]["compute_hotspot_xy"]
            ax.add_patch(Circle((x + hx * w, y + hy * h), 0.75, color="#d1361b", zorder=3, alpha=0.9))
    for lid, rt in routing["routes"].items():
        pts = [rt["from_port"]] + [((i + 0.5) * 0.5, (j + 0.5) * 0.5) for i, j in rt["path_grid"]] + [rt["to_port"]]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=LINK_COLORS[lid[0]], lw=2.4 if lid[0] == "P" else 1.6, zorder=5, solid_capstyle="round")
        mx, my = pts[len(pts) // 2]
        ax.text(mx, my, f"{lid} {rt['route_length_mm']:.1f}mm", fontsize=6.5, zorder=6, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.set_xlim(-0.5, W + 0.5); ax.set_ylim(-0.5, H + 0.5); ax.set_aspect("equal")
    ax.set_xlabel("mm"); ax.set_ylabel("mm")
    used, lim = routing["weighted_route_gb_s_mm"], routing["route_limit_gb_s_mm"]
    ax.set_title(f"{title}\nwire budget used: {used:,.1f} of {lim:,.0f} GB/s·mm", fontsize=11)


if __name__ == "__main__":
    pairs = [(json.loads(Path(f).read_text()), t) for f, t in zip(sys.argv[2::2], sys.argv[3::2])]
    fig, axes = plt.subplots(1, len(pairs), figsize=(7.2 * len(pairs), 6.6), dpi=130)
    axes = [axes] if len(pairs) == 1 else axes
    for ax, (d, t) in zip(axes, pairs):
        draw(ax, d.get("placements_mm", d.get("random_layout", {}).get("placements_mm")), t)
    fig.text(0.5, 0.015, "Orange = GPU (11.5 × 10.5 mm), blue = HBM memory (10.5 × 10.2 mm), red dot = GPU compute hot spot, "
             "black = 600 GB/s main link, purple = 300 GB/s side link. Numbers in brackets = chip corner position (mm).",
             ha="center", fontsize=8.5, color="#3a3f44")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(sys.argv[1]); print("wrote", sys.argv[1])
