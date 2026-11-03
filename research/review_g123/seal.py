"""Seal review artifacts, or verify the repository-relative manifest read-only."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
PIN='4ee9e6fefcd33619bcd763eacba9c56be4d3fb265b9e2ca0d73d49d59b8c1e64'
START='2026-10-28T10:16:35+00:00'


def fence(event,args):
    paths=[]
    if event=='open':
        path,mode,flags=args
        if isinstance(path,(str,bytes,os.PathLike)) and (
            isinstance(mode,str) and any(c in mode for c in 'wax+') or
            isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            paths.append(path)
    elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.utime','os.truncate'):
        paths.append(args[0])
    elif event in ('os.rename','os.link','os.symlink'):
        paths.extend(args[:2])
    elif event in ('socket.connect','socket.bind','socket.getaddrinfo'):
        raise PermissionError('REVIEW_NETWORK_DISABLED')
    for path in paths:
        assert Path(os.fsdecode(path)).resolve().is_relative_to(OUT),path


sys.addaudithook(fence)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def protected():
    values=json.loads((OUT/'inputs-before.json').read_text())
    changed=[name for name,expected in values.items() if not (ROOT/name).is_file() or digest(ROOT/name)!=expected]
    assert not changed,changed
    dat=ROOT/'firmware/package_v36_g123/SD_ROOT/GXRCE.DAT'
    assert digest(dat)==PIN and dat.stat().st_size==62676
    return values


def check_report():
    text=(OUT/'REVIEW.md').read_text()
    assert text.splitlines()[0]=='不可以上测试卡'
    summary=json.loads((OUT/'evidence/review-summary.json').read_text())
    assert summary['status']=='REJECTED' and summary['blocking_P1']==summary['P2']==1
    for target in re.findall(r'\]\(([^)]+)\)',text):
        assert (OUT/target).exists(),target


def seal():
    before=protected()
    now=datetime.datetime.now(datetime.timezone.utc)
    minutes=(now-datetime.datetime.fromisoformat(START)).total_seconds()/60
    assert 0<=minutes<=90,minutes
    integrity=dict(status='PASS_FROZEN_INPUTS',frozen_inputs=len(before),changed_inputs=[],
        start_UTC=START,finish_UTC=now.isoformat(),wall_minutes=round(minutes,2),
        timebox_minutes=90,dat_sha256=PIN,
        write_scope='research/review_g123/',
        enforcement='Strict Python audit write fence and network denial in support.py; seal.py enforces the same directory boundary. Shell and objdump destinations were review-local.',
        camera_card_network_used=False,subagents_started=False,
        raw_Ricoh_bytes='local/',
        scope='Frozen inputs are checked individually; this is not a machine-wide filesystem audit.')
    (OUT/'integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n')
    check_report()
    values=dict(before)
    paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    assert not any(p.is_symlink() for p in paths)
    for p in paths:
        values[str(p.relative_to(ROOT))]=digest(p)
    manifest=''.join(value+'  '+name+'\n' for name,value in sorted(values.items()))
    (OUT/'SHA256SUMS').write_text(manifest)
    print('SEALED',len(values),'files;',len(before),'frozen inputs;',len(paths),'review files;',round(minutes,2),'minutes')


def check():
    protected();check_report()
    manifest=OUT/'SHA256SUMS';names=set()
    for line in manifest.read_text().splitlines():
        expected,name=line.split('  ',1)
        assert len(expected)==64 and not Path(name).is_absolute()
        p=(ROOT/name).resolve();assert p.is_relative_to(ROOT)
        assert p.is_file() and digest(p)==expected,name
        assert name not in names,name
        names.add(name)
    actual={str(p.relative_to(ROOT)) for p in OUT.rglob('*') if p.is_file() and p!=manifest}
    assert actual<=names,sorted(actual-names)
    assert set(json.loads((OUT/'inputs-before.json').read_text()))<=names
    print('PASS',len(names),'SHA256 entries; complete review coverage; frozen inputs unchanged')


if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--seal',action='store_true');group.add_argument('--check',action='store_true')
    args=parser.parse_args()
    seal() if args.seal else check()
