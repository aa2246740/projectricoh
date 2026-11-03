"""Q1a: render today's GXR 04 frame with the frozen GR IV 17^3 software LUT and align it to the 01/02 frames."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from scipy import ndimage

SRC = ROOT / 'captures/street-g137-20261031/jpg'
LUT = ROOT / 'research/gr4_lut_ceiling/local/lut'
SCALE = 4


def small(a, k=SCALE):
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    return a[:h, :w].reshape(h // k, k, w // k, k, -1).mean((1, 3))


def edges(rgb):
    g = lab(rgb.reshape(-1, 3)).reshape(rgb.shape)[..., 0]
    g = ndimage.gaussian_filter(g, 1.0)
    m = np.hypot(ndimage.sobel(g, 0), ndimage.sobel(g, 1))
    return (m - m.mean()) / (m.std() + 1e-9)


def warp(img, s, ty, tx, order=1):
    # output(y,x) = input(s*y + ty, s*x + tx): maps reference grid to moving image
    out = [ndimage.affine_transform(img[..., c], [s, s], offset=[ty, tx], order=order, mode='constant', cval=np.nan)
           for c in range(img.shape[-1])]
    return np.stack(out, -1)


def align(ref_e, mov_e):
    best = None
    H, W = ref_e.shape
    win = np.hanning(H)[:, None] * np.hanning(W)[None]
    for s in np.arange(0.95, 1.0501, 0.005):
        m = ndimage.affine_transform(mov_e, [s, s], offset=[0, 0], order=1, mode='constant', cval=0)
        F = np.fft.fft2(ref_e * win) * np.conj(np.fft.fft2(m * win))
        r = np.real(np.fft.ifft2(F / (np.abs(F) + 1e-9)))
        y, x = np.unravel_index(np.argmax(r), r.shape)
        y = y - H if y > H // 2 else y
        x = x - W if x > W // 2 else x
        # shift found means ref(p) ~ m(p - d); offset for input coords: -d
        ty, tx = -float(y), -float(x)
        m2 = ndimage.affine_transform(mov_e, [s, s], offset=[ty, tx], order=1, mode='constant', cval=np.nan)
        ok = np.isfinite(m2)
        ncc = float(np.corrcoef(ref_e[ok], m2[ok])[0, 1])
        if best is None or ncc > best[0]:
            best = (ncc, s, ty, tx)
    ncc, s, ty, tx = best
    # sub-pixel refinement of translation/scale by direct NCC maximisation
    from scipy.optimize import minimize

    def cost(p):
        m2 = ndimage.affine_transform(mov_e, [p[0], p[0]], offset=[p[1], p[2]], order=1, mode='constant', cval=np.nan)
        ok = np.isfinite(m2)
        return -np.corrcoef(ref_e[ok], m2[ok])[0, 1]
    r = minimize(cost, [s, ty, tx], method='Nelder-Mead', options=dict(xatol=1e-3, fatol=1e-5, maxiter=300))
    return dict(scale=float(r.x[0]), ty=float(r.x[1]), tx=float(r.x[2]), ncc=float(-r.fun), coarse_ncc=ncc)


def main():
    CAPS.mkdir(parents=True, exist_ok=True)
    (LOCAL / 'render').mkdir(parents=True, exist_ok=True)
    std = jpg(SRC / 'R8051533.JPG')
    pred = {}
    for slot, name in (('01', 'pos'), ('02', 'neg')):
        nodes = np.load(LUT / f'host_only_RGB_Q8_8_{slot}_17.npz')['nodes']
        out = lut_apply(nodes, std.reshape(-1, 3)).reshape(std.shape)
        pred[slot] = out
        Image.fromarray(out).save(CAPS / f'R8051533_04_to_GRIV_{name}_model17.jpg', quality=94)
        print('rendered', slot, flush=True)
    sm = {k: small(v.astype(float)) for k, v in dict(std=std, p01=pred['01'], p02=pred['02']).items()}
    info = {}
    for slot, frame in (('01', 'R8051530'), ('02', 'R8051531')):
        act = small(jpg(SRC / f'{frame}.JPG').astype(float))
        a = align(edges(act), edges(sm['std']))
        print(slot, a, flush=True)
        info[slot] = dict(frame=frame, **a)
        w = {k: warp(v, a['scale'], a['ty'], a['tx']) for k, v in sm.items()}
        np.savez_compressed(LOCAL / f'render/aligned_{slot}.npz', actual=act, std=w['std'], pred=w['p' + slot],
                            other=w['p02' if slot == '01' else 'p01'])
    dump(LOCAL / 'render/alignment.json', dict(scale_factor=SCALE, frames=info,
         lut='research/gr4_lut_ceiling/local/lut/host_only_RGB_Q8_8_{01,02}_17.npz',
         input='R8051533.JPG (GXR MOUNT 04, ISO800, AsShotNeutral equal to R8051530)'))


if __name__ == '__main__':
    main()
