"""Read-only input access and review-scoped native replay support."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
MATERIALS = ROOT / 'research/g122_keep_list'
TREE = ROOT / 'firmware/engine_v44_keep'
DAT = ROOT / 'firmware/package_v36_g122/SD_ROOT/GXRCE.DAT'
ELF = TREE / 'candidate/local/full-r13/engine.elf'
BASE_DAT = ROOT / 'firmware/package_v36_g121/SD_ROOT/GXRCE.DAT'
BASE_ELF = ROOT / 'firmware/engine_v43_fix/candidate/local/full-r13/engine.elf'
BODY = ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3'
PIN = '9724268c3d8a2c8c60650b903db1d536ca6ab594f95144d5991cb3b964ebb262'
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
    elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('REVIEW_NETWORK_DISABLED')
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if not p.is_relative_to(OUT):
            raise PermissionError('REVIEW_WRITE_FENCE: ' + str(p))

sys.addaudithook(fence)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    return sha(Path(path).read_bytes())

def save(name, value):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def inputs():
    paths = {DAT, ELF, BASE_DAT, BASE_ELF, BODY,
             ROOT / 'firmware/resident_v36/local/resident/build/resident.elf'}
    for tree in (TREE / 'candidate/containers/product', TREE / 'candidate/engine_services',
                 ROOT / 'firmware/engine_v43_fix/candidate/containers/product',
                 ROOT / 'firmware/engine_v43_fix/candidate/engine_services',
                 ROOT / 'tools/native_harness'):
        paths.update(p for p in tree.rglob('*') if p.is_file() and
                     'local' not in p.relative_to(tree).parts and p.suffix in ('.c', '.h', '.S', '.ld', '.py'))
    paths.update(p for p in MATERIALS.iterdir() if p.is_file() and p.suffix in ('.py', '.json', '.patch', '.md', '.txt'))
    paths.update(p for p in (MATERIALS / 'compiled').glob('*.txt'))
    return {str(p.relative_to(ROOT)): file_sha(p) for p in sorted(paths)}

def setup(generation=122, unit='50mm', tag='review'):
    assert file_sha(DAT) == PIN and DAT.stat().st_size == 63380
    sys.path.insert(0, str(MATERIALS))
    ux = load(MATERIALS / 'native_ux.py', 'review_native_ux')
    ux.configure(False, tag)
    m, fr, pe, v = ux.m, ux.fr, ux.pe, ux.v
    dat, elf = (DAT, ELF) if generation == 122 else (BASE_DAT, BASE_ELF)
    m.DAT = dat
    m.OUT = OUT / 'local/runtime'
    ux.OUT = OUT / 'local/runtime'
    pe.STAGED, pe.STAGED_SHA, pe.ENGINE_ELF = dat, file_sha(dat), elf
    v.python_backend.CACHE = OUT / 'local/decode' / (str(generation) + '-' + unit)
    original_symbol = m.Product.symbol_pc
    def symbol(self, name):
        actual = next((x for x in (name, name + '.constprop.0', name + '.lto_priv.0') if x in self.elf.symbols), name)
        return original_symbol(self, actual)
    m.Product.symbol_pc = symbol
    m.OUT.mkdir(parents=True, exist_ok=True)
    return ux, m, fr, pe, v

def ui_audit(h):
    scope = load(MATERIALS / 'ui_trace_scope.py', 'review_ui_scope')
    writes = [x for x in h.writes if any(int(x['address'], 16) < hi and
              int(x['address'], 16) + x['size'] > lo for lo, hi, *_ in scope.UI_RANGES)]
    bad = [x for x in writes if x['origin'] not in ('cpu', 'model:native_memset')]
    return dict(watched=len(writes), host_ui_writes=len(bad), bad=bad,
                getter_callback_present=0x20271fec in h.b.breakpoints)

def record_command():
    path = OUT / 'commands.jsonl'
    with path.open('a') as stream:
        stream.write(json.dumps(dict(argv=['/usr/bin/python3', '-I', '-B', *sys.argv],
                                    cwd=str(ROOT))) + '\n')

record_command()
