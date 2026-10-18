"""Plot measured stage medians; no inferred chip performance or power."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('profile', type=Path)
parser.add_argument('output', type=Path)
a = parser.parse_args()
r = json.loads(a.profile.read_text())
s = {v['name']: v for v in r['stages']}
fig, (left, right) = plt.subplots(1, 2, figsize=(12, 6), dpi=160, gridspec_kw={'width_ratios':[1.2,1]})
fig.patch.set_facecolor('#f5f7fa')
labels = ['311 · individual', '311 · bulk', 'Permits · individual', 'Permits · bulk']
positions = list(range(4))
offsets = [0.] * 4
for operation, label, color in [('json_decode', 'JSON decode', '#97c3cb'), ('normalize', 'Normalize', '#3c97a8'), ('insert', 'Persist', '#224979')]:
    values=[]
    for domain in ('service_requests','building_permits'):
        for mode in ('individual','bulk'):
            key=f'{domain}.{operation}_{mode}' if operation=='insert' else f'{domain}.{operation}'
            values.append(s[key]['summary']['wall_s']['median']*1000)
    left.barh(positions,values,left=offsets,label=label,color=color,height=.65)
    offsets=[x+y for x,y in zip(offsets,values)]
for y,value in zip(positions,offsets):
    left.text(value+7,y,f'{value:.0f}',va='center',fontsize=10)
left.set_yticks(positions,labels)
left.invert_yaxis()
left.set_xlim(0,max(offsets)*1.15)
left.set_xlabel('Sum of stage medians (ms per dataset batch)')
left.set_title('Ingestion: existing individual and bulk APIs',loc='left',fontsize=12,pad=15)
left.legend(loc='lower right',frameon=False)
keys=['records.indexed_query','inference.empirical_311','digest.context_and_rank','inference.request_prepare']
values=[s[key]['summary']['wall_s']['median']*1000/s[key]['units_per_iteration'] for key in keys]
right.barh(range(4),values,color=['#224979','#3c97a8','#224979','#97c3cb'],height=.65)
right.set_yticks(range(4),['100-row query','Empirical prediction','Digest context + rank','LLM request formatting'])
right.invert_yaxis()
right.set_xscale('log')
right.set_xlim(.01,max(values)*3)
for y,value in enumerate(values):
    right.text(value*1.15,y,f'{value:.3f} ms',va='center',fontsize=10)
right.set_xlabel('Median per operation (ms, logarithmic scale)')
right.set_title('Local request processing',loc='left',fontsize=12,pad=15)
for ax in (left,right):
    ax.set_facecolor('#f5f7fa')
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='x',alpha=.15)
    ax.set_axisbelow(True)
fig.suptitle(f"Muni workload profile · {r['host']['cpu_model']}",x=.03,ha='left',fontsize=18,fontweight='bold')
count=r['observations']['sample_rows_per_table']
fig.text(.03,.89,f"{count['service_requests']:,} service requests · {count['building_permits']:,} permits · {r['observations']['digest_cards']} selected digest cards",fontsize=11,color='#4a5867')
fig.text(.03,.03,f"{r['protocol']['repeats']} measured repetitions after {r['protocol']['warmups']} warmups. Bounded public-data replay, warm caches, one process.\nIngestion totals sum isolated medians. Generative inference and power were not measured.",fontsize=10,color='#4a5867')
fig.tight_layout(rect=(0,.11,1,.86),w_pad=3)
a.output.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(a.output)
print(a.output)
