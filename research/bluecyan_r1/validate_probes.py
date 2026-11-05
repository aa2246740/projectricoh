#!/usr/bin/env python3
"""Replay probe2/3 deltas against the frozen conditional sector correction."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,np,read,dump,stats
from correction import Correction


def main():
    noon,ref,_=a.load();correction=Correction()
    fmt=a.module('blue_probe_dat',ROOT/'research/v39_g153/dat_format.py')
    rows_out=[];summary={}
    for kind in ('probe2','probe3'):
        if kind=='probe2':
            data_path=ROOT/'research/probe_pack_r2/local/field_probe2_20261103/measure-0.5.json'
            datpath=ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT'
            data=datpath.read_bytes()
            entries={k:fmt.expand_effect(data,8+i) for i,k in enumerate(('A','RN','GN','BN','RD','GD','BD'))}
        else:
            data_path=ROOT/'research/probe_pack_r3/field/local/measure-0.5.json'
            expected_path=ROOT/'research/probe_pack_r3/local/expected.json'
            entries={k:bytes.fromhex(v['entry_hex']) for k,v in read(expected_path)['M'].items()}
        source=read(data_path)['points'];valid=[r for r in source if not r['excluded']]
        assert all(e[115:211]==ref.entries['04 Std'][115:211] for e in entries.values())
        replay=0.;change=0.
        for label in sorted(set(r['label'] for r in valid)):
            rr=[r for r in valid if r['label']==label];x=np.array([r['x_B'] for r in rr])
            baseline=ref.model.predict(entries['A'],x)
            old=ref.model.predict(entries[label],x)-baseline
            new=correction.predict(ref.model,entries[label],x)-correction.predict(ref.model,entries['A'],x)
            replay=max(replay,float(np.max(abs(old-np.array([r['predicted_rgb'] for r in rr])))))
            change=max(change,float(np.max(abs(old-new))))
            for r,o,n in zip(rr,old,new):
                # Compare native observed YCC deltas with the original saved prediction;
                # this is the same measurement contract, not a new JPEG re-extraction.
                dycc=noon.ycc(n[None])[0]-noon.ycc(o[None])[0]
                err=np.array(r['observed_ycc'])-np.array(r['predicted_ycc'])
                rows_out.append(dict(probe=kind,label=label,patch=r['patch'],gray=r['gray'],
                    old_error=err,corrected_error=err-dycc,prediction_change=dycc,
                    observed=r['observed_ycc'],predicted=r['predicted_ycc']))
        for group in ('all','gray','coloured'):
            rr=[r for r in rows_out if r['probe']==kind and (group=='all' or r['gray']==(group=='gray'))]
            old=np.array([r['old_error'] for r in rr]);new=np.array([r['corrected_error'] for r in rr])
            summary[kind+' '+group]=dict(n=len(rr),old_rmse=np.sqrt(np.mean(old*old,axis=0)),
                corrected_rmse=np.sqrt(np.mean(new*new,axis=0)),old_max_abs=np.max(abs(old),axis=0),
                corrected_max_abs=np.max(abs(new),axis=0))
        summary[kind+' replay']=dict(max_old_replay_difference_rgb=replay,max_correction_change_rgb=change,
            source_sha256=a.sha(data_path),all_C080_equal_native04=True)
        assert change<1e-9
        print(kind,'saved replay difference',replay,'corrected change',change,flush=True)
    dump('probe-validation.json',summary);dump('probe-points.json',rows_out)
    print(a.plain(summary),flush=True)


if __name__=='__main__':main()
