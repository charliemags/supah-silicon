"""Exact-valid, plateau-aware local experiments; screening is never certification."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'simulation/tools'))
sys.path.insert(0, str(ROOT / 'simulation/research-v3/packaging'))
import fast
from explore import alternatives
from optimize import compact, key, write_json
from population import proposal
from surrogate import DIES, SCREEN, cheap_legal, placement, vector


def measure(sub, workloads=SCREEN, grid=64):
    result = fast.estimate(sub['placements_mm'], grid, workers=3,
                           workloads=workloads, paths=sub.get('wire_routes_grid'))
    if not result['passed']:
        raise ValueError(result)
    # Search-only tie-breaker. The real max-temperature scoring is unchanged.
    xy = sub['placements_mm']['G0']
    xx = (np.arange(grid) + .5) * 52 / grid
    yy = 42 - (np.arange(grid) + .5) * 42 / grid
    values = result['grids']['skewed_compute'][np.ix_(
        (yy >= xy[1]) & (yy < xy[1]+10.5),
        (xx >= xy[0]) & (xx < xy[0]+11.5))].ravel()
    hottest = np.sort(values)[-9:]
    result['hotspot_neighborhood_c'] = float(hottest.mean())
    result['smooth_hotspot_c'] = float(hottest[-1] + .25 * np.log(np.exp((hottest-hottest[-1])/.25).sum()))
    ref = json.loads((fast.HILL/f'reference_{grid}.json').read_text())
    result['screen_score'] = max((result['gpu']-25)/(ref['worst_gpu_c']-25),
                                 (result['hbm']-25)/(ref['worst_hbm_c']-25))
    return {'submission': sub, **compact(result)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['routes', 'placement'])
    p.add_argument('--start', default='simulation/research-v3/lead/finalists/control-hbm/submission.json')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--evals', type=int, default=1024)
    p.add_argument('--seed', type=int, default=2026101804)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    initial = json.loads(Path(a.start).read_text())
    write_json(a.output/'manifest.json', {
        'kind': 'native screening; pinned all-workload 64/128 verification required',
        'arguments': {k: str(v) if isinstance(v, Path) else v for k,v in vars(a).items()},
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'solver_sha256': hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
        'input_sha256': hashlib.sha256(Path(a.start).read_bytes()).hexdigest(),
        'challenge_sha256': {str(f):hashlib.sha256((fast.HILL/f).read_bytes()).hexdigest()
                             for f in ['challenge_spec.json', 'workloads.json', 'geometry.py', 'run_simulations.py']}})
    rng = np.random.default_rng(a.seed)
    start = time.monotonic()
    records = []
    log = (a.output/'search.jsonl').open('w')

    def save(rec, **meta):
        rec.update(evaluation=len(records), elapsed_seconds=round(time.monotonic()-start, 3), **meta)
        records.append(rec)
        log.write(json.dumps(rec)+'\n'); log.flush()
        best = min(records, key=lambda r:(r['screen_score'], r['smooth_hotspot_c'],r['hbm']))
        if rec is best:
            write_json(a.output/'submission.json', rec['submission'])
            print('BEST', len(records), rec['screen_score'], rec['gpu'], rec['hbm'], rec['smooth_hotspot_c'], flush=True)
        write_json(a.output/'summary.json', {'evaluations':len(records), 'best_score':best['screen_score'],
            'best_evaluation':best['evaluation'], 'elapsed_seconds':time.monotonic()-start})
        if len(records)%64 == 0:
            print('PROGRESS',len(records),'best',best['screen_score'],flush=True)

    if a.mode == 'routes':
        routing = fast.legal(initial['placements_mm'])[2]
        candidates = [(initial, {'kind':'control'})]
        for link, route in routing['routes'].items():
            paths = alternatives(initial['placements_mm'],route)
            for i,path in enumerate(paths):
                if path == route['path_grid']: continue
                sub = {'placements_mm':initial['placements_mm'], 'wire_routes_grid':{link:path}}
                if not fast.legal(sub['placements_mm'],sub['wire_routes_grid'])[0]: raise ValueError('invalid enumerated route')
                candidates.append((sub,{'kind':'equal-length-route','link':link,'path_index':i}))
        with ThreadPoolExecutor(max_workers=2) as pool:
            for (sub,meta),res in zip(candidates,pool.map(lambda c:measure(c[0],['skewed_compute']),candidates)):
                save(res,**meta)
        # Combine the strongest independently changed routes and screen all workloads.
        routes = {}
        for link in routing['routes']:
            options = [r for r in records if r.get('link')==link]
            if options:
                best = min(options,key=lambda r:(r['screen_score'],r['smooth_hotspot_c']))
                routes[link] = best['submission']['wire_routes_grid'][link]
        save(measure({'placements_mm':initial['placements_mm'],'wire_routes_grid':routes},None),kind='combined-all-five')
    else:
        # Eight chains explore plateaus and feasible disconnected track cells.
        # G0 remains near its promising basin in half of moves; remote dies are free.
        first=measure(initial); save(first,kind='control')
        states=[first]*8
        seen={key(initial)}; archive=[vector(initial['placements_mm'])]
        attempts=0
        def merit(r):
            gpu_equiv=25+(r['hbm']-25)*79.59/72.68
            other=max(v for w,peaks in r['peaks'].items() for d,v in peaks.items()
                      if d.startswith('G') and (w,d)!=('skewed_compute','G0'))
            return max(r['smooth_hotspot_c'], other, gpu_equiv)
        with ThreadPoolExecutor(max_workers=2) as pool:
            while len(records)<a.evals:
                best=min(records,key=lambda r:(r['screen_score'],r['smooth_hotspot_c']))
                batch=[]
                for j in range(min(2,a.evals-len(records))):
                    walker=(len(records)+j)%8
                    anchor=states[walker]
                    if rng.random()<.15: anchor=best
                    av=vector(anchor['submission']['placements_mm'])
                    radius=rng.choice([.03,.1,.3,.7,1.4])
                    for trial in range(10000):
                        attempts+=1
                        x=proposal(anchor['submission']['placements_mm'],best['submission']['placements_mm'],archive,rng,radius)
                        if rng.random()<.55:x[:2]=av[:2]
                        if rng.random()<.15:
                            x[:2]=vector(initial['placements_mm'])[:2]+rng.normal(0,[.025,.09])
                        sub={'placements_mm':placement(x)}
                        if key(sub) not in seen and cheap_legal(x) and fast.legal(sub['placements_mm'])[0]:break
                    else: raise RuntimeError('No new valid proposal')
                    seen.add(key(sub)); batch.append((walker,sub,pool.submit(measure,sub)))
                for walker,sub,future in batch:
                    rec=future.result()
                    temperature=[.00001,.003,.01,.025,.05,.1,.2,.4][walker]
                    delta=merit(rec)-merit(states[walker])
                    accepted=delta<=0 or rng.random()<np.exp(-delta/temperature)
                    if accepted:states[walker]=rec
                    archive.append(vector(sub['placements_mm']));archive=archive[-500:]
                    save(rec,kind='plateau-aware-placement',walker=walker,accepted=bool(accepted),merit_c=merit(rec),attempts=attempts)
                if len(records)%128<2:
                    states[0]=min(records,key=merit)
    log.close()


if __name__=='__main__':main()
