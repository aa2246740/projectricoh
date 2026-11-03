"""Read-only inputs and review-local outputs for the independent g155c review."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import fcntl
import shlex
import struct
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / 'research/tweak_memory_r1'
TMP = HERE / 'tmp'
EXPECTED = {
    'test': 'c3017d3663e9501b43c921e3b46333b74d751eaa170781c4e1a00d90118f0335',
    'release': '69fa85104fcb449e613950bb58c802b9b64464769ae524fe3f7303e06093c2ad',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_info(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=digest(raw))


def guard(event, args):
    if event == 'socket.connect':
        raise PermissionError('This review is offline')
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and (
            (isinstance(mode, str) and any(c in mode for c in 'wax+')) or
            (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        ):
            paths = [path]
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate'):
        paths = [args[0]]
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths = list(args[:2])
    for path in paths:
        if isinstance(path, (str, bytes, os.PathLike)):
            target = Path(os.fsdecode(path)).resolve()
            if target == Path('/dev/null'):
                continue
            if not target.is_relative_to(HERE):
                raise PermissionError('Write outside review directory: ' + str(target))


assert os.getpriority(os.PRIO_PROCESS, 0) >= 15, 'Use nice -n 15'
sys.dont_write_bytecode = True
sys.addaudithook(guard)
for directory in (TMP, HERE/'local', HERE/'evidence'):
    directory.mkdir(exist_ok=True)
process_rows = []
for line in subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines():
    fields = line.strip().split(None,1)
    if len(fields)!=2:
        continue
    pid,command=fields
    parts=command.split()
    if (int(pid)!=os.getpid() and parts and Path(parts[0]).name.lower().startswith('python') and
        any('research/review_g155c_r1/' in part for part in parts[1:5])):
        process_rows.append(dict(pid=int(pid),command=command))
assert len(process_rows)<2, ('Two review processes already active',process_rows)
_slot = None
for index in range(2):
    candidate=(HERE/('process-slot-'+str(index)+'.lock')).open('a+')
    try:
        fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        candidate.close()
        continue
    _slot=candidate
    break
assert _slot is not None, 'Both review slots are occupied'
with (HERE/'evidence/process-starts.jsonl').open('a') as stream:
    stream.write(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),
                                argv=sys.argv,nice=os.getpriority(os.PRIO_PROCESS,0),
                                other_review_processes=process_rows))+'\n')
os.environ['TMPDIR'] = str(TMP)
os.environ['CLANG_MODULE_CACHE_PATH'] = str(TMP/'clang-modules')
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
os.environ['GXR_HARNESS_BACKEND'] = 'c'


def save(name, value):
    path = HERE/'evidence'/(name+'.json')
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(name=name, status=value.get('status'), rows=len(value.get('rows', []))), ensure_ascii=False), flush=True)


def runtime():
    # Install the retained model from its original read-only location first.
    # Redirect every writable Runtime destination before constructing a Machine.
    sys.path.insert(0, str(PRIOR))
    import runtime as module
    module.models()
    module.models = lambda: None
    original_load = module.load_snapshot
    def load_review_snapshot(path):
        saved = original_load(path)
        for kind, device in zip(saved['cpu']['device_types'], saved['cpu']['devices']):
            if kind != 'SdHost' or not device.get('medium_record'):
                continue
            record = device['medium_record']
            old = Path(record['path'])
            if not old.exists() or digest(old.read_bytes()) != record['sha256']:
                retained = PRIOR/'local/media'/(record['sha256']+'.img')
                assert digest(retained.read_bytes()) == record['sha256']
                device['medium_record'] = dict(record, path=str(retained))
        return saved
    module.load_snapshot = load_review_snapshot
    module.HERE = HERE
    module.TEMP = TMP
    return module


RT = None


def snapshot(path):
    global RT
    if RT is None:
        RT = runtime()
    return RT.load_snapshot(Path(path))


def backends():
    sys.path.insert(0, str(ROOT/'tools/native_harness_c'))
    import python_backend as pb
    pb.CACHE = TMP/'decode'/str(os.getpid())
    return [('c', pb.PythonBackend), ('python', pb.PurePythonBackend)]


def cpu_for(saved, Backend):
    b = Backend()
    state = saved['cpu']
    regs = state['registers']
    for at, raw, writable in state['regions']:
        b.map(at, raw, writable)
    for name in ('psw', 'spi', 'spu', 'bpc', 'bbpc', 'evb', *[f'r{i}' for i in range(16)]):
        b.set_reg(name, regs[name])
    if 'acch' in regs:
        b.set_reg('acc', (regs['acch']<<32)|regs['accl'])
    return b


def mem(saved, at, length):
    for base, raw, _ in reversed(saved['cpu']['regions']):
        if base <= at and at+length <= base+len(raw):
            return bytes(raw[at-base:at-base+length])
    raise ValueError(hex(at))


def word(saved, at, length=4):
    return int.from_bytes(mem(saved, at, length), 'big')


def dat(profile):
    path = ROOT/'firmware'/('package_v310_g155c_test' if profile == 'test' else 'package_v310_g155c')/'GXRCE.DAT'
    raw = path.read_bytes()
    assert digest(raw) == EXPECTED[profile]
    return raw


def bind(saved, profile='test', mutable=()):
    raw = dat(profile)
    assert saved['dat_sha256'] == digest(raw)
    base = word(saved, 0x20054770)-int.from_bytes(raw[132:136], 'big')
    relocated = bytearray(raw)
    start, length = struct.unpack_from('>II', raw, 144)
    for at in range(start, start+length, 8):
        patch, rel = struct.unpack_from('>II', raw, at)
        struct.pack_into('>I', relocated, patch, base+rel)
    actual = bytearray(mem(saved, base, len(raw)))
    differences = [i for i, (a, b) in enumerate(zip(actual, relocated)) if a != b]
    allowed = {at for start, length in mutable for at in range(start, start+length)}
    assert set(differences) <= allowed, ('loaded DAT mismatch', differences[:20])
    return base, dict(dat_sha256=digest(raw), loaded_base=hex(base), bytes=len(raw),
                      relocation_count=length//8, mutable_byte_differences=differences)
