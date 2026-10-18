"""Cross-track-cell mixed-integer thermal placement search in local Docker."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact,key,write_json
from surrogate import DIES,SCREEN,vector
from route_milp import propose

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--evals',type=int,default=256)
p.add_argument('--start',type=Path,required=True);p.add_argument('--seed',type=int,default=941);p.add_argument('--smoke',action='store_true');a=p.parse_args()
a.output.mkdir(exist_ok=False);rng=np.random.default_rng(a.seed);start=time.monotonic();records=[];seen=set()
history=[];paths=list((ROOT/'simulation/research-v4').glob('*/search.jsonl'))
for path in paths:
    for line in path.read_text().splitlines():
        r=json.loads(line)
        if r.get('passed') and r.get('grid')==64 and set(SCREEN)<=set(r.get('peaks',{})) and not r['submission'].get('wire_routes_grid'):
            history.append(r)
history=[]  # Fresh local secants; do not let rounded incumbent history dominate.
write_json(a.output/'manifest.json',{'kind':'native screening; proposal MILP changes route-grid cells, original validator and pinned judge authoritative',
    'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ['balance.py','route_milp.py']},
    'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'historical_records':len(history),'budget':a.evals,'seed':a.seed,'target':.94})
components=[(w,d) for w in SCREEN for d in DIES];den=np.array([79.59 if d.startswith('G') else 72.68 for w,d in components])
def response(r):
    peaks=r.get('raw_peaks_c',r['peaks'])
    return np.array([25+(peaks[w][d]-25)*79.59/den[i] for i,(w,d) in enumerate(components)])
log=(a.output/'search.jsonl').open('w');proposal_log=(a.output/'proposals.jsonl').open('w')
def measure(lay,kind,**meta):
    sub={'placements_mm':lay};ident=key(sub)
    if ident in seen:return None
    ok,reason,_=fast.legal(lay)
    if not ok:return None
    r=fast.estimate(lay,64,3,SCREEN);xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw={}
    for w,g in r['grids'].items():
        raw[w]={}
        for d,(x,y) in lay.items():
            width,height=fast.SPEC['dies'][d]['size_mm']
            raw[w][d]=float(g[np.ix_((yy>=y)&(yy<y+height),(xx>=x)&(xx<x+width))].max())
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'kind':kind,'evaluation':len(records),
         'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68),'elapsed_seconds':time.monotonic()-start,**meta}
    rec['continuous_merit_c']=float(max(response(rec)))
    seen.add(ident);records.append(rec);log.write(json.dumps(rec)+'\n');log.flush()
    best=min(records,key=lambda r:r['continuous_merit_c'])
    if rec is best:
        write_json(a.output/'submission.json',sub)
        print('BEST',len(records),rec['screen_score'],rec['gpu'],rec['hbm'],rec['continuous_merit_c'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'best_score':best['screen_score'],
        'best_continuous_merit_c':best['continuous_merit_c'],'elapsed_seconds':time.monotonic()-start})
    return rec

base=json.loads(a.start.read_text())
if a.smoke:
    incumbent=json.loads((ROOT/'simulation/layouts/supah-v2/submission.json').read_text())['placements_mm']
    lay,info=propose(incumbent,np.zeros((1,16)),np.array([101.4]),radius=0,g0_radius=(0,0))
    assert lay==incumbent and info['exact_valid'],(lay,info)
    write_json(a.output/'smoke.json',info);print(info,flush=True);sys.exit(0)
measure(base['placements_mm'],'control')

source=ROOT/'simulation/research-v5/isolation-relocated/search.jsonl'
rs=[json.loads(line) for line in source.read_text().splitlines()]
for r in rs:
 if r['gpu']>101.28 or r['hbm']>94.2:continue
 lay={d:list(xy) for d,xy in r['submission']['placements_mm'].items()};lay['G0']=base['placements_mm']['G0']
 measure(lay,'balanced-neighbor-transfer',source_evaluation=r['evaluation'])
# Rank the original rounded screen score first, then the memory peak.
best=min(records,key=lambda r:(r['screen_score'],r['hbm'],r['continuous_merit_c']))
write_json(a.output/'submission.json',best['submission']);write_json(a.output/'selection.json',best)
log.close();proposal_log.close()
