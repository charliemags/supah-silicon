"""Reproduce the incumbent physics figure from retained source diagnostics."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=json.loads((ROOT/'.cache/challenge/challenge_spec.json').read_text())
layout=json.loads((ROOT/'simulation/layouts/supah-v2/submission.json').read_text())['placements_mm']
reports={n:json.loads((HERE/f'incumbent-{n}/diagnostic.json').read_text()) for n in [64,128]}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'figure.dpi':150})
fig,(ax,bx)=plt.subplots(1,2,figsize=(13.2,7.0),gridspec_kw={'width_ratios':[1,1.1]})
fig.subplots_adjust(left=.055,right=.985,top=.84,bottom=.25,wspace=.25)
fig.suptitle('Why the incumbent plateaus: self-heating below, contact clipping above',x=.055,ha='left',y=.965,fontsize=16,weight='bold')
fig.text(.055,.907,'Fixed layout and thermal network • Native SuperLU diagnostics • All temperatures are simulated',fontsize=10,color='#4b5563')
cx,cy,cw,ch=spec['thermal_model']['cooling_contact_rect_mm']
ax.add_patch(Rectangle((0,0),52,42,facecolor='#f3f4f6',edgecolor='#6b7280',lw=1))
ax.add_patch(Rectangle((cx,cy),cw,ch,facecolor='#e2f5ef',edgecolor='#16836b',linestyle='--',lw=1.6))
for d,(x,y) in layout.items():
 w,h=spec['dies'][d]['size_mm'];fc='#d7e3f2' if d.startswith('G') else '#f9e5c0'
 ax.add_patch(Rectangle((x,y),w,h,facecolor=fc,edgecolor='#4b5563',lw=1,alpha=.85))
 ax.text(x+w/2,y+h/2,d,ha='center',va='center',weight='bold',fontsize=10,color='#334155')
cases=[('skewed_compute','G0','#b91c1c'),('tensor_training','G3','#7c3aed'),('tensor_training','G2','#7c3aed'),('memory_stream','H2','#b45309')]
for workload,d,color in cases:
 for n in [64,128]:
  rec=reports[n]['workloads'][workload]['per_die'][d];x,y=rec['xy_mm'];ax.plot([x],[y],marker='o' if n==64 else 'x',mfc='none',mec=color,color=color,markersize=6,markeredgewidth=1.7,linestyle='',zorder=5)
ax.annotate('Upper GPU peaks lie\nbeyond the y = 38 mm contact',xy=(45.0,38.5),xytext=(30.5,43.6),ha='center',va='bottom',fontsize=9,color='#6d28d9',arrowprops={'arrowstyle':'-','color':'#6d28d9','lw':1})
ax.set(xlim=(-.7,52.7),ylim=(-.7,46),xlabel='Interposer x (mm)',ylabel='Interposer y (mm)',title='A  Placement, cooling contact, and sampled hotspots')
ax.set_aspect('equal');ax.set_xticks(np.arange(0,53,10));ax.set_yticks(np.arange(0,43,10));ax.spines[['top','right']].set_visible(False)
handles=[Line2D([0],[0],color='#16836b',ls='--',label='High-conductance contact'),Line2D([0],[0],color='#374151',marker='o',mfc='none',ls='',label='64 grid'),Line2D([0],[0],color='#374151',marker='x',ls='',label='128 grid')]
ax.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,-.12),ncol=3,frameon=False,fontsize=8,handlelength=1.5,columnspacing=1.2)
labels=['Own die','Other GPUs','Other HBMs','PHY','Wire'];colors=['#315a91','#8cafd1','#dfb770','#ad6b8c','#5e9e83']
rows=[]
for workload,d in [('skewed_compute','G0'),('tensor_training','G3'),('memory_stream','H2')]:
 for n in [64,128]:
  r=reports[n]['workloads'][workload]['per_die'][d];v=r['source_rise_c'];rows.append((d,workload,n,r,[v[d],sum(c for k,c in v.items() if k.startswith('G') and k!=d),sum(c for k,c in v.items() if k.startswith('H') and k!=d),v['PHY'],v['wire']]))
ypos=[5.6,4.95,3.6,2.95,1.6,.95]
for i,(d,w,n,r,v) in enumerate(rows):
 left=0
 for j,(value,col) in enumerate(zip(v,colors)):
  bx.barh(ypos[i],value,left=left,height=.49,color=col,edgecolor='white',linewidth=.5,label=labels[j] if i==0 else None)
  if value>3:bx.text(left+value/2,ypos[i],f'{value:.2f}',ha='center',va='center',fontsize=8,color='white' if j==0 else '#253249')
  left+=value
 bx.text(left+.8,ypos[i],f'{r["temperature_c"]:.2f}°C',ha='left',va='center',fontsize=9,color='#1f2937')
bx.set_yticks(ypos,[f'{d} · {n}' for d,_,n,_,_ in rows]);bx.set(xlim=(0,86),ylim=(.4,6.2),xlabel='Contribution to hotspot temperature rise above 25°C (°C)',title='B  Source attribution at each full-run hotspot')
bx.set_xticks(np.arange(0,81,20));bx.grid(axis='x',alpha=.2,zorder=0);bx.set_axisbelow(True);bx.spines[['top','right','left']].set_visible(False);bx.tick_params(axis='y',length=0)
for y,label in [(6.07,'G0: skewed compute'),(4.07,'G3: tensor training'),(2.07,'H2: memory stream')]:bx.text(0,y,label,fontsize=9,weight='bold',color='#374151')
bx.legend(loc='upper left',bbox_to_anchor=(0,-.12),ncol=3,frameon=False,fontsize=8,columnspacing=1.3)
fig.text(.055,.045,'At G0, removing every wire watt would cool the fixed hotspot by only 0.37°C (64) or 0.38°C (128).\nThe 0.95 target requires placement changes. Source sums agree within 0.03°C; printed grid values resolve 0.01°C.',fontsize=9,color='#4b5563')
fig.savefig(HERE/'incumbent-physics.png',dpi=180,facecolor='white')
print(HERE/'incumbent-physics.png')
