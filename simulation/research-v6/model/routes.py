"""Exact-valid v5 equal-shortest-path screens, unchanged thermal/scoring rules."""
import hashlib,json,sys,time,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise')
sys.path.insert(0,str(ROOT/'simulation/tools'));sys.path.insert(0,str(ROOT/'simulation/research-v3/packaging'))
import fast
from explore import alternatives
from optimize import compact
out=ROOT/'simulation/research-v6/model/v5-routes';out.mkdir(exist_ok=False)
initial=json.loads((ROOT/'simulation/research-v5/submission.json').read_text());lay=initial['placements_mm'];routing=fast.legal(lay)[2];records=[];start=time.monotonic();log=(out/'search.jsonl').open('w')
(out/'manifest.json').write_text(json.dumps({'kind':'native screening; original pinned verification required','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'solver_sha256':hashlib.sha256(fast.HOTSPOT.read_bytes()).hexdigest(),'start_sha256':hashlib.sha256((ROOT/'simulation/research-v5/submission.json').read_bytes()).hexdigest(),'equal_path_counts':{k:len(alternatives(lay,r)) for k,r in routing['routes'].items()}},indent=2)+'\n')
def measure(paths,kind,link=None,index=None,workloads=['skewed_compute']):
 sub={'placements_mm':lay}
 if paths:sub['wire_routes_grid']=paths
 ok,reason,_=fast.legal(lay,paths);assert ok,reason
 r=fast.estimate(lay,64,workers=2,workloads=workloads,paths=paths)
 xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64;raw={}
 for w,g in r['grids'].items():
  raw[w]={}
  for d,(x,y) in lay.items():
   sx,sy=fast.SPEC['dies'][d]['size_mm'];raw[w][d]=float(g[np.ix_((yy>=y)&(yy<y+sy),(xx>=x)&(xx<x+sx))].max())
 rec={'submission':sub,**compact(r),'raw_peaks_c':raw,'evaluation':len(records),'kind':kind,'link':link,'path_index':index,'elapsed_seconds':time.monotonic()-start,'screen_score':max((r['gpu']-25)/79.59,(r['hbm']-25)/72.68)}
 records.append(rec);log.write(json.dumps(rec)+'\n');log.flush()
 print('ROUTE',len(records),kind,link,index,'G0',raw['skewed_compute']['G0'],'GPU',r['gpu'],'HBM',r['hbm'],flush=True)
 return rec
control=measure({},'control',workloads=None)
for link,route in routing['routes'].items():
 for i,path in enumerate(alternatives(lay,route)):
  if path!=route['path_grid']:measure({link:path},'single-shortest-route',link,i)
paths={}
for link,route in routing['routes'].items():
 opts=[r for r in records if r['link']==link]
 if opts:
  best=min(opts,key=lambda r:r['raw_peaks_c']['skewed_compute']['G0'])
  if best['raw_peaks_c']['skewed_compute']['G0']<control['raw_peaks_c']['skewed_compute']['G0']:
   paths[link]=best['submission']['wire_routes_grid'][link]
combined=measure(paths,'combined-all-five',workloads=None)
# Always retain the concrete combined candidate and honest comparison, even if tied.
(out/'submission.json').write_text(json.dumps(combined['submission'],indent=2)+'\n')
(out/'summary.json').write_text(json.dumps({'evaluations':len(records),'control_gpu':control['gpu'],'combined_gpu':combined['gpu'],'control_hbm':control['hbm'],'combined_hbm':combined['hbm'],'control_raw_g0':control['raw_peaks_c']['skewed_compute']['G0'],'combined_raw_g0':combined['raw_peaks_c']['skewed_compute']['G0'],'control_score':control['screen_score'],'combined_score':combined['screen_score'],'changed_links':list(paths),'elapsed_seconds':time.monotonic()-start},indent=2)+'\n')
