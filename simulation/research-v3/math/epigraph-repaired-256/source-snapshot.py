"""Screen unchanged challenge via feasible multi-scale secants and epigraph trust regions."""
import sys, os, json, time, hashlib, argparse
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0,'/work/simulation/tools')
import fast
from optimize import compact

DIES=list(fast.SPEC['dies'])
WLS=['skewed_compute','tensor_training','memory_stream']
COMP=[(w,d)for w in WLS for d in DIES]
DEN=np.array([79.59 if d.startswith('G') else 72.68 for w,d in COMP])
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--history',type=Path);p.add_argument('--evals',type=int,default=240);p.add_argument('--start',default='/work/simulation/layouts/supah-v2/submission.json');a=p.parse_args()
out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
rng=np.random.default_rng(9485); start=time.monotonic(); records=[];seen=set();rejected={};inherited=0
def vect(lay):return np.array([lay[d]for d in DIES]).reshape(-1)
def layout(x):return {d:[round(float(v),3)for v in x[2*i:2*i+2]]for i,d in enumerate(DIES)}
def evaluate(x,kind,**meta):
 lay=layout(x);key=json.dumps(lay,sort_keys=True)
 if key in seen or len(records)>=a.evals:return None
 ok,reason,route=fast.legal(lay)
 if not ok:
  rejected[reason]=rejected.get(reason,0)+1
  return None
 seen.add(key);res=compact(fast.estimate(lay,64,workers=3,workloads=WLS));
 y=np.array([(res['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)])
 r={'evaluation':len(records),'kind':kind,'submission':{'placements_mm':lay},'screen_score':float(max(y)),'elapsed_seconds':round(time.monotonic()-start,3),**meta,**res}
 records.append(r)
 with(out/'search.jsonl').open('a')as f:f.write(json.dumps(r)+'\n')
 if r['screen_score']<=min(z['screen_score']for z in records):
  (out/'submission.json').write_text(json.dumps(r['submission'],indent=2)+'\n');print('BEST',r['evaluation'],r['screen_score'],res['gpu'],res['hbm'],flush=True)
 return r

def constraint_model(x0):
 lay=layout(x0);_,_,routing=fast.legal(lay);sizes=np.array([fast.SPEC['dies'][d]['size_mm']for d in DIES]);xy0=x0.reshape(8,2);pairs=[]
 for i in range(8):
  for j in range(i+1,8):
   delta=xy0[j]-xy0[i]; choices=[(delta[k]-sizes[i,k],i,j,k)for k in range(2)]+[(-delta[k]-sizes[j,k],j,i,k)for k in range(2)]
   _,first,second,k=max(choices);pairs.append((first,second,k))
 links=list(routing['routes'].values());ia=np.array([DIES.index(r['from'])for r in links]);ib=np.array([DIES.index(r['to'])for r in links]);oa=np.array([r['from_port']for r in links])-xy0[ia];ob=np.array([r['to_port']for r in links])-xy0[ib];limits=np.array([r['limit_mm']for r in links]);weights=np.array([r['bandwidth_gb_s']for r in links])
 def manhattan(x):
  xy=x.reshape(8,2);return np.abs(xy[ia]+oa-xy[ib]-ob).sum(axis=1)
 overhead=np.array([r['route_length_mm']for r in links])-manhattan(x0)
 def cons(x):
  xy=x.reshape(8,2);lengths=manhattan(x)+overhead
  return np.r_[[xy[j,k]-xy[i,k]-sizes[i,k]-1.002 for i,j,k in pairs],limits-lengths,(13499-lengths@weights)/600]
 bounds=[(1.001,fast.SPEC['interposer_mm'][k]-sizes[i,k]-1.001)for i in range(8)for k in range(2)]
 return cons,bounds

seed=json.loads(Path(a.start).read_text())['placements_mm'];x0=vect(seed)
manifest={'kind':'native-screening-only repaired epigraph continuation','components':COMP,'denominators':DEN.tolist(),'seed':9485,'total_budget_including_inherited':a.evals,'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(Path(a.start).read_bytes()).hexdigest(),'files_sha256':{n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest()for n in ['challenge_spec.json','workloads.json']}}
if a.history:
 prior=json.loads((a.history/'experiment.json').read_text())
 for k in ['solver_sha256','input_sha256','files_sha256']:
  if prior[k]!=manifest[k]:raise ValueError('Incompatible history '+k)
 history=a.history/'search.jsonl';manifest['history_sha256']=hashlib.sha256(history.read_bytes()).hexdigest()
 for line in history.read_text().splitlines():
  r=json.loads(line)
  if r.get('grid')!=64 or not r.get('passed'):raise ValueError('Invalid history')
  r['inherited_from']=str(history);r['original_elapsed_seconds']=r.pop('elapsed_seconds');records.append(r);seen.add(json.dumps(r['submission']['placements_mm'],sort_keys=True))
 inherited=len(records)
 with(out/'search.jsonl').open('w')as f:
  for r in records:f.write(json.dumps(r)+'\n')
(out/'experiment.json').write_text(json.dumps(manifest,indent=2)+'\n')
evaluate(x0,'seed')
# Disconnected geometry trade: H3+G3 northwest, G2+H2 west to fund its routing.
for delta in [.025,.05,.1,.2,.4,.8,1.2]:
 for ratio in [.5,1.,1.5]:
  x=x0.copy()
  for name in ['H3','G3']:
   i=DIES.index(name);x[2*i]-=delta;x[2*i+1]+=delta
  for name in ['G2','H2']:
   i=DIES.index(name);x[2*i]-=ratio*delta
  evaluate(x,'directed_h3_isolation',delta=delta,budget_compensation_ratio=ratio)
# Secondary mode frees H3 reach by shifting the whole upper assembly south,
# tests whether that enables better G0-facing routing once components relax.
from population import proposal
iteration=0
while len(records)<a.evals:
 iteration+=1
 best=min(records,key=lambda r:r['screen_score']);xb=vect(best['submission']['placements_mm']);yb=np.array([(best['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)])
 X=np.array([vect(r['submission']['placements_mm'])-xb for r in records]);Y=np.array([[(r['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)]for r in records])-yb
 scale=[.12,.25,.5][(iteration-1)%3];weights=np.exp(-np.sum(X*X,axis=1)/(2*scale**2));G=np.linalg.solve(X.T@(weights[:,None]*X)+1e-5*np.eye(16),X.T@(weights[:,None]*Y)).T
 cons,bounds=constraint_model(xb);radius=[.08,.2,.4][(iteration-1)%3]
 bounds=[(max(l,xb[i]-radius),min(u,xb[i]+radius))for i,(l,u)in enumerate(bounds)]+[(.8,1.2)]
 def constraints(z):return np.r_[cons(z[:-1]),z[-1]-yb-G@(z[:-1]-xb)]
 sol=minimize(lambda z:z[-1]+.00001*np.sum((z[:-1]-xb)**2),np.r_[xb,max(yb)],bounds=bounds,constraints={'type':'ineq','fun':constraints},method='SLSQP',options={'maxiter':100,'ftol':1e-10})
 n0=len(records)
 for fraction in [1,.5,.25,.125,.0625,.03125]:
  if evaluate(xb+fraction*(sol.x[:-1]-xb),'epigraph_trial',iteration=iteration,radius=radius,fit_scale=scale,predicted_score=float(sol.x[-1]),solver_success=bool(sol.success),fraction=fraction):break
 # Exact-validator fallback fills the budget with feasible directional evidence.
 # Half the anchors come from diverse near-elites rather than only the best.
 if len(records)==n0 or iteration%3==0:
  elite=[r for r in records if r['screen_score']<=best['screen_score']+.003]
  anchor=best if rng.random()<.5 else elite[int(rng.integers(len(elite)))];xa=vect(anchor['submission']['placements_mm'])
  archive=[vect(r['submission']['placements_mm'])for r in records[-400:]]
  success=False
  for attempt in range(1000):
   trial=proposal(anchor['submission']['placements_mm'],best['submission']['placements_mm'],archive,rng,radius)
   for fraction in [1,.5,.2,.05]:
    rec=evaluate(xa+fraction*(trial-xa),'feasible_fallback_secant',iteration=iteration,fraction=fraction,anchor_evaluation=anchor['evaluation'])
    if rec:success=True;break
   if success:break
  if not success:raise RuntimeError('No feasible unseen point after1000 fallback attempts')
 if iteration%10==0:print('PROGRESS',len(records),'/',a.evals,flush=True)
best=min(records,key=lambda r:r['screen_score']);(out/'submission.json').write_text(json.dumps(best['submission'],indent=2)+'\n')
(out/'summary.json').write_text(json.dumps({'kind':'native screening; not official','evaluations_including_inherited':len(records),'new_evaluations':len(records)-inherited,'inherited_evaluations':inherited,'best_score':best['screen_score'],'best_evaluation':best['evaluation'],'elapsed_seconds':round(time.monotonic()-start,2),'rejected_proposals':rejected},indent=2)+'\n')
print('DONE',len(records),best['screen_score'],flush=True)
