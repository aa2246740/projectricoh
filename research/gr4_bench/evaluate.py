#!/usr/bin/env python3
"""Compute additive-Lab relative and absolute GR IV bench metrics."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import benchlib as b
b.guard()
import numpy as np


def matched():
    return dict(np.load(b.LOCAL/'matched.npz', allow_pickle=False))


def input_x(data, bridge='common_white', ev=0.):
    matrices = dict(np.load(b.LOCAL/'bridges.npz', allow_pickle=False))
    return data['wb_effective'] @ matrices[bridge].T * (320/.0853)*2**ev


def target(e, data, slot, x):
    lab04 = e.fs.lab_from_codes(e.predict('04', x))
    mode = 'pos' if slot == '01' else 'neg'
    lstd = e.fs.lab_from_codes(data['jpeg_std'])
    lmode = e.fs.lab_from_codes(data['jpeg_'+mode])
    return lab04+lmode-lstd, lmode, lab04


def groups(e, data):
    l = e.fs.lab_from_codes(data['jpeg_std'])
    c = np.hypot(l[:,1],l[:,2])
    h = np.degrees(np.arctan2(l[:,2],l[:,1]))%360
    sels = {'all': np.ones(len(l),bool), 'chromatic_Cge6': c>=6, 'neutral_Clt6': c<6}
    sels.update({f'hue_{lo:03d}_{lo+30:03d}': (c>=6)&(h>=lo)&(h<lo+30) for lo in range(0,360,30)})
    sels.update({f'L_{lo}_{hi}': (l[:,0]>=lo)&(l[:,0]<hi) for lo,hi in ((0,35),(35,60),(60,80),(80,101))})
    return sels


def score(e, data, slot, x, prediction):
    relative, absolute, lab04 = target(e,data,slot,x)
    return {kind: {name: b.metric(e.fs,prediction[s],t[s],lab04[s])
                   for name,s in groups(e,data).items()}
            for kind,t in (('relative',relative),('absolute',absolute))}


def baseline():
    e,_ = b.engine()
    data = matched()
    out = {}
    for bridge in ('common_white','per_camera'):
        for ev in (-.3,0.,.3):
            x = input_x(data,bridge,ev)
            key = f'{bridge}_{ev:+.1f}'
            out[key] = {slot: score(e,data,slot,x,e.fs.lab_from_codes(e.predict(slot,x)))
                        for slot in ('01','02')}
    b.dump(b.LOCAL/'baseline.json',out)
    primary = out['common_white_+0.0']
    for slot in primary:
        print(slot, {kind:primary[slot][kind]['all'] for kind in ('relative','absolute')})
    print('hues', {key:value['n'] for key,value in primary['01']['relative'].items()})
    # Identical camera input and model path to round5, not a different approximation.
    g = b.round5()
    regression = {}
    for iso in (200,1600):
        E,_ = b.engine(iso)
        for slot in ('01','02'):
            d = g.Data(slot,iso)
            f = b.read(b.ROOT/f'research/color_fit_v2/gr_round5/local/fit_{slot}_r5.json')
            row,aa,bb = g.engine.f.unpack_solution(f)
            x=d.a['chart_x']*d.a['exposure']
            old = d.forward(d.a['chart_pre'],row,g.fs.Z_of_words(aa,bb,d.ctx))[0]
            new = E.fs.lab_from_codes(E.predict(slot,x))
            assert np.array_equal(old,new)
            regression[f'{slot}_{iso}'] = dict(max_lab_difference=float(abs(old-new).max()),
                                             identical_parameters=True)
    b.dump(b.LOCAL/'engine_crosscheck.json',regression)


def consistency03():
    E,_ = b.engine()
    cm = b.colour()
    matrices = dict(np.load(b.LOCAL/'bridges.npz'))
    radial = np.asarray(b.read(b.ROOT/'research/gr4_modes/local/tone_curves.json')['radial']['gr4_coef_natural_log'])
    out = {}
    t = b.tiff_reader()
    gx=t.Tiff((b.ROOT/'captures/a12-50/2026-10-20/stage2j-v1-calibration/R8051178.DNG').read_bytes()).tags()
    for key,folder,stem in (('hc','gr4hdf-set','R0003007_bw'),('A_hc','gr4-modes','hc_bw')):
        d=dict(np.load(b.LOCAL/f'blocks_{key}.npz'))
        gr=t.Tiff((b.ROOT/f'captures/contrib/2026-10-19/{folder}/{stem}.DNG').read_bytes()).tags()
        A4,i4=cm.dng_camera_to_xyz(gr)
        old,_=cm.common_white_sensor_bridge(gx,gr,np.array(i4['scene_white_xyz_y1']))
        n4=np.asarray(gr[50728]); nx=np.linalg.solve(old,n4)
        bridge=np.diag(1/nx)@np.linalg.inv(old)@np.diag(n4)
        hh,ww=d['u'].shape
        yy,xx=np.mgrid[:hh,:ww]
        r2=(((xx+.5)*16-6192/2)**2+((yy+.5)*16-4128/2)**2)/((6192/2)**2+(4128/2)**2)
        gain=np.exp(-(radial[0]*r2+radial[1]*r2**2+radial[2]*r2**3))
        x=d['wb']*gain[...,None]@bridge.T*(320/.0853)
        select=((r2<=.85**2)&(d['ucv']<.04)&(d['rawmax']<.97)&~d['rawclip']
                &(d['jpeg'].mean(axis=-1)>3)&(d['jpeg'].mean(axis=-1)<250)
                &np.all((x>0)&(x<4095),axis=-1))
        pred=E.fs.lab_from_codes(E.predict('03',x[select]))
        observed=E.fs.lab_from_codes(d['jpeg'][select])
        out[key]=b.stats(E.fs.delta_e00(pred,observed))
    out['is_independent_validation']=False
    out['scope']='same two GR IV images already defining current03; absolute consistency only'
    b.dump(b.LOCAL/'consistency03.json',out)
    print('03',out)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('baseline','03'))
    a=parser.parse_args()
    baseline() if a.command=='baseline' else consistency03()
