# How the heat simulation works

This explains, in plain English, what happens when a chip layout gets a temperature. Everything here describes the organizer's simulator ([Czaja107/chiplet-thermal-simulator](https://github.com/Czaja107/chiplet-thermal-simulator)), which we use unchanged for every official number.

## The short version

1. You say where the 8 chips sit on the base slab.
2. The simulator works out where every watt of heat is made: inside the chips, and along the wires between them.
3. It slices the package into a fine grid of small blocks, stacked in layers.
4. It solves for the temperature of every block once the chip has run long enough to settle (a "steady state": heat in equals heat out).
5. It reports the hottest spot on any GPU and the hottest spot on any memory stack, across five different workloads.

## What is being simulated

**The chips.** 4 GPUs (11.5 × 10.5 mm each) and 4 HBM memory stacks (10.5 × 10.2 mm each). Their sizes, orientations and heat patterns are fixed by the challenge. Only their positions change.

**The package, bottom to top:**

| Layer | What it is | Thickness | Notes |
|---|---|---|---|
| Interposer | The silicon base slab all chips sit on, 52 × 42 mm | 500 µm | Carries the wires between chips. Wire heat and half of the link-port heat go here. |
| Chip layer | The 8 chips, plus filler in the gaps between them | 150 µm | Chip heat goes here. The filler conducts heat about 260× worse than silicon. |
| Thermal paste (TIM) | The thin layer between the chips and the metal lid | 20 µm | A central 44 × 34 mm area conducts well. Outside it, the paste is 8× worse. |
| Spreader | Copper plate that spreads heat sideways | 55 mm wide | Fixed. |
| Heat sink | Copper block cooled by air or liquid | 60 mm wide | Fixed. Connects to the 25 °C room through a 0.08 °C-per-watt cooling path. |

The cooler never moves. When chips move, they move relative to the good and bad parts of the thermal paste.

## Where the heat comes from

**Inside each chip.** Every chip has a 16 × 16 map of where its watts are made. Each GPU has a strong compute hot spot in one corner; each memory stack has hot banks and a hot input/output area.

**The links between chips.** There are 8 required links:
- 4 main links, each GPU to its own memory: 600 GB/s each, wire no longer than 5 mm.
- 4 side links, each GPU to a neighbor's memory: 300 GB/s each, wire no longer than 6 mm.

Moving data costs energy, and that energy becomes heat:
- **Ports:** 0.2 picojoules per bit, split between the two ends. At each end, half the port heat lands just inside the chip edge and half on the interposer just outside it.
- **Wire:** 0.08 picojoules per bit for every millimetre of wire, spread along the wire path in the interposer.

Example from the organizer: a fully used 600 GB/s link, 4 mm long, makes about 0.96 W at its ports and about 1.5 W along its wire.

**How busy the links are depends on the workload**, so link heat changes from workload to workload.

## The five workloads

| Workload | GPU watts (G0–G3) | Memory watts (H0–H3) | Total (before links) |
|---|---|---|---|
| tensor_training | 88, 94, 86, 90 | 10, 11, 10, 10 | 399 W |
| skewed_compute | 104, 56, 92, 48 | 12, 10, 11, 9 | 342 W |
| attention_decode | 53, 57, 50, 55 | 24, 26, 25, 23 | 313 W |
| memory_stream | 44, 46, 42, 48 | 51, 49, 50, 53 | 383 W |
| mixed_serving | 72, 79, 54, 63 | 18, 15, 24, 19 | 344 W |

A layout has to survive all five. The hottest moment across all of them is what counts.

## How the temperature is solved

The simulator is **HotSpot**, a widely used research thermal model (Skadron et al., ISCA 2003; Huang et al., IEEE Trans. Computers 2008). It treats heat flow like electric current through a network of resistors:

- Each small block of material is a node.
- Neighboring blocks are joined by a "thermal resistance" that depends on the material and the block's size.
- Each block that makes heat injects its watts.
- The solver finds the temperature at every node so that heat flowing in equals heat flowing out everywhere.

The spreader and heat sink are gridded directly under the chip. Their outer rims are lumped into a few extra nodes. The heat sink finally dumps heat into the 25 °C room.

**Grid size.** The package is sliced into a 64 × 64 grid for normal scoring (each block about 0.8 × 0.7 mm) and 128 × 128 for the finals. A finer grid sees sharp hot spots better but takes much longer.

## How a layout is scored

1. **Rule check first.** Chips at least 1 mm apart and at least 1 mm from the edge; every link fits its port space and its maximum wire length; total wire use under a fixed budget. Break any rule and the layout is rejected before any heat is simulated.
2. **Heat simulation** for all five workloads.
3. **Score** = the larger of two ratios:
   - (hottest GPU − 25 °C) ÷ (reference layout's hottest GPU − 25 °C)
   - (hottest memory − 25 °C) ÷ (reference layout's hottest memory − 25 °C)

1.0 means "as hot as the organizer's reference layout." Lower is better. Because the score takes the worse of the two, the GPU and the memory both have to improve.

## What this model leaves out

The organizer says so plainly: cooling, filler, ports and wire energy are simplified, and the numbers are relative benchmark values, not real chip temperatures. Nothing here models chips slowing down when hot, wire delay, or signal quality. It is a fair, fixed playing field for comparing layouts.
