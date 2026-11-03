"""Collect the required checks without treating absent records as passes."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'

def main():
    pin = hashlib.sha256((ROOT / 'firmware/package_v36_g131/local/SD_ROOT/GXRCE.DAT').read_bytes()).hexdigest()
    checks = WORK / 'local/checks'
    results = {}
    for path in checks.rglob('result-*.json'):
        item = json.loads(path.read_text())
        assert item['dat_sha256'] == pin
        results[item['name']] = dict(returncode=item['returncode'],
            postcheck_returncode=item.get('postcheck_returncode'),
            seconds=item['seconds'], source=str(path.relative_to(ROOT)))
    required = []
    for case in ('h07-parent', 'h07-parent-preview'):
        for unit in ('50mm', '28mm', 'mount'):
            required.append('native_checks---case-' + case + '---unit-' + unit + '---crc-mode-native')
    for script in ('ownership_settings', 'cold_reentry', 'cold_exit', 'settings_cases'):
        for unit in ('50mm', '28mm', 'mount'):
            required.append(script + '---unit-' + unit)
    for group in ('safety', 'locked', 'nested', 'cutpoints', 'exits'):
        required.append('batch---unit-50mm---groups-' + group + '---tag-g131-' + group)
    missing = [name for name in required if name not in results]
    failed = [name for name in required if name in results and results[name]['returncode'] != 0]
    windows = []
    for unit in ('50mm', '28mm', 'mount'):
        legacy = 'native_checks---case-preview-window---unit-' + unit + '---crc-mode-native'
        path = checks / 'review_g127' / ('observed-preview-window-' + unit + '.json')
        windows.append(dict(unit=unit, legacy=results.get(legacy),
            observation=json.loads(path.read_text()) if path.exists() else dict(status='INCOMPLETE')))
    focused = {}
    for name, relative in [('host', 'host-results.json'), ('target-counts', 'evidence/target-counts.json'),
            ('codegen', 'evidence/codegen-four-categories.json'), ('communications', 'evidence/rpc-summary.json'),
            ('target-0', 'target-0.json'), ('target-1', 'target-1.json'), ('target-2', 'target-2.json')]:
        path = WORK / relative
        focused[name] = json.loads(path.read_text()) if path.exists() else dict(status='INCOMPLETE')
    for unit in ('50mm', '28mm', 'mount'):
        path = checks / 'review_g126' / ('h01-restore-' + unit + '.json')
        focused['H01-' + unit] = json.loads(path.read_text()) if path.exists() else dict(status='INCOMPLETE')
    for item in focused.values():
        if item.get('status') in ('PASS', 'PASS_STATIC'):
            assert item.get('dat_sha256') == pin
    incomplete = [name for name, item in focused.items() if item.get('status') not in ('PASS', 'PASS_STATIC')]
    incomplete += ['window-' + item['unit'] for item in windows if item['observation']['status'] == 'INCOMPLETE']
    result = dict(status='可以交复审' if not missing and not failed and not incomplete else '有缺陷',
        dat_sha256=pin, required_retained_checks=len(required), missing=missing,
        failed=failed, incomplete=incomplete, retained=results, inherited_windows=windows,
        focused={name: {key: value for key, value in item.items() if key in
            ('status', 'dat_sha256', 'cases', 'golden', 'plans', 'complete_records', 'native_backend_cases')}
            for name, item in focused.items()})
    (WORK / 'evidence/acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(name='focused-acceptance', returncode=int(result['status'] != '可以交复审'),
        counts=dict(required=len(required), missing=len(missing), failed=len(failed), incomplete=len(incomplete)))))
    return result

if __name__ == '__main__':
    main()
