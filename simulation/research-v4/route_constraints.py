import numpy as np
import fast
from surrogate import DIES, vector as vect, placement as layout

def constraint_model(x0):
 lay=layout(x0);_,_,routing=fast.legal(lay);sizes=np.array([fast.SPEC['dies'][d]['size_mm']for d in DIES]);xy0=x0.reshape(8,2);pairs=[]
 for i in range(8):
  for j in range(i+1,8):
   delta=xy0[j]-xy0[i];choices=[(delta[k]-sizes[i,k],i,j,k)for k in range(2)]+[(-delta[k]-sizes[j,k],j,i,k)for k in range(2)]
   _,first,second,k=max(choices);pairs.append((first,second,k))
 links=list(routing['routes'].values());ia=np.array([DIES.index(r['from'])for r in links]);ib=np.array([DIES.index(r['to'])for r in links]);oa=np.array([r['from_port']for r in links])-xy0[ia];ob=np.array([r['to_port']for r in links])-xy0[ib];limits=np.array([r['limit_mm']for r in links]);weights=np.array([r['bandwidth_gb_s']for r in links]);pitch=.5;clearance=.2;margin=.002
 qa=np.array([r['path_grid'][0]for r in links])*pitch+pitch/2
 qb=np.array([r['path_grid'][-1]for r in links])*pitch+pitch/2
 tracks=np.array([(len(r['path_grid'])-1)*pitch for r in links])
 lower=np.ones(16)*1.001;upper=np.array([fast.SPEC['interposer_mm'][k]-sizes[i,k]-1.001 for i in range(8)for k in range(2)])
 # The two exact endpoint-access cells stay fixed. All port offsets are affine
 # while facing sides and their per-edge allocation remain unchanged.
 for link_idx,r in enumerate(links):
  for die_idx,offset,normal,cell in [(ia[link_idx],oa[link_idx],r['from_normal'],r['path_grid'][0]),(ib[link_idx],ob[link_idx],r['to_normal'],r['path_grid'][-1])]:
   for k in range(2):
    j=2*die_idx+k;lower[j]=max(lower[j],cell[k]*pitch-offset[k]-(clearance+pitch)*normal[k]+margin)
    upper[j]=min(upper[j],(cell[k]+1)*pitch-offset[k]-(clearance+pitch)*normal[k]-margin)
 # Every frozen path point stays outside each .2mm-expanded die. Select the
 # currently safest separating halfspace, giving conservative linear bounds.
 points={tuple(cell)for r in links for cell in r['path_grid']}
 for cell in points:
  point=np.array(cell)*pitch+pitch/2
  for i in range(8):
   choices=[]
   for k in range(2):
    choices += [(xy0[i,k]-point[k]-clearance,k,'lower'),(point[k]-xy0[i,k]-sizes[i,k]-clearance,k,'upper')]
   slack,k,which=max(choices);j=2*i+k
   if which=='lower':lower[j]=max(lower[j],point[k]+clearance+margin)
   else:upper[j]=min(upper[j],point[k]-sizes[i,k]-clearance-margin)
 # Sides selected by dominant center displacement must remain unchanged.
 normals=np.array([r['from_normal']for r in links]);axes=np.argmax(abs(normals),axis=1);signs=np.sum(normals,axis=1)
 def cons(x):
  xy=x.reshape(8,2);lengths=tracks+np.abs(xy[ia]+oa-qa).sum(axis=1)+np.abs(xy[ib]+ob-qb).sum(axis=1)
  centers=xy+sizes/2;delta=centers[ib]-centers[ia];facing=[]
  for z,axis in enumerate(axes):
   dominant=signs[z]*delta[z,axis];other=delta[z,1-axis];facing.extend([dominant-other-margin,dominant+other-margin])
  return np.r_[[xy[j,k]-xy[i,k]-sizes[i,k]-1.002 for i,j,k in pairs],limits-lengths,(13499-lengths@weights)/600.,facing]
 if np.any(lower>upper):raise ValueError('Conservative fixed-route bounds became empty')
 return cons,list(zip(lower,upper))
