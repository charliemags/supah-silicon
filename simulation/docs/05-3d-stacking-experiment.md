# CRYO-GOBLIN 2.0: simulating a 3D stack

The challenge only scores flat (2.5D) layouts. To ask "what if we stacked the memory on the GPU?", `tools/stack3d.py` builds a 3D version using the **same** HotSpot program, the same five workloads and the same cooler, so the numbers can be compared with 1.0.

## How the 3D model is built

Each memory stack sits directly on its own GPU, centered. Two orders:
- **A, memory on top:** interposer → GPU → bond layer → memory → thermal paste → cooler. GPU heat has to pass through the memory to escape. This is the setup imec studied (IEDM 2025).
- **B, GPU on top:** interposer → memory → bond layer → GPU → thermal paste → cooler. The GPU touches the cooler directly. AMD used this trick when it moved its stacked cache under the CPU die.

Assumptions. These are not measured from a real product, so we sweep them instead of guessing one value:
- Memory stack: one 720 µm layer. Heat conductivity swept: 10 (poor) or 30 (good) W/m·K.
- Bond layer between the dies: 10 µm. Conductivity swept: 1.5 (bumps and glue) or 100 (direct copper bonding) W/m·K.
- Filler around the stacks: mold-like (the challenge's gap material) or silicon (imec's fix).
- The 600 GB/s main links become vertical: port heat only, no wire. Side links stay flat; their heat is added to the GPU, to be conservative.

## Results (coarse 32 × 32 grid; compare designs with each other, not to real chips)

| Design | Hottest GPU | Hottest memory |
|---|---|---|
| 1.0, flat (same grid, for comparison) | ~103.6 °C | ~95.6 °C |
| A, memory on top, worst variant | 197.3 °C | 152.3 °C |
| A, memory on top, best variant | 126.3 °C | 110.8 °C |
| B, GPU on top, worst variant | 119.1 °C | 132.6 °C |
| **B, GPU on top, best variant** (silicon filler, good memory conductivity, copper bonding) | **110.5 °C** | **110.5 °C** |

All 16 variants are in `results3d/sweep32.json`.

## What it means

1. **Which die goes on top decides almost everything.** With the same materials, GPU-on-top runs the GPU about 16–78 °C cooler than memory-on-top.
2. **Filler is the next lever.** With GPU-on-top, silicon filler beats mold by about 5 °C on the GPU. With memory-on-top it matters far more (16–42 °C), because the GPU's heat then has to squeeze around the memory.
3. **The bond type barely matters with GPU-on-top** (under 1 °C). With memory-on-top it is worth about 3–7 °C, again because the GPU's heat has to cross it.
4. **Memory heat is the open 3D problem.** Under a hot GPU the memory reaches 110–133 °C, well above the roughly 85 °C where DRAM is commonly expected to need more frequent refreshing (a general rule of thumb, not something this model checks).

imec reported the same direction: about 70 °C for flat to about 142 °C for naive memory-on-GPU, recovered to about 71 °C with a stack of fixes including bottom-side cooling ([IEEE Spectrum](https://spectrum.ieee.org/hbm-on-gpu-imec-iedm)).
