"""Wider ring with independently displaced side GPUs, preserving fixed die orientations."""
from explore import *
cycle=['G0','H0','G1','H1','G2','H2','G3','H3']
sites=[(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1)]
records=[]
for flip,shift,side_dx,dy in itertools.product([False,True],range(0,8,2),[16,16.25],[11.5,11.75]):
 lay={}
 for i,(col,row) in enumerate(sites):
  die=cycle[((-i if flip else i)+shift)%8];w,h=SPEC['dies'][die]['size_mm']
  # HBMs remain at15.5mm halfspan: primary horizontal links cannot allow>16mm.
  dx=side_dx if row==0 else 15.5
  lay[die]=[round(26+dx*col-w/2,6),round(21+dy*row-h/2,6)]
 name=f'wide-f{int(flip)}-r{shift}-dx{side_dx}-dy{dy}'
 sub={'placements_mm':lay};p=OUT/'candidates'/name/'submission.json';write(p,sub)
 result=verify(p);write(p.parent/'validation.json',result)
 records.append({'name':name,'family':'wide-inverted-ring','submission':sub,'validation':result})
write(OUT/'inverted-wide-manifest.json',records)
print('wide',len(records),'valid',sum(r['validation']['passed'] for r in records),flush=True)
if len(sys.argv)>1 and sys.argv[1]=='screen':
 sys.path.insert(0,str(ROOT/'simulation/tools'));import fast
 with (OUT/'inverted-wide-results.jsonl').open('w') as f:
  for r in records:
   if not r['validation']['passed']:continue
   start=time.monotonic();est=fast.estimate(r['submission']['placements_mm'],64,workers=2);est.pop('grids',None)
   rec={'name':r['name'],'family':r['family'],'elapsed_seconds':time.monotonic()-start,'result':est}
   f.write(json.dumps(rec)+'\n');f.flush();print(r['name'],est['gpu'],est['hbm'],flush=True)
