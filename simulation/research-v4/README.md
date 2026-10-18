# Placement iteration v4: verified improvement

The saved [submission.json](submission.json) beats the requested **0.95979394** threshold with a pinned 64-grid score of **0.95966830**. **The 0.95 target was not reached.** The v2 incumbent, signed report, original verification reports, challenge inputs and pinned evaluator remain byte-for-byte unchanged; see [audit.json](audit.json).

## Pinned results

Both candidate reports use the original pinned evaluator and all five workloads. Reference temperatures are matched separately to each grid. These are local verification reports, not new signed AutoLab results or leaderboard submissions.

| Grid | Incumbent score | Candidate score | GPU maximum °C, old → new | HBM maximum °C, old → new |
|---|---:|---:|---:|---:|
| 64 | 0.95991959 | **0.95966830** | 101.40 → 101.38 | 94.16 → 94.19 |
| 128 | 0.96200150 | **0.96175069** | 101.71 → 101.69 | 94.24 → 94.28 |

Reports: [64 grid](verification-64.json), [128 grid](verification-128.json), [full comparison](comparison.json). The HBM column explicitly records any tradeoff; the benchmark score is the maximum normalized temperature rise, not an average.

At 64, 0.95 requires GPU ≤100.61 °C and HBM ≤94.04 °C at the judge's two-decimal precision. This candidate still needs 0.77 °C GPU cooling and 0.15 °C HBM cooling. These experiments do not prove that 0.95 is impossible.

## What worked

A quadratic response model with an adaptive trust region found coordinated changes that the prior rounded-score searches missed. The first pinned improvement tied 0.95979394. A subsequent constrained finite-difference search and precision rescreen resolved small differences between candidates that all printed the same native temperature. A final memory-focused sweep moved H2 and adjusted neighboring dies to recover HBM cooling while retaining the verified GPU improvement.

The additional search build changes **one output format**, from two decimal digits to eight, in the native solver's steady-grid text writer. It changes no equations, material data, hardware, cooling, heat inputs or judge scoring. [Build provenance](precision-build.json) records the exact replacement and hashes; its original source hash matches the pinned source checkout. Each precision search calibrated its rounded per-die peaks against the existing native binary. Unrounded numbers guide exploration only; all scores in the table above come from the unchanged pinned binary.

The frozen route-cell constraints include exact port access lengths and route budgets; every simulated candidate also passes the unmodified organizer validator. Larger coordinated neighbor projections, random connected-group moves and a fine G0 basin sweep were tested. Broad random, pattern and late gradient searches were stopped after plateaus. The independent [search audit](search-audit.json) revalidated all 3,628 unique logged submissions, including measured die movements as large as 2.733 mm from the incumbent.

Exhaustive equal-length routing tests were run at both the initial seed and the improved placement: 129 single-link alternatives per placement, plus controls and a combined-route candidate. None improved the primary native score over its corresponding control. The winner retains automatic routing.

## Placement and legality

| Die | New x mm | New y mm | Δx mm | Δy mm |
|---|---:|---:|---:|---:|
| G0 | 3.981938 | 3.438952 | -0.000062 | -0.010048 |
| G1 | 36.609876 | 3.687866 | +0.069876 | -0.027134 |
| G2 | 37.214995 | 29.016908 | +0.013995 | -0.006092 |
| G3 | 10.099897 | 29.019907 | +0.073897 | +0.017907 |
| H0 | 20.298000 | 3.649914 | +0.002000 | -0.039086 |
| H1 | 37.016908 | 15.583001 | -0.003092 | +0.043001 |
| H2 | 25.698000 | 29.166908 | +0.114000 | +0.020908 |
| H3 | 6.999914 | 17.420924 | -0.019086 | +0.022924 |

Weighted route length is **13499.70 / 13500.00 GB/s·mm**. Minimum die separation is **1.016995 mm**. All individual reach, port capacity, package-edge and separation checks passed. Hardware and die orientations are unchanged.

Submission SHA-256: `87f67547b68a27c63679ca4fd90147430400a1d5303859c2a0c7413f12c8afe4`.

## All five workloads at both grids

| Grid | Workload | GPU peak °C, incumbent → candidate | HBM peak °C, incumbent → candidate |
|---|---|---:|---:|
| 64 | tensor_training | 101.13 → 101.26 | 84.44 → 85.85 |
| 64 | skewed_compute | 101.40 → 101.38 | 78.39 → 80.01 |
| 64 | attention_decode | 83.72 → 83.70 | 76.84 → 77.25 |
| 64 | memory_stream | 93.52 → 93.50 | 94.16 → 94.19 |
| 64 | mixed_serving | 91.37 → 91.34 | 78.75 → 79.12 |
| 128 | tensor_training | 101.17 → 101.38 | 85.49 → 85.51 |
| 128 | skewed_compute | 101.71 → 101.69 | 79.64 → 79.63 |
| 128 | attention_decode | 83.89 → 83.86 | 77.37 → 77.40 |
| 128 | memory_stream | 93.64 → 93.56 | 94.24 → 94.28 |
| 128 | mixed_serving | 91.47 → 91.43 | 79.20 → 79.25 |

## Experiment accounting

| Experiment | Logged candidate evaluations | Workload solves | Status |
|---|---:|---:|---|
| directed | 10 | 50 | completed |
| g0-polish | 267 | 267 | completed |
| memory-polish | 107 | 321 | completed |
| pattern | 355 | 1065 | stopped after plateau |
| placement | 859 | 2577 | stopped after plateau |
| placement-from-quadratic | 551 | 1653 | stopped after plateau |
| precise | 593 | 1779 | stopped after plateau |
| precise-coarse-gradient | 377 | 1131 | stopped after plateau |
| precision-rescreen | 261 | 261 | completed |
| quadratic | 256 | 768 | completed |
| routes | 131 | 135 | completed |
| routes-finalist | 131 | 135 | completed |

These counts include repeated controls and precision rescreens, and exclude inherited histories, additional original-native calibration controls and pinned verification. Every retained observation and submission is in its experiment's `search.jsonl`; manifests retain seeds, source/input hashes and budgets. Early-stopped searches retain their actual completed counts and termination reason.

## Reproduce verification

From the repository root, with the existing local images:

```sh
./simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v4/submission.json --grid 64 --output simulation/results/v4-recheck-64.json
./simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v4/submission.json --grid 128 --output simulation/results/v4-recheck-128.json
```

The launcher checks challenge revision `8948d9bc5e3aa041dcd1ff8a5a63ed6200d04d81`, uses local network-disabled containers, and mounts `/challenge` read-only. It does not mount a Docker socket. No paid compute or AutoLab connection was used. To reproduce the search-only output precision build, run `simulation/research-v4/build_precision.py` through the launcher's `native` mode; then use `precise_search.py` with a new output directory and the saved manifest arguments.
