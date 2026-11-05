#!/usr/bin/env python3
"""Keep the original nine-branch sign rule and rebuild native C040 responses."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,NOON,np,read,dump
import physical
import ast
import types
import collections


def main():
    noon,ref,_=a.load();physical.update_reference(ref)
    rows=read(LOCAL/'physical/noon-patches-all-roi.json')
    frames={p.stem:read(p) for p in (NOON/'frames').glob('*.json')};cache={};branches=[];updated=[]
    def anchor(stem,fraction):
        key=stem,fraction
        if key not in cache:
            pp=frames[stem]['patches'][str(fraction)];j=np.array([r['jpeg_mean'] for r in pp]);raw=np.array([r['raw_wb'] for r in pp]);native=np.array([r['native_ycc_mean'] for r in pp])
            x,_=ref.inverse04(j);cache[key]=dict(ix={r['id']:i for i,r in enumerate(pp)},x=x,raw=raw,native=native,
                offset=native-noon.ycc(j))
        return cache[key]
    grouped=collections.defaultdict(list)
    for row in rows:grouped[row['frame'],row['ROI']].append(row)
    for (frame,fraction),rr in grouped.items():
        aa,bb=[anchor(stem,fraction) for stem in rr[0]['anchors']];alpha=rr[0]['alpha']
        ia=np.array([aa['ix'][r['patch']] for r in rr]);ib=np.array([bb['ix'][r['patch']] for r in rr])
        raw=np.array([r['raw_wb'] for r in rr]);native=np.array([r['native_observed_YCbCr'] for r in rr])
        x=np.array([r['physical_input'] for r in rr]);base=ref.predict('04 Std',x);pred=np.array([r['physical_predicted_rgb'] for r in rr])
        offset=(1-alpha)*aa['offset'][ia]+alpha*bb['offset'][ib]
        observed=native-noon.ycc(base)-offset;predicted=noon.ycc(pred)-noon.ycc(base)
        variants=[]
        for endpoint,ix in ((aa,ia),(bb,ib)):
            xx=endpoint['x'][ix]/np.maximum(endpoint['raw'][ix],1e-9)*raw
            b=ref.predict('04 Std',xx);p=ref.predict(rr[0]['setting'],xx)
            variants.append((native-noon.ycc(b)-endpoint['offset'][ix],noon.ycc(p)-noon.ycc(b)))
        direct=native-(1-alpha)*aa['native'][ia]-alpha*bb['native'][ib]
        for i,r in enumerate(rr):
            updated.append(dict(r,conditioned_input=x[i],predicted_rgb=pred[i],
                observed_delta_from04=observed[i],predicted_delta_from04=predicted[i],
                native_YCbCr_error=native[i]-noon.ycc(pred[i])-offset[i]))
            branches.append(dict(frame=frame,kind=r['kind'],setting=r['setting'],page=r['page'],patch=r['patch'],
                ROI=fraction,time_bracketed=r['time_bracketed'],observed=[observed[i],variants[0][0][i],variants[1][0][i]],
                predicted=[predicted[i],variants[0][1][i],variants[1][1][i]],direct_ycc=direct[i]))
    source=NOON/'finalize_r2.py';tree=ast.parse(source.read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sign_analysis')
    proxy=types.SimpleNamespace(dump=lambda path,value:dump('physical/sign-points.json',value))
    ns=dict(np=np,n=proxy,OUT=LOCAL/'physical')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),ns)
    signs=ns['sign_analysis'](updated,branches)
    old=read(NOON/'sign-gaps-r2.json');summary={}
    for subject in sorted(set(r['subject'] for r in signs)):
        a0=[r for r in old if r['subject']==subject];a1=[r for r in signs if r['subject']==subject]
        summary[subject]=dict(old=dict(collections.Counter(r['state'] for r in a0)),physical=dict(collections.Counter(r['state'] for r in a1)),
            old_independent_opposite=sum(r['state']=='opposite_sign' and not r['conditional'] for r in a0),
            physical_independent_opposite=sum(r['state']=='opposite_sign' and not r['conditional'] for r in a1),
            by_recipe={name:dict(collections.Counter(r['state'] for r in a1 if r['setting']==name)) for name in sorted(set(r['setting'] for r in a1))})
    assert summary['screen_skin']['old']['opposite_sign']==19 and summary['screen_blue']['old']['opposite_sign']==12
    dump('physical/sign-summary.json',dict(summary=summary,rule_source_sha256=a.sha(source),
        thresholds_unchanged=True,three_ROIs_times_three_anchor_branches=True,weak_components_not_promoted=True))
    print(summary,flush=True)


if __name__=='__main__':main()
