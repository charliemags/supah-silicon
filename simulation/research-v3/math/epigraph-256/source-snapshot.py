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
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--evals',type=int,default=240);p.add_argument('--start',default='/work/simulation/layouts/supah-v2/submission.json');a=p.parse_args()
out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
rng=np.random.default_rng(9485); start=time.monotonic(); records=[];seen=set()
def vect(lay):return np.array([lay[d]for d in DIES]).reshape(-1)
def layout(x):return {d:[round(float(v),3)for v in x[2*i:2*i+2]]for i,d in enumerate(DIES)}
def evaluate(x,kind,**meta):
 lay=layout(x);key=json.dumps(lay,sort_keys=True)
 if key in seen or len(records)>=a.evals:return None
 ok,reason,route=fast.legal(lay)
 if not ok:return None
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
manifest={'kind':'native-screening-only','components':COMP,'denominators':DEN.tolist(),'seed':9485,'budget':a.evals,'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(Path(a.start).read_bytes()).hexdigest(),'files_sha256':{n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest()for n in ['challenge_spec.json','workloads.json']}}
(out/'experiment.json').write_text(json.dumps(manifest,indent=2)+'\n');evaluate(x0,'seed')
# Feasible one-sided/central perturbations reveal gradient dependence on step.
for h in [.025,.1,.25]:
 for j in range(16):
  for sign in [-1,1]:
   x=x0.copy();x[j]+=sign*h;evaluate(x,'coordinate_secant',coordinate=j,step=sign*h)
print('COORDINATE DONE',len(records),flush=True)
# Coordinated broad but legal probes, including vertical ring relaxation while G0 holds.
groups=[[1,2,3,5,6,7],[3,7],[1,4],[2,5,6],[0,4],[0,7],list(range(8))]
for group in groups:
 for h in [-.3,-.1,.1,.3]:
  for axis in [0,1]:
   x=x0.copy()
   for i in group:x[2*i+axis]+=h
   evaluate(x,'group_secant',group=group,axis=axis,step=h)
# Feasibility-preserving projections excite coupled directions inaccessible to one-die moves.
attempts=0
while len(records)<min(125,a.evals) and attempts<400:
 attempts+=1;cons,bounds=constraint_model(x0);target=x0+rng.normal(0,.18 if attempts<100 else .4,16)
 if attempts%2:target[:2]=x0[:2]
 r=minimize(lambda x:np.sum((x-target)**2),x0,jac=lambda x:2*(x-target),bounds=bounds,constraints={'type':'ineq','fun':cons},method='SLSQP',options={'maxiter':50,'ftol':1e-8})
 x=r.x
 for frac in [1,.5,.25]:
  rec=evaluate(x0+frac*(x-x0),'projected_secant',attempt=attempts)
  if rec:break
print('MODEL START',len(records),flush=True)
iteration=0;misses=0
while len(records)<a.evals and iteration<60:
 iteration+=1
 best=min(records,key=lambda r:r['screen_score']);xb=vect(best['submission']['placements_mm']);yb=np.array([(best['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)])
 X=np.array([vect(r['submission']['placements_mm'])-xb for r in records]);Y=np.array([[(r['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)]for r in records])-yb
 scale=[.12,.25,.5][(iteration-1)%3];weights=np.exp(-np.sum(X*X,axis=1)/(2*scale**2));G=np.linalg.solve(X.T@(weights[:,None]*X)+1e-5*np.eye(16),X.T@(weights[:,None]*Y)).T
 cons,bounds=constraint_model(xb);radius=[.08,.2,.4][(iteration-1)%3]
 bounds=[(max(l,xb[i]-radius),min(u,xb[i]+radius))for i,(l,u)in enumerate(bounds)]+[(.8,1.2)]
 def constraints(z):return np.r_[cons(z[:-1]),z[-1]-yb-G@(z[:-1]-xb)]
 sol=minimize(lambda z:z[-1]+.00001*np.sum((z[:-1]-xb)**2),np.r_[xb,max(yb)],bounds=bounds,constraints={'type':'ineq','fun':constraints},method='SLSQP',options={'maxiter':100,'ftol':1e-10})
 n0=len(records)
 for fraction in [1,.5,.25,.125]:
  evaluate(xb+fraction*(sol.x[:-1]-xb),'epigraph_trial',iteration=iteration,radius=radius,fit_scale=scale,predicted_score=float(sol.x[-1]),solver_success=bool(sol.success),fraction=fraction)
 if len(records)==n0 or iteration%3==0:
  for k in range(5):
   target=xb+rng.normal(0,radius,16);q=minimize(lambda x:np.sum((x-target)**2),xb,jac=lambda x:2*(x-target),bounds=bounds[:-1],constraints={'type':'ineq','fun':cons},method='SLSQP',options={'maxiter':60,'ftol':1e-8})
   for fraction in [1,.5,.25]:
    if evaluate(xb+fraction*(q.x-xb),'refresh_secant',iteration=iteration):break
 if len(records)==n0:misses+=1
 else:misses=0
 if misses>=8:break
best=min(records,key=lambda r:r['screen_score']);(out/'summary.json').write_text(json.dumps({'kind':'native screening; not official','evaluations':len(records),'best_score':best['screen_score'],'best_evaluation':best['evaluation'],'elapsed_seconds':round(time.monotonic()-start,2)},indent=2)+'\n')
print('DONE',len(records),best['screen_score'],flush=True)
