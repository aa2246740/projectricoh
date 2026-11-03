#!/usr/bin/env python3
"""Task-local evidence commands. All outputs are confined to the two allowed dirs."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
DOWNLOADS = ROOT / 'artifacts/downloads/emulator_feasibility_r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    rows = json.loads((LOCAL / 'protected-inputs.json').read_text())['files']
    changed = [r['path'] for r in rows
               if not (ROOT / r['path']).is_file() or sha(ROOT / r['path']) != r['sha256']]
    if changed:
        raise SystemExit('STOP protected input changed: ' + json.dumps(changed))
    return len(rows)


def fetch(url, name):
    target = (DOWNLOADS / name).resolve()
    assert target.is_relative_to(DOWNLOADS.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = LOCAL / 'sources.json'
    rows = json.loads(manifest.read_text()) if manifest.exists() else []
    old = next((r for r in rows if r['url'] == url and r['path'] == str(target.relative_to(ROOT))), None)
    if old and target.exists() and old.get('sha256') == sha(target):
        print(json.dumps({'cached': name, 'sha256': old['sha256']}))
        return
    record = {'url': url, 'path': str(target.relative_to(ROOT)), 'method': 'GET',
              'fetched_epoch': time.time(), 'untrusted': True, 'executed_in_downloads': False}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'projectricoh-host-research/1'})
        with urllib.request.urlopen(req, timeout=45) as response:
            data = response.read(500_000_000)
            record.update(status=response.status, resolved_url=response.url)
        target.write_bytes(data)
        record.update(size=len(data), sha256=sha(target))
    except (urllib.error.URLError, TimeoutError) as exc:
        record.update(error=str(exc))
    rows = [r for r in rows if not (r['url'] == url and r['path'] == record['path'])] + [record]
    manifest.write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps({k: v for k, v in record.items() if k not in ('fetched_epoch', 'untrusted', 'executed_in_downloads')}))


def freeze_extra(paths):
    manifest = LOCAL / 'protected-inputs.json'
    data = json.loads(manifest.read_text())
    known = {r['path'] for r in data['files']}
    for path in paths:
        p = (ROOT / path).resolve()
        assert p.is_relative_to(ROOT)
        name = str(p.relative_to(ROOT))
        assert p.name != 'decisions.tsv'
        if name not in known:
            data['files'].append({'path': name, 'size': p.stat().st_size, 'sha256': sha(p)})
            known.add(name)
    data['files'].sort(key=lambda r: r['path'])
    manifest.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'frozen_files': len(data['files'])}))


def checksums():
    lines = []
    for p in sorted(HERE.rglob('*')):
        if p.is_file() and p.name != 'SHA256SUMS':
            lines.append(f'{sha(p)}  {p.relative_to(HERE)}')
    (HERE / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'checksums': len(lines), 'protected_verified': verify()}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['verify', 'fetch', 'freeze-extra', 'checksums'])
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch(*args.args)
    elif args.command == 'freeze-extra':
        verify()
        freeze_extra(args.args)
    elif args.command == 'checksums':
        checksums()
    else:
        print(json.dumps({'protected_verified': verify()}))


if __name__ == '__main__':
    main()
