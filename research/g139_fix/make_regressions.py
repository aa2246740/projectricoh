"""Tabulate the g139 81-group matrix and the extra queues from their OS receipts.

Every group keeps all attempts; the final status is the last attempt's. A
group is PASS only with OS exit 0 and a run time not below half of the g138
review's time for the same group (short runs are flagged SHORT for review).
Output: REGRESSIONS.md / REGRESSIONS.json in research/g139_fix.
"""
from pathlib import Path
import glob
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def receipt(name):
    path = HERE / 'evidence/receipts' / (name + '.json')
    return json.loads(path.read_text()) if path.exists() else None


def main():
    review = {}
    for f in glob.glob(str(ROOT / 'research/review_g138/evidence/receipts/*.json')):
        d = json.loads(Path(f).read_text())
        if 'name' in d and 'seconds' in d:
            review[d['name']] = d['seconds']
    rows = []
    for job in json.loads((HERE / 'queue-g139.json').read_text())['jobs']:
        if job.get('kind') != 'regression':
            continue
        attempts = [r for r in (receipt(job['name']), receipt(job['name'] + '-r2')) if r]
        last = attempts[-1]
        base = job['name'].replace('-g139', '')
        ref = review.get(base + '-final-r2') or review.get(base)
        status = 'PASS' if last['returncode'] == 0 else 'FAIL'
        if status == 'PASS' and ref and last['seconds'] < 0.5 * ref and not job['name'].endswith('-g139'):
            status = 'SHORT'
        rows.append(dict(name=job['name'], family=job['family'], unit=job['unit'], group=job['group'],
                         contract='g139-current' if job['name'].endswith('-g139') else 'retained',
                         returncode=last['returncode'], seconds=last['seconds'], review_g138_seconds=ref,
                         status=status, attempts=[dict(name=a['name'], returncode=a['returncode'], seconds=a['seconds'])
                                                  for a in attempts],
                         receipt='evidence/receipts/' + last['name'] + '.json'))
    counts = {}
    for row in rows:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    (HERE / 'REGRESSIONS.json').write_text(json.dumps(dict(total=len(rows), counts=counts, rows=rows), indent=1) + '\n')
    lines = ['# g139 81 组回归', '',
             f'DAT `aab6c4f8d525dfda94fd33861c0a632b16f4d0df5481c7d9423e2bf820399e21`。共 {len(rows)} 组：' +
             '，'.join(f'{k} {v}' for k, v in sorted(counts.items())) + '。', '',
             '最终状态取最后一次尝试；所有尝试都列出。12 个 `-g139` 组是旧约定组的现行版本（`queue-stale12.json`）。', '',
             '| 家族 | 单元 | 组 | 合同 | 返回码 | 秒 | g138 复审秒 | 状态 | 尝试 |', '| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |']
    for r in rows:
        tries = '；'.join(f"{a['name']} rc={a['returncode']} {a['seconds']}s" for a in r['attempts'])
        lines.append(f"| {r['family']} | {r['unit']} | {r['group']} | {r['contract']} | {r['returncode']} | {r['seconds']} | "
                     f"{r['review_g138_seconds'] or ''} | {r['status']} | {tries} |")
    (HERE / 'REGRESSIONS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(total=len(rows), counts=counts)))


if __name__ == '__main__':
    main()
