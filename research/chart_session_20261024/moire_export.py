"""Prepare threshold-specific mean-based exchange inputs, without running a fit."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import session_runtime as s
from moire_review import flagged, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', default='moire-review-v2')
    ap.add_argument('--threshold', type=float, choices=(3., 6.), required=True)
    args = ap.parse_args()
    s.guard()
    sys.addaudithook(s.audit)
    out = s.LOCAL / args.run
    dest = out / ('exchange-jpeg' + str(int(args.threshold)))
    assert not dest.exists()
    metrics = {(r['frame'],r['patch_id']):r for r in (json.loads(line) for line in (out/'roi_metrics.jsonl').read_text().splitlines())}
    scores = json.loads((out/'scored/mean.json').read_text())
    cases = json.loads((out/'sensitivity.json').read_text())['cases']
    policy = 'jpeg' + str(int(args.threshold))
    summary = {}
    adapted = {}
    for unit in ('50mm','mount'):
        original = s.LOCAL/'analysis-final/exchange'/unit
        folder = dest/unit
        folder.mkdir(parents=True)
        frame_meta = json.loads((original/'frames.json').read_text())
        dataset = [json.loads(line) for line in (original/'patches.jsonl').read_text().splitlines()]
        for row in dataset:
            r = metrics[(row['frame'],row['patch_id'])]
            assert np.max(abs(np.array(row['raw_rgb'])-r['raw']['mean'])) < 1e-9
            assert np.max(abs(np.array(row['jpeg_rgb'])-r['jpeg']['mean'])) < 1e-9
            old_flags = list(row['flags'])
            row['original_valid_1p5'] = row['valid']
            row['flags'] = [flag for flag in old_flags if flag != 'moire-suspect']
            if flagged(r,policy):
                row['flags'].append('moire-amplitude-exceeds-' + str(args.threshold))
            row['valid'] = not row['flags']
            row['review'] = {'moire_policy':policy, 'spectral_peak_ratio':r['jpeg_spatial']['peak_ratio'],
                'amplitude_codes':r['jpeg_spatial']['amplitude'], 'original_moire_flag': 'moire-suspect' in old_flags,
                'raw_plane_1pct_flag_for_diagnostics':flagged(r,'raw1pct'), 'clipping_category':r['clipping']['category'],
                'unclipped_channel_mask':r['clipping']['unclipped_channel_mask'],
                'RAW_only_measurement_available':r['raw_saturation_fraction']<=.001}
        with (folder/'patches.jsonl').open('w') as f:
            for row in dataset:
                f.write(json.dumps(s.plain(row),ensure_ascii=False,allow_nan=False)+'\n')
        frame_meta['measurement_quality_policy'] = {'moire':policy, 'JPEG_clipping':'unchanged strict >1% any channel <=2 or >=253',
            'note':'threshold review only; no model parameters or camera metadata inferred'}
        s.dump(folder/'frames.json',frame_meta)
        adapted[unit] = dataset
        summary[unit] = {'frames':len(frame_meta['frames']),'rows':len(dataset),'measurement_valid':sum(r['valid']for r in dataset),
            'newly_retained':sum(r['valid'] and not r['original_valid_1p5'] for r in dataset),
            'metadata_complete':frame_meta['metadata_complete']}
    # Read the unchanged calibration boundary parser. No solver is called.
    sys.path.insert(0,str(s.ROOT/'research/module_adapt'))
    import calibrate
    target_samples = []
    fit_eligibility = {}
    good04 = {}
    original_meta = json.loads((dest/'50mm/frames.json').read_text())['frames']
    stock_rows, _ = calibrate.load_exchange(dest/'50mm/patches.jsonl',dest/'50mm/frames.json','50mm','04')
    for r in stock_rows:
        if r['usable']:
            good04[(str(r['page']),str(r['patch_id']))]=r
    for slot in ('01','02','03','04','05','06'):
        parsed,_=calibrate.load_exchange(dest/'50mm/patches.jsonl',dest/'50mm/frames.json','50mm',slot)
        case=next(c for c in cases if c['estimator']=='mean' and c['moire_policy']==policy and c['clipping_policy']=='strict' and c['slot']==slot)
        keep={(f,pid)for f,pid in case['selected_keys']}
        count=0
        for key,q in scores.items():
            if original_meta[key]['selector_bytes']['recipe_slot'] != slot or slot=='04':
                continue
            own=[r for r in adapted['50mm'] if r['frame']==key]
            expected=json.loads((s.LOCAL/'analysis-final/frames'/(key+'.json')).read_text())['patches']
            assert [r['patch_id']for r in own]==[r['patch_id']for r in expected] and len(own)==len(q['valid'])
            for i,r in enumerate(own):
                if (key,r['patch_id']) not in keep:
                    continue
                target_samples.append({'page':r['page'],'patch_id':r['patch_id'],'slot':slot,
                    'target_lab':q['baseline_target_lab'][i],'baseline_target_lab':q['baseline_target_lab'][i],
                    'baseline_frame':q['matched04'],'source_recipe_frame':key})
                if (str(r['page']),str(r['patch_id'])) in good04:
                    count+=1
        fit_eligibility[slot]={'parser_usable':sum(r['usable']for r in parsed),
            'usable_by_page':dict(__import__('collections').Counter(str(r['page'])for r in parsed if r['usable'])),
            'fit_recipe_usable_target_points':count if slot!='04' else None,
            'score_n':case['n'],'score_similarity':case['similarity']}
    s.dump(dest/'50mm/targets_for_04.json',{'schema':'ricoh-module-targets/1','whitepoint':'D65',
        'source':'same frozen closed_loop targets; mean estimator; matched04 targets; quality policy '+policy,
        'samples':target_samples})
    s.dump(dest/'export_summary.json',{'units':summary,'fit_eligibility':fit_eligibility,'no_fit_executed':True})
    print(json.dumps({'policy':policy,'units':summary,'fit_eligibility':fit_eligibility},ensure_ascii=False))


if __name__=='__main__':
    main()
