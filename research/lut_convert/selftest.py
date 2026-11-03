#!/usr/bin/env python3
"""Repeatable parser, transfer, representability and CLI-level regression checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import traceback
from guard import HERE, LOCAL, mount_guard, install_write_fence, output_path, dump


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='local/selftest')
    args = p.parse_args()
    mount_guard(); install_write_fence()
    import numpy as np
    from cube import Cube, write_cube
    from spaces import encode, decode, matrix, Target
    from camera import Camera
    from fit import Problem, score
    from convert import samples, limitations
    out = output_path(HERE/args.out)
    out.mkdir(parents=True, exist_ok=False)
    checks = []

    def check(name, fn):
        try:
            details = fn()
            checks.append(dict(name=name, passed=True, details=details))
            print('PASS', name, flush=True)
        except Exception as exc:
            checks.append(dict(name=name, passed=False, error=str(exc), traceback=traceback.format_exc()))
            print('FAIL', name, str(exc), flush=True)
        dump(out/'results.json', {'checks': checks, 'passed': all(x['passed'] for x in checks)})

    identity2 = ('LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n'
                 '0 0 1\n1 0 1\n0 1 1\n1 1 1\n')

    def parser():
        a = Cube.parse(identity2)
        x = np.array([[.1,.25,.75],[0,1,.5],[1,0,1]])
        np.testing.assert_allclose(a.apply(x), x, atol=1e-14)
        one = Cube.parse('TITLE "test # title"\nLUT_1D_SIZE 3\n0 0 0\n.25 .25 .25\n1 1 1\n')
        np.testing.assert_allclose(one.apply([[.25,.5,.75]]), [[.125,.25,.625]], atol=1e-14)
        domain = Cube.parse('DOMAIN_MIN -1 0 1\nDOMAIN_MAX 1 2 3\n'+identity2)
        np.testing.assert_allclose(domain.apply([[0,1,2]]), [[.5,.5,.5]], atol=1e-14)
        combo = Cube.parse('LUT_1D_SIZE 3\nLUT_3D_SIZE 2\nLUT_1D_INPUT_RANGE -1 1\n'
                           '0 0 0\n.25 .25 .25\n1 1 1\n'+identity2.split('\n',1)[1])
        np.testing.assert_allclose(combo.apply([[0,.5,-.5]]), [[.25,.625,.125]], atol=1e-14)
        return {'rgb_fast_order': True, 'domain_per_channel': True, 'shaper_then_3d': True}
    check('1D / 3D / DOMAIN / shaper literal vectors', parser)

    def sizes():
        emax = {}
        for size in (17,33,65):
            path = out/f'affine_{size}.cube'
            write_cube(path, lambda v: v*np.array([.8,.7,.6])+[.1,.15,.2], size=size)
            a = Cube.read(path)
            x = np.random.default_rng(6).uniform(0,1,(100,3))
            expected = x*np.array([.8,.7,.6])+[.1,.15,.2]
            emax[size] = float(np.max(abs(a.apply(x)-expected)))
            assert emax[size] < 2e-9
        return emax
    check('17 / 33 / 65 cube parsing and tetrahedral interpolation', sizes)

    def rejects():
        cases = ['LUT_3D_SIZE 999999\n', 'LUT_1D_SIZE 1\n0 0 0\n',
                 'LUT_1D_SIZE 2\n0 0 0\nnan 1 1\n', 'LUT_1D_SIZE 2\n0 0 0\n',
                 'LUT_1D_SIZE 2\n0 0 0\n1 1 1\n1 1 1\n',
                 'LUT_3D_SIZE 2\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 0 1 1\n'+identity2.split('\n',1)[1],
                 'LUT_1D_SIZE 2\n0 0 0\nDOMAIN_MIN 0 0 0\n1 1 1\n',
                 'LUT_1D_SIZE 2\nLUT_1D_SIZE 2\n0 0 0\n1 1 1\n',
                 'LUT_3D_SIZE 2\nBOGUS 1\n', 'import os\n',
                 'DOMAIN_MIN 0 0 0\nLUT_1D_INPUT_RANGE 0 1\n'+identity2]
        for text in cases:
            try:
                Cube.parse(text)
            except ValueError:
                continue
            raise AssertionError('bad cube accepted: '+text[:80])
        try:
            output_path(HERE/'candidate.entry')
        except ValueError:
            pass
        else:
            raise AssertionError('output fence accepted a non-local output')
        return {'invalid_inputs_rejected': len(cases), 'output_fence': True}
    check('untrusted data rejection and output fence', rejects)

    def transfers():
        gold = {'flog': (95,470,705), 'flog2': (95,400,570), 'llog': (92,445,634),
                'vlog': (128,433,602), 'slog3': (95,420,None)}
        result = {}
        for space in ('srgb','rec709','gamma24','flog','flog2','llog','llog709','vlog','slog3','slog3-sgamut3','applelog'):
            x = np.r_[0.,.0001,.002,.008,.03,.18,.9,2.,5.]
            error = float(np.max(abs(decode(encode(x,space),space)-x)))
            assert error < 5e-6, (space,error)
            code = encode(np.array([0.,.18,.9]),space)*1023
            if space in gold:
                for actual, expected in zip(code,gold[space]):
                    if expected is not None:
                        assert abs(actual-expected) < 1.1, (space,code)
            result[space] = {'roundtrip_max': error, '10bit_black_18_90': code.tolist()}
        for gamut in ('rec709','rec2020','vgamut','sgamut3','sgamut3cine'):
            np.testing.assert_allclose(matrix(gamut)@np.ones(3), [.3127/.329,1,(1-.3127-.329)/.329], atol=1e-12)
        return result
    check('official transfer vectors / inverse / D65 gamut white', transfers)
    c = Camera()
    x, _ = samples(c,500,77)
    base = c.stock(x)
    hold, _ = samples(c,1000,80)
    hbase = c.stock(hold)

    def forward_match():
        P = Problem(c,x,base)
        error = float(np.max(abs(P.predict(P.theta0,x)-base)))
        assert error < 1e-9
        return {'max_code_error': error}
    check('safe model agrees with independent Engine stock prediction', forward_match)

    def jacobian():
        results = {}
        for variant,bw in (('safe',False),('t1',False),('t2-hypothesis',False),('safe',True)):
            target = np.repeat((base@np.array([.4,.4,.2]))[:,None],3,axis=1) if bw else base*.92+[.5,.1,.4]
            P = Problem(c,x[:100],target[:100],variant,bw)
            th = P.theta0.copy()
            direction = np.random.default_rng(19).normal(size=P.np)
            direction[:P.qstart] *= .01
            direction[P.qstart:P.t2start] *= .1
            if P.t2: direction[P.t2start:] *= .02
            r,J = P.data_parts(th)
            eps = 1e-4
            diff = (P.data_parts(th+eps*direction)[0]-P.data_parts(th-eps*direction)[0])/(2*eps)
            rel = float(np.linalg.norm(diff-J@direction)/max(np.linalg.norm(diff),1e-12))
            assert rel < .025, (variant,bw,rel)
            results[variant+('-bw' if bw else '')] = rel
        gx=np.repeat(np.linspace(30,1200,77)[:,None],3,axis=1)
        target=c.stock(gx)+[1,-.2,.5]
        P=Problem(c,gx,target)
        v=np.zeros(P.np);v[P.qstart:]=np.random.default_rng(33).normal(size=33)
        r,J=P.data_parts(P.theta0);eps=1e-4
        diff=(P.data_parts(P.theta0+eps*v)[0]-P.data_parts(P.theta0-eps*v)[0])/(2*eps)
        rel=float(np.linalg.norm(diff-J@v)/np.linalg.norm(diff))
        assert rel<.005,('neutral-axis',rel)
        results['safe-neutral-axis-with-tinted-target']=rel
        return results
    check('safe / T1 / T2 / B&W directional Jacobian', jacobian)

    native = {}
    for kind in ('tone','sector'):
        def native_test(kind=kind):
            P = Problem(c,x,base,regularization=0)
            th = P.theta0.copy()
            if kind == 'tone':
                outputs = np.rint(c.curve.ys*.86).astype(int)
                target_curve = c.mm.Curve(c.curve.xs, outputs)
                target_fn = lambda z: np.clip(c.mm.Chain(c.E.table,c.row,target_curve,100.).forward(z)['rgb'],0,255)
            else:
                A, B = c.A.copy(), c.B.copy()
                B[4:10] += np.array([1,2,3,3,2,1])
                target_fn = lambda z: c.E.predict('04',z,A=A,B=B)
            expected = target_fn(x)
            P = Problem(c,x,expected,regularization=0)
            fit, solver = P.solve(max_nfev=50)
            q = P.quantize(fit.x)
            result,_ = score(c,hbase,P.predict(q['theta'],hold),target_fn(hold))
            P.export(q,out/('native-'+kind))
            result['solver'] = solver
            native[kind] = (P,q,target_fn)
            if kind == 'sector' and result['similarity'] is None:
                effect = c.fs.delta_e00(c.fs.lab_from_codes(hbase), c.fs.lab_from_codes(target_fn(hold))) > .25
                local,_ = score(c,hbase[effect],P.predict(q['theta'],hold[effect]),target_fn(hold)[effect])
                result = {'all_samples':result, 'affected_sectors':local, 'affected_n':int(effect.sum()),
                          'similarity':local['similarity'],
                          'denominator_scope':'only baseline DE00 > .25; unaffected sectors keep global similarity undefined'}
            assert result['similarity'] is not None and result['similarity'] > .985, result
            return result
        check('exactly representable native '+kind+' reaches 98.5% after integerization',native_test)

    def cube_native():
        result = {}
        for kind,(_,_,fn) in native.items():
            path = out/f'native-{kind}.cube'
            def transform(rgb):
                parts = []
                for start in range(0,len(rgb),2048):
                    xx, valid, _ = c.inverse(rgb[start:start+2048]*255)
                    y = fn(xx)/255
                    y[~valid] = rgb[start:start+2048][~valid]
                    parts.append(y)
                return np.vstack(parts)
            write_cube(path,transform,size=33,title='native-'+kind)
            lut = Cube.read(path)
            target = lut.apply(base/255)*255
            P = Problem(c,x,target,regularization=0)
            fit,solver = P.solve(max_nfev=45)
            q = P.quantize(fit.x)
            desired = lut.apply(hbase/255)*255
            s,_ = score(c,hbase,P.predict(q['theta'],hold),desired)
            if s['similarity'] is None and kind == 'sector':
                effect=c.fs.delta_e00(c.fs.lab_from_codes(hbase),c.fs.lab_from_codes(desired)) > .25
                local,_=score(c,hbase[effect],P.predict(q['theta'],hold[effect]),desired[effect])
                s={'all_samples':s,'affected_sectors':local,'affected_n':int(effect.sum()),'similarity':local['similarity']}
            result[kind] = s
            # Grid interpolation and the stock inverse's unavailable boundary are retained in this test.
            assert s['similarity'] is not None and s['similarity'] > .97, (kind,s)
        return result
    check('representable native effect through .cube reader and fit',cube_native)

    def bw():
        pre = c.curve(x)
        expected = np.repeat((pre@np.array([.5,.3,.2]))[:,None],3,axis=1)
        P = Problem(c,x,expected,bw=True,regularization=0)
        f,s = P.solve(max_nfev=40);q = P.quantize(f.x)
        desired = np.repeat((c.curve(hold)@np.array([.5,.3,.2]))[:,None],3,axis=1)
        metric,_ = score(c,hbase,P.predict(q['theta'],hold),desired)
        exported = P.export(q,out/'bw-native03')
        assert metric['de00']['median'] < .06
        assert exported['mask'] == 17 and not exported['T_writes_required']
        return {'metric':metric,'export':exported}
    check('native 03 monochrome curve plus channel mixer exports without T',bw)

    def split_tone():
        def transform(rgb):
            y = rgb@np.array([.2126,.7152,.0722])
            drift = (2*y-1)[:,None]*np.array([-.065,.005,.065])
            return np.clip(rgb+drift,0,1)
        path = out/'split-tone.cube';write_cube(path,transform,size=17)
        target = Target(Cube.read(path),'srgb')
        scene = c.scene(ROOT/'captures/a12-50/2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051131.DNG',160)
        desired = target.render(base)
        P = Problem(c,x,desired)
        f,s = P.solve(max_nfev=30);q=P.quantize(f.x)
        metric,_=score(c,hbase,P.predict(q['theta'],hold),target.render(hbase))
        limits=limitations(c,target,scene,False,{'safe':{'synthetic_holdout':metric}})
        assert limits['split_toning_limited']
        # Neutral greys cannot acquire brightness-dependent tint with the daily controls.
        grayx=np.repeat(np.linspace(20,1200,80)[:,None],3,axis=1)
        graypred=P.predict(q['theta'],grayx)
        graytarget=target.render(c.stock(grayx))
        e=c.fs.delta_e00(c.fs.lab_from_codes(graypred),c.fs.lab_from_codes(graytarget))
        assert float(np.percentile(e,90))>2
        return {'metric':metric,'limitations':limits,'neutral_p90_de00':float(np.percentile(e,90))}
    from guard import ROOT
    check('split toning is detected and retains irreducible neutral error',split_tone)
    dump(out/'inputs.json',c.E.provenance.finish())
    passed=all(x['passed'] for x in checks)
    print('checks',len(checks),'passed',sum(x['passed'] for x in checks))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
