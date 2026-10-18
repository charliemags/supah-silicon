#!/usr/bin/env python3
"""Exact packaging slack, distinct C8 packings, and power-neutral routing experiments."""
import argparse, collections, hashlib, itertools, json, math, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
CHALLENGE=Path('/challenge') if Path('/challenge/challenge_spec.json').exists() else ROOT/'.cache/challenge'
sys.path.insert(0,str(CHALLENGE))
from geometry import die_box,validate_layout
from verify_submission import verify
SPEC=json.loads((CHALLENGE/'challenge_spec.json').read_text())
BASE=json.loads((ROOT/'simulation/layouts/supah-v2/submission.json').read_text())

def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')

def alternatives(layout,route):
 boxes=[die_box(SPEC,layout,d) for d in layout]
 start=tuple(route['path_grid'][0]); end=tuple(route['path_grid'][-1]); length=len(route['path_grid'])-1
 def blocked(c):
  x,y=(c[0]+.5)*.5,(c[1]+.5)*.5
  return any(x0-.2<x<x1+.2 and y0-.2<y<y1+.2 for x0,y0,x1,y1 in boxes)
 paths=[]
 def visit(p):
  c=p[-1];rem=length-len(p)+1
  dist=abs(c[0]-end[0])+abs(c[1]-end[1])
  if dist>rem:return
  if rem==0:
   if c==end:paths.append([list(a) for a in p])
   return
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
   n=c[0]+dx,c[1]+dy
   if n not in p and 0<=n[0]<104 and 0<=n[1]<84 and not blocked(n):visit(p+[n])
 visit([start]);return paths

def prepare():
 layout=BASE['placements_mm'];routing=validate_layout(SPEC,layout)
 boxes={d:die_box(SPEC,layout,d) for d in layout}
 pairs=[]
 for (a,A),(b,B) in itertools.combinations(boxes.items(),2):
  gx=max(B[0]-A[2],A[0]-B[2],0);gy=max(B[1]-A[3],A[1]-B[3],0)
  pairs.append({'dies':[a,b],'clearance_mm':round(max(gx,gy),6),'slack_mm':round(max(gx,gy)-1,6)})
 links={k:{'length_mm':v['route_length_mm'],'slack_mm':round(v['limit_mm']-v['route_length_mm'],6),'port_manhattan_mm':round(sum(abs(a-b) for a,b in zip(v['from_port'],v['to_port'])),6)} for k,v in routing['routes'].items()}
 power={w:{'wire_w':round(sum(.00064*link['gb_s']*s['link_utilization'][link['id']]*routing['routes'][link['id']]['route_length_mm'] for link in SPEC['links']),6),'phy_w':round(sum(.0016*link['gb_s']*s['link_utilization'][link['id']] for link in SPEC['links']),6)} for w,s in SPEC['workloads'].items()}
 data={'incumbent_sha256':hashlib.sha256((ROOT/'simulation/layouts/supah-v2/submission.json').read_bytes()).hexdigest(),'exact_validation':verify(ROOT/'simulation/layouts/supah-v2/submission.json'),'route_slack':links,'weighted_route_slack':13500-routing['weighted_route_gb_s_mm'],'pair_clearances':sorted(pairs,key=lambda p:p['slack_mm']),'interconnect_watts':power}
 alts={k:alternatives(layout,v) for k,v in routing['routes'].items()}
 data['shortest_route_counts']={k:len(v) for k,v in alts.items()}
 write(OUT/'incumbent-analysis.json',data)
 records=[]
 def save(name,sub,kind,**meta):
  p=OUT/'candidates'/name/'submission.json';write(p,sub);result=verify(p)
  rec={'name':name,'family':kind,'submission':sub,'validation':result,**meta};records.append(rec)
  write(p.parent/'validation.json',result)
 save('incumbent',BASE,'control')
 # Explicitly distinct 4-column/two-row cycle; sizes never rotated. Every relabeling retained.
 sites=[(0,0),(1,0),(2,0),(3,0),(3,1),(2,1),(1,1),(0,1)]
 cycle=['G0','H0','G1','H1','G2','H2','G3','H3']
 for flip,shift,dy,dx in itertools.product([False,True],range(8),[12.5,14.5],[-.75,.75]):
  lay={}
  for i,(col,row) in enumerate(sites):
   die=cycle[((-i if flip else i)+shift)%8];w,h=SPEC['dies'][die]['size_mm']
   lay[die]=[round(8+12*col+dx-w/2,6),round(21+(row-.5)*dy-h/2,6)]
  save(f'flat-f{int(flip)}-r{shift}-dy{dy}-dx{dx}',{'placements_mm':lay},'4x2-cycle',flip=flip,cycle_shift=shift,row_separation=dy,x_shift=dx)
 # Representative S0 shortest paths chosen uniformly from deterministic enumeration.
 for link,paths in alts.items():
  if len(paths)<=1:continue
  inds=sorted(set(round(i*(len(paths)-1)/min(19,len(paths)-1)) for i in range(min(20,len(paths)))))
  for index in inds:
   if paths[index]==routing['routes'][link]['path_grid']:continue
   save(f'route-{link}-{index}',{'placements_mm':layout,'wire_routes_grid':{link:paths[index]}},'equal-length-route',link=link,index=index)
 write(OUT/'candidate-manifest.json',records)
 print(json.dumps({'prepared':len(records),'valid':sum(r['validation']['passed'] for r in records),'route_counts':data['shortest_route_counts'],'slack':links},indent=2),flush=True)

def screen():
 sys.path.insert(0,str(ROOT/'simulation/tools'));import fast
 records=json.loads((OUT/'candidate-manifest.json').read_text());results=[];start=time.monotonic()
 manifest={'solver':str(fast.HOTSPOT),'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'grid':64,'workloads':'all five','purpose':'native screening; not pinned certification'}
 write(OUT/'screen-manifest.json',manifest)
 with (OUT/'screen-results.jsonl').open('w') as f:
  for i,r in enumerate(records):
   if not r['validation']['passed']:continue
   before=time.monotonic();sub=r['submission']
   est=fast.estimate(sub['placements_mm'],64,workers=2,paths=sub.get('wire_routes_grid',{}))
   est.pop('grids',None)
   rec={'name':r['name'],'family':r['family'],'elapsed_seconds':time.monotonic()-before,'result':est}
   f.write(json.dumps(rec)+'\n');f.flush();results.append(rec)
   print(r['name'],est.get('gpu'),est.get('hbm'),round(rec['elapsed_seconds'],2),flush=True)
 write(OUT/'screen-summary.json',{'elapsed_seconds':time.monotonic()-start,'evaluations':len(results)})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','screen']);a=p.parse_args()
 {'prepare':prepare,'screen':screen}[a.action]()
