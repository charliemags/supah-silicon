"""Summarize actual native global-search results, including G0 Pareto seeds."""
import hashlib,json,math
from pathlib import Path
D=Path(__file__).resolve().parent;rows=[];runs={}
for p in D.glob('*/search.jsonl'):
    rs=[json.loads(s) for s in p.read_text().splitlines()]
    runs[p.parent.name]={'screens':len(rs),'counts_by_grid':{str(g):sum(r['grid']==g for r in rs) for g in sorted({r['grid'] for r in rs})},'log_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    for r in rs:
        r=dict(r,run=p.parent.name)
        if r['grid'] != 64:continue
        raw=r['raw_peaks_c'];r['g0_c']=raw['skewed_compute']['G0']
        r['other_equivalent_c']=max(25+(t-25)*79.59/(79.59 if d.startswith('G') else 72.68) for w,ps in raw.items() for d,t in ps.items() if (w,d)!=('skewed_compute','G0'))
        r['overall_equivalent_c']=max(r['g0_c'],r['other_equivalent_c'])
        rows.append(r)
if not rows:raise SystemExit('No simulations found')
base=json.loads((D.parents[1]/'research-v5/submission.json').read_text())['placements_mm']
for r in rows:r['max_die_displacement_from_v5_mm']=max(math.hypot(p[0]-base[d][0],p[1]-base[d][1]) for d,p in r['submission']['placements_mm'].items())
pareto=[];minimum=math.inf;seen=set()
for r in sorted(rows,key=lambda r:(r['g0_c'],r['other_equivalent_c'])):
    k=json.dumps(r['submission'],sort_keys=True)
    if k in seen:continue
    seen.add(k)
    if r['other_equivalent_c']<minimum:
        pareto.append(r);minimum=r['other_equivalent_c']
best=min(rows,key=lambda r:r['overall_equivalent_c']);g0=min(rows,key=lambda r:r['g0_c'])
seed_dir=D/'pareto-seeds';seed_dir.mkdir(exist_ok=True)
for i,r in enumerate(pareto):(seed_dir/f'{i:03d}.json').write_text(json.dumps(r['submission'],indent=2)+'\n')
report={'kind':'native screening only; pinned verification is required','runs':runs,'screens':sum(r['screens'] for r in runs.values()),'grid64_screens':len(rows),'grid64_unique_submissions':len(seen),
 'best_overall':best,'lowest_g0':g0,'pareto_front':pareto,'max_die_displacement_from_v5_mm':max(r['max_die_displacement_from_v5_mm'] for r in rows)}
(D/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['best_overall','lowest_g0','pareto_front']},indent=2))
print('Best',best['run'],best['evaluation'],best['overall_equivalent_c'],'G0 minimum',g0['run'],g0['evaluation'],g0['g0_c'],'other',g0['other_equivalent_c'],'Pareto seeds',len(pareto))
