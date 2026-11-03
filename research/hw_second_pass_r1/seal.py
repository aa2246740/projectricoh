"""Freeze all task files, recheck protected inputs and verify the entire manifest."""
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def files():
    out=[]
    for p in sorted(HERE.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file() and p!=HERE/'SHA256SUMS':out.append(p)
    return out


def main():
    mount=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and mount['FilesystemType']=='apfs'
    assert mount['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert mount['WritableMedia'] and mount['WritableVolume']
    inputs={}
    for path in sorted((HERE/'local/inputs').glob('*.json')):
        doc=json.loads(path.read_text())
        assert doc['all_inputs_unchanged']
        for name,value in doc['sha256'].items():
            assert name not in inputs or inputs[name]==value,name
            inputs[name]=value
    for name,value in inputs.items():assert digest(ROOT/name)==value,name
    verified=json.loads((HERE/'local/verification/final.json').read_text())
    assert verified['all_expected_fits_present'] and verified['all_fields_valid']
    assert verified['independent_packed_max_rgb']<1e-8
    report=(HERE/'REPORT.md').read_text()
    assert '<!--' not in report,'Report still contains unfilled conclusions'
    count=len([p for p in files() if p!=HERE/'local/verification/seal.json'])+1
    record=dict(protected_inputs=len(inputs),all_inputs_unchanged=True,
                expected_manifest_files=count,manifest_self_excluded=True,
                prediction_label='电脑预测',firmware_build=False,camera=False,
                independent_fit_verification=verified['fits'],
                report_sha256=digest(HERE/'REPORT.md'))
    (HERE/'local/verification/seal.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    inventory=files();assert len(inventory)==count
    manifest=HERE/'SHA256SUMS'
    manifest.write_text(''.join(f'{digest(p)}  {p.relative_to(HERE)}\n' for p in inventory))
    seen=[]
    for row in manifest.read_text().splitlines():
        value,name=row.split('  ',1);p=HERE/name
        assert p.resolve().is_relative_to(HERE) and digest(p)==value,name
        seen.append(p)
    assert seen==files(),'Manifest coverage changed during sealing'
    print(json.dumps(dict(files=len(seen),all_OK=True,protected_inputs=len(inputs),
                          protected_inputs_unchanged=True,manifest=str(manifest)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
