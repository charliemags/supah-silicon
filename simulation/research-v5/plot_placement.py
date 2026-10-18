"""Render the actual incumbent and frozen candidate geometry, without rescaling."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.cache/challenge'))
from geometry import validate_layout
spec = json.loads((ROOT / '.cache/challenge/challenge_spec.json').read_text())
paths = [ROOT / 'simulation/layouts/supah-v2/submission.json', OUT / 'finalists/relocated/submission.json']
fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
for ax, path, title in zip(axes, paths, ['Preserved incumbent', 'Relocated candidate']):
    sub = json.loads(path.read_text())
    lay = sub['placements_mm']
    routes = validate_layout(spec, lay, wire_routes_grid=sub.get('wire_routes_grid', {}))
    ax.add_patch(Rectangle((0, 0), 52, 42, facecolor='#f3f4f6', edgecolor='#475569'))
    cx, cy, cw, ch = spec['thermal_model']['cooling_contact_rect_mm']
    ax.add_patch(Rectangle((cx, cy), cw, ch, facecolor='#ecfdf5', edgecolor='#059669', linestyle='--', linewidth=1.2))
    for r in routes['routes'].values():
        pts = [r['from_port']] + [[.5*x+.25, .5*y+.25] for x, y in r['path_grid']] + [r['to_port']]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color='#64748b', linewidth=1.2, zorder=2)
    for d, (x, y) in lay.items():
        w, h = spec['dies'][d]['size_mm']
        color = '#2563eb' if d.startswith('G') else '#d97706'
        ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor='white', alpha=.88, zorder=3))
        ax.text(x+w/2, y+h/2, d, ha='center', va='center', color='white', weight='bold', fontsize=12, zorder=4)
    ax.set(xlim=(-1, 53), ylim=(-1, 43), aspect='equal', xlabel='x (mm)', ylabel='y (mm)', title=title)
    ax.spines[['top', 'right']].set_visible(False)
fig.suptitle('Same hardware and cooling contact; changed placement and legal routes', fontsize=14)
fig.savefig(OUT / 'placement-comparison.png', dpi=180)
plt.close(fig)
