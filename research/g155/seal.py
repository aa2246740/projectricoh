"""封存本轮允许目录，并核对写出的每个摘要。"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    folders=[HERE,ROOT/'firmware/engine_v64_g155',ROOT/'firmware/resident_v310_g155',
        ROOT/'firmware/package_v310_g155',ROOT/'firmware/package_v310_g155_test']
    files=[]
    for folder in folders:
        for p in folder.rglob('*'):
            if p.is_file() and not p.is_symlink() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts:
                files.append(p)
    result=''.join(f'{sha(p)}  {p.relative_to(ROOT)}\n' for p in sorted(files))
    (HERE/'SHA256SUMS').write_text(result)
    for line in result.splitlines():
        expected,name=line.split('  ',1);assert sha(ROOT/name)==expected,name
    print(json.dumps(dict(status='PASS',files=len(files),checksum_file=str((HERE/'SHA256SUMS').relative_to(ROOT)))))

if __name__=='__main__':main()
