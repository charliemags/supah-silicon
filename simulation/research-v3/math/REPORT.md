# Applied mathematics research notes

## Evidence and current limit

The immutable incumbent is `simulation/layouts/supah-v2/submission.json`, SHA-256
`09b3c673fd8a8a6b940abd8219cf9a85f88d70efcd98667e55604bb394845724`.
Its pinned 64 result is 0.95991959, not the native screen's 0.95979394.
`audit_history.py` reproduces `history-audit.json` using stored observations only.
It found 5,648 valid 64-grid records and 5,502 unique submissions after exact
JSON deduplication, including reused history; these are not 5,648 independent
new experiments. Of these, 3,461 have screening score below 0.961.
All those near elites put G0 in x=[3.934,4.021], y=[3.368,3.634] mm.
The best historical native G0/skewed peak is 101.39 C. Neither observation
proves that a different placement family cannot improve.

The incumbent's GPU maximum is G0 under skewed_compute, 101.40 C. Its HBM
maximum is H2 under memory_stream, 94.16 C. To attain 0.95, independently
binding requirements include:

| Component | Current C | Required reduction C |
|---|---:|---:|
| skewed_compute G0 | 101.40 | 0.79 |
| tensor_training G3 | 101.13 | 0.52 |
| tensor_training G2 | 100.90 | 0.29 |
| skewed_compute G2 | 100.85 | 0.24 |
| memory_stream H2 | 94.16 | 0.12 |

G1/tensor is 100.29 C and has 0.32 C slack to the target. Thus a movement that
cools G0 alone cannot achieve 0.95. (The continuous HBM threshold is 94.046 C;
the judge's hundredths require 94.04 C.)

The tight route reaches are S1=.002, S0=.014, P3=.051, P0=.096 mm slack.
The weighted budget has 55.2 GB/s*mm slack. The minimum die clearance has .117 mm
slack; package edge clearance has 1.477 mm slack above the required 1 mm.
The port allocations have ample capacity in the current arrangement.
This is a coupled routing-reach problem before it is a package-edge problem.

## Formulation and proposed optimizer

Let x be 16 die coordinates, r the discrete valid routes, and theta_w solve
K(x) theta_w=q_w(x,r). For every workload w, die d and sampled location p on
d, impose

    theta[w,d,p] / reference_rise[d] <= t.

Minimize t subject to all exact placement, port, reach and budget constraints.
The sampled peak can instead be one response per workload/die while retaining
all 40 components. Screening retains 24 components across the three historically
critical workloads, with all-five verification required for finalists.
No average-temperature objective is substituted for the minimax objective.

`epigraph_search.py` implements a bounded 240-evaluation experiment. It measures
legal coordinate perturbations at .025, .1, .25 mm, legal coordinated group
perturbations, then projected feasible probes. Weighted local least squares
fits each separate component. SLSQP minimizes a shared epigraph variable with
die separation, package bounds, approximate route lengths and weighted budget.
Exact organizer validation gates every thermal simulation. Radius and fit
scale vary to expose misleading local slopes. Only unchanged thermal inputs
and solver screening are used. The projection fixes the local pair-separation
choices: this optimizer intentionally refines one topology and must be paired
with the separate topology exploration.

An analytic adjoint is not available from this Python wrapper: it does not
expose K, its factorization, or derivatives of block-to-grid mapping. A true
adjoint would require instrumenting the native solver and differentiating
both geometry-dependent conductance and deposition. Ignoring dK/dx would be
particularly unsafe near the contact boundary. Finite feasible secants are
the practical first experiment; their scale disagreement must be reported.

## Testable hypotheses

1. **Coupled active-reach directions were undersampled.** G0's desired local
   movement may require several linked dies to move together to preserve S0,
   S1, P0 and P3. Fit component secants and solve a constrained epigraph problem
   under the same evaluation budget as a local population baseline. Falsify
   useful local gains if 200-300 evaluations cannot improve the native incumbent
   by more than the measured native/pinned difference, or gains vanish at 128.
   A negative result is local, not global.

2. **The previous topology survey did not cover the main alternative packing.**
   Its 36 cases relabelled five existing ring layouts. It did not optimize a
   4-column by 2-row perimeter cycle. Eight approximately 11 x 10 mm dies fit that
   shape within 52 x 42 mm, and the fixed bipartite link graph is an 8-cycle. Enumerate
   all cycle labelings, align facing ports and vary row/column offsets before
   exact validation. Screen diverse legal seeds, then give the strongest equal
   refinement budgets. Falsify this family's practical advantage if the best
   robustly refined candidate is no better at both 64 and 128. This is not proof
   that every continuous arrangement in that family is inferior.

3. **Grid phase is distorting local sensitivity.** In the first two expanded
   population records, small coupled moves including G2 (37.027,28.854) to
   (37.061,28.797) change its skewed peak 99.68→98.89 C, while G0 stays 101.42 C.
   This is not an isolated derivative because other dies also moved. Test
   symmetric feasible perturbations at multiple scales and repeat at 128;
   falsify the suspected artifact if trends and magnitudes converge consistently
   and persist in small neighborhoods.

4. **Equal-length routing is a low-cost residual degree of freedom.** At fixed
   incumbent endpoints, any longer Manhattan track path adds at least two
   half-mm edges, i.e. 1 mm, since all paths between fixed grid cells have the
   same parity. Even the cheapest link then consumes 300 GB/s*mm, exceeding
  55.2 slack. Therefore no strictly longer optional route is feasible without
   placement changes. This is a rigorous combinatorial statement for this
   fixed placement and router. Enumerate alternate shortest paths instead;
   their total wire power is unchanged but spatial deposition differs. Falsify
   significance if all such alternatives change the limiting peaks by less
   than the precision/calibration margin.

## Bounds: what can and cannot be certified

For a fixed layout with linear passive conduction, K inverse is nonnegative
(the discrete thermal network is an M-matrix after ambient boundary
conditions). Removing nonnegative source components cannot raise any node's
temperature. Solving only G0's own base source, with all geometry/materials
unchanged, is therefore an optimistic *fixed-layout* lower bound on G0's full
peak. The same holds for any workload/die and for stripping PHY/wire sources.
These are diagnostic relaxations, never valid challenge scores.

A useful decomposition is to retain fixed K and solve base-G0, other base,
PHY and wire independently, summing *temperature rises at the original
limiting grid point*. Summing each source's separate spatial maximum is wrong;
the peaks need not coincide. The total reconstructed grid should agree with
the full grid within solver/print precision. This quantifies the maximum gain
obtainable by removing all other heat at the fixed geometry and separates
self-heating from reducible coupling. Moving dies also changes K, so it does
not certify bounds on all placements.

A global bound requires proving a lower bound on

    min_{valid x,r} max_{w,d} normalized_peak(w,d,x,r).

The minimax inequality supplies max_i inf_x f_i(x) <= inf_x max_i f_i(x), but
numerically minimizing individual peaks supplies upper estimates of those
infima, not certified lower bounds. A search plateau or the smallest observed
G0 temperature cannot establish infeasibility of 0.95 or 0.94. No numerical
global thermal lower bound has been established in this study.

## Execution status

The offline audit ran successfully. The epigraph script passes Python syntax
compilation. Its attempted local Docker run was stopped by automatic approval
review, which read the initial specialist assignment “do not launch costly
simulations yet” as prohibiting the subsequently requested bounded experiment.
The lead subsequently clarified that the initial wait instruction originated
from the lead, and that the human request authorizes local simulation. A
reviewed network-disabled, four-CPU run then started successfully under
`epigraph-256/`, with an equal-budget population baseline. See that directory
for live results; no paid resources or AutoLab Docker connection were used.

## Completed controlled experiments (native screening)

The first epigraph run evaluated 91 valid points in 63.41 seconds, then hit its
iteration cap. The best remained the native incumbent, 0.95979394. Its
approximate route model never produced a thermally evaluated epigraph trial.
This is a proposal-model failure, not evidence that the epigraph formulation
is ineffective. Multi-scale secants and feasible stochastic probes did run.
`source-snapshot.py` preserves the exact original source matching its manifest.

Controlled downward G2 moves of .025, .1, .25 mm reduced its skewed peak by
.30, 1.09, 2.15 C, while G0 changed by 0, +.01, +.01 C. G3 downward moves of
the same sizes reduced its tensor peak by .24, .25, .35 C: the sensitivity is
strongly scale dependent. These local cooling gains do not improve the
minimax score because G0 remains active. At .025 mm, two-decimal response
rounding alone allows up to .4 C/mm secant error; at .1 mm it allows .1 C/mm.
`analyze_secants.py` records all component deltas and this error bound.

Geometry-only testing found all 21 initial diagonal H3/G3 moves invalid even
though their port-Manhattan lengths were unchanged. Exact endpoint track
access changed; P3 grew to 5.06–5.35 mm against its 5 mm maximum. This
identifies a concrete flaw in constant-overhead routing approximations.
Enumeration with coordinate repairs recovered 12 valid placements from 384
candidates. Their all-five-workload screens are in the packaging specialist's
`directed-results.jsonl`. None improved minimax: the best was GPU 101.42 C,
HBM 94.08 C. Larger .4 mm H3/G3 northwest moves heated G3/tensor to 105.58 C,
while G0 remained 101.42 C. Moving H3 farther from the G0 hotspot in this
family failed because the necessary G3 motion crossed the cooler boundary.

The repaired continuation uses compatible prior observations and a feasible
stochastic fallback to meet the 256 total-evaluation budget. Its successor,
`epigraph_fixed_routes.py`, replaces the flawed geometric approximation with
frozen route-cell paths, exact L1 port access lengths, and conservative
linear halfspaces keeping every path cell clear. That is a local route
topology model, with exact validation still required. Its trial log includes
rejections and duplicate points to expose whether epigraph proposals actually
reach thermal evaluation.

## Final experiment accounting

| Experiment | New thermal evaluations | Elapsed seconds | Best native screen |
|---|---:|---:|---:|
| Original epigraph/secant stage | 91 | 63.41 | 0.95979394 |
| Repaired continuation | 165 | 102.66 | 0.95979394 |
| Combined first two stages | 256 | 166.07 | 0.95979394 |
| Existing population control | 256 | 107.05 | 0.95979394 |
| Correct fixed-route-cell epigraph follow-up | 64 | 38.52 | 0.95979394 |

The fixed-cell follow-up produced 48 actual epigraph thermal trials and 16
fallback probes. Of the 48 unbacktracked fitted optima, 43 passed the exact
validator immediately; the remaining five yielded valid smaller moves.
The best epigraph trial, evaluation 305, tied the native incumbent's 101.39 C
GPU but had 94.18 C HBM. Its exact candidate and response are preserved as
`epigraph-fixed-64/best-epigraph-trial.json`. No new candidate from this math
workstream beats the incumbent, so none is promoted as an official improvement.

The component linear models overpredicted improvement by an average
0.001906 score and a maximum 0.008623 score (about .152 and .686 C expressed
in GPU-reference units). These errors are much larger than the .01 C
native/pinned difference near the incumbent. This identifies local thermal
curvature and grid response as material limitations after routing was fixed.
The follow-up cycles three radii instead of adapting a trust radius to actual
versus predicted reduction; it is not a converged trust-region method and is
not evidence that every constrained minimax approach must fail. A follow-up
would fit at least G0's x/y curvature and use actual/predicted reduction to
shrink the radius, while retaining exact route-cell constraints.

All 320 unique thermal evaluations in this workstream are native screening
with unchanged benchmark physics. The 256-control comparison is equal in
actual evaluation count but compares an adaptive two-stage experimental
method against the existing population method; it is not a randomized
multi-seed algorithm benchmark. No 0.95 or 0.94 result was obtained here,
and no global impossibility bound is claimed.
