#!/usr/bin/env python3
"""Copy capture bytes from an SD card, hash both sides, never open sources for writing."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = ROOT / 'captures/a12-50/2026-10-16/S1b-sd-import'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlink in source inventory: {path}')
        if path.is_file():
            st = path.stat()
            result[str(path.relative_to(root))] = {
                'bytes': st.st_size, 'sha256': digest(path), 'mtime_ns': st.st_mtime_ns}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/Volumes/RICOHDCX'))
    parser.add_argument('--dest', type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()
    source, dest = args.source.resolve(strict=True), args.dest.resolve()
    if not dest.is_relative_to(ROOT / 'captures') or source == dest or dest.is_relative_to(source):
        raise ValueError('Destination must be a separate project captures directory')
    before = inventory(source)
    files = []
    for relative, info in before.items():
        if Path(relative).suffix.lower() not in {'.dng', '.jpg', '.jpeg'} or Path(relative).name.startswith('._'):
            continue
        src, target = source / relative, dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(target) != info['sha256']:
                raise ValueError(f'Refusing to overwrite a different capture: {target}')
        else:
            with src.open('rb') as reader, target.open('xb') as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
            shutil.copystat(src, target)
        target.chmod(0o444)
        actual = {'bytes': target.stat().st_size, 'sha256': digest(target)}
        if any(actual[key] != info[key] for key in actual):
            raise ValueError(f'Copy verification failed: {target}')
        files.append({'source': str(src), 'destination': str(target.relative_to(ROOT)),
                      **actual, 'destination_mode': '0444'})
    after = inventory(source)
    changes = [name for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]
    manifest = {
        'schema': 'gxr-read-only-sd-ingest-v1',
        'ingested_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source_root': str(source), 'destination_root': str(dest.relative_to(ROOT)),
        'source_access': 'Only rb/stat/directory listing; no card writes, deletions, chmod or metadata updates',
        'camera_dates': 'Import date is 2026-10-16; EXIF capture dates are independently parsed in verification.json',
        'source_inventory_before': before, 'source_inventory_after': after,
        'source_changes_during_ingest': changes, 'source_unchanged': not changes,
        'copied_files': files, 'copied_count': len(files)}
    manifest_path = dest / 'ingest_manifest.json'
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    else:
        original = json.loads(manifest_path.read_text())
        if original['copied_files'] != files or changes:
            raise ValueError('Existing manifest no longer agrees with source/copies')
    print(json.dumps({'captures_copied': len(files), 'source_unchanged': not changes,
                      'manifest': str(manifest_path.relative_to(ROOT))}))
    if changes:
        raise SystemExit('Card changed during read-only ingest; inspect manifest')


if __name__ == '__main__':
    main()
