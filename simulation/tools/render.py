"""Render a Supah-Silicon layout as a heat map: worst-case temperature per cell across
workloads, die outlines with peak temps, the well-cooled contact area, and the links."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
sys.path.insert(0, str(Path(__file__).parent))
import fast

SPEC = fast.SPEC
W, H = SPEC["interposer_mm"]
PAIR_COLORS = {"0": "#4cc9f0", "1": "#f72585", "2": "#b5e48c", "3": "#ffd166"}


def die_size(name):
    return SPEC["dies"][name]["size_mm"]


def render(layout, res, path, title="", vmin=60, vmax=106):
    grids = res["grids"]
    worst = np.max(np.stack(list(grids.values())), axis=0)
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=110)
    im = ax.imshow(worst, extent=[0, W, 0, H], origin="upper", cmap="inferno", vmin=vmin, vmax=vmax)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.set_label("worst-case °C (all workloads)")
    x0, y0, w, h = SPEC["thermal_model"]["cooling_contact_rect_mm"]
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, ls="--", lw=1.2, ec="white", alpha=0.7))
    peak = {}
    for p in res["peaks"].values():
        for d, t in p.items():
            peak[d] = max(peak.get(d, -1), t)
    centers = {}
    for d, (x, y) in layout.items():
        sw, sh = die_size(d)
        ax.add_patch(Rectangle((x, y), sw, sh, fill=False, lw=2.2, ec=PAIR_COLORS[d[1]]))
        centers[d] = (x + sw / 2, y + sh / 2)
        ax.text(x + sw / 2, y + sh / 2, f"{d}\n{peak[d]:.1f}°", ha="center", va="center",
                color="white", fontsize=9, weight="bold")
    for l in SPEC["links"]:
        (ax1, ay1), (bx, by) = centers[l["from"]], centers[l["to"]]
        ax.plot([ax1, bx], [ay1, by], color="white", lw=1.6 if l["id"][0] == "P" else 0.9,
                ls="-" if l["id"][0] == "P" else ":", alpha=0.55)
    gpu = max(v for k, v in peak.items() if k[0] == "G"); hbm = max(v for k, v in peak.items() if k[0] == "H")
    ax.set_title(f"{title}  GPU max {gpu:.2f}°C · HBM max {hbm:.2f}°C", fontsize=10)
    ax.set_xlabel("mm"); ax.set_ylabel("mm"); ax.set_xlim(0, W); ax.set_ylim(0, H)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    lay = json.loads(Path(sys.argv[1]).read_text())["placements_mm"]
    grid = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    r = fast.estimate(lay, grid)
    render(lay, r, sys.argv[2], title=Path(sys.argv[1]).parent.name)
    print("wrote", sys.argv[2])
