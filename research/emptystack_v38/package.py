from pathlib import Path
import json
import shutil
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, sha, save, setup

def main():
    setup()
    target = ROOT / 'firmware/package_v38_g137'
    local = target / 'local/SD_ROOT'
    local.mkdir(parents=True, exist_ok=True)
    (target / '.gitignore').write_text('local/\nSD_ROOT\n')
    visible = target / 'SD_ROOT'
    if not visible.exists():
        visible.symlink_to('local/SD_ROOT', target_is_directory=True)
    source = ROOT / 'firmware/package_v37_g135/SD_ROOT'
    assert len(list(source.iterdir())) == 30
    for path in source.iterdir():
        if path.name not in ('ilaunch3', 'GXRCE.DAT'):
            shutil.copyfile(path, local / path.name)
    shutil.copyfile(ROOT / 'firmware/resident_v38/local/body/ilaunch3', local / 'ilaunch3')
    shutil.copyfile(ROOT / 'firmware/engine_v54_g137/candidate/local/full-r13/GXRCE.DAT', local / 'GXRCE.DAT')
    dat = (local / 'GXRCE.DAT').read_bytes()
    assert struct.unpack_from('>I', dat, 28)[0] == 137
    trust = json.loads((ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
    assert dat[80:112].hex() == trust['resident_build_id']
    assert dat[212:228].hex() == trust['resident_abi_id']
    rows = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(local.iterdir())]
    assert len(rows) == 30
    assert sum((local / p.name).read_bytes() == p.read_bytes() for p in source.iterdir()) == 28
    save(WORK / 'package.json', {'files': rows, 'unchanged_files': 28, 'generation': 137, 'resident_build_id': trust['resident_build_id'], 'resident_abi_id': trust['resident_abi_id']})
    (target / 'SHA256SUMS').write_text(''.join(f"{row['sha256']}  {row['path']}\n" for row in rows))
    print(json.dumps({'files': 30, 'unchanged': 28, 'dat_sha256': sha(local / 'GXRCE.DAT'), 'body_sha256': sha(local / 'ilaunch3')}))

if __name__ == '__main__':
    main()
