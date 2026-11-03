"""Paths, provenance, and read-only helpers for the offline GR test cards."""
import os
for _name in ('TMPDIR', 'TMP', 'TEMP'):
    os.environ[_name] = str(__import__('pathlib').Path(__file__).resolve().parent / 'local/tmp')
for _name in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[_name] = '1'
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
TMP = LOCAL / 'tmp'
DELIVERY = ROOT / 'artifacts/gr-incamera-dev'
GR3 = ROOT / 'artifacts/downloads/bastibe-gr3/downloads/bastibe_gr3_dng/Target.DNG'
GR4 = ROOT / 'captures/contrib/2026-10-19/gr4-modes/positive.DNG'
MATH = ROOT / 'research/gr_evalsets/local/vendor/gr_complete_pipeline/colour_math_frozen.py'
MODEL = ROOT / 'research/gr_evalsets/local/vendor/gr_complete_pipeline/forward_model_results.json'
DECODER = ROOT / 'research/contrib_gr_analysis/lj92.c'
PY_DECODER = ROOT / 'research/contrib_gr_analysis/lossless_jpeg.py'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def mount_check():
    p = subprocess.run(['diskutil', 'info', '-plist', '/Volumes/Workspace'],
                       check=True, capture_output=True)
    d = plistlib.loads(p.stdout)
    require(d.get('MountPoint') == '/Volumes/Workspace' and d.get('FilesystemType') == 'apfs'
            and d.get('VolumeUUID', d.get('DiskUUID')) == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
            and d.get('WritableVolume') is True, '外置卷身份或可写状态不符')


def sha(path):
    require(Path(path).resolve().is_relative_to(ROOT), '哈希输入越界')
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def output(path, delivery=False):
    require(not LOCAL.is_symlink() and not DELIVERY.is_symlink(), '输出根目录不能是符号链接')
    require(not Path(path).is_symlink(), '输出不能是符号链接')
    p = Path(path).resolve()
    bases = (LOCAL.resolve(), DELIVERY.resolve()) if delivery else (LOCAL.resolve(),)
    require(any(p.is_relative_to(b) for b in bases), f'输出越界: {p}')
    require(not p.exists() or not p.is_symlink(), '不能覆盖符号链接')
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, 'tolist'):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return value


def dump(path, data, delivery=False):
    output(path, delivery).write_text(json.dumps(plain(data), ensure_ascii=False,
                                               indent=2, allow_nan=False) + '\n')


def read(path):
    require(Path(path).resolve().is_relative_to(ROOT), 'JSON 输入越界')
    return json.loads(Path(path).read_text())


def pin(path):
    p = Path(path).resolve()
    # Every source is inside this checkout; a symlink cannot bring in another volume.
    require(p.is_relative_to(ROOT), f'输入不在仓库内: {p}')
    ledger = LOCAL / 'inputs.json'
    saved = read(ledger) if ledger.exists() else {'base': str(ROOT), 'sha256': {}}
    key, digest = relative(p), sha(p)
    require(key not in saved['sha256'] or saved['sha256'][key] == digest, f'输入发生变化: {key}')
    if key not in saved['sha256']:
        saved['sha256'][key] = digest
        dump(ledger, saved)
    return p


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, pin(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def colour():
    return load_module('gr_card_colour_math', MATH)


def binaries():
    TMP.mkdir(parents=True, exist_ok=True)
    result = []
    for source, name in ((HERE / 'sof3.c', 'sof3-encode'), (pin(DECODER), 'lj92-decode')):
        binary = TMP / name
        digest = sha(source)
        stamp = binary.with_suffix('.source-sha256')
        if not binary.exists() or not stamp.exists() or stamp.read_text().strip() != digest:
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(source), '-o', str(binary)], check=True)
            stamp.write_text(digest + '\n')
        result.append(binary)
    return result


def git_status_outside():
    p = subprocess.run(['git', 'status', '--porcelain=v1', '-uall'], cwd=ROOT,
                       check=True, capture_output=True, text=True)
    return [s for s in p.stdout.splitlines()
            if not s[3:].startswith(('research/gr_incamera_dev/', 'artifacts/gr-incamera-dev/'))]


def initialize():
    mount_check()
    require((HERE / '.gitignore').read_text() == 'local/\n', 'research 忽略规则不符')
    require((DELIVERY / '.gitignore').read_text() == '*\n!.gitignore\n', '交付忽略规则不符')
    for p in (LOCAL / 'probe', DELIVERY / 'probe'):
        subprocess.run(['git', 'check-ignore', '-q', str(p)], cwd=ROOT, check=True)
    TMP.mkdir(parents=True, exist_ok=True)
    baseline = LOCAL / 'baseline.json'
    if not baseline.exists():
        files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True,
                               capture_output=True).stdout.decode().split('\0')
        digests = {p: sha(ROOT / p) for p in files if p and (ROOT / p).is_file()
                   and not p.startswith(('research/gr_incamera_dev/', 'artifacts/gr-incamera-dev/'))}
        dump(baseline, {'git_status_outside': git_status_outside(), 'tracked_files': digests})
    for p in (GR3, GR4, MATH, MODEL, DECODER, PY_DECODER,
              ROOT / 'research/contrib_gr_analysis/tiff_makernote.py',
              ROOT / 'artifacts/downloads/calib16/16位校色DNG/使用说明.md',
              ROOT / 'research/gr4_modes/REPORT.md', ROOT / 'research/gr4_modes/gr4io.py',
              ROOT / 'research/contrib_gr_analysis/measure.py',
              ROOT / 'research/color_fit_v2/gr_round5/gr_targets.py',
              ROOT / 'research/color_fit_v2/gr_round5/local/inputs/gr_parameters.json',
              ROOT / 'research/color_fit_v2/gr_round5/local/inputs/gr_metadata.json',
              ROOT / 'research/closed_loop/REPORT.md', ROOT / 'research/closed_loop/targets.py'):
        pin(p)


if __name__ == '__main__':
    initialize()
    print('mount, ignore rules, baseline, input hashes: OK')
