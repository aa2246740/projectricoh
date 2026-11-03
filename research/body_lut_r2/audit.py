"""Read-only input checks and scoped evidence. Run: /usr/bin/python3 -I -B audit.py."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
PROTECTED = (
    'firmware/resident_v34c', 'firmware/image_v34c', 'firmware/stage2k_p0',
    'artifacts/firmware/gxr-1.51', 'artifacts/downloads/gxr-151.zip',
    'research/body_lut',
    'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/GXRBX0.decoded.json',
)


def sha(path, limit=None):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        if limit is None:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                h.update(chunk)
        else:
            while limit:
                chunk = stream.read(min(limit, 1 << 20))
                if not chunk:
                    break
                h.update(chunk)
                limit -= len(chunk)
    return h.hexdigest()


def guard():
    info = plistlib.loads(subprocess.check_output(
        ['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount()
    assert info['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['MountPoint'] == '/Volumes/Workspace'
    assert all(info[k] for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    assert not LOCAL.is_symlink()
    subprocess.run(['git', 'check-ignore', '-q', 'research/body_lut_r2/local/x'],
                   cwd=ROOT, check=True)
    LOCAL.mkdir(exist_ok=True)
    return info


def snapshot():
    rows = {}
    for rel in PROTECTED:
        base = ROOT / rel
        assert base.exists(), rel
        files = [base] if base.is_file() else sorted(p for p in base.rglob('*') if p.is_file())
        for path in files:
            if path.name == 'decisions.tsv':
                continue
            rows[str(path.relative_to(ROOT))] = {'size': path.stat().st_size, 'sha256': sha(path)}
    return rows


def dump(name, value):
    (LOCAL / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def check():
    before = json.loads((LOCAL / 'protected-before.json').read_text())
    after = snapshot()
    drift, tails = [], []
    for rel, row in before.items():
        now = after.get(rel)
        if row == now:
            continue
        path = ROOT / rel
        # Only append-only text logs qualify. Code, JSON, maps and binaries stay exact.
        is_log = path.suffix in ('.log', '.jsonl', '.tsv')
        if now and is_log and now['size'] > row['size'] and sha(path, row['size']) == row['sha256']:
            tails.append(rel)
        else:
            drift.append(rel)
    drift += sorted(set(after) - set(before))
    source_path = LOCAL / 'source-inputs.json'
    source_rows = json.loads(source_path.read_text()) if source_path.exists() else {}
    for rel, digest in source_rows.items():
        if not (ROOT / rel).is_file() or sha(ROOT / rel) != digest:
            drift.append(rel)
    dump('protected-check.json', {'files': len(before), 'changed': drift,
                                 'source_inputs': len(source_rows),
                                 'append_only_tails': tails, 'decisions_tsv': 'excluded'})
    if drift:
        raise SystemExit('STOP: protected input changed: ' + ', '.join(drift[:8]))
    print('protected inputs unchanged:', len(before), '; append-only logs:', len(tails))


def main():
    info = guard()
    action = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if action == 'freeze':
        assert not (LOCAL / 'protected-before.json').exists(), 'baseline already exists'
        rows = snapshot()
        dump('protected-before.json', rows)
        dump('preflight.json', {'mount_uuid': info['VolumeUUID'], 'python': sys.version,
                               'write_root': str(HERE), 'no_build': True, 'no_network': True,
                               'protected_roots': PROTECTED,
                               'git_tracked_status': subprocess.check_output(
                                   ['git', 'status', '--porcelain=v1', '-uno'], cwd=ROOT, text=True)})
        print('frozen files:', len(rows))
    elif action == 'check':
        check()
    elif action == 'seal':
        check()
        paths = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
        (HERE / 'SHA256SUMS').write_text(''.join(
            sha(p) + '  ' + str(p.relative_to(HERE)) + '\n' for p in paths))
        print('sealed output files:', len(paths))
    else:
        raise SystemExit('usage: audit.py freeze|check|seal')


if __name__ == '__main__':
    main()
