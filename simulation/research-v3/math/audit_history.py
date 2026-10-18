"""Reproduce historical minimax audit without running any thermal solver."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
HISTORY=ROOT/'layouts/supah-v2/search'
OUT=Path(__file__).parent/'history-audit.json'
records=[]
for path in sorted(HISTORY.rglob('*.jsonl')):
 for line_number,line in enumerate(path.read_text().splitlines(),1):
  try:r=json.loads(line)
  except json.JSONDecodeError:continue
  if r.get('passed') and r.get('grid')==64 and 'peaks' in r and 'submission' in r:
   records.append((str(path.relative_to(ROOT)),line_number,r))
unique={json.dumps(r['submission'],sort_keys=True):(p,i,r)for p,i,r in records}
rows=list(unique.values());near=[row for row in rows if row[2]['screen_score']<.961]
inc=json.loads((ROOT/'layouts/supah-v2/verification-64.json').read_text())
active=[]
for w,data in inc['workloads'].items():
 for d,temp in data['per_die_peak_c'].items():
  denom=79.59 if d.startswith('G') else 72.68
  active.append({'workload':w,'die':d,'temperature_c':temp,'normalized_rise':(temp-25)/denom,'reduction_to_095_c':max(0,temp-(100.61 if d.startswith('G')else 94.04))})
best=min(rows,key=lambda r:r[2]['screen_score'])
report={'note':'Historical screening records, not independently rerun or signed results; unique identity is exact submission JSON. Reused history records inflate raw count.',
 'valid64_records':len(records),'unique_placements':len(rows),'below0961_unique':len(near),
 'best':{'source':best[0],'line':best[1],'score':best[2]['screen_score']},
 'near_elite_coordinate_ranges':{d:[[min(r['submission']['placements_mm'][d][axis]for p,i,r in near),max(r['submission']['placements_mm'][d][axis]for p,i,r in near)]for axis in range(2)]for d in inc['workloads']['tensor_training']['per_die_peak_c']},
 'incumbent_components':sorted(active,key=lambda r:r['normalized_rise'],reverse=True),
 'route_slack_mm':{link:val['max_route_mm']-val['route_length_mm']for link,val in inc['constraints']['links'].items()},
 'weighted_slack':inc['constraints']['route_limit_gb_s_mm']-inc['constraints']['weighted_route_gb_s_mm']}
OUT.write_text(json.dumps(report,indent=2)+'\n');print(OUT)
