"""Fresh all-workload native checks; pinned judge remains required for promotion."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'simulation/tools'))
import fast
from optimize import compact

p = argparse.ArgumentParser()
p.add_argument('submissions', nargs='+', type=Path)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--grids', nargs='+', type=int, default=[64, 128])
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = {'kind': 'fresh native screening, not pinned verification',
            'source_sha256': sha(Path(__file__)), 'solver_sha256': sha(fast.HOTSPOT),
            'inputs_sha256': {str(p): sha(p) for p in a.submissions}, 'grids': a.grids,
            'workloads': list(fast.PORTABLE['workloads'])}
(a.output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
started = time.monotonic()
records = []
with (a.output / 'results.jsonl').open('w') as log:
    for path in a.submissions:
        sub = json.loads(path.read_text())
        for grid in a.grids:
            result = fast.estimate(sub['placements_mm'], grid, workers=2,
                                   paths=sub.get('wire_routes_grid'))
            record = {'source': str(path), 'submission': sub, **compact(result),
                      'elapsed_seconds': time.monotonic()-started}
            if result['passed']:
                ref = json.loads((fast.HILL / f'reference_{grid}.json').read_text())
                record['screen_score'] = max((result['gpu']-25)/(ref['worst_gpu_c']-25),
                                             (result['hbm']-25)/(ref['worst_hbm_c']-25))
            records.append(record)
            log.write(json.dumps(record)+'\n'); log.flush()
            print(json.dumps({k: record[k] for k in ['source', 'grid', 'gpu', 'hbm', 'screen_score'] if k in record}), flush=True)
(a.output / 'summary.json').write_text(json.dumps(records, indent=2)+'\n')
