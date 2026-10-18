import sys,json,itertools,time,hashlib
from pathlib import Path
sys.path.insert(0,'simulation/tools')
import fast
from optimize import compact,score,write_json,key
from concurrent.futures import ThreadPoolExecutor
out=Path('simulation/experiments/topology')
starts=[json.loads(Path(p).read_text())['placements_mm'] for p in ['simulation/experiments/finalists/per-die.json','simulation/layouts/supah-v1/submission.json']]
starts.extend(fast.SPEC['example_layouts_mm'].values())
seen=set();candidates=[]
for seed,base in enumerate(starts):
 for rotate,reflect in itertools.product(range(4),[False,True]):
  lay={}
  for i in range(4):
   j=(-i+rotate)%4 if reflect else (i+rotate)%4
   k=(-i+rotate-1)%4 if reflect else (i+rotate)%4
   lay[f'G{i}']=base[f'G{j}']
   lay[f'H{i}']=base[f'H{k}']
  sub={'placements_mm':lay}; ident=key(sub)
  if ident not in seen and fast.legal(lay)[0]:
   seen.add(ident);candidates.append((seed,rotate,reflect,sub))
print('Legal arrangements',len(candidates),flush=True)
ref={'gpu':104.59,'hbm':97.68};best=float('inf');start=time.monotonic()
write_json(out/'experiment.json',{'kind':'native screen; topology survey','grid':64,'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
with ThreadPoolExecutor(max_workers=2) as pool,(out/'search.jsonl').open('w') as log:
 def run(item):return compact(fast.estimate(item[3]['placements_mm'],64,workers=3,workloads=['skewed_compute','tensor_training','memory_stream']))
 for i,(item,r) in enumerate(zip(candidates,pool.map(run,candidates))):
  s=score(r,ref);record={'evaluation':i,'seed':item[0],'rotate':item[1],'reflect':item[2],'submission':item[3],'screen_score':s,**r}
  log.write(json.dumps(record)+'\n');log.flush()
  print(item[:3],s,r['gpu'],r['hbm'],flush=True)
  if s<best:best=s;write_json(out/'submission.json',item[3])
write_json(out/'summary.json',{'evaluations':len(candidates),'best_score':best,'elapsed_seconds':round(time.monotonic()-start,2)})
