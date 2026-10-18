"""Finite-difference constrained search using extra output digits, not new physics."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import minimize

ROOT=Path(__file__).resolve().parents[2]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact,write_json,key
from surrogate import DIES,SCREEN,vector
from route_constraints import constraint_model

p=argparse.ArgumentParser();p.add_argument('--start',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--iterations',type=int,default=30);p.add_argument('--epochs',type=int,default=3)
p.add_argument('--epsilon',type=float,default=.0005);p.add_argument('--radius',type=float,default=.3)
a=p.parse_args();a.output.mkdir(exist_ok=False)
base=json.loads(a.start.read_text());t0=time.monotonic();cache={};records=[]
write_json(a.output/'manifest.json',{'kind':'output-precision-only native search; original pinned judge required for promotion',
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'input_sha256':hashlib.sha256(a.start.read_bytes()).hexdigest(),
    'args':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()}})
log=(a.output/'search.jsonl').open('w')
def layout(x):return {d:[round(float(v),6) for v in x[2*i:2*i+2]] for i,d in enumerate(DIES)}
def measure(x,kind='gradient-or-trial'):
    sub={'placements_mm':layout(x)};ident=key(sub)
    if ident in cache:return cache[ident]
    ok,reason,_=fast.legal(sub['placements_mm'])
    if not ok:return None
    r=fast.estimate(sub['placements_mm'],64,3,SCREEN)
    xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw={}
    for w,g in r['grids'].items():
        raw[w]={}
        for d,(x0,y0) in sub['placements_mm'].items():
            width,height=fast.SPEC['dies'][d]['size_mm']
            raw[w][d]=float(g[np.ix_((yy>=y0)&(yy<y0+height),(xx>=x0)&(xx<x0+width))].max())
    merit=max(25+(v-25)*79.59/(79.59 if d.startswith('G') else 72.68)
              for peaks in raw.values() for d,v in peaks.items())
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'continuous_merit_c':merit,
         'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68),
         'evaluation':len(records),'kind':kind,'elapsed_seconds':time.monotonic()-t0}
    records.append(rec);cache[ident]=rec;log.write(json.dumps(rec)+'\n');log.flush()
    best=min(records,key=lambda r:r['continuous_merit_c'])
    if rec is best:
        write_json(a.output/'submission.json',sub)
        print('BEST',len(records),f'{merit:.8f}',r['gpu'],r['hbm'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'best_screen_score':best['screen_score'],
        'best_continuous_merit_c':best['continuous_merit_c'],'elapsed_seconds':time.monotonic()-t0})
    return rec

# Exact same emitted temperatures, rounded back to the native binary's precision.
precise_binary=fast.HOTSPOT
fast.HOTSPOT=Path('/opt/hotspot/hotspot')
control=compact(fast.estimate(base['placements_mm'],64,3,SCREEN))
fast.HOTSPOT=precise_binary
first=measure(vector(base['placements_mm']),'precision-calibration-control')
assert first['peaks']==control['peaks'], (first['peaks'],control['peaks'])
write_json(a.output/'calibration.json',{'unchanged_rounded_per_die_peaks':True,'original_native':control,
    'precise_native_rounded_peaks':first['peaks'],'raw_peaks_c':first['raw_peaks_c']})
anchor=first
for epoch in range(a.epochs):
    x0=vector(anchor['submission']['placements_mm'])
    cons,bounds=constraint_model(x0)
    bounds=[(max(l,x0[i]-a.radius),min(u,x0[i]+a.radius)) for i,(l,u) in enumerate(bounds)]
    def objective(x):
        rec=measure(x)
        return rec['continuous_merit_c'] if rec else 110+sum(np.maximum(0,-cons(x)))
    sol=minimize(objective,np.clip(x0,*np.array(bounds).T),method='SLSQP',bounds=bounds,
        constraints={'type':'ineq','fun':cons},options={'maxiter':a.iterations,'eps':a.epsilon,'ftol':1e-8})
    anchor=min(records,key=lambda r:r['continuous_merit_c'])
    write_json(a.output/f'epoch-{epoch}.json',{'success':bool(sol.success),'message':str(sol.message),
        'iterations':int(sol.nit),'evaluations':int(sol.nfev),'objective':float(sol.fun),
        'best_continuous_merit_c':anchor['continuous_merit_c'],'submission':anchor['submission']})
    print('EPOCH',epoch,sol.message,anchor['continuous_merit_c'],flush=True)
log.close()
