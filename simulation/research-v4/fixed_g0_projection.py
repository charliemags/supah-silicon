import numpy as np
from scipy.optimize import minimize
import fast
from geometry import _route_grid, die_box
from surrogate import DIES, vector, placement

def project(anchor, target, die='G0', rounds=5):
    ok, _, routing = fast.legal(anchor)
    if not ok:
        return None
    sizes = np.array([fast.SPEC['dies'][d]['size_mm'] for d in DIES])
    origin = vector(anchor)
    index = DIES.index(die)
    bounds = [(1., fast.SPEC['interposer_mm'][axis]-sizes[i,axis]-1.)
              for i in range(8) for axis in range(2)]
    bounds[2*index:2*index+2] = [(float(t),float(t)) for t in target]
    if die != 'G0':
        bounds[:2] = [(float(t),float(t)) for t in origin[:2]]
    pairs = []
    for i in range(8):
        for j in range(i+1,8):
            delta = origin.reshape(8,2)[j]-origin.reshape(8,2)[i]
            choices = [(delta[k]-sizes[i,k], i,j,k) for k in range(2)]
            choices += [(-delta[k]-sizes[j,k],j,i,k) for k in range(2)]
            _, first, second, axis = max(choices)
            pairs.append((first,second,axis))
    links = list(routing['routes'].values())
    ia = np.array([DIES.index(r['from']) for r in links])
    ib = np.array([DIES.index(r['to']) for r in links])
    oa = np.array([r['from_port'] for r in links])-origin.reshape(8,2)[ia]
    ob = np.array([r['to_port'] for r in links])-origin.reshape(8,2)[ib]
    limits = np.array([r['limit_mm'] for r in links])
    weights = np.array([r['bandwidth_gb_s'] for r in links])
    def manhattan(x):
        xy = x.reshape(8,2)
        return np.abs(xy[ia]+oa-xy[ib]-ob).sum(axis=1)
    overhead = np.array([r['route_length_mm'] for r in links])-manhattan(origin)
    def constraints(x):
        xy = x.reshape(8,2)
        gaps = [xy[j,k]-xy[i,k]-sizes[i,k]-1.001 for i,j,k in pairs]
        lengths = manhattan(x)+overhead
        return np.r_[gaps,limits-lengths, (13499.-lengths@weights)/600.]
    start = origin.copy()
    start[2*index:2*index+2] = target
    for _ in range(rounds):
        result = minimize(lambda x:float(np.sum((x-origin)**2)),start,
                          jac=lambda x:2*(x-origin), bounds=bounds,
                          constraints={'type':'ineq','fun':constraints},method='SLSQP',
                          options={'maxiter':120,'ftol':1e-8})
        candidate = placement(result.x)
        if fast.legal(candidate)[0]:
            return candidate
        if np.min(constraints(result.x)) < -0.05:
            return None
        # Re-estimate only track-access overhead; final validation is unchanged.
        boxes = {d:die_box(fast.SPEC,candidate,d) for d in DIES}
        lengths = []
        try:
            for i,r in enumerate(links):
                pa = {'center_mm':np.array(candidate[r['from']])+oa[i], 'normal':r['from_normal']}
                pb = {'center_mm':np.array(candidate[r['to']])+ob[i], 'normal':r['to_normal']}
                lengths.append(_route_grid(fast.SPEC,boxes,pa,pb)[0])
        except ValueError:
            return None
        overhead = np.maximum(0,np.array(lengths)-manhattan(vector(candidate)))+0.005
        start = result.x
    return None
