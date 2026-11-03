"""Read the final DATs, original C gates and persisted photo predictions again."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r
import argparse
import json
import struct
import subprocess
import zlib
import numpy as np
from PIL import Image

ap=argparse.ArgumentParser()
ap.add_argument('--write',action='store_true')
ap.add_argument('--hashes',action='store_true')
args=ap.parse_args()
src=r.module('bwstd_verify_src','firmware/stage2l_switch/tools/deep_sources.py')
_,old_surface=src.surface_bank()
surface=(r.LOCAL/'candidate/recipe_bank_reference.bin').read_bytes()
identity=(r.LOCAL/'candidate/recipe03.identity49.bin').read_bytes()
record=(r.LOCAL/'candidate/recipe03.record64.bin').read_bytes()
assert len(record)==64 and len(identity)==49
assert record[2:3]+record[4:36]+record[3:4]+record[36:51]==identity
assert record[0:4]==bytes([3,1,8,1]) and record[36:51]==bytes(15)
assert struct.unpack_from('>I',record,60)[0]==zlib.crc32(record[:60])
assert zlib.crc32(identity)==0x8015CBA7
manifests=json.loads((r.LOCAL/'candidate/manifest.json').read_text())
checks=[]
for m in manifests:
    unit=m['unit'];pin=0x0d2b0ea9 if unit=='50mm' else 0x4686301b
    src.STOCK_ENTRY_CRC=pin
    path=r.ROOT/m['candidate'];b=path.read_bytes();base=(r.ROOT/m['base']).read_bytes()
    assert r.freeze.digest(path)==m['sha256']
    old=src.parse(base,old_surface);new=src.parse(b,surface)
    assert (r.LOCAL/f'candidate/entry03_{unit}.bin').read_bytes()==b[1360:1808]
    changed=[i for i,(a,c) in enumerate(zip(base,b)) if a!=c]
    assert changed==m['changed_byte_offsets']
    assert all(12<=i<16 or 1360<=i<1808 for i in changed)
    assert new[3]['mask']==1 and new[3]['control']==2
    assert new[3]['written'][:2]==old[3]['written'][:2]
    assert new[3]['written'][2]==bytes(96)
    for off in (0,28):
        assert new[3]['written'][3][off:off+6]==old[3]['written'][3][off:off+6]
        assert new[3]['written'][3][off+6:off+18]==bytes(12)
    for variant,accepted in [('standard',True),('legacy',False)]:
        host=r.LOCAL/'host'/unit/variant
        assert (host/'deep_isp.c').read_bytes()==(r.ROOT/'firmware/stage2l_switch/deep_isp.c').read_bytes()
        cp=subprocess.run([str(host/'validator'),str(path),'accept' if accepted else 'reject'],
            capture_output=True,text=True,timeout=10)
        assert cp.returncode==0 and not cp.stderr
        checks.append(dict(unit=unit,variant=variant,stdout=cp.stdout))

# Recompute through the same real model, reloading the final candidate. The
# new entry uses a different key to select the ordinary colour computation.
sys.path.insert(0,str(r.ROOT/'research/module_adapt'))
import support as s
s.HERE,s.LOCAL=r.HERE,r.LOCAL
from unit_model import UnitModel
M=UnitModel('50mm',iso=200)
decode=M.fs.decode_word
M.fs.decode_word=lambda w:(0,0) if bytes(w)==bytes(4) else decode(w)
src.STOCK_ENTRY_CRC=0x0d2b0ea9
new=src.parse((r.LOCAL/'candidate/DEEPTBL_50mm_bw03_standard.DAT').read_bytes(),surface)
M.base.entries={f'{e["slot"]:02d}':e for e in new}
M.base.entries['standard03']=new[3]
frames=json.loads((r.LOCAL/'photo_frames.json').read_text())
summary=json.loads((r.LOCAL/'photo_summary.json').read_text())
all_dl=[];all_de=[]
for row in frames:
    with np.load(r.LOCAL/'samples'/(row['frame']+'.npz'),allow_pickle=False) as sample:
        x=sample['x'][sample['valid']];actual=sample['actual_selected']
        pred=M.predict(row['prediction_slot'],x)
        assert np.array_equal(pred,sample['predicted'])
    dl=abs(M.fs.lab_from_codes(pred)[:,0]-M.fs.lab_from_codes(actual)[:,0])
    de=M.de(pred,actual)
    assert abs(float(np.median(dl))-row['abs_dL']['median'])<1e-12
    assert abs(float(np.percentile(de,90))-row['de00']['p90'])<1e-12
    if row['prediction_slot']=='standard03':
        all_dl.extend(dl);all_de.extend(de)
        assert np.median(dl)<1 and np.max(np.ptp(pred,axis=1))==0
        for rel in row['predicted_jpegs']:
            with Image.open(r.HERE/rel) as im:
                assert im.size==(1072,712)
                if '_new03' in rel:assert np.max(np.ptp(np.asarray(im).astype(int),axis=2))==0
assert len(all_dl)==9727 and summary['flat_patches']==len(all_dl)
assert abs(float(np.median(all_dl))-summary['pooled_abs_dL']['median'])<1e-12
assert abs(float(np.percentile(all_de,90))-summary['pooled_de00']['p90'])<1e-12
tone=json.loads((r.LOCAL/'tone_ramps.json').read_text())
prior=json.loads((r.ROOT/'research/daily_bugs_20261024/local/tone_ramps.json').read_text())
assert np.array_equal(np.asarray(tone['standard03'])[prior['raw_neutral_codes']],prior['hc03'])
branches=json.loads((r.LOCAL/'branch_checks.json').read_text())
assert branches['all_passed'] and len(branches['checks'])==8
assert all(c['new_vs_legacy_max_code']<1e-10 and c['max_rgb_spread']<1e-10 for c in branches['checks'])
cp=subprocess.run([str(r.LOCAL/'host/settings/plan')],capture_output=True,text=True,timeout=10)
assert cp.returncode==0 and not cp.stderr
protected=r.freeze.verify()
result=dict(passed=True,protected_inputs=len(protected),all_protected_inputs_unchanged=True,
    decisions_tsv_excluded=not any(Path(k).name=='decisions.tsv' for k in protected),
    candidates=2,original_C_rechecks=checks,photo_frames_recomputed=len(frames),live03_frames=14,
    flat_patches=len(all_dl),prior_daily_tone_anchors_exact=True,branch_checks=8,
    S_plan=json.loads(cp.stdout),camera_acceptance=False,firmware_build=False)
assert result['decisions_tsv_excluded']
if args.write:r.dump('verification.json',result)
if args.hashes:
    count=0
    for line in (r.HERE/'SHA256SUMS').read_text().splitlines():
        h,name=line.split('  ',1)
        p=r.HERE/name
        assert p.resolve().is_relative_to(r.HERE) and r.freeze.digest(p)==h,name
        count+=1
    result['manifest_files_checked']=count
print(json.dumps(result,ensure_ascii=False))
