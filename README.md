# supah-silicon

Sundai @ MIT hackathon, Track 2: design the coolest chiplet layout.

## Profile the real Supah/Muni workload

[Measured Muni results](profiling/RESULTS.md) cover public-record ingestion,
SQLite queries, empirical prediction and inference-context preparation at two
dataset sizes. [Supah Edge v0](architecture/README.md) translates those
measurements into a CPU/shared-memory architecture hypothesis with an optional
inference accelerator. Generative model execution and power remain unmeasured.

```sh
export SUPAH_MUNI_ROOT=/absolute/path/to/muni
./profiling/run --cache .cache/muni-corpus --output profiling/results/local-5000.json --fetch --rows 5000
python3 profiling/design.py profiling/results/local-5000.json --output architecture/local-design.json
```

See the [profiling workflow](profiling/README.md) for replay, measurement limits
and team iteration. Raw data stays local; aggregate profiles and source hashes
are checked in.

## Build and evaluate a Supah layout

The first Supah Silicon artifact is a simulated 2.5D GPU/HBM package. The
challenge fixes the hardware and workloads; we optimize placements and routes.
The [Supah design workflow](simulation/docs/07-supah-design-workflow.md) connects
this experiment to the proposed data-processing, retrieval and inference
pipeline, and explains the evidence still needed for Track 1.

**Built: [Supah Silicon v1](simulation/layouts/supah-v1/README.md).** A 50-layout
search produced a candidate verified on all five workloads at both 64 and 128.
At 128, it scores **0.981063** versus p2's **0.989090**: GPU peak
**103.23 °C** (0.64 °C lower), HBM peak **95.61 °C** (0.52 °C higher).
These are local checks with the unmodified pinned evaluator, not signed
leaderboard results or measurements of Supah application efficiency.

With Docker running, from this directory:

```sh
./simulation/run setup
./simulation/run test
./simulation/run validate simulation/layouts/supah-v1/submission.json
./simulation/run search simulation/layouts/supah-v1/submission.json --output simulation/experiments/run1 --evals 80
./simulation/run score simulation/experiments/run1/submission.json --grid 128 --output simulation/results/run1-128.json
```

The wrapper supports Apple Silicon by running the pinned Linux scorer in a
container. Search results are estimates until checked by the judge. Local
verification does not submit a result to AutoLab.

## Simulation

**Start here: [the Supah-Silicon story](simulation/STORY.md)**, how we found a cooler layout, in plain English with the official test outputs.

Run a test yourself (Linux, or a GitHub Codespace in your browser): `bash simulation/run.sh`

Everything about how we simulate and search chip layouts is in [`simulation/`](simulation/):

- [`simulation/docs/`](simulation/docs/README.md): plain-English guides (how the heat simulation works, how to run it, making it faster, searching for a cool layout, a 3D stacking experiment, and the organizers' simulator and GUI)
- [`simulation/tools/`](simulation/tools/): the search, fast-estimate, heat-map and 3D-stack code
- [`simulation/layouts/`](simulation/layouts/): designs and their evidence. `supah-v1` includes the submission, local 64/128 verification, floorplan, full search history and a Track 1 system-profile export. Earlier layouts retain their signed reports.

Built on the organizers' [chiplet-thermal-simulator](https://github.com/Czaja107/chiplet-thermal-simulator) and [chiplet-thermal-gui](https://github.com/Czaja107/chiplet-thermal-gui).
