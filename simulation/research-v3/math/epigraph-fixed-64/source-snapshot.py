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
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--history',type=Path);p.add_argument('--additional-evals',type=int,default=64);p.add_argument('--evals',type=int,default=240);p.add_argument('--start',default='/work/simulation/layouts/supah-v2/submission.json');a=p.parse_args()
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
   delta=xy0[j]-xy0[i];choices=[(delta[k]-sizes[i,k],i,j,k)for k in range(2)]+[(-delta[k]-sizes[j,k],j,i,k)for k in range(2)]
   _,first,second,k=max(choices);pairs.append((first,second,k))
 links=list(routing['routes'].values());ia=np.array([DIES.index(r['from'])for r in links]);ib=np.array([DIES.index(r['to'])for r in links]);oa=np.array([r['from_port']for r in links])-xy0[ia];ob=np.array([r['to_port']for r in links])-xy0[ib];limits=np.array([r['limit_mm']for r in links]);weights=np.array([r['bandwidth_gb_s']for r in links]);pitch=.5;clearance=.2;margin=.002
 qa=np.array([r['path_grid'][0]for r in links])*pitch+pitch/2
 qb=np.array([r['path_grid'][-1]for r in links])*pitch+pitch/2
 tracks=np.array([(len(r['path_grid'])-1)*pitch for r in links])
 lower=np.ones(16)*1.001;upper=np.array([fast.SPEC['interposer_mm'][k]-sizes[i,k]-1.001 for i in range(8)for k in range(2)])
 # The two exact endpoint-access cells stay fixed. All port offsets are affine
 # while facing sides and their per-edge allocation remain unchanged.
 for link_idx,r in enumerate(links):
  for die_idx,offset,normal,cell in [(ia[link_idx],oa[link_idx],r['from_normal'],r['path_grid'][0]),(ib[link_idx],ob[link_idx],r['to_normal'],r['path_grid'][-1])]:
   for k in range(2):
    j=2*die_idx+k;lower[j]=max(lower[j],cell[k]*pitch-offset[k]-(clearance+pitch)*normal[k]+margin)
    upper[j]=min(upper[j],(cell[k]+1)*pitch-offset[k]-(clearance+pitch)*normal[k]-margin)
 # Every frozen path point stays outside each .2mm-expanded die. Select the
 # currently safest separating halfspace, giving conservative linear bounds.
 points={tuple(cell)for r in links for cell in r['path_grid']}
 for cell in points:
  point=np.array(cell)*pitch+pitch/2
  for i in range(8):
   choices=[]
   for k in range(2):
    choices += [(xy0[i,k]-point[k]-clearance,k,'lower'),(point[k]-xy0[i,k]-sizes[i,k]-clearance,k,'upper')]
   slack,k,which=max(choices);j=2*i+k
   if which=='lower':lower[j]=max(lower[j],point[k]+clearance+margin)
   else:upper[j]=min(upper[j],point[k]-sizes[i,k]-clearance-margin)
 # Sides selected by dominant center displacement must remain unchanged.
 normals=np.array([r['from_normal']for r in links]);axes=np.argmax(abs(normals),axis=1);signs=np.sum(normals,axis=1)
 def cons(x):
  xy=x.reshape(8,2);lengths=tracks+np.abs(xy[ia]+oa-qa).sum(axis=1)+np.abs(xy[ib]+ob-qb).sum(axis=1)
  centers=xy+sizes/2;delta=centers[ib]-centers[ia];facing=[]
  for z,axis in enumerate(axes):
   dominant=signs[z]*delta[z,axis];other=delta[z,1-axis];facing.extend([dominant-other-margin,dominant+other-margin])
  return np.r_[[xy[j,k]-xy[i,k]-sizes[i,k]-1.002 for i,j,k in pairs],limits-lengths,(13499-lengths@weights)/600.,facing]
 if np.any(lower>upper):raise ValueError('Conservative fixed-route bounds became empty')
 return cons,list(zip(lower,upper))

seed=json.loads(Path(a.start).read_text())['placements_mm'];x0=vect(seed)
manifest={'kind':'native-screening-only epigraph with fixed exact routes and access cells','components':COMP,'denominators':DEN.tolist(),'seed':9485,'total_budget_including_inherited':a.evals,'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(Path(a.start).read_bytes()).hexdigest(),'files_sha256':{n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest()for n in ['challenge_spec.json','workloads.json']}}
if a.history:
 prior=json.loads((a.history/'experiment.json').read_text())
 for k in ['solver_sha256','input_sha256','files_sha256']:
  if prior[k]!=manifest[k]:raise ValueError('Incompatible history '+k)
 history=a.history/'search.jsonl';manifest['history_sha256']=hashlib.sha256(history.read_bytes()).hexdigest()
 for line in history.read_text().splitlines():
  r=json.loads(line)
  if r.get('grid')!=64 or not r.get('passed'):raise ValueError('Invalid history')
  r['inherited_from']=str(history);r['original_elapsed_seconds']=r.pop('elapsed_seconds',r.get('original_elapsed_seconds'));records.append(r);seen.add(json.dumps(r['submission']['placements_mm'],sort_keys=True))
 inherited=len(records)
 with(out/'search.jsonl').open('w')as f:
  for r in records:f.write(json.dumps(r)+'\n')
a.evals=inherited+a.additional_evals
manifest['total_budget_including_inherited']=a.evals
manifest['additional_budget']=a.additional_evals
(out/'experiment.json').write_text(json.dumps(manifest,indent=2)+'\n')
evaluate(x0,'seed')
from population import proposal
iteration=0
while len(records)<a.evals:
 iteration+=1
 best=min(records,key=lambda r:r['screen_score']);xb=vect(best['submission']['placements_mm']);yb=np.array([(best['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)])
 X=np.array([vect(r['submission']['placements_mm'])-xb for r in records]);Y=np.array([[(r['peaks'][w][d]-25)/DEN[i]for i,(w,d)in enumerate(COMP)]for r in records])-yb
 scale=[.12,.25,.5][(iteration-1)%3];weights=np.exp(-np.sum(X*X,axis=1)/(2*scale**2));G=np.linalg.solve(X.T@(weights[:,None]*X)+1e-5*np.eye(16),X.T@(weights[:,None]*Y)).T
 cons,bounds=constraint_model(xb);radius=[.08,.2,.4][(iteration-1)%3]
 bounds=[(max(l,xb[i]-radius),min(u,xb[i]+radius))for i,(l,u)in enumerate(bounds)]+[(.8,1.2)]
 if any(l>u for l,u in bounds):raise ValueError('Empty trust region')
 def constraints(z):return np.r_[cons(z[:-1]),z[-1]-yb-G@(z[:-1]-xb)]
 initial_x=np.array([min(max(xb[i],l),u)for i,(l,u)in enumerate(bounds[:-1])])
 sol=minimize(lambda z:z[-1]+.00001*np.sum((z[:-1]-xb)**2),np.r_[initial_x,max(yb)],bounds=bounds,constraints={'type':'ineq','fun':constraints},method='SLSQP',options={'maxiter':100,'ftol':1e-10})
 with(out/'epigraph-proposals.jsonl').open('a')as f:
  proposed=layout(sol.x[:-1]);ok,why,_=fast.legal(proposed)
  f.write(json.dumps({'iteration':iteration,'success':bool(sol.success),'message':str(sol.message),'predicted_score':float(sol.x[-1]),'minimum_model_constraint':float(min(constraints(sol.x))),'exact_valid':ok,'exact_reason':why,'submission':{'placements_mm':proposed}})+'\n')
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
