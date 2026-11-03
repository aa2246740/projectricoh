"""Collect final-DAT acceptance records without counting missing cases as passes."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import OUT, DAT_SHA, save, file_sha
from run_queue import commands

def main():
    items = [('run_native.py', 'matrix', '50mm'), *commands()]
    rows = []
    original = list(sys.argv)
    for item in items:
        sys.argv = [str(OUT/item[0]), *item[1:]]
        name = common.result_path()
        assert name, item
        path = OUT/name
        row = dict(command=item, file=name, status='INCOMPLETE')
        if path.exists():
            value = json.loads(path.read_text())
            actual = value.get('dat_sha256', value.get('dat', value.get('tested_dat_sha256')))
            row.update(status=value.get('status', 'UNKNOWN'), sha256=file_sha(path),
                       tested_dat=actual, matches_final_dat=actual == DAT_SHA)
            assert actual == DAT_SHA, (name, actual)
            assert all(x['host_writes'] == 0 and not x['getter_callback_present']
                       for x in value.get('native_state_audits', [])), name
        rows.append(row)
    sys.argv = original
    passed = [r for r in rows if r['status'].startswith('PASS')]
    summary = dict(status='PASS' if len(passed) == len(rows) else 'INCOMPLETE',
                   dat_sha256=DAT_SHA, required_records=len(rows),
                   completed=len(passed), records=rows)
    save('acceptance.json', summary)
    print('Acceptance records', len(passed), '/', len(rows), flush=True)
    return summary

if __name__ == '__main__':
    main()
