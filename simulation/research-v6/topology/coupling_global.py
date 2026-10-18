"""Different C8 packing topologies and nonlinear mixed-integer thermal search.

Proposals do not change the authoritative router, hardware, sources or score.
Every observation below is an exact-valid local native HotSpot simulation.
"""
import argparse, hashlib, itertools, json, os, sys, time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact, key, write_json
from surrogate import DIES, SCREEN, vector
from route_milp import propose

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--evals',type=int,default=1700);p.add_argument('--seed',type=int,default=9411)
p.add_argument('--only-refine',type=Path);p.add_argument('--seed-list',type=Path);p.add_argument('--objective',choices=['full','g0'],default='full');p.add_argument('--freeze-g0',action='store_true');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);rng=np.random.default_rng(a.seed)
start=time.monotonic();records=[];seen=set();failures={};proposal_count=0
log=(a.output/'search.jsonl').open('w');plog=(a.output/'proposals.jsonl').open('w')
components=[(w,d) for w in SCREEN for d in DIES]
den=np.array([79.59 if d.startswith('G') else 72.68 for w,d in components])
def response(r):
    pp=r['raw_peaks_c']
    return np.array([25+(pp[w][d]-25)*79.59/den[i] for i,(w,d) in enumerate(components)])
def signature(lay):
    ok,_,routing=fast.legal(lay)
    return ''.join(str(v) for route in routing['routes'].values() for v in route['from_normal']) if ok else None
def record_proposal(lay,kind,**meta):
    global proposal_count
    proposal_count+=1;ok,why,_=fast.legal(lay)
    plog.write(json.dumps({'submission':{'placements_mm':lay},'kind':kind,'passed':ok,'reason':why,**meta})+'\n');plog.flush()
    if not ok:failures[why]=failures.get(why,0)+1
    return ok
def measure(lay,kind,**meta):
    sub={'placements_mm':lay};ident=key(sub)
    if ident in seen or not fast.legal(lay)[0] or len(records)>=a.evals:return None
    seen.add(ident);r=fast.estimate(lay,64,3,SCREEN)
    xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw={w:{d:float(g[np.ix_((yy>=y)&(yy<y+fast.SPEC['dies'][d]['size_mm'][1]),
                  (xx>=x)&(xx<x+fast.SPEC['dies'][d]['size_mm'][0]))].max())
            for d,(x,y) in lay.items()} for w,g in r['grids'].items()}
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'kind':kind,'evaluation':len(records),
         'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68),
         'topology':signature(lay),'elapsed_seconds':time.monotonic()-start,**meta}
    rec['continuous_merit_c']=float(max(response(rec)));records.append(rec)
    log.write(json.dumps(rec)+'\n');log.flush()
    best=min(records,key=lambda q:q['continuous_merit_c'])
    if rec is best:
        write_json(a.output/'submission.json',sub)
        print('BEST',len(records),rec['screen_score'],rec['gpu'],rec['hbm'],rec['continuous_merit_c'],kind,flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'proposals':proposal_count,
        'best_score':best['screen_score'],'best_continuous_merit_c':best['continuous_merit_c'],
        'distinct_topologies':len(set(r['topology'] for r in records)),'elapsed_seconds':time.monotonic()-start})
    if len(records)%25==0:print('PROGRESS',len(records),kind,'best',best['screen_score'],flush=True)
    return rec

write_json(a.output/'manifest.json',{'kind':'native64 screening; pinned certification required','workloads':SCREEN,
    'budget':a.evals,'seed':a.seed,'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in [Path(__file__).name,'route_milp.py']},
    'rules_sha256':{n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest() for n in ['challenge_spec.json','geometry.py','run_simulations.py','workloads.json']}})

if a.seed_list:
    seeds=json.loads(a.seed_list.read_text())
    for q in seeds:
        sub=q.get('submission') or json.loads((ROOT/q['path']).read_text())
        lay=sub['placements_mm']
        if record_proposal(lay,'provided-seed',metadata=q):measure(lay,'provided-seed',family=q.get('signature',q.get('kind','provided')))
elif a.only_refine:
    measure(json.loads(a.only_refine.read_text())['placements_mm'],'provided-seed',family='provided')
else:
    cycle=['G0','H0','G1','H1','G2','H2','G3','H3']
    # Three-square L boundary: a concave eight-die polygon absent from old surveys.
    sites=[(0,0),(1,0),(2,0),(2,1),(1,1),(1,2),(0,2),(0,1)]
    seeds=[]
    for mirror,turn,shift,px,py in itertools.product([False,True],range(4),range(0,8,2),[12.,13.5,15.],[11.5,12.75,14.]):
        xy=np.array(sites,dtype=float)-1
        if mirror:xy[:,0]*=-1
        for _ in range(turn):xy=xy[:,::-1]*[1,-1]
        lay={}
        for i,(x,y) in enumerate(xy):
            die=cycle[(i+shift)%8];w,h=fast.SPEC['dies'][die]['size_mm']
            lay[die]=[round(26+px*x-w/2,6),round(21+py*y-h/2,6)]
        meta={'family':'concave-L','mirror':mirror,'turn':turn,'shift':shift,'px':px,'py':py}
        if record_proposal(lay,'new-topology-seed',**meta):seeds.append((lay,meta))
    # Include already asymmetric inverted ring, plus its label-preserving reflections.
    inv=json.loads((ROOT/'simulation/research-v3/lead/inverted-refinement/submission.json').read_text())['placements_mm']
    for fx,fy in itertools.product([False,True],repeat=2):
        lay={d:[round(52-x-fast.SPEC['dies'][d]['size_mm'][0] if fx else x,6),
                round(42-y-fast.SPEC['dies'][d]['size_mm'][1] if fy else y,6)] for d,(x,y) in inv.items()}
        meta={'family':'inverted-asymmetric','fx':fx,'fy':fy}
        if record_proposal(lay,'new-topology-seed',**meta):seeds.append((lay,meta))
    write_json(a.output/'seed-summary.json',{'valid':len(seeds),'rejection_counts':failures})
    print('SEEDS',len(seeds),'of',proposal_count,flush=True)
    for lay,meta in seeds:measure(lay,'new-topology-seed',**meta)

def merit(r):
    return r['raw_peaks_c']['skewed_compute']['G0'] if a.objective=='g0' else r['continuous_merit_c']

# Maintain independent local models for different facing-edge patterns, moving
# all sixteen coordinates and endpoint track cells; no protected G0 position.
family_records={}
for r in records:family_records.setdefault(r['topology'],[]).append(r)
families=sorted(family_records,key=lambda s:min(merit(q) for q in family_records[s]))[:12]
write_json(a.output/'refined-topologies.json',[{'signature':s,'seed_score':min(q['screen_score'] for q in family_records[s])} for s in families])
for iteration in range(a.evals*8):
    if len(records)>=a.evals:break
    # Every fourth proposal explores a weaker distinct topology; otherwise refine leaders.
    family=families[(iteration//4)%len(families)] if iteration%4==0 else min(families,key=lambda s:min(merit(q) for q in family_records[s]))
    pool=family_records[family];ranked=sorted(pool,key=merit)
    best=ranked[0];anchor=best if iteration%5 else ranked[int(rng.integers(min(6,len(ranked))))]
    xb=vector(anchor['submission']['placements_mm']);X=np.array([vector(q['submission']['placements_mm'])-xb for q in pool])
    distance=np.sum((X/.6)**2,axis=1);ix=np.argsort(distance)[:240];xx=X[ix]/.3
    Y=np.array([response(pool[i]) for i in ix]);weights=np.maximum(1e-6,np.exp(-distance[ix]/3))
    F=np.column_stack([np.ones(len(xx)),xx,xx*xx])
    model=np.linalg.solve(F.T@(weights[:,None]*F)+np.diag([1e-9]+[.001]*32),F.T@(weights[:,None]*Y))
    gradients=model[1:17].T/.3
    radius=[.08,.2,.4,.8,1.5,3.][iteration%6]
    # Sample local directions before trusting a model, then retain exploration.
    if len(pool)<35:gradients=np.zeros_like(gradients)
    noise=rng.normal(0,.15 if len(pool)<35 else (.02 if iteration%11==0 else .0002),16)
    if a.freeze_g0:noise[:2]=0
    target=response(anchor)
    if a.objective=='g0':
        ii=components.index(('skewed_compute','G0'));gradients=gradients[ii:ii+1];target=target[ii:ii+1]
    lay,info=propose(anchor['submission']['placements_mm'],gradients,target,radius,(0,0) if a.freeze_g0 else (radius,radius),noise)
    if lay is not None:
        legal=record_proposal(lay,'global-milp',iteration=iteration,anchor=anchor['evaluation'],radius=radius,proposal=info)
        if legal:
            rec=measure(lay,'global-milp',iteration=iteration,anchor=anchor['evaluation'],radius=radius,family=anchor.get('family'),proposal=info)
            if rec:
                family_records.setdefault(rec['topology'],[]).append(rec)
                bestobjective=min(records,key=merit)
                if rec is bestobjective:write_json(a.output/'objective-submission.json',rec['submission']);print('OBJECTIVE',len(records),merit(rec),rec['screen_score'],flush=True)
    if iteration%20==0:print('ITER',iteration,'sims',len(records),'familybest',best['screen_score'],flush=True)

write_json(a.output/'completion.json',{'evaluations':len(records),'proposals':proposal_count,'elapsed_seconds':time.monotonic()-start})
log.close();plog.close()
