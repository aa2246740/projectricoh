"""Verify every frozen input and detect additions in protected directories."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT, OUT, save, file_sha

def verify(name,target,check_roots=False):
    before=json.loads((OUT/name).read_text())
    changed=[]
    expected={row['path_hex'] for row in before['files']}
    for row in before['files']:
        path=ROOT/bytes.fromhex(row['path_hex']).decode()
        if not path.is_file():
            changed.append(dict(path_hex=row['path_hex'],status='MISSING'))
        else:
            actual=file_sha(path)
            if actual!=row['sha256']:
                changed.append(dict(path_hex=row['path_hex'],status='CHANGED',
                                    expected=row['sha256'],actual=actual))
    added=[]
    if check_roots:
        current={(str(p.relative_to(ROOT))).encode().hex()
                 for root in before['roots'] for p in (ROOT/root).rglob('*') if p.is_file()}
        current.add('artifacts/downloads/gxr-151.zip'.encode().hex())
        added=sorted(current-expected)
    value=dict(status='PASS' if not changed and not added else 'FAIL',
               checked=len(before['files']),changed=changed,added_path_hex=added)
    save(target,value)
    assert value['status']=='PASS',value
    print('PASS frozen inputs',name,value['checked'],flush=True)

if __name__=='__main__':
    verify('inputs-before.json','input-integrity.json',True)
    verify('extra-inputs-before.json','extra-input-integrity.json')
