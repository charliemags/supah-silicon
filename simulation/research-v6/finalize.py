"""Promote only a hash-matched, pinned finalist that preserves both grid scores."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')

p = argparse.ArgumentParser()
p.add_argument('candidate', type=Path)
a = p.parse_args()
candidate = a.candidate.resolve()
digest = sha(candidate / 'submission.json')
spec = json.loads((ROOT / '.cache/challenge/challenge_spec.json').read_text())
comparison = {}
for grid in (64, 128):
    old = json.loads((OUT / f'preserved-v5/verification-{grid}.json').read_text())
    new = json.loads((candidate / f'verification-{grid}.json').read_text())
    original = json.loads((ROOT / f'simulation/layouts/supah-v2/verification-{grid}.json').read_text())
    assert new['passed'] and new['constraints']['passed'] and new['grid'] == grid
    assert set(new['workloads']) == set(old['workloads']) == set(spec['workloads'])
    assert new['provenance']['submission_sha256'] == digest
    assert new['hotspot_sha256'] == old['hotspot_sha256'] == sha(ROOT / '.cache/challenge/vendor/HotSpot/hotspot')
    assert new['reference_c'] == old['reference_c']
    assert new['score'] <= old['score']
    for name, expected in new['provenance']['files_sha256'].items():
        assert sha(ROOT / '.cache/challenge' / name) == expected
    comparison[str(grid)] = {'preserved_incumbent': old, 'original_incumbent': original,
                             'candidate': new, 'score_delta': round(new['score']-old['score'], 8)}
assert any(c['score_delta'] < 0 for c in comparison.values())
# Preserve the strongest confirmed 64-grid result found during this round.
confirmed64 = []
for path in OUT.rglob('verification-64.json'):
    report = json.loads(path.read_text())
    if report.get('passed') and report.get('grid') == 64 and report.get('hotspot_sha256') == comparison['64']['candidate']['hotspot_sha256']:
        confirmed64.append(report['score'])
assert comparison['64']['candidate']['score'] <= min(confirmed64)
subprocess.run([sys.executable, str(OUT / 'audit_search.py')], check=True)
audit = json.loads((OUT / 'audit.json').read_text())
audit['selected'] = str(candidate.relative_to(ROOT))
audit['selected_submission_sha256'] = digest
audit['selected_pinned_scores'] = {grid: c['candidate']['score'] for grid, c in comparison.items()}
for name in ('submission.json', 'verification-64.json', 'verification-128.json'):
    shutil.copy2(candidate / name, OUT / name)
write(OUT / 'audit.json', audit)
write(OUT / 'comparison.json', comparison)
lines = ['# Global placement optimization, round 6', '',
         'The saved submission improves the preserved best under the unchanged pinned evaluator. The 0.94 target was not reached. This is the best completed two-grid pinned candidate at the user-requested wrap-up; remaining searches and an unfinished additional verification were stopped.', '',
         '## Pinned results: all five workloads', '',
         '| Grid | Preserved v5 | New candidate | Change | GPU °C, old → new | HBM °C, old → new |',
         '|---|---:|---:|---:|---:|---:|']
for grid, c in comparison.items():
    o, n = c['preserved_incumbent'], c['candidate']
    lines.append(f"| {grid} | {o['score']:.8f} | **{n['score']:.8f}** | {c['score_delta']:+.8f} | {o['worst_gpu_c']:.2f} → {n['worst_gpu_c']:.2f} | {o['worst_hbm_c']:.2f} → {n['worst_hbm_c']:.2f} |")
lines += ['', '[Submission](submission.json) · [Pinned 64](verification-64.json) · [Pinned 128](verification-128.json) · [Comparison](comparison.json) · [Integrity audit](audit.json)', '',
          'These are local pinned verification results. Native screening values were used to select candidates, never substituted for pinned scores.', '',
          '## Experiments', '',
          'The useful breakthrough came from adaptive differential evolution with mixed-integer repair of placement and endpoint routing cells. It moved G0 together with its neighbors into a better region after broad surrogate-guided steps failed. A separate local minimax search refined the new region.', '',
          'The independent topology search tested concave, folded, inverted and offset arrangements. One new topology cooled G0 at exactly its preserved coordinates, but overheated another GPU; it was rejected. Fully contacted layouts also lost because of tighter thermal coupling. The topology model generated 111 exact-valid seeds from 26,240 geometry proposals; geometry proposals are not counted as thermal simulations.', '',
          'All 84 shortest S0 paths at the preserved placement were tested. The best lowered raw G0 by only 0.00015689°C and tied the pinned 64 score. It was not promoted. Explicit paths cannot change mandatory endpoints or facing edges; the automatic router already finds a shortest path. Longer routes cannot fit the preserved placement’s remaining weighted-route slack.', '',
          f"This round logged {audit['logged_candidate_evaluations']:,} completed native candidate evaluations ({audit['logged_workload_solves']:,} workload solves), including controls and rescreens. The independent audit replayed {audit['independently_revalidated_unique_submissions']:,} unique submissions through the original validator. Per-experiment counts and hashes are in audit.json.", '',
          'The original incumbent, research-v5 source files and saved results, hardware, physics, scoring, workloads and pinned evaluator remain unchanged. All 139 protected hashes match. All computation stayed in local Docker with networking disabled and the challenge mounted read-only. No AutoLab Docker socket connection or rented compute was used.', '',
          'A later native128 candidate is retained at global/joint128-relaxed-40/finalists/eval-010/submission.json. Its native screening score is 0.95949335, but pinned verification is incomplete, so it was not promoted. See selection-status.json for the selection cutoff.', '',
          'The search-only precise native build changes one output format string to expose additional temperature digits; its provenance is in ../research-v4/precision-build.json. Pinned verification uses the original binary.', '',
          '## Remaining gap', '',
          'At grid 64, a 0.94 score requires GPU ≤99.81°C and HBM ≤93.31°C at the evaluator’s output precision. These experiments did not reach those temperatures and do not prove the target impossible.', '',
          '## All workload peaks', '',
          '| Grid | Workload | GPU °C, old → new | HBM °C, old → new |', '|---|---|---:|---:|']
for grid, c in comparison.items():
    for w, n in c['candidate']['workloads'].items():
        o = c['preserved_incumbent']['workloads'][w]
        lines.append(f"| {grid} | {w} | {o['gpu_peak_c']:.2f} → {n['gpu_peak_c']:.2f} | {o['hbm_peak_c']:.2f} → {n['hbm_peak_c']:.2f} |")
lines += ['', f'Selected source: `{candidate.relative_to(ROOT)}`.', '', f'Submission SHA-256: `{digest}`.', '',
          '## Reproduce verification', '', '```sh',
          './simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v6/submission.json --grid 64 --output simulation/results/v6-recheck-64.json',
          './simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v6/submission.json --grid 128 --output simulation/results/v6-recheck-128.json', '```', '']
(OUT / 'README.md').write_text('\n'.join(lines))
print(json.dumps({'selected': str(candidate.relative_to(ROOT)), 'sha256': digest,
                  'scores': audit['selected_pinned_scores']}, indent=2))
