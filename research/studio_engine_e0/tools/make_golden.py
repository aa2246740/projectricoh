"""Write the hash-only golden lists used by studio/tests (no Ricoh bytes: only digests).

    studio/.venv/bin/python -I research/studio_engine_e0/tools/make_golden.py

1. studio/tests/golden/knobs_cases.json — digest of (entry || stats) for every case in tests/e0_support.knob_cases,
   computed by the RESEARCH knobs.py / menu.py (loaded by file path) on the entries of the g127 DAT.
2. studio/tests/golden/render_frames.json — every 10th frame of knobs_v2_r2/local/preview_frames.json, the table
   that the original previews.py run (CPython 3.9 / numpy 1.26.4, 2026-10-28) left behind: entry sha256 and the sha256
   of the quantised RGB bytes per (unit, slot, param, level, scene). Copied as-is, not recomputed.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'studio/src'))
sys.path.insert(0, str(ROOT / 'studio/tests'))
import e0_support as t  # noqa: E402
from gxr_studio.camdata import datcodec  # noqa: E402


def main():
    raw = t.fixture_dat(127)
    if raw is None:
        raise SystemExit('g127 fixture DAT not found / hash differs')
    dat = datcodec.parse(raw)
    knobs, menu = t.research_knobs_and_menu()
    data = menu.load()
    cases = t.knob_cases(data)
    digests, errors = {}, 0
    for c in cases:
        stock, base = dat.entry_of(c['unit'], 4), dat.entry_of(c['unit'], c['slot'])
        out = t.run_case(knobs, menu, data, c, stock, base)
        errors += out[0] == 'error'
        digests[c['id']] = t.outcome_digest(out)
    sources = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
               ('research/knobs_v2_r2/src/knobs.py', 'research/knobs_v2_r2/src/menu.py',
                'research/knobs_v2_r2/tables/final.json')}
    t.GOLDEN.mkdir(exist_ok=True)
    (t.GOLDEN / 'knobs_cases.json').write_text(json.dumps(
        {'schema': 'gxr-studio/golden-knobs/1', 'dat_generation': 127, 'dat_sha256': t.FIXTURE_SHA256[127],
         'sources': sources, 'cases': len(cases), 'error_cases': errors, 'digests': digests},
        indent=0, sort_keys=True) + '\n')
    print('knobs golden:', len(cases), 'cases,', errors, 'expected errors')

    frames = json.loads((ROOT / 'research/knobs_v2_r2/local/preview_frames.json').read_text())
    keep = [{k: f[k] for k in ('unit', 'slot', 'param', 'level', 'scene', 'entry_sha256', 'display_RGB_sha256')}
            for f in frames[::10]]
    (t.GOLDEN / 'render_frames.json').write_text(json.dumps(
        {'schema': 'gxr-studio/golden-render/1', 'origin': 'research/knobs_v2_r2/local/preview_frames.json '
         '(CPython 3.9.6, numpy 1.26.4, 2026-10-28), every 10th of 5664 frames',
         'source_sha256': hashlib.sha256((ROOT / 'research/knobs_v2_r2/local/preview_frames.json').read_bytes()).hexdigest(),
         'frames': keep}, indent=0) + '\n')
    print('render golden:', len(keep), 'frames')


if __name__ == '__main__':
    main()
