#!/usr/bin/env python3
"""Write fence, input ledger, and redirected reuse of the existing card tools."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = LOCAL / 'tmp'
ARTIFACTS = ROOT / 'artifacts/gr-dense-reference'
PROTECTED = ('captures', 'research/gr_incamera_dev', 'research/gr_pairs',
             'research/hue_ring', 'artifacts/downloads')

import hashlib
import json
import os
import subprocess


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ignored(path):
    return subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT,
                          capture_output=True).returncode == 0


def delivery():
    return ARTIFACTS if ignored(ARTIFACTS / 'probe.DNG') else LOCAL / 'public'


def allowed(path):
    p = Path(path).resolve()
    roots = (HERE.resolve(),)
    if ignored(ARTIFACTS / 'probe.DNG'):
        roots += (ARTIFACTS.resolve(),)
    require(any(p.is_relative_to(r) for r in roots), f'write outside task: {p}')
    require(not Path(path).is_symlink(), f'output symlink: {path}')
    return p


def guard():
    # Child encoders receive only checked input/output arguments and this TMPDIR.
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        os.environ[key] = str(TMP)
    for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[key] = '1'
    def audit(event, args):
        if event == 'open':
            path, mode, flags = args
            if isinstance(path, (str, bytes, os.PathLike)) and (
                (mode and any(c in mode for c in 'wax+')) or
                (flags and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            ):
                allowed(os.fsdecode(path))
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate'):
            allowed(args[0])
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            allowed(args[0]); allowed(args[1])
    sys.addaudithook(audit)


def sha(path):
    p = Path(path).resolve()
    require(p.is_relative_to(ROOT), 'hash input outside checkout')
    digest = hashlib.sha256()
    with p.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, 'tolist'):
        return value.tolist()
    return value


def dump(path, value):
    p = allowed(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2,
                            allow_nan=False) + '\n')


def legacy():
    sys.path.insert(0, str(ROOT / 'research/gr_incamera_dev'))
    import common
    common.mount_check()
    require((HERE / '.gitignore').read_text() == 'local/\n', 'local ignore rule missing')
    require(ignored(LOCAL / 'probe'), 'local data is not ignored')
    require(not LOCAL.is_symlink(), 'local root is a symlink')
    common.LOCAL, common.TMP, common.DELIVERY = LOCAL, TMP, delivery()
    # Keep common.HERE at its original source directory for sof3.c. No old entrypoint runs.
    guard()
    TMP.mkdir(parents=True, exist_ok=True)
    return common


def tree(folder):
    base = ROOT / folder
    require(base.is_dir(), f'protected tree missing: {folder}')
    result = {}
    for p in sorted(base.rglob('*')):
        if p.is_file():
            require(p.resolve().is_relative_to(ROOT), f'input symlink leaves checkout: {p}')
            result[str(p.relative_to(ROOT))] = dict(sha256=sha(p), size=p.stat().st_size,
                link=os.readlink(p) if p.is_symlink() else None)
        elif p.is_symlink():
            result[str(p.relative_to(ROOT))] = dict(link=os.readlink(p))
    return result


def snapshot():
    legacy()
    ledger = LOCAL / 'protected.json'
    require(not ledger.exists(), 'baseline already exists; refusing to reset it')
    files = {folder: tree(folder) for folder in PROTECTED}
    tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True,
                             capture_output=True).stdout.decode().split('\0')
    hashes = {p: sha(ROOT / p) for p in tracked if p and (ROOT / p).is_file()
              and not p.startswith('research/gr_dense_reference/')}
    dump(ledger, dict(schema='gr-dense-protected/1', trees=files, tracked=hashes,
        artifacts_ignored=ignored(ARTIFACTS / 'probe.DNG'), checksum_base=str(ROOT)))
    print(json.dumps(dict(protected_files={k: len(v) for k, v in files.items()},
                         tracked_files=len(hashes), delivery=str(delivery()))))


def preservation(strict_workspace=False):
    base = read(LOCAL / 'protected.json')
    counts = {}
    for folder, before in base['trees'].items():
        require(tree(folder) == before, f'protected tree changed: {folder}')
        counts[folder] = len(before)
    outside_changes = []
    for name, digest in base['tracked'].items():
        actual = sha(ROOT / name) if (ROOT / name).is_file() else None
        if actual != digest:
            outside_changes.append(dict(path=name, before=digest, after=actual))
    for name, digest in read(LOCAL / 'inputs.json')['sha256'].items():
        require(sha(ROOT / name) == digest, f'reused input changed: {name}')
    require(not strict_workspace or not outside_changes, 'outside tracked files changed: ' +
            ', '.join(p['path'] for p in outside_changes))
    return dict(protected_files=counts, tracked_files=len(base['tracked']),
                reused_inputs=len(read(LOCAL / 'inputs.json')['sha256']),
                outside_tracked_unchanged=not outside_changes, outside_changes=outside_changes)


if __name__ == '__main__':
    require(sys.argv[1:] == ['snapshot'], 'usage: python3 -I -B dense.py snapshot')
    snapshot()
