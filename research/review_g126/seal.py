"""Freeze the review, preserve real command results and verify root-relative hashes."""
from pathlib import Path
import datetime
import hashlib
import json
import shlex
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
ROOTS=('firmware/engine_v47_fix','firmware/engine_v46_ui','firmware/engine_v43_fix',
       'firmware/package_v36_g126','firmware/package_v36_g124','firmware/package_v36_g121',
       'research/review_g124','research/review_g123','research/review_g122','research/g126_fix',
       'research/g122_keep_list','tools/native_harness','firmware/resident_v36')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def main():
    before=json.loads((OUT/'inputs-before.json').read_text())
    current={str(p.relative_to(ROOT)):sha(p) for name in ROOTS for p in (ROOT/name).rglob('*')
             if p.is_file() and not p.is_symlink()}
    changed=[p for p,h in before.items() if p in current and current[p]!=h]
    missing=sorted(set(before)-set(current))
    added=sorted(set(current)-set(before))
    state=subprocess.run(['git','--no-optional-locks','status','--short','--untracked-files=no'],
                         cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines()
    integrity=dict(status='PASS' if not changed and not missing and not added else 'FAIL',
        frozen_files=len(before),current_files=len(current),changed=changed,missing=missing,added=added,
        tracked_status=state,closed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='Read-only identity comparison of the declared protected input roots. Review outputs are excluded.')
    (OUT/'integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n')
    assert not changed and not missing and not added,integrity
    records=[json.loads(line) for line in (OUT/'commands.jsonl').read_text().splitlines()]
    actual=[r for r in records if 'returncode' in r]
    lines=['# 实际验证命令\n\n',
           '工作目录为 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh`。以下来自本轮实际命令记录，保留非零返回码。读取源码、指令文件和状态的辅助命令不列作测试通过证据。\n\n']
    for r in actual:
        lines.append('## '+r.get('label','command')+'\n\n')
        lines.append('```sh\n'+shlex.join(r['argv'])+'\n```\n\n')
        lines.append('返回码：'+str(r['returncode'])+'。')
        if r.get('log'):lines.append('日志：`'+r['log']+'`。')
        if r.get('reason'):lines.append(r['reason'])
        lines.append('\n\n')
    lines.append('## 封存\n\n```sh\n/usr/bin/python3 -I -B research/review_g126/seal.py\n```\n')
    (OUT/'COMMANDS.md').write_text(''.join(lines))
    own=[p for p in OUT.rglob('*') if p.is_file() and not p.is_symlink() and p.name!='SHA256SUMS']
    hashes=dict(current)
    hashes.update({str(p.relative_to(ROOT)):sha(p) for p in own})
    (OUT/'SHA256SUMS').write_text(''.join(h+'  '+p+'\n' for p,h in sorted(hashes.items())))
    failures=[p for p,h in hashes.items() if sha(ROOT/p)!=h]
    assert not failures,failures
    print('SEALED',len(own),'review files;',len(before),'protected inputs;',len(hashes),'root-relative hashes verified')
    print('REVIEW_SHA256',sha(OUT/'REVIEW.md'))
    print('SHA256SUMS_SHA256',sha(OUT/'SHA256SUMS'))

if __name__=='__main__':main()
