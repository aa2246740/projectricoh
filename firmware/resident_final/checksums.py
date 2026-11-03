#!/usr/bin/env python3
"""Hash all task source, deliverables and retained evidence except temporary files."""
import argparse
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and p!=HERE/'SHA256SUMS'
                  and 'tmp' not in p.relative_to(HERE).parts and '__pycache__' not in p.parts)
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    current=''.join(sha(f)+'  '+f.relative_to(HERE).as_posix()+'\n' for f in files())
    target=HERE/'SHA256SUMS'
    if a.check:assert target.read_text()==current,'task files changed; regenerate SHA256SUMS'
    else:target.write_text(current)
    print(('PASS' if a.check else 'WROTE')+' SHA256SUMS files='+str(len(files())))
if __name__=='__main__':main()
