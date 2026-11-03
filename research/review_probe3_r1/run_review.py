"""Read-only probe3 review. All writes and temporary files stay in this directory."""
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
REVIEW = Path(__file__).resolve().parent
LOCAL = REVIEW / 'local'
TMP = LOCAL / 'tmp'
SOURCE = ROOT / 'research/probe_pack_r3'
PACKAGE = ROOT / 'firmware/package_v39_g154_probe3'
sys.dont_write_bytecode = True

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def fence(event, args):
    def check(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        resolved = Path(os.fsdecode(path)).resolve()
        if resolved != REVIEW and REVIEW not in resolved.parents:
            raise PermissionError('Review write fence: ' + str(resolved))
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)):
            resolved = Path(os.fsdecode(path)).absolute()
            if str(resolved).startswith('/Volumes/') and not str(resolved).startswith('/Volumes/Workspace/'):
                raise PermissionError('Other volumes forbidden: ' + str(resolved))
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
            check(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'):
        check(args[0])
    elif event in ('os.rename', 'os.replace'):
        check(args[0]); check(args[1])
    elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        raise PermissionError('Review forbids network')

def guard(*args, **kwargs):
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 15
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(TMP), PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0',
        CLANG_MODULE_CACHE_PATH=str(TMP / 'clang'), OPENBLAS_NUM_THREADS='1',
        OMP_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', MPLCONFIGDIR=str(TMP / 'mpl'))

def setup():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume'] and os.path.ismount('/Volumes/Workspace')
    guard()
    sys.addaudithook(fence)
    sys.path.insert(0, str(SOURCE))
    import common
    common.TMP = TMP
    common.guard = guard
    return common

def freeze_inputs():
    prior = json.loads((SOURCE / 'local/frozen-inputs.json').read_text())
    paths = {ROOT / name for name in prior}
    for folder in (SOURCE, PACKAGE, ROOT / 'research/review_probe2_r1',
                   ROOT / 'research/probe_pack_r2', ROOT / 'research/g154_looks_r1',
                   ROOT / 'tools/native_harness_c', ROOT / 'tools/gxr_emulator_fast/strict_r2'):
        paths.update(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.update(ROOT / name for name in ('research/v39_g153/dat_format.py',
        'research/v39_g153/format_checks.py', 'research/v39_g153/tests/v39_host.py',
        'research/probe_pack_r1/field_20261103.py', 'research/probe_pack_r1/local/ramp_field_20261103/measure-0.5.json',
        'research/probe_pack_r2/local/field_probe2_20261103/measure-0.5.json'))
    values = {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}
    save(LOCAL / 'inputs-before.json', values)
    save(LOCAL / 'session.json', dict(nice=os.getpriority(os.PRIO_PROCESS, 0),
        max_compute_jobs=2, no_network=True, write_root=str(REVIEW), files=len(values),
        body_sha256=digest(ROOT / 'firmware/package_v39_g154_looks18_test/local/SD_ROOT/ilaunch3'),
        dat_sha256=digest(PACKAGE / 'local/SD_ROOT/GXRCE.DAT'),
        zip_sha256=digest(PACKAGE / 'local/GXR-probe3.zip')))
    print(json.dumps(dict(frozen_files=len(values))))

def main():
    setup()
    mode = sys.argv[1]
    if mode == 'freeze':
        freeze_inputs(); return
    if mode == 'stability':
        before = json.loads((LOCAL / 'inputs-before.json').read_text())
        supplemental = LOCAL / 'supplementary-inputs.json'
        if supplemental.exists():
            for name, value in json.loads(supplemental.read_text()).items():
                if name in before: assert before[name] == value
                before[name] = value
        after = {name: digest(ROOT / name) for name in before}
        changed = [name for name in before if before[name] != after[name]]
        save(LOCAL / 'inputs-after.json', after)
        save(LOCAL / 'input-stability.json', dict(status='PASS' if not changed else 'FAIL', files=len(before), changed=changed))
        assert not changed, changed
        print(json.dumps(dict(unchanged_files=len(before)))); return
    if mode == 'build':
        module = load(SOURCE / 'build.py', 'probe3_review_build')
        module.HERE = LOCAL / 'rebuild'
        module.TMP = TMP
        module.PACKAGE = LOCAL / 'rebuild/package'
        module.guard = guard
        module.main()
        matches = []
        for name in ('SD_ROOT/GXRCE.DAT', 'build/engine.bin', 'build/reloc.bin', 'build/trust.bin'):
            got = (module.PACKAGE / 'local' / name).read_bytes()
            wanted = (PACKAGE / 'local' / name).read_bytes()
            assert got == wanted, name
            matches.append(dict(path=name, bytes=len(got), sha256=sha(got)))
        save(LOCAL / 'rebuild-comparison.json', dict(status='PASS', matches=matches))
        print(json.dumps(dict(status='PASS', identical_files=len(matches)))); return
    restoring = mode.startswith('restore-')
    if restoring:
        mode = mode[len('restore-'):]
    paths = dict(host='host_checks.py', native='local/native_from_cold.py',
                 unit='local/unit_checks.py', codec='python_checks.py', response='response_checks.py')
    module = load(SOURCE / paths[mode], 'probe3_review_' + mode)
    module.HERE = REVIEW
    module.TMP = TMP
    module.guard = guard
    if restoring:
        module.PACKAGE = ROOT / 'firmware/package_v39_g154_looks18_test'
    (REVIEW / 'evidence').mkdir(exist_ok=True)
    if not (REVIEW / 'evidence/build.json').exists():
        (REVIEW / 'evidence/build.json').write_bytes((SOURCE / 'evidence/build.json').read_bytes())
    assert (LOCAL / 'expected.json').exists(), 'Run static_review.py first'
    sys.argv = [str(SOURCE / paths[mode])] + sys.argv[2:]
    module.main()

if __name__ == '__main__':
    main()
