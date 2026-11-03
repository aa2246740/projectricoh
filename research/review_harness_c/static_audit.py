"""Capture source locations and copied-backend provenance for this review."""
import ast
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, sha

enable()
records={}
targets={
 'tools/native_harness_c/ccore/backend.py':['method_same','_c_compatible','_c_prepare_filters','_c_finish','call'],
 'tools/speedlab/content_cache.py':['tool_identity','identity','locked','compile'],
 'tools/speedlab/adapters/snapshot.py':['quiet','save','load'],
 'tools/speedlab/emulator.py':['binding','load_cached'],
}
for name,functions in targets.items():
    path=ROOT/name;source=path.read_text();lines=source.splitlines()
    tree=ast.parse(source)
    records[name]=dict(sha256=sha(path),functions={node.name:dict(line=node.lineno,end_line=node.end_lineno,
           source='\n'.join(lines[node.lineno-1:node.end_lineno]))
           for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in functions})
old=(ROOT/'tools/native_harness/python_backend.py').read_bytes()
new=(ROOT/'tools/native_harness_c/python_backend.py').read_bytes()
copied=[]
for path in sorted((ROOT/'tools/native_harness_c').glob('*.py')):
    reference=ROOT/'tools/native_harness'/path.name
    if path.name!='python_backend.py':
        copied.append(dict(name=path.name,equal=path.read_bytes()==reference.read_bytes(),sha256=sha(path)))
emit(HERE/'local/static-audit.json',dict(sources=records,python_prefix_equal=new[:len(old)]==old,
     other_python_files=copied,stubs_equal=(ROOT/'tools/native_harness/STUBS.md').read_bytes()==(ROOT/'tools/native_harness_c/STUBS.md').read_bytes()))
print('Recorded source locations and copy provenance',flush=True)
