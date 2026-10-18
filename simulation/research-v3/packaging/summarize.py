"""Summarize all completed exact-valid native screen records without promoting them."""
from explore import *
files=['screen-results.jsonl','inverted-results.jsonl','inverted-wide-results.jsonl','directed-results.jsonl']
rows=[]
for name in files:
 p=OUT/name
 if p.exists():rows.extend(json.loads(line) for line in p.read_text().splitlines())
score=lambda r:max((r['result']['gpu']-25)/79.59,(r['result']['hbm']-25)/72.68)
families={}
for family in sorted({r['family'] for r in rows}):
 selected=[r for r in rows if r['family']==family];best=min(selected,key=score)
 families[family]={'evaluations':len(selected),'native_best_score':score(best),'best_candidate':best['name'],'gpu':best['result']['gpu'],'hbm':best['result']['hbm'],'elapsed_seconds_sum':round(sum(r['elapsed_seconds'] for r in selected),3),'best_power':best['result']['power']}
write(OUT/'summary.json',{'status':'native screening only; all five workloads at64; no new pinned or signed claims','evaluations':len(rows),'families':families})
invalid=[]
for p in (OUT/'candidates').glob('wide-*/validation.json'):
 r=json.loads(p.read_text())
 if not r['passed']:invalid.append({'candidate':p.parent.name,**r})
write(OUT/'inverted-wide-rejected.json',invalid)
print(json.dumps(families,indent=2))
