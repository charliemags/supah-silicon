"""Mixed integer placement proposals; original validator always decides legality.

The proposal model permits endpoint track-cell changes. It does not replace
the organizer router, thermal model, hardware, or scoring rules.
"""
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
import fast
from surrogate import DIES,vector


def propose(anchor, gradients, temperatures, radius=1., g0_radius=(.02,.08), noise=None, g0_target=None, target=None, repair_weight=.0002, temperature_weight=1., time_limit=.8, contact_gpus=False):
    origin=vector(anchor);xy=origin.reshape(8,2)
    sizes=np.array([fast.SPEC['dies'][d]['size_mm'] for d in DIES])
    ok,why,routing=fast.legal(anchor)
    if not ok:raise ValueError(why)
    routes=list(routing['routes'].values())
    # 16 origins, 32 integer endpoint cells, 16 access absolute values,
    # 8 transverse track distances, one shared thermal epigraph, 16 move norms.
    count=89;T=72
    lo=np.zeros(count);hi=np.full(count,np.inf);integrality=np.zeros(count)
    lo[:16]=np.maximum(1.001,origin-radius)
    hi[:16]=np.minimum(np.tile([52,42],8)-sizes.ravel()-1.001,origin+radius)
    lo[:2]=np.maximum(lo[:2],origin[:2]-g0_radius)
    hi[:2]=np.minimum(hi[:2],origin[:2]+g0_radius)
    if g0_target is not None: lo[:2]=g0_target;hi[:2]=g0_target
    if contact_gpus:
        for i in range(1,4):
            lo[2*i:2*i+2]=np.maximum(lo[2*i:2*i+2],[4.,4.])
            hi[2*i:2*i+2]=np.minimum(hi[2*i:2*i+2],np.array([48.,38.])-sizes[i])
    if np.any(lo>hi):return None,{'status':2,'message':'empty proposal bounds'}
    lo[16:48]=0;hi[16:48]=np.tile([103,83],16);integrality[16:48]=1
    lo[T]=70;hi[T]=140
    rows=[];lower=[];upper=[]
    def add(items,low=-np.inf,high=np.inf):
        row=np.zeros(count)
        for k,v in items:row[k]+=v
        rows.append(row);lower.append(low);upper.append(high)
    def cell(link,end,k):return 16+link*4+end*2+k
    # Preserve only the relative separation directions, not fixed endpoint cells.
    for i in range(8):
        for j in range(i+1,8):
            choices=[(xy[j,k]-xy[i,k]-sizes[i,k],i,j,k) for k in range(2)]
            choices += [(xy[i,k]-xy[j,k]-sizes[j,k],j,i,k) for k in range(2)]
            _,first,second,k=max(choices)
            add([(2*second+k,1),(2*first+k,-1)],low=sizes[first,k]+1.001)
    weighted=[];weighted_constant=0
    for z,r in enumerate(routes):
        ia=DIES.index(r['from']);ib=DIES.index(r['to'])
        oa=np.array(r['from_port'])-xy[ia];ob=np.array(r['to_port'])-xy[ib]
        normal=np.array(r['from_normal']);axis=int(np.argmax(abs(normal)));tangent=1-axis;sign=int(normal[axis])
        assert np.array_equal(np.array(r['to_normal']),-normal)
        # Facing sides, and therefore the fixed port offsets, stay valid.
        center_constant=(sizes[ib]-sizes[ia])/2
        for s in [-1,1]:
            add([(2*ib+axis,sign),(2*ia+axis,-sign),(2*ib+tangent,s),(2*ia+tangent,-s)],
                low=.001-sign*center_constant[axis]-s*center_constant[tangent])
        for end,(die,offset,norm,pathcell) in enumerate([
                (ia,oa,normal,r['path_grid'][0]),(ib,ob,-normal,r['path_grid'][-1])]):
            for k in range(2):
                add([(2*die+k,1),(cell(z,end,k),-.5)],
                    low=-offset[k]-.7*norm[k],high=.5-.00001-offset[k]-.7*norm[k])
            # Endpoint access must remain outside every expanded die box.
            q0=np.array(pathcell)*.5+.25
            for other in range(8):
                options=[]
                for k in range(2):
                    options.extend([(xy[other,k]-q0[k]-.2,k,-1),
                                    (q0[k]-xy[other,k]-sizes[other,k]-.2,k,1)])
                _,k,side=max(options)
                if side==-1:add([(2*other+k,1),(cell(z,end,k),-.5)],low=.451)
                else:add([(cell(z,end,k),.5),(2*other+k,-1)],low=sizes[other,k]-.049)
            access=48+2*z+end;c=cell(z,end,tangent);d=2*die+tangent
            add([(access,1),(c,-.5),(d,1)],low=.25-offset[tangent])
            add([(access,1),(c,.5),(d,-1)],low=offset[tangent]-.25)
        ca=cell(z,0,tangent);cb=cell(z,1,tangent);transverse=64+z
        add([(transverse,1),(cb,-.5),(ca,.5)],low=0)
        add([(transverse,1),(cb,.5),(ca,-.5)],low=0)
        add([(cell(z,1,axis),sign),(cell(z,0,axis),-sign)],low=0)
        # Normal access and track terms cancel; transverse quantization remains.
        length=[(2*ib+axis,sign),(2*ia+axis,-sign),(48+2*z,1),(49+2*z,1),(transverse,1)]
        constant=sign*(ob[axis]-oa[axis])
        add(length,high=r['limit_mm']-constant-.0001)
        weighted.extend([(k,v*r['bandwidth_gb_s']) for k,v in length])
        weighted_constant+=constant*r['bandwidth_gb_s']
    add(weighted,high=13499.-weighted_constant)
    for gradient,temp in zip(gradients,temperatures):
        add([(T,1)]+[(i,-v) for i,v in enumerate(gradient)],low=float(temp-gradient@origin))
    target = origin if target is None else np.asarray(target)
    for i in range(16):
        add([(73+i,1),(i,-1)],low=-target[i])
        add([(73+i,1),(i,1)],low=target[i])
    objective=np.zeros(count);objective[T]=temperature_weight;objective[73:]=repair_weight
    if noise is not None:objective[:16]=noise
    result=milp(objective,integrality=integrality,bounds=Bounds(lo,hi),
        constraints=LinearConstraint(np.array(rows),lower,upper),
        options={'time_limit':time_limit,'mip_rel_gap':1e-7})
    if result.x is None:return None,{'status':int(result.status),'message':result.message}
    candidate={d:[round(float(v),6) for v in result.x[2*i:2*i+2]] for i,d in enumerate(DIES)}
    valid,reason,actual=fast.legal(candidate)
    return candidate,{'status':int(result.status),'message':result.message,'predicted_equivalent_c':float(result.x[T]),
        'exact_valid':valid,'exact_reason':reason,'weighted_route':actual['weighted_route_gb_s_mm'] if valid else None,
        'cell_changes':sum(int(round(result.x[cell(z,end,k)]))!=r['path_grid'][0 if end==0 else -1][k]
            for z,r in enumerate(routes) for end in range(2) for k in range(2))}
