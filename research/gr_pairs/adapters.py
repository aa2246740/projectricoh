"""Target-only adapters. Never create or upgrade a GXR camera measurement."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as own
from common import ROOT, LOCAL, read, dump, load, guard
from targets import round5, Transfer
import argparse
import json
import numpy as np


def round5_data(group, slot, iso=200):
    """Return the existing Data interface with three compatible auxiliary arrays."""
    g = round5()
    data = g.Data(slot, iso)
    with np.load(LOCAL / 'targets' / f'{group}_{slot}_200.npz', allow_pickle=False) as z:
        target = dict(z)
    data.generated = target
    data.generated['aux_x'] = target['input_x'] / data.a['exposure']
    assert data.generated['aux_target'].shape == data.generated['aux_x'].shape
    assert data.generated['aux_weights'].shape == (len(data.generated['aux_x']),)
    return data


def hook(group, request_path, measurement_path, output, physical_model_iso=None):
    """Read actual closed_loop requests and bind targets to their unchanged hashes."""
    requests, measurement = read(request_path), read(measurement_path)
    assert requests['schema'] == 'closedloop-target-requests/1'
    assert measurement['schema'] == 'closedloop-measurement/1'
    frames = {f['id']: f for f in measurement['frames']}
    g = round5()
    generator = g.GRGenerator(ROOT / 'artifacts/downloads/bastibe-gr3')
    transfers = {s: Transfer(group, 'positive' if s == '01' else 'negative', g, generator) for s in ('01', '02')}
    cc = load('pairs_closedloop_common', ROOT / 'research/closed_loop/common.py')
    # The existing package uses an unqualified `common` import. Bind it only while
    # loading/constructing its read-only Engine, then restore our own namespace.
    prior = sys.modules.get('common')
    try:
        sys.modules['common'] = cc
        model = load('pairs_closedloop_model', ROOT / 'research/closed_loop/model.py')
        engines, out = {}, {}
        for q in requests['frames']:
            slot = q['slot']
            if slot not in transfers:
                continue
            f = frames[q['id']]
            assert q['dng_sha256'] == f['hashes']['DNG']
            assert q['labels'] == [p['label'] for p in f['patches']]
            for key in ('input_x', 'raw_wb', 'xyz_camera'):
                assert np.array_equal(q[key], f[key]), 'Request must match actual measured inputs'
            iso = f['meta']['iso']
            if iso == 800:
                assert physical_model_iso in (200, 1600), 'ISO800 needs an explicit existing calibration-model proxy'
                iso = physical_model_iso
            assert iso in (200, 1600)
            key = (f['model']['table'], iso)
            if key not in engines:
                engines[key] = model.Engine(*key)
            engine = engines[key]
            x = np.asarray(q['input_x'], float)
            rows, valid = {}, np.ones(len(x), bool)
            for ev in (-.3, 0., .3):
                xx = x * 2 ** ev
                standard, styled, ms, ss, conf = transfers[slot].labs(xx)
                from targets import apply_relative
                rows[f'{ev:+.1f}'] = apply_relative(engine.fs.lab_from_codes(engine.predict('04', xx)), standard, styled)
                valid &= ms & ss & (conf >= .9)
            out[q['key']] = {'slot': slot, 'dng_sha256': q['dng_sha256'], 'labels': q['labels'],
                'lab': rows['+0.0'], 'anchor_lab': {e: rows[e] for e in ('-0.3', '+0.3')},
                'source': f'gr_pairs {group}: camera RAW/JPEG functions; common-white ColorMatrix bridge; declared 118 anchor',
                'unsupported_patches': np.flatnonzero(~valid), 'reference_grade': 'surrogate',
                'metering_anchor_determined': False, 'camera_output': False,
                'physical_model_iso_proxy': physical_model_iso if f['meta']['iso'] == 800 else None}
    finally:
        if prior is None:
            sys.modules.pop('common', None)
        else:
            sys.modules['common'] = prior
    result = {'schema': 'closedloop-targets/1', 'frames': out, 'accepted': False,
              'firmware_ready': False, 'metering_anchor_determined': False,
              'changes_measurement_eligibility': False, 'target_only': True}
    dump(output, result)
    print(json.dumps({'frames': len(out), 'unsupported': sum(len(v['unsupported_patches']) for v in out.values()),
                      'schema': result['schema'], 'target_only': True}), flush=True)


def main():
    guard()
    p = argparse.ArgumentParser()
    p.add_argument('--group', choices=['gr3', 'gr4_hdf'], required=True)
    p.add_argument('--requests', required=True)
    p.add_argument('--measurement', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--physical-model-iso', type=int, choices=[200, 1600])
    a = p.parse_args()
    hook(a.group, a.requests, a.measurement, a.out, a.physical_model_iso)


if __name__ == '__main__':
    main()
