# Runs

Raw records of every test we ran, so anyone can check our numbers.

| Folder | What it is |
|---|---|
| `search/01_first_search_coarse_grid.jsonl` | First search: 150 layouts scored with the fast 16 × 16 estimate. Its best became layout `p1` (official score 0.9987). |
| `search/02_second_search_exact_gpu.jsonl` | Second search: 45 layouts scored with the exact GPU check (official 64 × 64 grid, the two GPU-deciding workloads). Its best became layout `p2`, Supah-Silicon (official score 0.9873). |
| `official_run_20261018/` | The organizers' own runner on the reference, our first guess and Supah-Silicon. `results.json` has every chip's peak temperature in every workload; `layouts.json` is the exact input. |

Each line of a `.jsonl` search log is one test: the chip positions (`layout`), the hottest GPU and memory temperatures it produced (`gpu`, `hbm`), the search's own score for it (`proxy`), and whether the search kept it (`accepted`). Search-log temperatures come from our fast checks; only `layouts/*/report.json` and `official_run_*` are official scores.
