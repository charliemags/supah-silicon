"""Population DE/basin hopping with mixed-integer legal routing-cell repair.

Actual HotSpot screens are authoritative for selection, not learned predictions.
The proposal helper was adapted from research-v5/target_milp.py, with L1 target
repair, a controllable thermal weight, and a bounded proposal solve time.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
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
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--evals',type=int,default=1600)
p.add_argument('--seed',type=int,default=9406);a=p.parse_args()
a.output.mkdir(exist_ok=False);rng=np.random.default_rng(a.seed);start=time.monotonic()
components=[(w,d) for w in SCREEN for d in DIES]
den=np.array([79.59 if d.startswith('G') else 72.68 for w,d in components])
def response(r):
    peaks=r.get('raw_peaks_c',r['peaks'])
    return np.array([25+(peaks[w][d]-25)*79.59/den[i] for i,(w,d) in enumerate(components)])
base=json.loads((ROOT/'simulation/research-v5/submission.json').read_text())
history={};sources=[]
for directory in ['research-v4','research-v5']:
    for path in (ROOT/'simulation'/directory).glob('*/search.jsonl'):
        sources.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        for line in path.read_text().splitlines():
            r=json.loads(line)
            if r.get('passed') and r.get('grid')==64 and set(SCREEN)<=set(r.get('peaks',{})) and not r['submission'].get('wire_routes_grid'):
                r['continuous_merit_c']=float(max(response(r)));history[key(r['submission'])]=r
history=list(history.values());records=[];seen=set();rejected={};proposals=0
log=(a.output/'search.jsonl').open('w');plog=(a.output/'proposals.jsonl').open('w')
manifest={'kind':'population differential-evolution + mixed integer basin hopping; native screens only; unchanged original rules',
 'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('proposal.py')]},
 'helper_origin':'simulation/research-v5/target_milp.py','helper_origin_sha256':hashlib.sha256((ROOT/'simulation/research-v5/target_milp.py').read_bytes()).hexdigest(),
 'hotspot_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'baseline_sha256':hashlib.sha256((ROOT/'simulation/research-v5/submission.json').read_bytes()).hexdigest(),
 'historical_records':len(history),'historical_sources':sources,'seed':a.seed,'budget':a.evals,'grid':64,'workloads':SCREEN,'cpus':3}
write_json(a.output/'manifest.json',manifest)
def measure(lay,kind,**meta):
    sub={'placements_mm':lay};ident=key(sub)
    if ident in seen:return None
    ok,reason,routing=fast.legal(lay)
    if not ok:raise AssertionError(reason)
    r=fast.estimate(lay,64,3,SCREEN);xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw={}
    for w,g in r['grids'].items():
        raw[w]={}
        for d,(x,y) in lay.items():
            width,height=fast.SPEC['dies'][d]['size_mm']
            raw[w][d]=float(g[np.ix_((yy>=y)&(yy<y+height),(xx>=x)&(xx<x+width))].max())
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'kind':kind,'evaluation':len(records),'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68),
         'elapsed_seconds':time.monotonic()-start,'weighted_route':routing['weighted_route_gb_s_mm'],**meta}
    rec['continuous_merit_c']=float(max(response(rec)));seen.add(ident);records.append(rec)
    log.write(json.dumps(rec)+'\n');log.flush();best=min(records,key=lambda r:r['continuous_merit_c'])
    if rec is best:
        write_json(a.output/'submission.json',sub);write_json(a.output/'best.json',rec)
        print('BEST',len(records),rec['gpu'],rec['hbm'],rec['screen_score'],rec['continuous_merit_c'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'proposals':proposals,'best_screen_score':best['screen_score'],'best_continuous_merit_c':best['continuous_merit_c'],
        'rejected':rejected,'elapsed_seconds':time.monotonic()-start})
    return rec
measure(base['placements_mm'],'control')
# Build diverse archive of genuinely measured historical placements. No predictions enter it.
population=[records[0]]
for r in sorted(history,key=lambda r:r['continuous_merit_c']):
    if r['continuous_merit_c']>104:break
    x=vector(r['submission']['placements_mm'])
    if min(np.linalg.norm(x-vector(p['submission']['placements_mm'])) for p in population)>.85:
        population.append(r)
    if len(population)>=32:break
seed_pop=list(population)
write_json(a.output/'initial-population.json',[{'submission':r['submission'],'native_continuous_merit_c':r['continuous_merit_c']} for r in population])
for iteration in range(a.evals*8):
    if len(records)>=a.evals:break
    best=min(records,key=lambda r:r['continuous_merit_c']);mode=iteration%6
    # Exploit actual best, retain distant islands, periodically restart old basins.
    anchor=best if iteration%3==0 else population[int(rng.integers(len(population)))]
    if iteration%41==0:anchor=seed_pop[int(rng.integers(len(seed_pop)))]
    xb=vector(anchor['submission']['placements_mm']);allrecords=history+records
    XX=np.array([vector(r['submission']['placements_mm']) for r in allrecords]);dist=np.sum(((XX-xb)/np.array([.5,.5]+[1.5]*14))**2,axis=1)
    idx=np.argsort(dist)[:240];X=(XX[idx]-xb);Y=np.array([response(allrecords[i]) for i in idx]);weights=np.maximum(1e-7,np.exp(-dist[idx]/3))
    F=np.column_stack([np.ones(len(X)),X]);model=np.linalg.solve(F.T@(weights[:,None]*F)+np.diag([1e-9]+[.003]*16),F.T@(weights[:,None]*Y))
    gradients=model[1:17].T;yb=response(anchor);radius=[1.,2.,4.,8.][(iteration//6)%4]
    params={'radius':radius,'g0_radius':(radius,radius),'time_limit':.65};name='global-linear-minimax'
    if mode in [1,2]:
        # DE/rand/1 and current-to-best/1, followed by exact mixed integer L1 repair.
        pa,pb,pc=[vector(population[i]['submission']['placements_mm']) for i in rng.choice(len(population),3,replace=len(population)<3)]
        target=pa+rng.uniform(.45,1.6)*(pb-pc) if mode==1 else xb+rng.uniform(.2,.9)*(vector(best['submission']['placements_mm'])-xb)+rng.uniform(.4,1.4)*(pb-pc)
        cross=rng.random(16)<.7;target=np.where(cross,target,xb)
        target += rng.normal(0,.08 if iteration%4 else .4,16)
        params.update(target=target,repair_weight=1.,temperature_weight=.01,noise=None);name='differential-evolution-repair'
    elif mode==3:
        # Thermal-grid-scale relocation can cross basins without losing the favourable hotspot phase.
        hop=np.array([.8125,.65625])*rng.choice([-3,-2,-1,0,1,2,3],2)+rng.normal(0,.015,2)
        target_g0=np.clip(vector(best['submission']['placements_mm'])[:2]+hop,[1.001,1.001],[39.499,30.499])
        params.update(radius=8.,g0_radius=(8,8),g0_target=target_g0,noise=rng.normal(0,.002,16));name='hotspot-phase-basin-hop'
    elif mode==4:
        params.update(temperature_weight=.02,noise=rng.normal(0,.1,16));name='global-random-support'
    else:
        params.update(noise=rng.normal(0,.0005 if mode==0 else .005,16))
    lay,info=propose(anchor['submission']['placements_mm'],gradients,yb,**params);proposals+=1
    info.update(iteration=iteration,kind=name,anchor={'placements_mm':anchor['submission']['placements_mm']},
                params={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in params.items()},submission={'placements_mm':lay} if lay else None)
    plog.write(json.dumps(info)+'\n');plog.flush()
    if lay is None or not info['exact_valid']:
        reason=info.get('exact_reason',info.get('message','unknown'));rejected[reason]=rejected.get(reason,0)+1
    else:
        rec=measure(lay,name,proposal_iteration=iteration,cell_changes=info['cell_changes'])
        if rec:
            # Niches preserve distinct G0/neighbor arrangements even if not immediately best.
            x=vector(lay);distances=[np.linalg.norm((x-vector(r['submission']['placements_mm']))/np.array([.7,.7]+[2.]*14)) for r in population]
            nearest=int(np.argmin(distances))
            if min(distances)<.6:
                if rec['continuous_merit_c']<population[nearest]['continuous_merit_c']:population[nearest]=rec
            elif len(population)<48:population.append(rec)
            elif rec['continuous_merit_c']<max(r['continuous_merit_c'] for r in population):population[np.argmax([r['continuous_merit_c'] for r in population])]=rec
    if iteration%25==0:print('PROGRESS',iteration,'screens',len(records),'best',min(r['continuous_merit_c'] for r in records),'population',len(population),'seconds',round(time.monotonic()-start),flush=True)
write_json(a.output/'completed.json',{'evaluations':len(records),'proposals':proposals,'seconds':time.monotonic()-start,'stopped':'budget' if len(records)>=a.evals else 'proposal-limit'})
log.close();plog.close()
