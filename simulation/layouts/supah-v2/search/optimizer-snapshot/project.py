"""Explore a die's location with constrained coordinated movement of its neighbors.

SLSQP only proposes placements. Its approximate route constraints never replace
the organizer's exact legality checks or thermal simulation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy.optimize import minimize
import fast
from geometry import _route_grid, die_box
from bayes import DIES, SCREEN, placement, vector
from optimize import compact, key, score, write_json


def project(anchor, target, die='G0', rounds=5):
    ok, _, routing = fast.legal(anchor)
    if not ok:
        return None
    sizes = np.array([fast.SPEC['dies'][d]['size_mm'] for d in DIES])
    origin = vector(anchor)
    index = DIES.index(die)
    bounds = [(1., fast.SPEC['interposer_mm'][axis]-sizes[i,axis]-1.)
              for i in range(8) for axis in range(2)]
    bounds[2*index:2*index+2] = [(float(t),float(t)) for t in target]
    pairs = []
    for i in range(8):
        for j in range(i+1,8):
            delta = origin.reshape(8,2)[j]-origin.reshape(8,2)[i]
            choices = [(delta[k]-sizes[i,k], i,j,k) for k in range(2)]
            choices += [(-delta[k]-sizes[j,k],j,i,k) for k in range(2)]
            _, first, second, axis = max(choices)
            pairs.append((first,second,axis))
    links = list(routing['routes'].values())
    ia = np.array([DIES.index(r['from']) for r in links])
    ib = np.array([DIES.index(r['to']) for r in links])
    oa = np.array([r['from_port'] for r in links])-origin.reshape(8,2)[ia]
    ob = np.array([r['to_port'] for r in links])-origin.reshape(8,2)[ib]
    limits = np.array([r['limit_mm'] for r in links])
    weights = np.array([r['bandwidth_gb_s'] for r in links])
    def manhattan(x):
        xy = x.reshape(8,2)
        return np.abs(xy[ia]+oa-xy[ib]-ob).sum(axis=1)
    overhead = np.array([r['route_length_mm'] for r in links])-manhattan(origin)
    def constraints(x):
        xy = x.reshape(8,2)
        gaps = [xy[j,k]-xy[i,k]-sizes[i,k]-1.001 for i,j,k in pairs]
        lengths = manhattan(x)+overhead
        return np.r_[gaps,limits-lengths, (13499.-lengths@weights)/600.]
    start = origin.copy()
    start[2*index:2*index+2] = target
    for _ in range(rounds):
        result = minimize(lambda x:float(np.sum((x-origin)**2)),start,
                          jac=lambda x:2*(x-origin), bounds=bounds,
                          constraints={'type':'ineq','fun':constraints},method='SLSQP',
                          options={'maxiter':120,'ftol':1e-8})
        candidate = placement(result.x)
        if fast.legal(candidate)[0]:
            return candidate
        if np.min(constraints(result.x)) < -0.05:
            return None
        # Re-estimate only track-access overhead; final validation is unchanged.
        boxes = {d:die_box(fast.SPEC,candidate,d) for d in DIES}
        lengths = []
        try:
            for i,r in enumerate(links):
                pa = {'center_mm':np.array(candidate[r['from']])+oa[i], 'normal':r['from_normal']}
                pb = {'center_mm':np.array(candidate[r['to']])+ob[i], 'normal':r['to_normal']}
                lengths.append(_route_grid(fast.SPEC,boxes,pa,pb)[0])
        except ValueError:
            return None
        overhead = np.maximum(0,np.array(lengths)-manhattan(vector(candidate)))+0.005
        start = result.x
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('start',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--die',choices=DIES,default='G0')
    p.add_argument('--x',type=float,nargs=3,default=[3.4,5.4,11],metavar=('START','STOP','COUNT'))
    p.add_argument('--y',type=float,nargs=3,default=[3.,5.8,15],metavar=('START','STOP','COUNT'))
    p.add_argument('--grid',type=int,choices=(64,128),default=64)
    p.add_argument('--parallel',type=int,default=2)
    a=p.parse_args()
    if a.parallel<1 or any(v[2]<1 or int(v[2]) != v[2] for v in (a.x,a.y)):
        p.error('parallel and grid counts must be positive integers')
    anchor=json.loads(a.start.read_text())['placements_mm']
    if not fast.legal(anchor)[0]:p.error('illegal starting placement')
    a.output.mkdir(parents=True,exist_ok=False)
    manifest={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()}
    manifest.update(kind='native screening; requires pinned all-workload verification',
        hotspot_sha256=hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=hashlib.sha256(a.start.read_bytes()).hexdigest(),
        files_sha256={n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest() for n in ('challenge_spec.json','workloads.json')})
    write_json(a.output/'experiment.json',manifest)
    ref=json.loads((fast.HILL/f'reference_{a.grid}.json').read_text())
    reference={'gpu':ref['worst_gpu_c'],'hbm':ref['worst_hbm_c']}
    started=time.monotonic()
    seen={key({'placements_mm':anchor})}
    feasible=[anchor]
    rejected=0
    for x in np.linspace(a.x[0],a.x[1],int(a.x[2])):
        for y in np.linspace(a.y[0],a.y[1],int(a.y[2])):
            candidate=project(anchor,[x,y],a.die)
            if candidate is None:
                rejected+=1
                continue
            identity=key({'placements_mm':candidate})
            if identity not in seen:
                feasible.append(candidate); seen.add(identity)
    write_json(a.output/'proposals.json',{'placements':feasible,'rejected':rejected})
    print(f'Projected {len(feasible)} legal candidates; rejected {rejected}',flush=True)
    best=float('inf')
    with ThreadPoolExecutor(max_workers=a.parallel) as pool, (a.output/'search.jsonl').open('w') as log:
        def evaluate(lay):return compact(fast.estimate(lay,a.grid,workers=3,workloads=SCREEN))
        for i,(layout,result) in enumerate(zip(feasible,pool.map(evaluate,feasible))):
            if not result['passed']:raise RuntimeError(result)
            value=score(result,reference)
            sub={'placements_mm':layout}
            record={'evaluation':i,'submission':sub,'screen_score':value,
                    'elapsed_seconds':round(time.monotonic()-started,2),**result}
            log.write(json.dumps(record)+'\n');log.flush()
            if value<best:
                best=value
                write_json(a.output/'submission.json',sub)
                print(f'BEST {i+1}: {best:.8f} GPU={result["gpu"]:.2f} HBM={result["hbm"]:.2f}',flush=True)
            write_json(a.output/'summary.json',{'kind':'screen estimate; verify with pinned judge',
                'evaluations':i+1,'rejected':rejected,'best_score':best,'elapsed_seconds':round(time.monotonic()-started,2)})


if __name__=='__main__':main()
