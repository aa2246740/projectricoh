"""Recompute fit scores from the final packaged DAT, never from fit callbacks."""
from pathlib import Path
import json
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import fit_looks as F
from dat_format import expand_effect,expand,strict_effects,sha
import numpy as np

def main():
    started=time.time_ns();tick=time.monotonic()
    raw=(F.ROOT/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT').read_bytes()
    strict_effects(raw);camera=F.Camera();scenes=F.prepare(camera,F.DEFAULT_SCENES,280)
    effects=json.loads((HERE/'local/effects.json').read_text());original=json.loads((HERE/'fit_results.json').read_text());rows=[]
    for i,effect in enumerate(effects):
        encoded=expand_effect(raw,i);cube=F.Cube.read(HERE/'local/luts'/effect['source'])
        assert cube.source_sha256==effect['source_sha256']
        target=F.scene_target(cube) if effect['interpretation']=='scene' else F.Target(cube,'srgb','srgb')
        data=F.build_sets(camera,target,scenes)
        predicted=F.render_encoded(camera,encoded,data['testx']);image=F.render_encoded(camera,encoded,data['hx'])
        synthetic,_=F.score(camera,camera.stock(data['testx']),np.rint(predicted),data['testt'])
        scene,_=F.score(camera,camera.stock(data['hx']),np.rint(image),data['ht'])
        old=next(x for x in original[i]['options'] if x['interpretation']==effect['interpretation'])
        assert synthetic==old['synthetic_holdout'] and scene==old['scene_holdout']
        stored=bytes.fromhex(effect['entry_hex'])
        assert {j for j,(a,b) in enumerate(zip(encoded,stored)) if a!=b}<=set(range(4,8))
        assert encoded[20:82]==expand(raw,0,4)[20:82] and encoded[20:115]==encoded[456:551]
        if i==2:
            assert encoded[115:211]==bytes(96)
            assert max(np.ptp(predicted,axis=1))==max(np.ptp(image,axis=1))==0
            assert all(expand(raw,unit,3)[115:211]==encoded[115:211] for unit in range(3))
        rows.append(dict(index=i+1,name=effect['name'],interpretation=effect['interpretation'],
                         source_sha256=cube.source_sha256,synthetic_holdout=synthetic,scene_holdout=scene,
                         final_entry_sha256=sha(encoded),solver=old['solver']))
    out=dict(status='PASS',dat_sha256=sha(raw),test_dat_sha256=sha((F.ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()),
             effects=rows,started_ns=started,ended_ns=time.time_ns(),seconds=time.monotonic()-tick,
             bw='Final encoded C080 is 96 zero bytes on all three unit maps. Direct encoded coefficient interpolation yields zero chroma for every input hue; final encoded curve/matrix rendering has exact R=G=B on both holdouts.',
             scope='50mm ISO 200 host calibration only. No independent 28mm or MOUNT calibration and no physical camera photos.')
    (HERE/'evidence/final_predictions.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(status=out['status'],effects=len(rows),seconds=out['seconds'],dat_sha256=out['dat_sha256'])))

if __name__=='__main__':main()
