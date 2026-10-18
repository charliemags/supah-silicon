"""Quadratic response models with actual-reduction adaptive trust regions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import minimize
from search import measure, ROOT
from route_constraints import constraint_model
import fast
from optimize import key, write_json
from population import proposal
from surrogate import DIES, SCREEN, vector, placement, cheap_legal

p=argparse.ArgumentParser()
p.add_argument('--output',type=Path,required=True)
p.add_argument('--evals',type=int,default=256)
p.add_argument('--history',type=Path,nargs='+',required=True)
p.add_argument('--start',type=Path,default=ROOT/'simulation/research-v3/lead/finalists/control-hbm/submission.json')
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
historical=[]
for path in a.history:
    for line in path.read_text().splitlines():
        r=json.loads(line)
        if r.get('passed') and r.get('grid')==64 and set(SCREEN)<=set(r.get('peaks',{})):
            historical.append(r)
historical=list({key(r['submission']):r for r in historical}.values())
write_json(a.output/'manifest.json',{'kind':'quadratic native screen with adaptive actual/predicted reduction',
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'constraints_sha256':hashlib.sha256((Path(__file__).parent/'route_constraints.py').read_bytes()).hexdigest(),
    'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'history_snapshot_sha256':{str(h):hashlib.sha256(h.read_bytes()).hexdigest() for h in a.history},
    'historical_records':len(historical),'new_budget':a.evals,'seed':404})
rng=np.random.default_rng(404);t0=time.monotonic();records=[];seen={key(r['submission']) for r in historical}
components=[(w,d) for w in SCREEN for d in DIES]
den=np.array([79.59 if d.startswith('G') else 72.68 for w,d in components])
log=(a.output/'search.jsonl').open('w')
def save(rec,**meta):
    rec.update(evaluation=len(records),elapsed_seconds=time.monotonic()-t0,**meta)
    records.append(rec);log.write(json.dumps(rec)+'\n');log.flush();seen.add(key(rec['submission']))
    best=min(records,key=lambda r:(r['screen_score'],r['smooth_hotspot_c'],r['hbm']))
    if rec is best:
        write_json(a.output/'submission.json',rec['submission'])
        print('BEST',len(records),rec['screen_score'],rec['gpu'],rec['hbm'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'best_score':best['screen_score'],
        'elapsed_seconds':time.monotonic()-t0,'radius_mm':radius})
    return rec
radius=.15
anchor=save(measure(json.loads(a.start.read_text())),kind='control')

def features(x):
    x=np.atleast_2d(x)
    return np.column_stack([np.ones(len(x)),x,x*x,x[:,0::2]*x[:,1::2]])

for iteration in range(1,a.evals):
    xb=vector(anchor['submission']['placements_mm'])
    source=historical+records
    X=np.array([vector(r['submission']['placements_mm'])-xb for r in source])
    # Emphasize the G0 basin; nearby remote moves teach small coupling effects.
    distances=np.sum((X/np.array([.06,.18]+[.65]*14))**2,axis=1)
    indices=np.argsort(distances)[:600]
    X=X[indices]/.2
    Y=np.array([[(source[i]['peaks'][w][d]-25)/den[j] for j,(w,d) in enumerate(components)] for i in indices])
    weights=np.maximum(1e-8,np.exp(-distances[indices]/2))
    F=features(X);regularizer=np.diag([1e-10]+[1e-6]*16+[1e-5]*24)
    model=np.linalg.solve(F.T@(weights[:,None]*F)+regularizer,F.T@(weights[:,None]*Y))
    yb=np.array([(anchor['peaks'][w][d]-25)/den[j] for j,(w,d) in enumerate(components)])
    offset=yb-features(np.zeros(16))[0]@model
    def predicted(x):return features((x-xb)/.2)[0]@model+offset
    cons,bounds=constraint_model(xb)
    bounds=[(max(l,xb[i]-radius),min(u,xb[i]+radius)) for i,(l,u) in enumerate(bounds)]
    xinit=np.clip(xb,*np.array(bounds).T)
    def constraints(z):return np.r_[cons(z[:-1]),z[-1]-predicted(z[:-1])]
    sol=minimize(lambda z:z[-1],np.r_[xinit,max(yb)],method='SLSQP',bounds=bounds+[(.8,1.3)],
                 constraints={'type':'ineq','fun':constraints},options={'maxiter':150,'ftol':1e-10})
    candidate=None
    if iteration%4:
        for fraction in [1,.5,.25]:
            sub={'placements_mm':placement(xb+(sol.x[:-1]-xb)*fraction)}
            if key(sub) not in seen and fast.legal(sub['placements_mm'])[0]:
                candidate=sub;break
    kind='quadratic-trust-trial'
    if candidate is None:
        kind='feasible-refresh'
        elite=sorted(source,key=lambda r:r['screen_score'])[:150]
        for attempt in range(10000):
            ar=anchor if rng.random()<.7 else elite[int(rng.integers(len(elite)))]
            x=proposal(ar['submission']['placements_mm'],anchor['submission']['placements_mm'],
                       [vector(r['submission']['placements_mm']) for r in elite],rng,max(.05,radius*2))
            sub={'placements_mm':placement(x)}
            if key(sub) not in seen and cheap_legal(x) and fast.legal(sub['placements_mm'])[0]:candidate=sub;break
        if candidate is None:raise RuntimeError('No feasible refresh')
    pred=float(max(predicted(vector(candidate['placements_mm']))))
    rec=measure(candidate)
    actual=anchor['screen_score']-rec['screen_score'];expected=anchor['screen_score']-pred
    ratio=actual/expected if expected>1e-8 else None
    save(rec,kind=kind,predicted_score=pred,actual_reduction=actual,predicted_reduction=expected,
         reduction_ratio=ratio,radius_mm=radius,optimizer_success=bool(sol.success))
    if (rec['screen_score'],rec['smooth_hotspot_c'],rec['hbm']) < (anchor['screen_score'],anchor['smooth_hotspot_c'],anchor['hbm']):anchor=rec
    if kind=='quadratic-trust-trial':
        if ratio is None or ratio<.1:radius=max(.015,radius*.65)
        elif ratio>.75:radius=min(.3,radius*1.5)
    if iteration%32==0:
        radius=max(.08,radius)
        print('PROGRESS',iteration,'best',anchor['screen_score'],'radius',radius,flush=True)
log.close()
