"""Reallocate legal route budget to reduce HBM without surrendering the GPU gain."""
import os,json,hashlib,itertools,time,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact,write_json,key
from surrogate import SCREEN
out=ROOT/'simulation/research-v4/memory-polish';out.mkdir(exist_ok=False)
basepath=ROOT/'simulation/research-v4/finalists/precision-best/submission.json'
base=json.loads(basepath.read_text());start=time.monotonic();candidates=[];rejected=0
for hx,hy,gy,iy in itertools.product([-.01,0,.01],[0,.01,.02,.03,.04,.06],[0,-.025,-.05,-.075,-.1],[0,-.025]):
    lay={d:list(xy) for d,xy in base['placements_mm'].items()}
    lay['H2'][0]+=hx;lay['H2'][1]+=hy;lay['G3'][1]+=gy;lay['H1'][1]+=iy
    sub={'placements_mm':{d:[round(v,6) for v in xy] for d,xy in lay.items()}}
    if fast.legal(sub['placements_mm'])[0]:candidates.append(sub)
    else:rejected+=1
write_json(out/'manifest.json',{'kind':'secondary HBM cooling with continuous G0 constraint; native only',
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_sha256':hashlib.sha256(basepath.read_bytes()).hexdigest(),'valid':len(candidates),'rejected':rejected})
print('VALID',len(candidates),'REJECTED',rejected,flush=True)
def run(sub):
    r=fast.estimate(sub['placements_mm'],64,3,SCREEN)
    g=r['grids']['skewed_compute'];x,y=sub['placements_mm']['G0'];xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw=float(g[np.ix_((yy>=y)&(yy<y+10.5),(xx>=x)&(xx<x+11.5))].max())
    return {'submission':sub,**compact(r),'raw_g0_c':raw,'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68)}
best=None
with ThreadPoolExecutor(max_workers=2) as pool,(out/'search.jsonl').open('w') as log:
    for i,r in enumerate(pool.map(run,candidates)):
        r.update(evaluation=i,elapsed_seconds=time.monotonic()-start)
        log.write(json.dumps(r)+'\n');log.flush()
        if r['raw_g0_c']<=101.3805 and r['gpu']<=101.38:
            rank=(r['hbm'],r['raw_g0_c'])
            if best is None or rank<best:
                best=rank;write_json(out/'submission.json',r['submission']);print('BEST',i,r['gpu'],r['hbm'],r['raw_g0_c'],flush=True)
        write_json(out/'summary.json',{'evaluations':i+1,'total':len(candidates),'best':best,'elapsed_seconds':time.monotonic()-start})
