"""Hash the actual final local artifacts and verify every emitted checksum."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, ROOT, LOCAL, guard, read, dump, sha
import json


def main():
    guard()
    local = sorted(p for p in LOCAL.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS', 'manifest.json'))
    checks = {str(p.relative_to(ROOT)): sha(p) for p in local}
    manifest = {'schema': 'gr-pairs-local-delivery/1', 'accepted': False, 'firmware_ready': False,
                'deployable': False, 'v6_package_created': False, 'camera_acceptance': False,
                'all_photo_and_firmware_derivations_ignored': True, 'files_sha256': checks,
                'targets': {p.stem: sha(p) for p in sorted((LOCAL / 'targets').glob('*.npz'))},
                'verification': {p.stem: sha(p) for p in sorted((LOCAL / 'verification').glob('*.json'))}}
    dump(LOCAL / 'manifest.json', manifest)
    (LOCAL / 'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p, h in checks.items()) +
                                      f"{sha(LOCAL / 'manifest.json')}  {(LOCAL / 'manifest.json').relative_to(ROOT)}\n")
    public = sorted(p for p in HERE.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (HERE / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in public))
    for sumfile in (LOCAL / 'SHA256SUMS', HERE / 'SHA256SUMS'):
        for line in sumfile.read_text().splitlines():
            digest, path = line.split('  ', 1)
            assert sha(ROOT / path) == digest, path
    print(json.dumps({'local_files_hashed': len(checks) + 1, 'public_files_hashed': len(public),
                      'all_checksums_verified': True, 'accepted': False}))


if __name__ == '__main__':
    main()
