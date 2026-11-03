#!/usr/bin/env python3
"""For stocks whose default medium is the screen (Digital Reference): how far the app's default
Auto Levels render of a photo sits from the fixed-timing LUT. Low-passed 8x8 so sharpness and
edge effects drop out and the per-frame re-timing remains. CLI runs only in the sandbox."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from common import CUBES, LOCAL, WORK, apply_lut, de00, decode_image, dump, fotufilm, lab, p3_to_srgb_codes, \
    read_cube_table, stats
from bake import FLAGS, FULL, load_photos, lowpass, r3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard', default='0/1')
    args = ap.parse_args()
    k, m = map(int, args.shard.split('/'))
    rows = []
    for p in sorted(LOCAL.glob('bake_*of*.json')):
        rows += [r for r in json.loads(p.read_text()) if r.get('success')]
    rows = sorted((r for r in rows if r['medium'] == 'screen' and not r['reflection_print']), key=lambda r: r['id'])
    rows = rows[k::m]
    _, full = load_photos(f'al_{k}.u16')
    flags = [f if f != 'reference-exposure' else 'auto-levels' for f in FLAGS]
    out = LOCAL / f'autolevels_{k}of{m}.json'
    res = []
    for r in rows:
        sid = r['id']
        T = read_cube_table(CUBES / r['cubes']['srgb'])
        photos = {}
        for n in FULL:
            h, w, _ = full[n].shape
            fotufilm([WORK / f'full_{n}.png', WORK / f'al_{sid}.png', '--stock', sid, *flags])
            a, _ = decode_image(WORK / f'al_{sid}.png', WORK / f'al_{sid}.u16')
            a = p3_to_srgb_codes(a.reshape(-1, 3)).reshape(h, w, 3)
            ls = apply_lut(T, full[n].reshape(-1, 3)).reshape(h, w, 3)
            photos[n] = r3(stats(de00(lab(lowpass(a)), lab(lowpass(ls)))))
            for f in WORK.glob(f'al_{sid}.*'):
                f.unlink()
        res.append({'id': sid, 'photos': photos, 'flags': flags})
        print(sid, photos, flush=True)
        dump(out, res)


if __name__ == '__main__':
    main()
