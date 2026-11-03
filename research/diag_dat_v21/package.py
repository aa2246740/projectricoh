"""Stage the final DAT and the 29 frozen files, then read them back."""
from pathlib import Path
import json
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope


def main():
    scope.freeze_check()
    root = scope.ROOT
    package = root / 'firmware/package_v36_diag21'
    dest = package / 'local/SD_ROOT'
    dest.mkdir(parents=True, exist_ok=True)
    dat = root / 'firmware/engine_diag_v21/candidate/local/full-r13/GXRCE.DAT'
    assert int.from_bytes(dat.read_bytes()[28:32], 'big') == 132
    previous = json.loads((root / 'firmware/package_v36_diag2/manifest.json').read_text())
    items = []
    for item in previous['files']:
        name = item['name']
        source = dat if name == 'GXRCE.DAT' else root / 'firmware/package_v36_g120b/SD_ROOT' / name
        shutil.copyfile(source, dest / name)
        assert (dest / name).read_bytes() == source.read_bytes()
        items.append(dict(name=name, bytes=(dest / name).stat().st_size, sha256=scope.sha(dest / name)))
    assert len(items) == 30 and len(list(dest.iterdir())) == 30
    scope.save(package / 'manifest.json', dict(generation=132, files=items, fixed_files_identical=29,
               dat_sha256=scope.sha(dat), camera_acceptance='NOT_RUN'))
    (package / 'CARD_SHA256SUMS').write_text(''.join(
        item['sha256'] + '  ' + str((dest / item['name']).relative_to(root)) + '\n' for item in items))
    (package / 'STATUS.txt').write_text('Generation 132. Complete 30-file package. Host review candidate.\n')
    print('PACKAGE RETURN 0 FILES 30 FIXED 29')


if __name__ == '__main__':
    main()
