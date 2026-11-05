#!/usr/bin/env python3
"""Rebuild probe anchor inversions with native MOUNT C040 geometry."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
import physical
from analyze import ROOT,LOCAL,np,read,dump,stats
import struct


def main():
    noon,old,_=a.load();new=physical.update_reference(noon.Reference())
    fmt=a.module('physical_probe_dat',ROOT/'research/v39_g153/dat_format.py')
    out=[];summary={};replay=0.
    for probe in ('probe2','probe3'):
        if probe=='probe2':
            folder=ROOT/'research/probe_pack_r2/local/field_probe2_20261103'
            raw=(ROOT/'firmware/package_v39_g154_probe2/local/SD_ROOT/GXRCE.DAT').read_bytes()
            entries={k:fmt.expand_effect(raw,8+i) for i,k in enumerate(('A','RN','GN','BN','RD','GD','BD'))}
        else:
            folder=ROOT/'research/probe_pack_r3/field/local'
            entries={k:bytes.fromhex(v['entry_hex']) for k,v in read(ROOT/'research/probe_pack_r3/local/expected.json')['M'].items()}
        b=entries['A'];xs=np.r_[0,struct.unpack_from('>31H',b,20),4095]
        curves=np.array([list(b[379:412]),list(b[82:115]),list(b[412:445])]);row=old.mm.MatrixRow.from_bytes(b[216:244])
        frames={p.stem:read(p) for p in (folder/'frames').glob('*.json')};cache={}
        def inverse(stem,fraction,ref):
            key=stem,fraction,id(ref)
            if key not in cache:
                pp=frames[stem]['patches'][fraction];j=np.array([p['jpeg_mean'] for p in pp])
                # Match the original probe's rounded BT.601 inverse convention.
                y,co=ref.mm.ycbcr(j);ci,_=ref.model.engine.table.inverse_stock(co)
                pre=row.invert(y,ci)
                x=np.column_stack([np.interp(pre[:,c],curves[c],xs) for c in range(3)])
                cache[key]=dict(x=x,pre=pre,j=j,raw=np.array([p['raw_dn_mean'] for p in pp]),
                    native=np.array([p['native_ycc_mean'] for p in pp]))
            return cache[key]
        for fraction in ('0.35','0.5','0.65'):
            source=read(folder/('measure-'+fraction+'.json'))['points']
            for r in source:
                if r['excluded']:continue
                p=r['patch_index'];sa,sb=r['reference_frames'];alpha=r['reference_alpha'];results={}
                target=frames[r['frame']]['patches'][fraction][p]
                for name,ref in (('old',old),('new',new)):
                    aa=inverse(sa,fraction,ref);bb=inverse(sb,fraction,ref)
                    gain=(1-alpha)*aa['x'][p]/aa['raw'][p]+alpha*bb['x'][p]/bb['raw'][p]
                    x=gain*np.array(target['raw_dn_mean'])
                    base=ref.model.predict(b,x[None])[0];pre=ref.model.pre(b,x[None])[0]
                    off=(1-alpha)*(aa['native'][p]-noon.ycc(aa['j'][p]))+alpha*(bb['native'][p]-noon.ycc(bb['j'][p]))
                    expected=noon.ycc(base)+off
                    expected[0]=(1-alpha)*aa['native'][p,0]+alpha*bb['native'][p,0]+(pre-(1-alpha)*aa['pre'][p]-alpha*bb['pre'][p])@(row.coef[0]/1024)
                    observed=np.array(target['native_ycc_mean'])-expected
                    pred=ref.model.predict(entries[r['label']],x[None])[0]-base
                    predicted=noon.ycc(base+pred)-noon.ycc(base)
                    results[name]=dict(x=x,observed=observed,predicted=predicted,error=observed-predicted)
                delta=max(np.max(abs(results['old']['x']-r['x_B'])),np.max(abs(results['old']['observed']-r['observed_ycc'])),np.max(abs(results['old']['predicted']-r['predicted_ycc'])))
                replay=max(replay,float(delta))
                assert delta<1e-7,(probe,r['frame'],r['patch'],delta)
                out.append(dict(probe=probe,ROI=fraction,label=r['label'],patch=r['patch'],gray=r['gray'],
                    old=results['old'],physical=results['new']))
        print(probe,'rows',sum(r['probe']==probe for r in out),'old replay',replay,flush=True)
    for probe in ('probe2','probe3'):
      for group in ('all','gray','coloured'):
        rr=[r for r in out if r['probe']==probe and r['ROI']=='0.5' and (group=='all' or r['gray']==(group=='gray'))]
        e0=np.array([r['old']['error'] for r in rr]);e1=np.array([r['physical']['error'] for r in rr])
        summary[probe+' '+group]=dict(n=len(rr),old_rmse=np.sqrt(np.mean(e0*e0,axis=0)),physical_rmse=np.sqrt(np.mean(e1*e1,axis=0)),
            old_max_abs=np.max(abs(e0),axis=0),physical_max_abs=np.max(abs(e1),axis=0))
    signs=[r for r in out if r['probe']=='probe3' and not r['gray'] and r['label'] in ('RP','BP')]
    dump('physical/probe-points.json',out);dump('physical/probe-scores.json',dict(scores=summary,old_replay_max=replay,signs=signs,
        no_fitted_parameters=True,anchors_and_input_raw_ratios_rebuilt=True))
    for row in signs:
        if row['ROI']=='0.5':print(row['label'],row['patch'],'old obs/pred',row['old']['observed'],row['old']['predicted'],
            'physical obs/pred',row['physical']['observed'],row['physical']['predicted'],flush=True)
    print(summary,flush=True)


if __name__=='__main__':main()
