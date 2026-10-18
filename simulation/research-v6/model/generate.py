"""Free topology placement MILP proposals, always gated by original validator.

Enumerates connected-side direction cycles. Pair separation is a four-way
binary disjunction, independent of incumbent geometry. Routing cell endpoints
are integer variables. No thermal, hardware or validation rules are changed.
"""
import argparse,itertools,json,os,sys,time,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'simulation/tools'))
import fast
DIES=list(fast.SPEC['dies']); RING=['G0','H0','G1','H1','G2','H2','G3','H3']
V=np.array([[1,0],[0,1],[-1,0],[0,-1]])
S=np.array([fast.SPEC['dies'][d]['size_mm'] for d in DIES]); specs=fast.SPEC['links']
LINKS={(l['from'],l['to']):l for l in specs}

def signature(lay):
    from geometry import _side,die_box
    return ''.join({'right':'E','top':'N','left':'W','bottom':'S'}[_side(die_box(fast.SPEC,lay,d),die_box(fast.SPEC,lay,RING[(i+1)%8]))] for i,d in enumerate(RING))

def solve(directions,rng,seconds=1.,clearance=1.001,contact=False,g0fixed=False,isolate=False):
    # 16 positions,32 integer endpoints,16 tangential access,8 transverse
    # route distances,112 pair-separation selectors, and16 target deviations.
    n=200;sep=72;dev=184; big=110
    low=np.zeros(n);high=np.full(n,np.inf);integ=np.zeros(n)
    low[:16]=clearance;high[:16]=(np.tile([52,42],8)-S.ravel()-clearance)
    if contact:
        low[:16]=np.tile([4.,4.],8);high[:16]=np.tile([48.,38.],8)-S.ravel()
    if g0fixed:
        low[:2]=[3.193438,4.119202];high[:2]=low[:2]
        for d in ["G1","G2","G3"]:
            i=DIES.index(d);low[2*i+1]=4.;high[2*i+1]=27.5
    high[16:48]=np.tile([103,83],16);integ[16:48]=1
    high[sep:dev]=1;integ[sep:dev]=1
    rows=[];lower=[];upper=[]
    def add(items,lo=-np.inf,hi=np.inf):
        r=np.zeros(n)
        for i,v in items:r[i]+=v
        rows.append(r);lower.append(lo);upper.append(hi)
    def cell(z,e,k):return 16+z*4+e*2+k
    for z,(i,j) in enumerate(itertools.combinations(range(8),2)):
        q=sep+4*z
        add([(q+t,1) for t in range(4)],lo=1)
        for t,(a,b,k) in enumerate([(i,j,0),(i,j,1),(j,i,0),(j,i,1)]):
            add([(2*b+k,1),(2*a+k,-1),(q+t,-big)],lo=S[a,k]+clearance-big)
    sides={d:{} for d in DIES}
    for z,(a,b) in enumerate(zip(RING,RING[1:]+RING[:1])):
        link=LINKS.get((a,b),LINKS.get((b,a)))
        sides[a][link['id']]=int(directions[z]);sides[b][link['id']]=(int(directions[z])+2)%4
    offsets={}
    for d,links in sides.items():
        wh=S[DIES.index(d)]
        for side in set(links.values()):
            ids=sorted([l for l,s in links.items() if s==side])
            widths=[next(l for l in specs if l['id']==l_id)['gb_s']/150 for l_id in ids]
            length=wh[1] if side%2==0 else wh[0];needed=sum(widths)+.4*(len(ids)-1)
            if needed>length*.6+1e-9:return None,{'reason':'capacity'}
            cursor=(length-needed)/2
            for l_id,w in zip(ids,widths):
                tangent=cursor+w/2;cursor+=w+.4
                offsets[(d,l_id)]=np.array([(wh[0] if side==0 else 0),tangent]) if side%2==0 else np.array([tangent,(wh[1] if side==1 else 0)])
    weighted=[];wc=0
    for z,link in enumerate(specs):
        ia=DIES.index(link['from']);ib=DIES.index(link['to']);side=sides[link['from']][link['id']]
        norm=V[side];axis=side%2;tan=1-axis;sgn=int(norm[axis]);oa=offsets[(link['from'],link['id'])];ob=offsets[(link['to'],link['id'])]
        centers=(S[ib]-S[ia])/2
        for s in [-1,1]:
            add([(2*ib+axis,sgn),(2*ia+axis,-sgn),(2*ib+tan,s),(2*ia+tan,-s)],lo=.0001-sgn*centers[axis]-s*centers[tan])
        for end,(die,off,no) in enumerate([(ia,oa,norm),(ib,ob,-norm)]):
            for k in range(2):
                add([(2*die+k,1),(cell(z,end,k),-.5)],lo=-off[k]-.7*no[k],hi=.5-.00001-off[k]-.7*no[k])
            ac=48+2*z+end;c=cell(z,end,tan);d=2*die+tan
            add([(ac,1),(c,-.5),(d,1)],lo=.25-off[tan])
            add([(ac,1),(c,.5),(d,-1)],lo=off[tan]-.25)
        ca=cell(z,0,tan);cb=cell(z,1,tan);td=64+z
        add([(td,1),(cb,-.5),(ca,.5)],lo=0);add([(td,1),(cb,.5),(ca,-.5)],lo=0)
        add([(cell(z,1,axis),sgn),(cell(z,0,axis),-sgn)],lo=0)
        length=[(2*ib+axis,sgn),(2*ia+axis,-sgn),(48+2*z,1),(49+2*z,1),(td,1)]
        constant=sgn*(ob[axis]-oa[axis])
        add(length,hi=link['max_route_mm']-constant-.01)
        weighted.extend([(i,v*link['gb_s']) for i,v in length]);wc+=constant*link['gb_s']
    add(weighted,hi=13490-wc)
    # Random target positions avoid simply minimizing perimeter into one shape.
    targets=np.array([rng.uniform([2,2],[39,29]) for d in DIES]).ravel()
    targets[:2]=[rng.uniform(3.0,10),rng.uniform(3.8,10)]
    for i in range(16):
        add([(dev+i,1),(i,-1)],lo=-targets[i]);add([(dev+i,1),(i,1)],lo=targets[i])
    obj=np.zeros(n);obj[dev:]=rng.uniform(.2,1,16);obj[dev:dev+2]=rng.choice([.25,2,10]);obj[48:72]=.01
    if isolate:
        obj[dev:]*=.01
        for d in ['H0','H3']:
            i=DIES.index(d);obj[2*i:2*i+2]=-rng.uniform(.8,1.2,2)
        for d in ['G1','G2','G3']:
            i=DIES.index(d);obj[2*i:2*i+2]=-rng.uniform(.01,.03,2)
    result=milp(obj,integrality=integ,bounds=Bounds(low,high),constraints=LinearConstraint(rows,lower,upper),options={'time_limit':seconds,'mip_rel_gap':.01})
    if result.x is None:return None,{'reason':result.message,'status':int(result.status)}
    lay={d:[round(float(v),6) for v in result.x[2*i:2*i+2]] for i,d in enumerate(DIES)}
    ok,reason,routing=fast.legal(lay)
    return lay,{'valid':ok,'reason':reason,'status':int(result.status),'weighted':routing['weighted_route_gb_s_mm'] if ok else None,'signature':signature(lay),'directions':list(map(int,directions))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=500);p.add_argument('--seconds',type=float,default=.4);p.add_argument('--seed',type=int,default=946);p.add_argument('--screen',type=int,default=0);p.add_argument('--contact',action='store_true');p.add_argument('--g0-fixed',action='store_true');p.add_argument('--isolate',action='store_true');a=p.parse_args()
    a.output.mkdir(exist_ok=False);rng=np.random.default_rng(a.seed);log=(a.output/'proposals.jsonl').open('w');start=time.monotonic()
    seq=[]
    for ds in itertools.product(range(4),repeat=8):
        if any(ds[i]==(ds[(i-1)%8]+2)%4 and (i%2==1 or ds[i]%2==0) for i in range(8)):continue
        # Single-direction cycles cannot close; retain 2/3-side cycles too.
        # The MILP, rather than a convex-ring assumption, checks their feasibility.
        if len(set(ds))<2:continue
        seq.append(ds)
    rng.shuffle(seq)
    # Start with concave and folded cycles, then randomly cover all admissible side assignments.
    # Randomize instead of spending the budget entirely on the hardest shared-port patterns.
    # Explicit concave, rectangle, and folded controls precede the broad enumeration.
    seq=[(0,0,1,2,1,2,3,3),(0,0,1,1,2,2,3,3),(0,0,0,1,2,2,2,3)]+seq
    seeds=[];seen=set()
    for z in range(a.trials):
        ds=seq[z%len(seq)];lay,meta=solve(ds,rng,a.seconds,contact=a.contact,g0fixed=a.g0_fixed,isolate=a.isolate)
        rec={'trial':z,'direction_sequence':ds,'submission':{'placements_mm':lay} if lay else None,**meta}
        log.write(json.dumps(rec)+'\n');log.flush()
        if lay and meta['valid']:
            key=json.dumps(lay,sort_keys=True)
            if key not in seen:
                seen.add(key);path=a.output/f'seed-{len(seeds):04d}.json';path.write_text(json.dumps({'placements_mm':lay},indent=2)+'\n');seeds.append({'path':str(path),'trial':z,**meta})
                print('SEED',len(seeds),meta['signature'],meta['weighted'],flush=True)
                (a.output/'seeds.json').write_text(json.dumps(seeds,indent=2)+'\n')
        if z%20==0:print('PROGRESS',z,'seeds',len(seeds),'seconds',round(time.monotonic()-start),flush=True)
    log.close();(a.output/'summary.json').write_text(json.dumps({'trials':a.trials,'seeds':len(seeds),'elapsed':time.monotonic()-start,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'direction_sequences':len(seq),'all_dies_within_contact':a.contact,'g0_fixed_to_v5':a.g0_fixed,'max_neighbor_distance_objective':a.isolate},indent=2)+'\n')
if __name__=='__main__':main()
