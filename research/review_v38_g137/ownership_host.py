import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_v38_g137'
LOCAL = OUT / 'local/ownership-host'
LOCAL.mkdir(parents=True, exist_ok=True)
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v38-g137/ownership-host')
TEMP.mkdir(parents=True, exist_ok=True)
os.environ['TMPDIR'] = str(TEMP)

def function(path, name):
    text = path.read_text()
    mark = text.index(name + '(')
    start = text.rfind('\n', 0, mark) + 1
    opening = text.index('{', mark)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'

inputs = [
    ('firmware/resident_v38/resident/hooks.c', 'owned', None),
    ('firmware/resident_v37/resident/hooks.c', 'owned', 'owned_before'),
    ('firmware/engine_v54_g137/candidate/engine_services/native_seed.c', 'rv_view_owned', None),
    ('firmware/engine_v53_g135/candidate/engine_services/native_seed.c', 'rv_view_owned', 'rv_view_owned_before'),
    ('firmware/engine_v54_g137/candidate/engine_services/services.c', 'rv_settings_owned', None),
]
parts = []
for path, name, changed in inputs:
    code = function(ROOT / path, name)
    parts.append(code.replace(name+'(', changed+'(', 1) if changed else code)
(LOCAL / 'owner_functions.inc.c').write_text('\n'.join(parts))
program = LOCAL / 'owner-check'
command = ['/usr/bin/clang','-std=c11','-O1','-g','-fsanitize=address,undefined','-DRV_HOST',
           '-I'+str(ROOT/'firmware/resident_v38/resident'), '-I'+str(LOCAL),
           str(OUT/'ownership_host.c'),'-o',str(program)]
subprocess.run(command, check=True)
result = json.loads(subprocess.check_output([str(program)], text=True))
result['sources'] = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path,_,_ in inputs}
result['executable_sha256'] = hashlib.sha256(program.read_bytes()).hexdigest()
(OUT/'evidence/ownership-predicates-resume.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result), flush=True)
