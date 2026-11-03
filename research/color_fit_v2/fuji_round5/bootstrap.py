#!/usr/bin/env python3
"""Freeze round-five inputs. Run only with python3 -I -B."""
import ast
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / 'local'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount()
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume'] and info['WritableMedia']
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True)
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    subprocess.run(['git', 'check-ignore', '-v', str(LOCAL / 'guard')], cwd=ROOT, check=True)
    LOCAL.mkdir(exist_ok=True)
    frozen = LOCAL / 'vendor/research/closed_loop'
    if not frozen.is_dir():
        originals=list((ROOT/'research/closed_loop').glob('*.py'))
        originals += [p for p in (ROOT/'research/closed_loop/local/vendor').rglob('*') if p.is_file()]
        originals += [ROOT/'research/closed_loop/local'/n for n in
                    ('vendor_manifest.json','m20261021_prelim.json','frames_20261021_no_phys06.json')]
        manifest={}
        for p in originals:
            if not p.exists():continue
            d=LOCAL/'vendor'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True)
            digest=sha(p);shutil.copyfile(p,d);assert sha(d)==digest
            manifest[str(p.relative_to(ROOT))]={'sha256':digest,'copy':str(d.relative_to(LOCAL))}
        (LOCAL/'frozen_inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for item in json.loads((LOCAL/'frozen_inputs.json').read_text()).values():
        assert sha(LOCAL/item['copy'])==item['sha256'], 'The first closed_loop snapshot changed'
    supplemental=LOCAL/'supplemental_inputs.json'
    corrected=ROOT/'research/closed_loop/local/m20261021_r1.json'
    if not supplemental.exists() and corrected.exists():
        d=frozen/'local/m20261021_r1_physical.json';digest=sha(corrected)
        shutil.copyfile(corrected,d);assert sha(d)==digest and sha(corrected)==digest
        supplemental.write_text(json.dumps({str(corrected.relative_to(ROOT)):{'sha256':digest,
            'copy':str(d.relative_to(LOCAL)),'scope':'physical holdout only'}},indent=2)+'\n')
    if supplemental.exists():
        for item in json.loads(supplemental.read_text()).values():assert sha(LOCAL/item['copy'])==item['sha256']
    runtime = LOCAL / 'runtime'
    inputs = {}
    sources = list((frozen / 'local/vendor').rglob('*'))
    for p in sources:
        if not p.is_file():
            continue
        rel = p.relative_to(frozen / 'local/vendor')
        d = runtime / 'vendor' / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == '.py':
            text = p.read_text().replace(str(ROOT / 'research/closed_loop/local/vendor'), str(runtime / 'vendor'))
            d.write_text(text)
        else:
            shutil.copyfile(p, d)
    for name in ('common.py', 'model.py', 'refit.py'):
        p = frozen / name
        text = p.read_text()
        if name == 'refit.py':
            text = text.replace('from measure import stats', 'from stats_only import stats')
        (runtime / name).write_text(text)
    # Importing measure.py would execute it. Extract only its pure statistic function.
    code = (frozen / 'measure.py').read_text()
    node = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == 'stats')
    (runtime / 'stats_only.py').write_text('import numpy as np\n' + ast.get_source_segment(code, node) + '\n')
    files = [ROOT / 'research/hue_ring/local' / n for n in ('ring_model_v2.json', 'ring_model_v2_iso1600.json')]
    for slot in ('05_classic_chrome', '06_classic_neg'):
        base = ROOT / 'research/color_fit_v2' / slot / 'round4/local'
        files += [p for p in base.rglob('*') if p.is_file() and
                  (p.name.startswith('data_') or p.name in ('fit_v4_T1.json', 'fit_v4_noT1.json', 'synthetic_training.npz'))]
    files += [ROOT / 'artifacts/downloads/fuji-luts' / n for n in ('SHA256SUMS', 'gfx-eterna-55-3d-lut-v110.zip')]
    files += [ROOT / 'research/t1_probe/build_validate.py', ROOT / 'research/tables_v4/build_v4.py',
              ROOT / 'research/tables_v4/build_v4r3.py']
    files += list((ROOT / 'firmware/stage2j').rglob('*.c')) + list((ROOT / 'firmware/stage2j').rglob('*.h'))
    files += [ROOT / 'firmware/stage2j/examples/DEEPISP0.DAT',
              ROOT / 'firmware/stage2h/examples/tables/equal-2g/DEEPTBL0.DAT',
              ROOT / 'artifacts/stage2j-packages/stage2j/local/tables-equal-2h/DEEPTBL0.DAT']
    for name in ('tables-v4r3-probe', 'tables-v4r3-noprobe', 'tables-v4r3-t1/b5G_cR_dB'):
        files += [p for p in (ROOT / 'artifacts/stage2j-packages' / name).rglob('*') if p.is_file()]
    previous=json.loads((LOCAL/'inputs.json').read_text()) if (LOCAL/'inputs.json').exists() else {}
    for p in sorted(set(files)):
        assert not p.is_symlink()
        key=str(p.relative_to(ROOT))
        if key in previous:assert sha(p)==previous[key]['sha256'], 'Protected input changed: '+key
        d = LOCAL / 'inputs' / p.relative_to(ROOT)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, d)
        inputs[str(p.relative_to(ROOT))] = {'sha256': sha(p), 'bytes': p.stat().st_size,
                                         'copy': str(d.relative_to(LOCAL))}
    sums = (ROOT / 'artifacts/downloads/fuji-luts/SHA256SUMS').read_text().splitlines()
    for line in sums:
        h, name = line.split(maxsplit=1)
        assert sha(ROOT / 'artifacts/downloads/fuji-luts' / name.strip()) == h
    copies = {str(p.relative_to(runtime)): sha(p) for p in (runtime / 'vendor').rglob('*') if p.is_file()}
    (runtime / 'vendor_manifest.json').write_text(json.dumps({'copies_sha256': copies}, indent=2) + '\n')
    (LOCAL / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    (LOCAL / 'runtime_hashes.json').write_text(json.dumps({str(p.relative_to(LOCAL)): sha(p)
         for p in runtime.rglob('*') if p.is_file()}, indent=2) + '\n')
    (LOCAL / 'volume.json').write_text(json.dumps({k: info[k] for k in
         ('MountPoint', 'VolumeUUID', 'FilesystemType', 'WritableVolume', 'WritableMedia')}, indent=2) + '\n')
    print(f'Frozen {len(inputs)} inputs, {len(copies)} numerical helpers; all Fuji SHA256SUMS entries verified.')


if __name__ == '__main__':
    main()
