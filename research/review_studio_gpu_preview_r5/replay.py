"""Serial independent replay against the frozen fifth-review source copy."""
import argparse
import contextlib
import difflib
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import traceback

BUNDLE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('REVIEW_R5_OUTPUT', str(BUNDLE)))
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5')
SOURCE = TMP / 'source'
OLD = BUNDLE.parent


def environment(label, reuse=False):
    assert SOURCE.is_dir()
    os.setpriority(os.PRIO_PROCESS, 0, max(10, os.getpriority(os.PRIO_PROCESS, 0)))
    for key in tuple(os.environ):
        if key.startswith(('GXR_', 'SENTRY_')):
            os.environ.pop(key)
    fixture = TMP / 'fixtures' / label
    fixture.mkdir(exist_ok=reuse)
    result = OUT / 'cases' / label
    result.mkdir(parents=True, exist_ok=reuse)
    os.environ.update(HOME=str(TMP / 'home'), TMPDIR=str(TMP / 'tmp'), TMP=str(TMP / 'tmp'),
                      TEMP=str(TMP / 'tmp'), XDG_CACHE_HOME=str(TMP / 'cache'),
                      XDG_CONFIG_HOME=str(TMP / 'config'), XDG_DATA_HOME=str(TMP / 'data'),
                      PYTHONDONTWRITEBYTECODE='1', REVIEW_SOURCE=str(SOURCE),
                      REVIEW_TMP=str(fixture), REVIEW_OUT=str(result),
                      OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                      VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    tempfile.tempdir = str(TMP / 'tmp')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SOURCE / 'src'))
    os.chdir(SOURCE)
    return fixture, result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case')
    a = p.parse_args()
    fixture, result = environment(a.case)
    previous = OLD / 'review_studio_gpu_preview_r4'
    args = []
    original = None
    if a.case.startswith('r2-') and a.case[3:] in ('media_root_race', 'path_delete_race', 'card_reader_retarget', 'lut_reimport_probe', 'http_boundary_extra'):
        previous = previous / 'replay_r2.py'
        text = previous.read_text().replace("OLD = BUNDLE.parent / 'review_studio_gpu_preview_r2'", f"OLD = Path({str(OLD / 'review_studio_gpu_preview_r2')!r})")
        args = [a.case[3:]]
    else:
        mapping = {
            'r3-extra': 'extra_boundaries.py', 'r3-loop': 'windows_loop_guard.py',
            'r3-contracts': 'windows_contracts.py', 'r4-extra': 'extra_boundaries.py',
            'r4-loop': 'windows_loop_guard.py', 'r4-contracts': 'windows_contracts.py',
            'r4-new-contracts': 'windows_new_contracts.py', 'r4-card-extra': 'additional_card_cases.py',
            'r4-dat-root': 'card_root_dat.py', 'r4-dat-variants': 'dat_root_variants.py',
            'r2-exhaustive': 'exhaustive_lut.py', 'r4-exhaustive': 'exhaustive_lut.py',
        }
        if a.case.startswith(('r4-old-runtime-', 'r4-ab-runtime-')):
            filename = 'runtime-old-probe-source.py' if a.case.startswith('r4-old') else 'runtime-ab-probe-source.py'
            args = [a.case.rsplit('-', 1)[1]]
        else:
            filename = mapping[a.case]
        if a.case == 'r2-exhaustive':
            previous = OLD / 'review_studio_gpu_preview_r2'
        previous = previous / filename
        text = previous.read_text()
        if a.case.startswith('r3-'):
            original = OLD / 'review_studio_gpu_preview_r3' / filename
        text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4/source/src', str(SOURCE / 'src'))
        if a.case == 'r4-dat-root':
            text = text.replace('assert response.status_code==422 and reads==[other]', 'assert response.status_code==409 and response.json()["error"]=="card_read_failed" and reads==[]')
        if a.case == 'r4-dat-variants':
            text = text.replace("else:assert response.status_code==422 and response.json()['error']=='dat_invalid' and read_other", "else:assert response.status_code==409 and response.json()['error']=='card_read_failed' and not reads")
    script = result / previous.name
    script.write_text(text)
    baseline = original or previous
    (result / 'adaptation.diff').write_text(''.join(difflib.unified_diff(baseline.read_text().splitlines(True), text.splitlines(True), fromfile=str(baseline), tofile=str(script))))
    (result / 'input.json').write_text(json.dumps({'original': str(baseline), 'original_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(), 'replay_source': str(previous), 'replay_source_sha256': hashlib.sha256(previous.read_bytes()).hexdigest(), 'adapted_sha256': hashlib.sha256(text.encode()).hexdigest()}, indent=2)+'\n')
    sys.argv = [str(script), *args]
    start = time.monotonic()
    error = None
    signal.alarm(300)
    try:
        with (result / 'stdout.log').open('w') as stdout, (result / 'stderr.log').open('w') as stderr, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                exec(compile(text, str(script), 'exec'), {'__file__': str(script), '__name__': '__main__'})
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        with (result / 'stderr.log').open('a') as stderr:
            traceback.print_exc(file=stderr)
    finally:
        signal.alarm(0)
    receipt = {'case': a.case, 'head': '652847c0ea570ba4bc1e5e635055e3a1543ec996', 'error': error, 'seconds': time.monotonic()-start, 'nice': os.getpriority(os.PRIO_PROCESS, 0), 'fixture': str(fixture)}
    (result / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
    return 1 if error else 0


if __name__ == '__main__':
    raise SystemExit(main())
