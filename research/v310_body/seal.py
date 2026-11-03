#!/usr/bin/python3
"""Verify frozen inputs, clean the task scratch directory, and seal delivered files."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')
sys.path.insert(0,str(HERE))
from launch import active


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sums(paths,target):
    target.write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(set(paths))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--final',action='store_true')
    a=p.parse_args()
    if a.final:
        assert not active(),'tests are still active'
        frozen=json.loads((HERE/'evidence/frozen-inputs.json').read_text())
        changed=[name for name,digest in frozen.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=digest]
        assert not changed,changed
        (HERE/'evidence/frozen-verification.json').write_text(json.dumps(dict(
            files=len(frozen),changed=changed,verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
        if TEMP.exists():shutil.rmtree(TEMP)
        assert not TEMP.exists()
        (HERE/'evidence/cleanup.json').write_text(json.dumps(dict(temporary=str(TEMP),
            deleted=True,residual_test_processes=active(),protected_input_changes=0,
            finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
        for suffix in ('','_test'):
            package=ROOT/('firmware/package_v310_g155'+suffix)
            manifest=json.loads((package/'MANIFEST').read_text())
            manifest.update(acceptance='defects',verdict='有缺陷',report='research/v310_body/REPORT.md',camera_verified=False)
            (package/'MANIFEST').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
            sums([f for f in package.rglob('*') if f.is_file() and f.name!='SHA256SUMS'],package/'SHA256SUMS')
        image=ROOT/'firmware/image_v310'
        sums([f for f in image.rglob('*') if f.is_file() and f.name!='SHA256SUMS'],image/'SHA256SUMS')
    paths=[]
    for base in (HERE,ROOT/'firmware/image_v310',ROOT/'firmware/package_v310_g155',ROOT/'firmware/package_v310_g155_test'):
        paths += [f for f in base.rglob('*') if f.is_file() and f not in (HERE/'SHA256SUMS',HERE/'SHA256SUMS.partial')]
    target=HERE/('SHA256SUMS' if a.final else 'SHA256SUMS.partial')
    sums(paths,target)
    print(json.dumps(dict(final=a.final,files=len(paths),manifest=str(target),sha256=sha(target))))


if __name__=='__main__':main()
