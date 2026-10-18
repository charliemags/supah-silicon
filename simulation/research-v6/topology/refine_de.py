"""Fresh local cross-track-cell minimax refinement; original rules authoritative."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
from optimize import compact,key,write_json
from surrogate import DIES,SCREEN,vector
from route_milp import propose
p=argparse.ArgumentParser();p.add_argument('--start',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);p.add_argument('--evals',type=int,default=400)
p.add_argument('--seed',type=int,default=94321);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);rng=np.random.default_rng(a.seed)
started=time.monotonic();records=[];seen=set();rejected=0
log=(a.output/'search.jsonl').open('w');plog=(a.output/'proposals.jsonl').open('w')
components=[(w,d) for w in SCREEN for d in DIES]
den=np.array([79.59 if d.startswith('G') else 72.68 for w,d in components])
def response(r):return np.array([25+(r['raw_peaks_c'][w][d]-25)*79.59/den[i] for i,(w,d) in enumerate(components)])
def measure(lay,kind,**meta):
    sub={'placements_mm':lay};ident=key(sub)
    if ident in seen or len(records)>=a.evals:return None
    ok,why,routing=fast.legal(lay)
    if not ok:return None
    r=fast.estimate(lay,64,3,SCREEN)
    xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw={w:{d:float(g[np.ix_((yy>=y)&(yy<y+fast.SPEC['dies'][d]['size_mm'][1]),
             (xx>=x)&(xx<x+fast.SPEC['dies'][d]['size_mm'][0]))].max())
            for d,(x,y) in lay.items()} for w,g in r['grids'].items()}
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'kind':kind,'evaluation':len(records),
         'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68),'weighted_route':routing['weighted_route_gb_s_mm'],
         'elapsed_seconds':time.monotonic()-started,**meta}
    rec['continuous_merit_c']=float(max(response(rec)));seen.add(ident);records.append(rec)
    log.write(json.dumps(rec)+'\n');log.flush();best=min(records,key=lambda r:r['continuous_merit_c'])
    if best is rec:
        write_json(a.output/'submission.json',sub)
        frozen=a.output/'finalists'/f'eval-{rec["evaluation"]:04d}';frozen.mkdir(parents=True)
        write_json(frozen/'submission.json',sub);write_json(frozen/'observation.json',rec)
        print('BEST',rec['evaluation'],rec['screen_score'],rec['gpu'],rec['hbm'],rec['continuous_merit_c'],str(frozen),flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'best_score':best['screen_score'],
        'best_continuous_merit_c':best['continuous_merit_c'],'elapsed_seconds':time.monotonic()-started})
    return rec
base=json.loads(a.start.read_text())
write_json(a.output/'manifest.json',{'kind':'native64 three-workload screening only; original validator and pinned judge authoritative',
    'start_path':str(a.start),'start_sha256':hashlib.sha256(a.start.read_bytes()).hexdigest(),
    'seed':a.seed,'budget':a.evals,'historical_observations':0,'workloads':SCREEN,'grid':64,
    'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
    'source_sha256':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['refine_de.py','route_milp.py']},
    'challenge_sha256':{n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest() for n in ['challenge_spec.json','geometry.py','run_simulations.py','workloads.json']}})
measure(base['placements_mm'],'control')
for iteration in range(a.evals*12):
    if len(records)>=a.evals:break
    ranked=sorted(records,key=lambda r:r['continuous_merit_c']);best=ranked[0]
    elite=[r for r in ranked[:24] if r['continuous_merit_c']<=best['continuous_merit_c']+.15]
    anchor=best if iteration%5 else elite[int(rng.integers(len(elite)))]
    xb=vector(anchor['submission']['placements_mm'])
    X=np.array([vector(r['submission']['placements_mm'])-xb for r in records])
    distance=np.sum((X/np.array([.025,.04]+[.35]*14))**2,axis=1)
    ix=np.argsort(distance)[:240];XX=X[ix]/np.array([.01,.02]+[.2]*14)
    Y=np.array([response(records[i]) for i in ix]);weights=np.maximum(1e-6,np.exp(-distance[ix]/3))
    F=np.column_stack([np.ones(len(XX)),XX])
    model=np.linalg.solve(F.T@(weights[:,None]*F)+np.diag([1e-9]+[.0001]*16),F.T@(weights[:,None]*Y))
    gradient=model[1:17].T/np.array([.01,.02]+[.2]*14)
    radius=[.025,.05,.1,.2,.5,1.][iteration%6]
    g0radius=(0,0) if iteration%3==0 else (.008,.015) if iteration%3==1 else (.02,.035)
    if len(records)<33:gradient=np.zeros_like(gradient)
    strength=.1 if len(records)<33 else .02 if iteration%11==0 else .0002
    noise=rng.normal(0,strength,16);noise[:2]*=.1
    lay,info=propose(anchor['submission']['placements_mm'],gradient,response(anchor),radius,g0radius,noise)
    entry={'iteration':iteration,'radius':radius,'g0_radius':g0radius,'anchor':anchor['evaluation'],
           'submission':{'placements_mm':lay} if lay is not None else None,**info}
    plog.write(json.dumps(entry)+'\n');plog.flush()
    if lay is not None and info['exact_valid']:
        measure(lay,'fresh-local-cross-cell',proposal=entry)
    else:rejected+=1
    # Also sample exact-valid small proposals to avoid repeatedly choosing one MILP vertex.
    if iteration%3==0 and len(records)>=33:
        x=vector(best['submission']['placements_mm']);ids=rng.choice(8,size=int(rng.choice([1,2,3])),replace=False)
        step=float(rng.choice([.001,.005,.015,.04,.1]))
        for i in ids:x[2*i:2*i+2]+=rng.normal(0,step*.15 if i==0 else step,2)
        candidate={d:[round(float(v),6) for v in x[2*i:2*i+2]] for i,d in enumerate(DIES)}
        ok,why,_=fast.legal(candidate);plog.write(json.dumps({'iteration':iteration,'kind':'fine-jitter','submission':{'placements_mm':candidate},'exact_valid':ok,'exact_reason':why})+'\n');plog.flush()
        if ok:measure(candidate,'fine-jitter',iteration=iteration)
    if iteration%30==0:print('PROGRESS',iteration,'simulations',len(records),flush=True)
write_json(a.output/'completion.json',{'completed_observations':len(records),'proposal_iterations':iteration+1,
    'rejected_milp_proposals':rejected,'elapsed_seconds':time.monotonic()-started})
log.close();plog.close()
