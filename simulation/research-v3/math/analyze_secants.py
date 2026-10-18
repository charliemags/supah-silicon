"""Summarize exact controlled one-die perturbations; no thermal solves."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('experiment',type=Path);a=p.parse_args()
rows=[json.loads(line)for line in (a.experiment/'search.jsonl').read_text().splitlines()];base=rows[0];dies=list(base['submission']['placements_mm']);data=[]
for r in rows:
 if r['kind']!='coordinate_secant':continue
 j,h=r['coordinate'],r['step'];deltas={w:{d:round(t-base['peaks'][w][d],5)for d,t in peaks.items()}for w,peaks in r['peaks'].items()}
 slopes={w:{d:round(t/h,5)for d,t in peaks.items()}for w,peaks in deltas.items()}
 data.append({'evaluation':r['evaluation'],'die':dies[j//2],'axis':'xy'[j%2],'step_mm':h,'peak_delta_c':deltas,'secant_c_per_mm':slopes,'rounding_only_error_bound_c_per_mm':.01/abs(h),'score':r['screen_score']})
out={'note':'Per-die peaks are rounded to .01C; secant worst-case error from two rounded endpoints is .01/abs(h). Solver and grid discrepancies add uncertainty beyond this bound. Invalid perturbations were skipped, so these are feasible one-sided samples, not necessarily central derivatives.','baseline_evaluation':0,'evaluations_observed':len(rows),'controlled_perturbations':data}
(a.experiment/'secant-analysis.json').write_text(json.dumps(out,indent=2)+'\n');print('observed',len(rows),'controlled',len(data))
