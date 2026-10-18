"""Resolve tied native screens using more printed digits from identical equations."""
import os
from pathlib import Path
import json
import hashlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact,key,write_json

out=ROOT/'simulation/research-v4/precision-rescreen';out.mkdir(exist_ok=False)
files=[ROOT/f'simulation/research-v4/{name}/search.jsonl' for name in
       ['quadratic','g0-polish','pattern','placement-from-quadratic']]
source={}
for file in files:
    for line in file.read_text().splitlines():
        r=json.loads(line)
        if r['gpu']<=101.38:source[key(r['submission'])]={'source_file':str(file.relative_to(ROOT)),
            'source_evaluation':r.get('evaluation'),'source_peaks':r['peaks'],'submission':r['submission']}
write_json(out/'manifest.json',{'kind':'native output-precision tie resolution; not certification',
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'candidates':len(source),'inputs':list(source.values())})
start=time.monotonic();best=1e6
def run(item):
    sub=item['submission'];r=fast.estimate(sub['placements_mm'],64,1,['skewed_compute'])
    g=r['grids']['skewed_compute'];x,y=sub['placements_mm']['G0'];xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw=float(g[np.ix_((yy>=y)&(yy<y+10.5),(xx>=x)&(xx<x+11.5))].max())
    return {**item,**compact(r),'raw_g0_c':raw}
with ThreadPoolExecutor(max_workers=2) as pool,(out/'search.jsonl').open('w') as log:
    for i,r in enumerate(pool.map(run,source.values())):
        r.update(evaluation=i,elapsed_seconds=time.monotonic()-start)
        log.write(json.dumps(r)+'\n');log.flush()
        if r['raw_g0_c']<best:
            best=r['raw_g0_c'];write_json(out/'submission.json',r['submission'])
            print('BEST',i,f'{best:.8f}',r['source_file'],r['source_evaluation'],flush=True)
        write_json(out/'summary.json',{'evaluations':i+1,'total':len(source),'best_raw_g0_c':best,'elapsed_seconds':time.monotonic()-start})
