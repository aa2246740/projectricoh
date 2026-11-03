"""Generation 123 paths and a process-local write fence."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import fcntl

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
TREE = ROOT / 'firmware/engine_v45_verify'
PACKAGE = ROOT / 'firmware/package_v36_g123'
DAT = PACKAGE / 'SD_ROOT/GXRCE.DAT'
BASE_DAT = ROOT / 'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT'
DAT_SHA = hashlib.sha256(DAT.read_bytes()).hexdigest() if DAT.exists() else ''
START_UTC = '2026-10-28T07:57:05Z'
DEADLINE_UTC = '2026-10-28T10:27:05Z'
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
        raise PermissionError('NETWORK_DISABLED')
    for path in paths:
        q = Path(os.fsdecode(path)).resolve()
        if not any(q.is_relative_to(root) for root in (OUT, TREE, PACKAGE)):
            raise PermissionError('WRITE_FENCE: ' + str(q))

sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    return sha(Path(path).read_bytes())

def command_lock(label):
    folder = OUT / 'locks'
    folder.mkdir(exist_ok=True)
    stream = (folder / (label + '.lock')).open('a')
    fcntl.flock(stream, fcntl.LOCK_EX)
    return stream

def save(name, value):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    guard = sys.modules.get('runtime_guard')
    if isinstance(value, dict) and guard:
        value = dict(value, native_state_audits=guard.AUDITS)
        value['communication_range_audits'] = guard.RPC_AUDITS
    body=json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if p.exists() and p.read_text()!=body:
        history=OUT/'local/history/generated-output-history';history.mkdir(exist_ok=True)
        old=p.read_bytes()
        (history/(p.stem+'-'+sha(old)[:16]+p.suffix)).write_bytes(old)
    p.write_text(body)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def record_command():
    """Serialize equal native commands and retain their completed execution."""
    script=Path(sys.argv[0]).resolve()
    allowed={'run_native.py','native_cases.py','fn2_quality.py','confirm_paths.py',
             'latch_paths.py','native_names.py','entry_switch.py','concurrent_menu.py',
             'ui_cutpoints.py','coalescing.py','failure_boundaries.py'}
    if script.parent!=OUT or script.name not in allowed or not DAT.exists():return
    import atexit
    parts=[script.name,*sys.argv[1:]]
    identity=sha(json.dumps(parts).encode())[:24]
    held=command_lock('execution-'+identity)
    dependencies=sorted({script.name,'common.py','runtime_guard.py','run_native.py',
        'native_ux.py','native_cases.py','native_exits.py','ui_trace_scope.py','key_probe.py','native_sequence.py'})
    def source_key():
        digest=hashlib.sha256()
        for name in dependencies:
            digest.update(name.encode());digest.update((OUT/name).read_bytes())
        return digest.hexdigest()
    key=source_key();pin=file_sha(DAT)
    folder=OUT/'command-records';folder.mkdir(exist_ok=True)
    path=folder/(identity+'.json')
    if path.exists():
        previous=json.loads(path.read_text())
        if previous.get('exit_status')==0 and previous.get('dat_sha256')==pin and previous.get('source_sha256')==key:
            print('REUSE completed command, fixed DAT and sources',parts,flush=True)
            raise SystemExit(0)
    result={'exit_status':0}
    original_hook=sys.excepthook
    def failed(kind,value,trace):
        result['exit_status']=1
        return original_hook(kind,value,trace)
    sys.excepthook=failed
    original_exit=sys.exit
    def exiting(code=None):
        if code not in (None,0):result['exit_status']=1
        original_exit(code)
    sys.exit=exiting
    def finished():
        stable=file_sha(DAT)==pin and source_key()==key
        value=dict(command=parts,dat_sha256=pin,source_sha256=key,
            exit_status=result['exit_status'] if stable else 'INPUT_CHANGED',
            dependencies=dependencies,process=os.getpid())
        body=json.dumps(value,indent=2)+'\n'
        if path.exists() and path.read_text()!=body:
            history=OUT/'history/command-records';history.mkdir(parents=True,exist_ok=True)
            old=path.read_bytes();(history/(identity+'-'+sha(old)[:16]+'.json')).write_bytes(old)
        path.write_text(body)
        held.close()
    atexit.register(finished)

record_command()
