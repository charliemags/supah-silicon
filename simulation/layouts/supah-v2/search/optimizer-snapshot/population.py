"""Parallel tempered placement walkers with connected-group and differential moves.

Only legal layouts are simulated. Each retained score is a native HotSpot
screening estimate; use the pinned judge at both grids before promotion.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import fast
from bayes import DIES, SCREEN, cheap_legal, placement, vector
from optimize import compact, key, score, write_json

RING = [DIES.index(d) for d in ("G0", "H0", "G1", "H1", "G2", "H2", "G3", "H3")]


def proposal(current, best, archive, rng, radius):
    x = vector(current)
    mode = rng.random()
    step = radius * rng.choice([0.08, 0.2, 0.5, 1.0, 2.0])
    if mode < 0.25 and len(archive) > 2:
        a, b = rng.choice(len(archive), 2, replace=False)
        delta = (archive[a] - archive[b]) * rng.uniform(0.2, 0.9)
        delta *= rng.random(16) < rng.choice([0.25, 0.5, 1.0])
        if rng.random() < 0.5:
            delta += (vector(best)-x)*rng.uniform(0.05, 0.4)
        x += delta
    elif mode < 0.65:
        start = rng.integers(8)
        count = rng.choice([1, 2, 3, 4, 5, 6, 8])
        delta = rng.normal(0, step, 2)
        for i in (RING[(start+j) % 8] for j in range(count)):
            x[2*i:2*i+2] += delta
    elif mode < 0.8:
        centers = x.reshape(8, 2) + np.array([fast.SPEC['dies'][d]['size_mm'] for d in DIES])/2
        x += ((centers-[26, 21])*rng.normal(0, step/15, 2)).ravel()
    else:
        ids = rng.choice(16, int(rng.choice([1, 2, 4, 8, 16])), replace=False)
        x[ids] += rng.normal(0, step, len(ids))
    return x


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('start', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--history', type=Path, nargs='*', default=[])
    p.add_argument('--evals', type=int, default=1200)
    p.add_argument('--parallel', type=int, default=4)
    p.add_argument('--walkers', type=int, default=12)
    p.add_argument('--grid', type=int, choices=(64,128), default=64)
    p.add_argument('--seed', type=int, default=71)
    p.add_argument('--radius', type=float, default=1)
    p.add_argument('--temperature', type=float, default=0.003)
    a = p.parse_args()
    if min(a.evals, a.parallel, a.walkers, a.radius) <= 0 or a.temperature < 0:
        p.error('budgets and radius must be positive; temperature nonnegative')
    initial = json.loads(a.start.read_text())
    if initial.get('wire_routes_grid') or not fast.legal(initial['placements_mm'])[0]:
        p.error('start must be legal and automatically routed')
    a.output.mkdir(parents=True, exist_ok=False)
    manifest = {k: [str(i) for i in v] if isinstance(v,list) else str(v) if isinstance(v,Path) else v
                for k,v in vars(a).items()}
    manifest.update(kind='native screening only; pinned verification required',
                    code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    hotspot_sha256=hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),
                    input_sha256=hashlib.sha256(a.start.read_bytes()).hexdigest(),
                    history_sha256={str(h):hashlib.sha256(h.read_bytes()).hexdigest() for h in a.history},
                    files_sha256={n:hashlib.sha256((fast.HILL/n).read_bytes()).hexdigest()
                                  for n in ('challenge_spec.json','workloads.json')})
    write_json(a.output/'experiment.json',manifest)
    ref = json.loads((fast.HILL/f'reference_{a.grid}.json').read_text())
    reference = {'gpu':ref['worst_gpu_c'], 'hbm':ref['worst_hbm_c']}
    rng = np.random.default_rng(a.seed)
    records = [json.loads(line) for h in a.history for line in h.read_text().splitlines() if line.strip()]
    archive = [vector(r['submission']['placements_mm']) for r in records
               if r.get('passed') and r.get('grid')==a.grid and not r['submission'].get('wire_routes_grid')]
    # Keep old observations for directions, never treat their scores as this run's result.
    archive = archive[-1000:]
    seen = set()
    states = [initial['placements_mm'] for _ in range(a.walkers)]
    values = [float('inf')]*a.walkers
    best, best_value = states[0], float('inf')
    count, attempts = 0, 0
    started = time.monotonic()
    temperatures = np.geomspace(max(1e-7,a.temperature/30),max(1e-7,a.temperature),a.walkers)
    with ThreadPoolExecutor(max_workers=a.parallel) as executor, (a.output/'search.jsonl').open('w') as log:
        while count < a.evals:
            batch = []
            for j in range(min(a.parallel, a.evals-count)):
                walker = (count+j) % a.walkers
                if count == 0 and j == 0:
                    candidate = initial
                else:
                    candidate = None
                    for trial in range(3000):
                        attempts += 1
                        anchor = best if rng.random()<0.2 else states[walker]
                        x = proposal(anchor,best,archive,rng,a.radius)
                        # Backtracking moves can follow a tight constraint boundary.
                        for fraction in (1.0,0.5,0.2):
                            y = np.round(vector(anchor)+(x-vector(anchor))*fraction,3)
                            sub = {'placements_mm':placement(y)}
                            identity = key(sub)
                            if identity not in seen and cheap_legal(y) and fast.legal(sub['placements_mm'])[0]:
                                candidate = sub
                                break
                        if candidate:
                            break
                    if candidate is None:
                        raise RuntimeError('No legal unseen proposal after 3000 attempts')
                seen.add(key(candidate))
                future = executor.submit(fast.estimate,candidate['placements_mm'],a.grid,3,SCREEN)
                batch.append((walker,candidate,future))
            for walker,candidate,future in batch:
                result = future.result()
                if not result['passed']:
                    raise RuntimeError(result)
                value = score(result,reference)
                accepted = value<=values[walker] or rng.random()<np.exp(min(0,(values[walker]-value)/temperatures[walker]))
                if accepted:
                    states[walker], values[walker] = candidate['placements_mm'],value
                if value < best_value:
                    best,best_value = candidate['placements_mm'],value
                    write_json(a.output/'submission.json',candidate)
                    print(f'BEST {count+1}: {value:.8f} GPU={result["gpu"]:.2f} HBM={result["hbm"]:.2f}',flush=True)
                record = {'evaluation':count,'walker':walker,'submission':candidate,'screen_score':value,
                          'accepted':bool(accepted),'elapsed_seconds':round(time.monotonic()-started,2),**compact(result)}
                log.write(json.dumps(record)+'\n'); log.flush()
                archive.append(vector(candidate['placements_mm']))
                archive = archive[-1000:]
                count += 1
            # Periodically reseed the coldest walker; warmer walkers retain exploration.
            if count % (a.walkers*10) < a.parallel:
                states[0],values[0] = best,best_value
            write_json(a.output/'summary.json',{'kind':'screening; verify all workloads with pinned judge',
                        'evaluations':count,'proposals':attempts,'best_score':best_value,
                        'elapsed_seconds':round(time.monotonic()-started,2)})
            if count % 40 < a.parallel:
                print(f'{count}/{a.evals}: best={best_value:.8f}',flush=True)


if __name__ == '__main__':
    main()
