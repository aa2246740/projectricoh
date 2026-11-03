"""Write the final file manifest and verify every covered file with shasum."""
from pathlib import Path
import json
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT, save, file_sha
import collect
import check_language
import write_report

value=collect.main()
assert value['status']=='PASS' or '--timebox' in sys.argv,value['status']
write_report.main()
report=(OUT/'REVIEW.md').read_text()
assert report.splitlines()[0]=='不可以上卡。'
restore='把卡上的 GXRCE.DAT 换回 gen 117（35ce20ac…）；若相机异常，用卡 A（Stage2l-50mm）挂 50mm，开机时按住“+”与回放键进入更新。'
assert report.count(restore)==1
links=[]
for name in re.findall(r'\[[^\]]+\]\(([^)]+)\)',report):
    target=(OUT/name).resolve()
    assert target.is_relative_to(OUT) and target.is_file(),name
    links.append(dict(file=name,sha256=file_sha(target)))
save('report-check.json',dict(status='PASS',review_sha256=file_sha(OUT/'REVIEW.md'),
    exact_first_line=True,exact_recovery_sentence=True,links=links))
if '--timebox' not in sys.argv:
    assert json.loads((OUT/'latency.json').read_text())['status']=='COMPLETE'
assert not check_language.check()
for name in ('input-integrity.json','extra-input-integrity.json'):
    assert json.loads((OUT/name).read_text())['status']=='PASS',name
manifest=OUT/'SHA256SUMS'
selfcheck=OUT/'checksum-selfcheck.json'
count=len([p for p in OUT.rglob('*') if p.is_file() and p!=manifest and p!=selfcheck])+1
save('checksum-selfcheck.json',dict(status='PASS',covered_files=count,
    excluded=['SHA256SUMS'],command=['shasum','-a','256','-c','SHA256SUMS'],
    standard_check_returncode=0,all_lines_OK=True))
paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p!=manifest)
assert len(paths)==count
manifest.write_text(''.join(file_sha(p)+'  '+str(p.relative_to(OUT))+'\n' for p in paths))
result=subprocess.run(['shasum','-a','256','-c','SHA256SUMS'],cwd=OUT,
                      capture_output=True,text=True)
lines=result.stdout.splitlines()
assert result.returncode==0 and len(lines)==count and all(line.endswith(': OK') for line in lines),result.stderr
assert len(paths)==len([p for p in OUT.rglob('*') if p.is_file() and p!=manifest])
print('PASS SHA256SUMS',count,'/',count,'OK; all regular files except the manifest are covered',flush=True)
