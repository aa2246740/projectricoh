"""Assemble firmware/package_v38_probe_p1/SD_ROOT: the 29 files of the v3.8 package
(ilaunch3 and the 28 official files, byte for byte) plus the P1 probe GXRCE.DAT."""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
from scope import ROOT, sha
scope.enable_fence()

SOURCE = ROOT / 'firmware/package_v38_g137'
DAT = ROOT / 'firmware/engine_probe_p1/candidate/local/full-r1/GXRCE.DAT'
OUT = ROOT / 'firmware/package_v38_probe_p1'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'


def main():
    scope.freeze_check()
    listed = {}
    for line in (SOURCE / 'SHA256SUMS').read_text().splitlines():
        digest, path = line.split(None, 1)
        listed[Path(path).name] = digest
    names = sorted(p.name for p in (SOURCE / 'SD_ROOT').iterdir())
    assert len(names) == 30 and set(names) == set(listed), (len(names), set(names) ^ set(listed))
    assert listed['ilaunch3'] == BODY_SHA
    target = OUT / 'SD_ROOT'
    assert not target.exists(), 'package exists; remove it deliberately before rebuilding'
    target.mkdir(parents=True)
    (OUT / '.gitignore').write_text('/SD_ROOT/\n')
    for name in names:
        if name == 'GXRCE.DAT':
            shutil.copyfile(DAT, target / name)
        else:
            shutil.copyfile(SOURCE / 'SD_ROOT' / name, target / name)
            assert sha(target / name) == listed[name], name
    assert sha(target / 'ilaunch3') == BODY_SHA
    lines = ['%s  %s' % (sha(target / n), (target / n).relative_to(ROOT)) for n in names]
    (OUT / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print('PACKAGE', len(names), 'files; GXRCE.DAT', sha(target / 'GXRCE.DAT'))


if __name__ == '__main__':
    main()
