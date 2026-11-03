"""Seal all research files and verify both final manifests without later writes."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, OUT

FINAL = 'd11e88eae677f7ee3aeba4dc602c2085ef92b9c81f5c70286c8eb038211e4bbc'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def verify(manifest, base):
    names = []
    for line in manifest.read_text().splitlines():
        want, name = line.split('  ', 1)
        target = (base / name).resolve()
        assert target.is_relative_to(base.resolve()), name
        assert digest(target) == want, name
        names.append(name)
    assert len(names) == len(set(names))
    return names


def main():
    assert (OUT / 'REPORT.md').is_file()
    acceptance = json.loads((OUT / 'acceptance.json').read_text())
    assert acceptance['status'] == 'PASS_NATIVE_CODEGEN_INCOMPLETE'
    card = ROOT / 'firmware/package_v36_g119'
    card_names = verify(card / 'CARD_SHA256SUMS', card)
    assert len(card_names) == 30
    assert digest(card / 'SD_ROOT/GXRCE.DAT') == FINAL == acceptance['dat_sha256']
    assert set(card_names) == {'SD_ROOT/' + p.name for p in (card / 'SD_ROOT').iterdir()}
    # Every foreground recorded command must have its terminal status before
    # hashing. Interrupted command archives are explicitly excluded here.
    for name in ('resumed-matrix-50mm', 'resumed-matrix-28mm', 'resumed-matrix-mount',
                 'resumed-B-panel-render', 'resumed-codegen-closure',
                 'resumed-branch-coverage', 'resumed-codegen-selfcheck',
                 'resumed-protected-inputs', 'resumed-acceptance', 'resumed-report'):
        record = json.loads((OUT / 'local/commands' / name / 'command.json').read_text())
        assert record['returncode'] == 0, name
    check = OUT / 'checksum-selfcheck.json'
    check.write_text(json.dumps(dict(status='PREPARING'), indent=2) + '\n')
    manifest = OUT / 'SHA256SUMS'

    def files():
        found = []
        for path in OUT.rglob('*'):
            assert not path.is_symlink(), str(path)
            if path.is_file() and path != manifest:
                found.append(path)
        return sorted(found, key=lambda x: x.relative_to(OUT).as_posix())

    def write_manifest():
        paths = files()
        manifest.write_text(''.join(digest(p) + '  ' + p.relative_to(OUT).as_posix() + '\n' for p in paths))
        return len(paths)

    count = write_manifest()
    assert len(verify(manifest, OUT)) == count
    check.write_text(json.dumps(dict(status='PASS', research_files=count,
        research_manifest='SHA256SUMS', manifest_self_excluded=True,
        card_files=30, card_manifest='../../firmware/package_v36_g119/CARD_SHA256SUMS',
        dat_sha256=FINAL, native_status=acceptance['native_status'],
        codegen_status=acceptance['codegen_status'],
        method='Verify every listed SHA-256, include this record, regenerate and verify the final manifest. No file is written after the final verification.'), indent=2) + '\n')
    assert write_manifest() == count
    assert set(verify(manifest, OUT)) == {p.relative_to(OUT).as_posix() for p in files()}
    assert len(verify(card / 'CARD_SHA256SUMS', card)) == 30
    print('ALL OK: research', count, 'files; CARD 30/30; final DAT', FINAL, flush=True)
    print('A/B/C per-PC branch closure remains INCOMPLETE; see codegen-selfcheck.json.', flush=True)


if __name__ == '__main__':
    main()
