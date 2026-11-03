"""Verify that both default selectors avoid loading the optional C library."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scope_guard import HERE, ROOT, emit, enable, load

enable()
sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
os.environ['GXR_CCORE_BUILD_MANIFEST']=str(HERE/'local/unavailable-build.json')
rows=[]
for index,option in enumerate((None,'python')):
    if option is None:os.environ.pop('GXR_HARNESS_BACKEND',None)
    else:os.environ['GXR_HARNESS_BACKEND']=option
    module=load(ROOT/'tools/native_harness_c/python_backend.py','review_default_'+str(index))
    b=module.PythonBackend()
    passed=type(b) is module.PurePythonBackend and not hasattr(b,'native_stats') and 'ccore.backend' not in sys.modules
    rows.append(dict(selector=option,pure_python=passed))
emit(HERE/'local/default-summary.json',dict(passed=all(row['pure_python'] for row in rows),cases=rows))
assert all(row['pure_python'] for row in rows)
print(json.dumps(rows),flush=True)
