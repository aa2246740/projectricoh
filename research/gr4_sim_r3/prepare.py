"""Freeze read-only inputs and retain r1's exact sample support."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np


def main():
    old = 'research/gr4_analytic_target_r1'
    for name in ('SHA256SUMS', 'data.py', 'simulator.py', 'validate.py', 'diagnose.py', 'PROVENANCE.md', 'protocol.json'):
        rt.inp(old + '/' + name)
    checks = []
    for line in rt.inp(old + '/SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        rt.inp(old + '/' + name.strip().lstrip('*'), digest)
        checks.append(name)
    ledger = rt.read(old + '/local/inputs.json')
    for name in ('dense.npz', 'dense_audit.json', 'natural.npz', 'natural_audit.json',
                 'natural_modes.npz', 'natural_modes_audit.json', 'calibration/primary_pre_hard.json'):
        path = old + '/local/' + name
        rt.inp(path)
    a = rt.arrays(old + '/local/dense.npz')
    audit = rt.read(old + '/local/dense_audit.json')
    xy = np.empty((len(a['band']), 2))
    spatial_checks = []
    for row in audit:
        card = rt.read(row['card_manifest'], ledger[row['card_manifest']])
        rt.inp(card['dng_path'], row['dng_sha256'])
        patches = {p['id']: p for p in card['patches']}
        w, h = row['geometry']['crop_wh']
        scale = np.hypot(w / 2, h / 2)
        for i in np.flatnonzero(a['band'] == row['band']):
            x1, y1, x2, y2 = patches[a['id'][i]]['roi']
            xy[i] = [((x1 + x2) / 2 - w / 2) / scale, ((y1 + y2) / 2 - h / 2) / scale]
        error = abs(np.linalg.norm(xy[a['band'] == row['band']], axis=1) - a['radius'][a['band'] == row['band']]).max()
        spatial_checks.append(dict(page=row['band'], maximum_radius_difference=float(error)))
        assert error < 1e-10
        for p in row['mode_paths'].values():
            key = str(Path(p).relative_to(rt.ROOT)) if Path(p).is_absolute() else p
            rt.inp(p, ledger.get(key))
    a['xy'] = xy
    np.savez_compressed(rt.LOCAL / 'dense.npz', **a)
    for name in ('natural_audit.json', 'natural_modes_audit.json'):
        for row in rt.read(old + '/local/' + name):
            key = row.get('path')
            if key: rt.inp(key, row['source_dng_sha256'])
    rt.dump('prepare.json', dict(evidence='对真实 GR IV 照片的验证', inherited_source_checks=len(checks),
        dense_rows=len(a['band']), training_standard=int(((a['band'] < 4) & a['standard_valid']).sum()),
        spatial_checks=spatial_checks, observation_arrays_reused_without_color_correction=True,
        training_modes=['standard'], training_pages=[1, 2, 3], held_pages=[4],
        new_sample_role='all three whole-photo holdout'))
    print('Read-only input checks OK; sample support fixed.', flush=True)


if __name__ == '__main__': main()
