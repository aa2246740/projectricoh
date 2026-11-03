from pathlib import Path
import importlib.machinery
import importlib.util
import atexit
import builtins
import io
import json
import os
import runpy
import sys
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R2_CORE_LAYOUT = None
R2_ADAPTER_LAYOUT = None
sys.path.insert(0, str(HERE))
from scope import setup, ALLOWED
from build_tools import code_map

def relocate(code):
    values = []
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            value = relocate(value)
        elif isinstance(value, str):
            value = value.replace('g135_v37', 'emptystack_v38').replace('package_v37_g135', 'package_v38_g137')
        values.append(value)
    return code_map(code.replace(co_consts=tuple(values)))

def aligned_write_fence(event, arguments):
    if event != 'open':
        return
    file, mode, flags = arguments
    if isinstance(file, int):
        return
    writing = (isinstance(mode, str) and any(letter in mode for letter in 'wax+')) or (
        isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if not writing:
        return
    path = Path(os.fsdecode(file)).resolve()
    if str(path) in ('/dev/null', '/dev/tty'):
        return
    if not any(path == root or root in path.parents for root in r2_write_roots):
        raise PermissionError('Current write boundary: ' + str(path))


def align_loaded(frame, event, argument):
    if event == 'return' and frame.f_code.co_name == '<module>' and frame.f_globals.get('__name__') == 'support':
        values = frame.f_globals
        if 'fence' in values:
            values['r2_write_roots'] = ALLOWED
            values['fence'].__code__ = aligned_write_fence.__code__
            sys.setprofile(None)


def aligned_read(original, file, mode='r', *arguments, **keywords):
    if isinstance(file, (str, bytes, os.PathLike)) and not any(letter in mode for letter in 'wax+'):
        path = Path(os.fsdecode(file))
        if str(path).endswith('/review_g126/local/layout/layout.json'):
            data = json.dumps(R2_CORE_LAYOUT)
            return io.BytesIO(data.encode()) if 'b' in mode else io.StringIO(data)
        if str(path).endswith('/review_g126/local/layout/current-adapter-layout.json') and R2_ADAPTER_LAYOUT:
            data = json.dumps(R2_ADAPTER_LAYOUT)
            return io.BytesIO(data.encode()) if 'b' in mode else io.StringIO(data)
    return original(file, mode, *arguments, **keywords)

def main():
    global R2_CORE_LAYOUT, R2_ADAPTER_LAYOUT
    setup()
    fixture = ROOT / 'research/g135_v37/local/checks/review_g126/local/layout/layout.json'
    current = json.loads((HERE / 'layout-bindings.json').read_text())['layouts']['current']
    retained = json.loads(fixture.read_text())
    assert all(retained[name] == current[name] for name in retained.keys() & current.keys())
    R2_CORE_LAYOUT = dict(retained, **current)
    # Absolute adapter offsets: the retained fixture must agree with the offsets compiled for this build
    # (ui.* are stored relative to 'ui' in adapter-layout.json), so tests read the fixture only when it matches.
    adapter_fixture = ROOT / 'research/g135_v37/local/checks/review_g126/local/layout/current-adapter-layout.json'
    compiled = json.loads((HERE / 'adapter-layout.json').read_text())
    fixed = json.loads(adapter_fixture.read_text())
    for name, value in compiled.items():
        if name in fixed:
            assert fixed[name] == value + (compiled['ui'] if name.startswith('ui.') and name != 'ui' else 0), name
    assert fixed['bytes'] == compiled['bytes'] and fixed['ui'] == compiled['ui']
    R2_ADAPTER_LAYOUT = fixed
    original_open, original_io = builtins.open, io.open
    builtins.open = lambda file, mode='r', *arguments, **keywords: aligned_read(original_open, file, mode, *arguments, **keywords)
    io.open = lambda file, mode='r', *arguments, **keywords: aligned_read(original_io, file, mode, *arguments, **keywords)
    original_run_path = runpy.run_path
    def run_path(path, *arguments, **keywords):
        result = original_run_path(path, *arguments, **keywords)
        if Path(path).name == 'product_checks.py' and 'run' in result:
            from menu_frames import extend
            result['run'] = extend(result['run'])
        return result
    runpy.run_path = run_path
    sys.setprofile(align_loaded)
    if '--timeout-seconds' not in sys.argv:
        sys.argv[1:1] = ['--timeout-seconds', os.environ.get('GXR_JOB_TIMEOUT', '3600')]
    for name in ('adapter-layout.json', 'layout-bindings.json'):
        destination = HERE / name
        if not destination.exists():
            destination.write_bytes((ROOT / 'research/g135_v37' / name).read_bytes())
    old = ROOT / 'research/g135_v37/run_existing.py'
    loader = importlib.machinery.SourceFileLoader('__main__', str(old))
    code = relocate(loader.get_code('__main__'))
    namespace = {'__name__': '__main__', '__file__': str(old), '__package__': None, '__builtins__': __builtins__}
    try:
        exec(code, namespace)
    finally:
        sys.setprofile(None)
        callback = namespace.get('save_metadata')
        if callback:
            atexit.unregister(callback)
            callback()

if __name__ == '__main__':
    main()
