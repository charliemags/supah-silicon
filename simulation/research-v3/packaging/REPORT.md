# Packaging investigation

All geometry uses the frozen organizer `geometry.py` and `verify_submission.py`. Dimensions, die orientations, port allocation, bandwidths, cooling, and workload maps are unchanged. Candidate metadata and thermal estimates are separate from submitted JSON.

## Incumbent constraints

The immutable incumbent is SHA-256 `09b3c673fd8a8a6b940abd8219cf9a85f88d70efcd98667e55604bb394845724`. Its weighted route length is 13444.8 / 13500 GB/s·mm, leaving **55.2**. The closest die pair is G2–H2 at1.117 mm, leaving0.117 mm beyond the required gap. Die separation itself is generally less restrictive than access-cell rounding and link reach.

| Link | Length, mm | Reach slack, mm |
|---|---:|---:|
| P0 | 4.904 | 0.096 |
| P1 | 1.385 | 3.615 |
| P2 | 1.144 | 3.856 |
| P3 | 4.949 | 0.051 |
| S0 | 5.986 | 0.014 |
| S1 | 5.998 | 0.002 |
| S2 | 4.004 | 1.996 |
| S3 | 4.064 | 1.936 |

The1 μm one-coordinate feasibility scan in `local-feasible-axis-radius.json` makes the constraints concrete. G0 moving left or down first fails at0.015 mm; moving right fails at0.051 mm even though the continuous S0 port distance decreases, because its access cell changes. G1 moving right or up first fails at0.003 mm. G2 moving left fails at0.002 mm from an occupied access track, despite0.117 mm geometric gap slack. These are first local failures, not bounds on disconnected legal intervals farther away. Coordinated motion and explicit access-cell treatment are necessary; a smooth optimizer ignoring the router can misidentify feasible directions.

Each die terminates4 mm and2 mm ports. Sharing a side requires6.4 mm including their0.4 mm separation. HBM sides offer only6.3 mm horizontally and6.12 mm vertically, so **an HBM's two ports must be on different sides**. GPU top/bottom sides offer6.9 mm and permit shared ports, while left/right sides offer6.3 mm and do not. The current arrangement has one link per used side, so individual port capacity is slack; this topology restriction matters when generating different packings.

## Route hypothesis and a rigorous restriction

**Hypothesis:** alternate equal-length shortest tracks can reduce local wire interference without increasing power or consuming any route budget.

At fixed placement, start/end access cells and both access lengths are fixed. Any Manhattan path between fixed endpoints has edge-count parity fixed by the endpoints. Relative to a shortest path, a longer valid path therefore adds at least two0.5 mm edges, or1 mm. The cheapest link bandwidth is300 GB/s, so every longer route needs at least300 GB/s·mm extra. The incumbent's55.2 slack rules out **all strictly longer optional routes at its fixed coordinates**. This is a rigorous combinatorial restriction, not a thermal approximation.

Exhaustive shortest-path enumeration found126 paths forS0,5 forS2, and exactly1 for each other link. There are630 combinations, all with identical link lengths and wire powers. We screen20 evenly distributed S0 paths (omitting its automatic path) and all4 nonautomatic S2 paths. The unchanged routes are the control. A benefit must survive pinned evaluation and both grids; a tiny native change only establishes screening potential. Failure to improve beyond numerical precision falsifies meaningful benefit for these sampled tracks, not every possible coordinated placement/routing change.

The total wire watts are2.517819 (tensor training),2.336463 (skewed compute),6.096480 (attention decode),7.200223 (memory stream), and4.521815 (mixed serving). Total PHY watts respectively are1.8192,1.6848,4.2960,4.9392,3.1536. Thus wire rerouting acts on a small fraction of package heat and should not be expected to remove a large base-power hotspot by itself. Equal-length routes conserve every workload's total power exactly.

## Different feasible package arrangements

**Hypothesis A:** a4×2 alternating GPU/HBM cycle can bring the whole package vertically inside the cooling contact, save link power, and outperform the3×3 ring if reduced poor-contact exposure outweighs thermal coupling. The graph cycle is G0–H0–G1–H1–G2–H2–G3–H3–G0. We place that cycle around a two-row/four-column perimeter with12 mm center spacing horizontally,12.5 or14.5 mm row separation, and±0.75 mm horizontal translation. All16 directed cycle assignments are retained: no rotational or reflection symmetry is assumed for fixed power maps. This produces64 exact-valid candidates with no die rotations. These geometries change relative ordering and cannot be reached by the old order-preserving projection. A consistently worse all-workload minimax score falsifies this family at sampled spacings.

**Hypothesis B:** exchange the *kind* occupying corners and side midpoints: put HBMs at the four corners of a3×3 ring and GPUs at its four side midpoints. GPU compute hotspots can then stay within the central cooling contact, potentially reducing GPU limits while sacrificing some HBM temperature margin. This differs from permuting GPU labels among the incumbent's corner slots. We screen48 exact-valid candidates: eight directed cycle assignments, horizontal center gaps13.5/15 mm, vertical center gaps11.6/12/12.5 mm. Its falsifier is either GPU interference offsetting contact benefits or HBM corner temperatures exceeding the competing minimax limit.

## Reproduction

From repository root, `python3 simulation/research-v3/packaging/explore.py prepare`, `python3 simulation/research-v3/packaging/slack.py`, and `python3 simulation/research-v3/packaging/inverted.py` regenerate exact-valid seeds and geometry evidence without thermal dependencies. Inside the existing local search image, run `explore.py screen` and `inverted.py screen`; both use the unchanged64-grid source generation and native SuperLU solver, all five workloads, and two workload workers. `screen-manifest.json` records the native executable hash. The image runs with no network and never mounts a Docker socket; no hosted resources are provisioned. Native screens are not signed AutoLab scores or pinned certifications.

## Completed thermal evidence

All results below are native SuperLU **screening**, using all five workloads on the unchanged 64 grid. The control reproduces the known native-versus-pinned difference: native GPU 101.39 °C versus the incumbent's signed 101.40 °C. No row below is a new official result.

| Family | Evaluations | Best native score | GPU peak °C | HBM peak °C |
|---|---:|---:|---:|---:|
| Incumbent control | 1 | 0.95979394 | 101.39 | 94.16 |
| Equal-length routes | 23 | 0.95979394 | 101.39 | 94.16 |
| Four-column/two-row cycle | 64 | 1.05255916 | 108.57 | 101.50 |
| Inverted ring | 48 | 1.03015454 | 106.99 | 90.75 |
| Wider inverted ring | 32 | 1.01545420 | 105.82 | 90.71 |
| Coordinated movement from math agent | 12 | 0.96017088 | 101.42 | 94.08 |

There were **180 all-workload evaluations**, including the control. The best result of this investigation remains the incumbent. Exact candidates, per-workload/per-die peaks, powers, validation reports and timings are preserved. `summary.json` aggregates results without discarding failed hypotheses.

The routing hypothesis did not yield an improvement. Alternative paths left the rounded GPU maximum at 101.39–101.40 °C and HBM at 94.16 °C. Because this is at the native/pinned uncertainty scale, there is no supported reason to promote a route variant.

The best flat cycle saved approximately 0.82 W in skewed-compute wire heat and 2.67 W in memory-stream wire heat relative to the incumbent, yet made both thermal objectives much worse. Lower interconnect power alone therefore fails as a useful ranking surrogate for these packings. More compact geometry and exposure at the horizontal contact edges dominate those savings.

The inverted ring substantially improved HBM temperature but made the GPU bottleneck worse. Its best initial assignment puts G0 on the west side; the limiting cells are G0 in skewed compute at 106.99 °C and G1 in tensor training at 105.74 °C. This establishes a real trade, not a uniformly bad arrangement. The stronger wider seed places G0's origin at (4.0,15.75) mm, keeps its compute hotspot within the good-contact region, and improves its family to 105.82 °C. Its candidate is `candidates/wide-f0-r2-dx16.25-dy11.75/submission.json`; this was handed to the lead for asymmetric refinement. These seed screens do **not** prove the entire inverted topology uncompetitive.

Trying to expand the inverted ring in both dimensions was rejected by the exact router: side-GPU halfspans 16/16.25 mm, HBM corner halfspan 15.5 mm, and vertical halfspans 13.5/14.5 mm produced aggregate route excess or primary-link lengths 5.15–5.40 mm. Even vertical halfspans 12/12.5 mm required 13770/14670 GB/s·mm, above 13500. The screened wider seeds therefore used vertical halfspans 11.5/11.75 mm. The rejected files and `inverted-wide-rejected.json` preserve these negative geometry tests. Their rejection is specific to this parameterized family; asymmetric redistribution may free budget.

## Coordinated movement and contact-edge failure

A further hypothesis, developed jointly with the math agent, keeps G0 fixed and moves H3 northwest, reallocating S0's Manhattan length from horizontal offset to vertical separation. G3 follows to preserve P3, and G2/H2 move left to recover weighted route budget. Exact routing invalidates many naive directions because port-access rounding changes under translation. The math agent repaired 12 candidates from 384 cheap geometry proposals; `directed-screen.py` evaluates those unchanged proposals.

The best repaired movement cools HBM from 94.16 to 94.08 °C, but heats the GPU maximum from 101.39 to 101.42 °C. Its competing GPU peaks become G0/skewed-compute 101.42 °C and G3/tensor-training 101.40 °C. The four larger 0.4 mm northwest moves push G3/tensor-training to 105.58 °C, while G0/skewed-compute stays at 101.42 °C. Thus the proposed local HBM benefit is overwhelmed by G3's contact-edge penalty. This is a specific physical and constraint-based failure, not evidence that no multi-die direction can work.

Run `python3 simulation/research-v3/packaging/summarize.py` after all screens to regenerate the comparison. The isolated image entrypoint is Python, so pass the script path directly rather than adding another `python` command. `inverted-wide.py screen` and `directed-screen.py` add the final two screen families. All incumbent files remain unchanged.
