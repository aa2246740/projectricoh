"""Freeze the consumed research and all supplied original photo corpora."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from collections import Counter
import json

SOURCES = [
    'captures/contrib/2026-10-25-gr4-wechat',
    'captures/contrib/2026-10-25-gr4-wechat-nega-redo',
    'captures/contrib/2026-10-22-gr4hdf-screenchart',
    'captures/contrib/2026-10-21-webpairs',
    'captures/contrib/2026-10-21-evalsets',
    'captures/contrib/2026-10-19',
    'captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473',
    'captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228',
    'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root/DCIM/100RICOH',
    'research/gr4_dense_returns_r1', 'research/gr4_nega_returns_r1',
    'research/refit_50mm_r7', 'research/body_lut', 'research/gr_dense_reference',
    'research/capability_ladder', 'research/channel_mixing', 'research/color_table_fit',
    'research/beyond24', 'research/lut_convert', 'research/gr_webpairs',
    'research/gr_pairs', 'research/gr_hdfchart', 'research/calibration_20261020',
    'research/chart_session_20261024', 'research/chart_v2',
]


def main():
    manifest = rt.LOCAL / 'inputs.json'
    state = json.loads(manifest.read_text()) if manifest.exists() else {}
    inventory = []
    for folder in SOURCES:
        root = rt.ROOT / folder
        files = sorted(p for p in root.rglob('*') if p.is_file() and not p.is_symlink()
                       and p.name != 'decisions.tsv' and '__pycache__' not in p.parts
                       and '.DS_Store' != p.name)
        nbytes = 0
        for path in files:
            key = str(path.relative_to(rt.ROOT))
            value = rt.sha(path)
            assert key not in state or state[key] == value, 'FROZEN INPUT CHANGED: ' + key
            state[key] = value
            nbytes += path.stat().st_size
        inventory.append(dict(folder=folder, files=len(files), bytes=nbytes,
                              extensions=dict(Counter(p.suffix.lower() for p in files))))
        print(folder, len(files), round(nbytes/1e6), 'MB', flush=True)
    rt.dump('inputs.json', state)
    rt.dump('inventory.json', inventory)
    rt.dump('preflight.json', dict(python=sys.executable, version=sys.version,
                                  write_root=rt.HERE, no_network=True, camera=False,
                                  builds=False, decisions_tsv_excluded=True,
                                  frozen_files=len(state)))
    print('frozen', len(state), flush=True)


if __name__ == '__main__':
    main()
