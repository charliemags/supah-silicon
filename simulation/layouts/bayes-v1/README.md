# Bayes v1

Supah v1 refined by Bayesian optimization. Same four GPU dies, four HBM stacks,
links, power maps and cooler; only five die positions changed.

## Result

| Mesh | Design | Score ↓ | Worst GPU | Worst HBM |
|---|---|---:|---:|---:|
| 64 × 64 | Reference | 1.000000 | 104.59 °C | 97.68 °C |
| 64 × 64 | Supah v1 | 0.981153 | 103.09 °C | 95.56 °C |
| 64 × 64 | **Bayes v1** | **0.971856** | **102.35 °C** | **95.50 °C** |
| 128 × 128 | Reference | 1.000000 | 104.74 °C | 97.70 °C |
| 128 × 128 | Supah v1 | 0.981063 | 103.23 °C | 95.61 °C |
| 128 × 128 | **Bayes v1** | **0.974668** | **102.72 °C** | **95.52 °C** |

At finalist resolution the score is 0.65% lower than Supah v1: GPU 0.51 °C and
HBM 0.09 °C cooler. The gain is smaller at 128 than at 64 (0.93%), as the
workflow guide warns.

**These are native-binary estimates, not judge reports.** They come from HotSpot
built natively on Apple Silicon from the pinned source (see
[the workflow](../../docs/07-supah-design-workflow.md)). The same build reproduced
the official numbers exactly for the reference at 64 (104.59 / 97.68) and for
Supah v1 at both grids (103.09 / 95.56 at 64, 103.23 / 95.61 / 0.981063 at 128;
see `estimate-128.json`). Run `./simulation/run score` at 64 and 128 before
treating this as a submission.

![Worst-case heat map](heatmap.png)

## What changed

| Die | Supah v1 (x, y) | Bayes v1 (x, y) | Moved |
|---|---|---|---|
| G0 | 4.313, 2.841 | 3.150, 3.621 | −1.16, +0.78 |
| H0 | 19.052, 2.176 | 18.511, 2.920 | −0.54, +0.74 |
| G2 | 30.966, 27.939 | 32.166, 28.414 | +1.20, +0.48 |
| H2 | 18.413, 29.887 | 19.613, 28.687 | +1.20, −1.20 |
| H3 | 6.072, 15.609 | 6.270, 16.565 | +0.20, +0.96 |

G1, G3 and H1 were not searched. G0, which sets the GPU score in
skewed_compute, moves further into its corner with H0 following.

The GPU and HBM score ratios are now nearly equal (0.9719 and 0.9700 at 64), so
further gains need both to cool together.

## How the search works

`tools/bayes.py` fits a Gaussian process (Matern 5/2 kernel, length scale and
noise chosen by marginal likelihood) to every result so far, then evaluates the
legal candidate with the highest expected improvement. Candidates are offsets of
the chosen dies within a box around the start; illegal ones are dropped by the
instant rule check before the model sees them. Every evaluation runs all five
workloads, so there is no screening mismatch.

This run: start Supah v1, dies G0 H0 H2 H3 G2, box ±1.2 mm, 8 random starts
then 62 model-guided picks, 70 evaluations at 64 × 64, seed 11, about 27 minutes
on an Apple M4. The full record is in `search/`.

Three offsets hit the ±1.2 mm box edge (G2 x, H2 x and H2 y), so a wider box,
or including all eight dies, is the obvious next run.

## Reproduce

Build HotSpot natively as in `docs/07`, then from the repository root:

```sh
CRYO_HILL="$PWD/.cache/challenge" CRYO_HOTSPOT=/absolute/path/to/native/hotspot \
  python3 simulation/tools/bayes.py simulation/layouts/supah-v1/submission.json \
  --output simulation/experiments/bayes-1 --evals 70 --seed 11
./simulation/run score simulation/layouts/bayes-v1/submission.json --grid 128 --output simulation/results/bayes-v1-128.json
```
