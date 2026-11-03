"""Read-only review helpers with a single output directory."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import fcntl

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TREE = ROOT / 'firmware/engine_v42_ux'
DAT = ROOT / 'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT'
DAT_SHA = '233e23f7b4c9426a267f02fae409d1d580ef940f2b9cccd0379d7f4a479e1607'
START_UTC = '2026-10-27T17:10:47Z'
DEADLINE_UTC = '2026-10-27T20:10:47Z'
sys.dont_write_bytecode = True

def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and (
            isinstance(mode, str) and any(c in mode for c in 'wax+') or
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    elif event in ('socket.connect', 'socket.bind'):
        raise PermissionError('REVIEW_NETWORK_DISABLED')
    for path in paths:
        q = Path(os.fsdecode(path)).resolve()
        if not q.is_relative_to(OUT):
            raise PermissionError('REVIEW_WRITE_FENCE: ' + str(q))

sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(name, value):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    guard = sys.modules.get('runtime_guard')
    if isinstance(value, dict) and guard:
        value = dict(value, native_state_audits=guard.AUDITS)
    if isinstance(value, dict) and REQUEST_SOURCE_SHA:
        value = dict(value, tested_dat_sha256=DAT_SHA,
                     source_script_sha256=REQUEST_SOURCE_SHA)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def result_path():
    name = Path(sys.argv[0]).name
    args = sys.argv[1:]
    if name == 'run_native.py' and len(args) >= 2:
        return 'native/'+args[0]+'-'+args[1]+'.json'
    if name == 'fn2_all.py' and args:
        return 'native/fn2-four-parameters-'+args[0]+'.json'
    if name == 'native_cases.py' and len(args) >= 2 and args[0] == 'h07':
        return 'native/h07-all-'+args[1]+'.json'
    if name == 'fn2_quality.py' and len(args) >= 2:
        group = {'retain':'fn2-retain', 'failures':'fn2-failures', 'measure':'fn2-step-counts'}.get(args[0])
        return 'native/'+group+'-'+args[1]+'.json' if group else None
    single = {'confirm_paths.py':'confirm-paths', 'latch_paths.py':'latch-paths', 'native_names.py':'names'}
    if name in single and args:
        return 'native/'+single[name]+'-'+args[0]+'.json'
    if name == 'entry_switch.py' and len(args) >= 2:
        at = args[args.index('--at')+1] if '--at' in args else '1'
        return 'native/entry-switch-'+args[0]+'-'+args[1]+'-at'+at+'.json'
    if name == 'concurrent_menu.py' and len(args) >= 2:
        extra = ''
        if args[0] == 'other_menu':
            at = args[args.index('--at')+1] if '--at' in args else '1'
            extra = '-at'+at+('-reopen-fn2' if '--reopen-fn2' in args else '')
        return 'native/concurrent_menu-'+args[0]+'-'+args[1]+extra+'.json'
    if name == 'ui_cutpoints.py' and len(args) >= 2:
        return 'native/ui-cutpoint-'+args[0]+'-'+args[1]+'.json'
    if name == 'coalescing.py' and len(args) >= 2:
        at = args[args.index('--at')+1] if '--at' in args else '1'
        return 'native/coalescing-'+args[0]+'-'+args[1]+'-at'+at+'.json'
    if name == 'failure_boundaries.py' and len(args) >= 2:
        return 'native/failure-boundary-'+args[0]+'-at'+args[1]+'.json'
    return None

REQUEST_SOURCE_SHA = None
REQUEST_LOCK = None
REQUEST_RESULT = result_path()
if REQUEST_RESULT:
    assert file_sha(DAT)==DAT_SHA, 'Final DAT identity changed'
    REQUEST_SOURCE_SHA = file_sha(Path(sys.argv[0]))
    lock_dir = OUT/'request-locks'
    lock_dir.mkdir(exist_ok=True)
    key = sha((Path(sys.argv[0]).name+' '+repr(sys.argv[1:])).encode())
    REQUEST_LOCK = (lock_dir/(key+'.lock')).open('a')
    fcntl.flock(REQUEST_LOCK, fcntl.LOCK_EX)
    result_file = OUT/REQUEST_RESULT
    if result_file.exists():
        previous = json.loads(result_file.read_text())
        if (previous.get('status','').startswith('PASS') and
            previous.get('tested_dat_sha256') == DAT_SHA and
            previous.get('source_script_sha256') == REQUEST_SOURCE_SHA):
            print('PASS reuse completed review result', REQUEST_RESULT, flush=True)
            raise SystemExit(0)
