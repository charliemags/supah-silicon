# Simulation documents

Plain-English guides to how CRYO-GOBLIN is simulated and searched. Read them in order:

1. [How the heat simulation works](01-how-the-heat-simulation-works.md): the package, where heat comes from, how temperatures are solved and how a layout is scored.
2. [Running a simulation yourself](02-running-a-simulation.md): the commands, what you need, and how to read a result.
3. [Making simulation faster](03-faster-simulation.md): coarse grids, simulating only the workloads that matter, and the reduced-order model plan.
4. [Searching for a cool layout](04-searching-for-a-cool-layout.md): the search method, the AI-guided option, what the physics taught us, and the official results.
5. [CRYO-GOBLIN 2.0: simulating a 3D stack](05-3d-stacking-experiment.md): the 3D what-if, its assumptions and results.
6. [The organizers' two tools, and how we use them](06-the-organizer-tools.md): the scorer repo and the Chiplet Thermal Studio GUI, proof they compute the same thing, and what the GUI adds (hand-drawn wires, live heat-source previews, run comparisons).

Everything is built on the organizers' repos: [chiplet-thermal-simulator](https://github.com/Czaja107/chiplet-thermal-simulator) (power workloads + scorer + HotSpot) and [chiplet-thermal-gui](https://github.com/Czaja107/chiplet-thermal-gui) (the same plus a desktop GUI).

The code these documents describe is in [`../tools`](../tools).

## Glossary

- **2.5D:** chips side by side on a shared silicon base (the interposer), wired densely through it.
- **3D:** chips stacked on top of each other.
- **HBM:** high-bandwidth memory, a stack of memory chips with a very wide connection.
- **Interposer:** the silicon slab the chips sit on, carrying the wires between them.
- **TIM (thermal interface material):** the thin paste between the chips and the cooler.
- **Steady state:** the temperatures after the chip has run long enough that heat in equals heat out.
- **Grid:** how finely the package is sliced for the calculation. Finer means more accurate and slower.
- **Hot spot:** the hottest small area on a chip.
- **Reduced-order model:** a fast mathematical stand-in for the full simulation.
