"""Memory-only reproduction. Exit 1 means the misaligned pair was accepted."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'studio/src'), str(ROOT / 'studio/tests')]
import hdr_support as hs
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

first = hs.scene(seed=0)
second = first.copy()
first[96:136, 420:460] = 0.035
second[96:136, 500:540] = 0.035
jpeg = hs.camera_jpeg(second)
raw = g.raw_luma(open_dng(hs.camera_dng(first)))
try:
    data, stats = g.hdr_from_camera_jpeg(jpeg, raw)
except g.HdrUnsupported as error:
    print(json.dumps({'rejected': True, 'reason': error.reason}))
    raise SystemExit(0)
print(json.dumps({'rejected': False, 'alignment': stats['alignment'], 'hdr_bytes': len(data)}))
raise SystemExit(1)
