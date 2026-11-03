"""Local review fence and reproducible frozen-input receipts."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import time

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
HERE = ROOT / 'research/review_cpuprobe'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cpuprobe')
OUTPUTS = (HERE, SCRATCH)
INPUTS = (
    'firmware/engine_cpuprobe_v38', 'firmware/package_v38_cpuprobe',
    'research/cpu_speed_probe', 'research/review_lut_p0',
    'research/review_lut_p0_r2', 'research/review_probe_p1',
    'research/review_cpuprobe/basis/body_next_plan-PLAN.md',
    'research/review_cpuprobe/basis/body_next_plan-SHA256SUMS',
    'research/review_cpuprobe/basis/body_next_steps-REPORT.md',
    'research/review_cpuprobe/basis/body_next_steps-SHA256SUMS',
    'research/body_next_steps/tools/dis.py', 'research/body_next_steps/local/dis/ui_recv.txt',
    'research/body_next_steps/local/emulator/stack-fill-r1.json',
    'research/body_next_steps/local/emulator/keys-r1.json',
    'firmware/engine_probe_p1', 'firmware/lut_p0_timing',
    'firmware/resident_v38', 'tools/native_harness',
    'tools/gxr_emulator_batch', 'research/cpu_speed_r1',
    'firmware/package_v36_g121/SD_ROOT/GXRCE.DAT',
    'firmware/package_v38_g137',
    'firmware/engine_v54_g137/candidate/local/full-r13/engine.elf',
    'artifacts/firmware/gxr-1.51/ilaunch3',
    'artifacts/firmware/gxr-1.51/jlaunch3',
    'artifacts/firmware/gxr-1.51/qlaunch3',
    'firmware/package_v36_g120b/SD_ROOT/l08firm3',
    'research/diag147/accept_diag147a.py', 'firmware/engine_v48_own',
)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    p = Path(path).resolve()
    assert any(p == d or d in p.parents for d in OUTPUTS), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fence(event, args):
    paths = []
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(path)).resolve()
            if str(p).startswith('/Volumes/RICOHDCX') or str(p).startswith('/dev/disk') or str(p).startswith('/dev/rdisk'):
                raise PermissionError('DEVICE_READ_DISABLED')
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
                paths.append(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime', 'os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        paths.extend(args[:2])
    elif event.startswith('socket.'):
        raise PermissionError('NETWORK_DISABLED')
    for path in paths:
        p = Path(os.fsdecode(path)).resolve()
        if p != Path('/dev/null') and not any(p == d or d in p.parents for d in OUTPUTS):
            raise PermissionError('REVIEW_WRITE_FENCE: ' + str(p))


def enable_fence():
    sys.dont_write_bytecode = True
    os.environ['TMPDIR'] = str(SCRATCH)
    sys.addaudithook(fence)


def inventory():
    files = {}
    links = {}
    for rel in INPUTS:
        base = ROOT / rel
        if not base.exists():
            raise FileNotFoundError(base)
        for p in sorted(base.rglob('*')) if base.is_dir() else [base]:
            if p.is_symlink():
                links[str(p.relative_to(ROOT))] = os.readlink(p)
            elif p.is_file():
                files[str(p.relative_to(ROOT))] = dict(bytes=p.stat().st_size, sha256=sha(p))
    return dict(files=files, links=links)


def freeze_check():
    baseline = HERE / 'inputs-active.json'
    if not baseline.exists():
        baseline = HERE / 'inputs-before.json'
    before = json.loads(baseline.read_text())
    after = inventory()
    changed = [p for p in sorted(set(before['files']) | set(after['files']))
               if before['files'].get(p) != after['files'].get(p)]
    changed_links = before['links'] != after['links']
    result = dict(files=len(after['files']), bytes=sum(v['bytes'] for v in after['files'].values()),
                  changed=changed, changed_links=changed_links, unchanged=not changed and not changed_links)
    save(HERE / 'inputs-after.json', result)
    if not result['unchanged']:
        raise RuntimeError(result)
    return result


if __name__ == '__main__':
    enable_fence()
    started = time.monotonic()
    if sys.argv[1:] == ['freeze']:
        result = inventory()
        save(HERE / 'inputs-before.json', result)
        print(json.dumps(dict(files=len(result['files']), bytes=sum(v['bytes'] for v in result['files'].values()), seconds=time.monotonic()-started)))
    elif sys.argv[1:] == ['check']:
        print(json.dumps(freeze_check()))
    else:
        raise SystemExit('use freeze or check')
