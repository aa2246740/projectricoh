from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_v37_flash'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert (OUT / 'REVIEW.md').read_text().splitlines()[0] == '不可以刷机'
    initial = json.loads((OUT / 'local/protected-inputs.json').read_text())
    shared = next(item for item in initial if item['path'] == 'decisions.tsv')
    shared_now = (ROOT / shared['path']).read_bytes()
    assert hashlib.sha256(shared_now[:shared['size']]).hexdigest() == shared['sha256']
    shared_record = {'path': shared['path'], 'before_size': shared['size'],
                     'after_size': len(shared_now), 'before_sha256': shared['sha256'],
                     'after_sha256': hashlib.sha256(shared_now).hexdigest(),
                     'prefix_unchanged': True,
                     'added_bytes': len(shared_now) - shared['size'],
                     'added_lines': shared_now[shared['size']:].count(b'\n')}
    (OUT / 'local/shared-log-change.json').write_text(json.dumps(shared_record, indent=2) + '\n')
    protected = [item for item in initial if item['path'] != 'decisions.tsv']
    changed = [item['path'] for item in protected
               if digest(ROOT / item['path']) != item['sha256']]
    assert not changed, changed
    inputs = {item['path'] for item in protected}
    for unit in ['50mm', '28mm', 'mount']:
        run = json.loads((OUT / ('local/run-' + unit + '.json')).read_text())
        result = json.loads((OUT / ('local/accept-' + unit + '.json')).read_text())
        assert run['status'] == 'PASS' and run['assertions_enabled']
        assert result['root']['state'] == 3 and result['redisplay']['rows'] == 8
        assert result['redisplay']['jl_delta'] == 0
        assert not any(result['writes'].values())
    native = json.loads((OUT / 'local/native-results.json').read_text())
    assert native['assertions_enabled'] and native['status'] == 'OBSERVED'
    cases = native['service_cases']
    assert len(cases) == 6 and all(row['initial_root_check'] == 0 for row in cases)
    assert sum(row['strict_owned'] == 0 and row['mode_after'] == 1 for row in cases) == 3
    assert sum(row['strict_owned'] == 0 and row['preview_entries'] == 1 for row in cases) == 3
    static = json.loads((OUT / 'local/artifacts.json').read_text())
    assert static['body_difference_count'] == 102 and not static['body_difference_outside']
    assert static['checksum_equal'] and static['engine_matches_elf']
    assert static['dat_header_crc_equal'] and static['dat_content_crc_equal']
    assert (OUT / '.gitignore').read_text() == 'local/\n'
    integrity = {'protected_files': len(protected), 'changed_inputs': changed,
                 'shared_log_changes': [shared_record],
                 'completed_utc': datetime.now(timezone.utc).isoformat(),
                 'started_utc': '2026-10-29T23:07:11Z',
                 'deadline_utc': '2026-10-30T00:07:11Z',
                 'camera_accessed': False, 'card_accessed': False,
                 'network_used': False, 'subagents_started': 0,
                 'local_ignored': True}
    (OUT / 'local/integrity.json').write_text(json.dumps(integrity, indent=2) + '\n')
    outputs = {str(p.relative_to(ROOT)) for p in OUT.rglob('*')
               if p.is_file() and p != OUT / 'SHA256SUMS'}
    paths = sorted(inputs | outputs)
    manifest = ''.join(digest(ROOT / name) + '  ' + name + '\n' for name in paths)
    (OUT / 'SHA256SUMS').write_text(manifest)
    checked = subprocess.run(['shasum', '-a', '256', '-c',
                              'research/review_v37_flash/SHA256SUMS'],
                             cwd=ROOT, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert len(checked.stdout.splitlines()) == len(paths)
    assert all(line.endswith(': OK') for line in checked.stdout.splitlines())
    print(json.dumps({'manifest_files': len(paths), 'protected_files': len(protected),
                      'changed_inputs': 0, 'checksum_exit': checked.returncode,
                      'shared_log_changes': 1,
                      'verdict': '不可以刷机'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
