# Searching for a cool layout

## The search: simulated annealing

`tools/climb.py` works like a careful hill-walker in fog:

1. Start from a legal layout.
2. Nudge it: move one or two chips a little, slide everything together, or swap two chips of the same kind.
3. Throw away anything that breaks the rules (checking is instant).
4. Simulate the rest. If it's cooler, keep it. If it's a bit hotter, sometimes keep it anyway, so the search can climb out of dead ends. That "sometimes" gets rarer over time.
5. Steps start big (about 1.5 mm) and shrink (to about 0.15 mm) as the search settles.

Every layout tried is logged, so nothing is lost.

## Option: AI-guided search (from "See it to Place it")

The VeoPlace paper ("See it to Place it: Evolving Macro Placements with Vision-Language Models", ICML submission under review) adds an AI that *looks at pictures* of past layouts and their scores, then suggests a box where each chip should go. The normal search then works inside those boxes.

The paper only optimized wire length. We point it at heat, so the AI looks at heat maps (`tools/render.py` draws them). What we copy from the paper:
- Show the AI 10–25 past layouts from one family of similar good designs, not just the single best (showing only the best got stuck in the paper).
- Ask it to explore, not just tweak (exploring won in the paper).
- Pull gently toward its boxes, so the search can still leave a box when the heat says so.
- Run half the attempts guided and half unguided, with the same simulation budget, so the comparison is fair.

## What the physics has taught us so far

| Idea | Result | Why |
|---|---|---|
| Move every chip into the well-cooled center area | **Worse** (1.003) | Fitting everything inside packed the chips closer, so they heated each other more. |
| Turn the GPUs so their hot spots face the middle | **Much worse** (GPU 108.0 °C) | The middle collects heat from all four GPUs. |
| Spread the GPUs toward the outer corners, hot spots facing outward | **Better** (0.9873) | Each hot GPU gets room, and its hot spot sits near cooler surroundings. |

The GPU sets the score. During the compute-heavy workloads each hot GPU mostly heats itself, so moving it changes its peak by tenths of a degree. That is why exact simulation matters.

## Results so far (official, 64 × 64)

| Layout | Score | Hottest GPU | Hottest memory |
|---|---|---|---|
| Organizer reference | 1.000 | 104.59 °C | 97.68 °C |
| v0: all chips in the well-cooled area | 1.003 | 104.66 °C | 97.90 °C |
| p1: first search, coarse grid | 0.9987 | 104.49 °C | 96.12 °C |
| **p2: second search, exact GPU check** | **0.9873** | **103.58 °C** | **95.17 °C** |
