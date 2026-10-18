"""Exact-valid two-coordinate basin scan; every value is measured in Docker."""
import argparse
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
import numpy as np
from search import measure
import fast
from optimize import write_json

p=argparse.ArgumentParser();p.add_argument('--start',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--die',default='G0');p.add_argument('--extent',type=float,nargs=2,default=[.025,.08]);p.add_argument('--step',type=float,default=.004)
a=p.parse_args();a.output.mkdir(exist_ok=False)
base=json.loads(a.start.read_text());candidates=[];rejected=0;t0=time.monotonic()
write_json(a.output/'manifest.json',{'kind':'native two-coordinate screening; pinned verification required',
    'args':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_sha256':hashlib.sha256(a.start.read_bytes()).hexdigest()})
for dx in np.arange(-a.extent[0],a.extent[0]+.00001,a.step):
    for dy in np.arange(-a.extent[1],a.extent[1]+.00001,a.step):
        lay={d:list(xy) for d,xy in base['placements_mm'].items()}
        lay[a.die]=[round(lay[a.die][0]+dx,3),round(lay[a.die][1]+dy,3)]
        sub={'placements_mm':lay}
        if fast.legal(lay)[0]:candidates.append(sub)
        else:rejected+=1
print('VALID',len(candidates),'REJECTED',rejected,flush=True)
best=None
with ThreadPoolExecutor(max_workers=2) as pool,(a.output/'search.jsonl').open('w') as log:
    for i,rec in enumerate(pool.map(lambda c:measure(c,['skewed_compute']),candidates)):
        rec.update(evaluation=i,elapsed_seconds=time.monotonic()-t0)
        log.write(json.dumps(rec)+'\n');log.flush()
        rank=(rec['screen_score'],rec['smooth_hotspot_c'])
        if best is None or rank<best:
            best=rank;write_json(a.output/'submission.json',rec['submission'])
            print('BEST',i,rec['gpu'],rec['smooth_hotspot_c'],rec['submission']['placements_mm'][a.die],flush=True)
write_json(a.output/'summary.json',{'evaluations':len(candidates),'rejected':rejected,'best_score':best[0],'elapsed_seconds':time.monotonic()-t0})
