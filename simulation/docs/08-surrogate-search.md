# Faster placement optimization in Docker

Use **HotSpot with its SuperLU direct solver for exploration, guided by an
additive Matérn Gaussian process**, then verify candidates with the original
pinned binary. This combination keeps the benchmark's thermal equations and
fixed hardware while making hundreds of placement experiments practical.

The live AutoLab leaderboard checked on October 18, 2026 uses a **64 × 64**
mesh and HotSpot SHA-256
`5c3fcad8ae63144b218d2fc1de28ea862f5c6d3751e7ab381d576e5c00cab4bb`.
Its leader at that check was `wilsonwu-ai`: **0.96230682**, GPU **101.59 °C**,
HBM **94.73 °C**. Finalists are checked separately at the 128 mesh.
On the later same-day recheck, that leader had improved to **0.96180425**,
GPU **101.55 °C**, HBM **94.72 °C**. Both snapshots are preserved with v2.
See the [leaderboard](https://app.autolab.ai/hills/czaja107/beat-the-hotspot/leaderboard)
and [challenge rules](https://app.autolab.ai/hills/czaja107/beat-the-hotspot).

## What changes

The optional native Docker image compiles the organizer's existing HotSpot
source with `SUPERLU=1`. It uses a direct sparse linear solve instead of the
pinned binary's iterative solve. No challenge files, power maps, material
properties, cooling settings, links, reference temperatures or judge code
are changed. The source checkout remains mounted read-only during runs.

The initial calibration covered ten historical layouts, two workloads per
layout and eight die peaks per workload: the maximum difference from the
stored pinned-solver results was **0.01 °C**. This is a finite calibration,
not a guarantee for every layout or grid. The v1 baseline took about 128 s
with the pinned binary and 1.2 s with the native direct build on this machine
(five workloads, 64 grid); timing varies with concurrent work.

The search model has 16 inputs: x and y for eight dies. It learns three
separate outcomes: GPU peak under skewed compute, GPU peak under tensor
training, and HBM peak under memory streaming. It minimizes the maximum
normalized temperature rise. All five workloads are checked before a final
design is promoted.

The optional `--per-die` variant models each of the four relevant die peaks
within each workload before taking the maximum. This avoids fitting a single
response whose hottest die can switch as placements move.

The full GP uses one Matérn-5/2 kernel over all coordinates. The additive
variant sums kernels over each die's x/y pair. This makes it easier to learn
the effects of moving different dies from a modest dataset, although it
approximates interactions. Length scales and regularization are selected
using leave-one-out prediction error. A lower-confidence-bound acquisition
balances promising placements with uncertain ones. It is a heuristic search,
not proof of a global optimum.

Proposals include individual moves, correlated movements of connected dies,
whole-layout translations, and expansion/contraction. A cheap geometric
prefilter saves time; the unmodified organizer validator and router make the
actual feasibility decision. The surrogate never supplies a reported score:
every retained observation comes from a thermal simulation.

## Run it

From the repository root, with Docker running:

```sh
./simulation/run setup
./simulation/run setup-search
./simulation/run test
./simulation/run bayes-native simulation/layouts/supah-v1/submission.json \
  --output simulation/experiments/my-search --kernel additive \
  --evals 240 --pool 3000 --seed 53
./simulation/run score simulation/experiments/my-search/submission.json \
  --grid 64 --output simulation/results/my-search-64.json
./simulation/run score simulation/experiments/my-search/submission.json \
  --grid 128 --output simulation/results/my-search-128.json
```

Output directories must be new. Each simulation is appended to `search.jsonl`;
the best simulated candidate and a summary are checkpointed after every
evaluation. `experiment.json` records arguments, input hashes and solver hash.
Use `--history path/to/search.jsonl ...` to warm-start the surrogate with trusted
observations from the same frozen challenge. The loader separates grid sizes,
ignores failed/missing workload records, deduplicates placements, and excludes
explicit routes because the model only represents automatically routed layouts.
It does not independently authenticate supplied histories: only reuse data from
compatible, checked inputs and a calibrated solver.

`--grid 128` supports finer-resolution exploration with its own reference and
training observations. A 64-grid history does not train a 128-grid model.
`search-native` retains the original annealing optimizer as a control or a
local polishing step. `bayes` runs the GP with the slower pinned binary.
`score` always uses the pinned binary, irrespective of which search produced
the submission.

### Expanded Docker search

The 16 GB / 18 CPU Docker configuration supports simultaneous candidate
simulations. Container limits are explicit and do not automatically increase
when Docker Desktop's VM memory changes:

```sh
SUPAH_SIM_CPUS=12 SUPAH_SIM_MEMORY=8g SUPAH_SIM_MEMORY_SWAP=12g \
  ./simulation/run population-native simulation/layouts/supah-v2/submission.json \
  --output simulation/experiments/expanded --evals 1600 --parallel 4 \
  --walkers 12 --radius 1.2 --temperature 0.003 --seed 71
```

`SUPAH_SIM_MEMORY_SWAP` is the **combined RAM plus swap limit**: `8g` RAM
with `12g` combined allows up to 4 GB of swap, subject to Docker's actual
swap availability. The wrapper preserves Docker's default swap behavior when
the variable is omitted. Leave headroom for concurrent verification jobs.
The observed searches are CPU-bound and use much less than their RAM limits;
forcing swap use would slow them down. Extra capacity permits concurrency,
but does not guarantee any particular thermal score.

`population-native` uses parallel annealing walkers at different temperatures,
connected groups along the GPU/HBM ring, differential directions from previous
observations, and backtracking near feasibility boundaries. It checkpoints
every simulated observation and retains the best candidate. It accepts trusted
same-grid `--history` files for proposal directions; histories do not become
reported scores for the new run.

`project-native` uses SciPy SLSQP to adjust neighboring dies around a requested
target position, with geometric and approximate routing constraints. Exact
organizer routing then decides whether to simulate each proposal. For example:

```sh
./simulation/run project-native simulation/layouts/supah-v2/submission.json \
  --output simulation/experiments/project-h3 --die H3 \
  --x 3.8 7.8 11 --y 16.5 19.5 11 --parallel 2
./simulation/run test-native
```

Projection preserves the seed's relative die ordering. It is a local search
helper, not an exhaustive search of package topologies. The native image adds
SciPy for projection; the pinned judge image and benchmark remain unchanged.

## How to interpret the target

A 0.95 score requires **both** GPU ≤100.6105 °C and HBM ≤94.046 °C at 64,
or GPU ≤100.753 °C and HBM ≤94.065 °C at 128. Rounded judge temperatures can
make equality at those exact thresholds unattainable. Beat the displayed
leader only after the pinned 64-grid score is strictly below 0.96230682.
Always report the separate 128-grid result as well. Local verification does
not create a signed AutoLab run or change the public leaderboard.

## Why this method

Bayesian optimization is designed for expensive evaluations with limited
budgets; see [Ax's introduction](https://ax.dev/docs/next/intro-to-bo/).
Surrogate-assisted thermal chiplet placement also has direct research precedent:
[Zhang et al., Fast Thermal-Aware Chiplet Placement Assisted by Surrogate](https://arxiv.org/abs/2504.03808).
That paper uses an RBF surrogate with annealing; this implementation uses a GP
and is not a reproduction of its method or results. A large learned placement
network would require relevant training data and is not justified by this
single eight-die instance.
