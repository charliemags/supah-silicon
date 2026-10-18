# Aggressive global search and two-grid refinement

This lane uses actual local Docker HotSpot simulations. Native scores below are screening evidence; promotion requires the root experiment's unchanged pinned evaluator at both grids and all five workloads. The v5 submission remains untouched.

## Completed global experiments

| Experiment | Actual 64-grid screens | Outcome |
|---|---:|---|
| Population DE, linear thermal proposals, and 1–8 mm basin hops | 631 | No minimax gain. Stopped early because broad linear extrapolation was optimistic by roughly 12°C, primarily near cooling-contact boundaries. |
| G0-only Pareto search | 600 | G0 fell to 101.228587°C, but other GPUs exceeded 112°C. Retained as a diagnostic tradeoff, not a winning submission. |
| Adaptive measured-only DE with route-cell repair | 1,000 | GPU 101.20°C / HBM 94.21°C native, with raw minimax 101.202630°C. This provided the successful new placement family. |

The adaptive search preserved favourable G0 thermal-grid phases while moving the other dies across routing cells. It combined differential crossover, group translations, affine expansion, random large perturbations, and occasional whole-grid G0 basin jumps. All candidates passed the original organizer validator before thermal simulation. Across this lane, actual legal die movements reached 11.0316 mm relative to v5.

The geometric gain includes better G0–H0 port alignment: the de0705 candidate increases their horizontal body separation from 4.8807 mm to 4.9739 mm while reducing port misalignment from 0.1192 mm to 0.0260 mm. This uses the same original link-length limit more effectively.

The 1,000-screen winner is frozen at [finalists/de-0936/submission.json](finalists/de-0936/submission.json). Earlier immutable checkpoints and their full raw temperatures are also in `finalists/`. Its native 64-grid control improves the v5 raw minimax from 101.263971°C to 101.202630°C. The rounded native score improves from 0.95816057 to 0.95740671; these are not pinned scores.

## Bounded 128-grid refinement

`joint128.py` completed 21 native128 screens behind 134 actual native64 gates, requiring the starting rounded native64 score and a 0.005°C raw tolerance. It produced no rounded128 improvement. This tight branch was stopped after pinned evaluation showed that de0705 and de0770 both score GPU101.21°C despite their native101.20°C screens.

`joint128_relaxed.py` then received a bounded40-screen budget and was stopped at the user’s wrap-up request after 21 completed native128 screens and 39 actual native64 gates. Its screening gate allows nativeGPU≤101.21°C, the equivalent unchanged normalized HBM limit, and raw64≤start+0.012°C. This is a proposal/selection tolerance informed by measured evaluator differences, not a change to physics or scoring. Promotion still requires pinned64≤0.95753235. Both branches use all three screening workloads; the independent64 winner remains frozen above.

Starting de0936 controls:

| Grid | Native GPU °C | Native HBM °C | Raw minimax °C |
|---|---:|---:|---:|
| 64 | 101.20 | 94.21 | 101.20262957 |
| 128 | 101.54 | 94.31 | 101.53688543 |

Current or final refinement results are recorded in `joint128-relaxed-40/summary.json`, `best.json`, and `completed.json` when finished. The tight branch has an explicit `joint128-60/termination.json`. Immutable improvements appear under each branch’s `finalists/` directory. The root experiment independently rescreens and pins promotion candidates.

## Evidence and constraints

- `manifest.json` in each run records source, baseline, and solver hashes, seeds, budgets, and historical input provenance.
- `search.jsonl` contains every actual screen, raw per-die temperatures, native rounded peaks, coordinates, workload set, and grid.
- `proposals.jsonl` records all MILP proposals, duplicates, and rejected proposals as well as accepted candidates.
- `population-1600/termination.json` documents the early stop and replacement method.
- `analysis.json` records Pareto seeds, placement displacement, and completed screen counts.
- `legality-audit.json` independently revalidates every distinct measured placement using the original organizer validator.

The proposal MILP is an optimization aid, not a replacement evaluator. It was adapted from research-v5/target_milp.py by adding L1 target repair and adjustable search objectives. Hardware, thermal physics, routing/scoring rules, the challenge checkout, and the pinned binary were not changed. The existing search-only high-precision native binary changes only grid-output decimal formatting; its provenance is in research-v4/precision-build.json.

Each Docker job uses three CPUs, the challenge is mounted read-only, and networking is disabled. No Docker socket was exposed to AutoLab and no compute was rented.

## Wrap-up status

All search jobs in this lane are stopped. The root experiment selected fully pinned de0321 (64 score0.95753235;128 score0.96012039). Later native candidates are retained as unverified follow-up, including joint128-relaxed-40/finalists/eval-010, which screens128GPU101.51°C but was not fully pinned before the user ended the experiment. No claim of reaching0.94 is made.
