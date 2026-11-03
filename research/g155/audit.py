"""核对冻结输入、源差异、最终包和统一上限。"""
from pathlib import Path
import difflib
import hashlib
import json
import os

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(p):
    return {str(f.relative_to(p)):f for f in p.rglob('*') if f.is_file() and not f.is_symlink() and 'local' not in f.relative_to(p).parts and '__pycache__' not in f.parts}

def main():
    original=json.loads((HERE/'evidence/inputs.json').read_text())
    drift=[name for name,value in original.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=value['sha256']]
    assert not drift,drift
    changes={};diff=[]
    pairs=[('engine','firmware/engine_v63_g154','firmware/engine_v64_g155'),
           ('resident','firmware/resident_v310_thin','firmware/resident_v310_g155')]
    for label,a,b in pairs:
        aa,bb=tree(ROOT/a),tree(ROOT/b);rows=[]
        for name in sorted(aa.keys()|bb.keys()):
            left=aa[name].read_bytes() if name in aa else b'';right=bb[name].read_bytes() if name in bb else b''
            if left==right:continue
            rows.append(dict(path=name,before_sha256=hashlib.sha256(left).hexdigest() if name in aa else None,
                after_sha256=hashlib.sha256(right).hexdigest() if name in bb else None))
            try:diff.extend(difflib.unified_diff(left.decode().splitlines(True),right.decode().splitlines(True),fromfile=a+'/'+name,tofile=b+'/'+name))
            except UnicodeDecodeError:pass
        changes[label]=rows
    (HERE/'evidence/source.diff').write_text(''.join(diff))
    limits={
        'firmware/resident_v310_g155/resident/resident.h':'RV_MAX_CODE=69632',
        'firmware/engine_v64_g155/resident/resident.h':'RV_MAX_CODE=69632',
        'firmware/engine_v64_g155/candidate/containers/product/src/firmware/card_container_v2/gate.c':'length>69632',
        'firmware/engine_v64_g155/candidate/containers/product/src/firmware/engine/core/eng_data.c':'length>69632',
        'firmware/engine_v64_g155/candidate/containers/product/engine.ld':'<= 69632',
        'firmware/engine_v64_g155/candidate/containers/product/pack.py':'> 69632',
        'firmware/engine_v64_g155/candidate/engine_services/library.ld':'<=69632',
        'firmware/engine_v64_g155/candidate/service_build.py':'max_engine_code=69632',
        'research/g155/build.py':"final['engine_bytes']<=69632",
        'research/g155/build_resident.py':"['engine']=69632",
        'firmware/engine_v64_g155/candidate/containers/product/build.py':"first=link(98304,'probe')",
    }
    for path,marker in limits.items():assert marker in (ROOT/path).read_text(),path
    sizes=[]
    for suffix in ('','_test'):
        folder=ROOT/('firmware/package_v310_g155'+suffix)
        assert sorted(p.name for p in folder.iterdir())==['GXRCE.DAT','MANIFEST']
        m=json.loads((folder/'MANIFEST').read_text());assert m['dat_sha256']==sha(folder/'GXRCE.DAT')
        assert m['code_bytes']<=69632 and m['main_request']<=107612 and m['dat_bytes']<=98304
        assert not m['body_image_built'] and not m['camera_verified'];sizes.append(m)
    result=dict(status='PASS',inputs=len(original),input_drift=drift,source_changes=changes,cap_readers=list(limits),sizes=sizes,
        no_body_image=True,package_files=['GXRCE.DAT','MANIFEST'])
    (HERE/'evidence/audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',inputs=len(original),source_changes={k:len(v) for k,v in changes.items()},cap_readers=len(limits))))

if __name__=='__main__':main()
