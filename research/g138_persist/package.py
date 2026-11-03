"""Assemble firmware/package_v38_g138: the v3.8 body files unchanged + the gen 138 DAT.

Reads package_v38_g137 (never writes it). Run with /usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'firmware/package_v38_g137/local/SD_ROOT'
TARGET_DIR = ROOT / 'firmware/package_v38_g138'
TARGET = TARGET_DIR / 'local/SD_ROOT'
BUILT = ROOT / 'firmware/engine_v55_g138/candidate/local/full-r13'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    files = sorted(p for p in SOURCE.iterdir() if p.is_file())
    assert len(files) == 30 and sha(SOURCE / 'ilaunch3') == BODY_SHA
    manifest = json.loads((BUILT / 'manifest.json').read_text())
    assert manifest['generation'] == 138 and manifest['loader_request'] <= 108124
    assert sha(BUILT / 'GXRCE.DAT') == manifest['sha256']
    TARGET.mkdir(parents=True, exist_ok=True)
    for path in files:
        if path.name != 'GXRCE.DAT':
            shutil.copyfile(path, TARGET / path.name)
    shutil.copyfile(BUILT / 'GXRCE.DAT', TARGET / 'GXRCE.DAT')
    out = sorted(p for p in TARGET.iterdir() if p.is_file())
    assert [p.name for p in out] == [p.name for p in files]
    same = [p.name for p in out if p.name != 'GXRCE.DAT' and (SOURCE / p.name).read_bytes() == p.read_bytes()]
    assert len(same) == 29 and sha(TARGET / 'ilaunch3') == BODY_SHA
    link = TARGET_DIR / 'SD_ROOT'
    if not link.is_symlink():
        link.symlink_to('local/SD_ROOT')
    (TARGET_DIR / '.gitignore').write_text('local/\nSD_ROOT\n')
    lines = ''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in out)
    (TARGET_DIR / 'SHA256SUMS').write_text(lines)
    print(json.dumps({'files': len(out), 'unchanged_from_v38_g137': len(same), 'body_sha256': sha(TARGET / 'ilaunch3'),
                      'dat_sha256': sha(TARGET / 'GXRCE.DAT'), 'dat_bytes': (TARGET / 'GXRCE.DAT').stat().st_size,
                      'loader_request': manifest['loader_request']}))


if __name__ == '__main__':
    main()
