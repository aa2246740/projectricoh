"""核对本轮输入、独立回执和进程，再清理指定临时目录。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g154-r1')
sys.path.insert(0,str(HERE))
import freeze


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==10
    before=json.loads((HERE/'evidence/inputs-before.json').read_text())
    after=freeze.inputs()
    changed=[name for name in before.keys()|after.keys() if before.get(name)!=after.get(name)]
    assert not changed,changed
    (HERE/'evidence/inputs-after.json').write_text(json.dumps(dict(status='PASS',files=len(after),changed=changed),indent=2)+'\n')
    process=subprocess.run(['/usr/bin/pgrep','-af','[r]esearch/review_g154/run[.]py'],capture_output=True,text=True,timeout=30)
    assert process.returncode==1,(process.returncode,process.stdout,process.stderr)
    dat=ROOT/'firmware/package_v39_g154_test/SD_ROOT/GXRCE.DAT'
    assert hashlib.sha256(dat.read_bytes()).hexdigest()=='ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e'
    report=(HERE/'REVIEW.md').read_text()
    assert report.splitlines()[0]=='修改后再上卡' and 'P1-01' in report
    assert TMP.resolve()==TMP and TMP.is_dir()
    files=[p for p in TMP.rglob('*') if p.is_file()]
    count=len(files);size=sum(p.stat().st_size for p in files)
    shutil.rmtree(TMP)
    assert not TMP.exists()
    ended=datetime.datetime.now().astimezone()
    start=datetime.datetime.fromisoformat('2026-11-02T06:38:40+08:00')
    result=dict(status='PASS',input_files=len(after),changed_inputs=changed,active_review_runs=[],
                pgrep_returncode=process.returncode,TMPDIR=str(TMP),deleted_files=count,deleted_bytes=size,
                tmp_exists=False,ended=ended.isoformat(),wall_minutes=(ended-start).total_seconds()/60,
                verdict='修改后再上卡',P1=['MOUNT 两项 OPEN 尚缺 Python 复核'])
    (HERE/'evidence/cleanup.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (HERE/'PROGRESS.md').write_text(f"{ended.isoformat()} 复审收尾。结论：修改后再上卡。\n\n"
        "所选 C 抽查全部通过。50mm OPEN 已在 Python 确认；MOUNT OPEN 的 Python 复核未完成，列 P1-01。\n"
        f"冻结输入 {len(after)} 项无变化，指定临时目录已删除，无仍在运行的复审作业。\n"
        "未访问相机、存储卡、网络或 Git 写入；没有子代理。初始准备与计时差异详见 REVIEW.md。\n")
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
