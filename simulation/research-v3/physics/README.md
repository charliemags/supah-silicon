# Thermal attribution research

These are diagnostic simulations using the archived native SuperLU solver. They do not replace pinned verification or signed challenge reports. `diagnose.py` holds the complete layout-dependent conductivity network fixed and splits the unchanged source vector into eight base-die sources, PHY heat, and wire heat. Their temperature rises add at the *same full-run hotspot*, within printed-grid precision. No diagnostic source removal is a permitted challenge design.

The incumbent remains `simulation/layouts/supah-v2/submission.json`, SHA-256 `09b3c673fd8a8a6b940abd8219cf9a85f88d70efcd98667e55604bb394845724`.

## Findings at 64

| Workload / die | Native peak °C | Actual thermal hotspot x,y mm | Own source rise °C | Other base sources °C | PHY °C | Wire °C |
|---|---:|---|---:|---:|---:|---:|
| skewed_compute / G0 | 101.39 | 6.90625, 6.890625 | 55.83 | 19.97 | 0.23 | 0.37 |
| tensor_training / G3 | 101.12 | 13.40625, 38.390625 | 48.79 | 26.85 | 0.20 | 0.29 |
| tensor_training / G2 | 100.90 | 45.09375, 38.390625 | 47.32 | 28.12 | 0.21 | 0.24 |
| memory_stream / H2 | 94.16 | 32.09375, 35.109375 | 28.18 | 39.14 | 0.86 | 0.98 |

The official incumbent peaks differ from native by up to 0.01°C. Printed grids resolve only 0.01°C; the largest sum-of-components residual across the diagnostic table is 0.03°C. The thermal cell centers locate sampled maxima, not continuous maxima.

**The upper GPUs peak outside the cooling contact.** The high-conductance contact ends at y=38mm. Both G2 and G3 tensor maxima occur at y=38.390625mm. Their compute power-map Gaussians are centered farther south: these are boundary-driven thermal peaks, not simply the hottest power pixels. The lower limiting GPU instead peaks inside the contact near its compute source.

**G0 is mostly self-heating plus shared cooling.** Its own source accounts for 55.83/76.39=73.1% of rise. The other GPU sources total 15.69°C, almost exactly their aggregate 196W times the nominal 0.08K/W cooling resistance. H0 and H3 are its meaningful nearby sources. For a heuristic spatial-coupling diagnostic, subtract 0.08K/W times source watts:

| Source at G0/skewed hotspot | Rise °C | Rise minus 0.08×watts °C |
|---|---:|---:|
| G0 | 55.83 | 47.51 |
| G1 | 4.80 | +0.32 |
| G2 | 6.72 | −0.64 |
| G3 | 4.17 | +0.33 |
| H0 | 1.61 | +0.65 |
| H1 | 0.79 | −0.01 |
| H2 | 0.84 | −0.04 |
| H3 | 1.04 | +0.32 |
| PHY | 0.23 | +0.0952 |
| Wire | 0.37 | +0.1831 |

The nominal sink term is not a rigorous pointwise floor: individual sources have negative residuals because the sink temperature is spatially nonuniform. Holding G0's present own-source contribution and replacing all other contributions by this nominal common term gives 100.192°C. That is a conditional optimistic heuristic, not an attainable design, and not a global bound. It suggests the 0.95 target deserves further tests, while providing no proof of its feasibility.

**H2 is neighbor-sensitive.** It is responsible for only 28.18/69.16=40.7% of its own rise. G2 contributes 9.54°C and G3 7.68°C, with excess over the nominal common sink term of 6.18 and 3.84°C respectively. H1 and H3 contribute another 5.42 and 5.31°C. Its 0.12°C improvement needed for 0.95 should therefore be tested through spacing and stagger, alongside route and self-cooling changes.

## Hypotheses and falsification

1. **Upper contact clipping masks useful geometric freedom.** Move upper GPUs south, with coordinated H2/H3 moves needed for link reach and 1mm separation, retaining G0 near its present position. Prediction: G2 and G3 tensor peaks fall until hotspot identity changes; released peak slack allows routes/spacing that benefit G0. Falsification: south-moving feasible candidates do not improve those upper GPU peaks at both grids, or no arrangement redistributes the slack without worsening G0/HBM maxima. Existing rigid translation evidence supports the mechanism: y−0.5mm lowers G2/skewed 100.85→97.27°C and G3/tensor 101.12→100.62°C, but G0 rises101.39→101.58°C. The rigid move itself is not a win.

2. **H0/H3 separation is the best direct G0 coupling lever.** Their combined excess over nominal common sink rise is ~0.97°C, versus ~0.01°C combined for other GPUs. Allocate scarce route reach preferentially to increasing G0–H0/H3 thermal separation; compensate by shortening nonlimiting right/upper connections. Falsification: controlled feasible coordinated moves do not reduce G0 at both grids, or the reduction is smaller than adverse self-cooling/interface changes. P0 and S0 are already almost at maximum length, making this a constraint-management problem rather than a single-die displacement.

3. **Route-only changes can yield small gains but cannot reach 0.95 at fixed placement.** At G0's full-run peak, *all* wire heat contributes only0.37°C. Positivity of the thermal response means deleting every wire watt, an impossible but favorable relaxation at fixed K, still leaves that fixed point near101.02°C. Thus route-only re-deposition of nonnegative wire heat cannot lower the GPU maximum to100.61°C with this placement, up to output rounding. This conditional bound is rigorous for the fixed linear model; it is not a bound when die placement changes K or endpoint PHY deposition. Test equal-length alternative routes, which can improve small differences without added power. Falsification of an expected small gain: all equivalent paths produce equal or worse critical peaks across both grids. Current weighted slack is55.2GB/s·mm; a one-pitch out-and-back detour adds1mm (300 or600 weighted units), so positive detours require shortening other routes or changing placement first.

4. **HBM improvement can use asymmetry instead of uniformly increasing spacing.** Shift H2 away from its bank-hotspot-facing G2 neighbor while preserving sufficient distance from G3, exploiting released upper-ring route budget. Predict H2 memory cools while some nonlimiting dies warm. Falsification: the other GPU or HBM peak takes over above the old maximum, or benefit disappears at128.

5. **Part of the plateau is cooling-boundary and mesh phase, not exhausted geometry.** Translation data shows dramatic nonlinear changes near top contact. Separate geometry changes from pure grid-phase tuning using64/128 paired checks and small perturbations. Falsification: gains persist across grid/perturbation and arise primarily from changed inter-die coupling, rather than contact cell inclusion; then topology and constraints explain more of the plateau.

## Reproduce

Run inside the existing local search image, with no network and no Docker-socket mount:

```sh
docker run --rm --network none --cpus 6 --memory 4g \
  -v "$PWD:/work" -v "$PWD/.cache/challenge:/challenge:ro" \
  supah-silicon-search:local simulation/research-v3/physics/diagnose.py \
  --grid 64 --workers 3 --output simulation/research-v3/physics/incumbent-64
```

Change grid/output to128 for the finer diagnostic. The35 independent solves comprise five full benchmark workload sources and10 component sources for each of the three potentially limiting workloads. Raw floorplans, traces, and retained grids are in each output's `inputs/` directory and ignored by Git. Reports include solver/submission hashes, source watts, per-die maxima/coordinates, attribution, summation residuals, solve count, elapsed and aggregate workload seconds. The pinned solver is never edited. The diagnostic code never writes inside the challenge checkout.

## 128-grid cross-check

The finer diagnostic completed35 solves in55.44s versus5.33s at64 (three concurrent workloads, six-CPU container cap). Its native GPU/HBM peaks are101.70/94.23°C, each0.01°C below the incumbent pinned report. Source-superposition residual is≤0.02°C.

| Case | Thermal hotspot x,y mm | Peak °C | Own rise °C | Wire rise °C |
|---|---|---:|---:|---:|
| G0 / skewed_compute | 7.109375, 6.7265625 | 101.70 | 56.12 | 0.38 |
| G3 / tensor_training | 13.609375, 38.2265625 | 101.16 | 48.74 | 0.29 |
| G2 / tensor_training | 44.890625, 38.5546875 | 100.78 | 47.14 | 0.24 |
| H2 / memory_stream | 31.890625, 35.2734375 | 94.23 | 28.44 | 0.98 |

G0's64→128 increase is0.31°C, of which0.29°C comes from its own source. Remote source contributions are nearly unchanged. This makes its apparent64-grid sweet spot especially important to validate at128 and under small perturbations. Upper GPU maxima remain beyond the contact edge at128: the cooling-boundary diagnosis survives refinement. H2's neighbor attribution remains strong (G2=9.36°C,G3=7.75°C), so the asymmetry hypothesis also survives.

## Scientific figure

![Incumbent hotspot locations and source attribution](incumbent-physics.png)

`plot_diagnosis.py` renders the figure directly from both diagnostic reports. The source bars sum contributions evaluated at each grid's full-run hotspot; bar-end values are full-run absolute temperatures. Plotting requires Matplotlib, available in the existing `supah-silicon-sim:local` image:

```sh
docker run --rm --network none --platform linux/amd64 --cpus 2 --memory 2g \
  -v "$PWD:/work" supah-silicon-sim:local \
  simulation/research-v3/physics/plot_diagnosis.py
```
