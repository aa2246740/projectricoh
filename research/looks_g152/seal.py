"""Hash the final review material, packages and retained fit inputs."""
from pathlib import Path
import hashlib
import json
import os

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ENGINE=ROOT/'firmware/engine_v60_g152'
PACKAGES=[ROOT/'firmware/package_v38_g152',ROOT/'firmware/package_v38_g152_test']

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    audit=json.loads((HERE/'evidence/final_audit.json').read_text())
    assert audit['status'] in ('PASS','PARTIAL')
    verdict=(HERE/'REPORT.md').read_text().splitlines()[0]
    assert verdict==('有缺陷' if audit['status']=='PARTIAL' else '可以交复审')
    files=set()
    for base in [HERE,ENGINE,*PACKAGES]:
        for directory,dirs,names in os.walk(base,followlinks=False):
            dirs[:]=[n for n in dirs if n not in ('local','SD_ROOT','__pycache__')]
            for name in names:
                path=Path(directory)/name
                if not path.is_symlink() and path!=HERE/'SHA256SUMS':files.add(path)
    for package in PACKAGES:files.update(p for p in (package/'local/SD_ROOT').iterdir() if p.is_file())
    for name in ('GXRCE.DAT','engine.elf','engine.bin','layout.json','manifest.json'):
        files.add(ENGINE/'candidate/local/full-r13'/name)
    files.update(p for p in (HERE/'local/luts').iterdir() if p.is_file())
    files.update((HERE/'local/fits').glob('*/quantized.json'))
    files.add(HERE/'local/effects.json')
    history=HERE/'local/earlier-candidate-159d/SHA256SUMS'
    if history.is_file():files.add(history)
    previous=HERE/'local/review-fix-prior/SHA256SUMS'
    if previous.is_file():files.add(previous)
    witness=HERE/'local/review-fix-runtime/runtime/evidence'
    if witness.is_dir():files.update(p for p in witness.iterdir() if p.is_file())
    lines=[f'{digest(path)}  {path.relative_to(ROOT)}\n' for path in sorted(files)]
    (HERE/'SHA256SUMS').write_text(''.join(lines))
    for path,line in zip(sorted(files),lines):assert digest(path)==line.split('  ',1)[0]
    print(json.dumps(dict(status='PASS',files=len(files),sha256sums_sha256=digest(HERE/'SHA256SUMS'))))

if __name__=='__main__':main()
