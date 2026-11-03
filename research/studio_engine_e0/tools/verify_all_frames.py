"""Check ALL 5664 frames of the original previews.py run against the studio engine.

    studio/.venv/bin/python -I research/studio_engine_e0/tools/verify_all_frames.py

For every (unit, slot, param, level, scene) in research/knobs_v2_r2/local/preview_frames.json (CPython 3.9 /
numpy 1.26.4 run of 2026-10-28): rebuild the 552 B entry with studio's menu + knobs from the g127 DAT, compare its
sha256 with the recorded one, predict the scene with the studio Model and compare sha256 of the quantised RGB bytes.
Result: research/studio_engine_e0/local/verify_all_frames.json (ignored directory) and one summary line.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'studio/src'))
sys.path.insert(0, str(ROOT / 'studio/tests'))
import e0_support as t  # noqa: E402
from gxr_studio.camdata import calib, datcodec, store  # noqa: E402
from gxr_studio.engine import knobs, menu  # noqa: E402


def main():
    import tempfile

    home = Path(tempfile.mkdtemp(prefix='e0-home-'))
    store.import_from_dat(t.fixture_dat(127), home)
    calib.import_calibration(home, calib.dev_sources(ROOT))
    model, _ = calib.model_for(home, 200)
    data = menu.load()
    frames = json.loads((ROOT / 'research/knobs_v2_r2/local/preview_frames.json').read_text())
    scenes = {}
    for s in t.SCENES:
        with np.load(t.SCENE_DIR / f'{s}_input.npz', allow_pickle=False) as z:
            scenes[s] = z['x'].copy()
    start, bad_entry, bad_rgb = time.time(), [], []
    for n, f in enumerate(frames):
        unit, slot = datcodec.NAMES.index(f['unit']), f['slot']
        r = next(r for r in data['recipes'] if r['unit'] == unit and r['slot'] == slot)
        items = data['items'][r['first_item']:r['first_item'] + r['item_count']]
        levels = [i['default_level'] for i in items]
        idx = next(i for i, it in enumerate(items) if data['controls'][it['control']]['name'] == f['param'])
        levels[idx] = f['level']
        entry = knobs.apply(store.load_stock04(home, unit), store.load_entry(home, unit, slot),
                            menu.request(data, unit, slot, levels))[0]
        if hashlib.sha256(entry).hexdigest() != f['entry_sha256']:
            bad_entry.append(n)
        rgb = model.predict(entry, scenes[f['scene']], quantize=True)
        if hashlib.sha256(rgb.tobytes()).hexdigest() != f['display_RGB_sha256']:
            bad_rgb.append(n)
        if n % 500 == 0:
            print(n, f'{time.time() - start:.0f}s', flush=True)
    result = dict(frames=len(frames), entry_mismatches=len(bad_entry), rgb_mismatches=len(bad_rgb),
                  first_bad_rgb=bad_rgb[:20], seconds=round(time.time() - start),
                  numpy=np.__version__, python=sys.version.split()[0])
    (ROOT / 'research/studio_engine_e0/local/verify_all_frames.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
