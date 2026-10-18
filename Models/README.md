# Models

Every Supah-Silicon design that beat the organizers' reference (score 1.0000), named by its official score. Lower is better.

| Rank | Model | Score (64 × 64) | Score (128 × 128 finals) | Hottest GPU | Hottest HBM | Found by |
|---|---|---|---|---|---|---|
| 1 | [Supah_0.9599 (v2)](../simulation/layouts/supah-v2/) | **0.95991959 (AutoLab signed)** | 0.96200150 (local pinned verification) | 101.40 °C | 94.16 °C | Additive GP and parallel placement search (Charlie) |
| 2 | [Supah_0.9719](Supah_0.9719/) | **0.9719** | 0.9747 (native estimate) | 102.35 °C | 95.50 °C | Bayesian optimization from Supah v1 (Zaiba) |
| 3 | [Supah_0.9812](../simulation/layouts/supah-v1/) | 0.9812 | 0.9811 | 103.09 °C | 95.56 °C | Bounded annealing from p2 (Charlie); lives in `simulation/layouts/supah-v1/` |
| 4 | [Supah_0.9873](Supah_0.9873/) | 0.9873 | 0.9891 | 103.58 °C | 95.17 °C | Second search, exact GPU check |
| 5 | [Supah_0.9987](Supah_0.9987/) | 0.9987 | not run | 104.49 °C | 96.12 °C | First search, fast estimate |

Earlier public leaderboard snapshot on 18 Oct 2026, 15:35 ET: #1 wilsonwu-ai 0.9623 (101.59 / 94.73 °C), #2 frido22 0.9644, #3 vyahhi 0.9647 (HBM 92.83 °C), #4 ottogin 0.9680, #5 czaja107 0.9685. Supah_0.9719 would rank 6th.

After the official v2 run on 18 Oct 2026 at 16:22 ET, **charliemags ranked #1 at 0.95991959**, ahead of vyahhi and wilsonwu-ai at 0.96180425. See the [signed report](../simulation/layouts/supah-v2/official-report-64.json) and [leaderboard snapshot](../simulation/layouts/supah-v2/autolab-leaderboard.jpg).

Reference for comparison: 104.59 °C GPU / 97.68 °C HBM on the 64 grid (104.74 / 97.70 °C on the 128 grid).

Designs that did not beat 1.0000, kept for the record in `simulation/layouts/`: the first guess `v0` (1.003) and the hot-spots-inward idea `r1` (GPU 108.01 °C).

Each folder has the layout (`submission.json`), its official scorer reports, a floorplan and a heat map. New models are added here only after an official score below 1.0000.
