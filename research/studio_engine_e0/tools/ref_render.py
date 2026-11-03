"""Reference runner: the research code itself (knobs.py + model_adapter.Model via closed_loop Engine).

Runs in its own process so the research modules (names `knobs`, `menu`, `model`, `support`, ...) and their
side effects (support.dependencies() edits sys.path / env) never leak into the studio test process.

    <python> ref_render.py CASES.json OUT.npz [--repo ROOT]

CASES.json: {"entries": {"<unit>/<slot>": "<hex of 552 B>"},
             "cases": [{"id": str, "scene": "desk|neutral|apple|redblue", "unit": int, "slot": int,
                        "request": {"amount": int, "doses": [10 ints], "wb_method": 0|1, "tone_method": 0|1} | null,
                        "iso": 200 | 1600}]}
OUT.npz: for every case id: entry_<id> (552 uint8) and rgb_<id> (uint8 N x 3, quantised prediction).
The reference never opens a card or the network; it reads only repo files (see CLOSURE.md).
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def main():
    cases_path, out_path = sys.argv[1], sys.argv[2]
    root = Path(sys.argv[sys.argv.index('--repo') + 1]) if '--repo' in sys.argv else Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'research/knobs_v2_r2/src'))
    import knobs as k            # research
    import model_adapter         # research; its support.dependencies() makes numpy importable on CPython 3.9
    import numpy as np
    spec = json.loads(Path(cases_path).read_text())
    entries = {key: bytes.fromhex(v) for key, v in spec['entries'].items()}
    scenes = {}
    models = {}
    out = {}
    for case in spec['cases']:
        iso = case.get('iso', 200)
        if iso not in models:
            if iso == 200:
                m = model_adapter.Model()      # exactly what previews.py builds
            else:                              # same constructor with the ISO 1600 calibration (Engine(iso=1600))
                m = model_adapter.Model.__new__(model_adapter.Model)
                sys.path.insert(0, str(root / 'research/closed_loop'))
                from model import Engine      # closed_loop/model.py
                m.engine = Engine(model_adapter.OLD_TABLE, iso=iso)
                m.mm, m.fs = m.engine.mm, m.engine.fs
                m.used = {}
            models[iso] = m
        model = models[iso]
        if case['scene'] not in scenes:
            with np.load(root / 'research/knobs_v2_r2/local' / f"{case['scene']}_input.npz", allow_pickle=False) as z:
                scenes[case['scene']] = z['x'].copy()
        x = scenes[case['scene']]
        stock = entries[f"{case['unit']}/4"]
        base = entries[f"{case['unit']}/{case['slot']}"]
        r = case.get('request')
        if r is None:
            entry = base
        else:
            entry, _ = k.apply(stock, base, k.Request(r['amount'], tuple(r['doses']), r['wb_method'], r['tone_method']))
        out['entry_' + case['id']] = np.frombuffer(entry, dtype=np.uint8)
        out['rgb_' + case['id']] = model.predict(entry, x, quantize=True)
    np.savez(out_path, **out)
    print('ref_render done', len(spec['cases']), 'cases; numpy', np.__version__, 'python', sys.version.split()[0])


if __name__ == '__main__':
    main()
