#!/usr/bin/env python3
"""Local residual-corrected v2 refit. Emits review-only JSON, never a DAT."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import json
import math
from types import SimpleNamespace
import numpy as np
from scipy.optimize import least_squares
from common import ROOT, LOCAL, read, dump, helper, require, sha, mount_guard, Provenance, output_path
from model import Engine
from measure import stats


class Problem:
    """Fit F(theta,x) + [JPEG_measured - F(theta_deployed,x)] in RGB code space.

    The correction is fixed at each measured scene input. It removes the local
    model bias at the deployed table; the v2 Jacobian supplies the change with
    table parameters. Its extrapolation must be checked by another camera shot.
    """
    def __init__(self, engine, slot, x, observed, target_lab, train=None, gray=None,
                 ridge=.06, smooth=.3, max_log_step=.22, max_angle_step=.22):
        self.E, self.slot = engine, slot
        self.fs, self.mm = engine.fs, engine.mm
        self.x, self.observed, self.target = map(lambda a: np.asarray(a, float), (x, observed, target_lab))
        self.row, self.A, self.B = engine.parameters(slot)
        self.color = slot != '03'
        self.np = 50 if self.color else 2
        self.pre = engine.curve_of(slot)(self.x)
        self.gray = np.zeros(len(x), bool) if gray is None else np.asarray(gray, bool)
        self.train = np.ones(len(x), bool) if train is None else np.asarray(train, bool)
        self.weight = np.where(self.gray, 4., 1.)
        self.ybase, self.ci = self.row.apply(self.pre)
        self.yderiv = np.column_stack([self.pre[:, 0]-self.pre[:, 1], self.pre[:, 2]-self.pre[:, 1]])
        self.initial = np.zeros(self.np)
        if self.color:
            z = self.fs.Z_of_words(self.A, self.B, engine.ctx)
            self.initial[2:26], self.initial[26:] = np.log(abs(z)), np.angle(z)
            h = self.mm.hue_deg(self.ci)
            W = engine.table.kernel_weights(h, abs(self.ci))
            self.T0, self.G = W @ engine.ctx.S_eff, W*engine.table.gain
            self.safety = helper('safety').Safety(SimpleNamespace(table=engine.table, ctx=engine.ctx))
        # The signed bias is observed minus predicted, not the reverse.
        self.bias = self.observed - engine.predict(slot, self.x, unclipped=True)
        self.ridge, self.smooth = ridge, smooth
        self.max_log_step, self.max_angle_step = max_log_step, max_angle_step
        self.R = self.regularizer()

    def regularizer(self):
        r = [np.eye(self.np)[0]*math.sqrt(self.ridge)/.08,
             np.eye(self.np)[1]*math.sqrt(self.ridge)/.08]
        if self.color:
            for offset, unit in ((2, .1), (26, math.radians(5))):
                for j in range(24):
                    v = np.zeros(self.np)
                    v[offset+j] = math.sqrt(self.ridge)/unit
                    r.append(v)
                    v = np.zeros(self.np)
                    v[offset+j], v[offset+(j+1)%24] = -math.sqrt(self.smooth), math.sqrt(self.smooth)
                    r.append(v/unit)
        return np.array(r)

    def parts(self, theta):
        y = self.ybase + self.yderiv @ theta[:2]
        if self.color:
            E = np.exp(theta[2:26]+1j*self.E.table.k*theta[26:])
            co = self.ci * (self.T0+self.G@(self.E.ctx.S_eff*(E-1)))
            return y, co, E
        return y, np.zeros(len(y), complex), None

    def corrected_rgb(self, theta):
        y, co, _ = self.parts(theta)
        rgb = self.mm.rgb_from_ycc(y, co) if self.color else np.repeat(y[:, None], 3, axis=1)
        return np.clip(rgb+self.bias, 0, 255)

    def data_residual(self, y, co):
        rgb = self.mm.rgb_from_ycc(y, co) if self.color else np.repeat(y[:, None], 3, axis=1)
        lab = self.fs.lab_from_codes(np.clip(rgb+self.bias, 0, 255))
        return self.fs.de00_components(self.target, lab) * np.sqrt(self.weight[:, None])

    def residuals(self, theta):
        y, co, _ = self.parts(theta)
        r = [self.data_residual(y, co)[self.train].ravel(), self.R@(theta-self.initial)]
        if self.color:
            r.append(self.safety.penalty(theta[2:26], theta[26:]))
            P = self.E.ctx.S_eff*np.exp(theta[2:26]+1j*theta[26:])*32
            ab = np.r_[P.real-self.E.ctx.d0, -P.imag-self.E.ctx.d1]
            r.append(np.maximum(abs(ab)-126.5, 0)*10)
        return np.concatenate(r)

    def jacobian(self, theta):
        y, co, E = self.parts(theta)
        eps = 1e-4
        dy = (self.data_residual(y+eps, co)-self.data_residual(y-eps, co))/(2*eps)
        J = np.zeros((len(y), 3, self.np))
        J[:, :, :2] = dy[:, :, None]*self.yderiv[:, None, :]
        if self.color:
            db = (self.data_residual(y, co+eps)-self.data_residual(y, co-eps))/(2*eps)
            dr = (self.data_residual(y, co+1j*eps)-self.data_residual(y, co-1j*eps))/(2*eps)
            dc = self.ci[:, None]*self.G*(self.E.ctx.S_eff*E)[None, :]
            dp = 1j*self.E.table.k*dc
            J[:, :, 2:26] = db[:, :, None]*dc.real[:, None, :]+dr[:, :, None]*dc.imag[:, None, :]
            J[:, :, 26:] = db[:, :, None]*dp.real[:, None, :]+dr[:, :, None]*dp.imag[:, None, :]
        parts = [J[self.train].reshape(-1, self.np), self.R]
        if self.color:
            _, sj = self.safety.penalty(theta[2:26], theta[26:], True)
            parts.append(np.column_stack([np.zeros((len(sj), 2)), sj]))
            P = self.E.ctx.S_eff*np.exp(theta[2:26]+1j*theta[26:])*32
            ab = np.r_[P.real-self.E.ctx.d0, -P.imag-self.E.ctx.d1]
            ej = np.zeros((48, self.np)); ix = np.arange(24)
            ej[ix, ix+2], ej[ix, ix+26] = P.real, -P.imag
            ej[ix+24, ix+2], ej[ix+24, ix+26] = -P.imag, -P.real
            ej *= (10*(abs(ab)>126.5)*np.sign(ab))[:, None]
            parts.append(ej)
        return np.vstack(parts)

    def solve(self, max_nfev=60):
        low, high = self.initial.copy(), self.initial.copy()
        low[:2], high[:2] = -.12, .12
        if self.color:
            low[2:26] -= self.max_log_step; high[2:26] += self.max_log_step
            low[2:26] = np.maximum(low[2:26], math.log(.25))
            low[26:] -= self.max_angle_step; high[26:] += self.max_angle_step
        return least_squares(self.residuals, np.clip(self.initial, low+1e-9, high-1e-9),
                             jac=self.jacobian, bounds=(low, high), max_nfev=max_nfev,
                             x_scale='jac', ftol=1e-8, xtol=1e-8, gtol=1e-6)

    def quantize(self, theta):
        C = self.row.coef.copy()
        dy = np.rint(theta[:2]*1024).astype(int)
        C[0, 0] += dy[0]; C[0, 2] += dy[1]; C[0, 1] = 1024-C[0, 0]-C[0, 2]
        row = self.row.copy(coef=C)
        if self.color:
            z = np.exp(theta[2:26]+1j*theta[26:])
            A, B, clipped = self.fs.to_words(z, self.E.ctx)
            require(not clipped.any(), '扇区量化越界；不允许静默裁切')
            self.rounding_repair_steps = 0
            if not self.safety.check(A, B):
                # Quantisation can cross a hue derivative limit. Repair integer words,
                # exactly as round 4 does, then recheck rather than trusting continuous safety.
                violation = self.safety.violation(A, B)
                for _ in range(5):
                    improved = False
                    for sector in range(24):
                        for da, db in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
                            aa, bb = A.copy(), B.copy(); aa[sector] += da; bb[sector] += db
                            value = self.safety.violation(aa, bb)
                            if value < violation-1e-12:
                                A, B, violation = aa, bb, value
                                improved = True; self.rounding_repair_steps += 1
                    if self.safety.check(A, B) or not improved:
                        break
                require(self.safety.check(A, B), '扇区整数修复后仍违反 round-4 安全约束')
        else:
            A, B = self.A.copy(), self.B.copy()
        row2, rule = self.mm.row2_from_row1(row, self.E.rows)
        require(not self.E.src.matrix_problems(row.to_bytes()+row2.to_bytes()), '矩阵编码违反原加载器约束')
        require(row.coef[0].sum() == 1024, 'Y 行和必须为 1024')
        if self.slot == '03':
            require(row.coef[0].min() >= -128 and row.coef[0].max() <= 1280, '03 Y 行超出 round-2 域')
        colour = b''.join(self.fs.encode_word(a, b) for a, b in zip(A, B))
        require(all(self.fs.decode_word(colour[i*4:i*4+4]) == (a, b) for i, (a, b) in enumerate(zip(A, B))),
                '扇区编码往返失败')
        return row, row2, A, B, colour, rule

    def integer_rgb(self, candidate):
        row, _, A, B, _, _ = candidate
        return np.clip(self.E.predict(self.slot, self.x, row, A, B, unclipped=True)+self.bias, 0, 255)


def split_indices(frames, gray, hues):
    charts = np.concatenate([np.repeat(f['chart'], int(np.asarray(f['valid']).sum())) for f in frames])
    if 'physical' in charts and 'hue-ring' in charts:
        train = charts == 'hue-ring'
        rule = 'screen trained; whole physical chart held out'
    else:
        # Entire hue bins stay together; greys are training anchors, never split by adjacent pixels.
        train = (np.floor(hues/15).astype(int) % 3 != 0) | gray
        rule = 'hue bins 0,3,... held out; greys train only'
    require(train.sum() >= 12 and (~train).sum() >= 4, '至少需要 12 个训练色块和 4 个留出色块')
    return train, rule


def candidate_gates(P, candidate, train, iso_engines):
    row, row2, A, B, colour, rule = candidate
    projected = P.integer_rgb(candidate)
    before = P.fs.delta_e00(P.fs.lab_from_codes(P.observed), P.target)
    after = P.fs.delta_e00(P.fs.lab_from_codes(projected), P.target)
    gates, safety = {}, {}
    for label, sel in (('training', train), ('heldout', ~train)):
        b, a = stats(before[sel]), stats(after[sel])
        gates[f'{label}_median_improves'] = a['median'] < b['median']-1e-6
        gates[f'{label}_p90_not_worse'] = a['p90'] <= b['p90']+1e-9
    gray = stats(after[P.gray])
    gates['gray_median_le_0p6_max_le_1p4'] = bool(gray['n'] and gray['median'] <= .6 and gray['max'] <= 1.4)
    chrom = ~P.gray
    if P.slot == '03':
        b, a = stats(before[chrom]), stats(after[chrom])
        gates['03_chromatic_median_p90_not_worse'] = a['median'] <= b['median'] and a['p90'] <= b['p90']
    else:
        for iso, E in iso_engines.items():
            safety[str(iso)] = E.safety(A, B, dense=True)
            gates[f'sector_safety_iso{iso}'] = safety[str(iso)]['passes']
            full = E.full_chain_safety(P.slot, row, A, B)
            safety[str(iso)]['full_chain'] = full
            gates[f'full_chain_iso{iso}'] = full['all_outputs_no_hue_reversal'] and full['neutral_ramp_preserved']
    # Preserve the existing split-tone rows, tone nodes, T1 flags and controls.
    gates['chroma_rows_unchanged'] = bool(np.array_equal(row.coef[1:], P.row.coef[1:]) and row.tail == P.row.tail)
    return {'conditions': gates, 'passes': all(gates.values()), 'safety': safety,
            'before': {'all': stats(before), 'heldout': stats(before[~train])},
            'projected_after': {'all': stats(after), 'heldout': stats(after[~train]), 'gray': gray},
            'projected_rgb': projected}


def run(measurement_path, output, slots=None, max_nfev=60):
    mount_guard()
    output = output_path(output)
    prov = Provenance()
    measurement = read(prov.add(measurement_path))
    require(measurement.get('schema') == 'closedloop-measurement/1', '测量结果 schema 不符')
    require(measurement.get('eligible_for_refit') is True and not measurement.get('diagnostic_only'),
            '拍摄条件或诊断标记未通过，禁止回拟；请重拍合格组')
    for path, q in measurement.get('provenance', {}).items():
        require(sha(prov.add(path)) == q['sha256'], '测量输入已变化，须重测')
    frames = measurement['frames']
    requested = slots or sorted({f['slot'] for f in frames if f['slot'] != '04'})
    results = {}
    for slot in requested:
        require(slot in ('01', '02', '03', '05', '06'), '只回拟配方槽位')
        ff = [f for f in frames if f['slot'] == slot]
        require(ff and all(f.get('measurement_valid') for f in ff), f'{slot}: 没有有效实拍')
        paths = {f['model']['table'] for f in ff}
        require(len(paths) == 1, '同槽位不能混用不同 DAT')
        isos = {f['meta']['iso'] for f in ff}
        require(len(isos) == 1, '一次回拟只能使用同一 ISO；另一 ISO 留作安全检查')
        E = Engine(next(iter(paths)), next(iter(isos)), prov)
        def cat(key):
            return np.concatenate([np.asarray(f[key])[np.asarray(f['valid'], bool)] for f in ff])
        x, rgb, target, hues = cat('input_x'), cat('rgb'), cat('target_lab'), cat('hue_deg')
        gray = np.concatenate([np.asarray([q['gray'] for q in f['patches']])[np.asarray(f['valid'], bool)] for f in ff])
        require(np.isfinite(x).all() and np.isfinite(rgb).all() and np.isfinite(target).all(), '回拟输入无效')
        try:
            train, split = split_indices(ff, gray, hues)
            P = Problem(E, slot, x, rgb, target, train, gray)
            solve = P.solve(max_nfev)
            candidate = P.quantize(solve.x)
        except ValueError as exc:
            rejected = {'schema': 'closedloop-rejection/1', 'recipe_slot': slot,
                        'status': '本槽回拟被拒绝，其他槽继续', 'reason': str(exc),
                        'firmware_ready': False, 'accepted': False, 'deployable': False,
                        'review_gate_passed': False, 'measurement_sha256': sha(measurement_path)}
            dump(output / f'slot{slot}_rejected.json', rejected)
            results[slot] = rejected
            print(f'槽位 {slot} 被拒绝：{exc}', flush=True)
            continue
        engines = {iso: Engine(E.table_path, iso, prov) for iso in (200, 1600)}
        gates = candidate_gates(P, candidate, train, engines)
        row, row2, A, B, colour, rule = candidate
        out = {'schema': 'closedloop-candidate/1', 'recipe_slot': slot,
               'status': '待审核；必须再拍同组照片验证；不得部署',
               'firmware_ready': False, 'accepted': False, 'deployable': False,
               'evidence_kind': measurement.get('evidence_kind', 'synthetic' if measurement.get('is_synthetic') else 'camera'),
               'review_gate_passed': gates['passes'] and bool(solve.success),
               'curve': {'input31_u16': E.curve_of(slot).xs[1:-1].astype(int),
                         'output33_u8': E.curve_of(slot).ys.astype(int)},
               'exposure': 1., 't1': False,
               'matrix_row1': row.describe(), 'matrix_row2': row2.describe(), 'matrix_row2_note': rule,
               'colour_words': {'row_hex': colour.hex(), 'words': [{'sector': i, 'new_ab': [a, b]}
                               for i, (a, b) in enumerate(zip(A, B))]},
               'source_table': E.description(), 'measurement_sha256': sha(measurement_path),
               'model_correction': 'F(theta,x) + measured_RGB - F(deployed,x); fixed local bias in RGB codes',
               'trust_region': {'max_Y_step_Q10': 123, 'max_sector_log_scale_step': P.max_log_step,
                                'max_sector_angle_step_rad': P.max_angle_step},
               'validation': {'split': split, 'training_patches': int(train.sum()),
                              'heldout_patches': int((~train).sum()),
                              'is_new_camera_output': False, **gates},
               'solver': {'success': bool(solve.success), 'nfev': solve.nfev, 'message': str(solve.message)},
               'integer_safety_repair_steps': getattr(P, 'rounding_repair_steps', 0),
               'target_definitions': [f['target_definition'] for f in ff]}
        # Keep the standard fitter field codecs usable, while every readiness flag stays false.
        require(E.src.json_colour(out, slot) == colour, '原 fitter 扇区接口往返失败')
        require(E.src.json_matrix(out, slot) == row.to_bytes()+row2.to_bytes(), '原 fitter 矩阵接口往返失败')
        dump(output / f'slot{slot}_candidate.json', out)
        results[slot] = {k: out[k] for k in ('recipe_slot', 'review_gate_passed', 'solver')}
        print(f'槽位 {slot} 候选已写入，仅供审核；审核门槛 {out["review_gate_passed"]}。', flush=True)
    dump(output / 'refit_summary.json', {'schema': 'closedloop-refit/1', 'candidates': results,
                                      'provenance': prov.finish(), 'firmware_ready': False})
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('measurement')
    ap.add_argument('--out', default=str(LOCAL / 'candidates'))
    ap.add_argument('--slots', nargs='+', choices=['01', '02', '03', '05', '06'])
    ap.add_argument('--max-nfev', type=int, default=60)
    a = ap.parse_args()
    run(a.measurement, a.out, a.slots, a.max_nfev)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f'回拟失败：{exc}', file=sys.stderr)
        sys.exit(1)
