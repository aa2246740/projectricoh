"""Chart measurements and targets. No parameters are fitted to recipe JPEGs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
import ast
import csv
import io
import json
from types import SimpleNamespace
import numpy as np

ASSIGN = dict(zip([f'R805{n}' for n in range(1693, 1702)],
                  ['04', '01', '02', '03', '05', '06', '07', '08', 'GRN*001']))
SLOTS = ['01', '02', '03', '05', '06', '07', '08']


def pred(key, x, kind='mount'):
    if key in ('GRN*001', 'FCC*002', 'FCC-001'):
        return a.predict('02' if key == 'GRN*001' else '05', x, 'user:' + key)
    return a.predict(key, x, kind)


def chart(stem):
    f = json.loads((a.HERE / 'charts' / (stem + '.json')).read_text())
    pp = f['patches']
    rgb = np.array([p['jpeg_rgb'] for p in pp])
    raw = np.array([p['raw_rgb'] for p in pp])
    wb = raw / np.array(f['meta']['as_shot_neutral'])
    b = a.models()
    x = b['mm'].calibrate.apply_calibration(wb, b['cal'])
    valid = np.array([p['valid'] for p in pp])
    return dict(frame=f, patches=pp, rgb=rgb, raw=raw, wb=wb, x=x, valid=valid)


def de_lab(A, B): return a.models()['m'].fs.delta_e00(A, B)


def target_score(rgb, target, base, use):
    use = np.asarray(use, bool) & np.isfinite(target).all(1)
    if not use.any(): return dict(n=0)
    L = a.lab(rgb)[use]
    T, B = target[use], a.lab(base)[use]
    e, e0 = de_lab(L, T), de_lab(B, T)
    ch = (a.chroma(L) >= 8) & (a.chroma(T) >= 8)
    return dict(n=int(use.sum()), de00_median=float(np.median(e)), de00_p90=float(np.percentile(e, 90)),
        baseline_de00_median=float(np.median(e0)), similarity=float(1-np.median(e)/np.median(e0)),
        dL_median=float(np.median(L[:, 0]-T[:, 0])), dC_median=float(np.median(a.chroma(L)-a.chroma(T))),
        dhue_median=float(np.median(a.dh(a.hue(L)[ch], a.hue(T)[ch]))) if ch.any() else None,
        hue_n=int(ch.sum()))


def relative_metrics(rgb, base, use):
    return a.metrics(rgb, base, use)


def csv_write(name, rows):
    keys = list(rows[0])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys)
    w.writeheader()
    for r in rows:
        w.writerow({k:json.dumps(a.plain(v), ensure_ascii=False) if isinstance(v, (list, dict, np.ndarray)) else a.plain(v)
                    for k, v in r.items()})
    (a.HERE / name).write_text(buf.getvalue())


def bleach_target():
    """Use only the original pure interpolation definitions, without its CLI runtime."""
    path = a.ROOT / 'research/gr4_bleach_fit_r1/target.py'
    text = path.read_text()
    tree = ast.parse(text)
    names = {'feature', 'relative', 'grouped', 'DenseTarget'}
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    assert len(nodes) == 4
    root = a.ROOT / 'research/gr4_bleach_fit_r1/local'
    rt = SimpleNamespace(LOCAL=root, read=lambda p:json.loads((root / p).read_text()))
    from scipy.interpolate import LinearNDInterpolator
    from scipy.spatial import cKDTree
    ns = dict(rt=rt, np=np, LinearNDInterpolator=LinearNDInterpolator, cKDTree=cKDTree)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    a.dump('bleach_adapter.json', dict(source=str(path.relative_to(a.ROOT)), sha256=a.sha(path),
           definitions=sorted(names), changes='none; CLI imports and runtime setup omitted'))
    return ns['DenseTarget']()


def main():
    b = a.models()
    charts = {st:chart(st) for st in ASSIGN}
    ref = charts['R8051693']
    ids = [p['patch_id'] for p in ref['patches']]
    keys = [p['sample_key'] for p in ref['patches']]
    mid = keys.index('ANCHOR_midgray')
    for f in charts.values(): assert [p['patch_id'] for p in f['patches']] == ids
    # This inverse conditions a second diagnostic on the measured 04 JPEG.
    b['m'].base.entries = b['mount']
    x4, invbad = b['m'].inverse04(ref['rgb'], ref['wb'])
    p4ref = pred('04', ref['x'])
    L4 = a.lab(ref['rgb'])
    grey = np.array([k.startswith('ANCHOR_') and k in ('ANCHOR_white', 'ANCHOR_lightgray', 'ANCHOR_midgray', 'ANCHOR_darkgray') for k in keys])
    candidates = ['04'] + SLOTS + ['GRN*001', 'FCC*002']
    results, perpatch, rankings = {}, [], {}
    for stem, slot in ASSIGN.items():
        f = charts[stem]
        rgb, x = f['rgb'], f['x']
        p = pred(slot, x)
        Li, Lp = a.lab(rgb), a.lab(p)
        same = f['valid'] & ref['valid']
        # Restrict exposure diagnostics to RAW channels clear of the floor.
        rawgood = (f['raw'].min(1) > .002) & (ref['raw'].min(1) > .002)
        ev = np.log2(f['raw'][:, 1]/ref['raw'][:, 1])
        ratio = np.maximum(f['wb'], 1e-6)/np.maximum(ref['wb'], 1e-6)
        xc = x4 * ratio
        pc = pred(slot, xc)
        strict = f['valid'] & (f['raw'].min(1) > .0005)
        scores = {s:a.metrics(rgb, pred(s, x), strict) for s in candidates}
        ranking = sorted(scores, key=lambda k:scores[k]['de00_median'])
        rankings[stem] = dict(scores=scores, rank=ranking)
        if slot == '04':
            oldp, fifty = p.copy(), a.predict('04', x, 'e50')
        elif slot == 'GRN*001':
            oldp, fifty = None, None
        else:
            oldp, fifty = a.predict(slot, x, 'oldmount'), a.predict(slot, x, 'e50')
        rows = {}
        for n, mask in dict(all=np.ones(len(ids), bool), usable=strict, paired=same,
                            midtone=same & (L4[:,0]>=30) & (L4[:,0]<=70),
                            chromatic=same & (a.chroma(L4)>8)).items():
            rows[n] = dict(camera_minus_04=relative_metrics(rgb, ref['rgb'], mask),
                camera_minus_g150=relative_metrics(rgb, p, mask),
                camera_minus_04_conditioned_model=relative_metrics(rgb, pc, mask & ~invbad),
                g150_minus_reference04_prediction=relative_metrics(p, p4ref, mask))
            if oldp is not None:
                rows[n].update(camera_minus_g137=relative_metrics(rgb, oldp, mask),
                    g137_minus_reference04_prediction=relative_metrics(oldp, p4ref, mask),
                    fifty_minus_reference04_prediction=relative_metrics(fifty, p4ref, mask),
                    camera_minus_50mm_design=relative_metrics(rgb, fifty, mask))
        anchors = {}
        for i, key in enumerate(keys):
            if not key.startswith('ANCHOR_'): continue
            Lp4 = a.lab(p4ref)[i]
            q = dict(camera_L=float(Li[i,0]), camera_hue=float(a.hue(Li[i:i+1])[0]) if a.chroma(Li[i:i+1])[0]>=8 else None,
                camera_chroma=float(a.chroma(Li[i:i+1])[0]),
                camera_dL_vs04=float(Li[i,0]-L4[i,0]), camera_dhue_vs04=float(a.dh(a.hue(Li[i:i+1]),a.hue(L4[i:i+1]))[0])
                    if a.chroma(Li[i:i+1])[0]>=8 and a.chroma(L4[i:i+1])[0]>=8 else None,
                g150_dL_vs04=float(Lp[i,0]-Lp4[0]), camera_minus_model_dL=float(Li[i,0]-Lp[i,0]),
                valid=bool(f['valid'][i]), paired_valid=bool(same[i]), raw_green_ev=float(ev[i]))
            if oldp is not None:
                q.update(g137_dL_vs04=float(a.lab(oldp)[i,0]-Lp4[0]),
                         fifty_dL_vs04=float(a.lab(fifty)[i,0]-Lp4[0]))
            anchors[key] = q
        results[slot] = dict(frame=stem, quality=dict(valid=int(f['valid'].sum()), paired=int(same.sum()),
            flags={v:sum(v in p['flags'] for p in f['patches']) for v in sorted({v for p in f['patches'] for v in p['flags']})}),
            exposure=dict(raw_green_ev_median=float(np.median(ev[rawgood])),
                          raw_green_ev_p10=float(np.percentile(ev[rawgood],10)), raw_green_ev_p90=float(np.percentile(ev[rawgood],90)),
                          as_shot_neutral=f['frame']['meta']['as_shot_neutral']),
            metrics=rows, anchors=anchors)
        for i, pp in enumerate(f['patches']):
            L0, P0 = L4[i], a.lab(p4ref)[i]
            hvalid = min(a.chroma(Li[i:i+1])[0], a.chroma(L4[i:i+1])[0]) >= 8
            r = dict(frame=stem, recipe=slot, patch_id=ids[i], sample_key=keys[i], valid=f['valid'][i], paired_valid=same[i],
                flags=pp['flags'], raw_rgb=f['raw'][i], jpeg_rgb=rgb[i], camera_L=Li[i,0], camera_a=Li[i,1], camera_b=Li[i,2],
                camera_hue=a.hue(Li[i:i+1])[0] if a.chroma(Li[i:i+1])[0]>=8 else None,
                camera_dL_vs04=Li[i,0]-L0[0], camera_dhue_vs04=a.dh(a.hue(Li[i:i+1]), a.hue(L4[i:i+1]))[0] if hvalid else None,
                g150_L=Lp[i,0], g150_dL_vs04=Lp[i,0]-P0[0],
                camera_model_de00=de_lab(Li[i:i+1],Lp[i:i+1])[0], camera_model_dL=Li[i,0]-Lp[i,0], raw_green_ev=ev[i],
                g137_L=None if oldp is None else a.lab(oldp)[i,0], fifty_L=None if fifty is None else a.lab(fifty)[i,0])
            for label, qrgb in dict(g150=p, g137=oldp, fifty=fifty).items():
                if qrgb is None:
                    r.update({label+'_hue':None, label+'_dhue_vs04':None, label+'_camera_dhue_residual':None})
                    continue
                qL = a.lab(qrgb)[i:i+1]
                qh = a.hue(qL)[0]
                good = a.chroma(qL)[0] >= 8
                baseline_prediction = a.lab(a.predict('04', ref['x'], 'e50'))[i:i+1] if label == 'fifty' else a.lab(p4ref)[i:i+1]
                baseline_hue = a.hue(baseline_prediction)
                r[label+'_hue'] = qh if good else None
                r[label+'_dhue_vs04'] = a.dh(np.array([qh]), baseline_hue)[0] if good and a.chroma(baseline_prediction)[0]>=8 else None
                r[label+'_camera_dhue_residual'] = a.dh(a.hue(Li[i:i+1]),np.array([qh]))[0] if good and a.chroma(Li[i:i+1])[0]>=8 else None
                r[label+'_relative_dhue_residual'] = a.dh(np.array([r['camera_dhue_vs04']]),np.array([r[label+'_dhue_vs04']]))[0] \
                    if r['camera_dhue_vs04'] is not None and r[label+'_dhue_vs04'] is not None else None
            perpatch.append(r)
        print(slot, stem, 'grey L/dL', round(Li[mid,0],2), round(Li[mid,0]-L4[mid,0],2),
              'model dL', round(Lp[mid,0]-a.lab(p4ref)[mid,0],2), 'residual',
              round(rows['usable']['camera_minus_g150']['de00_median'],3),
              'EV', round(float(np.median(ev[rawgood])),4), 'rank', ranking[:3], flush=True)
    a.dump('chart_metrics.json', results)
    a.dump('chart_recipe_ranking.json', rankings)
    csv_write('patch_metrics.csv', perpatch)
    # Compare a continuum at fixed 04 output L, including the older L=50 benchmark.
    ramp = np.repeat(np.geomspace(1, 4094, 3000)[:,None], 3, 1)
    lr = a.lab(pred('04', ramp))[:,0]
    design = {}
    for target in (20,25,30,50,70,85):
        i = int(np.argmin(abs(lr-target)))
        row = {}
        for s in SLOTS:
            row[s] = {kind:float(a.lab(a.predict(s, ramp[i:i+1],kind))[0,0]-lr[i]) for kind in ('oldmount','mount','e50')}
        design[str(target)] = dict(actual_L04=float(lr[i]), recipes=row)
    a.dump('design_grey.json', design)
    # Read the existing GR IV 17^3 LUT without running its command-line programs.
    gap = a.load('field_gap_common', 'research/gr_posneg_gap/common.py')
    import os
    os.environ['TMPDIR'] = str(a.TMP)
    for k in ('OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','OMP_NUM_THREADS'): os.environ[k]='1'
    targets = {}
    for slot in ('01','02'):
        stem = next(st for st, s in ASSIGN.items() if s == slot)
        f = charts[stem]
        nodes = np.load(a.ROOT / f'research/gr4_lut_ceiling/local/lut/host_only_RGB_Q8_8_{slot}_17.npz')['nodes']
        target = a.lab(gap.lut_apply(nodes, ref['rgb']))
        use = ref['valid'] & f['valid']
        xmatch = x4 * f['wb']/np.maximum(ref['wb'],1e-6)
        p4match = pred('04', xmatch)
        matchtarget = a.lab(gap.lut_apply(nodes, p4match))
        entries = dict(camera=f['rgb'], mount_g150=pred(slot, f['x']), mount_g137=a.predict(slot,f['x'],'oldmount'),
                       fifty_design=a.predict(slot,f['x'],'e50'))
        targets[slot] = dict(frame=stem, n_total=len(ids), paired_usable=int(use.sum()),
            scores={k:target_score(v,target,ref['rgb'],use) for k,v in entries.items()},
            all_patch_scores={k:target_score(v,target,ref['rgb'],np.ones(len(ids),bool)) for k,v in entries.items()},
            raw_matched_scores={k:target_score(v,matchtarget,p4match,use & ~invbad) for k,v in entries.items()},
            regions={})
        h, c = a.hue(L4), a.chroma(L4)
        regions = dict(neutral=c<8, warm=(c>=8)&((h<75)|(h>345)), green=(c>=8)&(h>=75)&(h<170),
                       blue=(c>=8)&(h>=220)&(h<300), bright=L4[:,0]>60, midtone=(L4[:,0]>=30)&(L4[:,0]<=60), dark=L4[:,0]<30)
        for name, mask in regions.items():
            targets[slot]['regions'][name] = target_score(f['rgb'],target,ref['rgb'],use & mask)
        np.savez_compressed(a.HERE / f'griv_{slot}_patches.npz', target_lab=target, baseline=ref['rgb'], actual=f['rgb'], usable=use)
        print('GR IV', slot, targets[slot]['scores'], flush=True)
    a.dump('griv_posneg.json', targets)
    # Original BB protocol: 04 inverse, sensor bridge, finite interpolation support,
    # and the revised chroma rule. No target values outside support are scored.
    bb = bleach_target()
    f = charts['R8051701']
    target, supported, distance = bb.target(x4, L4)
    usable = ref['valid'] & f['valid'] & supported & ~invbad
    xmatch = x4 * f['wb']/np.maximum(ref['wb'],1e-6)
    p4match = pred('04', xmatch)
    targetmatch, supmatch, dmatch = bb.target(xmatch, a.lab(p4match))
    entries = dict(camera=f['rgb'], mount_g150=pred('GRN*001',f['x']), base02=pred('02',f['x']),
                   fifty_design=a.predict('02', f['x'], 'user:GRN*001@50mm'))
    bbresult = dict(n_total=len(ids), inverse_failed=int(invbad.sum()), target_supported=int(supported.sum()),
        n_paired_usable=int((ref['valid'] & f['valid']).sum()), n_scored=int(usable.sum()),
        excluded_support=[keys[i] for i in np.flatnonzero(~supported | invbad)],
        scores={k:target_score(v,target,ref['rgb'],usable) for k,v in entries.items()},
        raw_matched_scores={k:target_score(v,targetmatch,p4match,usable & supmatch) for k,v in entries.items()},
        all_supported_scores={k:target_score(v,target,ref['rgb'],supported & ~invbad) for k,v in entries.items()},
        target_L_over_100=int((target[usable,0]>100).sum()),
        target_not_real_same_scene_GRIV=True, parameters=[100,2,5,5,0,-5,0,0,0,0],
        primary_population='current page 1 paired valid patches, supported by original dense target; no level search',
        regions={})
    for name, mask in dict(neutral=a.chroma(L4)<8, warm=(a.chroma(L4)>=8)&((a.hue(L4)<75)|(a.hue(L4)>345)),
                           green=(a.chroma(L4)>=8)&(a.hue(L4)>=75)&(a.hue(L4)<170),
                           blue=(a.chroma(L4)>=8)&(a.hue(L4)>=220)&(a.hue(L4)<300), bright=L4[:,0]>60,
                           midtone=(L4[:,0]>=30)&(L4[:,0]<=60), dark=L4[:,0]<30).items():
        bbresult['regions'][name] = target_score(f['rgb'],target,ref['rgb'],usable & mask)
    a.dump('griv_grn.json', bbresult)
    np.savez_compressed(a.HERE / 'griv_grn_patches.npz', target_lab=target, baseline=ref['rgb'], actual=f['rgb'],
                        supported=supported, inverse_bad=invbad, usable=usable, distance=distance)
    print('GR IV GRN', bbresult['n_scored'], bbresult['scores'], flush=True)
    # Verify g150 effective rows against g139m, rather than assuming the label.
    mod139 = b['mm'].g137_modules('firmware/package_v38_g139m/local/SD_ROOT/GXRCE.DAT')
    e139 = b['mm'].entries448(mod139['l08firm'])
    same139 = {s:dict(written_rows=b['mount'][s]['written']==e139[s]['written'],
                      mask=b['mount'][s]['mask']==e139[s]['mask'], control=b['mount'][s]['control']==e139[s]['control']) for s in ['04']+SLOTS}
    oldpreview = json.loads((a.ROOT / 'research/g139m/preview.json').read_text())
    a.dump('g139m_comparison.json',dict(g150_equals_g139m=same139, original_preview=oldpreview['frames']))
    a.finish('measure')


if __name__ == '__main__': main()
