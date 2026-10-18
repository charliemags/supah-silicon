"""Seed generation only: compressed, relabelled asymmetric rings."""
import itertools,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'.cache/challenge'))
from geometry import validate_layout
SPEC=json.loads((ROOT/'.cache/challenge/challenge_spec.json').read_text())
BASE=json.loads((ROOT/'simulation/research-v5/submission.json').read_text())['placements_mm']
cycle=['G0','H0','G1','H1','G2','H2','G3','H3'];records=[];rejects=[]
for top,bottom,flipx,flipy,reverse,shift in itertools.product([26.75,27.125,27.5],[3.75,4.25],range(2),range(2),range(2),range(0,8,2)):
    lay={}
    for i,d in enumerate(cycle):
        target=cycle[((-i if reverse else i)+shift)%8]
        x,y=BASE[d];w,h=SPEC['dies'][d]['size_mm']
        # Centers preserve asymmetric horizontal spacing and compress the vertical span.
        if d in ['G0','G1']:cy=bottom+5.25
        elif d in ['G2','G3']:cy=top+5.25
        elif d=='H0':cy=bottom+5.25
        elif d=='H2':cy=top+5.25
        else:cy=(bottom+top+.3)/2+5.1
        cx=x+w/2
        if flipx:cx=52-cx
        if flipy:cy=42-cy
        lay[target]=[round(cx-w/2,6),round(cy-h/2,6)]
    meta=dict(top=top,bottom=bottom,flipx=flipx,flipy=flipy,reverse=reverse,shift=shift)
    try:routing=validate_layout(SPEC,lay)
    except Exception as e:rejects.append({**meta,'reason':str(e),'submission':{'placements_mm':lay}});continue
    records.append({'submission':{'placements_mm':lay},'kind':'compressed-ring','meta':meta,'route_weight':routing['weighted_route_gb_s_mm']})
out=Path(__file__).parent/'compact-seeds.json';out.write_text(json.dumps(records,indent=2)+'\n')
(out.parent/'compact-rejections.json').write_text(json.dumps(rejects,indent=2)+'\n')
print(json.dumps({'valid':len(records),'invalid':len(rejects)}))
