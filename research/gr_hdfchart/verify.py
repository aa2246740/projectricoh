"""Verify the protected trees, public aggregate schema and actual sampled scores."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
import argparse
import ast
import csv
import json
import re
import subprocess
import numpy as np

PUBLIC={'.gitignore','support.py','extract_chart.py','score_chart.py','correct_targets.py',
        'supplement.py','report.py','run.py','verify.py','REPORT.md','aggregate.json',
        'sector_scores.csv','generation_hue5.csv','SHA256SUMS'}
FORBIDDEN={'pixels','pixel_data','pixel_rgb','target_lab','target_rgb','per_patch_targets',
           'camera_RGB_black_white_normalized','uc','raw3','source_observed','source_model',
           'effective_curve256_u16LE','values','coefficients','training_x'}


def scan_json(value):
    if isinstance(value,dict):
        assert not set(value)&FORBIDDEN, 'Private array key in public JSON'
        for v in value.values():scan_json(v)
    elif isinstance(value,list):
        # Public lists hold records, exclusions, hue-bin IDs or small metadata,
        # never nested vectors of sample colours.
        assert not any(isinstance(v,list) for v in value), 'Public numeric matrix'
        for v in value:scan_json(v)


def public_scan():
    files={p.name for p in s.HERE.iterdir() if p.is_file()}
    assert files<=PUBLIC and files>=PUBLIC-{'SHA256SUMS'}, files^PUBLIC
    assert all(p.name=='local' for p in s.HERE.iterdir() if p.is_dir())
    for name in files-{'SHA256SUMS'}:
        p=s.HERE/name
        assert not p.is_symlink()
        text=p.read_text()
        assert not re.search(r'(?<![0-9a-fA-F])[0-9a-fA-F]{96,}(?![0-9a-fA-F])',text),name
        assert not re.search(r'data:(?:image/|application/octet-stream)|BEGIN (?:RSA |EC )?PRIVATE KEY',text),name
        if p.suffix=='.py':
            tree=ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,bytes):
                    assert len(node.value)<48,(name,'long raw bytes')
                if isinstance(node,(ast.List,ast.Tuple)):
                    items=node.elts
                    if len(items)>=48 and all(isinstance(x,ast.Constant) and isinstance(x.value,int) for x in items):
                        raise AssertionError((name,'long literal integer array'))
        elif p.suffix=='.json':
            data=json.loads(text);assert data['schema']=='gr-hdfchart-aggregate/1';scan_json(data)
        elif p.suffix=='.csv':
            with p.open() as f:
                reader=csv.DictReader(f);fields=reader.fieldnames
                assert 'median_de00' in fields and 'n' in fields
                assert not set(fields)&FORBIDDEN
                for row in reader:
                    assert int(row['n'])>=0
                    if row['median_de00']:assert float(row['median_de00'])>=0
    tracked=subprocess.check_output(['git','ls-files','--',str(s.LOCAL)],cwd=s.ROOT,text=True)
    assert not tracked,'local/ is tracked'
    return len(files)


def score_values(cm,target,pred,base,mask,baseline_target=None):
    t,p,b=np.asarray(target)[mask],np.asarray(pred)[mask],np.asarray(base)[mask]
    e=cm.delta_e00(t,p)
    bt=t if baseline_target is None else np.asarray(baseline_target)[mask]
    den=cm.delta_e00(bt,b)
    if not len(e):return dict(n=0,median=None,p90=None,similarity=None,lt2=None,den=None)
    return dict(n=len(e),median=float(np.median(e)),p90=float(np.percentile(e,90)),
                den=float(np.median(den)),similarity=float(1-np.median(e)/np.median(den)),lt2=float(np.mean(e<2)))


def check_score(actual,expected):
    assert actual['n']==expected['n']
    for k in ('median','p90','similarity'):
        if actual[k] is not None:assert abs(actual[k]-expected[k])<1e-9,(k,actual[k],expected[k])
    if actual['den'] is not None:assert abs(actual['den']-expected['stock04']['median'])<1e-9
    if actual['lt2'] is not None:assert abs(actual['lt2']-expected['fractions']['lt2'])<1e-12


def numeric_checks():
    r=s.runtime();cm=r.P.CM
    a=s.read(s.LOCAL/'analysis.json');c=s.read(s.LOCAL/'correction.json');u=s.read(s.LOCAL/'supplement.json')
    report=s.load('chart_public_report',s.HERE/'report.py')
    assert s.read(s.HERE/'aggregate.json')==report.public_data(a,c,u), 'Public aggregate differs from local results'
    checks=0
    for ident in ('R0003037','R0003039'):
        md=s.read(s.LOCAL/(ident+'_quality.json'))
        assert md['raw']['decoder']['prefix_rows_mismatch']==0
        assert s.read(s.LOCAL/'samples'/(ident+'.json'))['registration']['geometry_confirmed']
        for kind in ('roi','whole_flat','chart_flat'):
            with np.load(s.LOCAL/(ident+'_'+kind+'_scores.npz'),allow_pickle=False) as z:d=dict(z)
            assert not np.any(d['valid']&(d['ids']==50))
            for iso in ('200','1600'):
                q=a[ident][kind]['models'][iso]
                check_score(score_values(cm,d['target'],d['pred'+iso],d['base'],d['valid']),q['score']);checks+=1
                check_score(score_values(cm,d['fw_target'],d['pred'+iso],d['base'],d['eligible']),
                            q['uniform_firmware_standard_proxy']['score']);checks+=1
    for slot in ('01','02'):
        with np.load(s.LOCAL/(slot+'_corrected_gxr.npz'),allow_pickle=False) as z:d=dict(z)
        assert not d['valid'][49]
        check_score(score_values(cm,d['target'],d['pred'],d['base'],d['valid'],d['baseline_target']),c[slot]['corrected']);checks+=1
        check_score(score_values(cm,d['target'],d['pred'],d['base'],d['valid']),c[slot]['corrected_same_target']);checks+=1
        check_score(score_values(cm,d['old_target'],d['pred'],d['base'],d['valid'],d['old_baseline_target']),
                    c[slot]['old_on_common_mask']);checks+=1
        for q in c[slot]['anchor_and_residual_sensitivity']:
            key=f"{q['anchor_ev']:+.1f}_{q['residual']}"
            check_score(score_values(cm,d['target_'+key],d['pred'],d['base'],d['valid'],d['baseline_target_'+key]),q);checks+=1
        with np.load(s.LOCAL/(slot+'_simple_grey.npz'),allow_pickle=False) as z:sd=dict(z)
        check_score(score_values(cm,sd['target'],sd['pred'],sd['base'],sd['valid']),u['grey_referred_'+slot]['score']);checks+=1
    return r,checks


def spot_checks(r):
    roi_max=raw_max=jpeg_max=0.
    count=0
    from PIL import Image
    for ident in ('R0003037','R0003039'):
        md=s.read(s.LOCAL/(ident+'_quality.json'));f=md['frame']
        with Image.open(s.ROOT/f['jpg']) as im:full=np.asarray(im.convert('RGB'))
        hh,ww=full.shape[0]//2,full.shape[1]//2
        half=full.reshape(hh,2,ww,2,3).mean((1,3),dtype=np.float64)
        geom=md['geometry'];geom['H']=np.array(geom['H']);geom['Hinv']=np.linalg.inv(geom['H'])
        with np.load(s.LOCAL/(ident+'_roi.npz'),allow_pickle=False) as z:roi=dict(z)
        layout=r.ring.load_layout()['patches']
        for i in np.linspace(0,154,16,dtype=int):
            p=layout[i];x0,y0,x1,y1=p['bbox_px']
            q=r.ring.roi_mask(geom,[x0+30,y0+30,x1-30,y1-30],half.shape)
            ya,yb,xa,xb,mask,_=q
            measured=half[ya:yb,xa:xb][mask].mean(0)
            roi_max=max(roi_max,float(abs(measured-roi['jpeg'][i]).max()))
        raw,rawmd=r.extract.raw_frame(f)
        tags=rawmd['tags'];rgb=raw['rgb'].astype(float)
        coef=s.read(s.ROOT/'research/gr4_modes/local/tone_curves.json')['radial']['gr4_coef_natural_log']
        with np.load(s.LOCAL/'samples'/(ident+'.npz'),allow_pickle=False) as z:samples=dict(z)
        for i in np.linspace(0,len(samples['xy'])-1,64,dtype=int):
            x,y=map(int,samples['xy'][i]);ys,xs=np.mgrid[y-2:y+3,x-2:x+3]
            rr=((ys-(hh-1)/2)**2+(xs-(ww-1)/2)**2)/((hh/2)**2+(ww/2)**2)
            gain=np.exp(-sum(v*rr**(j+1) for j,v in enumerate(coef)))
            uc=rgb[y-2:y+3,x-2:x+3]/np.array(tags['50728'])*2**tags['50730'][0]*gain[...,None]
            raw_max=max(raw_max,float(abs(uc.mean((0,1))-samples['uc'][i]).max()))
            jpeg_max=max(jpeg_max,float(abs(half[y-2:y+3,x-2:x+3].mean((0,1))-samples['jpeg'][i]).max()))
            count+=1
    assert roi_max<1e-4,roi_max
    assert raw_max<2e-6,raw_max
    assert jpeg_max<1e-4,jpeg_max
    for ident in ('R0003036','R0003038'):
        assert s.read(s.LOCAL/(ident+'_white_raw.json'))['decoder']['prefix_rows_mismatch']==0
    return dict(roi_patches=32,flat_positions=count,roi_rgb_max_error=roi_max,
                flat_uc_max_error=raw_max,flat_jpeg_max_error=jpeg_max,decoder_prefix_mismatches=0)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');arg=ap.parse_args();s.guard()
    before=s.read(s.LOCAL/'protected_before.json')
    after={str(p.relative_to(s.ROOT)):s.sha(p) for folder in s.PROTECTED
           for p in sorted((s.ROOT/folder).rglob('*')) if p.is_file()}
    assert before==after,dict(changed=[k for k in before.keys()&after.keys() if before[k]!=after[k]],
                               added=sorted(after.keys()-before.keys()),removed=sorted(before.keys()-after.keys()))
    source=s.ROOT/'captures/contrib/2026-10-22-gr4hdf-screenchart'
    for line in (source/'SHA256SUMS').read_text().splitlines():
        digest,rel=line.split(maxsplit=1);assert s.sha(source/rel.lstrip('*'))==digest
    public_scan()
    if arg.seal:
        text=''.join(f'{s.sha(s.HERE/name)}  {name}\n' for name in sorted(PUBLIC-{'SHA256SUMS'}))
        (s.HERE/'SHA256SUMS').write_text(text)
    sums=(s.HERE/'SHA256SUMS').read_text().splitlines()
    assert len(sums)==len(PUBLIC)-1
    for line in sums:
        digest,rel=line.split(maxsplit=1);assert s.sha(s.HERE/rel)==digest,rel
    r,checks=numeric_checks();sampling=spot_checks(r)
    assert not list(s.HERE.rglob('*.DAT')) and not list(s.HERE.rglob('*.dat'))
    assert s.read(s.HERE/'aggregate.json')['generated_tables']==0
    result=dict(result='PASS',protected_files=len(before),changed_inputs=0,added_inputs=0,removed_inputs=0,
                source_hashes_verified=15,public_files=len(PUBLIC),public_hashes_verified=len(sums),
                public_pixel_and_raw_byte_scan='PASS',independent_score_recomputations=checks,
                sampling_checks=sampling,refit_performed=False,generated_tables=0,
                candidate_accepted=False,firmware_ready=False,deployable=False)
    s.dump(s.LOCAL/'verification.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
