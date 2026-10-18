# Making simulation faster

A full official simulation takes about 94 seconds. A search needs to try hundreds or thousands of layouts, so speed matters. Here is everything we measured, and the plan for going much faster.

## Option 1: a coarser grid (same physics, fewer blocks)

`tools/fast.py` runs the same HotSpot program with the same heat sources, but on a coarser grid.

| Grid | Time per layout (all 5 workloads, 2 cores) | How wrong is the hottest GPU? |
|---|---|---|
| 16 × 16 | ~2 s | Up to **4.4 °C too cool**. It blurs the small GPU hot spot. |
| 32 × 32 | ~9 s | 0.6–1.2 °C too cool |
| 64 × 64 (official) | ~94 s | Exact |
| 128 × 128 (finals) | Many minutes (not measured) | Finer than official |

**Lesson:** the coarse grids are fine for spotting big mistakes but can't rank good layouts. The differences we care about are tenths of a degree, smaller than the coarse grids' error. HotSpot also only accepts grid sizes that are powers of two (16, 32, 64, 128).

## Option 2: only simulate the workloads that matter

The GPU score is always set by `skewed_compute` or `tensor_training`. Running just those two at the official 64 grid takes about **39 seconds** and matches the official GPU number exactly (to 0.01 °C). The memory has about 2% headroom, so we check it with one full official run at the end.

This is what our searches use now: about 90 layouts per hour, all exact.

## Option 3 (next): a reduced-order model

**The key fact:** at a steady state this heat model is *linear*. Double the watts and you double the temperature rise. Temperatures from separate heat sources simply add up.

That opens two shortcuts:

**3a. Our own copy of the solver.** We read HotSpot's source code to copy exactly how it builds its resistor network, then write the whole network as one big sparse matrix in Python. The expensive step (factoring the matrix) is done once per layout; after that, all five workloads are nearly free. Expected: about 0.3–1 second per layout, about 5,000 layouts an hour, with the same answers as HotSpot if the copy is faithful.

Details we confirmed in the HotSpot source so the copy matches:
- In the chip layer, each grid block takes the material of whatever covers at least 95% of it; otherwise it blends materials by how much each covers.
- Neighboring blocks are joined through half of each block's resistance.
- The spreader and heat sink edges connect to a ring of extra "rim" nodes, and the sink connects to the room through the 0.08 °C-per-watt cooling path, shared out by area.
- The pinned build uses an iterative solver (no direct sparse solver library), so tiny rounding differences are expected.

**3b. A superposition model (the true reduced-order model).** Precompute, once, how a single watt placed at each spot warms everything around it. Two parts:
- a sharp "self" response, how a chip's own hot spot heats itself;
- a smooth "neighbor and package" response, how heat from one place warms another.

Any layout's temperatures are then just a weighted sum of these responses. That takes about a millisecond per layout, so millions of layouts an hour, plus free gradients (which direction to nudge each chip to cool it).

The catch: when a chip moves, the material under it changes (silicon vs. gap filler), which bends the "just add them up" rule a little. How much has to be measured, not assumed. Our pass bar: the hottest GPU within about 0.1 °C of the official number, and layouts ranked in the same order, checked against 20–30 official runs. If it misses, 3a is the fallback.

## The rule we never break

Fast models are for *searching*. Every number we report or submit comes from the official 64 × 64 simulation, through the organizer's own scorer.
