# supah-silicon

Sundai @ MIT hackathon, Track 2: design the coolest chiplet layout.

## Simulation

**Start here: [the Supah-Silicon story](simulation/STORY.md)**, how we found a cooler layout, in plain English with the official test outputs.

Run a test yourself (Linux, or a GitHub Codespace in your browser): `bash simulation/run.sh`

Everything about how we simulate and search chip layouts is in [`simulation/`](simulation/):

- [`simulation/docs/`](simulation/docs/README.md): plain-English guides (how the heat simulation works, how to run it, making it faster, searching for a cool layout, a 3D stacking experiment, and the organizers' simulator and GUI)
- [`simulation/tools/`](simulation/tools/): the search, fast-estimate, heat-map and 3D-stack code
- [`simulation/layouts/`](simulation/layouts/): every layout we scored, with the official reports. Best so far: `p2`, official score 0.9873 (GPU 103.58 °C, HBM 95.17 °C vs. 104.59 / 97.68 for the reference)

Built on the organizers' [chiplet-thermal-simulator](https://github.com/Czaja107/chiplet-thermal-simulator) and [chiplet-thermal-gui](https://github.com/Czaja107/chiplet-thermal-gui).
