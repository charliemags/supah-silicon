# Run it and see it

Three ways to see Supah-Silicon's tests, from zero effort to fully hands-on.

## 1. Just look (no setup)

Everything we've run is already saved in this repo:

| What | Where |
|---|---|
| The story of how we got here, with pictures | [`../STORY.md`](../STORY.md) |
| Official temperature maps: reference vs. first guess vs. Supah-Silicon, all five workloads | [`../img/temperature_maps.png`](../img/temperature_maps.png) |
| Heat maps of single layouts | [`../img/`](../img/) |
| The exact numbers behind every score | `../layouts/<name>/report.json` |

**How to read a temperature map.** Each picture is the chip seen from above. The rectangles are the 8 chips (GPUs are larger). The color is temperature: dark is cool, bright yellow is hot. The dashed box is the well-cooled part of the thermal paste. The hottest yellow spot on any GPU and on any memory stack sets the score.

## 2. Run it in your browser (no install, about 10 minutes)

GitHub Codespaces gives you a free Linux computer inside your browser, which is exactly what the simulator needs.

1. Open https://github.com/charliemags/supah-silicon.
2. Click the green **Code** button → **Codespaces** tab → **Create codespace on main**.
3. When the editor opens, click into the **Terminal** at the bottom and type:
   ```bash
   bash simulation/run.sh
   ```
4. Wait about 5–10 minutes. It downloads the organizers' simulator, checks the rules, runs all five workloads for the reference layout and our best layout, then prints a table like this:
   ```
   layout                  hottest GPU  hottest HBM    score
   reference                  104.59 C     97.68 C   1.0000
   p2                         103.58 C     95.17 C   0.9873
   ```
5. In the file list on the left, open `simulation/output/<today's time>/temperature_maps.png`. That's the test result, as a picture.

To test your own layout, save it as a JSON file (same format as `simulation/layouts/p2/submission.json`) and run:
```bash
bash simulation/run.sh simulation/layouts/p2/submission.json my_layout.json
```

## 3. Run it on your own computer

**Linux (Intel/AMD) or Windows with WSL:** clone this repo and run `bash simulation/run.sh`. It needs Python 3 and git.

**Mac:** the official HotSpot program is built for Linux on Intel/AMD chips, so it won't run directly on macOS. Two options:
- **Docker Desktop.** From the repo folder:
  ```bash
  docker run --rm -it --platform linux/amd64 -v "$PWD":/work -w /work python:3.12 bash simulation/run.sh
  ```
  On Apple Silicon this runs through emulation, so expect it to be several times slower. We haven't timed it on a Mac.
- **Codespaces** (option 2): usually the simplest.

## 4. Drag chips around and watch (the organizers' GUI)

The organizers' [Chiplet Thermal Studio](https://github.com/Czaja107/chiplet-thermal-gui) is a desktop app. You drag chips, rules are re-checked as you go, and you can see where heat is produced in real time. Our layouts load straight into it with **Import layout**. It runs on Mac for everything except the final temperature solve, which needs a HotSpot program it can run. See [the organizer tools guide](06-the-organizer-tools.md).

## What "a test" is, in one paragraph

A test is one layout run through the five workloads. For each workload, HotSpot computes the steady temperature of every small block of the package. The test records the hottest GPU spot and the hottest memory spot across all five, and compares them with the organizers' reference layout. That ratio is the score. Every official number in this repo came from that same test, run by the organizers' own code.
