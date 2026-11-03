"""Thin chart-v2 adapter for the frozen closed_loop target / measurement code."""
import csv
import numpy as np
from analyzer_runtime import input_path, require


def as_measure_frame(frame):
    patches = []
    for p in frame['patches']:
        require(p.get('raw_wb') is not None and p.get('xyz_camera') is not None and p['jpeg_rgb'] is not None,
                '色块缺少 RAW/JPEG/XYZ，不能评分')
        # scene_scale requires exactly one G_L50 or D4. This is a fixed semantic
        # mapping of the designed mid-grey anchor, never a best-score selection.
        name = 'G_L50' if p['sample_key'] == 'ANCHOR_midgray' else p['sample_key']
        gray = p['class'] in ('gray', 'white_page') or (
            p['class'] == 'anchor' and np.hypot(*p['nominal_lab_d65'][1:]) < 1.)
        patches.append({'label': str(p['patch_id']), 'name': name, 'gray': gray,
                        'rgb': p['jpeg_rgb'], 'raw': p['raw'], 'flags': list(p['flags'])})
    return {'id': frame['frame'], 'slot': frame['slot'], 'chart': 'hue-ring',
            'set': frame['unit'], 'meta': frame['meta'], 'metadata_errors': frame['metadata_errors'],
            'hashes': frame['hashes'], 'patches': patches,
            'rgb': np.array([p['jpeg_rgb'] for p in frame['patches']]),
            'raw_cam': np.array([p['raw_rgb'] for p in frame['patches']]),
            'raw_wb': np.array([p['raw_wb'] for p in frame['patches']]),
            'xyz_camera': np.array([p['xyz_camera'] for p in frame['patches']])}


def time_key(f):
    return (str(f['meta'].get('when') or ''), str(f['meta'].get('subsec') or ''), f['frame'])


def comparable(frame, base):
    errors = []
    for key in ('iso','t','f','wb_exif','wb_record_0x26'):
        if frame['meta'].get(key) != base['meta'].get(key):
            errors.append(f'{key} 与同页 04 不同')
    a, b = frame['meta'].get('asn'), base['meta'].get('asn')
    if a is None or b is None or not np.allclose(a, b, rtol=1e-6, atol=1e-6):
        errors.append('AsShotNeutral 与同页 04 不同')
    return errors


def score_all(frames, chain, out, overrides=None, table=None):
    source = [f for f in frames if f.get('kind') == 'screen' and f['unit'] == 'a12-50'
              and f['slot'] is not None and f['purpose'] not in ('drift','trial')]
    result = {'schema':'chart-v2-scores/1', 'status':'unassigned', 'slots':{}, 'errors':[],
              'definition':'1 - median(slot to its target) / median(matched 04 to that same slot target)',
              'denominator_floor_de00':.25, 'is_absolute_original_camera_similarity':False,
              'anchor':'fixed 0 EV; per-page ANCHOR_midgray mapped to existing G_L50 convention',
              'source':'frozen closed_loop.measure.score_record, summarize_slot, similarity; Engine and Targets unchanged',
              'evidence_kind': sorted({f.get('evidence_kind','camera') for f in source}),
              'coverage':{}, 'frames':{}, 'metadata_checks':{}}
    if not source:
        result['reason'] = '没有已指定配方和 a12-50 单元的 chart-v2 帧；EXIF 不能恢复彩色配方槽号'
        write_tables(out, result)
        return result
    base = {}
    for f in sorted(source, key=time_key):
        if f['slot'] == '04':
            base.setdefault(f['page'], f)
    engines, scored = {}, []
    for f in source:
        try:
            if f['slot'] == '04' and f is not base.get(f['page']):
                result.setdefault('diagnostic_stock_repeats', []).append(f['frame'])
                continue
            b = base.get(f['page'])
            if f['manifest'].get('baseline'):
                b = next((x for x in source if x['frame'] == f['manifest']['baseline'].upper()), None)
            require(b is not None and b['slot'] == '04' and b['page'] == f['page'] and b['unit'] == f['unit'],
                    '缺少同单元、同页的 04 基准')
            require(not f['metadata_errors'] and not b['metadata_errors'], '帧元数据或 manifest 校验失败')
            differences = comparable(f, b)
            require(not differences, '; '.join(differences))
            ff, bb = as_measure_frame(f), as_measure_frame(b)
            check = chain.measure.metadata_checks([bb, ff])
            result['metadata_checks'][f['frame']] = check
            require(check['pass'], '; '.join(check['errors']))
            iso = int(f['meta']['iso'])
            if iso not in engines:
                engine = chain.model.Engine(input_path(table) if table else chain.model.DEFAULT_TABLE,
                                            iso=iso, provenance=chain.p)
                targets = chain.targets.Targets(engine, chain.p, input_path(overrides) if overrides else None)
                engines[iso] = (engine, targets)
            engine, targets = engines[iso]
            ff = chain.measure.score_record(engine, targets, ff, bb)
            ff['matched04'] = b['frame']; scored.append(ff)
            result['frames'][f['frame']] = {k: ff[k] for k in ('matched04','target_definition','model',
                  'valid','hue_deg','input_lightness_Lstar','de00','baseline_de00','model_de00',
                  'target_lab','baseline_target_lab','model_rgb','observed_lab','gr_anchor_sensitivity')}
            f['score'] = {'baseline': b['frame'], 'valid_patches': int(ff['valid'].sum()),
                          'similarity': chain.measure.similarity(ff['de00'][ff['valid']], ff['baseline_de00'][ff['valid']])}
        except Exception as e:
            result['errors'].append({'frame': f['frame'], 'slot':f['slot'], 'error': f'{type(e).__name__}: {e}'})
    for slot in ('04','01','02','03','05','06'):
        expected = set(range(1,7)) if slot == '04' else {1,4}
        actual = {f['page'] for f in source if f['slot'] == slot}
        result['coverage'][slot] = {'pages':sorted(actual), 'missing_pages':sorted(expected-actual),
                                  'expected_patch_instances':696 if slot=='04' else 232}
        group = [f for f in scored if f['slot'] == slot]
        if not group:
            continue
        summary = chain.measure.summarize_slot(group)
        for sector in range(24):
            dd, bb = [], []
            for f in group:
                chrom = np.array([not q['gray'] for q in f['patches']])
                keep = f['valid'] & chrom & (np.floor(f['hue_deg']/15).astype(int) == sector)
                dd.extend(f['de00'][keep]); bb.extend(f['baseline_de00'][keep])
            summary['per_hue'][sector]['similarity'] = chain.measure.similarity(dd, bb)
        summary['control'] = slot == '04'
        summary['target_scope'] = 'surrogate GR transfer / empirical BW / official Fuji LUT, same as measure.py'
        result['slots'][slot] = summary
    incomplete = any(q['missing_pages'] for q in result['coverage'].values())
    result['status'] = 'error' if result['errors'] else 'partial' if incomplete else 'ok'
    result['calibrated_iso'] = all(e.calibrated_iso for e, _ in engines.values()) if engines else False
    result['iso_and_module_scope'] = 'Existing Engine calibration: A12 50mm, ISO 200/1600 only; other ISOs use the old ISO200 fallback and remain uncalibrated.'
    result['scope_note'] = 'P1+P4 cover four L*/chroma combinations per hue; 04 covers all six pages. Counts and exclusions are not equal across slots.'
    write_tables(out, result)
    return result


def write_tables(out, result):
    with (out/'scores_by_recipe.csv').open('w', newline='') as f:
        w = csv.writer(f); w.writerow(('slot','n','median_de00','p90_de00','max_de00','share_under_1',
                                       'share_under_2','share_under_3','similarity','excluded_patches','target_kinds'))
        for slot, q in result['slots'].items():
            s = q['measured_vs_target']
            w.writerow([slot, *(s[k] for k in ('n','median','p90','max','share_under_1','share_under_2','share_under_3')),
                        q['similarity']['value'], q['excluded_patches'], ';'.join(q['target_kinds'])])
    with (out/'scores_by_hue.csv').open('w', newline='') as f:
        w = csv.writer(f); w.writerow(('slot','hue_start_deg','n','median_de00','p90_de00','model_median_de00','similarity'))
        for slot, q in result['slots'].items():
            for h in q['per_hue']:
                w.writerow([slot,h['hue_start_deg'],h['n'],h['median'],h['p90'],h['model_vs_measured']['median'],h['similarity']['value']])


def stability_report(frames, chain):
    fs = chain.common.helper('fs')
    result = {'schema':'chart-v2-stability/1', 'drift':{}, 'uniformity':{},
              'thresholds':{'drift_abs_median_raw_EV':.03,'drift_median_de00':1.,'drift_p90_de00':2.,
                            'uniformity_anchor_raw_range_EV':.1,'uniformity_p90_de00':2.},
              'interpretation':'Observed anchor consistency includes screen, camera/lens shading, viewing angle, '
                               'exposure and image-dependent display response; it cannot isolate panel uniformity.'}
    units = sorted({f['unit'] for f in frames if f['unit']})
    for unit in units:
        stock = sorted([f for f in frames if f['kind']=='screen' and f['unit']==unit and f['slot']=='04'
                        and f['purpose']!='trial'], key=time_key)
        firstpages = [f for f in stock if f['page']==1]
        if len(firstpages) < 2:
            result['drift'][unit] = {'status':'unknown','reason':'缺少开头/结尾两张 04 第 1 页'}
        else:
            a, b = firstpages[0], firstpages[-1]
            differences = comparable(a,b)
            aa = {p['sample_key']:p for p in a['patches'] if p['class']=='anchor' and p['valid']}
            bb = {p['sample_key']:p for p in b['patches'] if p['class']=='anchor' and p['valid']}
            keys = sorted(aa.keys() & bb.keys())
            if differences or len(keys) < 8:
                result['drift'][unit] = {'status':'unknown','frames':[a['frame'],b['frame']],
                                        'reason': differences or '有效共同锚点不足 8 个','n':len(keys)}
            else:
                raw_a = np.array([aa[k]['raw_rgb'] for k in keys]); raw_b = np.array([bb[k]['raw_rgb'] for k in keys])
                ev = np.log2(np.maximum(raw_b @ [.25,.5,.25],1e-9)/np.maximum(raw_a @ [.25,.5,.25],1e-9))
                de = fs.delta_e00(fs.lab_from_codes([aa[k]['jpeg_rgb'] for k in keys]),
                                 fs.lab_from_codes([bb[k]['jpeg_rgb'] for k in keys]))
                shifted = abs(np.median(ev))>.03 or np.median(de)>1. or np.percentile(de,90)>2.
                result['drift'][unit] = {'status':'drift-detected' if shifted else 'within-thresholds',
                       'frames':[a['frame'],b['frame']], 'n':len(keys), 'median_raw_EV':float(np.median(ev)),
                       'jpeg_de00':chain.measure.stats(de),
                       'anchors':[{'sample_key':k,'raw_EV':float(e),'de00':float(d)} for k,e,d in zip(keys,ev,de)]}
        pages = {}
        for f in stock:
            if f['purpose'] != 'drift':
                pages.setdefault(f['page'],f)
        consistency = []
        if pages:
            ref = next(iter(pages.values()))
            for page, f in pages.items():
                consistency.extend(f'P{page}: {e}' for e in comparable(f, ref))
        anchors = {}
        for page, f in sorted(pages.items()):
            for p in f['patches']:
                if p['class']=='anchor' and p['valid']:
                    anchors.setdefault(p['sample_key'],[]).append({'frame':f['frame'],'page':page,
                        'raw_rgb':p['raw_rgb'],'jpeg_rgb':p['jpeg_rgb'],'roi_polygon':p['roi_polygon']})
        rows, common = [], {}
        for key, samples in anchors.items():
            if len(samples) < 2:
                continue
            raw_y = np.array([q['raw_rgb'] for q in samples]) @ [.25,.5,.25]
            ev = np.log2(np.maximum(raw_y,1e-9)/max(float(np.median(raw_y)),1e-9))
            labs = fs.lab_from_codes([q['jpeg_rgb'] for q in samples])
            de = fs.delta_e00(labs, np.broadcast_to(np.median(labs,axis=0),labs.shape))
            for q,e in zip(samples,ev):
                common.setdefault(q['page'],[]).append(float(e))
                q['raw_EV_from_anchor_median']=float(e)
            rows.append({'sample_key':key,'n':len(samples),'raw_range_EV':float(np.ptp(ev)),
                         'jpeg_de00_from_anchor_median':chain.measure.stats(de),'samples':samples})
        page_ev = {k:float(np.median(v)) for k,v in common.items()}
        corrected = []
        for row in rows:
            ev = [q['raw_EV_from_anchor_median']-page_ev[q['page']] for q in row['samples']]
            row['page_common_EV_removed_range'] = float(np.ptp(ev)); corrected.append(float(np.ptp(ev)))
        incomplete = len(pages)<6 or len(rows)<12 or any(r['n']<6 for r in rows)
        uneven = any(x>.1 for x in corrected) or any(r['jpeg_de00_from_anchor_median']['p90']>2 for r in rows)
        result['uniformity'][unit] = {'status':'unknown-metadata-change' if consistency else 'unknown-incomplete' if incomplete else 'nonuniformity-suspect' if uneven else 'within-thresholds',
             'pages':sorted(pages), 'per_page_common_EV':page_ev, 'anchors':rows,
             'metadata_consistency_errors':consistency,
             'method':'same semantic anchor at six positions; show raw spreads and page-common-EV-removed spreads separately; scores are not corrected'}
    return result
