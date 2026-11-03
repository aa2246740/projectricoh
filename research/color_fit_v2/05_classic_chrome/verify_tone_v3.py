#!/usr/bin/env python3
"""Independently check the exact v3 curve against the original phase-2 maths."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import json
from pathlib import Path
import signal

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('chrome_v3_tone_verify',HERE/'fit_v3.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
m = v.m
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('90 second tone check bound')))
signal.alarm(90)
d = v.read(v.LOCAL/'evaluation.json')
fit = v.read(m.LOCAL/'fit_v3.json')
ref = v.read(m.LOCAL/'fit.json')
S,T,_,_,_,_ = v.r3.setup('iso200',np.array(ref['input_gains'][m.fs.BASE_STEM]))
original = T.lut.ff
f = d['curve']['f']
rho = .18*np.maximum(np.arange(4096)/4095-f,0)/(v.UM-f)
ideal = original.rec709_luma(original.to_srgb_from_lut(
    original.neutral_codes(T.lut.cube('classic_chrome'),rho),'passthrough'))*255
a,b = v.src.Sources.curve(None,fit['curve'],'05-v3')[0]
A,B = v.src.unpack_tone(a,b)
curve = m.mm.Curve.from_rows(A,B)
pred = curve(np.arange(4096))
error = pred-ideal
rmse = float(np.sqrt(np.mean(error**2)))
maximum = float(np.max(abs(error)))
assert abs(rmse-d['curve']['chosen']['rmse'])<1e-12
assert abs(maximum-d['curve']['chosen']['max_abs'])<1e-12
assert np.all(np.diff(A)>0) and np.all(np.diff(B)>=0)
assert all(1<=x<=4094 for x in A) and all(0<=x<=255 for x in B)
changed = int(np.sum(np.array(A)!=S.curves['chrome'].xs[1:-1]))
delta = pred-S.curves['chrome'](np.arange(4096))
assert changed>0 and float(np.ptp(delta))>1
assert fit['colour_words']==ref['colour_words']
assert all(fit[key]['words_u16']==ref[key]['words_u16'] for key in ('matrix_row1','matrix_row2'))
copy_sha = m.sha(HERE/'phase2_fit_fuji_v3.py')
original_sha = m.sha(m.ROOT/'research/fuji_phase2/fit_fuji.py')
assert copy_sha==original_sha
mid_target = float(original.rec709_luma(original.neutral_codes(
    T.lut.cube('classic_chrome'),np.array([.18])))[0]*255)
assert abs(float(curve(v.UM*4095))-mid_target)<=maximum+.02
proof = {'phase2_copy_sha256':copy_sha,'phase2_original_sha256':original_sha,
         'curve_rmse_codes':rmse,'curve_max_error_codes':maximum,'changed_input_knots':changed,
         'uniform_output_offset':False,'delta_code_range':[float(delta.min()),float(delta.max())],
         'a5_bytes':len(a),'b5_bytes':len(b),'curve_and_colour_readback_pass':True}
m.dump(v.LOCAL/'tone_independent_check.json',proof)
print('PASS original phase2 maths, 4096 codes, exact rows, relocated knots, unchanged v2 colour')
