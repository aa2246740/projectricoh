"""只清理本轮指定 TMPDIR，留下数量与字节回执。"""
from pathlib import Path
import json
import os
import shutil
import time

HERE=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1')

def main():
    assert TMP.parent==Path('/Volumes/Workspace/Scratch/tmp/projectricoh') and TMP.name=='g155-boot-r1'
    assert not TMP.is_symlink()
    files=[p for p in TMP.rglob('*') if p.is_file()]
    count=len(files);size=sum(p.stat().st_size for p in files)
    shutil.rmtree(TMP)
    assert not TMP.exists()
    result=dict(status='PASS',path=str(TMP),files=count,bytes=size,ended_ns=time.time_ns())
    (HERE/'evidence/cleanup.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
