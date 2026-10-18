# Running a simulation yourself

## Mac and cross-platform workflow

The new [Supah design workflow](07-supah-design-workflow.md) runs the exact Linux
scorer through Docker, including on Apple Silicon. Start with `./simulation/run
setup` from the repository root. The direct commands below are for Linux/WSL.

## What you need

- A Linux machine (or Windows with WSL). The bundled HotSpot program is a pinned Linux build for Intel/AMD processors. It won't run natively on a Mac, including Apple Silicon.
- Python 3 with `numpy` (and `matplotlib` for pictures).
- The organizer's simulator:

```bash
git clone https://github.com/Czaja107/chiplet-thermal-simulator
cd chiplet-thermal-simulator
```

## Step 1: write a layout

A layout is a small JSON file with the lower-left corner of each chip, in millimetres:

```json
{
  "placements_mm": {
    "G0": [4.869, 3.289],  "H0": [18.619, 1.773],
    "G1": [32.573, 3.089], "H1": [31.232, 15.059],
    "G2": [31.122, 27.751],"H2": [18.619, 29.757],
    "G3": [5.356, 27.792], "H3": [5.36, 14.975]
  }
}
```

That one is our current best (official score 0.9873).

## Step 2: check the rules (instant)

```bash
python3 verify_submission.py my_layout.json
```

This catches overlapping chips, links that are too long, or not enough edge space for ports, in under a millisecond. Always do this first; it saves a wasted simulation.

## Step 3: simulate and score

```bash
python3 verify_high_accuracy.py my_layout.json \
  --hotspot vendor/HotSpot/hotspot --grid 64 --output result.json
```

On a 2-core machine this takes about 94 seconds. The output shows the hottest GPU, the hottest memory, the score, and a per-workload, per-chip breakdown, so you can see which chip and which workload set the score.

For the finalist check use `--grid 128`. Expect this to take many minutes.

## Step 4 (optional): use AutoLab hills for signed, tracked scores

The repo is also an AutoLab "hill" named `beat-the-hotspot`. With the `hills` command-line tool:

```bash
hills eval my_layout_folder -H beat-the-hotspot
```

The folder must contain `submission.json`. Every score is logged and signed, which is how we keep an honest record of every attempt.

## Prefer clicking? Use the GUI

The organizers' [Chiplet Thermal Studio](https://github.com/Czaja107/chiplet-thermal-gui) does all of the above in a window: drag chips, see rule breaks live, draw wires, run HotSpot and compare runs. It uses the same scorer code, so the numbers match. See [the organizer tools guide](06-the-organizer-tools.md).

## Reading the result

The most useful part is the breakdown. For example, our best layout:

| Workload | Hottest GPU | Hottest memory |
|---|---|---|
| tensor_training | 101.82 °C | 85.22 °C |
| **skewed_compute** | **103.58 °C** (G0) | 80.23 °C |
| attention_decode | 85.16 °C | 77.64 °C |
| **memory_stream** | 94.23 °C | **95.17 °C** |
| mixed_serving | 93.42 °C | 80.66 °C |

So the GPU score is set by G0 during `skewed_compute` (G0 draws 104 W there), and the memory score by `memory_stream`. Those two workloads are where improvements have to come from.
