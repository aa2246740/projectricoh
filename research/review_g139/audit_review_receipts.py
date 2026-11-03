"""Check this review's result identity, generation times, and execution receipts."""
from pathlib import Path
import collections
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    receipts = []
    errors = []
    events = []
    sources = []
    for path in sorted((HERE / 'evidence').rglob('*.json')):
        data = json.loads(path.read_text())
        if not all(key in data for key in ('job', 'started_ns', 'ended_ns', 'outputs', 'log_sha256')):
            continue
        sources.append((path, data))
    for path, data in sources:
        row = dict(job=data['job'], receipt=str(path.relative_to(HERE)),
                   status=data['status'], seconds=data['seconds'],
                   timeout_seconds=data['timeout_seconds'], results=[])
        if data['timeout_seconds'] < 3 * data['seconds']:
            errors.append([data['job'], 'timeout below three times measured duration'])
        log = HERE / 'evidence' / (data['job'] + '.log')
        if not log.is_file() or sha(log) != data['log_sha256']:
            errors.append([data['job'], 'log identity'])
        if 'slot' in data:
            events.extend([(data['started_ns'], 1, data['job']), (data['ended_ns'], -1, data['job'])])
        for output in data['outputs']:
            target = ROOT / output['path']
            item = dict(path=output['path'], existed_at_end=output['exists'])
            if output['exists']:
                item.update(sha256=sha(target), mtime_ns=target.stat().st_mtime_ns)
                if item['sha256'] != output['sha256']:
                    errors.append([data['job'], output['path'], 'result identity'])
                if not data['started_ns'] <= output['mtime_ns'] <= data['ended_ns']:
                    errors.append([data['job'], output['path'], 'result generation time'])
                inner = json.loads(target.read_text()) if target.suffix == '.json' else {}
                if 'started_ns' in inner and 'ended_ns' in inner:
                    if not data['started_ns'] <= inner['started_ns'] <= inner['ended_ns'] <= data['ended_ns']:
                        errors.append([data['job'], output['path'], 'inner execution time'])
                if 'seconds' in inner:
                    item['case_seconds'] = inner['seconds']
            elif target.exists():
                later = [candidate['job'] for _, candidate in sources
                         if candidate['started_ns'] > data['ended_ns']
                         and candidate['status'] in ('PASS', 'OBSERVED')
                         and any(result['path'] == output['path']
                                 and result.get('fresh')
                                 and result.get('sha256') == sha(target)
                                 for result in candidate['outputs'])]
                item['later_producers'] = later
                if data['status'] != 'FAIL' or not later:
                    errors.append([data['job'], output['path'], 'missing result without later producer'])
            row['results'].append(item)
        receipts.append(row)
    active = set()
    peak = 0
    for timestamp, delta, job in sorted(events):
        if delta > 0:
            active.add(job)
            peak = max(peak, len(active))
        else:
            active.remove(job)
    if peak > 2 or active:
        errors.append(['execution slots', peak, sorted(active)])
    result = dict(status='PASS_RECEIPT_AUDIT' if not errors else 'FAIL_RECEIPT_AUDIT',
                  receipt_count=len(receipts), peak_test_jobs=peak,
                  counts=dict(collections.Counter(row['status'] for row in receipts)),
                  errors=errors, receipts=receipts)
    (HERE / 'evidence/review-receipt-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'receipts'}))
    assert not errors, errors


if __name__ == '__main__':
    main()
