"""Change only native solver text output precision; never touch the pinned binary."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

out=Path('/work/.cache/hotspot-precise')
with tempfile.TemporaryDirectory(prefix='hotspot-output-precision-') as tmp:
    source=Path(tmp)/'HotSpot'
    shutil.copytree('/opt/hotspot',source)
    file=source/'temperature_grid.c'
    before=file.read_text()
    old='fprintf(fp, "%d\\t%.2f\\n", i*model->cols+j,'
    new='fprintf(fp, "%d\\t%.8f\\n", i*model->cols+j,'
    assert before.count(old)==1
    file.write_text(before.replace(old,new))
    subprocess.run(['make','-C',str(source),'-j4','SUPERLU=1','hotspot'],check=True)
    shutil.copy2(source/'hotspot',out)
    manifest={'purpose':'native search guidance only; output formatting change, no thermal equations or judge changes',
              'original_source_sha256':hashlib.sha256(before.encode()).hexdigest(),
              'changed_source_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
              'exact_replacement':{'old':old,'new':new},
              'binary_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
    Path('/work/simulation/research-v4/precision-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest),flush=True)
