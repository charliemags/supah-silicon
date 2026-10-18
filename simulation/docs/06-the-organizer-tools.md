# The organizers' two tools, and how we use them

Everything we simulate is built on two repos from the challenge organizers.

| Repo | What it is | Use it for |
|---|---|---|
| [Czaja107/chiplet-thermal-simulator](https://github.com/Czaja107/chiplet-thermal-simulator) | The **scorer**: the power workload patterns, the rule checker and the pinned HotSpot thermal simulator, packaged as the AutoLab hill `beat-the-hotspot` | Official scores. Automated search. Every number we report. |
| [Czaja107/chiplet-thermal-gui](https://github.com/Czaja107/chiplet-thermal-gui) | **Chiplet Thermal Studio**: a desktop app built on the same scorer code | Seeing a layout, dragging chips by hand, drawing wires, editing workloads, comparing runs |

## They compute the same thing

We checked file by file. The challenge spec, the workload power maps, the rule checker (`geometry.py`), the link-heat model (`interconnect.py`) and the workload generator are **byte-for-byte identical** in both repos. The only differences in the simulation runner are where the plotting library is loaded, and that the scorer repo has separate reference temperatures for its 64 and 128 grids. The GUI's authors report that the reference layout reproduces exactly in the GUI: GPU 104.59 °C, memory 97.68 °C, score 1.0.

So a layout scored in one gives the same temperatures in the other.

## What the GUI adds

**Live layout editing.** Drag a chip and the rules are re-checked in about 2 ms. A chip that breaks a rule turns red, and every violation is listed at once.

**Instant heat-source preview.** Overlays show, in about 7 ms per move:
- chip-layer power (the chips plus the inside half of each link port),
- interposer power (wire heat plus the outside half of each port),
- the two combined, in watts per square millimetre,
- the temperature map from the last full simulation.

This shows where the heat is *made*, not yet how hot it gets. That still takes a full HotSpot run.

**Hand-drawn wires.** By default the scorer routes each link along a shortest path. In the GUI you can draw your own path on the 0.5 mm track grid. It's checked live against the link's maximum length and against the shared wire budget (13,500 GB/s·mm across all eight links). Hand-drawn wires are saved as `wire_routes_grid` in the submission file, and the official scorer accepts them.

**Workload editor.** Change any chip's watts or hot-spot weights, add or duplicate workloads, and import or export trace files. Changing anything in the setup is fine for exploring, but the app flags that the score is then no longer comparable with the leaderboard.

**Run history as a two-axis chart.** Every run is a dot: hottest GPU across, hottest memory up, with the reference layout as crosshairs. Anything below and left of both lines beats the reference on both. Click a dot to bring that run back.

**Exports.** "Export for judge" writes a submission file. "Export HotSpot inputs" writes everything needed to simulate elsewhere, which is handy because HotSpot needs Linux.

## Two things from the GUI repo that change our plan

**1. Wire routes are a scoring lever we haven't used yet.** Wire heat goes into the interposer under the chips, along the wire's path. Total link heat is small: about 3–10 W out of 313–399 W per workload in the reference layout. But where it lands matters near the hottest GPU spot. Routing wires away from G0's compute corner (G0 sets the score) is a cheap thing to test. Expected gain: small, probably hundredths to a tenth of a degree. That's worth checking, but not a big lever.

**2. Check close results on a finer grid.** The organizers' own validation note says: "Before fixing prize rankings, run promising and close-scoring layouts at 128 and 256 and freeze the chosen resolution." Port heat is defined at 1 mm scale, finer than the 64-grid cells (about 0.81 × 0.66 mm). So before we submit a final, we re-check our best layouts at 128 × 128, the finalist grid, and make sure the ranking holds.

## Running the GUI

```bash
git clone https://github.com/Czaja107/chiplet-thermal-gui
cd chiplet-thermal-gui
python -m pip install -r requirements.txt   # PySide6, numpy, matplotlib
python -m chiplet_gui
```

Load a layout with **Import layout** (our `layouts/p2/submission.json` works as-is). Without HotSpot, everything except the temperature solve still works. With HotSpot (Linux), runs solve the five workloads in parallel; the authors quote about 85 seconds on a 32-core machine versus about 7 minutes one after another.

## How we split the work

| Job | Tool |
|---|---|
| Official score, final submission | Scorer repo (`verify_high_accuracy.py` / `hills eval`) |
| Thousands of automatic tries | Our `tools/` on top of the scorer repo |
| Understanding *why* a layout is hot, hand tweaks, wire drawing | The GUI |
| Demo visuals | The GUI's overlays and two-axis run chart, plus our heat maps |
