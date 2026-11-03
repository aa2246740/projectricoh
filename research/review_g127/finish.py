#!/usr/bin/python3
"""Finish the timeboxed review only after its executors have exited."""
from pathlib import Path
import datetime
import hashlib
import json
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'
PY=['/usr/bin/python3','-I','-B']

def run(script):
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(OUT/'write-fence.sb'),*PY,str(OUT/script)],cwd=ROOT,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(script+' returncode '+str(result.returncode))
    print(result.stdout.strip(),flush=True)

def main():
    names={'run_regressions.py','run_priority.py','run_additional.py'}
    expected={str(OUT/name) for name in names}|{'research/review_g127/'+name for name in names}
    raw=subprocess.run(['ps','-ax','-o','pid=,command='],capture_output=True,text=True,check=True).stdout
    active=[]
    for line in raw.splitlines():
        parts=line.split(None,1)
        if len(parts)!=2:continue
        try:argv=shlex.split(parts[1])
        except ValueError:continue
        if any(arg in expected for arg in argv):
            active.append(int(parts[0]))
    assert not active, 'review executors remain active'
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT/'process-final.json').write_text(json.dumps(dict(checked_utc=now,
        active_review_executors=0,method='exact executor argument match'),indent=2)+'\n')
    for script in ('summarize_regressions.py','summarize_history.py','summarize_controls.py','write_review.py'):
        run(script)
    matrix=json.loads((OUT/'regressions.json').read_text())
    history=json.loads((OUT/'history122.json').read_text())
    assert len(matrix['groups'])==81 and len(matrix['extra'])==6 and len(history)==27
    assert (OUT/'REVIEW.md').read_text().splitlines()[0]=='不可以上测试卡'
    remaining=sum(row['status']!='PASS' for row in matrix['groups'])
    lines=['本轮验证已结束，所有本轮协调器均已退出。','',
        f'主矩阵闭合 {matrix["groups_complete"]}/81，失败 {matrix["groups_failed"]}，未闭合 {remaining}。',
        '附加 history123、settings_cases 六个单元均按最终结果表列出；gen 122 保留二十七条 OBSERVED。',
        '最终结论为不可以上测试卡，P1-02 的 H07 父层重构切点仍未闭合。',
        '本轮曾短暂出现六组重叠，已在 REVIEW.md 与 queue-change.json 保留执行偏差。',
        '本轮结束后的重跑应按 REPRODUCE.md 指定新的截止时间；重跑会改变 local 记录，需要重新汇总和封存。',
        '',f'结束汇总时间：{now}。']
    (OUT/'STATE.md').write_text('\n'.join(lines)+'\n')
    run('seal.py')
    count=0
    errors=0
    for line in (OUT/'SHA256SUMS').read_text().splitlines():
        expected_hash,name=line.split('  ',1)
        relative=Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        actual=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
        errors+=actual!=expected_hash
        count+=1
    assert not errors
    print(json.dumps(dict(name='final-sha256',returncode=0,files=count,errors=errors)),flush=True)

if __name__=='__main__':
    main()
