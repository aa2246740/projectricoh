"""Read-only R3 review runner. All writes are fenced to this directory.

The supplied scenario recipes are reused unchanged. Their output bindings and
the state comparator are replaced here; the implementation under review is not.
Run with nice -n 15 /usr/bin/python3 -I -B .../review.py COMMAND ...
"""
import argparse
from collections import Counter, deque
import contextlib
import ctypes
import faulthandler
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import signal
import struct
import subprocess
import sys
import time
import traceback
from types import FunctionType

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SCRIPTS = ROOT / 'research/emulator_fast_r1/strict_r2/scripts'
FAST = ROOT / 'tools/gxr_emulator_fast/strict_r2'
LOCAL = OUT / 'local'
RUNS = OUT / 'runs'
TEMP = LOCAL / 'tmp'


def allowed(path):
    if isinstance(path, int):
        return True
    if path is None:
        return False
    return Path(os.fsdecode(path)).resolve().is_relative_to(OUT)


def fence(event, args):
    if event == 'open':
        path, mode, flags = args
        write = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if write and not allowed(path):
            raise PermissionError('R3 write fence: ' + str(path))
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate'):
        if not allowed(args[0]):
            raise PermissionError('R3 mutation fence: ' + str(args[0]))
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        if not all(allowed(p) for p in args[:2]):
            raise PermissionError('R3 rename/link fence: ' + str(args[:2]))
    elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('R3 network fence: ' + event)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    """Independent typed streaming hash; no native hash implementation."""
    h = hashlib.sha256()
    def data(tag, raw=b''):
        h.update(tag.encode('ascii')); h.update(struct.pack('>Q', len(raw))); h.update(raw)
    def visit(v):
        t = type(v)
        if v is None:
            data('none')
        elif t is bool:
            data('bool', bytes([v]))
        elif t is int:
            data('int', bytes([v < 0]) + abs(v).to_bytes((v.bit_length() + 7) // 8, 'big'))
        elif t is str:
            data('str', v.encode('utf-8'))
        elif t in (bytes, bytearray):
            data(t.__name__, v)
        elif t is float:
            data('float', v.hex().encode('ascii'))
        elif t in (dict, Counter):
            data(t.__name__, str(len(v)).encode('ascii'))
            for key in sorted(v, key=lambda k: (type(k).__name__, repr(k))):
                visit(key); visit(v[key])
        elif t in (list, tuple, deque, set, frozenset):
            data(t.__name__, str(len(v)).encode('ascii'))
            if t is deque:
                visit(v.maxlen)
            for item in sorted(v, key=lambda k: (type(k).__name__, repr(k))) if t in (set, frozenset) else v:
                visit(item)
        elif t is FunctionType:
            data('function', v.__qualname__.encode('utf-8'))
            visit(v.__code__.co_code)
            visit(v.__code__.co_names)
        elif t.__name__ in ('UnitLink', 'PreviewLink'):
            data('UnitLink'); visit(v.state())
        else:
            raise TypeError('review hash does not recognize ' + str(t))
    visit(value)
    return h.hexdigest()


def fingerprint(ctx):
    """All RAM/ROM, architecture, models, histories and virtual medium bytes."""
    from ownership import _access
    from backend import REGS
    from devices import Device
    from native_controls import export_controls
    from snapshots import arch_state
    m, c = ctx.machine, ctx.machine.cpu
    c.materialize_native()
    with _access(c):
        devices = {}
        for dev in c.devices:
            if getattr(dev.snapshot, '__func__', None) is Device.snapshot:
                state = {k: v for k, v in vars(dev).items() if k != 'backend'}
            else:
                state = dev.snapshot()
            if type(dev).__name__ == 'SdHost' and state.get('medium_record'):
                state['medium_record']['path'] = '<review-private-medium>'
            devices[type(dev).__name__] = digest(state)
        result = dict(
            steps=c.steps, registers={k: c.get_reg(k) for k in REGS},
            architecture=hashlib.sha256(arch_state(c)).hexdigest(),
            memory=[(base, len(buf), writable, hashlib.sha256(buf).hexdigest())
                    for base, buf, writable in c.regions],
            devices=devices,
            observers=digest([{k: v for k, v in vars(o).items() if k != 'cpu'}
                              for o in c._observer_owners]),
            events=digest([m.events, m.pending_returns, getattr(m, 'return_hooks', set())]),
            panel=digest({k: v for k, v in vars(m.panel).items() if k not in ('cpu', 'devices')}),
            controls=digest(export_controls(m)), trace=digest(c.trace),
            mmio_trace=digest(c.mmio_trace), coverage=digest(c.coverage),
            io_counts=digest(c.io_counts), error=c.error,
            sd_bytes=sha_file(m.sd.medium.path) if m.sd.medium else None)
        flow = getattr(c, '_flow_owner', None)
        if flow is not None:
            result['flow'] = digest({k: v for k, v in vars(flow).items()
                                     if k not in ('cpu', 'machine', 'observer')})
    result['all'] = digest(result)
    return result


def runner():
    sys.path.insert(0, str(SCRIPTS))
    import runner as R
    R.HERE, R.RUNS, R.TEMP, R.ROOT, R.FAST = LOCAL, RUNS, TEMP, ROOT, FAST
    R.fingerprint = fingerprint
    return R


def load_script(name):
    spec = importlib.util.spec_from_file_location('r3_recipe_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def freeze(check=False):
    target = OUT / 'inputs.initial.json'
    if check:
        old = json.loads(target.read_text())
        changes = {p: [h, sha_file(ROOT / p) if (ROOT / p).is_file() else None]
                   for p, h in old['files'].items()
                   if not (ROOT / p).is_file() or sha_file(ROOT / p) != h}
        result = dict(files=len(old['files']), changes=changes, utc=time.strftime('%FT%TZ', time.gmtime()))
        (OUT / 'inputs.final.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result)); return
    paths = set()
    for base in (FAST, ROOT / 'tools/gxr_emulator_fast/fix_r1', ROOT / 'tools/gxr_emulator_batch',
                 ROOT / 'tools/gxr_emulator_standby', SCRIPTS):
        if not base.exists():
            continue
        paths.update(p for p in base.iterdir() if p.is_file())
        paths.update(p for p in (base / 'build').glob('*') if p.is_file() and p.suffix in ('.dylib', '.so', '.json'))
    for base in (ROOT / 'research/review_emulator_fast_r1', ROOT / 'research/review_emulator_fast_r2'):
        paths.update(base / x for x in ('REVIEW.md', 'ADOPTION.md', 'SHA256SUMS'))
        paths.update((base / 'local').glob('*.py'))
    for p in ('research/emulator_fast_r1/REPORT.md',
              'research/emulator_fast_r1/strict_r2/ADOPTION.md',
              'research/emulator_fast_r1/strict_r2/DESIGN.md',
              'tools/native_harness/product_execute.py',
              'research/v310_body/local/50mm-user-settings.bin',
              'research/emulator_m2b/local/nand-reflector.pages.json',
              'research/emulator_m2b/local/unit-info-synthetic.bin',
              'firmware/resident_v310_g155/local/resident/symbols.log',
              'artifacts/downloads/gxr-151.zip'):
        paths.add(ROOT / p)
    for base in ('firmware/package_v310_g155b/local/SD_ROOT', 'firmware/package_v39_g154_looks18_test/local/SD_ROOT'):
        paths.update(ROOT / base / x for x in ('ilaunch3', 'GXRCE.DAT'))
    for name in ('ilaunch3', 'jlaunch3', 'qlaunch3', 'l08firm3'):
        paths.add(ROOT / 'artifacts/firmware/gxr-1.51' / name)
    paths.update((ROOT / 'research/v310_body/fix/emulator').glob('*.py'))
    result = dict(utc=time.strftime('%FT%TZ', time.gmtime()), nice=os.getpriority(os.PRIO_PROCESS, 0),
                  files={str(p.relative_to(ROOT)): sha_file(p) for p in sorted(paths) if p.is_file()})
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(files=len(result['files']), utc=result['utc'])))


def recipe(name, arguments):
    R = runner()
    sys.argv = [str(SCRIPTS / (name + '.py')), *arguments]
    module = load_script(name)
    if hasattr(module, 'HERE'):
        module.HERE = OUT
    if hasattr(module, 'ROOT'):
        module.ROOT = ROOT
    if hasattr(module, 'FAST'):
        module.FAST = FAST
    return module.main() if hasattr(module, 'main') else None


def replay(name, script, arguments):
    R = runner()
    contexts = []
    original = R.construct
    def construct(*args, **kwargs):
        ctx = original(*args, **kwargs); contexts.append(ctx); return ctx
    R.construct = construct
    row = dict(script=script, args=arguments, source_sha256=sha_file(SCRIPTS / (script + '.py')),
               status='ERROR', before_steps=[])
    try:
        recipe(script, ['--name', name, *arguments])
        row['status'] = 'ACCEPTED'
        product = RUNS / (name + '.json')
        if product.exists():
            row['result'] = json.loads(product.read_text())
    except Exception as error:
        row['error'] = dict(type=type(error).__name__, message=str(error))
        if type(error).__name__ in ('NativeContractError', 'NativeStateError') and 'reference' in str(error):
            row['status'] = 'REJECTED'
        else:
            traceback.print_exc()
    row['constructed'] = len(contexts)
    row['steps'] = [ctx.machine.cpu.steps for ctx in contexts]
    # Historical recipes close their machines in finally blocks. Do not call
    # the C stats function on those retired handles; use their saved receipts.
    target = RUNS / (name + '-verdict.json')
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps({k: v for k, v in row.items() if k != 'result'}), flush=True)
    for ctx in contexts:
        try:
            ctx.machine.close()
        except Exception:
            pass
    if row['status'] == 'ERROR':
        raise SystemExit(1)
    # A retained-reference case may execute a legal prefix before the denied
    # mutation. Keep exact steps instead of calling every nonzero count a bug.


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    faulthandler.register(signal.SIGUSR1)
    os.environ['TMPDIR'] = str(TEMP)
    sys.addaudithook(fence)
    cmd, *args = sys.argv[1:]
    if cmd == 'freeze':
        freeze('--check' in args)
    elif cmd == 'recipe':
        recipe(args[0], args[1:])
    elif cmd == 'replay':
        replay(args[0], args[1], args[2:])
    else:
        raise ValueError(cmd)


if __name__ == '__main__':
    main()
