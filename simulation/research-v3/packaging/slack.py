"""First local infeasibility in1μm axis steps; valid islands beyond are not excluded."""
from explore import *
base=BASE['placements_mm'];out={}
for d in base:
 out[d]={}
 for axis,sign in itertools.product(range(2),[-1,1]):
  key='xy'[axis]+('+' if sign>0 else '-')
  for i in range(1,501):
   lay={k:v[:] for k,v in base.items()};lay[d][axis]+=sign*i*.001
   try:validate_layout(SPEC,lay)
   except ValueError as e:
    out[d][key]={'first_invalid_mm':round(i*.001,3),'reason':str(e)};break
  else:out[d][key]={'first_invalid_mm':None,'tested_through_mm':.5}
write(OUT/'local-feasible-axis-radius.json',out)
