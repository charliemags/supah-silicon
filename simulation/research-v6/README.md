# Global placement optimization, round 6

The saved submission improves the preserved best under the unchanged pinned evaluator. The 0.94 target was not reached. This is the best completed two-grid pinned candidate at the user-requested wrap-up; remaining searches and an unfinished additional verification were stopped.

## Pinned results: all five workloads

| Grid | Preserved v5 | New candidate | Change | GPU °C, old → new | HBM °C, old → new |
|---|---:|---:|---:|---:|---:|
| 64 | 0.95828622 | **0.95753235** | -0.00075387 | 101.27 → 101.21 | 94.27 → 94.21 |
| 128 | 0.96024580 | **0.96012039** | -0.00012541 | 101.57 → 101.56 | 94.36 → 94.31 |

[Submission](submission.json) · [Pinned 64](verification-64.json) · [Pinned 128](verification-128.json) · [Comparison](comparison.json) · [Integrity audit](audit.json)

These are local pinned verification results. Native screening values were used to select candidates, never substituted for pinned scores.

## Experiments

The useful breakthrough came from adaptive differential evolution with mixed-integer repair of placement and endpoint routing cells. It moved G0 together with its neighbors into a better region after broad surrogate-guided steps failed. A separate local minimax search refined the new region.

The independent topology search tested concave, folded, inverted and offset arrangements. One new topology cooled G0 at exactly its preserved coordinates, but overheated another GPU; it was rejected. Fully contacted layouts also lost because of tighter thermal coupling. The topology model generated 111 exact-valid seeds from 26,240 geometry proposals; geometry proposals are not counted as thermal simulations.

All 84 shortest S0 paths at the preserved placement were tested. The best lowered raw G0 by only 0.00015689°C and tied the pinned 64 score. It was not promoted. Explicit paths cannot change mandatory endpoints or facing edges; the automatic router already finds a shortest path. Longer routes cannot fit the preserved placement’s remaining weighted-route slack.

This round logged 4,494 completed native candidate evaluations (13,378 workload solves), including controls and rescreens. The independent audit replayed 4,362 unique submissions through the original validator. Per-experiment counts and hashes are in audit.json.

The original incumbent, research-v5 source files and saved results, hardware, physics, scoring, workloads and pinned evaluator remain unchanged. All 139 protected hashes match. All computation stayed in local Docker with networking disabled and the challenge mounted read-only. No AutoLab Docker socket connection or rented compute was used.

A later native128 candidate is retained at global/joint128-relaxed-40/finalists/eval-010/submission.json. Its native screening score is 0.95949335, but pinned verification is incomplete, so it was not promoted. See selection-status.json for the selection cutoff.

The search-only precise native build changes one output format string to expose additional temperature digits; its provenance is in ../research-v4/precision-build.json. Pinned verification uses the original binary.

## Remaining gap

At grid 64, a 0.94 score requires GPU ≤99.81°C and HBM ≤93.31°C at the evaluator’s output precision. These experiments did not reach those temperatures and do not prove the target impossible.

## All workload peaks

| Grid | Workload | GPU °C, old → new | HBM °C, old → new |
|---|---|---:|---:|
| 64 | tensor_training | 101.20 → 101.10 | 85.34 → 85.30 |
| 64 | skewed_compute | 101.27 → 101.21 | 79.42 → 79.41 |
| 64 | attention_decode | 83.97 → 83.89 | 77.41 → 77.35 |
| 64 | memory_stream | 93.65 → 93.56 | 94.27 → 94.21 |
| 64 | mixed_serving | 91.49 → 91.48 | 79.27 → 79.20 |
| 128 | tensor_training | 101.29 → 101.24 | 85.72 → 85.68 |
| 128 | skewed_compute | 101.57 → 101.56 | 79.86 → 79.84 |
| 128 | attention_decode | 84.00 → 83.94 | 77.58 → 77.50 |
| 128 | memory_stream | 93.72 → 93.60 | 94.36 → 94.31 |
| 128 | mixed_serving | 91.52 → 91.54 | 79.43 → 79.34 |

Selected source: `simulation/research-v6/global/finalists/de-0321`.

Submission SHA-256: `30d8038d5b0c92bd819aa4cc132eed10630d9a479bd576fd4b35ff38b5942d46`.

## Reproduce verification

```sh
./simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v6/submission.json --grid 64 --output simulation/results/v6-recheck-64.json
./simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v6/submission.json --grid 128 --output simulation/results/v6-recheck-128.json
```
