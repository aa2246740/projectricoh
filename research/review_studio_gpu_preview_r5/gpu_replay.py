"""Prepare/check original GPU fixtures in separate processes to keep the limit at two."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import environment, SOURCE, OUT

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('phase', choices=['prepare', 'check'])
parser.add_argument('case', choices=['r2-colour', 'r4-colour', 'current-colour'])
args = parser.parse_args()
fixture, result = environment(args.case, reuse=args.phase == 'check')
sys.path.insert(0, str(SOURCE/'tests'))
import numpy as np
import gpu_support


class Prepared(BaseException):
    pass


def stage(tmp_path, files, cases, timeout=180):
    fingerprints = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    if args.phase == 'prepare':
        browser = fixture/'browser'
        browser.mkdir()
        paths = {}
        for i, (name, data) in enumerate(files.items()):
            path = browser/f'input-{i}.bin'
            path.write_bytes(data)
            paths[name] = str(path)
        (browser/'files.json').write_text(json.dumps(paths)+'\n')
        (browser/'cases.json').write_text(json.dumps(cases)+'\n')
        (result/'gpu-inputs.json').write_text(json.dumps({'file_sha256': fingerprints, 'cases': cases}, indent=2)+'\n')
        raise Prepared()
    assert json.loads((result/'gpu-inputs.json').read_text()) == {'file_sha256': fingerprints, 'cases': cases}
    data = json.loads((fixture/'browser'/'gpu-result.json').read_text())
    assert 'error' not in data['summary'], data['summary']
    images = {}
    for cid, image in data['images'].items():
        raw = Path(image['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == image['sha256']
        images[cid] = np.frombuffer(raw, np.uint8).reshape(image['h'], image['w'], 4)[..., :3].copy()
    return images, data['summary']


gpu_support.run_engine = stage
if args.case == 'current-colour':
    import test_gpu_parity as parity
    directory = fixture/'parity'
    directory.mkdir(exist_ok=True)
    fn = getattr(parity.parity, '__wrapped__', None) or parity.parity._fixture_function
    try:
        values = fn(SimpleNamespace(mktemp=lambda name: directory))
    except Prepared:
        assert args.phase == 'prepare'
        print(json.dumps({'case': args.case, 'phase': args.phase, 'prepared': True}))
    else:
        assert args.phase == 'check'
        rows = []
        out, refs, summary, masks, display = values
        for cid in parity.CASES:
            parity.test_gpu_matches_python(values, cid)
            measured = parity.evaluate(out[cid], refs[cid], mask=masks[cid], frozen=parity.FROZEN.get(cid), display_lut=display[cid])
            rows.append({'id': cid, **{k: v for k, v in measured.items() if k != 'over_2_out_band'}})
        parity.test_gpu_parity_ran_on_a_real_adapter(values)
        (result/'colour-results.json').write_text(json.dumps({'rows': rows, 'summary': summary, 'passed': 14}, indent=2)+'\n')
        print(json.dumps({'case': args.case, 'phase': args.phase, 'passed': 14}))
else:
    previous = Path(__file__).resolve().parent.parent/('review_studio_gpu_preview_r2' if args.case.startswith('r2') else 'review_studio_gpu_preview_r4')/'synthetic_lut_counterexample.py'
    text = previous.read_text()
    text = text.replace("WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')", f'WT=Path({str(SOURCE)!r})')
    text = text.replace("TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2')", f'TEMP=Path({str(fixture)!r})')
    text = text.replace("TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4')", f'TEMP=Path({str(fixture)!r})')
    text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4/source', str(SOURCE))
    text = text.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4/r2-gpu-colour', str(fixture/'legacy'))
    text = text.replace('TEMP.mkdir()', 'TEMP.mkdir(exist_ok=True)')
    text = text.replace("(TEMP/'synthetic-parity').mkdir()", "(TEMP/'synthetic-parity').mkdir(exist_ok=True)")
    script = result/previous.name
    if args.phase == 'prepare':
        script.write_text(text)
        (result/'adaptation.diff').write_text(''.join(difflib.unified_diff(previous.read_text().splitlines(True), text.splitlines(True), fromfile=str(previous), tofile=str(script))))
        (result/'input.json').write_text(json.dumps({'original': str(previous), 'original_sha256': hashlib.sha256(previous.read_bytes()).hexdigest(), 'adapted_sha256': hashlib.sha256(text.encode()).hexdigest()}, indent=2)+'\n')
    else:
        assert script.read_text() == text
    sys.argv = [str(script), 'swiftshader']
    try:
        exec(compile(text, str(script), 'exec'), {'__file__': str(script), '__name__': '__main__'})
    except Prepared:
        assert args.phase == 'prepare'
        print(json.dumps({'case': args.case, 'phase': args.phase, 'prepared': True}))
    except SystemExit as exc:
        assert args.phase == 'check' and exc.code == 0
        print(json.dumps({'case': args.case, 'phase': args.phase, 'passed': True}))
