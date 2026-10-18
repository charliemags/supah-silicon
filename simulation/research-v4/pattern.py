"""Fixed-G0 multi-scale pattern search with exact routes and measured acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import itertools
import time
import numpy as np
from search import measure
import fast
from surrogate import DIES, placement, vector, cheap_legal
from optimize import key,write_json

p=argparse.ArgumentParser();p.add_argument('--start',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--evals',type=int,default=600);a=p.parse_args();a.output.mkdir(exist_ok=False)
base=json.loads(a.start.read_text());t0=time.monotonic();rng=np.random.default_rng(405)
write_json(a.output/'manifest.json',{'kind':'multi-scale fixed-G0 pattern search, native screening only',
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_sha256':hashlib.sha256(a.start.read_bytes()).hexdigest(),'budget':a.evals,'seed':405})
states=[];seen=set();log=(a.output/'search.jsonl').open('w')
def rank(r):return (r['screen_score'],r['smooth_hotspot_c'],r['hbm'])
def save(r,**meta):
    r.update(evaluation=len(states),elapsed_seconds=time.monotonic()-t0,**meta);states.append(r)
    log.write(json.dumps(r)+'\n');log.flush()
    if r is min(states,key=rank):
        write_json(a.output/'submission.json',r['submission']);print('BEST',len(states),r['gpu'],r['hbm'],r['smooth_hotspot_c'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(states),'best_score':min(states,key=rank)['screen_score'],'elapsed_seconds':time.monotonic()-t0})
save(measure(base),kind='control');seen.add(key(base));anchor=states[0]
cycle=['H0','G1','H1','G2','H2','G3','H3']
groups=[cycle[i:i+n] for n in range(1,8) for i in range(8-n)]
directions=[]
for group in groups:
    for dx,dy in itertools.product([-1,0,1],repeat=2):
        if not(dx or dy):continue
        delta=np.zeros((8,2))
        for d in group:delta[DIES.index(d)]=[dx,dy]
        directions.append(delta.ravel())
# Anti-correlated moves redistribute individual reach and route budgets.
for d1,d2 in itertools.combinations(cycle,2):
    for axis in range(2):
        delta=np.zeros((8,2));delta[DIES.index(d1),axis]=1;delta[DIES.index(d2),axis]=-1
        directions.extend([delta.ravel(),-delta.ravel()])
with ThreadPoolExecutor(max_workers=2) as pool:
    for epoch in range(30):
        old=anchor
        scale=[.025,.075,.15,.3,.5][epoch%5]
        candidates=[];x=vector(anchor['submission']['placements_mm'])
        for direction in directions:
            v=x+scale*direction;sub={'placements_mm':placement(v)}
            if key(sub) not in seen and cheap_legal(v) and fast.legal(sub['placements_mm'])[0]:
                seen.add(key(sub));candidates.append(sub)
        rng.shuffle(candidates);candidates=candidates[:min(96,a.evals-len(states))]
        for rec in pool.map(measure,candidates):
            save(rec,kind='pattern',epoch=epoch,step_mm=scale)
            if rank(rec)<rank(anchor):anchor=rec
        print('EPOCH',epoch,'tested',len(candidates),'best',anchor['gpu'],anchor['smooth_hotspot_c'],flush=True)
        if len(states)>=a.evals:break
log.close()
