"""只清理本任务临时目录，保存清理回执。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-impl-r1')


def main():
    mount=json.loads((HERE/'mount.json').read_text())
    assert os.path.ismount('/Volumes/Workspace') and os.stat('/Volumes/Workspace').st_dev==mount['device']
    result=subprocess.run(['pgrep','-fal','research/g154/(batch|run)'],text=True,capture_output=True)
    assert result.returncode in (0,1)
    rows=[line for line in result.stdout.splitlines() if int(line.split()[0]) not in (os.getpid(),os.getppid())]
    assert not rows,rows
    counts={}
    for path in (TMP,HERE/'local/native',HERE/'local/variants'):
        if path.exists():
            counts[str(path)]=sum(p.is_file() for p in path.rglob('*'));shutil.rmtree(path)
        assert not path.exists()
    receipt=dict(status='PASS',completed_ns=time.time_ns(),removed_files=counts,active_test_processes=rows,
        retained='保留旧候选的比较证据、旧脚本和正式构建产物；临时测试变体已清理。')
    (HERE/'evidence/cleanup.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
