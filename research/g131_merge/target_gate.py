"""Apply the requested H07 acceptance counts to the observed target records."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'

def main():
    pin = hashlib.sha256((ROOT / 'firmware/package_v36_g131/local/SD_ROOT/GXRCE.DAT').read_bytes()).hexdigest()
    folder = WORK / 'local/checks/review_g127/evidence'
    rows = []
    for case in ('h07-parent', 'h07-parent-preview'):
        for unit in ('50mm', '28mm', 'mount'):
            path = folder / (case + '-native-' + unit + '.json')
            data = json.loads(path.read_text())
            run_path = folder.parent / ('result-native_checks---case-' + case + '---unit-' + unit + '---crc-mode-native.json')
            run = json.loads(run_path.read_text())
            assert run['returncode'] == 0 and run['dat_sha256'] == pin
            assert data['generation'] == 131 and data['switched'] is True
            assert data['case'] == case and data['unit'] == unit
            stores, previews = data['settings_stores_after_switch'], data['preview_entries']
            assert isinstance(stores, list) and isinstance(previews, list)
            assert len(stores) == len(previews) == 0, (case, unit, len(stores), len(previews))
            before = data['before']
            assert before['rows'] == 8 and before['mode'] == 1 and before['wb'] == [9, 9]
            rows.append(dict(case=case, unit=unit, late_settings_stores=0, late_previews=0,
                first_H01=dict(mode=before['mode'], wb=before['wb'], rows=before['rows']),
                source=str(path.relative_to(ROOT))))
    result = dict(status='PASS', dat_sha256=pin, cases=rows)
    (WORK / 'evidence/target-counts.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name='target-counts', returncode=0, counts=dict(cases=len(rows),
        late_settings_stores=0, late_previews=0))))

if __name__ == '__main__':
    main()
