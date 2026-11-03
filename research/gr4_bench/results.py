#!/usr/bin/env python3
"""Recompute metrics from integer candidates; keep per-point results local."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import benchlib as b
b.guard()
import numpy as np
import evaluate as ev

DEFAULT='common_white_+0.0'


def parameters(e, record):
    return e.mm.MatrixRow(record['row_coef'],record['row_tail']),np.asarray(record['A']),np.asarray(record['B'])


def gr():
    e,_=b.engine();data=ev.matched();baseline=b.read(b.LOCAL/'baseline.json')
    out={}
    for scenario in baseline:
        bridge,anchor=scenario.rsplit('_',1)
        x=ev.input_x(data,bridge,float(anchor))
        slots={}
        for slot in ('01','02'):
            slots[slot]={'A':dict(full=baseline[scenario][slot],spatial=baseline[scenario][slot],
                                 accepted=False,firmware_ready=False,deployable=False)}
            for variant in ('B','C'):
                folder=b.LOCAL/'fits'/scenario
                record=b.read(folder/f'{slot}_{variant}_full.json')
                row,A,B=parameters(e,record)
                lab=e.fs.lab_from_codes(e.predict(slot,x,row,A,B))
                pooled=np.full_like(lab,np.nan);cover=np.zeros(len(lab),int)
                folds=[]
                for index in range(4):
                    p=folder/f'{slot}_{variant}_spatial_{index:02d}'
                    r=b.read(p.with_suffix('.json'))
                    rr,aa,bb=parameters(e,r)
                    test=data['fold']==index
                    predicted=e.fs.lab_from_codes(e.predict(slot,x[test],rr,aa,bb))
                    z=dict(np.load(p.with_suffix('.npz')))
                    assert np.array_equal(z['test_indices'],np.flatnonzero(test))
                    # BLAS batch sizes can change the last rounding bit.
                    assert np.allclose(predicted,z['prediction_lab'],rtol=0,atol=1e-10)
                    pooled[test]=predicted;cover[test]+=1
                    folds.append(dict(fold=index,n=int(test.sum()),**r['GR_test']))
                assert np.all(cover==1) and np.isfinite(pooled).all()
                np.savez(b.LOCAL/f'pooled_{slot}_{variant}_{scenario}.npz',prediction_lab=pooled)
                slots[slot][variant]=dict(full=ev.score(e,data,slot,x,lab),
                     spatial=ev.score(e,data,slot,x,pooled),folds=folds,
                     accepted=False,firmware_ready=False,deployable=False)
        out[scenario]=slots
    b.dump(b.LOCAL/'GR_results.json',out)
    for slot,variants in out[DEFAULT].items():
        print(slot,{v:{mode:{k:round(q[mode][k]['all']['similarity']*100,2) for k in ('relative','absolute')}
                      for mode in ('full','spatial')} for v,q in variants.items()})


def original():
    g=b.round5();summary={};details={}
    for iso in (200,1600):
        e,_=b.engine(iso)
        for slot in ('01','02'):
            d=g.Data(slot,iso)
            cx=d.a['chart_x']*d.a['exposure'];rx=d.a['ring_x']*d.a['exposure']
            stock_chart=e.fs.lab_from_codes(e.predict('04',cx))
            stock_ring=e.fs.lab_from_codes(e.predict('04',rx))
            groups={'chart_train':(cx[d.chrom],d.a['chart_target'][d.chrom],stock_chart[d.chrom]),
                    'grey':(cx[d.greys],d.a['chart_target'][d.greys],stock_chart[d.greys]),
                    'firmware_ring':(rx,d.generated['ring_target'],stock_ring),
                    'legacy_ring':(rx,d.a['ring_target'],stock_ring)}
            key=f'{slot}_{iso}';summary[key]={};details[key]={}
            for variant in ('A','B','C'):
                if variant=='A': row,A,B=e.parameters(slot)
                else:
                    record=b.read(b.LOCAL/'fits'/DEFAULT/f'{slot}_{variant}_full.json')
                    row,A,B=parameters(e,record)
                summary[key][variant]={};details[key][variant]={}
                for name,(xx,target,stock) in groups.items():
                    prediction=e.fs.lab_from_codes(e.predict(slot,xx,row,A,B))
                    summary[key][variant][name]=b.metric(e.fs,prediction,target,stock)
                    details[key][variant][name]=dict(error=e.fs.delta_e00(prediction,target),prediction=prediction)
                loo=[]
                for index in d.chrom:
                    if variant=='A':
                        name='dualgrey' if slot=='01' else 'quarter_strict'
                        rec=b.read(b.ROOT/f'research/color_fit_v2/gr_round5/local/{slot}_{name}_loo_{index:02d}.json')
                        rr,aa,bb=g.engine.f.unpack_solution(rec)
                    else:
                        rec=b.read(b.LOCAL/'fits'/DEFAULT/f'{slot}_{variant}_chartloo_{index:02d}.json')
                        rr,aa,bb=parameters(e,rec)
                    pred=e.fs.lab_from_codes(e.predict(slot,cx[[index]],rr,aa,bb))[0]
                    loo.append(pred)
                loo=np.asarray(loo)
                summary[key][variant]['chart_loo']=b.metric(e.fs,loo,d.a['chart_target'][d.chrom],stock_chart[d.chrom])
                details[key][variant]['chart_loo']=dict(error=e.fs.delta_e00(loo,d.a['chart_target'][d.chrom]),prediction=loo)
            details[key]['labels']=[d.meta['labels'][i] for i in d.chrom]
    b.dump(b.LOCAL/'original_results.json',summary)
    b.dump(b.LOCAL/'original_details.json',details)
    for key,variants in summary.items():
        print(key,{v:{name:round(q[name]['median'],4) for name in ('chart_loo','firmware_ring','legacy_ring','grey')}
                   for v,q in variants.items()})


def safety():
    out={}
    for iso in (200,1600):
        e,_=b.engine(iso)
        for slot in ('01','02'):
            for variant in ('A','B','C'):
                if variant=='A': row,A,B=e.parameters(slot)
                else:
                    r=b.read(b.LOCAL/'fits'/DEFAULT/f'{slot}_{variant}_full.json')
                    row,A,B=parameters(e,r)
                    original=e.mm.MatrixRow.from_bytes(e.entries[slot]['written'][3][28:56])
                    assert np.array_equal(r['row2_coef'][1:],original.coef[1:])
                    assert tuple(r['row2_tail'])==tuple(original.tail)
                dense=e.safety(A,B,dense=True)
                full=e.full_chain_safety(slot,row,A,B)
                out[f'{slot}_{variant}_{iso}']=dict(sector=dense,full_chain=full)
    b.dump(b.LOCAL/'safety.json',out)
    print({k:dict(sector=v['sector']['passes'],full=v['full_chain']['all_outputs_no_hue_reversal']) for k,v in out.items()})


def diagnostics():
    e,_=b.engine();data=ev.matched()
    pixel=data['pos_xy']; ix=np.rint(pixel[:,0]/16-.5).astype(int);iy=np.rint(pixel[:,1]/16-.5).astype(int)
    r2=((pixel[:,0]-6192/2)**2+(pixel[:,1]-4128/2)**2)/((6192/2)**2+(4128/2)**2)
    radial=np.asarray(b.read(b.ROOT/'research/gr4_modes/local/tone_curves.json')['radial']['gr4_coef_natural_log'])
    gain=np.exp(-(radial[0]*r2+radial[1]*r2**2+radial[2]*r2**3))
    std=dict(np.load(b.LOCAL/'blocks_std.npz'))
    mat=np.load(b.LOCAL/'bridges.npz')['common_white']
    stock=e.fs.lab_from_codes(e.predict('04',ev.input_x(data)))
    out={}
    for key in ('pos','neg'):
        d=dict(np.load(b.LOCAL/f'blocks_{key}.npz'))
        wb=d['cam'][iy,ix]/std['neutral']*2**float(std['baseline_exposure'])*gain[:,None]
        proxy=e.fs.lab_from_codes(e.predict('04',wb@mat.T*(320/.0853)))
        out[key]=b.stats(e.fs.delta_e00(stock,proxy))
    out['cell_counts']=np.bincount(data['cell'],minlength=16)
    out['raw_agreement_relative']=b.stats(data['raw_agreement'])
    peaks={key:float(np.load(b.LOCAL/f'blocks_{key}.npz')['rawmax'][iy,ix].max())
           for key in ('std','pos','neg')}
    # A single green can be at most twice its pair mean plus the negative black floor.
    out['retained_CFA_peak_upper_bound']={key:2*value+64/(16317-64) for key,value in peaks.items()}
    assert max(out['retained_CFA_peak_upper_bound'].values())<.395
    out['scope']='Same-position inter-frame RAW change rendered through stock model; proxy, not an error lower bound'
    b.dump(b.LOCAL/'diagnostics.json',out)
    print(out)


def gates():
    gr=b.read(b.LOCAL/'GR_results.json');orig=b.read(b.LOCAL/'original_results.json')
    safe=b.read(b.LOCAL/'safety.json');out={}
    for slot in ('01','02'):
        for variant in ('B','C'):
            base=gr[DEFAULT][slot]['A']['spatial']['relative']['all']
            after=gr[DEFAULT][slot][variant]['spatial']['relative']['all']
            checks={'GR_heldout_median_improves':after['median']<base['median']-1e-6,
                    'GR_heldout_p90_not_worse':after['p90']<=base['p90']+1e-9}
            for iso in (200,1600):
                q=orig[f'{slot}_{iso}'];ss=safe[f'{slot}_{variant}_{iso}']
                for name in ('chart_loo','firmware_ring','legacy_ring','grey'):
                    for statistic in ('median','p90'):
                        checks[f'{name}_{statistic}_not_worse_iso{iso}']=q[variant][name][statistic]<=q['A'][name][statistic]+1e-9
                checks[f'grey_max_not_worse_iso{iso}']=q[variant]['grey']['max']<=q['A']['grey']['max']+1e-9
                checks[f'dense_sector_safety_iso{iso}']=ss['sector']['passes']
                checks[f'full_chain_no_hue_reversal_iso{iso}']=ss['full_chain']['all_outputs_no_hue_reversal']
                checks[f'neutral_ramp_preserved_iso{iso}']=ss['full_chain']['neutral_ramp_preserved']
            records=[b.read(p) for p in (b.LOCAL/'fits'/DEFAULT).glob(f'{slot}_{variant}_*.json')]
            checks['all_default_fits_converged']=all(q['solve']['success'] for q in records)
            checks['curve_other_fields_fixed']=all(q['curve_unchanged'] and q['other_fields_unchanged'] and q['encoding_roundtrip'] for q in records)
            out[f'{slot}_{variant}']=dict(conditions=checks,passes=all(checks.values()),
                  failed=[key for key,value in checks.items() if not value],
                  accepted=False,firmware_ready=False,deployable=False,
                  gate_source='closed_loop heldout/safety checks plus explicit no-regression on original round5 metrics')
    b.dump(b.LOCAL/'review_gates.json',out)
    print({key:dict(passes=q['passes'],failed=len(q['failed'])) for key,q in out.items()})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('gr','original','safety','diagnostics','gates'))
    args=p.parse_args()
    globals()[args.command]()
