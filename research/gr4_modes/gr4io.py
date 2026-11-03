#!/usr/bin/env python3
"""Read-only loaders for GR IV / GR III DNG + camera JPEG pairs.

Reuses the TIFF / maker-note reader and the SOF3 decoder from
research/contrib_gr_analysis (lj92.c for the full mosaic, the Python decoder
for a two-row cross-check). Inputs are opened read-only. The lj92 binary is
compiled into a scratch directory under /tmp, never next to the inputs.

Definitions used everywhere in research/gr4_modes:

  camera RGB  c = (raw - BlackLevel) / (WhiteLevel - BlackLevel), per CFA
              plane, on 2x2 RGGB quads of the DefaultCrop (G = mean of G1,G2).
  u           = 2**BaselineExposure * (cR/nR + 2 cG/nG + cB/nB) / 4,
              n = AsShotNeutral. u = 1 is a white-balanced neutral that
              would just reach the white level before BaselineExposure.
  u_nobe      = the same without the 2**BaselineExposure factor.

The GXR model in research/phase1_curves uses u_gxr = (R/nR + 2G/nG + B/nB)/4
on a 12-bit white level and no BaselineExposure (the GXR DNG has none).
"""
import hashlib
import io
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
CONTRIB = HERE.parent / 'contrib_gr_analysis'
sys.path.insert(0, str(CONTRIB))

from measure import decode_mosaic, dng_geometry, load_tiff, raw_subifd, tag_map, scalar  # noqa: E402
from tiff_makernote import decode_gr3_family, maker_note_bytes, jpeg_exif_tiff  # noqa: E402

SCRATCH = Path('/tmp/gr4modes_work')
LOCAL = HERE / 'local'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def lj92_binary():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    binary = SCRATCH / 'lj92'
    if not binary.exists():
        subprocess.run(['cc', '-O3', '-Wall', '-Wextra', '-o', str(binary), str(CONTRIB / 'lj92.c')], check=True)
    return binary


def ifd0_tags(tiff):
    _, _, _, root, _ = maker_note_bytes(tiff)
    return {item['tag']: item['value'] for item in root}


def maker(tiff):
    _, offset, note, root, exif = maker_note_bytes(tiff)
    if not note.startswith(b'RICOH\0'):
        return None, root, exif
    _, decoded = decode_gr3_family(tiff, offset)
    return decoded, root, exif


def decode_dng(path):
    """Return dict with the cropped mosaic (uint16, RGGB at 0,0) and tags."""
    tiff = load_tiff(path)
    decoded, root, exif = maker(tiff)
    raw, subs = raw_subifd(root, tiff)
    geometry = dng_geometry(raw, tag_map(root))
    blob = tiff.data[geometry['strip_offset']:geometry['strip_offset'] + geometry['strip_bytes']]
    work = SCRATCH / ('decode_' + Path(path).stem)
    work.mkdir(parents=True, exist_ok=True)
    mosaic, check = decode_mosaic(lj92_binary(), blob, (geometry['width'], geometry['height']), work)
    x0, y0 = geometry['crop_origin_xy']
    w, h = geometry['crop_size_wh']
    pattern = np.array(geometry['cfa_pattern'], np.uint8).reshape(2, 2)
    if (x0 % 2) or (y0 % 2) or pattern[0, 0] != 0 or pattern[1, 1] != 2:
        raise RuntimeError(f'crop is not RGGB at an even origin: {geometry}')
    crop = np.ascontiguousarray(mosaic[y0:y0 + h, x0:x0 + w])
    tags = {item['tag']: item['value'] for item in root}
    exif_tags = {item['tag']: item['value'] for item in exif}
    return {'path': str(path), 'crop': crop, 'geometry': geometry, 'decoder': check,
            'tags': tags, 'exif': exif_tags, 'maker': decoded,
            'raw_max': int(mosaic.max())}


def camera_rgb_half(crop, geometry):
    """2x2 quad means -> (H/2, W/2, 3) float32 normalised camera RGB (not WB)."""
    black = np.array(geometry['black_level'], np.float32)
    if black.size == 1:
        black = np.repeat(black, 4)
    white = float(geometry['white_level'])
    c = crop.astype(np.float32)
    r = (c[0::2, 0::2] - black[0]) / (white - black[0])
    g = 0.5 * ((c[0::2, 1::2] - black[1]) / (white - black[1]) + (c[1::2, 0::2] - black[2]) / (white - black[2]))
    b = (c[1::2, 1::2] - black[3]) / (white - black[3])
    clip = (c[0::2, 0::2] >= white) | (c[0::2, 1::2] >= white) | (c[1::2, 0::2] >= white) | (c[1::2, 1::2] >= white)
    return np.stack([r, g, b], axis=-1), clip


def u_of(rgb, neutral, baseline_exposure=0.0):
    n = np.asarray(neutral, np.float32)
    wb = rgb / n
    return (2.0 ** baseline_exposure) * (wb[..., 0] + 2 * wb[..., 1] + wb[..., 2]) / 4.0


def load_jpeg(path_or_bytes):
    if isinstance(path_or_bytes, (bytes, bytearray)):
        image = Image.open(io.BytesIO(path_or_bytes))
    else:
        image = Image.open(path_or_bytes)
    info = {'mode': image.mode, 'size': list(image.size), 'format': image.format}
    try:
        info['subsampling'] = image.layer if hasattr(image, 'layer') else None
    except Exception:  # noqa: BLE001
        info['subsampling'] = None
    try:
        q = image.quantization
        info['quant_tables_first8'] = {int(k): list(v)[:8] for k, v in q.items()}
    except Exception:  # noqa: BLE001
        pass
    arr = np.asarray(image.convert('RGB'))
    return arr, info


def half(arr):
    h, w = arr.shape[:2]
    a = arr[:h - h % 2, :w - w % 2].astype(np.float32)
    if a.ndim == 2:
        return a.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
    return a.reshape(h // 2, 2, w // 2, 2, a.shape[2]).mean(axis=(1, 3))


def load_pair(dng_path, jpg_path, cache_name=None, keep_crop=False, cache_dir=None):
    """Decode once, cache half-res arrays in <cache_dir or local/>/<cache_name>.npz.

    Contributor photos cache into local/ (git-ignored). Public downloads cache
    under /tmp/gr4modes_work/cache.
    """
    cdir = Path(cache_dir) if cache_dir else LOCAL
    cdir.mkdir(parents=True, exist_ok=True)
    cache = cdir / f'{cache_name}.npz' if cache_name else None
    if cache and cache.exists() and not keep_crop:
        z = np.load(cache, allow_pickle=False)
        out = {k: z[k] for k in z.files}
        out['tags'] = None
        return out
    d = decode_dng(dng_path)
    rgb, clip = camera_rgb_half(d['crop'], d['geometry'])
    jpg, info = load_jpeg(jpg_path)
    if jpg.shape[0] != d['crop'].shape[0] or jpg.shape[1] != d['crop'].shape[1]:
        raise RuntimeError(f'JPEG {jpg.shape} vs crop {d["crop"].shape}')
    tags = d['tags']
    neutral = np.array(tags[50728], np.float32)
    be = float(tags.get(50730, [0.0])[0]) if 50730 in tags else 0.0
    cm1 = np.array(tags[50721], np.float64)
    cm2 = np.array(tags.get(50722, tags[50721]), np.float64)
    out = {
        'rgb': rgb.astype(np.float32), 'raw_clip': clip, 'jpeg_half': half(jpg).astype(np.float32),
        'neutral': neutral, 'baseline_exposure': np.float32(be),
        'cm1': cm1, 'cm2': cm2,
        'ill': np.array([tags.get(50778, [17])[0], tags.get(50779, [21])[0]], np.int32),
        'black': np.array(d['geometry']['black_level'], np.float32),
        'white': np.float32(d['geometry']['white_level']),
    }
    if cache:
        np.savez(cache, **out)
    out['tags'] = tags
    out['exif'] = d['exif']
    out['maker'] = d['maker']
    out['decoder'] = d['decoder']
    out['geometry'] = d['geometry']
    out['jpeg_info'] = info
    if keep_crop:
        out['crop'] = d['crop']
        out['jpeg_full'] = jpg
    return out


def dng_tags_for_colour(pair):
    """Tag dict in the shape research/color_references/colour_math.py expects."""
    return {50721: list(pair['cm1']), 50722: list(pair['cm2']), 50778: [int(pair['ill'][0])],
            50779: [int(pair['ill'][1])], 50728: list(map(float, pair['neutral'])), 50727: [1.0, 1.0, 1.0]}
