"""Independent mask/arithmetic/source checks for the threshold review. No solver."""
import ast
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import session_runtime as s


def main():
    s.guard();sys.addaudithook(s.audit)
    out=s.LOCAL/'moire-review-v2'
    rows={(r['frame'],r['patch_id']):r for r in(json.loads(line)for line in(out/'roi_metrics.jsonl').read_text().splitlines())}
    frames={f['frame']:f for f in(json.loads(p.read_text())for p in(s.LOCAL/'analysis-final/frames').glob('*.json'))}
    cases=json.loads((out/'sensitivity.json').read_text())['cases']
    scored=json.loads((out/'scored/mean.json').read_text())
    independent={}
    for threshold in (1.5,3,6):
        for slot in ('04','01','02','03','05','06'):
            de,bd,keys=[],[],[]
            for key,q in scored.items():
                f=frames[key]
                if f['slot']!=slot:continue
                b=frames[q['matched04']]
                for i,patch in enumerate(f['patches']):
                    if not q['valid'][i]:continue
                    pair=(rows[(key,patch['patch_id'])],rows[(b['frame'],patch['patch_id'])])
                    bad=any(r['clipping']['any_fraction']>.01 or
                            r['jpeg_spatial']['peak_ratio']>25 and r['jpeg_spatial']['amplitude']>threshold for r in pair)
                    if not bad:
                        de.append(q['de00'][i]);bd.append(q['baseline_de00'][i]);keys.append([key,patch['patch_id']])
            policy='jpeg'+str(threshold).removesuffix('.0')
            case=next(c for c in cases if c['estimator']=='mean'and c['moire_policy']==policy and c['clipping_policy']=='strict'and c['slot']==slot)
            assert len(de)==case['n']and keys==case['selected_keys']
            sim=1-float(np.median(de))/float(np.median(bd))if len(bd)and np.median(bd)>=.25 else None
            assert sim is None and case['similarity']is None or abs(sim-case['similarity'])<1e-12
            independent[policy+':'+slot]={'n':len(de),'similarity':sim}
    source_count={}
    for name in ('sampling_provenance.json','review_provenance.json'):
        for path,row in json.loads((out/name).read_text()).items():
            assert row['unchanged']and s.sha(path)==row['sha256'],path
            source_count[path]=row['sha256']
    # Re-compare every cached native RAW mean and median to the original verified extraction.
    for (key,pid),r in rows.items():
        old=next(q for q in frames[key]['patches']if q['patch_id']==pid)
        assert np.max(abs(np.array(r['raw']['mean'])-old['raw']['mean_cam']))<1e-9
        assert np.max(abs(np.array(r['raw']['median'])-old['raw_rgb']))<1e-9
        assert r['verified_RAW_offset_xy']==frames[key]['raw_jpeg_registration'].get('after_offset',frames[key]['raw_jpeg_registration'])['offset_applied_xy']
    summary=json.loads((out/'exchange-jpeg6/export_summary.json').read_text())
    sys.path.insert(0,str(s.ROOT/'research/module_adapt'))
    import calibrate
    folder=out/'exchange-jpeg6/50mm'
    stock,_=calibrate.load_exchange(folder/'patches.jsonl',folder/'frames.json','50mm','04')
    good=[r for r in stock if r['usable']]
    assert len(good)==303==summary['fit_eligibility']['04']['parser_usable']
    held=np.array([str(r['page'])=='6'for r in good]);assert held.sum()==47
    raw=np.array([r['raw_wb']for r in good]);H=np.column_stack([np.ones(len(raw)),raw])
    assert np.linalg.matrix_rank(H[~held])==4
    good_keys={(str(r['page']),str(r['patch_id']))for r in good}
    targets=json.loads((folder/'targets_for_04.json').read_text())['samples']
    assert len({(str(r['page']),str(r['patch_id']),r['slot'])for r in targets})==len(targets)
    for slot in ('01','02','03','05','06'):
        parsed,_=calibrate.load_exchange(folder/'patches.jsonl',folder/'frames.json','50mm',slot)
        assert sum(r['usable']for r in parsed)==summary['fit_eligibility'][slot]['parser_usable']
        points=sum((str(r['page']),str(r['patch_id']))in good_keys for r in targets if r['slot']==slot)
        assert points==summary['fit_eligibility'][slot]['fit_recipe_usable_target_points']and points>=80
    template=json.loads((s.LOCAL/'operator_reports/mount.pending.json').read_text())
    assert template['lens']['focal_length_mm']==35 and template['lens']['maximum_aperture_f']==2
    assert template['capture']['actual_aperture_f']is None
    injected=json.loads((out/'exchange-jpeg6/mount/frames.user-report.json').read_text())
    assert not injected['metadata_complete']
    assert all(f['aperture_f']is None and f['exif_observations']['aperture_f']is None and
               f['operator_report']['lens']['maximum_aperture_f']==2 for f in injected['frames'].values())
    clip=json.loads((out/'clipping_review.json').read_text())
    assert sum(v['patches']for v in clip['counts']['C'].values())==4176
    assert sum(v['patches']for v in clip['counts']['M'].values())==812
    for path in s.HERE.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
    s.dump(out/'verification.json',{'passed':True,'independently_recomputed_cases':independent,
        'native_RAW_patch_records_reproduced':len(rows),'inputs_unchanged':len(source_count),
        'all_five_fit_recipe_input_counts_at_least_80':True,'fit04_training_design_rank':4,'fit04_holdout_page6_points':47,
        'pending_user_report_does_not_become_EXIF_or_actual_f2':True,'no_fit_executed':True})
    print(json.dumps({'passed':True,'source_inputs_unchanged':len(source_count),'RAW_records_reproduced':len(rows)},ensure_ascii=False))


if __name__=='__main__':main()
