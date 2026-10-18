"""Build the search-only output-precision variant without rewriting archived evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, default=ROOT / '.cache/hotspot-precise')
p.add_argument('--manifest', type=Path, default=ROOT / '.cache/hotspot-precise-build.json')
a = p.parse_args()
if a.output.resolve() == (ROOT / '.cache/challenge/vendor/HotSpot/hotspot').resolve():
    raise ValueError('The pinned evaluator must never be replaced.')
with tempfile.TemporaryDirectory(prefix='hotspot-output-precision-') as tmp:
    source = Path(tmp) / 'HotSpot'
    shutil.copytree('/opt/hotspot', source)
    file = source / 'temperature_grid.c'
    before = file.read_text()
    old = 'fprintf(fp, "%d\\t%.2f\\n", i*model->cols+j,'
    new = 'fprintf(fp, "%d\\t%.8f\\n", i*model->cols+j,'
    assert before.count(old) == 1
    file.write_text(before.replace(old, new))
    subprocess.run(['make', '-C', str(source), '-j4', 'SUPERLU=1', 'hotspot'], check=True)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'hotspot', a.output)
    manifest = {
        'purpose': 'Native search guidance only; one output-format change, no physics or judge changes.',
        'original_source_sha256': hashlib.sha256(before.encode()).hexdigest(),
        'changed_source_sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
        'exact_replacement': {'old': old, 'new': new},
        'binary_sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
    }
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest), flush=True)
