"""Verify the review against its inputs and evidence; generate the final SHA256SUMS."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STUDIO=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(root,*args):
    return subprocess.check_output(['git','--no-optional-locks','-C',str(root),*args],
                                   env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},text=True).strip()

def main():
    snapshot=json.loads((HERE/'evidence/inputs-before.json').read_text())
    changed=[label for label,wanted in snapshot['sha256'].items()
             if not Path(label).is_file() or digest(Path(label))!=wanted]
    head=git(STUDIO,'rev-parse','HEAD')
    status=git(STUDIO,'status','--short','--untracked-files=all')
    assert head==snapshot['studio_head']=='6a50c77a8ba04c45ada308a1cbc28074a79116fb'
    assert status==snapshot['studio_status']==''
    assert git(ROOT,'rev-parse','HEAD')==snapshot['parent_head']
    audit=json.loads((HERE/'evidence/delta-audit.json').read_text())
    assert audit['status']=='PASS' and len(audit['real_packages'])==4
    assert len(audit['rejected_cases'])==30 and len(audit['other_generations'])==11
    assert len(audit['user_edits'])==6 and all(row['c_gate']==[0,0,0] for row in audit['user_edits'])
    assert audit['storage_replacements']==0 and audit['install_home_created'] is False
    for row in audit['rejected_cases']:
        for name in ('parse','pack','inspect_dat','_install'):
            assert row['paths'][name]['rejected']
        assert row['paths']['http-upload']==dict(status=422,code='dat_invalid')
    assert all(row['old_parser_accepts_canonical_roundtrip'] for row in audit['rejected_cases'][:4])
    assert '22 passed' in (HERE/'evidence/new-22-regressions.log').read_text()
    old=(HERE/'evidence/old-22-regressions.log').read_text()
    assert '22 failed' in old and old.count('Failed: DID NOT RAISE')==22
    assert '4 passed, 4 skipped' in (HERE/'evidence/parent-parser-absent.log').read_text()
    suite=ET.parse(HERE/'evidence/g156-all.xml').getroot().find('testsuite')
    assert suite is not None and suite.attrib['tests']=='107' and suite.attrib['failures']=='14' and suite.attrib['skipped']=='0'
    for stem in ('audit_dat','audit_intake'):
        assert digest(HERE/f'r1_{stem}.py')==digest(ROOT/f'research/review_studio_g156_r1/{stem}.py')
    report=(HERE/'REVIEW.md').read_text()
    assert report.splitlines()[0]=='可以合并'
    now=datetime.datetime.now(datetime.timezone.utc)
    assert now-datetime.datetime(2026,11,3,21,1,43,tzinfo=datetime.timezone.utc)<datetime.timedelta(hours=1)
    integrity=dict(finished_utc=now.isoformat(),checked_files=len(snapshot['sha256']),changed=changed,
                   studio_head=head,studio_status=status,parent_head=snapshot['parent_head'],
                   parent_status=git(ROOT,'status','--short','--untracked-files=all'),
                   matrix_cases=30,paths_per_case=5,verdict=report.splitlines()[0])
    (HERE/'evidence/integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n')
    assert not changed, changed
    paths={Path(label) for label in snapshot['sha256']}
    paths.update(p for p in HERE.glob('*') if p.is_file() and p.name!='SHA256SUMS')
    paths.update(p for p in (HERE/'evidence').rglob('*') if p.is_file())
    paths.update(p for p in (HERE/'parent-static/evidence').rglob('*') if p.is_file())
    paths.update(p for p in (HERE/'tmp/counterexamples').glob('*.dat'))
    paths.update(p for p in (HERE/'tmp').glob('*-users-*.dat'))
    paths.add(HERE/'tmp/parent-c-gate/parsers.dylib')
    for folder in (HERE/'parent-static/tmp',HERE/'tmp/gate155'):
        paths.update(folder.rglob('*.dylib'))
    lines=[]
    for path in sorted(paths):
        assert path.is_file(), path
        label=str(path.relative_to(HERE)) if path.is_relative_to(HERE) else str(path)
        lines.append(f'{digest(path)}  {label}\n')
    (HERE/'SHA256SUMS').write_text(''.join(lines))
    print(json.dumps(dict(status='PASS',unchanged_inputs=len(snapshot['sha256']),checksum_entries=len(paths),
                          matrix_cases=30,verdict=integrity['verdict']),ensure_ascii=False))

if __name__=='__main__':
    main()
