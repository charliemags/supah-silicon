"""Summarize only completed native observations, keeping minimax and G0 separate."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
allrows=[];runs=[]
for log in sorted(OUT.glob('*/search.jsonl')):
    # Keep the separate same-topology refinement out of the earlier alternative-
    # topology comparison; its own summary and frozen finalists are authoritative.
    if log.parent.name.startswith('de0321-') or log.parent.name in {'p0-alignment','de-restart'}:continue
    rows=[]
    for line in log.read_text().splitlines():
        try:r=json.loads(line)
        except json.JSONDecodeError:continue
        r['log']=str(log.relative_to(ROOT));rows.append(r)
    if not rows:continue
    allrows+=rows
    b=min(rows,key=lambda r:r['continuous_merit_c']);g=min(rows,key=lambda r:r['raw_peaks_c']['skewed_compute']['G0'])
    runs.append({'run':str(log.parent.relative_to(ROOT)),'completed_observations':len(rows),
        'best_screen_score':b['screen_score'],'best_evaluation':b['evaluation'],
        'lowest_g0_skewed_c':g['raw_peaks_c']['skewed_compute']['G0'],'g0_evaluation':g['evaluation'],
        'manifest_sha256':hashlib.sha256((log.parent/'manifest.json').read_bytes()).hexdigest()})
unique={json.dumps(r['submission'],sort_keys=True):r for r in allrows}
bytop={}
for r in allrows:bytop.setdefault(r['topology'],[]).append(r)
summary={'kind':'native64 screening only; all original rules unchanged; not pinned certification',
    'completed_observations':len(allrows),'unique_submissions':len(unique),'distinct_facing_patterns':len(bytop),'runs':runs,
    'topologies':[{'signature':s,'observations':len(rs),'best_screen_score':min(r['screen_score'] for r in rs),
                  'lowest_g0_skewed_c':min(r['raw_peaks_c']['skewed_compute']['G0'] for r in rs)} for s,rs in bytop.items()]}
(OUT/'results-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
if allrows:
    best=min(allrows,key=lambda r:r['continuous_merit_c']);g0=min(allrows,key=lambda r:r['raw_peaks_c']['skewed_compute']['G0'])
    for name,rec in [('best-minimax',best),('best-g0',g0)]:
        folder=OUT/name;folder.mkdir(exist_ok=True)
        (folder/'submission.json').write_text(json.dumps(rec['submission'],indent=2)+'\n')
        (folder/'observation.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='topologies'},indent=2))
