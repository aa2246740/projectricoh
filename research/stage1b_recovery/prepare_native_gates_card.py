#!/usr/bin/env python3
"""Stage this reviewed experiment on the identified card; never flash a camera."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CARD = Path('/Volumes/RICOHDCX')
PACKAGE = ROOT / 'artifacts/stage1b-candidate/packages/stage1b-16-recipes-012bcd24e77b'
EVIDENCE = ROOT / 'artifacts/stage1b-candidate/media-012bcd24e77b'
UUID = '0F824AED-99E3-397F-AC62-EFC0D90DD373'
MANIFEST_SHA = 'abbd9c116180dbab77b2f130cad68d37717cd99b886f7a608e18c24c0aa73441'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    require(stat.S_ISREG(path.lstat().st_mode), f'Not a regular file: {path}')
    return path.read_bytes()


def card_identity():
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(CARD)]))
    require(info.get('VolumeUUID') == UUID and info.get('MountPoint') == str(CARD), 'Different card')
    require(info.get('DeviceIdentifier') == 'disk8s1' and info.get('TotalSize') == 31902433280, 'Device changed')
    require(info.get('FilesystemType') == 'msdos' and info.get('RemovableMedia')
            and info.get('WritableVolume') and not info.get('OSInternalMedia'), 'Unexpected storage')
    require(CARD.resolve() == CARD and os.path.ismount(CARD), 'Not the mounted card')
    return {k:info[k] for k in ('VolumeUUID', 'DeviceIdentifier', 'MountPoint', 'TotalSize', 'FilesystemType')}


def media_files():
    result = {}
    for name in ('DCIM', 'CLIPINFO'):
        directory = CARD / name
        require(directory.is_dir() and not directory.is_symlink(), f'Missing camera directory: {name}')
        for path in sorted(directory.rglob('*')):
            require(not path.is_symlink(), f'Unexpected symlink: {path}')
            if path.is_file():
                result[str(path.relative_to(CARD))] = sha(regular(path))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    identity = card_identity()
    raw_manifest = regular(PACKAGE / 'manifest.json')
    require(sha(raw_manifest) == MANIFEST_SHA, 'Package manifest changed')
    manifest = json.loads(raw_manifest)
    target_hashes = manifest['candidate_sha256']
    old_hashes = manifest['recovery_sha256']
    require(len(target_hashes) == 29 and set(target_hashes) == set(old_hashes), 'Component inventory differs')
    for name, expected in target_hashes.items():
        require(sha(regular(PACKAGE / 'candidate/SD_ROOT' / name)) == expected, f'Candidate changed: {name}')
        require(sha(regular(PACKAGE / 'recovery-official-1.51/SD_ROOT' / name)) == old_hashes[name], f'Recovery changed: {name}')
    desired = {'ilaunch3':regular(PACKAGE / 'candidate/SD_ROOT/ilaunch3'),
               'RECIPES0.DAT':regular(PACKAGE / 'recipe-library/RECIPES0.DAT')}
    require(sha(desired['RECIPES0.DAT']) == manifest['recipe_library_sha256'], 'Recipe library changed')
    require(not (CARD / 'RECIPES1.DAT').exists(), 'Existing second recipe bank requires inspection')
    card_hashes = {}
    for name, expected in old_hashes.items():
        current = sha(regular(CARD / name))
        require(current in (expected, target_hashes[name]), f'Unexpected card component: {name}')
        card_hashes[name] = current
    if (CARD / 'RECIPES0.DAT').exists():
        require(regular(CARD / 'RECIPES0.DAT') == desired['RECIPES0.DAT'], 'Existing recipe library requires backup')
    before_media = media_files()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    before = {'card':identity, 'firmware_sha256':card_hashes, 'media_sha256':before_media,
              'package_manifest_sha256':MANIFEST_SHA, 'camera_executed':False}
    before_path = EVIDENCE / 'before.json'
    if before_path.exists():
        recorded = json.loads(before_path.read_text())
        require(recorded['card'] == identity and recorded['media_sha256'] == before_media, 'Card changed since preparation')
    else:
        before_path.write_text(json.dumps(before, indent=2)+'\n')
    backup = EVIDENCE / 'original-ilaunch3'
    if not backup.exists():
        data = regular(CARD / 'ilaunch3')
        require(sha(data) == old_hashes['ilaunch3'], 'Original card image missing for backup')
        with backup.open('xb') as stream:
            stream.write(data)
    require(sha(regular(backup)) == old_hashes['ilaunch3'], 'Backup readback failed')
    if not args.write:
        print(json.dumps({'status':'CARD_PREFLIGHT_PASS', 'card':identity, 'media_files':len(before_media),
                          'backup':str(backup), 'planned_files':list(desired), 'card_written':False}))
        return
    changed = []
    for name in ('RECIPES0.DAT', 'ilaunch3'):
        require(card_identity() == identity, 'Card changed before write')
        target = CARD / name
        if target.exists() and regular(target) == desired[name]:
            continue
        if target.exists():
            require(name == 'ilaunch3' and sha(regular(target)) == old_hashes[name], 'Target changed before write')
        temporary = CARD / ('.gxr-012bcd24-' + name + '.tmp')
        with temporary.open('xb') as stream:
            stream.write(desired[name]); stream.flush(); os.fsync(stream.fileno())
        require(regular(temporary) == desired[name], 'Temporary file readback failed')
        require(card_identity() == identity, 'Card changed during write')
        os.replace(temporary, target)
        require(regular(target) == desired[name], 'Installed file readback failed')
        changed.append(name)
    require(card_identity() == identity, 'Card changed before final verification')
    for name, expected in target_hashes.items():
        require(sha(regular(CARD / name)) == expected, f'Final firmware readback failed: {name}')
    require(regular(CARD / 'RECIPES0.DAT') == desired['RECIPES0.DAT'], 'Final recipe readback failed')
    require(media_files() == before_media, 'Camera media changed')
    result = {'status':'CARD_PREPARED_AND_READ_BACK', 'card':identity,
              'package':str(PACKAGE.relative_to(ROOT)), 'candidate_sha256':target_hashes['ilaunch3'],
              'recipe_sha256':manifest['recipe_library_sha256'], 'firmware_files_verified':29,
              'changed_or_added_files':changed, 'media_files_preserved':len(before_media),
              'backup':str(backup.relative_to(ROOT)), 'camera_executed':False, 'camera_flashed':False}
    (EVIDENCE / 'after.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
