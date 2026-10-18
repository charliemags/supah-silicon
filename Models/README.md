# Models

Every Supah-Silicon design that beat the organizers' reference (score 1.0000), named by its official score. Lower is better.

| Rank | Model | Score (64 × 64) | Score (128 × 128 finals) | Hottest GPU | Hottest HBM | Found by |
|---|---|---|---|---|---|---|
| 1 | [Supah_0.9873](Supah_0.9873/) | **0.9873** | **0.9891** | 103.58 °C | 95.17 °C | Second search, exact GPU check |
| 2 | [Supah_0.9987](Supah_0.9987/) | 0.9987 | not run | 104.49 °C | 96.12 °C | First search, fast estimate |

Reference for comparison: 104.59 °C GPU / 97.68 °C HBM on the 64 grid (104.74 / 97.70 °C on the 128 grid).

Designs that did not beat 1.0000, kept for the record in `simulation/layouts/`: the first guess `v0` (1.003) and the hot-spots-inward idea `r1` (GPU 108.01 °C).

Each folder has the layout (`submission.json`), its official scorer reports, a floorplan and a heat map. New models are added here only after an official score below 1.0000.
