"""Enumerate exact-validated repair of directed H3 isolation; no thermal solves."""
import sys,json,itertools,math,collections
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'.cache/challenge'));from geometry import validate_layout
spec=json.loads((root/'.cache/challenge/challenge_spec.json').read_text());base=json.loads((root/'simulation/layouts/supah-v2/submission.json').read_text())['placements_mm'];out=Path(__file__).parent
valid=[];reject=collections.Counter();seen=set();count=0
for delta,eps,extra_g3left,reduce_h3up in itertools.product([.05,.1,.2,.4,.6,1.],[.2,.4,.6,1.], [.05,.15,.3,.5], [0,.025,.05,.1]):
 x={k:v[:]for k,v in base.items()}
 x['H3']=[round(x['H3'][0]-delta,3),round(x['H3'][1]+delta-reduce_h3up,3)]
 x['G3']=[round(x['G3'][0]-delta-extra_g3left,3),round(x['G3'][1]+delta,3)]
 for name in ['G2','H2']:x[name][0]=round(x[name][0]-eps,3)
 count+=1
 try:r=validate_layout(spec,x)
 except Exception as e:reject[str(e)]+=1;continue
 ident=json.dumps(x,sort_keys=True)
 if ident in seen:continue
 seen.add(ident)
 ghot=[base['G0'][0]+11.5*.25,base['G0'][1]+10.5*.28];hhot=[x['H3'][0]+10.5*.34,x['H3'][1]+10.2*.68]
 valid.append({'submission':{'placements_mm':x},'delta':delta,'left_g2_h2':eps,'extra_g3_left':extra_g3left,'reduce_h3_up':reduce_h3up,'weighted_route':r['weighted_route_gb_s_mm'],'h3_bank_to_g0_compute_distance':math.dist(ghot,hhot)})
valid.sort(key=lambda r:(r['delta'],r['left_g2_h2'],r['extra_g3_left'],r['reduce_h3_up']))
(out/'directed-legal-seeds.json').write_text(json.dumps({'kind':'exact valid placement candidates; no thermal predictions or simulations','tested':count,'legal_count':len(valid),'candidates':valid,'rejections':dict(reject)},indent=2)+'\n')
print('tested',count,'legal',len(valid));print([(r['delta'],r['left_g2_h2'],r['extra_g3_left'],r['reduce_h3_up'],r['weighted_route'])for r in valid[:20]])
