#!/usr/bin/env python3
"""Freeze trusted helpers and hash read-only inputs. Run with python3 -I -B."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
DATA = ROOT / 'captures/contrib/2026-10-21-evalsets'
VOLUME_UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'

VENDOR = [
    'research/contrib_gr_analysis/tiff_makernote.py',
    'research/contrib_gr_analysis/lossless_jpeg.py',
    'research/contrib_gr_analysis/measure.py',
    'research/contrib_gr_analysis/lj92.c',
    'research/gr4_modes/gr4io.py',
    'research/gr_complete_pipeline/colour_math_frozen.py',
    'research/gr_complete_pipeline/pipeline_math.py',
    'research/gr_complete_pipeline/reference_tiff_frozen.py',
    'research/gr_complete_pipeline/arm_gamma_model.py',
    'research/gr_complete_pipeline/arm_gamma_inspect.py',
    'research/gr_complete_pipeline/forward_model.py',
    'research/gr_complete_pipeline/forward_model_results.json',
    'research/gr_complete_pipeline/reference_metadata.json',
    'research/gr_complete_pipeline/gr3_gr4_effective_curves.json',
    'research/color_references/gr3_reference_measurements.json',
    'research/gr_firmware/data/gr3-2.10-tables.json',
    'research/gr_ae_target/local/gr3_center_weights.npy',
    'research/gr_ae_target/local/gr3_ae_spatial_tables.npz',
    'research/gr_ae_target/local/inputs/gr3-2.10/fwdc239b.bin.decoded',
    'research/color_fit_v2/gr_round5/local/inputs/state01.json',
    'research/color_fit_v2/gr_round5/local/inputs/state02.json',
]
DOCUMENTS = [
    'research/gr_ae_target/REPORT.md', 'research/gr_metering_anchor/REPORT.md',
    'research/gr_complete_pipeline/REPORT.md',
    'research/color_fit_v2/gr_round5/gr_targets.py',
    'research/color_fit_v2/gr_round5/REPORT.md',
]


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def gate():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info.get('MountPoint') == '/Volumes/Workspace'
    assert info.get('VolumeUUID') == VOLUME_UUID
    assert info.get('FilesystemType') == 'apfs' and info.get('WritableVolume') is True
    assert os.access('/Volumes/Workspace', os.W_OK)
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    result = subprocess.check_output(['git', 'check-ignore', '-v', 'research/gr_evalsets/local/probe'], cwd=ROOT, text=True)
    assert 'research/gr_evalsets/.gitignore:1:local/' in result
    return info, result.strip()


def check_data_manifest():
    checked = []
    for line in (DATA / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = (DATA / name).resolve()
        assert path.is_relative_to(DATA.resolve()) and path.is_file()
        assert not (DATA / name).is_symlink() and sha(path) == digest, name
        checked.append(path)
    assert len(checked) == 18
    actual = {p.resolve() for p in DATA.rglob('*') if p.is_file() and p.name not in ('README.md', 'SHA256SUMS')}
    extras = actual - set(checked)
    assert all(p.parent == DATA / 'thumbs' and p.suffix == '.JPG' for p in extras), 'unexpected unlisted input files'
    return checked + sorted(extras)


def main():
    info, ignored = gate()
    paths = check_data_manifest() + [DATA / 'README.md', DATA / 'SHA256SUMS']
    paths += [ROOT / p for p in VENDOR + DOCUMENTS]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    LOCAL.mkdir(exist_ok=True)
    (LOCAL / 'tmp').mkdir(exist_ok=True)
    snapshot = LOCAL / 'inputs.sha256.json'
    if snapshot.exists():
        previous = json.loads(snapshot.read_text())
        assert all(hashes.get(k) == v for k, v in previous.items()), 'inputs changed since initial snapshot'
        snapshot.write_text(json.dumps(hashes, indent=2, ensure_ascii=False) + '\n')
    else:
        snapshot.write_text(json.dumps(hashes, indent=2, ensure_ascii=False) + '\n')
        (LOCAL / 'git-status-before.txt').write_text(subprocess.check_output(
            ['git', 'status', '--short', '--untracked-files=normal'], cwd=ROOT, text=True,
            env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}))
    for name in VENDOR:
        src = ROOT / name
        dest = LOCAL / 'vendor' / Path(name).relative_to('research')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copyfile(src, dest)
        assert sha(dest) == hashes[name], name
    # Reports are evidence inputs, not imported or executed.
    (LOCAL / 'preflight.json').write_text(json.dumps({
        'volume_uuid': info['VolumeUUID'], 'filesystem': info['FilesystemType'],
        'writable': info['WritableVolume'], 'ignore_check': ignored,
        'df': subprocess.check_output(['df', '-h', '/Volumes/Workspace'], text=True),
        'input_hash_base': str(ROOT), 'vendor_base': 'local/vendor',
        'data_manifest_count': 18, 'all_input_count': len(hashes),
    }, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'data_files_verified': 18, 'frozen_inputs': len(hashes), 'vendor_files': len(VENDOR)}))


if __name__ == '__main__':
    main()
