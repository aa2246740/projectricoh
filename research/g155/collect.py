"""在删除 Scratch 前保存可复审的返回片段与后端摘要。"""
from pathlib import Path
import hashlib
import json
import shutil

HERE=Path(__file__).resolve().parent
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1')

def main():
    saved=[]
    for unit in ('50mm','mount'):
        source=TMP/'retire-live'/unit;target=HERE/'evidence/retire-live'/unit;target.mkdir(parents=True,exist_ok=True)
        for name in ('return.S','return.ld','return.o','return.elf'):
            p=source/name;assert p.is_file(),p;shutil.copyfile(p,target/name)
            saved.append(dict(path=str((target/name).relative_to(HERE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    metrics=[]
    for p in (HERE/'evidence').glob('job-accepted-*.log'):
        for line in p.read_text().splitlines():
            if not line.startswith('{'):continue
            try:row=json.loads(line)
            except json.JSONDecodeError:continue
            if 'native_stats' in row:
                stats=row['native_stats'];assert stats['instructions']>0 and not stats['fallback_calls'] and not stats['fallback_steps']
                metrics.append(dict(job=p.name,native_stats=stats))
    for p in (HERE/'evidence').glob('navigation-*-c.json'):
        row=json.loads(p.read_text());stats=row['details']['audit']['native_stats']
        assert stats['instructions']>0 and not stats['fallback_calls'] and not stats['fallback_steps']
        metrics.append(dict(job=p.name,native_stats=stats))
    result=dict(status='PASS',saved=saved,native_backend_metrics=metrics)
    (HERE/'evidence/collected.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status='PASS',saved=len(saved),native_backend_samples=len(metrics))))

if __name__=='__main__':main()
