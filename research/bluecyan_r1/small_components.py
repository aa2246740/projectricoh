#!/usr/bin/env python3
"""Diagnose weak probe components without fitting any JPEG response."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,np,read,dump
import physical
from assess import phase_output
import itertools


def main():
    noon,ref,_=a.load();physical.update_reference(ref)
    entries={k:bytes.fromhex(v['entry_hex']) for k,v in read(ROOT/'research/probe_pack_r3/local/expected.json')['M'].items()}
    source=read(ROOT/'research/probe_pack_r3/field/local/measure-0.5.json')['points']
    measured=read(LOCAL/'physical/probe-points.json')
    out=[]
    for label,patch,component in (('RP','skin',1),('BP','blue',2)):
        row=next(r for r in measured if r['probe']=='probe3' and r['ROI']=='0.5' and r['label']==label and r['patch']==patch)
        original=next(r for r in source if r['label']==label and r['patch']==patch)
        x=np.array([row['physical']['x']]);A=ref.model.predict(entries['A'],x);B=ref.model.predict(entries[label],x)
        values=[]
        for order in ('YCbCr8_then_RGB8','RGB8_then_YCbCr8'):
            for phase in itertools.product((0.,.25,.5,.75),repeat=3):
                aa=phase_output(A,np.array(phase),order,ref.mm);bb=phase_output(B,np.array(phase),order,ref.mm)
                values.append(noon.ycc(bb)[0]-noon.ycc(aa)[0])
        values=np.array(values);obs=np.array(row['physical']['observed'])
        hist=original['raw_histogram'];dn=np.array(hist['dn']);w=np.array(hist['counts'],float);w/=w.sum()
        xx=np.repeat(x,len(dn),axis=0);c='RGB'.index(label[0])
        xx[:,c]=x[0,c]*np.maximum(dn-original['raw_black'],0)/(original['raw_target_mean']-original['raw_black'])
        predictions={}
        for blur in ('inherited_blur','unblurred_per_sample'):
            table=ref.model.engine.table;old_s0,old_kappa=table.s0,table.kappa
            if blur=='unblurred_per_sample':table.s0=table.kappa=0.
            try:
                avgA=w@ref.model.predict(entries['A'],xx);avgB=w@ref.model.predict(entries[label],xx)
                predictions[blur]=noon.ycc(avgB)-noon.ycc(avgA)
            finally:table.s0,table.kappa=old_s0,old_kappa
        out.append(dict(label=label,patch=patch,component=component,observed=obs,
            physical_mean_input=row['physical']['predicted'],quantization_min=values.min(0),quantization_max=values.max(0),
            target_component_inside_axis_envelope=bool(values[:,component].min()<=obs[component]<=values[:,component].max()),
            simultaneous_phase_matches_within_quarter_code=int((np.max(abs(values-obs),axis=1)<=.25).sum()),
            histogram_predictions=predictions,diagnostic_only=True,
            limitations='one-channel CFA histogram holds other channels at their mean; output quantization hypotheses, not a measured ISP rounding model'))
    dump('physical/small-components.json',out);print(a.plain(out),flush=True)


if __name__=='__main__':main()
