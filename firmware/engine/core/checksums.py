#!/usr/bin/env python3
"""Hash this task's sources, reports and local evidence. Never walks the repo."""
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE,LOCAL,guard

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();guard()
    output=HERE/'SHA256SUMS'
    if a.check:
        count=0
        for line in output.read_text().splitlines():
            expected,name=line.split('  ',1);path=(HERE/name).resolve();path.relative_to(HERE)
            if digest(path)!=expected:raise RuntimeError('SHA256 mismatch: '+name)
            count+=1
        print(f'PASS: {count} SHA256 entries')
        return
    lines=[]
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or path==output or path.is_symlink() or path.is_relative_to(LOCAL/'tmp'):continue
        lines.append(digest(path)+'  '+str(path.relative_to(HERE)))
    output.write_text('\n'.join(lines)+'\n');print(f'Wrote {len(lines)} SHA256 entries')
if __name__=='__main__':main()
