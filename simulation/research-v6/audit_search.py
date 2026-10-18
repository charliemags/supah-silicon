"""Independently validate logged experiments and preserved evaluator provenance."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.cache/challenge'))
from geometry import validate_layout

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

protected = json.loads((OUT / 'integrity-before.json').read_text())
changed = [p for p, digest in protected.items() if sha(ROOT / p) != digest]
assert not changed, changed
spec = json.loads((ROOT / '.cache/challenge/challenge_spec.json').read_text())
baseline = json.loads((OUT / 'preserved-v5/submission.json').read_text())
experiments = {}
unique = {}
records = []
paths = sorted(set(OUT.rglob('search.jsonl')) | set(OUT.rglob('results.jsonl')) | set(OUT.rglob('skewed-screen.json')))
for path in paths:
    snapshot = path.read_bytes()
    rows = (json.loads(snapshot) if path.suffix == '.json' else
            [json.loads(line) for line in snapshot.splitlines() if line.strip()])
    measured = [r for r in rows if r.get('passed') and r.get('peaks') and 'submission' in r]
    if not measured:
        continue
    experiments[str(path.relative_to(OUT))] = {
        'sha256': hashlib.sha256(snapshot).hexdigest(), 'candidate_evaluations': len(measured),
        'workload_solves': sum(len(r['peaks']) for r in measured),
        'grids': sorted(set(r['grid'] for r in measured)),
    }
    for row in measured:
        sub = row['submission']
        unique[json.dumps(sub, sort_keys=True)] = sub
        records.append((str(path.relative_to(OUT)), row))
max_move = 0
for sub in unique.values():
    validate_layout(spec, sub['placements_mm'], wire_routes_grid=sub.get('wire_routes_grid', {}))
    max_move = max(max_move, *(math.dist(xy, baseline['placements_mm'][d]) for d, xy in sub['placements_mm'].items()))
verification = {}
for grid in (64, 128):
    path = OUT / f'preserved-v5/verification-{grid}.json'
    report = json.loads(path.read_text())
    assert report['passed'] and report['constraints']['passed'] and report['grid'] == grid
    assert set(report['workloads']) == set(spec['workloads'])
    assert report['provenance']['submission_sha256'] == sha(OUT / 'preserved-v5/submission.json')
    assert report['hotspot_sha256'] == sha(ROOT / '.cache/challenge/vendor/HotSpot/hotspot')
    for name, digest in report['provenance']['files_sha256'].items():
        assert sha(ROOT / '.cache/challenge' / name) == digest
    verification[str(grid)] = {'score': report['score'], 'sha256': sha(path),
                               'workloads': list(report['workloads'])}
eligible = [(path, row) for path, row in records if row['grid'] == 64 and
            {'skewed_compute', 'tensor_training', 'memory_stream'} <= set(row['peaks'])]
best = min(eligible, key=lambda pair: max((pair[1]['gpu']-25)/79.59, (pair[1]['hbm']-25)/72.68))
audit = {
    'all_protected_hashes_unchanged': True, 'protected_files': len(protected),
    'protected_manifest_sha256': sha(OUT / 'integrity-before.json'),
    'repository_revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
    'challenge_revision': subprocess.check_output(['git', '-C', str(ROOT / '.cache/challenge'), 'rev-parse', 'HEAD'], text=True).strip(),
    'preserved_submission_sha256': sha(OUT / 'preserved-v5/submission.json'),
    'preserved_pinned_verification': verification,
    'logged_candidate_evaluations': len(records),
    'logged_workload_solves': sum(len(r['peaks']) for _, r in records),
    'independently_revalidated_unique_submissions': len(unique),
    'largest_die_displacement_from_preserved_mm': max_move,
    'best_three_workload_native64_screen': {'source': best[0], 'record': best[1]},
    'experiments': experiments,
    'count_note': 'Actual completed native solver screens only, including repeated controls and rescreens; geometry proposals, inherited observations, and copied reports excluded.',
    'execution': 'Local network-disabled Docker. Challenge read-only. No AutoLab Docker socket connection; no rented compute.',
}
(OUT / 'audit.json').write_text(json.dumps(audit, indent=2)+'\n')
print(json.dumps({k: audit[k] for k in ['all_protected_hashes_unchanged', 'protected_files', 'logged_candidate_evaluations', 'logged_workload_solves', 'independently_revalidated_unique_submissions']}, indent=2))
