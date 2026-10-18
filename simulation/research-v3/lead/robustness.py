"""Two-grid, all-workload screening of exact-valid small placement perturbations."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact
from verify_submission import verify

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('submission',type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
sub=json.loads(a.submission.read_text())
if sub.get('wire_routes_grid'):
    raise ValueError('This placement perturbation survey requires automatic routing')
manifest={'kind':'native robustness screening, not pinned certification',
          'submission_sha256':hashlib.sha256(a.submission.read_bytes()).hexdigest(),
          'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
          'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'grids':[64,128], 'workloads':'all five','steps_mm':[.005,.025]}
(a.output/'experiment.json').write_text(json.dumps(manifest,indent=2)+'\n')
proposals=[('unperturbed',sub)]
for h in (.005,.025):
    for axis in (0,1):
        for sign in (-1,1):
            for die in [*sub['placements_mm'],'all']:
                candidate=json.loads(json.dumps(sub))
                for d,v in candidate['placements_mm'].items():
                    if die in (d,'all'):
                        v[axis]=round(v[axis]+sign*h,6)
                proposals.append((f'{die}-axis{axis}-{sign*h:+g}',candidate))
start=time.monotonic()
with (a.output/'results.jsonl').open('w') as log:
    for name,candidate in proposals:
        candidate_path=a.output/f'{name}.json'
        candidate_path.write_text(json.dumps(candidate,indent=2)+'\n')
        validity=verify(candidate_path)
        record={'name':name,'submission':candidate,'validation':validity,
                'sha256':hashlib.sha256(candidate_path.read_bytes()).hexdigest()}
        if validity['passed']:
            record['results']={}
            for grid in (64,128):
                result=compact(fast.estimate(candidate['placements_mm'],grid,workers=2))
                ref=json.loads((fast.HILL/f'reference_{grid}.json').read_text())
                result['screen_score']=max((result['gpu']-25)/(ref['worst_gpu_c']-25),
                                           (result['hbm']-25)/(ref['worst_hbm_c']-25))
                record['results'][str(grid)]=result
            print(name,[(g,r['gpu'],r['hbm'])for g,r in record['results'].items()],flush=True)
        record['elapsed_seconds']=round(time.monotonic()-start,3)
        log.write(json.dumps(record)+'\n');log.flush()
