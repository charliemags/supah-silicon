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

**Built: [Supah Silicon v2](simulation/layouts/supah-v2/README.md).** The
AutoLab signed evaluator confirms a **0.95991959** score at 64 × 64 across all five
workloads: GPU **101.40 °C**, HBM **94.16 °C**. It ranked **#1 as charliemags**
on an earlier October 18 leaderboard snapshot, ahead of **0.96180425**. The
[official report](simulation/layouts/supah-v2/official-report-64.json) matches
the local result. The 0.95 and 0.94 targets remain unmet; the 128-grid result
is locally verified only. These are thermal benchmark results, not measurements
of Supah application efficiency.

**Latest verified placement:** [research v6](simulation/research-v6/README.md)
improves the local pinned score to **0.95753235 at 64 × 64** and
**0.96012039 at 128 × 128**, across all five workloads. Adaptive differential
evolution with legal placement/routing repair produced the improvement;
different package topologies and valid routing alternatives were also tested.
The [submission](simulation/research-v6/submission.json), verification reports,
and search audit are saved together. The signed v2 incumbent and all benchmark
rules remain unchanged. The 0.95 and 0.94 targets remain unmet, and this is
not yet a signed AutoLab result. Earlier [v3](simulation/research-v3/README.md),
[v4](simulation/research-v4/README.md), and [v5](simulation/research-v5/README.md)
reports preserve the full investigation history.

The search combines native HotSpot/SuperLU simulation, additive Gaussian-process
guidance and parallel placement search. See the
[optimization guide](simulation/docs/08-surrogate-search.md) for the model,
Docker resource settings and verification workflow. The earlier
[v1 design](simulation/layouts/supah-v1/README.md) remains available.

With Docker running, from this directory:

```sh
./simulation/run setup
./simulation/run setup-search
./simulation/run test
./simulation/run test-native
./simulation/run validate simulation/research-v6/submission.json
./simulation/run score simulation/research-v6/submission.json --grid 64 --output simulation/results/supah-v6-64.json
./simulation/run score simulation/research-v6/submission.json --grid 128 --output simulation/results/supah-v6-128.json
```

The wrapper supports Apple Silicon by running the pinned Linux scorer in a
container. Search results are estimates until checked by the judge. Local
verification does not submit a result to AutoLab.

## Models

The signed design archive is in [`Models/`](Models/README.md), including
[`Supah_0.9719`](Models/Supah_0.9719/). The newer
[Supah v2](simulation/layouts/supah-v2/README.md) result includes its signed
AutoLab report and first-place leaderboard snapshot.

## Simulation

**Start here: [the Supah-Silicon story](simulation/STORY.md)**, how we found a cooler layout, in plain English with the official test outputs.

Run a test yourself (Linux, or a GitHub Codespace in your browser): `bash simulation/run.sh`

Everything about how we simulate and search chip layouts is in [`simulation/`](simulation/):

- [`simulation/docs/`](simulation/docs/README.md): plain-English guides (how the heat simulation works, how to run it, making it faster, searching for a cool layout, a 3D stacking experiment, and the organizers' simulator and GUI)
- [`simulation/tools/`](simulation/tools/): the search, fast-estimate, heat-map and 3D-stack code
- [`simulation/layouts/`](simulation/layouts/): designs and their evidence. `supah-v2` includes the improved submission, local verification, floorplan and search records. `supah-v1` also retains a Track 1 system-profile export. Earlier layouts retain their signed reports.

Built on the organizers' [chiplet-thermal-simulator](https://github.com/Czaja107/chiplet-thermal-simulator) and [chiplet-thermal-gui](https://github.com/Czaja107/chiplet-thermal-gui).
