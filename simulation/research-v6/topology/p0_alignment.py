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
from route_fixed import propose
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
    'source_sha256':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['p0_alignment.py','route_fixed.py']},
    'challenge_sha256':{n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest() for n in ['challenge_spec.json','geometry.py','run_simulations.py','workloads.json']}})
measure(base['placements_mm'],'control')
targets=[(dx,phase,trial) for dx in [-.02,-.01,0,.01,.02] for phase in [-.02,-.01,0,.01,.02] for trial in range(2)]
origin=base['placements_mm'];iteration=-1
for iteration,(dx,phase,trial) in enumerate(targets):
    if len(records)>=a.evals:break
    gx=origin['G0'][0]+dx;hy=4.15+phase;gy=hy-.15
    gap=5.-2*abs(phase)-.0001
    hx=gx+11.5+gap
    fixed={('G0',0):gx,('G0',1):gy,('H0',0):hx,('H0',1):hy}
    noise=np.zeros(16) if trial==0 else rng.normal(0,.00015,16)
    lay,info=propose(origin,np.zeros((1,16)),np.array([101.21]),radius=1.5,g0_radius=(1.5,1.5),noise=noise,fixed=fixed)
    entry={'iteration':iteration,'dx':dx,'phase':phase,'trial':trial,'target_gap_mm':gap,
        'target_g0_xy':[gx,gy],'target_h0_xy':[hx,hy],
        'submission':{'placements_mm':lay} if lay is not None else None,**info}
    plog.write(json.dumps(entry)+'\n');plog.flush()
    if lay is not None and info['exact_valid']:
        rec=measure(lay,'P0-aligned-target',proposal=entry)
        if rec:print('P0',iteration,rec['gpu'],rec['hbm'],rec['continuous_merit_c'],flush=True)
    else:rejected+=1
write_json(a.output/'completion.json',{'completed_observations':len(records),'proposal_iterations':iteration+1,
    'rejected_milp_proposals':rejected,'elapsed_seconds':time.monotonic()-started})
log.close();plog.close()
