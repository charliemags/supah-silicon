# Reproduce the verified placement

Run from the repository root with Docker running. No AutoLab connection is
needed. Setup downloads the pinned challenge and builds local images;
simulation containers run with networking disabled.

```sh
./simulation/run setup
./simulation/run validate simulation/research-v6/submission.json
./simulation/run score simulation/research-v6/submission.json --grid 64 --output simulation/results/v6-recheck-64.json
./simulation/run score simulation/research-v6/submission.json --grid 128 --output simulation/results/v6-recheck-128.json
```

Expected pinned scores are 0.95753235 at 64 and 0.96012039 at 128. Every
verification runs all five workloads. The original evaluator binary and
benchmark rules must remain unchanged.

## Continue native search

The faster search image and its output-precision binary are intentionally not
committed. Build them before running research scripts:

```sh
./simulation/run setup-search
./simulation/research-v3/run native simulation/research-v6/setup_precision.py
```

This changes only the native solver's temperature output from two to eight
decimal places. It does not alter equations, inputs, scoring, or the pinned
binary. The new build manifest is written to ignored
`.cache/hotspot-precise-build.json`; the historical
`research-v4/precision-build.json` remains untouched. Use this setup helper
instead of rerunning the archived v4 builder, which writes its historical
manifest location.

The successful population search is in `global/de_search.py`; the later
restart in `topology/de_restart.py` accepts `--start` for an explicit seed.
Inspect each script's `--help`, use a new output directory, and begin with the
verified `research-v6/submission.json`. Saved candidates under other research
directories are experiments, not automatic replacements for the selected file.

Native scores are screening estimates. A candidate may only be promoted after
the original pinned evaluator verifies it across all five workloads at both
64 and 128. Preserve the selected submission and its two reports before any
new run. The retained `global/joint128-relaxed-40/finalists/eval-010` candidate
has promising native128 results but lacks pinned verification.
