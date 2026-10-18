"""Targeted large thermal-basin jumps within newly discovered topologies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
os.environ['CRYO_HOTSPOT'] = str(ROOT / '.cache/hotspot-precise')
sys.path.insert(0, str(ROOT / 'simulation/tools'))
import fast
from optimize import compact, key, write_json
from surrogate import DIES, SCREEN, vector
from proposal import propose

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
rng=np.random.default_rng(9461);start=time.monotonic();records=[];seen=set()
anchors=[]
for directory in ['contact-g0','folded-g0','concave-global']:
    path=ROOT/'simulation/research-v6/topology'/directory/'search.jsonl'
    if not path.exists():continue
    groups={}
    for line in path.read_text().splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        sig=r.get('topology','unknown')
        if sig not in groups or r['raw_peaks_c']['skewed_compute']['G0']<groups[sig]['raw_peaks_c']['skewed_compute']['G0']:groups[sig]=r
    anchors.extend(sorted(groups.values(),key=lambda r:r['raw_peaks_c']['skewed_compute']['G0'])[:5])
write_json(a.output/'anchors.json',anchors)
write_json(a.output/'manifest.json',{'kind':'exact-valid native screening; pinned evaluation required',
    'source_sha256':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest() for n in ['search.py','proposal.py']},
    'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'seed':9461,
    'purpose':'Large G0-location jumps with coordinated neighbor repair in non-incumbent topologies; optional unchanged-contact containment of other GPUs.'})
log=(a.output/'search.jsonl').open('w');plog=(a.output/'proposals.jsonl').open('w')
def measure(sub,**meta):
    ident=key(sub)
    if ident in seen or not fast.legal(sub['placements_mm'])[0]:return
    r=fast.estimate(sub['placements_mm'],64,2,SCREEN);lay=sub['placements_mm']
    xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
    raw={w:{d:float(g[np.ix_((yy>=y)&(yy<y+fast.SPEC['dies'][d]['size_mm'][1]),(xx>=x)&(xx<x+fast.SPEC['dies'][d]['size_mm'][0]))].max()) for d,(x,y) in lay.items()} for w,g in r['grids'].items()}
    rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'evaluation':len(records),**meta,'elapsed_seconds':time.monotonic()-start}
    rec['screen_score']=max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68)
    rec['continuous_merit_c']=max(25+(v-25)*79.59/(79.59 if d.startswith('G') else 72.68) for pp in raw.values() for d,v in pp.items())
    seen.add(ident);records.append(rec);log.write(json.dumps(rec)+'\n');log.flush()
    best=min(records,key=lambda r:r['continuous_merit_c'])
    if rec is best:write_json(a.output/'submission.json',sub);print('BEST',len(records),r['gpu'],r['hbm'],flush=True)
    write_json(a.output/'summary.json',{'evaluations':len(records),'best_screen_score':best['screen_score'],'minimum_G0_c':min(r['raw_peaks_c']['skewed_compute']['G0'] for r in records),'elapsed_seconds':time.monotonic()-start})

measure(json.loads((ROOT/'simulation/research-v5/submission.json').read_text()),kind='preserved-control')
for ai,anchor in enumerate(anchors):
    lay0=anchor['submission']['placements_mm'];xy0=vector(lay0)
    for contact in [False,True]:
        for tx,ty in [(3.193438,4.119202),(3.193438,3.462952),(3.193438,4.775452),(4.005938,4.119202),(4.818438,4.119202)]:
            for variant in range(3):
                target=xy0.copy()
                if variant:
                    target[2:]+=rng.normal(0,2,14)
                cand,info=propose(lay0,np.zeros((1,16)),np.array([100.]),radius=14,g0_radius=(40,40),g0_target=(tx,ty),
                    target=target,repair_weight=.01,temperature_weight=0,contact_gpus=contact,time_limit=.6)
                info.update(anchor=ai,target_g0=[tx,ty],contact_gpus=contact,variant=variant,submission={'placements_mm':cand} if cand else None)
                plog.write(json.dumps(info)+'\n');plog.flush()
                if cand is not None and info['exact_valid']:measure({'placements_mm':cand},kind='repaired-basin-jump',proposal=info)
log.close();plog.close()
