"""All-workload native screening of mathematician's exact-valid coordinated movement."""
from explore import *
sys.path.insert(0,str(ROOT/'simulation/tools'));import fast
records=json.loads((OUT.parent/'math/directed-legal-seeds.json').read_text())['candidates']
with (OUT/'directed-results.jsonl').open('w') as f:
 for i,r in enumerate(records):
  name=f'directed-{i}';p=OUT/'candidates'/name/'submission.json';write(p,r['submission']);validation=verify(p);write(p.parent/'validation.json',validation)
  if not validation['passed']:raise ValueError(validation)
  start=time.monotonic();est=fast.estimate(r['submission']['placements_mm'],64,workers=2);est.pop('grids',None)
  rec={'name':name,'family':'directed-math','elapsed_seconds':time.monotonic()-start,'result':est,'parameters':{k:v for k,v in r.items() if k!='submission'}}
  f.write(json.dumps(rec)+'\n');f.flush();print(name,est['gpu'],est['hbm'],flush=True)
