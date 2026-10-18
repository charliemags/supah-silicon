"""Independent original-validator audit of every distinct measured submission."""
import hashlib,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;ROOT=D.parents[2];CH=ROOT/'.cache/challenge'
sys.path.insert(0,str(CH));from geometry import validate_layout
spec=json.loads((CH/'challenge_spec.json').read_text());seen={};counts={};failures=[];max_route=0
for p in D.glob('*/search.jsonl'):
    counts[p.parent.name]={}
    for l in p.read_text().splitlines():
        r=json.loads(l);g=str(r['grid']);counts[p.parent.name][g]=counts[p.parent.name].get(g,0)+1
        sub=r['submission'];k=json.dumps(sub,sort_keys=True)
        if k in seen:continue
        try:
            rr=validate_layout(spec,sub['placements_mm'],wire_routes_grid=sub.get('wire_routes_grid',{}));max_route=max(max_route,rr['weighted_route_gb_s_mm']);seen[k]=True
        except Exception as e:failures.append({'source':str(p),'evaluation':r['evaluation'],'reason':str(e),'submission':sub});seen[k]=False
integrity={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'simulation/research-v5/submission.json',CH/'challenge_spec.json',CH/'geometry.py',CH/'run_simulations.py',CH/'verify_submission.py',CH/'vendor/HotSpot/hotspot']}
report={'kind':'Original organizer legality revalidation of actual measured submissions; no thermal resimulation','counts_by_grid':counts,'unique_submissions':len(seen),'valid_unique':sum(seen.values()),'failures':failures,'maximum_weighted_route':max_route,'current_protected_sha256':integrity}
(D/'legality-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['current_protected_sha256','failures']},indent=2));assert not failures
