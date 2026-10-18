"""Publish only a hash-matched, fully pinned-verified local candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
p=argparse.ArgumentParser();p.add_argument('candidate',type=Path);a=p.parse_args()
original=json.loads((OUT/'integrity-before.json').read_text())
changed=[name for name,digest in original.items() if sha(ROOT/name)!=digest]
assert not changed, changed
assert sha(OUT/'incumbent.json')==sha(ROOT/'simulation/layouts/supah-v2/submission.json')
digest=sha(a.candidate/'submission.json')
expected=set(json.loads((ROOT/'.cache/challenge/challenge_spec.json').read_text())['workloads'])
comparisons={};rows=[]
for grid in [64,128]:
    old=json.loads((ROOT/f'simulation/layouts/supah-v2/verification-{grid}.json').read_text())
    new=json.loads((a.candidate/f'verification-{grid}.json').read_text())
    assert new['passed'] and new['constraints']['passed'] and new['grid']==grid
    assert set(new['workloads'])==expected and set(old['workloads'])==expected
    assert new['provenance']['submission_sha256']==digest
    assert new['hotspot_sha256']==old['hotspot_sha256']=='5c3fcad8ae63144b218d2fc1de28ea862f5c6d3751e7ab381d576e5c00cab4bb'
    assert new['reference_c']==old['reference_c']
    for name,h in new['provenance']['files_sha256'].items():assert sha(ROOT/'.cache/challenge'/name)==h
    comparisons[str(grid)]={'incumbent':old,'candidate':new,'score_delta':round(new['score']-old['score'],8)}
    for w in new['workloads']:
        o,n=old['workloads'][w],new['workloads'][w]
        rows.append(f"| {grid} | {w} | {o['gpu_peak_c']:.2f} → {n['gpu_peak_c']:.2f} | {o['hbm_peak_c']:.2f} → {n['hbm_peak_c']:.2f} |")
assert comparisons['64']['candidate']['score']<.95979394
for name in ['submission.json','verification-64.json','verification-128.json']:shutil.copy2(a.candidate/name,OUT/name)
counts={}
for path in sorted(OUT.glob('*/search.jsonl')):
    lines=[json.loads(line) for line in path.read_text().splitlines()]
    counts[path.parent.name]={'candidate_evaluations':len(lines),'workload_simulations':sum(len(r.get('peaks',{})) for r in lines),
        'stopped_early':(path.parent/'termination.json').exists()}
audit={'preserved_files':original,'all_preserved_hashes_match':not changed,'submission_sha256':digest,
       'selected_candidate':str(a.candidate.relative_to(ROOT)),'verified_grids':[64,128],
       'verified_workloads':sorted(expected),'counts':counts,
       'logged_candidate_evaluations':sum(r['candidate_evaluations'] for r in counts.values()),
       'count_note':'Includes repeated controls and precision rescreens; excludes inherited history, unlogged original-native precision calibration controls, and pinned final verification runs.',
       'challenge_revision':'8948d9bc5e3aa041dcd1ff8a5a63ed6200d04d81',
       'execution':'Local CPU Docker, network disabled; no AutoLab Docker socket access or rented compute.'}
write(OUT/'audit.json',audit);write(OUT/'comparison.json',comparisons)
summary=[]
for grid,c in comparisons.items():
    o,n=c['incumbent'],c['candidate']
    summary.append(f"| {grid} | {o['score']:.8f} | **{n['score']:.8f}** | {o['worst_gpu_c']:.2f} → {n['worst_gpu_c']:.2f} | {o['worst_hbm_c']:.2f} → {n['worst_hbm_c']:.2f} |")
inc=json.loads((OUT/'incumbent.json').read_text())['placements_mm'];lay=json.loads((OUT/'submission.json').read_text())['placements_mm']
placement_rows=[f"| {d} | {lay[d][0]:.6f} | {lay[d][1]:.6f} | {lay[d][0]-inc[d][0]:+.6f} | {lay[d][1]-inc[d][1]:+.6f} |" for d in inc]
count_rows=[f"| {name} | {v['candidate_evaluations']} | {v['workload_simulations']} | {'stopped after plateau' if v['stopped_early'] else 'completed'} |" for name,v in counts.items()]
best64=comparisons['64']['candidate'];constraints=best64['constraints']
report=f'''# Placement iteration v4: verified improvement

The saved [submission.json](submission.json) beats the requested **0.95979394** threshold with a pinned 64-grid score of **{best64['score']:.8f}**. **The 0.95 target was not reached.** The v2 incumbent, signed report, original verification reports, challenge inputs and pinned evaluator remain byte-for-byte unchanged; see [audit.json](audit.json).

## Pinned results

Both candidate reports use the original pinned evaluator and all five workloads. Reference temperatures are matched separately to each grid. These are local verification reports, not new signed AutoLab results or leaderboard submissions.

| Grid | Incumbent score | Candidate score | GPU maximum °C, old → new | HBM maximum °C, old → new |
|---|---:|---:|---:|---:|
{chr(10).join(summary)}

Reports: [64 grid](verification-64.json), [128 grid](verification-128.json), [full comparison](comparison.json). The HBM column explicitly records any tradeoff; the benchmark score is the maximum normalized temperature rise, not an average.

At 64, 0.95 requires GPU ≤100.61 °C and HBM ≤94.04 °C at the judge's two-decimal precision. This candidate still needs {best64['worst_gpu_c']-100.61:.2f} °C GPU cooling and {max(0,best64['worst_hbm_c']-94.04):.2f} °C HBM cooling. These experiments do not prove that 0.95 is impossible.

## What worked

A quadratic response model with an adaptive trust region found coordinated changes that the prior rounded-score searches missed. The first pinned improvement tied 0.95979394. A subsequent constrained finite-difference search and precision rescreen resolved small differences between candidates that all printed the same native temperature. A final memory-focused sweep moved H2 and adjusted neighboring dies to recover HBM cooling while retaining the verified GPU improvement.

The additional search build changes **one output format**, from two decimal digits to eight, in the native solver's steady-grid text writer. It changes no equations, material data, hardware, cooling, heat inputs or judge scoring. [Build provenance](precision-build.json) records the exact replacement and hashes; its original source hash matches the pinned source checkout. Each precision search calibrated its rounded per-die peaks against the existing native binary. Unrounded numbers guide exploration only; all scores in the table above come from the unchanged pinned binary.

The frozen route-cell constraints include exact port access lengths and route budgets; every simulated candidate also passes the unmodified organizer validator. Larger coordinated neighbor projections, random connected-group moves and a fine G0 basin sweep were tested. Broad random, pattern and late gradient searches were stopped after plateaus. The independent [search audit](search-audit.json) revalidated all 3,628 unique logged submissions, including measured die movements as large as 2.733 mm from the incumbent.

Exhaustive equal-length routing tests were run at both the initial seed and the improved placement: 129 single-link alternatives per placement, plus controls and a combined-route candidate. None improved the primary native score over its corresponding control. The winner retains automatic routing.

## Placement and legality

| Die | New x mm | New y mm | Δx mm | Δy mm |
|---|---:|---:|---:|---:|
{chr(10).join(placement_rows)}

Weighted route length is **{constraints['weighted_route_gb_s_mm']:.2f} / {constraints['route_limit_gb_s_mm']:.2f} GB/s·mm**. Minimum die separation is **{constraints['minimum_die_separation_mm']:.6f} mm**. All individual reach, port capacity, package-edge and separation checks passed. Hardware and die orientations are unchanged.

Submission SHA-256: `{digest}`.

## All five workloads at both grids

| Grid | Workload | GPU peak °C, incumbent → candidate | HBM peak °C, incumbent → candidate |
|---|---|---:|---:|
{chr(10).join(rows)}

## Experiment accounting

| Experiment | Logged candidate evaluations | Workload solves | Status |
|---|---:|---:|---|
{chr(10).join(count_rows)}

These counts include repeated controls and precision rescreens, and exclude inherited histories, additional original-native calibration controls and pinned verification. Every retained observation and submission is in its experiment's `search.jsonl`; manifests retain seeds, source/input hashes and budgets. Early-stopped searches retain their actual completed counts and termination reason.

## Reproduce verification

From the repository root, with the existing local images:

```sh
./simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v4/submission.json --grid 64 --output simulation/results/v4-recheck-64.json
./simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v4/submission.json --grid 128 --output simulation/results/v4-recheck-128.json
```

The launcher checks challenge revision `8948d9bc5e3aa041dcd1ff8a5a63ed6200d04d81`, uses local network-disabled containers, and mounts `/challenge` read-only. It does not mount a Docker socket. No paid compute or AutoLab connection was used. To reproduce the search-only output precision build, run `simulation/research-v4/build_precision.py` through the launcher's `native` mode; then use `precise_search.py` with a new output directory and the saved manifest arguments.
'''
(OUT/'README.md').write_text(report)
print(json.dumps({'selected':audit['selected_candidate'],'scores':{g:c['candidate']['score'] for g,c in comparisons.items()},'evaluations':audit['logged_candidate_evaluations'],'sha256':digest},indent=2))
