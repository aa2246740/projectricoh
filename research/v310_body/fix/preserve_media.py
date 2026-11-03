#!/usr/bin/python3
"""Retain exact observed virtual media as local evidence before temporary cleanup."""
import hashlib
import json
import os
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-body-pack-r1')


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    destination=HERE/'local/media';destination.mkdir(exist_ok=True)
    rows=[]
    for source in sorted(TEMP.rglob('*.img')):
        sha=digest(source);target=destination/(sha+'.img')
        if not target.exists():shutil.copyfile(source,target)
        assert digest(target)==sha
        rows.append(dict(original=str(source),retained=str(target.relative_to(ROOT)),sha256=sha,bytes=source.stat().st_size))
    receipt=dict(purpose='Exact media required by actual RAM/device snapshots; these are retained evidence, not temporary files',
        source_root=str(TEMP),files=rows,unique_media=len({x['sha256'] for x in rows}),
        retained_bytes=sum(p.stat().st_size for p in destination.glob('*.img')))
    (HERE/'evidence/media-retention.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}))


if __name__=='__main__':main()
