"""Render final recipe assignments and repaired Mount quality flags on source JPEGs."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image
import session_runtime as s


def render(out, frames, analyzer, scores, stability):
    for f in frames:
        with Image.open(f['paths']['jpeg']) as im:
            rgb = np.asarray(im.convert('RGB'))
        analyzer.overlay(rgb, f['patches'], f"{f['frame']} {f['kind']} page={f['page']} slot={f.get('slot')} {f['purpose']}",
                         out / 'overlays' / (f['frame'] + '.jpg'))
    analyzer.write_quality_html(out, frames, [], scores, stability)


def main():
    out = s.LOCAL / 'analysis-final'
    a, _, _ = s.setup(s.LOCAL / 'extraction', freeze=False)
    frames = [json.loads(p.read_text()) for p in sorted((out / 'frames').glob('*.json'))]
    render(out, frames, a, json.loads((out / 'scores_C/scores.json').read_text()),
           json.loads((out / 'stability.json').read_text()))
    print('Final overlays and self-contained quality.html rendered for 51 accepted frames.')


if __name__ == '__main__':
    main()
