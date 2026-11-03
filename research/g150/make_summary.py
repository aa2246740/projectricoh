"""Tabulate g150 results from their receipts: queue A (case jobs) and the regression queue.

Freshness (g139 report section 5): every case result file must have been
written during its own job (mtime between the job's start and end) and name
the DAT it ran on; every regression job's artifacts under run/local/jobs/<job>
must all be newer than the job's start. A run shorter than 0.5 x the g139 time
of the same group/case is flagged SHORT. Output: RESULTS.json / RESULTS.md.
/usr/bin/python3 -I -B.
"""
from pathlib import Path
import datetime as dt
import glob
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def utc(ns):
    return dt.datetime.fromtimestamp(ns / 1e9, dt.timezone.utc).strftime('%H:%M:%SZ')


def cases():
    rows = []
    g139 = {}
    for f in glob.glob(str(ROOT / 'research/g139_fix/tests/local/checks/*.json')):
        g139[Path(f).stem] = json.loads(Path(f).read_text())['seconds']
    for f in sorted(glob.glob(str(HERE / 'evidence/receipts/*.json'))):
        r = json.loads(Path(f).read_text())
        if 'outputs' not in r:
            continue
        for o in r['outputs']:
            path = ROOT / o['path']
            data = json.loads(path.read_text()) if path.exists() else {}
            stem = path.stem
            ref = g139.get(stem) if r['job'].startswith('h-') else None
            fresh = bool(o.get('fresh')) and o.get('mtime_ns', 0) <= r['ended_ns']
            status = data.get('status')
            if status and status.startswith('PASS') and ref and data.get('seconds', 0) < 0.5 * ref:
                status = 'SHORT'
            rows.append(dict(job=r['job'], case=stem, status=status, seconds=data.get('seconds'), g139_seconds=ref,
                             dat=(data.get('dat_sha256') or '')[:8], fresh=fresh,
                             started=utc(r['started_ns']), written=utc(o['mtime_ns']) if o.get('mtime_ns') else None,
                             returncode=r['returncode']))
    return rows


def regressions():
    queue = HERE / 'queue-reg.json'
    if not queue.exists():
        return []
    rows = []
    for job in json.loads(queue.read_text())['jobs']:
        if job.get('kind') != 'regression':
            continue
        path = HERE / 'evidence/receipts' / (job['name'] + '.json')
        if not path.exists():
            rows.append(dict(name=job['name'], covers=job['covers'], status='NOT_RUN'))
            continue
        r = json.loads(path.read_text())
        if r.get('execution') == 'NOT_RUN_LEFT_FOR_RELEASE_REVIEW':
            rows.append(dict(name=job['name'], covers=job['covers'], status='留给发布复审', reason=r['reason']))
            continue
        work = HERE / 'run/local/jobs' / job['name']
        mtimes = [p.stat().st_mtime for p in work.rglob('*') if p.is_file()] if work.exists() else []
        start = os.path.getmtime(path) - r['seconds']
        old = [m for m in mtimes if m < start - 2]
        ref = max(job['g139_seconds'].values())
        status = 'PASS' if r['returncode'] == 0 and r['execution'] == 'FINISHED' else 'FAIL'
        if status == 'PASS' and r['seconds'] < 0.5 * min(job['g139_seconds'].values()):
            status = 'SHORT'
        if status == 'PASS' and (not mtimes or old):
            status = 'STALE'
        rows.append(dict(name=job['name'], covers=job['covers'], status=status, returncode=r['returncode'],
                         seconds=r['seconds'], g139_seconds=job['g139_seconds'], timeout=job['timeout_seconds'],
                         artifacts=len(mtimes), artifacts_older_than_start=len(old),
                         first=dt.datetime.fromtimestamp(min(mtimes), dt.timezone.utc).strftime('%H:%M:%SZ') if mtimes else None,
                         last=dt.datetime.fromtimestamp(max(mtimes), dt.timezone.utc).strftime('%H:%M:%SZ') if mtimes else None,
                         dat=r['dat_sha256'][:8], log_sha256=r['log_sha256'][:12]))
    return rows


def main():
    c, g = cases(), regressions()
    count = lambda rows, key: {s: sum(1 for r in rows if r[key] == s) for s in sorted({r[key] for r in rows})}
    (HERE / 'RESULTS.json').write_text(json.dumps(dict(cases=c, regressions=g, case_counts=count(c, 'status'),
                                                       regression_counts=count(g, 'status')), indent=1) + '\n')
    lines = ['# g150 测试结果（由 make_summary.py 从回执生成）', '',
             '## 用例', '', '| 作业 | 用例 | 状态 | 秒 | g139 秒 | DAT | 开始 | 写入 | 新鲜 |', '| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |']
    for r in c:
        lines.append(f"| {r['job']} | {r['case']} | {r['status']} | {r['seconds']} | {r['g139_seconds'] or ''} | {r['dat']} | "
                     f"{r['started']} | {r['written']} | {'是' if r['fresh'] else '否'} |")
    lines += ['', '## 回归组', '', '| 运行 | 覆盖的组 | 状态 | 秒 | g139 秒 | 超时 | 产物数 | 产物时间 | DAT |',
              '| --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |']
    for r in g:
        if r['status'] in ('NOT_RUN', '留给发布复审'):
            lines.append(f"| {r['name']} | {'、'.join(r['covers'])} | {r['status']} | | | | | {r.get('reason', '')} | |")
            continue
        lines.append(f"| {r['name']} | {'、'.join(r['covers'])} | {r['status']} | {r['seconds']} | "
                     f"{' / '.join(str(v) for v in r['g139_seconds'].values())} | {r['timeout']} | {r['artifacts']} | "
                     f"{r['first']}–{r['last']} | {r['dat']} |")
    (HERE / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(cases=count(c, 'status'), regressions=count(g, 'status'))))


if __name__ == '__main__':
    main()
