"""Fixed-layout source attribution. Diagnostic sources are never valid challenge runs."""
import argparse, copy, hashlib, json, os, sys, time, subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
HILL=Path(os.environ.get('CRYO_HILL', str(ROOT/'.cache/challenge')))
sys.path.insert(0,str(HILL))
from geometry import validate_layout, die_box
from generate_workloads import generate
from run_simulations import create_hotspot_files, parse_grid, die_peaks
from interconnect import combined_heat

def main():
 p=argparse.ArgumentParser();p.add_argument('--grid',type=int,default=64);p.add_argument('--hotspot',default=os.environ.get('CRYO_HOTSPOT','/opt/hotspot/hotspot'));p.add_argument('--output',type=Path,required=True);p.add_argument('--submission',type=Path,default=ROOT/'simulation/layouts/supah-v2/submission.json');p.add_argument('--workers',type=int,default=3);p.add_argument('--full-only',action='store_true');a=p.parse_args()
 start=time.monotonic(); spec=json.loads((HILL/'challenge_spec.json').read_text());sub=json.loads(a.submission.read_text());layout=sub['placements_mm'];routing=validate_layout(spec,layout,wire_routes_grid=sub.get('wire_routes_grid',{}));portable=generate(spec)
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);rd=out/'inputs';vendor=HILL/'vendor/HotSpot';budgets=create_hotspot_files(spec,portable,layout,routing,rd,a.grid,vendor)
 tasks=[(w,'full',w) for w in portable['workloads']]
 crit=['skewed_compute','tensor_training','memory_stream']
 if not a.full_only:
  n=spec['power_pixels_per_die_side'];no_wire_spec=copy.deepcopy(spec);no_wire_spec['interconnect_model']['wire_energy_pj_per_bit_per_mm']=0
  for w in crit:
   names,values=(rd/f'{w}.ptrace').read_text().splitlines();names=names.split();values=np.array(list(map(float,values.split())))
   phy=combined_heat(no_wire_spec,w,portable['workloads'][w]['power_maps_w'],layout,routing)
   groups={d:np.zeros(len(names)) for d in layout};groups['PHY']=np.zeros(len(names));groups['wire']=np.zeros(len(names))
   for k,name in enumerate(names):
    if name.startswith('ip_'):
     _,row,col=name.split('_');j,i=int(row[1:]),int(col[1:]);groups['PHY'][k]=phy['interposer_tiles_w'][j,i];groups['wire'][k]=values[k]-groups['PHY'][k]
    elif name[:2] in layout:
     d,row,col=name.split('_');j,i=int(row[1:]),int(col[1:]);groups[d][k]=portable['workloads'][w]['power_maps_w'][d][j][i];groups['PHY'][k]=values[k]-groups[d][k]
   assert np.max(np.abs(sum(groups.values())-values))<1e-7
   for g,q in groups.items():
    tag=f'{w}__{g}';(rd/f'{tag}.ptrace').write_text('\t'.join(names)+'\n'+'\t'.join(f'{v:.12g}' for v in q)+'\n');tasks.append((w,g,tag))
 def solve(task):
  w,g,tag=task;args=[str(Path(a.hotspot).resolve()),'-c','benchmark.config','-f','chiplets.flp','-p',f'{tag}.ptrace','-materials_file',str(vendor/'examples/example3/example.materials'),'-model_type','grid','-detailed_3D','on','-grid_layer_file','stack.lcf','-grid_steady_file',f'{tag}.grid','-steady_file',f'{tag}.steady'];t=time.monotonic();r=subprocess.run(args,cwd=rd,text=True,capture_output=True,timeout=1800)
  if r.returncode: raise RuntimeError(r.stderr[-2000:])
  return w,g,parse_grid(rd/f'{tag}.grid',a.grid),time.monotonic()-t
 with ThreadPoolExecutor(max_workers=a.workers) as pool: results=list(pool.map(solve,tasks))
 grids={(w,g):arr for w,g,arr,_ in results};summary={'kind':'native solver diagnostic; altered sources are attribution only, never challenge scores','grid':a.grid,'solver_sha256':hashlib.sha256(Path(a.hotspot).read_bytes()).hexdigest(),'submission_sha256':hashlib.sha256(a.submission.read_bytes()).hexdigest(),'power_budget':budgets,'workloads':{},'total_seconds':time.monotonic()-start,'sum_workload_seconds':sum(t for *_,t in results),'source_solve_count':len(results)}
 W,H=spec['interposer_mm'];xx=(np.arange(a.grid)+.5)*W/a.grid;yy=H-(np.arange(a.grid)+.5)*H/a.grid
 for w in portable['workloads']:
  full=grids[w,'full'];peaks={}
  for d in layout:
   x0,y0,x1,y1=die_box(spec,layout,d);mask=((xx[None,:]>=x0)&(xx[None,:]<x1)&(yy[:,None]>=y0)&(yy[:,None]<y1));idx=np.unravel_index(np.argmax(np.where(mask,full,-np.inf)),full.shape)
   r={'temperature_c':float(full[idx]),'xy_mm':[float(xx[idx[1]]),float(yy[idx[0]])],'thermal_row_col':list(map(int,idx)),'die_relative_xy':[(float(xx[idx[1]])-x0)/(x1-x0),(float(yy[idx[0]])-y0)/(y1-y0)]}
   if w in crit and not a.full_only:
    r['source_rise_c']={g:float(grids[w,g][idx]-25) for g in [*layout,'PHY','wire']};r['superposition_residual_c']=float(full[idx]-25-sum(r['source_rise_c'].values()))
   peaks[d]=r
  summary['workloads'][w]={'per_die':peaks,'peaks_rounded_c':die_peaks(spec,layout,full)}
 (out/'diagnostic.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'output':str(out/'diagnostic.json'),'seconds':summary['total_seconds'],'solves':len(results)}))
if __name__=='__main__':main()
