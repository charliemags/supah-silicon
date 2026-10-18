import json,sys,itertools,time,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'simulation/tools')
import fast
from optimize import score,compact,write_json
out=Path('simulation/experiments/translation-sweep')
source=Path('simulation/experiments/finalists/population.json');base=json.loads(source.read_text())['placements_mm']
values=[0.,-.5,.5,-1.,1.,-1.5,1.5]
candidates=[]
for x,y in itertools.product(values,repeat=2):
 lay={d:[round(v[0]+x,3),round(v[1]+y,3)] for d,v in base.items()}
 if fast.legal(lay)[0]:candidates.append((x,y,lay))
write_json(out/'experiment.json',{'kind':'native screen; rigid translations on 0.5 mm routing pitch','grid':64,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'hotspot_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
print('Legal translations:',len(candidates),flush=True)
ref={'gpu':104.59,'hbm':97.68};best=float('inf');start=time.monotonic()
with ThreadPoolExecutor(max_workers=2) as pool,(out/'search.jsonl').open('w') as log:
 def evaluate(c):return compact(fast.estimate(c[2],64,workers=3,workloads=['skewed_compute','tensor_training','memory_stream']))
 for i,(candidate,result) in enumerate(zip(candidates,pool.map(evaluate,candidates))):
  value=score(result,ref);sub={'placements_mm':candidate[2]}
  r={'evaluation':i,'offset_mm':candidate[:2],'submission':sub,'screen_score':value,**result}
  log.write(json.dumps(r)+'\n');log.flush()
  if value<best:
   best=value;write_json(out/'submission.json',sub);print('BEST',candidate[:2],value,flush=True)
write_json(out/'summary.json',{'evaluations':len(candidates),'best_score':best,'elapsed_seconds':round(time.monotonic()-start,2)})
