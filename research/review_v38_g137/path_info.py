import inspect
import json
import runpy
import sys
from pathlib import Path

target = Path(sys.argv[1]).resolve()
sys.argv = [str(target), *sys.argv[2:]]
seen = {}

def trace(frame, event, arg):
    if frame.f_code.co_filename == str(target):
        for key, value in frame.f_globals.items():
            if isinstance(value, Path):
                seen[key] = str(value)
            elif key.isupper() and isinstance(value, (str, int, bool)) and len(str(value)) < 180:
                seen[key] = value
    return trace

sys.settrace(trace)
try:
    ns = runpy.run_path(str(target), run_name='path_info')
    seen['functions'] = {key: str(inspect.signature(value)) for key, value in ns.items()
                         if inspect.isfunction(value) and value.__module__ == 'path_info'}
    seen['classes']={key:{name:str(inspect.signature(method)) for name,method in value.__dict__.items()
                         if inspect.isfunction(method)} for key,value in ns.items()
                     if inspect.isclass(value) and value.__module__=='path_info'}
except BaseException as exc:
    seen['error_type'] = type(exc).__name__
finally:
    sys.settrace(None)
print(json.dumps(seen, ensure_ascii=False, indent=2))
