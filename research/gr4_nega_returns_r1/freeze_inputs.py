#!/usr/bin/env python3
"""Freeze protected inputs; decisions.tsv belongs to the orchestrator."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
import argparse


def main(action):
    path = rt.LOCAL / 'protected_inputs.json'
    if action == 'freeze':
        assert not path.exists(), 'never reset a frozen input manifest'
        roots = [
            'research/gr4_dense_returns_r1', 'research/refit_50mm_r7',
            'research/mount_calib_r1', 'research/module_adapt', 'research/closed_loop',
            'research/gr4_modes', 'research/gr_pairs', 'research/gr_webpairs',
            'research/gr_hdfchart', 'research/gr4_positive', 'research/color_references',
            'research/gr_dense_reference', 'research/gr_incamera_dev',
            'research/contrib_gr_analysis', 'research/color_fit_v2',
            'research/chart_session_20261024/local/moire-review-v2/exchange-jpeg6/50mm',
            'research/stage2l_leica_0708/local/DEEPTBL_v6_leica.DAT',
            'captures/contrib/2026-10-25-gr4-wechat-nega-redo/extracted',
            'firmware/stage2l_switch', 'firmware/recipe_v1',
        ]
        paths = set()
        for name in roots:
            base = rt.ROOT / name
            assert base.exists(), name
            for p in (base.rglob('*') if base.is_dir() else [base]):
                if p.is_file() and not p.is_relative_to(rt.RETURNS) and '__pycache__' not in p.parts and p.name != 'decisions.tsv':
                    paths.add(p)
        old = rt.read(rt.ROOT/'research/gr4_dense_returns_r1/local/verification/final.json')
        for name, digest in old['inputs_sha256'].items():
            p = rt.ROOT / name
            assert rt.sha(p) == digest, ('protected input already differs from Positive receipt', name)
            paths.add(p)
        for base in ('artifacts/firmware/gxr-1.51', 'artifacts/downloads/bastibe-gr3'):
            paths.update(p for p in (rt.ROOT/base).rglob('*') if p.is_file())
        values = {str(p.relative_to(rt.ROOT)): rt.sha(p) for p in sorted(paths)}
        assert 'decisions.tsv' not in values
        rt.dump(path, dict(sha256=values, excluded=['decisions.tsv'], protected_roots=roots))
        print('frozen protected files', len(values), flush=True)
    else:
        values = rt.read(path)['sha256']
        changed = [name for name, digest in values.items() if not (rt.ROOT/name).is_file() or rt.sha(rt.ROOT/name) != digest]
        rt.dump('verification/protected_check.json', dict(passed=not changed, files=len(values), changed=changed, decisions_tsv_excluded=True))
        assert not changed, ('STOP: protected inputs changed', changed)
        print('protected inputs unchanged', len(values), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['freeze', 'check'])
    main(ap.parse_args().action)
