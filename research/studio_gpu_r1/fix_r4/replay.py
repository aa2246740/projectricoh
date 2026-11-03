"""Run one frozen review case with isolated output and an adaptation receipt."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent.parent
SOURCE = Path(os.environ['REVIEW_SOURCE'])
TMP = Path(os.environ['REVIEW_TMP'])
R2 = RESEARCH / 'review_studio_gpu_preview_r2'
R3 = RESEARCH / 'review_studio_gpu_preview_r3'
R4 = RESEARCH / 'review_studio_gpu_preview_r4'
R2_CASES = ['media_root_race', 'path_delete_race', 'card_reader_retarget', 'lut_reimport_probe', 'http_boundary_extra']
CASES = ['r2-' + name for name in R2_CASES] + [
    'r2-exhaustive', 'r2-colour', 'r3-extra', 'r3-loop', 'r3-contracts',
    'r4-dat-root', 'r4-dat-variants', 'r4-card-extra', 'r4-extra', 'r4-loop',
    'r4-contracts', 'r4-new-contracts', 'r4-exhaustive', 'r4-colour',
    'r4-original-extra',
] + [label + '-' + mode for label in ['r4-old-runtime', 'r4-ab-runtime']
     for mode in ['io', 'loop', 'matmul', 'inverse', 'lut']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=CASES)
    parser.add_argument('--run-name', default='')
    options = parser.parse_args()
    assert not options.run_name or re.fullmatch('[a-z0-9_-]+', options.run_name)
    case = options.case
    output = HERE / 'replays' / options.run_name / case
    output.mkdir(parents=True, exist_ok=False)
    os.environ['REVIEW_OUT'] = str(output)
    args = []
    if case.startswith('r2-') and case[3:] in R2_CASES:
        origin = R4 / 'replay_r2.py'
        args = [case[3:]]
    elif case.startswith('r3-'):
        origin = HERE.parent / 'fix_r3/replay.py'
        args = [case[3:]]
    elif case in ['r2-exhaustive', 'r2-colour']:
        origin = R2 / ('exhaustive_lut.py' if case.endswith('exhaustive') else 'synthetic_lut_counterexample.py')
    elif '-runtime-' in case:
        origin = R4 / ('runtime-old-probe-source.py' if case.startswith('r4-old') else 'runtime-ab-probe-source.py')
        args = [case.rsplit('-', 1)[1]]
    else:
        name = {
            'r4-dat-root': 'card_root_dat.py', 'r4-dat-variants': 'dat_root_variants.py',
            'r4-card-extra': 'additional_card_cases.py', 'r4-extra': 'extra_boundaries.py',
            'r4-loop': 'windows_loop_guard.py', 'r4-contracts': 'windows_contracts.py',
            'r4-new-contracts': 'windows_new_contracts.py', 'r4-exhaustive': 'exhaustive_lut.py',
            'r4-colour': 'synthetic_lut_counterexample.py', 'r4-original-extra': 'run_original.py',
        }[case]
        origin = R4 / name
        if case == 'r4-original-extra':
            args = ['extra_boundaries.py']
    original = origin.read_text()
    current = original
    if origin.name == 'replay_r2.py':
        current = current.replace("OLD = BUNDLE.parent / 'review_studio_gpu_preview_r2'", f'OLD = Path({str(R2)!r})')
    elif case.startswith('r3-'):
        current = current.replace('OUT = Path(__file__).resolve().parent', f'OUT = Path({str(output)!r})')
        current = current.replace("REVIEW = OUT.parent.parent / 'review_studio_gpu_preview_r3'", f'REVIEW = Path({str(R3)!r})')
    elif case == 'r4-original-extra':
        current = current.replace("prior=Path(__file__).resolve().parent.parent/'review_studio_gpu_preview_r3'/name", f'prior=Path({str(R3)!r})/name')
    elif case == 'r4-dat-root':
        old = 'assert response.status_code==422 and reads==[other]'
        assert old in current
        current = current.replace(old, 'assert response.status_code==409 and reads==[]')
    elif case == 'r4-dat-variants':
        old = "if mode=='root_link':assert response.status_code==409 and not reads\n  else:assert response.status_code==422 and response.json()['error']=='dat_invalid' and read_other"
        assert old in current
        current = current.replace(old, 'assert response.status_code==409 and not reads')
    if case in ['r2-exhaustive', 'r2-colour', 'r4-exhaustive', 'r4-colour']:
        current = current.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4/source', str(SOURCE))
        current = current.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4/r2-gpu-colour', str(TMP / 'r2-gpu-colour'))
        current = current.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2', str(TMP / 'r2-gpu-colour'))
        if case == 'r2-colour':
            (TMP / 'r2-gpu-colour/synthetic-parity').mkdir(parents=True)
    target = output / origin.name
    target.write_text(current)
    (output / 'adaptation.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), current.splitlines(True), fromfile=str(origin), tofile=str(target))))
    (output / 'input.json').write_text(json.dumps({
        'original': str(origin), 'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
        'replay_sha256': hashlib.sha256(current.encode()).hexdigest(),
        'purpose': 'Keep the original trigger; update paths, removed interfaces, and the fixed DAT result.',
    }, indent=2) + '\n')
    sys.argv = [str(target), *args]
    exec(compile(current, str(target), 'exec'), {'__file__': str(target), '__name__': '__main__'})


if __name__ == '__main__':
    main()
