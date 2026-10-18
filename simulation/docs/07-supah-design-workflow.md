# Supah Silicon: runnable design workflow

Our first hardware artifact is a legal 2.5D package layout: four GPU dies and
four HBM stacks connected according to the organizer's frozen specification.
We optimize positions and, optionally, routes. We do not alter the dies,
power maps, cooling boundary or score to make a result look better.

## Run it on this Mac or Linux

Install Docker and Git, start Docker, then run these commands from the
repository root. Setup downloads the public challenge at revision
`8948d9bc5e3aa041dcd1ff8a5a63ed6200d04d81` and builds a local image. Containers
run without network access, with six CPU cores and 4 GB memory by default.
Set `SUPAH_SIM_CPUS` and `SUPAH_SIM_MEMORY` to change those limits.

```sh
./simulation/run setup
./simulation/run test
./simulation/run validate simulation/layouts/p2/submission.json
./simulation/run score simulation/layouts/p2/submission.json --grid 64 --output simulation/results/p2-64.json
./simulation/run search simulation/layouts/p2/submission.json --output simulation/experiments/run1 --evals 80 --seed 17
./simulation/run score simulation/experiments/run1/submission.json --grid 64 --output simulation/results/run1-64.json
./simulation/run score simulation/experiments/run1/submission.json --grid 128 --output simulation/results/run1-128.json
```

Each search needs a new output directory. It checkpoints the best screened
layout, records every thermal evaluation and bounds the number of invalid
proposals. The default search checks skewed compute and memory streaming at
64 × 64, then evaluates the seed and the best candidates on **all five**
workloads. `--screen` can select different official workloads. `--focus G0 H0
H3` favors moves of those dies while retaining broader proposals. It never
modifies the challenge's workloads.

Reports from `score` use the unmodified organizer judge, its hash-verified
Linux binary and the reference for the requested grid. They are local
verification reports, not signed AutoLab leaderboard results. Grid 128 is the
finalist check. A design selected at 64 must still be compared against p2 at
128; improvements need not survive a change of mesh.

## Faster native exploration

Native exploration can avoid Linux emulation on Apple Silicon. Copy
`.cache/challenge/vendor/HotSpot` to a separate build directory, run `make clean`
and `make`, and set `CRYO_HOTSPOT` to that build's `hotspot` executable. Use
`CRYO_HILL` for the pinned challenge directory. Python needs NumPy.

```sh
CRYO_HILL="$PWD/.cache/challenge" CRYO_HOTSPOT=/absolute/path/to/native/hotspot \
  python3 simulation/tools/optimize.py simulation/layouts/p2/submission.json \
  --output simulation/experiments/native-run --evals 80 --seed 17
```

The search records the native executable hash and calibrates its reference
at the same grid. Native results remain estimates even if they reproduce
the rounded baseline. Always run finalists through `./simulation/run score`.
Do not rebuild or replace the pinned binary in `.cache/challenge`.

## Supah data architecture hypothesis

We currently propose a software pipeline of ingest and normalization,
structured filtering, context retrieval/ranking, and inference. Muni's records
provide a concrete future workload source. This repository does not yet contain
measured Supah execution traces or evidence that a particular stage is the
real performance bottleneck.

The current Muni working copy provides a concrete starting point: its README
and `core/lib/muni/store.rb` describe public-source collection, typed records
and an indexed SQLite store. `core/lib/muni/analytics/civic_digest.rb` builds
selected context and can request streamed model output. These establish useful
ingestion, database and inference-boundary measurements; they do not establish
a GPU-resident database, vector-retrieval implementation or local model runtime.
Keep external API wait time separate from local compute when profiling.

Memory streaming is a proxy for scans and retrieval reads; attention decoding
is a proxy for inference/context traffic; mixed serving is a proxy for
concurrency. All five supplied workloads remain part of scoring. GPU identities
G0–G3 represent fixed benchmark dies, not dedicated Supah pipeline stages.
Changing their assigned functions would require a different architecture study.

## Evidence to bring to Track 1

```sh
./simulation/run profile simulation/results/run1-128.json --output simulation/results/system-profile.json
```

The export carries per-workload modeled package watts and temperatures with
source hashes. Task duration, throughput and joules per task remain null until
measured. Temperature reductions do not imply equivalent power reductions.
Package power excludes the rest of the server, power-supply losses and cooling.

Next, instrument representative Supah/Muni tasks for stage durations, memory
traffic, context size, concurrency, output quality and wall energy. Compare
ordinary CPU/NPU/GPU platforms before deciding which custom accelerator is
justified. A Track 1 model can then size local/regional deployments, schedule
background work and assess cooling within a building's power budget.

The Track 2 model is synthetic and has a fixed cooler. It does not validate
fabrication, signal integrity, cooling equipment, inference throughput or an
operating office appliance.

## Inspect a verified layout without rerunning the solver

```sh
./simulation/run diagram simulation/layouts/supah-v1/submission.json simulation/layouts/supah-v1/verification-128.json simulation/results/supah-v1.png
```

The renderer checks that the saved report hashes match the submission and
challenge specification. Each die is colored by its peak across workloads;
this diagram is a floorplan, not a spatial temperature field. Use `render`
when a newly computed spatial heat map is needed.
