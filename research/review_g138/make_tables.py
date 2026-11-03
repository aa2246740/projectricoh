"""Summarize matrix receipts without turning stale assertions into passes."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PIN = '88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a'


def load(path):
    return json.loads(path.read_text())


def relative(path):
    return str(path.relative_to(OUT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    matrix = [job for job in load(OUT / 'queue.json')['jobs'] if job['kind'] == 'regression']
    assert len(matrix) == 81 and len({row['name'] for row in matrix}) == 81
    repairs = {job['matrix_name']: job for job in load(OUT / 'repair-queue.json')['jobs']}
    fixture = OUT / 'local/users-fixture/GXRCE.DAT'
    fixture_sha = hashlib.sha256(fixture.read_bytes()).hexdigest() if fixture.exists() else None
    rows = []
    for job in matrix:
        names = [job['name']]
        if job['name'] in repairs:
            names.append(repairs[job['name']]['name'])
        attempts = []
        for name in names:
            receipt = OUT / 'evidence/receipts' / (name + '.json')
            if receipt.exists():
                value = load(receipt)
                assert value['dat_sha256'] == PIN
                assert hashlib.sha256((ROOT / value['log']).read_bytes()).hexdigest() == value['log_sha256'], name
                value['receipt'] = relative(receipt)
                attempts.append(value)
        record = dict(name=job['name'], family=job['family'], unit=job['unit'], group=job['group'],
                      original_args=job['original_args'], args=job['args'], attempts=attempts,
                      status='NOT_STARTED', completed=False)
        if attempts:
            attempt = attempts[-1]
            record.update(returncode=attempt['returncode'], seconds=attempt['seconds'],
                          execution=attempt['execution'], receipt=attempt['receipt'],
                          work='legacy/local/jobs/' + attempt['name'])
            work = OUT / record['work']
            argument_index = next(i for i, item in enumerate(attempt['args']) if item.endswith('.py'))
            script = Path(attempt['args'][argument_index])
            tail = attempt['args'][argument_index + 1:]
            result_name = 'result-' + script.stem + '-' + '-'.join(tail).replace('/', '_') + '.json'
            candidates = list((work / 'local/checks').glob('*/' + result_name))
            record['result_files'] = [relative(path) for path in candidates]
            inner = [load(path) for path in candidates]
            record['completed'] = bool(inner) and attempt['execution'] == 'FINISHED'
            for value in inner:
                assert value['dat_sha256'] == PIN
                assert value['returncode'] == attempt['returncode']
            case_summaries = []
            for path in (work / 'local/checks').glob('*/evidence/*.json'):
                value = load(path)
                cases = value.get('cases')
                if isinstance(cases, list) and any(isinstance(case, dict) and 'wait_status' in case for case in cases):
                    waits = [case['wait_status'] for case in cases if 'wait_status' in case]
                    case_summaries.append(dict(file=relative(path), cases=len(waits),
                                               exit_zero=sum(status == 0 for status in waits),
                                               dat_sha256=value.get('dat_sha256')))
            record['case_summaries'] = case_summaries
            if not record['completed']:
                record['status'] = 'TOOL_NOT_EXECUTED'
            elif attempt['returncode'] == 0:
                assert all(case['cases'] == case['exit_zero'] for case in case_summaries)
                required_cases = {'values': 7, 'transitions': 42}.get(job['group'])
                if required_cases is not None:
                    assert any(case['cases'] == required_cases for case in case_summaries), (job['name'], required_cases, case_summaries)
                record['status'] = 'PASS'
            else:
                errors = [load(path) for path in (work / 'local/checks').glob('*/error-*.json')]
                record['errors'] = errors
                if job['group'] == 'project' and any(error.get('error') == 'KeyError' and 'uv_levels' in error.get('message', '') for error in errors):
                    record['status'] = 'STALE_RETIRED_FUNCTION'
                    replacement = OUT / 'boundary-sweep.json'
                    if replacement.exists():
                        record['replacement'] = dict(file=relative(replacement), status=load(replacement)['status'], layer='HOST_C')
                elif job['group'] == 'labels' and any(error.get('error') == 'AssertionError' and any(site.get('file', '').endswith('/label_acceptance.py') and site.get('line') == 12 for site in error.get('location', [])) for error in errors):
                    record['status'] = 'STALE_LABEL_CONTRACT'
                    replacement = OUT / 'evidence' / ('labels-current-' + job['unit'] + '.json')
                    if replacement.exists():
                        record['replacement'] = dict(file=relative(replacement), status=load(replacement)['status'], layer='M32R_MODEL')
                else:
                    record['status'] = 'FAIL_UNCLASSIFIED'
        rows.append(record)
    counts = dict(collections.Counter(row['status'] for row in rows))
    completed = sum(row['completed'] for row in rows)
    if args.final:
        assert completed == 81, (completed, counts)
        assert 'FAIL_UNCLASSIFIED' not in counts and 'TOOL_NOT_EXECUTED' not in counts, counts
    report = dict(dat_sha256=PIN, users_fixture_sha256=fixture_sha, completed=completed,
                  total=81, counts=counts, final=args.final, rows=rows)
    (OUT / 'REGRESSIONS.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    text = ['# g138 完整 81 组回归', '',
            ('状态为 FINAL。' if args.final else '状态为 RUNNING，尚未闭合的组不计通过。'), '',
            'DAT SHA256：`' + PIN + '`。', '',
            '整组返回 0 且对应内层结果已写完，才记为 PASS。旧函数或旧页面约定的失败保留原退出码；当前替代检查单列，不能改写成原组 PASS。修正读取前的回执保存在 JSON 的 attempts 中。', '',
            f'已执行完整组 {completed}/81。状态计数：' + '，'.join(f'{key} {value}' for key, value in sorted(counts.items())) + '。', '',
            '| 家族 | 单元 | 组 | 返回码 | 秒 | 状态 | 回执及替代证据 |',
            '| --- | --- | --- | ---: | ---: | --- | --- |']
    for row in rows:
        evidence = ('[' + row['receipt'] + '](' + row['receipt'] + ')') if row.get('receipt') else ''
        if row.get('replacement'):
            replacement = row['replacement']
            evidence += '；[' + replacement['layer'] + ' ' + replacement['status'] + '](' + replacement['file'] + ')'
        text.append('| ' + ' | '.join(str(value) for value in
                    [row['family'], row['unit'], row['group'], row.get('returncode', ''),
                     row.get('seconds', ''), row['status'], evidence]) + ' |')
    text += ['', '81 个槽位沿用原矩阵。两个家族的 values 和 transitions 槽位使用同一个当前运行器，保留各自执行回执，不称为两套独立实现。', '',
             '复跑入口、读取修改和证据边界见 REVIEW.md、WRAPPER.md。']
    (OUT / 'REGRESSIONS.md').write_text('\n'.join(text) + '\n')
    print(json.dumps(dict(completed=completed, counts=counts, final=args.final)), flush=True)


if __name__ == '__main__':
    main()
