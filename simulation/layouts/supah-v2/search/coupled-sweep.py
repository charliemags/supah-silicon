import sys,json,time
from pathlib import Path
sys.path.insert(0,'simulation/tools')
import fast
from optimize import write_json,compact,score
root=Path('simulation/experiments/coupled-sweep')
seed=json.loads(Path('simulation/experiments/finalists/tied-screen.json').read_text())['placements_mm']
ref={'gpu':fast.REF64['worst_gpu_c'],'hbm':fast.REF64['worst_hbm_c']}
best=2
with (root/'search.jsonl').open('w') as log:
 for group in [['G0','H0'],['G0','H0','H3','G3']]:
  for dx in [-0.4,0,0.4]:
   for dy in [-0.328,0.328,0.656,0.984,1.312]:
    lay={k:list(v) for k,v in seed.items()}
    for d in group: lay[d]=[round(lay[d][0]+dx,3),round(lay[d][1]+dy,3)]
    if not fast.legal(lay)[0]:continue
    r=fast.estimate(lay,64,workers=3,workloads=['skewed_compute','tensor_training','memory_stream'])
    v=score(r,ref);rec={'submission':{'placements_mm':lay},'screen_score':v,'group':group,'delta':[dx,dy],**compact(r)}
    log.write(json.dumps(rec)+'\n');log.flush()
    if v<best:best=v;write_json(root/'submission.json',rec['submission'])
    print(group,dx,dy,v,r['gpu'],r['hbm'],flush=True)
