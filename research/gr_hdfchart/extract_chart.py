"""Sample the supplied chart with the existing decoder and marker geometry."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import support as s
import argparse
import json
import numpy as np
from scipy.ndimage import uniform_filter


def values(image, ring, geo, rect):
    q = ring.roi_mask(geo, rect, image.shape)
    assert q is not None
    y0, y1, x0, x1, mask, inner = q
    return image[y0:y1, x0:x1][mask], q


def inset_rect(patch, inset):
    x0, y0, x1, y1 = patch['bbox_px']
    return [x0 + inset, y0 + inset, x1 - inset, y1 - inset]


def noise_estimate(a):
    # Adjacent CFA-quad differences: an upper estimate including display texture.
    d = (a[1:] - a[:-1]).reshape(-1, 3)
    return np.median(abs(d - np.median(d, axis=0)), axis=0) / (.67448975 * np.sqrt(2))


def run(dng, jpeg, ident, whole=True):
    s.guard()
    dng, jpeg = dng.resolve(), jpeg.resolve()
    assert dng.is_relative_to(s.ROOT / 'captures') and jpeg.is_relative_to(s.ROOT / 'captures')
    r = s.runtime()
    io, cm, _, _ = s.modules()
    f = dict(id=ident, family='gr4', mode='negative' if ident.endswith('39') else 'positive',
             dng=str(dng.relative_to(s.ROOT)), jpg=str(jpeg.relative_to(s.ROOT)), metadata={})
    f['metadata'] = sys.modules['common'].metadata(dng)
    raw, md = r.extract.raw_frame(f)
    jpg, jvalid, ji = r.extract.camera_jpeg(f)
    assert raw['rgb'].shape == jpg.shape
    ring = r.ring
    lay = ring.load_layout()
    geo = ring.locate_screen(jpg, lay)
    hh, ww = jpg.shape[:2]
    yy, xx = np.mgrid[:hh, :ww]
    r2 = (((yy - (hh - 1) / 2) ** 2 + (xx - (ww - 1) / 2) ** 2) /
          ((hh / 2) ** 2 + (ww / 2) ** 2)).astype(np.float32)
    tags = {int(k): v for k, v in md['tags'].items()}
    coef = s.read(s.ROOT / 'research/gr4_modes/local/tone_curves.json')['radial']['gr4_coef_natural_log']
    gain = np.exp(-sum(c * r2 ** (i + 1) for i, c in enumerate(coef))).astype(np.float32)
    uc = raw['rgb'] / np.asarray(tags[50728], np.float32) * 2 ** tags.get(50730, [0])[0] * gain[..., None]
    rows, rgb_means, uc_means, raw_means, valid = [], [], [], [], []
    for p in lay['patches']:
        j, q = values(jpg, ring, geo, inset_rect(p, 30))
        c, _ = values(raw['rgb'], ring, geo, inset_rect(p, 30))
        u, _ = values(uc, ring, geo, inset_rect(p, 30))
        clip, _ = values(raw['clip'], ring, geo, inset_rect(p, 30))
        y0, y1, x0, x1, mask, inner = q
        ix0, iy0, ix1, iy1 = inner
        block = jpg[iy0:iy1, ix0:ix1].astype(float)
        moire = ring.moire_metrics(block)
        noise = noise_estimate(raw['rgb'][iy0:iy1, ix0:ix1])
        flags = []
        if p['id'] == 50:
            flags.append('mouse-crosshair-mask-entire-patch')
        if clip.mean() > .001 or np.quantile(c, .999) >= .985:
            flags.append('raw-clip')
        if np.mean((j <= 2) | (j >= 253)) > .01:
            flags.append('jpeg-clip')
        if max(j.std(axis=0)) > 12:
            flags.append('texture')
        if moire and any(v['peak_ratio'] > 20 and v['peak_amp'] > 1.5 for v in moire.values()):
            flags.append('moire')
        # Compare a central square with a concentric annulus, both away from edges.
        centre, _ = values(jpg, ring, geo, inset_rect(p, 60))
        outer, oq = values(jpg, ring, geo, inset_rect(p, 12))
        ya, yb, xa, xb, om, _ = oq
        cy, cx = np.mgrid[ya:yb, xa:xb]
        screen = ring.apply_h(geo['Hinv'], np.stack([cx + .5, cy + .5], axis=-1))
        ir = inset_rect(p, 40)
        am = om & ~((screen[..., 0] >= ir[0]) & (screen[..., 0] < ir[2]) &
                    (screen[..., 1] >= ir[1]) & (screen[..., 1] < ir[3]))
        ann = jpg[ya:yb, xa:xb][am]
        delta = cm.rgb_lab(ann.mean(0) / 255) - cm.rgb_lab(centre.mean(0) / 255)
        rows.append(dict(id=p['id'], flags=flags, n=len(j), raw_clip_fraction=float(clip.mean()),
                         raw_p999=float(np.quantile(c, .999)), raw_max=float(c.max()),
                         jpeg_clip_fraction=float(np.mean((j <= 2) | (j >= 253))),
                         jpeg_sd=j.std(0), moire=moire, raw_noise_sigma=noise,
                         raw_snr=np.mean(c, axis=0) / np.maximum(noise, 1e-9),
                         centre_annulus_delta_lab=delta,
                         centre_annulus_de00=float(cm.delta_e00(cm.rgb_lab(ann.mean(0)/255), cm.rgb_lab(centre.mean(0)/255)))))
        rgb_means.append(j.mean(0)); uc_means.append(u.mean(0)); raw_means.append(c.mean(0)); valid.append(not flags)
    s.dump(s.LOCAL / (ident + '_quality.json'), dict(frame=f, geometry=geo, raw=md, jpeg=ji, patches=rows))
    np.savez(s.LOCAL / (ident + '_roi.npz'), jpeg=np.array(rgb_means), uc=np.array(uc_means),
             raw=np.array(raw_means), valid=np.array(valid), ids=np.arange(1,156))
    # Gaps are measured in sensor green before WB, to avoid JPEG tone confounding.
    lookup = {(p['row'], p['col']): p for p in lay['patches']}
    gaps = []
    for p in lay['patches']:
        for dr, dc in ((0,1),(1,0)):
            other = lookup.get((p['row']+dr,p['col']+dc))
            if other is None or 50 in (p['id'], other['id']):
                continue
            a, b = np.array(p['center_px']), np.array(other['center_px'])
            centre = (a+b)/2
            rect = [centre[0]-5,centre[1]-5,centre[0]+5,centre[1]+5]
            gv, _ = values(raw['rgb'],ring,geo,rect)
            bright = .5*(raw_means[p['id']-1][1]+raw_means[other['id']-1][1])
            gaps.append([float(gv[:,1].mean()),float(bright)])
    s.dump(s.LOCAL / (ident + '_gaps.json'), gaps)
    # White chromaticity uses the unbalanced sensor values and native DNG matrix.
    whites = np.array(raw_means)[153:155].mean(0)
    temp = 6504.
    for _ in range(20):
        M, _ = cm.camera_matrix_at_temperature(tags,temp)
        xyz = np.linalg.solve(M, whites)
        temp = cm.cct_mccamy(xyz)
    xy = xyz[:2]/xyz.sum()
    s.dump(s.LOCAL / (ident + '_white.json'), dict(xy=xy,cct_K=temp,
           distance_xy_D65=float(np.linalg.norm(xy-np.array([.3127,.3290]))),
           method='native ColorMatrix applied to unbalanced reference-white RAW, iterative CCT; display spectrum approximate'))
    if whole:
        r.extract.extract(f,60000)
        p = s.LOCAL / 'samples' / (ident+'.npz')
        with np.load(p,allow_pickle=False) as z:
            d=dict(z)
        sx,sy=d['xy'].T
        d['uc_quad']=d['uc'];d['jpeg_quad']=d['jpeg']
        d['uc']=np.column_stack([uniform_filter(uc[...,c],5)[sy,sx] for c in range(3)])
        d['jpeg']=np.column_stack([uniform_filter(jpg[...,c],5)[sy,sx] for c in range(3)])
        d['features']=r.extract.feature(d['uc']).astype(np.float32)
        screen=ring.apply_h(geo['Hinv'],d['xy'].astype(float)+.5)
        ids=np.zeros(len(screen),int)
        mouse=np.zeros(len(screen),bool)
        for pp in lay['patches']:
            x0,y0,x1,y1=pp['bbox_px']
            inside=(screen[:,0]>=x0)&(screen[:,0]<x1)&(screen[:,1]>=y0)&(screen[:,1]<y1)
            ids[inside]=pp['id']
            if pp['id']==50:
                mouse=(screen[:,0]>=x0-8)&(screen[:,0]<x1+8)&(screen[:,1]>=y0-8)&(screen[:,1]<y1+8)
        d['patch_id']=ids;d['mouse_mask']=mouse
        np.savez_compressed(p,**d)
    print(json.dumps(dict(id=ident,usable_roi=sum(valid),excluded={q['id']:q['flags'] for q in rows if q['flags']},
                          corner_rms_full_px=2*geo['corner_rms_px'],white_xy=xy.tolist(),cct_K=temp)))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--dng',type=Path,required=True)
    ap.add_argument('--jpeg',type=Path,required=True)
    ap.add_argument('--id',required=True)
    ap.add_argument('--roi-only',action='store_true')
    a=ap.parse_args()
    run(a.dng,a.jpeg,a.id,not a.roi_only)
