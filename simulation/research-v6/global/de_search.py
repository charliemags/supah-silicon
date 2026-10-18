"""Adaptive measured-only DE with routing repair and thermal-phase-aware basins.

No learned thermal extrapolation is used for proposals or selection in this run.
Global group moves and differential crossover are repaired by the unchanged-rule
proposal MILP, then the original validator and actual HotSpot screen decide.
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
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--evals',type=int,default=1000);p.add_argument('--seed',type=int,default=9460);a=p.parse_args()
a.output.mkdir(exist_ok=False);rng=np.random.default_rng(a.seed);start=time.monotonic();records=[];seen=set();proposals=0
base=json.loads((ROOT/'simulation/research-v5/submission.json').read_text());basev=vector(base['placements_mm']);components=[(w,d) for w in SCREEN for d in DIES]
def response(r):
    raw=r.get('raw_peaks_c',r['peaks'])
    return np.array([25+(raw[w][d]-25)*79.59/(79.59 if d.startswith('G') else 72.68) for w,d in components])
history=[];sources=[]
for folder in ['simulation/research-v5','simulation/research-v6/global']:
    for path in (ROOT/folder).glob('*/search.jsonl'):
        if path.parent==a.output:continue
        sources.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        for l in path.read_text().splitlines():
            r=json.loads(l)
            if r.get('passed') and r.get('grid')==64 and set(SCREEN)<=set(r.get('peaks',{})) and not r['submission'].get('wire_routes_grid'):
                r['continuous_merit_c']=float(max(response(r)));history.append(r)
history=list({key(r['submission']):r for r in history}.values())
write_json(a.output/'manifest.json',{'kind':__doc__,'sources':sources,'baseline_sha256':hashlib.sha256((ROOT/'simulation/research-v5/submission.json').read_bytes()).hexdigest(),
 'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('proposal.py')]},'native_hotspot_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
 'cpus':3,'seed':a.seed,'budget':a.evals,'grid':64,'workloads':SCREEN})
log=(a.output/'search.jsonl').open('w');plog=(a.output/'proposals.jsonl').open('w');best=None
xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64

def measure(lay,kind,**meta):
    global best
    sub={'placements_mm':lay};ident=key(sub)
    if ident in seen:return None
    ok,reason,routing=fast.legal(lay)
    if not ok:raise AssertionError(reason)
    r=fast.estimate(lay,64,3,SCREEN);raw={}
    for w,g in r['grids'].items():
        raw[w]={}
        for d,(x,y) in lay.items():
            width,height=fast.SPEC['dies'][d]['size_mm'];raw[w][d]=float(g[np.ix_((yy>=y)&(yy<y+height),(xx>=x)&(xx<x+width))].max())
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'evaluation':len(records),'kind':kind,'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68),'elapsed_seconds':time.monotonic()-start,**meta}
    rec['continuous_merit_c']=float(max(response(rec)));seen.add(ident);records.append(rec);log.write(json.dumps(rec)+'\n');log.flush()
    if best is None or rec['continuous_merit_c']<best['continuous_merit_c']:
        best=rec;write_json(a.output/'submission.json',sub);write_json(a.output/'best.json',rec)
        print('BEST',len(records),rec['gpu'],rec['hbm'],rec['continuous_merit_c'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'proposals':proposals,'best_score':best['screen_score'],'best_continuous_merit_c':best['continuous_merit_c'],'elapsed_seconds':time.monotonic()-start})
    return rec
measure(base['placements_mm'],'control');population=[best]
# Initial archive has an accurate elite plus nearby-but-distinct measured basins.
for r in sorted(history,key=lambda r:r['continuous_merit_c']):
    if r['continuous_merit_c']>102.5:break
    x=vector(r['submission']['placements_mm'])
    if min(np.linalg.norm(x-vector(p['submission']['placements_mm'])) for p in population)>.25:population.append(r)
    if len(population)>=40:break
write_json(a.output/'initial-population.json',[{'submission':r['submission'],'continuous_merit_c':r['continuous_merit_c']} for r in population])
groups=[[0,4,7],[1,4,5],[2,5,6],[3,6,7],[0,1,4],[2,3,6],[0,3,7],[1,2,5],[0,1,2,3,4,5,6,7]]
for iteration in range(a.evals*8):
    if len(records)>=a.evals:break
    anchor=best if iteration%4 else population[int(rng.integers(len(population)))];origin=vector(anchor['submission']['placements_mm'])
    # Mix substantial coordinate-group translations, DE crossover, and basin hops.
    mode=iteration%5;scale=float(rng.choice([.05,.1,.2,.5,1.,2.,4.]))
    target=origin.copy();name='de-current-to-best';pa,pb,pc=[vector(population[i]['submission']['placements_mm']) for i in rng.choice(len(population),3,replace=len(population)<3)]
    if mode<2:
        target=origin+rng.uniform(.1,.8)*(vector(best['submission']['placements_mm'])-origin)+rng.uniform(.4,1.4)*(pb-pc)
        mask=rng.random(8)<rng.uniform(.25,.75);target=np.where(np.repeat(mask,2),target,origin)
    elif mode==2:
        group=groups[int(rng.integers(len(groups)))];delta=rng.normal(0,scale,2)
        for i in group:target[2*i:2*i+2]+=delta
        name='global-group-translation'
    elif mode==3:
        target+=rng.normal(0,scale,16);name='global-covariance-kick'
    else:
        centers=origin.reshape(8,2)+np.array([fast.SPEC['dies'][d]['size_mm'] for d in DIES])/2
        target+=((centers-[26,21])*rng.normal(0,scale/15,2)).ravel();name='global-affine-expansion'
    # Most proposals deliberately retain the best G0 sub-grid phase while the
    # other seven dies cross routing cells; occasional whole-grid basin jumps
    # and small phase changes explore G0 itself without arbitrary rounding.
    roll=rng.random()
    g0=vector(best['submission']['placements_mm'])[:2].copy()
    if roll<.15:g0 += np.array([.8125,.65625])*rng.choice([-2,-1,0,1,2],2)
    elif roll<.35:g0 += rng.normal(0,rng.choice([.005,.02,.05]),2)
    g0=np.clip(g0,[1.001,1.001],[39.499,30.499]);target[:2]=g0
    lay,info=propose(anchor['submission']['placements_mm'],np.zeros((1,16)),np.array([101.3]),radius=8,g0_radius=(8,8),g0_target=g0,target=target,repair_weight=1.,temperature_weight=0.,time_limit=.7)
    proposals+=1;info.update(iteration=iteration,kind=name,scale=scale,g0_target=g0.tolist(),target=target.tolist(),submission={'placements_mm':lay} if lay else None)
    plog.write(json.dumps(info)+'\n');plog.flush()
    if lay is not None and info['exact_valid']:
        rec=measure(lay,name,proposal_iteration=iteration,cell_changes=info['cell_changes'])
        if rec:
            x=vector(lay);ds=[np.linalg.norm(x-vector(r['submission']['placements_mm'])) for r in population];j=int(np.argmin(ds))
            if ds[j]<.2:
                if rec['continuous_merit_c']<population[j]['continuous_merit_c']:population[j]=rec
            elif len(population)<48:population.append(rec)
            elif rec['continuous_merit_c']<max(r['continuous_merit_c'] for r in population):population[np.argmax([r['continuous_merit_c'] for r in population])]=rec
    if iteration%25==0:print('PROGRESS',iteration,len(records),best['continuous_merit_c'],round(time.monotonic()-start),flush=True)
write_json(a.output/'completed.json',{'evaluations':len(records),'proposals':proposals,'seconds':time.monotonic()-start});log.close();plog.close()
