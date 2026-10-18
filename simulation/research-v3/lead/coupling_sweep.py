"""Controlled coordinated moves testing heat spreading versus neighbor coupling."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'simulation/tools'))
import fast
from optimize import compact

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)
base_path = ROOT / 'simulation/layouts/supah-v2/submission.json'
base = json.loads(base_path.read_text())['placements_mm']
manifest = {
    'purpose': 'native controlled screening; never an official score',
    'hypothesis': 'Moving connected neighbors can change lateral heat spreading as well as source coupling; southern upper-row movement can release route budget.',
    'solver_sha256': hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_sha256': hashlib.sha256(base_path.read_bytes()).hexdigest(),
    'challenge_files': {n: hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest()
                        for n in ('challenge_spec.json', 'workloads.json')},
    'grid': 64, 'workloads': 'all five',
}
(out/'experiment.json').write_text(json.dumps(manifest, indent=2)+'\n')
groups = {
    'right_arc': ['H0','G1','H1','G2','H2'],
    'upper_arc': ['H1','G2','H2','G3','H3'],
    'top_row': ['G2','H2','G3'],
    'west_top_pair': ['G3','H3'],
}
proposals = [('incumbent', {d:list(v) for d,v in base.items()})]
for name, group in groups.items():
    for axis in (0,1):
        for delta in (-3.,-2.,-1.,-.5,-.25,.25,.5,1.,2.):
            lay = {d:list(v) for d,v in base.items()}
            for d in group:
                lay[d][axis] = round(lay[d][axis]+delta, 3)
            proposals.append((f'{name}-axis{axis}-{delta:+g}', lay))
started = time.monotonic()
best = float('inf')
with (out/'results.jsonl').open('w') as f:
    for name, lay in proposals:
        ok, reason, routing = fast.legal(lay)
        record = {'name':name, 'submission':{'placements_mm':lay},
                  'valid':ok, 'reason':reason}
        if ok:
            result = compact(fast.estimate(lay,64,workers=2))
            value = max((result['gpu']-25)/79.59,(result['hbm']-25)/72.68)
            record.update(result=result, screen_score=value,
                          weighted_route=routing['weighted_route_gb_s_mm'])
            if value < best:
                best = value
                (out/'submission.json').write_text(json.dumps(record['submission'],indent=2)+'\n')
            print(name, result['gpu'], result['hbm'], flush=True)
        record['elapsed_seconds'] = round(time.monotonic()-started,3)
        f.write(json.dumps(record)+'\n');f.flush()
