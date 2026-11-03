"""Retain the frozen 118 to 119 dispatcher evidence for the remaining proof."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, file_sha

source = ROOT / 'research/review_g119b'
target = OUT / 'previous_delta'
target.mkdir(exist_ok=True)
scope = '''"""Previous frozen delta, within the generation 120 quality directory."""
from pathlib import Path
import importlib.util
_p=Path(__file__).resolve().parent.parent/'common.py'
_s=importlib.util.spec_from_file_location('root_quality_scope',_p)
_m=importlib.util.module_from_spec(_s);_s.loader.exec_module(_m)
OUT=Path(__file__).resolve().parent
ROOT=_m.ROOT
sha,file_sha,load=_m.sha,_m.file_sha,_m.load
def save(name,value):
    _m.save('previous_delta/'+str(name),value)
'''
(target / 'scope.py').write_text(scope)
for name in ('codegen', 'differential', 'misc_diff', 'service_targets', 'artifacts', 'file_gate_cfg'):
    p = source / (name + '.py')
    (target / p.name).write_text(p.read_text().replace('from common import', 'from scope import'))
files = ['identity.json', 'object-map.json', 'engine118.asm', 'engine119.asm',
         'decode118.json', 'decode119.json', 'rv_call-results.json',
         'service-targets.json', 'service-targets-early.json', 'service-more.json',
         'branch-dispositions.json', 'open-rv-call.json']
for directory in ('labels118', 'codegen'):
    files += [str(p.relative_to(source)) for p in (source / directory).rglob('*') if p.is_file()]
for name in files:
    p, q = source / name, target / name
    q.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(p, q)
save('previous-delta-binding.json', dict(status='PASS', files=[dict(name=n, sha256=file_sha(source/n)) for n in files],
    scope='Previously completed 10000+64 dispatcher pairs are frozen input evidence. New directed cases close the remaining outcomes.'))
print('PASS previous dispatcher proof inputs bound', len(files), flush=True)
