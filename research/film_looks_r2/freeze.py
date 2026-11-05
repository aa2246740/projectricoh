"""Freeze local-only inputs and source identities without importing numerical code."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

assert sys.flags.isolated, 'Run Python -I -B'
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOCAL = HERE/'local'
UNITS = ('a12-50', 'a12-28', 'mount-a12')


def main():
    LOCAL.mkdir(exist_ok=True)
    assert not (LOCAL/'freeze.json').exists(), 'Preserve the frozen inputs'
    files = []

    def copy(path, destination=None):
        source = ROOT/path
        target = destination or LOCAL/'frozen'/path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw)
        files.append(dict(path=str(path), frozen=str(target.relative_to(LOCAL)),
                          bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))

    for folder in ('research/model_c040_r1/local', 'research/bluecyan_r1',
                   'research/recipe_redo_r1', 'tools/fit_fast'):
        for path in sorted((ROOT/folder).glob('*.py')):
            copy(path.relative_to(ROOT))
    for path in ('research/module_adapt/c040.py', 'research/v39_g153/dat_format.py',
                 'research/look_ceiling_r1/quality.py',
                 'research/look_ceiling_r1/local/hardware_constants.json',
                 'research/model_c040_r1/local/g157_handoff.json',
                 'research/model_c040_r1/local/capacity.json',
                 'research/model_c040_r1/REPORT.md',
                 'research/recipe_redo_r1/REPORT.md',
                 'firmware/package_v310_g156/GXRCE.DAT',
                 'firmware/package_v310_g156_test/GXRCE.DAT',
                 'firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT'):
        copy(Path(path))
    for unit in UNITS:
        copy(Path('research/model_c040_r1/local/calibration')/('input-map-'+unit+'.json'),
             LOCAL/'calibration'/('input-map-'+unit+'.json'))
        for profile in ('release', 'test'):
            for path in sorted((ROOT/'research/model_c040_r1/local/layouts'/profile).glob(unit+'-builtin-*.record552')):
                copy(path.relative_to(ROOT))
        if unit == 'a12-50':
            copy(Path('research/recipe_redo_r1/local/inputs')/unit/'photos.json', LOCAL/'inputs'/unit/'photos.json')
        else:
            copy(Path('research/model_c040_r1/local/targets')/unit/'14/photos.json', LOCAL/'inputs'/unit/'photos.json')
    archive = Path('artifacts/downloads/fuji-luts/gfx-eterna-55-3d-lut-v110.zip')
    archive_sha = hashlib.sha256((ROOT/archive).read_bytes()).hexdigest()
    with zipfile.ZipFile(ROOT/archive) as z:
        sources = []
        for interpretation in ('F-Log2', 'F-Log2C'):
            member = next(n for n in z.namelist() if '/65Grid/'+interpretation+'/' in n
                          and '_to_ACROS_65grid_' in n and n.endswith('.cube'))
            raw = z.read(member)
            target = LOCAL/'luts'/Path(member).name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(raw)
            sources.append(dict(provider='FUJIFILM', package='GFX ETERNA 55 v1.10',
                archive=str(archive), archive_sha256=archive_sha, member=member,
                file=str(target), sha256=hashlib.sha256(raw).hexdigest(), input=interpretation,
                source_url='https://fujifilm-x.com/global/support/download/lut/',
                permission='Local research only. Manufacturer LUT and derived records are not licensed for public redistribution here.',
                output='BT.709 display codes, historical GXR direct-code comparison'))
    provenance = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_commit='7ba9cb4a2d921cd5ad88f037c1e9693323bad05f',
        c040_geometry='native', sources=sources, files=files,
        owner_photos_read_only=True, network_used=False, devices_used=False,
        no_DAT_written=True, uncommitted_work_preserved=True)
    (LOCAL/'freeze.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    print('Frozen',len(files),'files and',len(sources),'official Acros LUTs')


if __name__ == '__main__':
    main()
