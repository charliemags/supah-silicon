"""Publish a hash-matched pinned finalist and retain the incumbent unchanged."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.cache/challenge'))
from geometry import validate_layout

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

p = argparse.ArgumentParser()
p.add_argument('candidate', type=Path)
a = p.parse_args()
candidate = a.candidate.resolve()
protected = json.loads((ROOT / 'simulation/research-v4/integrity-before.json').read_text())
assert all(sha(ROOT / name) == digest for name, digest in protected.items())
spec = json.loads((ROOT / '.cache/challenge/challenge_spec.json').read_text())
inc_path = ROOT / 'simulation/layouts/supah-v2/submission.json'
inc = json.loads(inc_path.read_text())
submission = json.loads((candidate / 'submission.json').read_text())
digest = sha(candidate / 'submission.json')
comparison = {}
for grid in (64, 128):
    old = json.loads((inc_path.parent / f'verification-{grid}.json').read_text())
    new = json.loads((candidate / f'verification-{grid}.json').read_text())
    assert new['passed'] and new['constraints']['passed'] and new['grid'] == grid
    assert set(new['workloads']) == set(spec['workloads']) == set(old['workloads'])
    assert new['provenance']['submission_sha256'] == digest
    assert new['hotspot_sha256'] == old['hotspot_sha256'] == protected['.cache/challenge/vendor/HotSpot/hotspot']
    assert new['reference_c'] == old['reference_c']
    assert new['score'] < old['score']
    for name, value in new['provenance']['files_sha256'].items():
        assert sha(ROOT / '.cache/challenge' / name) == value
    comparison[str(grid)] = {'incumbent': old, 'candidate': new,
                              'score_delta': round(new['score'] - old['score'], 8)}
assert comparison['64']['candidate']['score'] < .95979394

counts = {}
unique = {}
for directory in (ROOT / 'simulation/research-v4', OUT):
    for path in sorted(directory.glob('*/search.jsonl')):
        records = [json.loads(line) for line in path.read_text().splitlines()]
        counts[str(path.parent.relative_to(ROOT / 'simulation'))] = {
            'candidate_evaluations': len(records),
            'workload_solves': sum(len(r.get('peaks', {})) for r in records),
            'stopped_early': (path.parent / 'termination.json').exists(),
        }
        for r in records:
            sub = r['submission']
            unique[json.dumps(sub, sort_keys=True)] = sub
max_move = 0
for sub in unique.values():
    validate_layout(spec, sub['placements_mm'], wire_routes_grid=sub.get('wire_routes_grid', {}))
    max_move = max(max_move, *(math.dist(xy, inc['placements_mm'][d]) for d, xy in sub['placements_mm'].items()))
audit = {'protected_sha256': protected, 'all_protected_hashes_unchanged': True,
         'repository_revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
         'challenge_revision': subprocess.check_output(['git', '-C', str(ROOT / '.cache/challenge'), 'rev-parse', 'HEAD'], text=True).strip(),
         'submission_sha256': digest, 'selected': str(candidate.relative_to(ROOT)),
         'verified_grids': [64, 128], 'verified_workloads': list(spec['workloads']),
         'independently_revalidated_unique_submissions': len(unique),
         'largest_die_displacement_mm': max_move, 'experiments': counts,
         'logged_candidate_evaluations': sum(c['candidate_evaluations'] for c in counts.values()),
         'count_note': 'Includes controls and rescreens; excludes inherited history, extra calibration controls, and pinned final verification.',
         'execution': 'Local network-disabled Docker only. No rented compute or AutoLab socket connection.'}
for name in ('submission.json', 'verification-64.json', 'verification-128.json'):
    shutil.copy2(candidate / name, OUT / name)
shutil.copy2(inc_path, OUT / 'incumbent.json')
write(OUT / 'audit.json', audit)
write(OUT / 'comparison.json', comparison)
lines = ['# Placement optimization results', '',
         'The saved submission beats 0.95979394. The requested 0.94 target was not reached.', '',
         '## Unchanged pinned evaluator, all five workloads', '',
         '| Grid | Incumbent | Candidate | Change | GPU °C, old → new | HBM °C, old → new |',
         '|---|---:|---:|---:|---:|---:|']
for grid, c in comparison.items():
    o, n = c['incumbent'], c['candidate']
    lines.append(f"| {grid} | {o['score']:.8f} | **{n['score']:.8f}** | {c['score_delta']:+.8f} | {o['worst_gpu_c']:.2f} → {n['worst_gpu_c']:.2f} | {o['worst_hbm_c']:.2f} → {n['worst_hbm_c']:.2f} |")
lines += ['', 'These are local pinned verification results, not signed AutoLab submissions. Each report records the submission and evaluator hashes. Both grids use their own unchanged reference temperatures.', '',
          'The GPU remains the limiting component. The memory peak increases slightly; the table records that tradeoff rather than claiming every temperature improved.', '',
          '[Saved submission](submission.json) · [64-grid report](verification-64.json) · [128-grid report](verification-128.json) · [Full comparison](comparison.json) · [Integrity and search audit](audit.json)', '',
          '![Actual incumbent and candidate placement](placement-comparison.png)', '',
          '## Search method', '',
          'The main improvement came from a mixed-integer proposal model that moves dies and changes endpoint routing cells together, followed by local thermal refinement. Larger G0 relocations, ring relabelings/reflections, fine position sweeps, and legal route alternatives were tested. Every simulated layout passed the original organizer validator.', '',
          'The faster native solver screens candidates. A search-only build prints eight digits instead of two in its steady temperature grid; it changes one output format string, not physics or scoring. Build provenance is in ../research-v4/precision-build.json. Only the original pinned binary supplies the scores above.', '',
          'No hardware, workload, cooling, material, geometry, interconnect or scoring rules were changed. The original incumbent and 21 protected files remain byte-for-byte unchanged. Search constraints are proposal aids; the original validator remains authoritative.', '',
          'At grid 64, 0.94 requires GPU ≤99.81°C and HBM ≤93.31°C at the evaluator’s output precision. The remaining gap is real; these experiments do not prove the target impossible.', '',
          '## All workload peaks', '',
          '| Grid | Workload | GPU °C, old → new | HBM °C, old → new |', '|---|---|---:|---:|']
for grid, c in comparison.items():
    for w, n in c['candidate']['workloads'].items():
        o = c['incumbent']['workloads'][w]
        lines.append(f"| {grid} | {w} | {o['gpu_peak_c']:.2f} → {n['gpu_peak_c']:.2f} | {o['hbm_peak_c']:.2f} → {n['hbm_peak_c']:.2f} |")
lines += ['', '## Evidence and reproduction', '',
          f"Logged candidate evaluations: {audit['logged_candidate_evaluations']}. Independently revalidated unique submissions: {len(unique)}. Counts include repeated controls and rescreens; see audit.json for per-experiment details.", '',
          f'Submission SHA-256: `{digest}`.', '',
          '```sh', './simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v5/submission.json --grid 64 --output simulation/results/v5-recheck-64.json',
          './simulation/research-v3/run pinned simulation/tools/evaluate.py simulation/research-v5/submission.json --grid 128 --output simulation/results/v5-recheck-128.json', '```', '',
          'All computation used local Docker with networking disabled and the challenge mounted read-only. No Docker socket was connected to AutoLab, and no compute was rented.', '']
(OUT / 'README.md').write_text('\n'.join(lines))
print(json.dumps({'scores': {g: c['candidate']['score'] for g, c in comparison.items()},
                  'submission_sha256': digest, 'evaluations': audit['logged_candidate_evaluations']}, indent=2))
