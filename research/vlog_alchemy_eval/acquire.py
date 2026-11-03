"""Fetch one pinned public archive and store regular files as data only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
SHA = 'e51ba9a23458ff5c316f630b860eb0201139d126'
DEST = ROOT / 'artifacts/downloads' / ('v-log-alchemy-' + SHA[:8])
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/vlog-alchemy-eval-r1')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def main():
    os.environ['TMPDIR'] = str(SCRATCH)
    os.umask(0o077)
    if DEST.exists():
        raise SystemExit('Destination must be new: ' + str(DEST))
    DEST.mkdir()
    url = 'https://codeload.github.com/shenmintao/V-Log-Alchemy/tar.gz/' + SHA
    archive = DEST / '_source.tar.gz'
    with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as f:
        while True:
            b = response.read(1024*1024)
            if not b:
                break
            f.write(b)
    count = 0
    size = 0
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != 'V-Log-Alchemy-' + SHA:
                raise ValueError('Unexpected archive root')
            rel = PurePosixPath(*parts[1:])
            if '..' in rel.parts or rel.is_absolute():
                raise ValueError('Invalid relative path')
            if member.isdir():
                continue
            if not member.isfile() or member.size > 200*1024*1024:
                raise ValueError('Unsupported archive member: ' + member.name)
            size += member.size
            if size > 1024*1024*1024:
                raise ValueError('Archive size limit')
            path = DEST / str(rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = tf.extractfile(member)
            with path.open('xb') as f:
                for b in iter(lambda: stream.read(1024*1024), b''):
                    f.write(b)
            count += 1
    record = {'repository': 'https://github.com/shenmintao/V-Log-Alchemy',
              'commit': SHA, 'commit_date': '2026-08-17T15:19:46Z',
              'archive_url': url, 'archive_sha256': digest(archive),
              'regular_files': count, 'expanded_bytes': size,
              'execution': 'none', 'mode': 'data only'}
    (DEST / '_acquisition.json').write_text(json.dumps(record, indent=2) + '\n')
    (DEST / 'SHA256SUMS').write_text(''.join(
        digest(p) + '  ' + p.relative_to(DEST).as_posix() + '\n'
        for p in sorted(DEST.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))
    print(json.dumps(record), flush=True)

if __name__ == '__main__':
    main()
