"""Rank valid topology seeds using the unchanged 64-grid skewed workload."""
import argparse,json,sys,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];os.environ['CRYO_HOTSPOT']=str(ROOT/'.cache/hotspot-precise');sys.path.insert(0,str(ROOT/'simulation/tools'))
import numpy as np
import fast
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();start=time.monotonic();report=a.directory/'skewed-screen.json';rows=json.loads(report.read_text()) if report.exists() else []
seen={r['path'] for r in rows}
for path in sorted(a.directory.glob('seed-*.json')):
 if str(path) in seen:continue
 sub=json.loads(path.read_text());r=fast.estimate(sub['placements_mm'],64,workers=1,workloads=['skewed_compute']);g=r.pop('grids')['skewed_compute'];xx=(np.arange(64)+.5)*52/64;yy=42-(np.arange(64)+.5)*42/64
 x,y=sub['placements_mm']['G0'];raw=float(g[np.ix_((yy>=y)&(yy<y+10.5),(xx>=x)&(xx<x+11.5))].max())
 row={'path':str(path),'submission':sub,**r,'raw_g0':raw,'elapsed_seconds':time.monotonic()-start};rows.append(row)
 print(path.name,'G0',raw,'GPU',r['gpu'],'HBM',r['hbm'],flush=True)
 (a.directory/'skewed-screen.json').write_text(json.dumps(sorted(rows,key=lambda r:r['raw_g0']),indent=2)+'\n')
