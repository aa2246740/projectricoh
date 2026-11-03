"""Root-relative output and protected-input checksums; check mode performs no writes."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def check(path):
    failures=[];count=0
    for line in path.read_text().splitlines():
        digest,relative=line.split('  ',1);target=ROOT/relative;count+=1
        if not target.is_file() or sha(target.read_bytes())!=digest:failures.append(relative)
    print('PASS' if not failures else 'FAIL',count,'SHA256 records',failures[:10])
    assert not failures,failures

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    target=OUT/'SHA256SUMS'
    if args.check:return check(target)
    old=OUT/'inputs-before.json'
    protected=json.loads(old.read_text())
    assert all((ROOT/name).is_file() and sha((ROOT/name).read_bytes())==digest for name,digest in protected.items())
    engine_sums=TREE/'EVIDENCE_SHA256SUMS'
    engine_paths=[path for path in sorted(TREE.rglob('*')) if path.is_file() and not path.is_symlink() and path!=engine_sums and path.name!='.DS_Store']
    engine_sums.write_text(''.join(sha(path.read_bytes())+'  '+str(path.relative_to(ROOT))+'\n' for path in engine_paths))
    paths={ROOT/name for name in protected}
    for folder in (OUT,TREE,PACKAGE):
        paths.update(path for path in folder.rglob('*') if path.is_file() and not path.is_symlink() and path!=target and path.name!='.DS_Store')
    target.write_text(''.join(sha(path.read_bytes())+'  '+str(path.relative_to(ROOT))+'\n' for path in sorted(paths)))
    check(target)

if __name__=='__main__':main()
