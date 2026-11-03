#!/usr/bin/env python3
"""Freeze the read-only numerical and loader inputs inside this round."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'
VENDOR = LOCAL / 'vendor'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    d = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert d['MountPoint'] == '/Volumes/Workspace' and d['FilesystemType'] == 'apfs'
    assert d['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert d['WritableVolume'] and d['WritableMedia'] and os.access('/Volumes/Workspace', os.W_OK)
    subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True)
    subprocess.run(['git', 'check-ignore', '-v', str(LOCAL / 'guard')], cwd=ROOT, check=True)
    (LOCAL / 'tmp').mkdir(parents=True, exist_ok=True)
    records = {}

    def copy(src, dest, transform=False):
        src = ROOT / src if not isinstance(src, Path) else src
        dest.parent.mkdir(parents=True, exist_ok=True)
        st = src.stat()
        records[str(src.relative_to(ROOT))] = dict(sha256=sha(src), bytes=st.st_size,
                                                   mtime_ns=st.st_mtime_ns, mode=st.st_mode)
        if transform:
            text = src.read_text().replace(str(ROOT / 'research/closed_loop/local/vendor'), str(VENDOR))
            text = re.sub(r'^ROOT\s*=.*$', f'ROOT = Path({str(ROOT)!r})', text, flags=re.M)
            dest.write_text(text)
        else:
            dest.write_bytes(src.read_bytes())

    original = ROOT / 'research/closed_loop/local/vendor'
    for p in sorted(original.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            copy(p, VENDOR / p.relative_to(original), p.suffix == '.py')
    for name in ('common.py', 'model.py', 'refit.py'):
        copy('research/closed_loop/' + name, VENDOR / name)
    # common's helpers use this round's copies and refuse all other output paths.
    c = VENDOR / 'common.py'
    text = c.read_text().replace('HERE = Path(__file__).resolve().parent', f'HERE = Path({str(HERE)!r})')
    text = re.sub(r'^ROOT\s*=.*$', f'ROOT = Path({str(ROOT)!r})', text, flags=re.M)
    c.write_text(text)
    for p in sorted((ROOT / 'firmware/stage2j').rglob('*')):
        if p.is_file() and p.suffix in ('.c', '.h'):
            copy(p, VENDOR / p.relative_to(ROOT))
    copy('research/t1_probe/build_validate.py', VENDOR / 'host.py')
    files = [
        'research/closed_loop/local/m20261021_r1_screen_refit_gr.json',
        'research/closed_loop/local/m20261021_r1_gr.json',
        'research/closed_loop/local/gr_targets_20261021_r1.json',
        'research/color_fit_v2/gr_round5/local/fit_01_r5.json',
        'research/color_fit_v2/gr_round5/local/fit_02_r5.json',
        'research/color_fit_v2/gr_round5/local/inputs/state01.json',
        'research/color_fit_v2/gr_round5/local/inputs/state02.json',
        'research/color_fit_v2/gr_round5/local/generated_01_200.npz',
        'research/color_fit_v2/gr_round5/local/generated_02_200.npz',
        'research/color_fit_v2/gr_round5/local/inputs/curves_source.json',
        'research/color_fit_v2/gr_round5/local/inputs/relative_photo.json',
        'research/hue_ring/local/ring_model_v2.json',
        'research/hue_ring/local/ring_model_v2_iso1600.json',
        'research/color_fit_v2/06_classic_neg/round4/local/cache/data_200.npz',
        'research/color_fit_v2/06_classic_neg/round4/local/cache/data_1600.npz',
        'firmware/stage2j/examples/DEEPISP0.DAT',
        'firmware/stage2h/examples/tables/equal-2g/DEEPTBL0.DAT',
    ]
    files += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'artifacts/stage2j-packages/tables-v4r3-noprobe').rglob('*')) if p.is_file()]
    for rel in files:
        copy(rel, LOCAL / 'inputs' / rel)
    original_manifest = json.loads((ROOT / 'research/closed_loop/local/vendor_manifest.json').read_text())
    (LOCAL / 'vendor_manifest.json').write_text(json.dumps({
        'original_closed_loop_manifest': original_manifest,
        'copies_sha256': {str(p.relative_to(LOCAL)): sha(p) for p in sorted(VENDOR.rglob('*')) if p.is_file()},
        'adaptation': 'ROOT and closed_loop vendor import paths rebound; common HERE rebound; algorithms unchanged.'
    }, indent=2) + '\n')
    (LOCAL / 'inputs_before.json').write_text(json.dumps(records, indent=2) + '\n')
    (LOCAL / 'git_before.z').write_bytes(subprocess.check_output(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=ROOT))
    (LOCAL / 'volume.json').write_text(json.dumps({k:d[k] for k in ['MountPoint','FilesystemType','VolumeUUID','WritableVolume','WritableMedia']}, indent=2)+'\n')
    print(f'Frozen {len(records)} inputs; all derived bytes are ignored.')


if __name__ == '__main__':
    main()
