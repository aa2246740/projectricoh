"""Check that 1530/1531/1533 share exposure: mean RAW levels (uncompressed GXR DNG) over the aligned overlap."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
import struct

TYPES = {1: 'B', 3: 'H', 4: 'I', 5: 'II', 7: 'B', 9: 'i', 10: 'ii', 12: 'd'}


def ifd(buf, off, e):
    n = struct.unpack_from(e + 'H', buf, off)[0]; out = {}
    for i in range(n):
        tag, typ, cnt, val = struct.unpack_from(e + 'HHII', buf, off + 2 + 12 * i)
        fmt = TYPES.get(typ, 'B'); size = struct.calcsize(e + fmt) * cnt
        pos = off + 2 + 12 * i + 8 if size <= 4 else val
        vals = struct.unpack_from(e + fmt * cnt, buf, pos)
        if typ in (5, 10):
            vals = tuple(vals[j] / (vals[j + 1] or 1) for j in range(0, len(vals), 2))
        out[tag] = vals
    return out


def raw(path):
    buf = Path(path).read_bytes(); e = '<' if buf[:2] == b'II' else '>'
    root = ifd(buf, struct.unpack_from(e + 'I', buf, 4)[0], e)
    for sub in root[330]:
        t = ifd(buf, sub, e)
        if t.get(254, (1,))[0] == 0:
            break
    W, H, bps = t[256][0], t[257][0], t[258][0]
    assert t[259][0] == 1, 'compressed'
    off = t[273][0]; data = np.frombuffer(buf, np.uint8, count=sum(t[279]), offset=off)
    if bps == 16:
        img = data.view(e.replace('<', '<').replace('>', '>') + 'u2' if False else ('<u2' if e == '<' else '>u2')).reshape(H, W)
    elif bps == 12:
        d = data[:W * H * 3 // 2].reshape(-1, 3).astype(np.uint16)
        a = (d[:, 0] << 4) | (d[:, 1] >> 4); b = ((d[:, 1] & 15) << 8) | d[:, 2]
        img = np.stack([a, b], 1).reshape(H, W)
    else:
        raise ValueError(bps)
    return img, dict(W=W, H=H, bps=bps, black=t.get(50714), white=t.get(50717), cfa=t.get(33422))


def main():
    out = {}
    for f in ('R8051530', 'R8051531', 'R8051533'):
        img, meta = raw(ROOT / f'captures/street-g137-20261031/dng/{f}.DNG')
        H, W = img.shape
        g = (img[0::2, 1::2].astype(float) + img[1::2, 0::2]) / 2  # green sites (pattern-agnostic average of two diagonals)
        c = g[H // 2 // 4: H // 2 * 3 // 4, W // 2 // 4: W // 2 * 3 // 4]
        out[f] = dict(meta={k: (list(v) if isinstance(v, tuple) else v) for k, v in meta.items()},
                      mean_all=float(g.mean()), median_all=float(np.median(g)), mean_centre=float(c.mean()),
                      p99=float(np.percentile(g, 99)))
        print(f, out[f], flush=True)
    from scipy import ndimage
    al = json.loads((LOCAL / 'render/alignment.json').read_text())['frames']
    grids = {}
    for f in out:
        img, _ = raw(ROOT / f'captures/street-g137-20261031/dng/{f}.DNG')
        g = (img[0::2, 1::2].astype(float) + img[1::2, 0::2]) / 2
        h, w = g.shape[0] // 2 * 2, g.shape[1] // 2 * 2
        grids[f] = g[:h, :w].reshape(h // 2, 2, w // 2, 2).mean((1, 3))
    for slot, f in (('01', 'R8051530'), ('02', 'R8051531')):
        a = al[slot]
        m = ndimage.affine_transform(grids['R8051533'], [a['scale']] * 2, offset=[a['ty'], a['tx']], order=1, cval=np.nan)
        ref = grids[f][:m.shape[0], :m.shape[1]]; m = m[:ref.shape[0], :ref.shape[1]]
        ok = np.isfinite(m) & (m > 50) & (ref > 50) & (m < 3800) & (ref < 3800)
        r = np.log2(ref[ok] / m[ok])
        out[f]['EV_vs_1533_aligned_overlap'] = dict(median=float(np.median(r)), iqr=[float(np.percentile(r, 25)), float(np.percentile(r, 75))], n=int(ok.sum()))
        out[f]['raw_grid_shape'] = list(ref.shape)
    dump(LOCAL / 'rawcheck.json', out)
    print({f: out[f].get('EV_vs_1533_aligned_overlap') for f in out})


if __name__ == '__main__':
    main()
