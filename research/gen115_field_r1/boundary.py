"""Host-only evidence boundary. Invoke with python3 -I -B."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
LOCAL.mkdir(exist_ok=True)
(LOCAL / 'tmp').mkdir(exist_ok=True)
for key in ('TMPDIR', 'TMP', 'TEMP', 'MPLCONFIGDIR'):
    os.environ[key] = str(LOCAL / 'tmp')
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
assert info['FilesystemType'] == 'apfs' and info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
assert info['WritableVolume'] and info['WritableMedia']

def audit(event, args):
    if event in ('socket.connect', 'socket.bind'):
        raise PermissionError('HOST ONLY: no network')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if write and not path.is_relative_to(HERE):
            raise PermissionError('write outside task: ' + str(path))
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for value in args[:2] if event == 'os.rename' else args[:1]:
            if isinstance(value, (str, bytes, Path)) and not Path(os.fsdecode(value)).resolve().is_relative_to(HERE):
                raise PermissionError('mutation outside task: ' + str(value))

sys.addaudithook(audit)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def dump(name, data):
    p = LOCAL / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

def frozen_paths():
    names = ['firmware/engine_v36_r28', 'firmware/resident_v34c',
             'research/gr4_lut_ceiling', 'research/module_adapt', 'research/closed_loop',
             'research/refit_50mm_r7', 'research/r28_bank_design', 'artifacts/firmware/gxr-1.51',
             'artifacts/card-b-mount/card-b-after-gen115-test-20261026T084138Z',
             'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z']
    for name in names:
        for p in sorted((ROOT / name).rglob('*')):
            if p.is_file() and p.name != 'decisions.tsv' and '__pycache__' not in p.parts:
                yield p

def freeze():
    path = LOCAL / 'frozen_inputs.json'
    assert not path.exists(), 'existing freeze must be verified, never replaced'
    data = {str(p.relative_to(ROOT)): sha(p) for p in frozen_paths()}
    dump('frozen_inputs.json', data)
    print('frozen', len(data), 'files; decisions.tsv and parallel workers excluded')

def add(path):
    path = Path(path).resolve()
    if path.is_relative_to(HERE):
        return path
    assert path.is_relative_to(ROOT) and path.name != 'decisions.tsv'
    assert not path.is_relative_to(ROOT / 'tools/native_harness')
    assert not path.is_relative_to(ROOT / 'tools/gxr_emulator')
    store = LOCAL / 'frozen_inputs.json'
    data = json.loads(store.read_text())
    key = str(path.relative_to(ROOT)); digest = sha(path)
    if key in data:
        assert data[key] == digest, 'FROZEN INPUT CHANGED: ' + key
    else:
        data[key] = digest
        dump('frozen_inputs.json', data)
    return path

def verify():
    data = json.loads((LOCAL / 'frozen_inputs.json').read_text())
    changed = [p for p, value in data.items() if not (ROOT / p).is_file() or sha(ROOT / p) != value]
    dump('frozen_verification.json', dict(files=len(data), changed=changed, passed=not changed,
         excluded=['**/decisions.tsv', 'tools/native_harness/**', 'tools/gxr_emulator/**']))
    assert not changed, 'STOP FROZEN INPUT CHANGED: ' + repr(changed)
    print('protected inputs unchanged:', len(data))

if __name__ == '__main__':
    {'freeze': freeze, 'verify': verify}[sys.argv[1]]()
