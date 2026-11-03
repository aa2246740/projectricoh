"""Check both native matrix selections on each candidate, including ISO100."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r
import json
import numpy as np

sys.path.insert(0,str(r.ROOT/'research/module_adapt'))
import support as s
s.HERE,s.LOCAL=r.HERE,r.LOCAL
from unit_model import UnitModel
src=r.module('bwstd_branches_src','firmware/stage2l_switch/tools/deep_sources.py')
_,legacy_surface=src.surface_bank()
surface=(r.LOCAL/'candidate/recipe_bank_reference.bin').read_bytes()
params=json.loads((r.ROOT/'research/module_adapt/local/official_parameters.json').read_text())
rng=np.random.default_rng(20261025)
x=np.vstack([np.repeat(np.arange(4096,dtype=float)[:,None],3,axis=1),rng.uniform(0,4095,(5000,3))])
results=[]
for unit,pin,rel in (
    ('50mm',0x0d2b0ea9,'research/gr4_nega_returns_r1/local/candidate/DEEPTBL_50mm_gr4_posi_nega_r1.DAT'),
    ('mount',0x4686301b,'research/gr4_nega_returns_r1/local/mount/candidate/DEEPTBL_mount_gr4_posi_nega_r1.DAT')):
    M=UnitModel(unit,iso=200)
    decode=M.fs.decode_word
    M.fs.decode_word=lambda w,d=decode:(0,0) if bytes(w)==bytes(4) else d(w)
    src.STOCK_ENTRY_CRC=pin
    old=src.parse((r.ROOT/rel).read_bytes(),legacy_surface)
    new=src.parse((r.LOCAL/f'candidate/DEEPTBL_{unit}_bw03_standard.DAT').read_bytes(),surface)
    M.base.entries={f'{e["slot"]:02d}':e for e in old}
    M.base.entries['standard03']=new[3]
    official=r.Image(params['units'][unit]['firmware'])
    for iso in (200,100):
        entries=dict(M.base.entries)
        if iso==100:
            for key in ('03','standard03'):
                e=dict(entries[key]);rows=list(e['written'])
                a5=params['units'][unit]['rows']['A5']['vma'];b5=params['units'][unit]['rows']['B5']['vma']
                rows[0]=official.read(a5+9*62,62);rows[1]=official.read(b5+9*33,33)
                e['written']=tuple(rows);M.base.entries[key]=e
        for index in range(2):
            oldrow=M.mm.MatrixRow.from_bytes(old[3]['written'][3][28*index:28*(index+1)])
            newrow=M.mm.MatrixRow.from_bytes(new[3]['written'][3][28*index:28*(index+1)])
            before=M.predict('03',x,row=oldrow);after=M.predict('standard03',x,row=newrow)
            result=dict(unit=unit,iso=iso,matrix_row=index+1,samples=len(x),
                new_vs_legacy_max_code=float(np.max(abs(after-before))),
                max_rgb_spread=float(np.ptp(after,axis=1).max()))
            assert result['new_vs_legacy_max_code']<1e-10 and result['max_rgb_spread']<1e-10,result
            results.append(result)
        M.base.entries=entries
r.dump('branch_checks.json',dict(checks=results,all_passed=True,mount_camera_acceptance=False))
# Correct a descriptive ISO list from the already verified frame records;
# no prediction or acceptance threshold changes.
summary=json.loads((r.LOCAL/'photo_summary.json').read_text())
summary['calibration_scope']='Existing ISO200 04 calibration borrowed for ISO800/1600/3200 scene prediction; no frame refit.'
r.dump('photo_summary.json',summary)
r.freeze.add(r.ROOT/p for p in s.INPUTS)
r.freeze.verify()
print(json.dumps(results))
