#!/usr/bin/env python3
"""Freeze numerical code and read-only inputs. Never writes outside this round."""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    disk = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert disk['MountPoint'] == '/Volumes/Workspace' and disk['WritableVolume'] and disk['FilesystemType'] == 'apfs'
    assert disk['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True)
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'probe.json')], cwd=ROOT, check=True)
    assert not (LOCAL / 'inputs.json').exists(), 'Snapshot already exists; do not overwrite it.'
    old = ROOT / 'research/color_fit_v2/06_classic_neg/round4/local/runtime'
    new = LOCAL / 'runtime'
    protected = {}

    def copy(source, target, rewrite=False):
        source = source.resolve()
        assert source.is_relative_to(ROOT)
        protected[str(source.relative_to(ROOT))] = sha(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if rewrite:
            target.write_text(source.read_text().replace(str(old), str(new)))
        else:
            shutil.copyfile(source, target)

    for p in old.rglob('*.py'):
        copy(p, new / p.relative_to(old), True)
    engine = ROOT / 'research/color_fit_v2/06_classic_neg/round4/fit_round4.py'
    copy(engine, LOCAL / 'engine.py')
    p = LOCAL / 'engine.py'
    p.write_text(p.read_text().replace('HERE = Path(__file__).resolve().parent',
                                     'HERE = Path(__file__).resolve().parent.parent'))
    paths = {
        'state01.json': 'research/color_fit_v2/01_gr_positive/local/neutralised_fit_state.json',
        'state02.json': 'research/color_fit_v2/02_gr_negative/round4/local/baseline/neutralised_prepared.json',
        'current01.json': 'research/color_fit_v2/01_gr_positive/local/fit.json',
        'current02.json': 'research/color_fit_v2/02_gr_negative/round4/local/fit_v4_noT1.json',
        'folds01.json': 'research/color_fit_v2/01_gr_positive/local/loo_solutions.json',
        'curves_source.json': 'research/stage2e_verification/local/tables_used.json',
        'fuji_chart.json': 'research/fuji_phase2/local/fit.json',
        'reference.json': 'research/color_references/gr3_reference_measurements.json',
        'relative_photo.json': 'research/stage2d_verification/measurements.json',
        'ring_design.json': 'research/hue_ring/patches.json',
        'absolute_rows.json': 'research/hue_ring/local/calibration_20261020/followup_v2/absolute_rows.json',
        'gr_tables.json': 'research/gr_firmware/data/gr3-2.10-tables.json',
        'gr_parameters.json': 'research/gr_complete_pipeline/forward_model_results.json',
        'gr_metadata.json': 'research/gr_complete_pipeline/reference_metadata.json',
    }
    for name, path in paths.items():
        copy(ROOT / path, LOCAL / 'inputs' / name)
    for i in range(18):
        copy(ROOT / f'research/color_fit_v2/02_gr_negative/round4/local/A_s03_fold_{i:02d}.json',
             LOCAL / 'inputs' / f'fold02_{i:02d}.json')
    for name in ('arm_gamma_model.py', 'pipeline_math.py', 'colour_math_frozen.py', 'reference_tiff_frozen.py'):
        copy(ROOT / 'research/gr_complete_pipeline' / name, LOCAL / 'gr_code' / name)
    copy(ROOT / 'research/color_references/lossless_jpeg.py', LOCAL / 'gr_code/lossless_jpeg.py')
    v2 = new / 'research/hue_ring/local/calibration_20261020/followup_v2/code/ring_model_v2.py'
    v2.write_text(v2.read_text().replace("LOCAL=ROOT/'research/hue_ring/local/calibration_20261020/followup_v2'",
                                       f'LOCAL=Path({str(LOCAL / "inputs")!r})'))
    (LOCAL / 'inputs.json').write_text(json.dumps(protected, indent=2) + '\n')
    print(json.dumps({'protected_inputs': len(protected), 'runtime_modules': len(list(new.rglob('*.py')))}))


if __name__ == '__main__':
    main()
