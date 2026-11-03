"""Verify report links, required verdict, receipt completion, and file hashes."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *

def main():
    guard(False);assert not TMP.exists()
    report=(HERE/'REVIEW.md').read_text();assert report.splitlines()[0]=='不能上卡'
    assert len(re.findall(r'^## [1-9]\. ',report,re.M))==9
    missing=[]
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if target.startswith(('http://','https://','#')):continue
        p=(HERE/target).resolve()
        if not p.is_file():missing.append(target)
    assert not missing,missing
    jobs=json.loads((HERE/'evidence/accepted-jobs.json').read_text());assert jobs['count']==23
    audit=json.loads((HERE/'evidence/final-input-audit.json').read_text());assert audit['status']=='PASS'
    cleanup=json.loads((HERE/'evidence/cleanup.json').read_text());assert cleanup['removed'] and not cleanup['after_exists']
    dat();dat(True)
    save('evidence/delivery-check.json',dict(status='PASS',verdict='不能上卡',P1=1,P2=2,
         report_sha256=sha((HERE/'REVIEW.md').read_bytes()),dat_sha256=EXPECTED,baseline_sha256=BASE_SHA,
         accepted_jobs=23,report_links_exist=True,scratch_absent=True,
         qualification='Delivery verification does not turn checklist item 9 into PASS.'))
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and not p.is_symlink() and p.name!='SHA256SUMS')
    manifest=''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n' for p in paths)
    (HERE/'SHA256SUMS').write_text(manifest)
    for line in manifest.splitlines():
        digest,relative=line.split('  ',1);assert sha((ROOT/relative).read_bytes())==digest
    assert not TMP.exists()
    print(json.dumps(dict(status='PASS',files=len(paths),verdict='不能上卡',P1=1,P2=2,report=str(HERE/'REVIEW.md'),scratch_removed=True)))

if __name__=='__main__':main()
