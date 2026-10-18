# Free topology seed generation

This sub-experiment changes placements only. It preserves the challenge, hardware, cooling contact, power maps, interconnect, routing validator, scoring rules, pinned evaluator, and v5 incumbent. Docker was local, network-disabled, and capped at two CPUs. No AutoLab or Docker socket connection was used.

## Proposal model

`generate.py` models the 16 die coordinates, 32 integer routing endpoint coordinates, 24 routing distance/access auxiliaries, 112 binary pair-separation choices, and 16 absolute target deviations. Every pair can choose any legal axis/direction of separation. It enumerates facing-side direction cycles, including concave and folded arrangements and the GPU's permitted two-ports-on-top/bottom case. HBM's two ports are required to occupy different sides by unchanged capacity rules.

The route-length expression is a Manhattan lower bound for the chosen endpoint cells, not a replacement for obstacle-aware routing. Proposals are subsequently passed to the original full validator. Only exact-valid submissions are saved as seeds. No thermal score is used to establish legality.

The early 1,000-proposal families required all four facing directions. Later families include two- and three-direction patterns too, rather than assuming a convex ring. No valid fewer-than-four-direction case was found in these samples. This is a heuristic search, not a proof that an unsampled topology is infeasible. A time-limited MILP result also does not establish global infeasibility.

## Geometry results

| Family | Proposals | Exact-valid seeds | Constraint |
|---|---:|---:|---|
| global-seeds-a | 240 | 0 | GPU shared-port patterns first |
| global-seeds-b | 1,000 | 42 | Free pair separations and facing topology |
| full-contact | 1,000 | 13 | Every die fully inside unchanged contact [4,48]×[4,38] |
| g0-preserved | 4,000 | 14 | G0 fixed to v5; other GPU y origins in [4,27.5] |
| g0-preserved-complete | 10,000 | 20 | Broader facing enumeration; same fixed G0 |
| g0-isolation | 10,000 | 22 | Same bounds, objective pushes H0/H3 away from G0 |

The `g0-preserved-complete` directory name denotes its completed run, not exhaustive global coverage: the later enumerator has 11,809 entries, and the run tested 10,000. Each directory retains proposals, saved seed submissions, an index of legal cases, and counts. Source hashes in summaries were captured at run completion; earlier source versions were developed between runs. The final `g0-isolation` run used the final saved `generate.py`, SHA256 a5e0e2545a5a03ab2d7664e92e920ad2bf47bfd47f0d0ebed6b3377f68b04368.

## Screening and handoff

`g0-isolation/skewed-screen.json` records native 64-grid skewed-compute screens. The precise-output search binary changes only grid-output formatting; these temperatures are screening evidence, not pinned scores and not a five-workload objective.

The strongest G0 isolation result is `g0-isolation/seed-0020.json`, facing sequence NEEESSWW. It keeps G0 exactly at v5 coordinates but lowers its native skewed peak to **101.19229247°C**. The package skewed bottleneck transfers to G2 at103.29°C, with G2 origin x39.211556mm, so it is a useful balancing seed rather than a winning submission. It was handed to topology search for moving the upper/right chain inward and testing all workloads.

Another genuinely different placement is `g0-isolation/seed-0003.json`, NENESSWW, with unchanged G0 origin and native skewed G0 peak101.51386895°C. The standard/reflected ring seeds0001/0009 screen at101.35952232/101.38502389°C G0, respectively. The final submission must be selected and verified by the parent experiment across all five workloads and both required grids.

## Routing reachability

In the unchanged original validator, facing sides are deterministic functions of die centers; port allocations follow those sides. Track endpoints are deterministic functions of port position, normal, clearance, and grid pitch. A supplied route must start and end at exactly those cells. Submissions cannot independently choose endpoint assignments or facing edges.

The default router computes a shortest obstacle-free Manhattan path. Consequently any supplied alternative is at least as long and cannot make a default-illegal placement legal. Alternative routes cannot expand the feasible placement set or create additional outward-spread freedom. Placement changes can alter facing sides and endpoints; the topology generator already allows those changes.

At the v5 placement, weighted route length is13499.1 /13500, leaving0.9GB/s·mm. With fixed endpoints, grid-path lengths have fixed parity, so any strictly longer path adds at least two0.5mm edges, or1mm. The cheapest link then consumes300 additional weighted units. Thus strictly longer routes are impossible at fixed v5 placement. Equal-length alternatives remain useful only for changing heat deposition. `routes.py` enumerates those alternatives at v5 specifically, then screens the best combined routes across all five workloads.

The completed v5 route experiment evaluates all84 S0 shortest paths (83 alternatives; each other link has exactly one path), then the combined selection across all five workloads. It improves raw G0 only101.26397098→101.26381409°C, a0.00015689°C change. Rounded all-five native GPU101.26°C/HBM94.26°C and score0.95816057 remain tied. The explicit route candidate is retained in `v5-routes/submission.json`; it is not promoted as a pinned improvement. The earlier v5 experiment covered the same input layout but ranked a hottest-neighborhood tie breaker; this pass records the exact raw G0 maximum.

## Reproduce the most useful seed family

```sh
SUPAH_RESEARCH_CPUS=2 ./simulation/research-v3/run native simulation/research-v6/model/generate.py --output simulation/research-v6/model/g0-isolation-repeat --trials 10000 --seconds .5 --g0-fixed --isolate
SUPAH_RESEARCH_CPUS=2 ./simulation/research-v3/run native simulation/research-v6/model/screen_seeds.py simulation/research-v6/model/g0-isolation-repeat
```

MILP time limits can produce machine-load-dependent solutions. Saved seed JSON files and exact validator output are the concrete retained evidence.
