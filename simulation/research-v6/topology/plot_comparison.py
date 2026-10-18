"""Static comparison of recorded native64 screens; no simulations performed."""
import hashlib,json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Patch
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'.cache/challenge'))
from geometry import validate_layout
spec=json.loads((ROOT/'.cache/challenge/challenge_spec.json').read_text())
base=json.loads((ROOT/'simulation/research-v5/submission.json').read_text())
baseline_log=ROOT/'simulation/research-v6/global/population-1600/search.jsonl'
baseline=next(json.loads(line) for line in baseline_log.read_text().splitlines()
              if json.loads(line).get('submission')==base)
overall=json.loads((OUT/'best-minimax/observation.json').read_text())
coupling=json.loads((OUT/'best-g0/observation.json').read_text())
assert coupling['submission']==json.loads((ROOT/'simulation/research-v6/model/g0-isolation/seed-0020.json').read_text())
assert baseline['submission']['placements_mm']['G0']==coupling['submission']['placements_mm']['G0']
rows=[baseline,overall,coupling]
titles=['Preserved v5 candidate','Best new overall topology','Lower-G0 topology · seed0020']
workloads=['tensor_training','skewed_compute','memory_stream']
for r in rows:
    assert r['grid']==64 and set(r['peaks'])==set(workloads)
data={'kind':'native64 screening; three workloads only; not pinned verification',
      'baseline_source':str(baseline_log.relative_to(ROOT)),
      'workloads':workloads,'cooling_contact_rect_mm':spec['thermal_model']['cooling_contact_rect_mm'],
      'interposer_mm':spec['interposer_mm'],'dies':{d:spec['dies'][d]['size_mm'] for d in spec['dies']},
      'panels':[{'title':title,'submission':r['submission'],'score':r['screen_score'],
                 'gpu_c':r['gpu'],'hbm_c':r['hbm'],
                 'g0_skewed_c':r['raw_peaks_c']['skewed_compute']['G0']} for title,r in zip(titles,rows)]}
(OUT/'placement-comparison-data.json').write_text(json.dumps(data,indent=2)+'\n')

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':13,
                     'axes.labelcolor':'#334155','text.color':'#172033','xtick.color':'#64748B','ytick.color':'#64748B'})
fig,axes=plt.subplots(1,3,figsize=(15.6,6.9))
fig.patch.set_facecolor('white')
fig.subplots_adjust(left=.045,right=.985,bottom=.20,top=.75,wspace=.14)
fig.text(.045,.955,'Different topologies shift heat, but raise the overall score',fontsize=18,fontweight='bold')
fig.text(.045,.908,'Native 64-grid screening · three workloads · lower score is better · not pinned evaluation',fontsize=11,color='#526174')
W,H=spec['interposer_mm'];cx,cy,cw,ch=spec['thermal_model']['cooling_contact_rect_mm']
for ax,title,r in zip(axes,titles,rows):
    lay=r['submission']['placements_mm'];routing=validate_layout(spec,lay)
    ax.add_patch(Rectangle((0,0),W,H,facecolor='#F1F3F6',edgecolor='#526174',linewidth=1.15))
    ax.add_patch(Rectangle((cx,cy),cw,ch,facecolor='#E7F3ED',edgecolor='#2B8867',linewidth=1.3,linestyle=(0,(4,3))))
    for route in routing['routes'].values():
        pts=[route['from_port']]+[[.5*x+.25,.5*y+.25] for x,y in route['path_grid']]+[route['to_port']]
        ax.plot([p[0] for p in pts],[p[1] for p in pts],color='#556777',linewidth=1.15,zorder=2)
    for d,(x,y) in lay.items():
        w,h=spec['dies'][d]['size_mm'];gpu=d.startswith('G')
        ax.add_patch(Rectangle((x,y),w,h,facecolor='#3776B8' if gpu else '#D58A38',
            edgecolor='#0B4B3E' if d=='G0' else 'white',linewidth=2.4 if d=='G0' else 1.1,zorder=3))
        ax.text(x+w/2,y+h/2,d,ha='center',va='center',color='white',fontweight='bold',fontsize=12,zorder=4)
    ax.set(xlim=(-.5,W+.5),ylim=(-.5,H+.5),aspect='equal',xlabel='x (mm)')
    ax.set_xticks([0,10,20,30,40,52]);ax.set_yticks([0,10,20,30,42])
    ax.tick_params(length=3,labelsize=9)
    for spine in ax.spines.values():spine.set_visible(False)
    ax.text(0,1.24,title,transform=ax.transAxes,fontsize=12.5,fontweight='bold')
    ax.text(0,1.13,f"Score {r['screen_score']:.8f}",transform=ax.transAxes,fontsize=14,fontweight='bold')
    ax.text(0,1.045,f"GPU {r['gpu']:.2f}°C  ·  HBM {r['hbm']:.2f}°C",transform=ax.transAxes,fontsize=11)
    g0=r['raw_peaks_c']['skewed_compute']['G0']
    ax.text(0,-.19,f'G0 in skewed compute: {g0:.3f}°C',transform=ax.transAxes,fontsize=11,color='#124F43',fontweight='bold')
axes[0].set_ylabel('y (mm)')
axes[2].text(0,-.26,'G0 location is identical to preserved v5.',transform=axes[2].transAxes,fontsize=9.5,color='#526174')
legend=[Patch(facecolor='#3776B8',label='GPU 11.5 × 10.5 mm'),Patch(facecolor='#D58A38',label='HBM 10.5 × 10.2 mm'),
        Patch(facecolor='#E7F3ED',edgecolor='#2B8867',linestyle='--',label='Cooling contact 44 × 34 mm'),
        Line2D([0],[0],color='#556777',lw=1.5,label='Validated route')]
fig.legend(handles=legend,loc='lower center',bbox_to_anchor=(.5,.025),ncol=4,frameon=False,fontsize=10)
fig.text(.045,.01,'Package: 52 × 42 mm. Peaks and scores use tensor training, skewed compute, and memory stream.',fontsize=9,color='#64748B')
fig.savefig(OUT/'placement-comparison.png',dpi=180,facecolor='white')
plt.close(fig)
print(json.dumps({'image':str(OUT/'placement-comparison.png'),'size_pixels':[2808,1242],'panels':data['panels']},indent=2))
