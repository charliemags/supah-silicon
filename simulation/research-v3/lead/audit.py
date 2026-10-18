"""Regenerate compact evidence accounting; never infer an official result."""
import collections
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
RESEARCH=ROOT/'simulation/research-v3'
def read(path): return json.loads(path.read_text())
def rows(path): return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

session=read(RESEARCH/'lead/session.json')
integrity={name:sha(ROOT/name)==digest for name,digest in session['incumbent_files'].items()}
if not all(integrity.values()): raise ValueError('Incumbent changed')
summary={'incumbent_unchanged':integrity,'official_new_submission':False,
         'paid_compute_used':False,'calibration':{},'experiments':{}}
for grid in (64,128):
    native=read(RESEARCH/f'physics/incumbent-{grid}/diagnostic.json')
    pinned=read(ROOT/f'simulation/layouts/supah-v2/verification-{grid}.json')
    errors=[]
    for workload,data in native['workloads'].items():
        for die,peak in data['per_die'].items():
            errors.append(peak['temperature_c']-pinned['workloads'][workload]['per_die_peak_c'][die])
    summary['calibration'][str(grid)]={'compared_die_workload_peaks':len(errors),
        'maximum_absolute_error_c':round(max(map(abs,errors)),8),
        'minimum_signed_error_c':round(min(errors),8),'maximum_signed_error_c':round(max(errors),8),
        'native_solver_sha256':native['solver_sha256'],
        'pinned_solver_sha256':pinned['hotspot_sha256']}

for name,rel in [('population_control','lead/control-population'),
                 ('inverted_refinement','lead/inverted-refinement'),
                 ('epigraph_all_stages','math/epigraph-fixed-64')]:
    data=rows(RESEARCH/rel/'search.jsonl')
    summary['experiments'][name]={'evaluations':len(data),
        'best_native_score':min(r['screen_score'] for r in data),
        'record_kinds':dict(collections.Counter(r.get('kind','population') for r in data))}
summary['experiments']['packaging']=read(RESEARCH/'packaging/summary.json')
data=rows(RESEARCH/'lead/coupling-sweep/results.jsonl')
summary['experiments']['coupling_sweep']={'proposals':len(data),
    'evaluations':sum(r['valid'] for r in data),
    'best_native_score':min(r['screen_score'] for r in data if r['valid'])}
data=rows(RESEARCH/'lead/robustness-control-hbm/results.jsonl')
valid=[r for r in data if r['validation']['passed']]
summary['robustness']={'proposals_completed':len(data),'exact_valid':len(valid),'grids':{}}
for grid in ('64','128'):
    base=next(r for r in valid if r['name']=='unperturbed')['results'][grid]
    pert=[r['results'][grid] for r in valid if r['name']!='unperturbed']
    summary['robustness']['grids'][grid]={
        'base_gpu_c':base['gpu'],'base_hbm_c':base['hbm'],
        'perturbed_gpu_range_c':[min(r['gpu'] for r in pert),max(r['gpu'] for r in pert)],
        'perturbed_hbm_range_c':[min(r['hbm'] for r in pert),max(r['hbm'] for r in pert)],
        'better_primary_score_count':sum(r['screen_score']<base['screen_score'] for r in pert)}
summary['finalist']={}
for grid in (64,128):
    path=RESEARCH/f'lead/finalists/control-hbm/verification-{grid}.json'
    if path.exists():
        result=read(path)
        summary['finalist'][str(grid)]={k:result[k] for k in
            ('passed','grid','score','worst_gpu_c','worst_hbm_c','hotspot_sha256')}
summary['finalist']['submission_sha256']=sha(RESEARCH/'lead/finalists/control-hbm/submission.json')
out=RESEARCH/'lead/audit.json'
out.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ('calibration','robustness','finalist')},indent=2))
