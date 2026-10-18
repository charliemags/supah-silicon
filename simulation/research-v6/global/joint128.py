"""Bounded native128 refinement with an actual native64 acceptance gate.

Both grids use the existing exact validator and unchanged HotSpot physics.
Only measured128 improvements whose64 raw minimax is within0.005C of the
preserved start are retained. Final pinned verification is still required.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact,key,write_json
from surrogate import DIES,SCREEN,vector
from proposal import propose
p=argparse.ArgumentParser();p.add_argument('--start',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--evals',type=int,default=60);p.add_argument('--seed',type=int,default=9464128);a=p.parse_args()
a.output.mkdir(exist_ok=False);rng=np.random.default_rng(a.seed);start=time.monotonic();records=[];tested=set();gates=[];iteration=0
base=json.loads(a.start.read_text());basev=vector(base['placements_mm']);components=[(w,d) for w in SCREEN for d in DIES]
refs={g:json.loads((fast.HILL/f'reference_{g}.json').read_text()) for g in [64,128]}
def response(r):
    raw=r['raw_peaks_c'];ref=refs[r['grid']]
    return np.array([25+(raw[w][d]-25)*(ref['worst_gpu_c']-25)/(ref['worst_gpu_c']-25 if d.startswith('G') else ref['worst_hbm_c']-25) for w,d in components])
log=(a.output/'search.jsonl').open('w');plog=(a.output/'proposals.jsonl').open('w')
write_json(a.output/'manifest.json',{'kind':__doc__,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('proposal.py')]},
 'start':str(a.start),'start_sha256':hashlib.sha256(a.start.read_bytes()).hexdigest(),'hotspot_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'budget128':a.evals,
 'seed':a.seed,'cpus':3,'gate64_raw_tolerance_c':.005,'workloads':SCREEN,'references':refs})
def measure(lay,grid,kind,**meta):
    assert fast.legal(lay)[0]
    r=fast.estimate(lay,grid,3,SCREEN);xx=(np.arange(grid)+.5)*52/grid;yy=42-(np.arange(grid)+.5)*42/grid;raw={}
    for w,g in r['grids'].items():
        raw[w]={}
        for d,(x,y) in lay.items():
            width,height=fast.SPEC['dies'][d]['size_mm'];raw[w][d]=float(g[np.ix_((yy>=y)&(yy<y+height),(xx>=x)&(xx<x+width))].max())
    ref=refs[grid];rec={'submission':{'placements_mm':lay},**compact(r),'raw_peaks_c':raw,'kind':kind,'evaluation':len(gates)+len(records),'elapsed_seconds':time.monotonic()-start,
      'screen_score':max((r['gpu']-25)/(ref['worst_gpu_c']-25),(r['hbm']-25)/(ref['worst_hbm_c']-25)),**meta}
    rec['continuous_merit_c']=float(max(response(rec)));log.write(json.dumps(rec)+'\n');log.flush()
    if grid==64:gates.append(rec)
    else:records.append(rec)
    return rec
control64=measure(base['placements_mm'],64,'preserved-control');threshold=control64['continuous_merit_c']+.005
best=measure(base['placements_mm'],128,'preserved-control',gate64=control64);tested.add(key(base));best64=control64
write_json(a.output/'submission.json',base);write_json(a.output/'best.json',best)
# Fresh 64 records provide independently measured nearby perturbations.
history=[]
for path in (ROOT/'simulation/research-v6/global').glob('*/search.jsonl'):
    if path.resolve()==(a.output/'search.jsonl').resolve():continue
    for l in path.read_text().splitlines():
        r=json.loads(l)
        if r['grid']==64 and r['continuous_merit_c']<=threshold and r['submission']!=base:
            # The G0-only experiment merit was not minimax; compute it afresh.
            if max(response(r))<=threshold:history.append(r)
history=list({key(r['submission']):r for r in history}.values())
# Rank diversity among promising measured64 candidates rather than tiny duplicates.
selected=[]
while history and len(selected)<20:
    if not selected:idx=int(np.argmin([np.linalg.norm(vector(r['submission']['placements_mm'])-basev) for r in history]))
    else:idx=int(np.argmax([min(np.linalg.norm(vector(r['submission']['placements_mm'])-vector(s['submission']['placements_mm'])) for s in selected+[control64]) for r in history]))
    selected.append(history.pop(idx))
for iteration in range(a.evals*60):
    if len(records)>=a.evals:break
    anchor=best if iteration%3 else records[int(rng.integers(len(records)))];origin=vector(anchor['submission']['placements_mm']);mode=iteration%4
    info={'iteration':iteration}
    if selected and mode==0:
        historic=selected.pop(0);lay=historic['submission']['placements_mm'];info.update(kind='measured64-diverse-history',source_evaluation=historic['evaluation'],exact_valid=True)
    else:
        radius=float(rng.choice([.02,.05,.1,.25,.5]));target=origin.copy();g0=origin[:2].copy()
        if mode==1:
            g0+=rng.normal(0,rng.choice([.003,.01,.025]),2);target[:2]=g0
            target[2:]+=rng.normal(0,radius/3,14)
        else:
            ids=rng.choice(8,size=int(rng.integers(1,4)),replace=False)
            for i in ids:target[2*i:2*i+2]+=rng.normal(0,radius,2)
            if 0 in ids:g0=target[:2].copy()
        params={'radius':1.,'g0_radius':(1.,1.),'g0_target':g0,'target':target,'repair_weight':1.,'temperature_weight':0.,'time_limit':.6}
        gradients=np.zeros((1,16));temperatures=np.array([101.5])
        if len(records)>=20 and mode==3:
            X=np.array([vector(r['submission']['placements_mm'])-origin for r in records]);Y=np.array([response(r) for r in records]);weights=np.exp(-np.sum((X/.2)**2,axis=1)/2)
            F=np.column_stack([np.ones(len(X)),X]);model=np.linalg.solve(F.T@(weights[:,None]*F)+np.diag([1e-8]+[.005]*16),F.T@(weights[:,None]*Y))
            gradients=model[1:].T;temperatures=response(anchor);params.update(radius=.1,g0_radius=(.015,.015),g0_target=None,temperature_weight=1.,repair_weight=.001)
        lay,proposal=propose(anchor['submission']['placements_mm'],gradients,temperatures,**params);info.update(proposal,kind='native128-refine',radius=radius)
    info['submission']={'placements_mm':lay} if lay else None;plog.write(json.dumps(info)+'\n');plog.flush()
    if lay is None or not info['exact_valid'] or key({'placements_mm':lay}) in tested:continue
    tested.add(key({'placements_mm':lay}));r64=measure(lay,64,'actual64-gate',iteration=iteration)
    if r64['continuous_merit_c']>threshold or r64['screen_score']>control64['screen_score']+1e-10:continue
    r128=measure(lay,128,'accepted64-native128',iteration=iteration,gate64=r64)
    if r128['continuous_merit_c']<best['continuous_merit_c']:
        best=r128;best64=r64;write_json(a.output/'submission.json',r128['submission']);write_json(a.output/'best.json',r128)
        freeze=a.output/'finalists'/f'eval-{len(records):03d}';freeze.mkdir(parents=True,exist_ok=True);write_json(freeze/'submission.json',r128['submission']);write_json(freeze/'record.json',r128)
        print('BEST128',len(records),best['gpu'],best['hbm'],best['continuous_merit_c'],'gate64',r64['gpu'],r64['hbm'],r64['continuous_merit_c'],flush=True)
    write_json(a.output/'summary.json',{'native128_screens':len(records),'native64_gates':len(gates),'best128_raw_c':best['continuous_merit_c'],'best128_score':best['screen_score'],
       'best64_gate_raw_c':best64['continuous_merit_c'],'threshold64_c':threshold,'elapsed_seconds':time.monotonic()-start})
    print('PROGRESS128',len(records),'gates',len(gates),'best',best['continuous_merit_c'],flush=True)
write_json(a.output/'completed.json',{'native128_screens':len(records),'native64_gates':len(gates),'iteration':iteration,'seconds':time.monotonic()-start});log.close();plog.close()
