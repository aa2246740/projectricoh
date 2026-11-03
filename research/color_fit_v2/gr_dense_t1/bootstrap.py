"""Freeze only the host research dependencies inside the task's ignored directory."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import hashlib
import json
import os
import plistlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'
VROOT = LOCAL / 'vendor/repo'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    disk = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['MountPoint'] == '/Volumes/Workspace'
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert disk['FilesystemType'] == 'apfs' and disk['WritableVolume']
    assert os.access('/Volumes/Workspace', os.W_OK)
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    ignore = subprocess.check_output(['git', 'check-ignore', '-v', str(LOCAL / 'probe')], cwd=ROOT, text=True)
    df = subprocess.check_output(['df', '-h', '/Volumes/Workspace'], text=True)
    assert not (LOCAL / 'inputs.json').exists(), 'Snapshot exists; verify it instead of overwriting.'
    inputs = set()
    for folder in ('research/color_fit_v2/gr_round5',):
        inputs.update(p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.json', '.npz'))
    for name in ('common', 'extract', 'models', 'targets', 'refit'):
        inputs.add(ROOT / f'research/gr_pairs/{name}.py')
    for folder in ('models', 'targets', 'fits', 'samples'):
        for p in (ROOT / 'research/gr_pairs/local' / folder).glob('*'):
            if folder != 'samples' or p.stem.startswith(('bastibe_', 'hdf_')):
                if p.suffix in ('.npz', '.json'):
                    inputs.add(p)
    for name in ('protected_before.json', 'inventory.json'):
        inputs.add(ROOT / 'research/gr_pairs/local' / name)
    for name in ('metrics.json', 'REPORT.md'):
        inputs.add(ROOT / 'research/gr_pairs' / name)
    for folder in ('research/contrib_gr_analysis', 'research/color_references', 'research/gr4_modes'):
        inputs.update(p for p in (ROOT / folder).glob('*.py'))
    for name in ('tone_curves.json', 'candidates.json'):
        inputs.add(ROOT / 'research/gr4_modes/local' / name)
    for folder in ('research/color_fit_v2/fuji_round5', 'research/tables_v4'):
        inputs.update(p for p in (ROOT / folder).glob('*.py'))
    for path in (
        'research/color_fit_v2/06_classic_neg/round4/map_channels.py',
        'captures/a12-50/2026-10-19/stage2d-colorchecker/R8051150.DNG',
        'artifacts/downloads/bastibe-gr3/downloads/bastibe_gr3_dng/Target.DNG',
        'artifacts/firmware/gxr-1.51/jlaunch3',
        'artifacts/firmware/gxr-1.51/jlaunch8',
        'firmware/stage2j/tools/deep_sources.py',
        'firmware/stage2j/examples/DEEPISP0.DAT',
        'research/color_calibration/analyze_capture.py',
    ):
        inputs.add(ROOT / path)
    inputs.update(p for p in (ROOT / 'artifacts/stage2j-packages/tables-v5-fuji-test').rglob('*') if p.is_file())
    manifest = {}
    for source in sorted(inputs):
        rel = source.relative_to(ROOT)
        target = VROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha(source)
        if source.suffix == '.py':
            content = source.read_text().replace(str(ROOT), str(VROOT))
            content = content.replace("Path('/tmp/fit_06')", f"Path({str(LOCAL / 'tmp/fit06')!r})")
            content = content.replace("Path('/tmp/gr4modes_work')", f"Path({str(LOCAL / 'tmp/gr4')!r})")
            target.write_text(content)
        else:
            shutil.copyfile(source, target)
        manifest[str(rel)] = {'input_sha256': digest, 'copy_sha256': sha(target),
                              'relocated_module': source.suffix == '.py'}
    (LOCAL / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (LOCAL / 'preflight.json').write_text(json.dumps({'disk': disk, 'df': df, 'ignore': ignore}, default=str, indent=2) + '\n')
    print(json.dumps({'protected_files': len(manifest), 'vendor': str(VROOT)}))


if __name__ == '__main__':
    main()
