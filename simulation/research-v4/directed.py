"""Substantial coordinated neighbor displacements with G0 held in its cool basin."""
import json
from pathlib import Path
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from search import measure, ROOT
from fixed_g0_projection import project
from optimize import write_json,key

out=ROOT/'simulation/research-v4/directed';out.mkdir(exist_ok=False)
base=json.loads((ROOT/'simulation/research-v4/finalists/quad-first/submission.json').read_text())
start=time.monotonic();candidates=[('control',base)];seen={key(base)};rejects=[]
write_json(out/'manifest.json',{'kind':'fixed-G0 projection; exact-validator-gated native screening',
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'projection_sha256':hashlib.sha256((Path(__file__).parent/'fixed_g0_projection.py').read_bytes()).hexdigest()})
for die,xs,ys in [('H3',np.linspace(6.4,7.3,10),np.linspace(17.3,18.1,9)),
                  ('H0',np.linspace(20.3,20.8,6),np.linspace(3.4,3.9,6)),
                  ('G3',np.linspace(9.7,10.7,6),np.linspace(28.5,29.05,6))]:
    for x in xs:
        for y in ys:
            name=f'{die}-{x:.3f}-{y:.3f}'
            candidate=project(base['placements_mm'],[x,y],die)
            if candidate is None:rejects.append(name);continue
            sub={'placements_mm':candidate}
            if key(sub) not in seen:candidates.append((name,sub));seen.add(key(sub))
write_json(out/'proposals.json',{'candidates':candidates,'rejected':rejects})
print('PROJECTED',len(candidates),'valid;',len(rejects),'rejected',flush=True)
best=float('inf')
with ThreadPoolExecutor(max_workers=2) as pool,(out/'search.jsonl').open('w') as log:
    for (name,sub),rec in zip(candidates,pool.map(lambda c:measure(c[1],None),candidates)):
        rec.update(name=name,elapsed_seconds=time.monotonic()-start)
        log.write(json.dumps(rec)+'\n');log.flush()
        if rec['screen_score']<best:
            best=rec['screen_score'];write_json(out/'submission.json',sub)
            print('BEST',name,best,rec['gpu'],rec['hbm'],flush=True)
write_json(out/'summary.json',{'evaluations':len(candidates),'rejected':len(rejects),'best_score':best,'elapsed_seconds':time.monotonic()-start})
