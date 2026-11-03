#!/usr/bin/env python3
"""Split slot 05 neutral errors and enforce per-patch tint protection on refit."""
import sys
sys.dont_write_bytecode = True
import copy
import importlib.util
import json
from pathlib import Path
import signal

import numpy as np

HERE = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location('chrome_neutral_base', HERE / 'fit_v2.py')
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
LOCAL = m.LOCAL / 'neutral_followup'
TRIGGER, ALLOWANCE = .5, .3


def tint_at_target_lightness(lab, target):
    aligned = np.asarray(lab, float).copy()
    aligned[..., 0] = target[..., 0]
    return aligned


def neutral_split(P, lab, baseline):
    idx = np.array([i for i, label in enumerate(P.labels) if label in m.fs.NEUTRAL])
    target, pred, base = P.lt[idx], lab[idx], baseline[idx]
    aligned = tint_at_target_lightness(pred, target)
    base_aligned = tint_at_target_lightness(base, target)
    total = m.fs.delta_e00(target, pred)
    tint = m.fs.delta_e00(target, aligned)
    tint_shift = m.fs.delta_e00(base_aligned, aligned)
    parts = m.fs.de00_components(target, pred)
    # CIEDE2000 lightness is orthogonal to the two coupled chroma/hue terms.
    assert np.allclose(total**2, parts[:, 0]**2 + tint**2, atol=1e-12)
    records = []
    for j, i in enumerate(idx):
        delta = pred[j] - target[j]
        records.append({'label': P.labels[i], 'dL': float(delta[0]), 'da': float(delta[1]),
                        'db': float(delta[2]), 'total_de00': float(total[j]),
                        'lightness_de00_signed': float(parts[j, 0]), 'tint_de00': float(tint[j]),
                        'tint_shift_from_v1_de00': float(tint_shift[j]),
                        'lightness_squared_fraction': float(parts[j, 0]**2 / total[j]**2),
                        'tint_direction': 'red_blue' if delta[1] > 0 and delta[2] < 0 else 'other'})
    return {'total_de00': m.stat(total), 'tint_de00': m.stat(tint),
            'tint_shift_from_v1_de00': m.stat(tint_shift), 'per_patch': records,
            'lightness_squared_fraction_all': float(np.sum(parts[:, 0]**2) / np.sum(total**2)),
            'lightness_dominates_patch_count': int(np.sum(parts[:, 0]**2 > tint**2))}


class ProtectedProblem(m.Problem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.mode == 'sector'
        self.neutral_idx = np.array([i for i, label in enumerate(self.labels) if label in m.fs.NEUTRAL])
        self.neutral_target = self.lt[self.neutral_idx]
        baseline = self.predict(np.zeros(48), self.neutral_idx)
        self.neutral_limit = m.fs.delta_e00(self.neutral_target,
                                           tint_at_target_lightness(baseline, self.neutral_target)) + ALLOWANCE

    def neutral_tint(self, th):
        lab = self.predict(th, self.neutral_idx)
        return m.fs.delta_e00(self.neutral_target, tint_at_target_lightness(lab, self.neutral_target))

    def residuals(self, th, idx=None):
        residual = super().residuals(th, idx)
        # All six neutrals remain in every fold. The penalty guides the solver;
        # quantize() and final evaluation reject violations before publication.
        over = np.maximum(self.neutral_tint(th) - self.neutral_limit, 0.)
        return np.r_[residual, 1000. * over]

    def quantize(self, th, idx=None, passes=2):
        q = super().quantize(th, idx, passes)
        assert np.all(self.neutral_tint(np.array(q['theta'])) <= self.neutral_limit + 1e-9)
        return q


def evaluate(S, target, samples, e, q, folds, previous):
    P = m.problem(S, samples, e, 'sector')
    baseline = P.predict(np.zeros(48))
    lab = P.predict(np.array(q['theta']))
    original = m.f.JointProblemV2.predict(P, np.array(q['theta']))
    assert np.max(abs(lab-original)) < 1e-10
    loo_lab = lab.copy()
    for i in P.chrom_idx:
        label = P.labels[i]
        fold = folds[label]
        assert label not in fold['training_labels']
        loo_lab[i] = m.f.JointProblemV2.predict(P, np.array(fold['theta']), np.array([i]))[0]
    rows, lin = m.fs.ring_design_scenes()
    r04 = m.fs.Nominal04(S.ctx).render(lin)
    xring = S.chain.invert(r04)['x']
    target_ring = np.array([target.scene_target(l @ m.fs.M709.T) for l in lin])
    q0 = {'Cq': S.rows['row1'].coef.tolist(), 'A': np.array(S.ctx.stock)[:,0].tolist(),
          'B': np.array(S.ctx.stock)[:,1].tolist()}
    rbase, ring = m.render(S, xring, e, q0), m.render(S, xring, e, q)
    old = P.predict(np.array(previous['theta']))
    bneutral = neutral_split(P, baseline, baseline)
    nneutral = neutral_split(P, lab, baseline)
    oldneutral = neutral_split(P, old, baseline)
    deltas = np.array([v['tint_de00']-b['tint_de00'] for v,b in zip(nneutral['per_patch'], bneutral['per_patch'])])
    assert (deltas <= ALLOWANCE + 1e-9).all()
    fold_increase_max = -float('inf')
    for fold in folds.values():
        flab = m.f.JointProblemV2.predict(P, np.array(fold['theta']))
        split = neutral_split(P, flab, baseline)
        increase = [v['tint_de00']-b['tint_de00'] for v,b in zip(split['per_patch'], bneutral['per_patch'])]
        fold_increase_max = max(fold_increase_max, max(increase))
    assert fold_increase_max <= ALLOWANCE + 1e-9
    total, total_base = m.fs.delta_e00(P.lt, lab), m.fs.delta_e00(P.lt, baseline)
    per = {P.labels[i]: {'de00':float(m.fs.delta_e00(P.lt[i],loo_lab[i])),
                        'dL':float(loo_lab[i,0]-P.lt[i,0])} for i in P.chrom_idx}
    ring_bins = []
    for h0 in range(0,360,30):
        sel = np.array([h0 <= r['lab_h_design_deg'] < h0+30 for r in rows])
        ring_bins.append({'design_hue':[h0,h0+30], 'n':int(sel.sum()),
                          'baseline':m.stat(m.fs.delta_e00(target_ring[sel],rbase[sel])),
                          'candidate':m.stat(m.fs.delta_e00(target_ring[sel],ring[sel]))})
    metrics = {'loo':m.stat(m.fs.delta_e00(P.lt,loo_lab)[P.chrom_idx]),
               'ring':m.stat(m.fs.delta_e00(target_ring,ring)),
               'in_sample':m.fm.group_stats(P,total),
               'loo_per_patch':per, 'signatures':m.signatures(P,lab,baseline,loo_lab),
               'ring_traits':{'chroma_ratio_to_v1':m.stat(m.fs.lch(ring)[1]/m.fs.lch(rbase)[1]),
                              'target_chroma_ratio_to_v1':m.stat(m.fs.lch(target_ring)[1]/m.fs.lch(rbase)[1])},
               'ring_by_design_hue':ring_bins, 'neutral':nneutral}
    base_metrics = {'loo':m.stat(total_base[P.chrom_idx]), 'ring':m.stat(m.fs.delta_e00(target_ring,rbase))}
    metrics['gate'] = {name:condition for name,condition in (
        ('loo_median_improves',metrics['loo']['median'] < base_metrics['loo']['median']),
        ('ring_median_improves',metrics['ring']['median'] < base_metrics['ring']['median']),
        ('loo_p90_not_worse',metrics['loo']['p90'] <= base_metrics['loo']['p90']),
        ('ring_p90_not_worse',metrics['ring']['p90'] <= base_metrics['ring']['p90']))}
    metrics['passes'] = all(metrics['gate'].values())
    assert metrics['passes']
    return {'baseline':base_metrics, 'baseline_neutral':bneutral, 'before_refit_neutral':oldneutral,
            'candidate':metrics, 'neutral_tint_increase_max':float(deltas.max()),
            'fold_neutral_tint_increase_max':float(fold_increase_max),
            'model_sha256':m.sha(S.model_path), 'inputs_sha256':S.inputs,
            'baseline_tables':m.baseline_check(S)}


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('180 second follow-up bound')))
    signal.alarm(180)
    LOCAL.mkdir(exist_ok=True)
    fit_path = m.LOCAL/'fit.json'
    before_path = LOCAL/'fit_before.json'
    if not before_path.exists():
        before_path.write_bytes(fit_path.read_bytes())
    before = json.loads(before_path.read_text())
    old_data = json.loads((m.LOCAL/'evaluation.json').read_text())
    previous = old_data['variants']['sector']['full']
    inputs = dict(old_data['inputs_sha256_before'])
    for p in [Path(__file__), HERE/'verify_v2.py', before_path, m.LOCAL/'evaluation.json', m.LOCAL/'training.json']:
        inputs[str(p)] = m.sha(p)
    assert all(m.sha(p)==h for p,h in old_data['inputs_sha256_before'].items())
    S,T,samples,e,ei = m.setup()
    P = ProtectedProblem(S,samples,S.curves['chrome'],e,'sector',lam_s=m.REG['smooth'],
                         lam_y=0,lam_c=0,mu=m.REG['sector_ridge'])
    baseline = P.predict(np.zeros(48))
    initial = neutral_split(P,P.predict(np.array(previous['theta'])),baseline)
    triggered = initial['tint_shift_from_v1_de00']['max'] > TRIGGER
    assert triggered
    th,cost = P.solve(max_nfev=600,tol=1e-9)
    assert np.all(P.neutral_tint(th) <= P.neutral_limit + 1e-9)
    q = P.quantize(th)
    folds = {}
    for i in P.chrom_idx:
        idx = np.array([j for j in P.fit_idx if j != i])
        ft,_ = P.solve(th,idx,max_nfev=350,tol=1e-8)
        fq = P.quantize(ft,idx)
        fq.update({'held_out':P.labels[i], 'training_labels':[P.labels[j] for j in idx],
                   'continuous_theta':ft.tolist()})
        folds[P.labels[i]] = fq
    print('protected_refit_and_18_integer_folds_done',flush=True)
    out = {'schema':'gxr-05-neutral-followup/1', 'trigger':TRIGGER, 'allowance':ALLOWANCE,
           'refitted':True, 'triggered_by_tint_change_not_worsening':triggered,
           'tint_metric':'deltaE00 at target L, with original a,b; per patch, no averaging before gate',
           'constraint_fit_model':'ISO200', 'cross_check':'ISO1600 frozen parameters and folds',
           'continuous_theta':th.tolist(), 'full':q, 'folds':folds, 'models':{}}
    for tag in ('iso200','iso1600'):
        Sc,Tc,ss,ec,eic = m.setup(tag)
        rec = evaluate(Sc,Tc,ss,ec,q,folds,previous)
        out['models'][tag] = rec
        print(tag,'neutral_v1',round(rec['baseline_neutral']['total_de00']['median'],4),
              'neutral_candidate',round(rec['candidate']['neutral']['total_de00']['median'],4),
              'max_tint_error_increase',round(rec['neutral_tint_increase_max'],4),
              'colour_gate',rec['candidate']['passes'],flush=True)
    out['colour_words_unchanged'] = all(q[k]==previous[k] for k in ('A','B','Cq'))
    out['integer_folds_unchanged'] = all(all(folds[l][k]==old_data['variants']['sector']['folds'][l][k]
                                               for k in ('A','B','Cq')) for l in folds)
    out['inputs_sha256_before'] = inputs
    out['inputs_sha256_after'] = {p:m.sha(p) for p in inputs}
    assert out['inputs_sha256_after']==inputs
    fit = copy.deepcopy(before)
    A,B = np.array(q['A']),np.array(q['B'])
    Z = m.fs.Z_of_words(A,B,S.ctx)
    fit['colour_words']['row_hex'] = b''.join(m.fs.encode_word(int(a),int(b)) for a,b in zip(A,B)).hex()
    fit['colour_words']['words'] = [{'sector':s,'new_ab':[int(A[s]),int(B[s])],
                                    'word_hex':m.fs.encode_word(int(A[s]),int(B[s])).hex(),
                                    'coef_scale':float(abs(Z[s])),'coef_rot_deg':float(np.angle(Z[s],deg=True))}
                                   for s in range(24)]
    fit['predicted_de00'] = {tag:rec['candidate'] for tag,rec in out['models'].items()}
    fit['alternatives']['sector']['colour_words'] = copy.deepcopy(fit['colour_words'])
    fit['alternatives']['sector']['predicted_de00'] = copy.deepcopy(fit['predicted_de00'])
    fit['neutral_protection'] = {'tint_error_allowance_de00':ALLOWANCE,
                                'trigger_tint_shift_de00':TRIGGER,'refitted':True,
                                'full_and_18_folds_pass_both_models':True,
                                'colour_words_unchanged':out['colour_words_unchanged'],
                                'evaluation_path':'local/neutral_followup/evaluation.json'}
    fit['stage'],fit['firmware_ready'] = 'v2-candidate',False
    src = m.load_module('chrome_protected_source',m.ROOT/'firmware/stage2j/tools/deep_sources.py')
    src.json_colour(fit,'05 neutral-protected candidate')
    src.json_matrix(fit,'05 neutral-protected candidate')
    assert all(P.sector_ok(int(a),int(b),s) for s,(a,b) in enumerate(zip(A,B)))
    assert np.array_equal(np.array(q['Cq']),S.rows['row1'].coef)
    m.dump(LOCAL/'evaluation.json',out)
    m.dump(fit_path,fit)
    out_hash = m.sha(fit_path)
    m.dump(LOCAL/'verification.json',{'fit_json_sha256':out_hash,
           'before_fit_json_sha256':m.sha(before_path),'inputs_unchanged':True,
           'protected_input_count':len(inputs),'tint_limit_per_patch_pass':True,
           'both_iso_four_condition_colour_gate_pass':True,
           'colour_words_unchanged':out['colour_words_unchanged'],
           'integer_folds_unchanged':out['integer_folds_unchanged']})
    print('PASS','colour_words_unchanged',out['colour_words_unchanged'],
          'integer_folds_unchanged',out['integer_folds_unchanged'],flush=True)


if __name__=='__main__':
    main()
