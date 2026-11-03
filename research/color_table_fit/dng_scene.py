#!/usr/bin/env python3
"""Scene colorimetry from a GXR DNG: raw CFA means in a JPEG-coordinate ROI -> CIE XYZ (D65). Analysis only.

Usage
  python3 -I research/color_table_fit/dng_scene.py --selftest          # synthetic + (if present) capture checks
  python3 -I research/color_table_fit/dng_scene.py --verify-map X.DNG [--jpeg X.JPG]

Pipeline (Adobe DNG Specification 1.7.1, chapters 5 and 6; camera profile without ForwardMatrix):
  1. raw CFA plane of the CFA IFD; LinearizationTable when present; BlackLevel with its repeat pattern and
     BlackLevelDeltaH/V; WhiteLevel; ActiveArea; DefaultCropOrigin/Size; CFA pattern (origin at the
     ActiveArea origin); normalised signal (v - black) / (white - black). Orientation of both files.
  2. ROI in JPEG pixel coordinates -> crop coordinates (Orientation of JPEG and DNG, DefaultScale, optional
     integer offset). verify_mapping() phase-correlates the half-resolution raw green plane against the
     2x2-binned JPEG luma in tiles and reports the shift field and its residual.
  3. Per-CFA-colour means inside the ROI (no demosaic, no interpolation), standard errors from the spread.
  4. White xy of a camera neutral: XYZtoCamera = AB * CC * CM, CM and CC interpolated in 1/CCT between the
     calibration illuminants (DNG SDK temperatures: StdA 2850 K, D65 6500 K, ...), CCT by Robertson's method,
     iterated from D50 to a fixed point (DNG SDK NeutralToXY).
  5. PCStoCamera = XYZtoCamera(white) * Bradford(D50 -> white), scaled so the PCS white is reached when the
     first camera channel saturates; CameraToPCS = its inverse; XYZ(D65) = Bradford(D50 -> D65) * PCS.
     (With ForwardMatrix tags the spec's forward-matrix path is used instead; GXR DNGs have none.)

White references: (i) AsShotNeutral (AsShotWhiteXY if only that is given); (ii) an in-frame neutral, the
mean G-normalised camera RGB of chosen neutral ROIs, through the same NeutralToXY. Absolute scale: a camera
neutral whose largest channel is at WhiteLevel maps to Y = 1; callers renormalise the exposure.

Ricoh-derived numbers (ColorMatrix, AsShotNeutral) are read from the DNG at run time and are not embedded.
The self-test uses an invented camera matrix, not the GXR one. Captures are only read.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
SELFTEST_TMP = Path("/tmp/gxr_dng_scene_selftest")

# CIE / DNG SDK constants
D50_XY = np.array([0.3457, 0.3585])          # DNG PCS white (SDK D50_xy_coord)
D65_XY = np.array([0.3127, 0.3290])          # sRGB / BT.709 / F-Gamut white
A_XY = np.array([0.44757, 0.40745])          # CIE illuminant A (2856 K), self-test only
BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])
# DNG SDK dng_camera_profile::IlluminantToTemperature (EXIF LightSource codes)
ILLUMINANT_K = {1: 5500.0, 2: 4150.0, 3: 2850.0, 4: 5500.0, 9: 5500.0, 10: 6500.0, 11: 7500.0,
                12: 6400.0, 13: 5050.0, 14: 4150.0, 15: 3525.0, 16: 2925.0, 17: 2850.0, 18: 5500.0,
                19: 6500.0, 20: 5500.0, 21: 6500.0, 22: 7500.0, 23: 5000.0, 24: 3200.0}
# Robertson (1968) isotemperature lines: mired, u, v, slope (CIE 1960 uv); 325-mired u is the corrected 0.24792.
ROBERTSON = np.array([
    [0, 0.18006, 0.26352, -0.24341], [10, 0.18066, 0.26589, -0.25479], [20, 0.18133, 0.26846, -0.26876],
    [30, 0.18208, 0.27119, -0.28539], [40, 0.18293, 0.27407, -0.30470], [50, 0.18388, 0.27709, -0.32675],
    [60, 0.18494, 0.28021, -0.35156], [70, 0.18611, 0.28342, -0.37915], [80, 0.18740, 0.28668, -0.40955],
    [90, 0.18880, 0.28997, -0.44278], [100, 0.19032, 0.29326, -0.47888], [125, 0.19462, 0.30141, -0.58204],
    [150, 0.19962, 0.30921, -0.70471], [175, 0.20525, 0.31647, -0.84901], [200, 0.21142, 0.32312, -1.0182],
    [225, 0.21807, 0.32909, -1.2168], [250, 0.22511, 0.33439, -1.4512], [275, 0.23247, 0.33904, -1.7298],
    [300, 0.24010, 0.34308, -2.0637], [325, 0.24792, 0.34655, -2.4681], [350, 0.25591, 0.34951, -2.9641],
    [375, 0.26400, 0.35200, -3.5814], [400, 0.27218, 0.35407, -4.3633], [425, 0.28039, 0.35577, -5.3762],
    [450, 0.28863, 0.35714, -6.7262], [475, 0.29685, 0.35823, -8.5955], [500, 0.30505, 0.35907, -11.324],
    [525, 0.31320, 0.35968, -15.628], [550, 0.32129, 0.36011, -23.325], [575, 0.32931, 0.36038, -40.770],
    [600, 0.33724, 0.36051, -116.45]])
TINT_SCALE = -3000.0


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MODS = {}


def analyze_capture():
    """The repo's read-only TIFF reader and GXR raw decoder (research/color_calibration/analyze_capture.py)."""
    if "ac" not in _MODS:
        _MODS["ac"] = load_module("analyze_capture", ROOT / "research/color_calibration/analyze_capture.py")
    return _MODS["ac"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


STAGE2E_RECORD = ROOT / "research/stage2e_verification/local/measurements.json"


def rel(path):
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _md_hashes(md):
    import re
    return dict(re.findall(r"\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", Path(md).read_text()))


def reference_sha256(path):
    """Expected SHA-256 of a capture file: SHA256SUMS next to it; else, for capture directories without one,
    the copy manifest in the directory or the hash table of the analysis that first read it."""
    p = Path(path)
    sums = p.parent / "SHA256SUMS"
    if sums.exists():
        for line in sums.read_text().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and Path(parts[-1].lstrip("*")).name == p.name:
                return parts[0].lower(), rel(sums)
        return None, f"{rel(sums)} (file not listed)"
    note = " (no SHA256SUMS in that directory)"
    man = p.parent / "copy_manifest.json"
    if man.exists():
        for f in json.loads(man.read_text()).get("files", []):
            if f.get("name") == p.name and f.get("copy_sha256"):
                return f["copy_sha256"], rel(man) + note
    if p.parent.name == "stage2e-colorchecker" and STAGE2E_RECORD.exists():
        rec = json.loads(STAGE2E_RECORD.read_text()).get("capture_sha256_before", {})
        if p.name in rec:
            return rec[p.name], f"{rel(STAGE2E_RECORD)} capture_sha256_before" + note
    if p.parent.name == "stage2d-colorchecker":
        md = ROOT / "research/stage2d_verification/REPORT.md"
        if md.exists() and p.name in _md_hashes(md):
            return _md_hashes(md)[p.name], rel(md) + " hash table" + note
    return None, "no SHA256SUMS next to the file and no other record"


class CaptureGuard:
    """SHA-256 of every capture file read: before (checked against the reference when one exists) and after."""

    def __init__(self):
        self.before, self.ref = {}, {}

    def add(self, path):
        p = Path(path).resolve()
        if str(p) in self.before:
            return self.before[str(p)]
        h = sha256_file(p)
        ref, src = reference_sha256(p)
        self.before[str(p)] = h
        self.ref[str(p)] = {"reference": ref, "reference_source": src, "matches_reference": None if ref is None
                            else ref == h}
        if ref is not None and ref != h:
            raise SystemExit(f"{p}: SHA-256 {h} differs from the reference {ref} ({src})")
        return h

    def after(self):
        files = {}
        for k, h in self.before.items():
            a = sha256_file(k)
            files[rel(k)] = {"before": h, "after": a, "unchanged": a == h, **self.ref[k]}
        return {"files": files, "all_unchanged": all(v["unchanged"] for v in files.values()),
                "none_mismatch_reference": all(v["matches_reference"] is not False for v in files.values()),
                "n_with_reference": sum(v["reference"] is not None for v in files.values())}


# ----------------------------------------------------------------- colour helpers

def xy_to_xyz(xy):
    x, y = float(xy[0]), float(xy[1])
    return np.array([x / y, 1.0, (1.0 - x - y) / y])


def xyz_to_xy(xyz):
    s = float(np.sum(xyz))
    if s <= 0:
        return D50_XY.copy()
    return np.array([xyz[0] / s, xyz[1] / s])


def bradford(src_xy, dst_xy):
    """Linear Bradford, as DNG SDK MapWhiteMatrix (cone ratios pinned to [0.1, 10])."""
    w1 = np.maximum(BRADFORD @ xy_to_xyz(src_xy), 0.0)
    w2 = np.maximum(BRADFORD @ xy_to_xyz(dst_xy), 0.0)
    a = np.array([np.clip(b / a_ if a_ > 0 else 10.0, 0.1, 10.0) for a_, b in zip(w1, w2)])
    return np.linalg.inv(BRADFORD) @ np.diag(a) @ BRADFORD


def xy_to_cct(xy):
    """Correlated colour temperature and tint, Robertson's method (DNG SDK dng_temperature)."""
    x, y = float(xy[0]), float(xy[1])
    den = 1.5 - x + 6.0 * y
    u, v = 2.0 * x / den, 3.0 * y / den
    last_dt = last_du = last_dv = 0.0
    for i in range(1, 31):
        r1, u1, v1, t1 = ROBERTSON[i]
        ln = math.hypot(1.0, t1)
        du, dv = 1.0 / ln, t1 / ln
        uu, vv = u - u1, v - v1
        dt = -uu * dv + vv * du
        if dt <= 0.0 or i == 30:
            dt = -min(dt, 0.0)
            f = 0.0 if i == 1 else dt / (last_dt + dt)
            r0 = ROBERTSON[i - 1]
            temp = 1.0e6 / (r0[0] * f + r1 * (1.0 - f))
            uu = u - (r0[1] * f + u1 * (1.0 - f))
            vv = v - (r0[2] * f + v1 * (1.0 - f))
            du = du * (1.0 - f) + last_du * f
            dv = dv * (1.0 - f) + last_dv * f
            ln = math.hypot(du, dv)
            du, dv = du / ln, dv / ln
            return temp, (uu * du + vv * dv) * TINT_SCALE
        last_dt, last_du, last_dv = dt, du, dv
    raise AssertionError("unreachable")


def xyz_to_lab(xyz, white):
    t = np.asarray(xyz, float) / np.asarray(white, float)
    d = 6 / 29
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


# ----------------------------------------------------------------- orientation

def orient_points(o, W, H, x, y):
    """TIFF Orientation o: stored continuous coords (pixel corners on integers, size W x H) -> displayed."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    return {1: (x, y), 2: (W - x, y), 3: (W - x, H - y), 4: (x, H - y), 5: (y, x), 6: (H - y, x),
            7: (H - y, W - x), 8: (y, W - x)}[int(o)]


def unorient_points(o, W, H, x, y):
    """Displayed continuous coords -> stored (W x H is the stored size)."""
    o = int(o)
    inv = {6: 8, 8: 6}.get(o, o)
    Wd, Hd = (H, W) if o >= 5 else (W, H)
    return orient_points(inv, Wd, Hd, x, y)


def displayed_size(o, W, H):
    return (H, W) if int(o) >= 5 else (W, H)


# ----------------------------------------------------------------- DNG reader

class Dng:
    """Read-only DNG: raw CFA plane and the tags needed for colorimetry. Reuses analyze_capture.Tiff."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        self.sha256 = hashlib.sha256(self.data).hexdigest()
        T = analyze_capture().Tiff(self.data)
        self.endian = "big" if T.endian == ">" else "little"
        root = T.ifd(T.root)
        subs = [T.ifd(o) for o in root.get(330, {}).get("value", [])]

        def val(d, tag, default=None):
            return d[tag]["value"] if tag in d else default
        raw = None
        for d in [root] + subs:
            if val(d, 262, [None])[0] == 32803 and val(d, 254, [0])[0] == 0:
                raw = d
                break
        if raw is None:
            raise ValueError(f"{self.path.name}: no full-resolution CFA IFD")
        self.width, self.height = int(val(raw, 256)[0]), int(val(raw, 257)[0])
        self.bps = int(val(raw, 258)[0])
        if val(raw, 259, [1])[0] != 1:
            raise NotImplementedError(f"compression {val(raw, 259)}")
        if val(raw, 277, [1])[0] != 1:
            raise NotImplementedError("SamplesPerPixel != 1 (not a CFA image)")
        if val(raw, 266, [1])[0] != 1:
            raise NotImplementedError("FillOrder 2")
        if 322 in raw or 324 in raw:
            raise NotImplementedError("tiled raw")
        self._strips = (list(val(raw, 273)), list(val(raw, 279)))
        dim = [int(v) for v in val(raw, 33421, [2, 2])]
        pat = val(raw, 33422)
        pat = list(pat) if isinstance(pat, (bytes, bytearray)) else [int(v) for v in pat]
        self.cfa = np.array(pat, int).reshape(dim)
        plane = val(raw, 50710, [0, 1, 2])
        plane = list(plane)
        if plane != [0, 1, 2] or sorted(set(self.cfa.ravel().tolist())) != [0, 1, 2]:
            raise NotImplementedError(f"CFA colours {plane} / pattern {pat}")
        if val(raw, 50711, [1])[0] != 1:
            raise NotImplementedError("non-rectangular CFALayout")
        self.lin_table = np.asarray(val(raw, 50712), float) if 50712 in raw else None
        aa = val(raw, 50829, [0, 0, self.height, self.width])
        self.active = tuple(int(round(v)) for v in aa)          # top, left, bottom, right
        aw, ah = self.active[3] - self.active[1], self.active[2] - self.active[0]
        bdim = [int(v) for v in val(raw, 50713, [1, 1])]
        bl = np.asarray(val(raw, 50714, [0.0]), float)
        if bl.size == 1:
            bl = np.full(bdim[0] * bdim[1], bl[0])
        if bl.size != bdim[0] * bdim[1]:
            raise NotImplementedError(f"BlackLevel count {bl.size} for repeat {bdim}")
        self.black_pattern = bl.reshape(bdim)
        self.black_dh = np.asarray(val(raw, 50715), float) if 50715 in raw else None
        self.black_dv = np.asarray(val(raw, 50716), float) if 50716 in raw else None
        if self.black_dh is not None and self.black_dh.size != aw:
            raise ValueError("BlackLevelDeltaH length")
        if self.black_dv is not None and self.black_dv.size != ah:
            raise ValueError("BlackLevelDeltaV length")
        self.white = float(val(raw, 50717, [(1 << self.bps) - 1])[0])
        self.default_scale = tuple(float(v) for v in val(raw, 50718, [1.0, 1.0]))
        co = [float(v) for v in val(raw, 50719, [0, 0])]
        cs = [float(v) for v in val(raw, 50720, [aw, ah])]
        if any(abs(v - round(v)) > 1e-9 for v in co + cs):
            raise NotImplementedError(f"fractional default crop {co} {cs}")
        self.crop_origin = (int(round(co[0])), int(round(co[1])))   # x, y relative to the ActiveArea
        self.crop_size = (int(round(cs[0])), int(round(cs[1])))     # w, h
        self.orientation = int(val(root, 274, [1])[0])
        self.as_shot_neutral = np.asarray(val(root, 50728), float) if 50728 in root else None
        self.as_shot_white_xy = np.asarray(val(root, 50729), float) if 50729 in root else None

        def mat(tag):
            v = val(root, tag)
            return None if v is None else np.asarray(v, float).reshape(3, 3)
        self.color_matrix = [mat(50721), mat(50722)]
        self.camera_calibration = [mat(50723), mat(50724)]
        self.forward_matrix = [mat(50964), mat(50965)]
        self.illuminant = [int(val(root, 50778, [0])[0]), int(val(root, 50779, [0])[0])]
        self.analog_balance = np.asarray(val(root, 50727, [1.0, 1.0, 1.0]), float)
        self.baseline_exposure = float(val(root, 50730, [0.0])[0])
        self.exif = {}
        if 34665 in root:
            try:
                ex = T.ifd(root[34665]["value"][0])
                for tag, name in ((34855, "iso"), (33434, "t"), (33437, "f"), (36867, "when"), (41987, "wb_exif"),
                                  (37383, "metering"), (34850, "program"), (37380, "bias_ev")):
                    if tag in ex:
                        v = ex[tag]["value"]
                        self.exif[name] = v[0] if isinstance(v, list) and len(v) == 1 else v
            except Exception as e:  # noqa: BLE001
                self.exif["error"] = str(e)
        self._mosaic = None

    # --- raw plane
    def mosaic(self):
        """Full raw CFA plane (height x width), uint16, before linearization."""
        if self._mosaic is not None:
            return self._mosaic
        offs, cnts = self._strips
        buf = np.concatenate([np.frombuffer(self.data, np.uint8, count=int(n), offset=int(o))
                              for o, n in zip(offs, cnts)])
        h, w, b = self.height, self.width, self.bps
        row = (w * b + 7) // 8
        if buf.size < row * h:
            raise ValueError("raw strips shorter than the image")
        rows = buf[:row * h].reshape(h, row)
        if b == 16:
            m = rows.reshape(-1).view(">u2" if self.endian == "big" else "<u2").reshape(h, w).astype(np.uint16)
        elif b == 8:
            m = rows[:, :w].astype(np.uint16)
        elif b == 12:
            n2 = w // 2
            a = rows[:, :3 * n2].reshape(h, n2, 3).astype(np.uint16)
            m = np.empty((h, w), np.uint16)
            m[:, 0:2 * n2:2] = (a[..., 0] << 4) | (a[..., 1] >> 4)
            m[:, 1:2 * n2:2] = ((a[..., 1] & 15) << 8) | a[..., 2]
            if w % 2:
                t = rows[:, 3 * n2:3 * n2 + 2].astype(np.uint16)
                m[:, -1] = (t[:, 0] << 4) | (t[:, 1] >> 4)
        else:
            bits = np.unpackbits(rows, axis=1)[:, :w * b].reshape(h, w, b)
            m = (bits.astype(np.uint32) << np.arange(b - 1, -1, -1, dtype=np.uint32)).sum(-1).astype(np.uint16)
        self._mosaic = m
        return m

    def crop_window(self):
        """(y0, x0, h, w) of the default crop in raw-plane coordinates."""
        return (self.active[0] + self.crop_origin[1], self.active[1] + self.crop_origin[0],
                self.crop_size[1], self.crop_size[0])

    def crop_mosaic(self):
        y0, x0, h, w = self.crop_window()
        return self.mosaic()[y0:y0 + h, x0:x0 + w]

    def cfa_at(self, ys, xs):
        """CFA colour (0 R, 1 G, 2 B) at raw-plane coordinates; pattern origin = ActiveArea origin."""
        r, c = self.cfa.shape
        return self.cfa[(np.asarray(ys) - self.active[0]) % r, (np.asarray(xs) - self.active[1]) % c]

    def black_at(self, ys, xs):
        ry, rx = np.asarray(ys) - self.active[0], np.asarray(xs) - self.active[1]
        bp = self.black_pattern
        b = bp[ry % bp.shape[0], rx % bp.shape[1]].astype(float)
        if self.black_dh is not None:
            b = b + self.black_dh[rx]
        if self.black_dv is not None:
            b = b + self.black_dv[ry]
        return b

    def linearize(self, v):
        v = np.asarray(v)
        if self.lin_table is None:
            return v.astype(float)
        return self.lin_table[np.minimum(v.astype(np.int64), len(self.lin_table) - 1)]

    def normalised_at(self, ys, xs):
        """(linearized value - black) / (white - black) at raw-plane coordinates (DNG chapter 5)."""
        black = self.black_at(ys, xs)
        return (self.linearize(self.mosaic()[ys, xs]) - black) / (self.white - black)

    def crop_cfa_phase(self):
        """2x2 colour codes of the crop's first quad (row-major), e.g. [[1, 2], [0, 1]] = G/B/R/G."""
        y0, x0, _, _ = self.crop_window()
        yy, xx = np.meshgrid(np.arange(y0, y0 + 2), np.arange(x0, x0 + 2), indexing="ij")
        return self.cfa_at(yy, xx)

    def summary(self):
        return {"file": self.path.name, "sha256": self.sha256, "endian": self.endian,
                "raw_size_wh": [self.width, self.height], "bits": self.bps, "cfa_pattern": self.cfa.tolist(),
                "crop_cfa_phase": self.crop_cfa_phase().tolist(), "active_area_tlbr": list(self.active),
                "default_crop_origin_xy": list(self.crop_origin), "default_crop_size_wh": list(self.crop_size),
                "default_scale": list(self.default_scale), "orientation": self.orientation,
                "linearization_table": None if self.lin_table is None else int(self.lin_table.size),
                "black_level_pattern": self.black_pattern.tolist(),
                "black_delta_h": self.black_dh is not None, "black_delta_v": self.black_dv is not None,
                "white_level": self.white, "as_shot_neutral": None if self.as_shot_neutral is None
                else self.as_shot_neutral.tolist(),
                "as_shot_white_xy": None if self.as_shot_white_xy is None else self.as_shot_white_xy.tolist(),
                "calibration_illuminants": self.illuminant,
                "forward_matrix": [m is not None for m in self.forward_matrix],
                "camera_calibration": [m is not None for m in self.camera_calibration],
                "analog_balance": self.analog_balance.tolist(), "baseline_exposure_ev": self.baseline_exposure,
                "exif": self.exif}


# ----------------------------------------------------------------- JPEG <-> raw crop mapping

def jpeg_info(jpg):
    from PIL import Image
    with Image.open(jpg) as im:
        o = im.getexif().get(0x0112, 1) or 1
        return {"size_wh": list(im.size), "orientation": int(o)}


class RawMap:
    """JPEG stored pixel coordinates -> DNG default-crop stored coordinates.

    stored JPEG -> displayed (JPEG Orientation) -> scaled to the displayed raw crop (DefaultScale and size
    ratio) -> stored crop (inverse DNG Orientation) -> + integer offset (from verify_mapping, default 0).
    """

    def __init__(self, dng, jpeg_size_wh, jpeg_orientation=1, offset_xy=(0, 0)):
        self.Wj, self.Hj = int(jpeg_size_wh[0]), int(jpeg_size_wh[1])
        self.oj = int(jpeg_orientation)
        self.Wc, self.Hc = dng.crop_size
        self.oc = dng.orientation
        self.dscale = tuple(dng.default_scale)
        sxr, syr = self.dscale
        wd, hd = displayed_size(self.oc, self.Wc * sxr, self.Hc * syr)
        wj, hj = displayed_size(self.oj, self.Wj, self.Hj)
        self.scale = (wd / wj, hd / hj)                     # displayed raw units per displayed JPEG pixel
        self.offset = (int(offset_xy[0]), int(offset_xy[1]))

    @property
    def unit(self):
        return (abs(self.scale[0] - 1) < 1e-12 and abs(self.scale[1] - 1) < 1e-12
                and self.dscale[0] == 1.0 and self.dscale[1] == 1.0)

    def points(self, x, y):
        """Continuous JPEG coordinates -> continuous crop coordinates."""
        xd, yd = orient_points(self.oj, self.Wj, self.Hj, x, y)
        xd, yd = xd * self.scale[0], yd * self.scale[1]
        sxr, syr = self.dscale
        xs, ys = unorient_points(self.oc, self.Wc * sxr, self.Hc * syr, xd, yd)
        return xs / sxr + self.offset[0], ys / syr + self.offset[1]

    def rect(self, rect):
        """[x0, y0, x1, y1) JPEG -> [x0, y0, x1, y1) crop (integer, clipped)."""
        x0, y0, x1, y1 = rect
        cx, cy = self.points(np.array([x0, x1, x1, x0], float), np.array([y0, y0, y1, y1], float))
        out = [int(round(cx.min())), int(round(cy.min())), int(round(cx.max())), int(round(cy.max()))]
        return [max(0, out[0]), max(0, out[1]), min(self.Wc, out[2]), min(self.Hc, out[3])]

    def pixels(self, ys, xs):
        """Integer JPEG pixel indices -> integer crop pixel indices (unit scale only)."""
        if not self.unit:
            raise NotImplementedError("mask ROIs need a 1:1 JPEG/raw scale")
        cx, cy = self.points(np.asarray(xs) + 0.5, np.asarray(ys) + 0.5)
        return np.floor(cy).astype(np.int64), np.floor(cx).astype(np.int64)

    def describe(self):
        return {"jpeg_size_wh": [self.Wj, self.Hj], "jpeg_orientation": self.oj, "crop_size_wh": [self.Wc, self.Hc],
                "dng_orientation": self.oc, "scale_xy": list(self.scale), "default_scale": list(self.dscale),
                "offset_xy": list(self.offset)}


def _phase_corr(a, b):
    """Shift s (dy, dx) with b(p) ~ a(p - s); sub-pixel by a parabola through the peak. Returns (s, peak)."""
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    A = np.fft.fft2((a - a.mean()) * win)
    B = np.fft.fft2((b - b.mean()) * win)
    R = np.conj(A) * B
    R /= np.abs(R) + 1e-12
    r = np.fft.ifft2(R).real
    py, px = np.unravel_index(int(np.argmax(r)), r.shape)
    out = []
    for ax in (0, 1):
        n = r.shape[ax]
        p = py if ax == 0 else px
        if ax == 0:
            cm, cp = r[(py - 1) % n, px], r[(py + 1) % n, px]
        else:
            cm, cp = r[py, (px - 1) % n], r[py, (px + 1) % n]
        c0 = r[py, px]
        den = cm - 2 * c0 + cp
        frac = 0.5 * (cm - cp) / den if abs(den) > 1e-12 else 0.0
        s = p + frac
        out.append(s - n if s > n / 2 else s)
    return np.array(out), float(r[py, px])


def jpeg_luma(rgb):
    rgb = np.asarray(rgb, np.float64)
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def jpeg_in_crop_frame(rawmap, arr):
    """Resample a stored JPEG array onto the crop's stored grid (unit scale; orientation only)."""
    if not rawmap.unit:
        raise NotImplementedError("verify_mapping needs a 1:1 JPEG/raw scale")
    if rawmap.oj == 1 and rawmap.oc == 1:
        return arr
    yy, xx = np.meshgrid(np.arange(rawmap.Hc) + 0.5, np.arange(rawmap.Wc) + 0.5, indexing="ij")
    xd, yd = orient_points(rawmap.oc, rawmap.Wc, rawmap.Hc, xx, yy)          # crop -> displayed
    xj, yj = unorient_points(rawmap.oj, rawmap.Wj, rawmap.Hj, xd, yd)        # displayed -> stored JPEG
    return arr[np.floor(yj).astype(int).clip(0, rawmap.Hj - 1), np.floor(xj).astype(int).clip(0, rawmap.Wj - 1)]


def raw_green_half(dng):
    """Half-resolution green (mean of the two green sites of each crop-aligned 2x2 quad), normalised."""
    y0, x0, h, w = dng.crop_window()
    ph = dng.crop_cfa_phase()
    g = [(i, j) for i in range(2) for j in range(2) if ph[i, j] == 1]
    if len(g) != 2:
        raise NotImplementedError(f"crop quad {ph.tolist()} does not hold two greens")
    h2, w2 = h // 2, w // 2
    acc = np.zeros((h2, w2))
    for (i, j) in g:
        ys = y0 + i + 2 * np.arange(h2)
        xs = x0 + j + 2 * np.arange(w2)
        acc += dng.normalised_at(ys[:, None], xs[None, :])
    return acc / 2


def verify_mapping(dng, jpeg_rgb, rawmap, tile=256, min_peak=0.08, gamma=1 / 2.2):
    """Phase correlation of the raw green plane against the JPEG luma, in tiles of `tile` half-res pixels.

    Shifts are in full-resolution crop pixels: content at JPEG-mapped position p sits at raw p + shift. A
    translation and an affine shift field are fitted; residuals show whether the mapping is a pure offset.
    """
    lum = jpeg_in_crop_frame(rawmap, jpeg_luma(jpeg_rgb))
    G = np.clip(raw_green_half(dng), 0, None) ** gamma
    ox, oy = rawmap.offset
    h2, w2 = G.shape
    # JPEG luma on the crop grid after the current integer offset (crop = jpeg + offset), 2x2-binned
    Lfull = np.full((2 * h2, 2 * w2), np.nan)
    ys0, ys1 = max(0, oy), min(2 * h2, lum.shape[0] + oy)
    xs0, xs1 = max(0, ox), min(2 * w2, lum.shape[1] + ox)
    Lfull[ys0:ys1, xs0:xs1] = lum[ys0 - oy:ys1 - oy, xs0 - ox:xs1 - ox]
    Lb = Lfull.reshape(h2, 2, w2, 2).mean(axis=(1, 3))
    rows = []
    for ty in range(0, h2 - tile + 1, tile):
        for tx in range(0, w2 - tile + 1, tile):
            a = Lb[ty:ty + tile, tx:tx + tile]
            b = G[ty:ty + tile, tx:tx + tile]
            if np.isnan(a).any() or a.std() < 1.0:
                continue
            s, peak = _phase_corr(a, b)
            rows.append({"cx": 2 * (tx + tile / 2), "cy": 2 * (ty + tile / 2), "dy": 2 * s[0], "dx": 2 * s[1],
                         "peak": peak})
    good = [r for r in rows if r["peak"] >= min_peak and abs(r["dx"]) < tile / 2 and abs(r["dy"]) < tile / 2]
    out = {"tiles_total": len(rows), "tiles_used": len(good), "tile_full_px": 2 * tile, "min_peak": min_peak,
           "offset_applied_xy": list(rawmap.offset)}
    if len(good) < 3:
        out["ok"] = False
        out["why"] = "fewer than 3 textured tiles"
        return out
    dx = np.array([r["dx"] for r in good])
    dy = np.array([r["dy"] for r in good])
    wts = np.array([r["peak"] for r in good])
    X = np.stack([np.array([r["cx"] for r in good]), np.array([r["cy"] for r in good]), np.ones(len(good))], 1)
    t = np.array([np.average(dx, weights=wts), np.average(dy, weights=wts)])
    res_t = np.hypot(dx - t[0], dy - t[1])
    sw = np.sqrt(wts)
    Ax = np.linalg.lstsq(X * sw[:, None], dx * sw, rcond=None)[0]
    Ay = np.linalg.lstsq(X * sw[:, None], dy * sw, rcond=None)[0]
    res_a = np.hypot(dx - X @ Ax, dy - X @ Ay)
    out.update({
        "ok": True, "shift_mean_xy": t.tolist(), "shift_median_xy": [float(np.median(dx)), float(np.median(dy))],
        "translation_residual_rms_px": float(np.sqrt(np.mean(res_t ** 2))),
        "translation_residual_max_px": float(res_t.max()),
        "affine": {"dx": Ax.tolist(), "dy": Ay.tolist(), "scale_minus_1_xy": [float(Ax[0]), float(Ay[1])],
                   "rotation_mrad": float(0.5 * (Ay[0] - Ax[1]) * 1000),
                   "residual_rms_px": float(np.sqrt(np.mean(res_a ** 2))), "residual_max_px": float(res_a.max())},
        "peak_median": float(np.median(wts)),
        "suggested_integer_offset_xy": [int(round(rawmap.offset[0] + t[0])), int(round(rawmap.offset[1] + t[1]))],
        "tiles": [{k: round(float(v), 4) for k, v in r.items()} for r in good]})
    return out


# ----------------------------------------------------------------- ROI statistics

def roi_pixels(rawmap, region):
    """Region in JPEG coordinates -> crop pixel indices (ys, xs).

    region: {"rect": [x0, y0, x1, y1]} (half-open) or {"mask": bool array, "origin_yx": [y0, x0]}.
    """
    if "rect" in region:
        x0, y0, x1, y1 = rawmap.rect(region["rect"])
        yy, xx = np.meshgrid(np.arange(y0, y1), np.arange(x0, x1), indexing="ij")
        return yy.ravel(), xx.ravel()
    m = np.asarray(region["mask"], bool)
    oy, ox = region.get("origin_yx", (0, 0))
    jy, jx = np.nonzero(m)
    ys, xs = rawmap.pixels(jy + oy, jx + ox)
    ok = (ys >= 0) & (ys < rawmap.Hc) & (xs >= 0) & (xs < rawmap.Wc)
    return ys[ok], xs[ok]


def cfa_stats(dng, ys, xs, clip_frac_of_white=0.98):
    """Per-CFA-colour means of normalised raw at crop pixels (ys, xs). No demosaic."""
    cy0, cx0, _, _ = dng.crop_window()
    ry, rx = np.asarray(ys) + cy0, np.asarray(xs) + cx0
    v = dng.normalised_at(ry, rx)
    col = dng.cfa_at(ry, rx)
    out = {"cam": [], "sd": [], "se": [], "n": []}
    for c in range(3):
        s = v[col == c]
        n = int(s.size)
        out["cam"].append(float(s.mean()) if n else float("nan"))
        out["sd"].append(float(s.std(ddof=1)) if n > 1 else float("nan"))
        out["se"].append(float(s.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan"))
        out["n"].append(n)
    out["max_frac_of_white"] = float(v.max()) if v.size else float("nan")
    out["clip_frac"] = float(np.mean(v >= clip_frac_of_white)) if v.size else float("nan")
    out["n_px"] = int(v.size)
    return out


# ----------------------------------------------------------------- DNG colour

class DngColour:
    """Camera <-> XYZ per DNG 1.7 chapter 6 (DNG SDK dng_color_spec semantics).

    matrix: "interp" (spec: interpolate in 1/CCT), or "cm1" / "cm2" to use one calibration only
    (sensitivity analysis: two independent Ricoh calibrations bracket the matrix uncertainty).
    """

    def __init__(self, dng, matrix="interp"):
        if all(m is None for m in dng.color_matrix):
            raise ValueError("no ColorMatrix")
        if matrix in ("cm1", "cm2"):
            k = 0 if matrix == "cm1" else 1
            if dng.color_matrix[k] is None:
                raise ValueError(f"{matrix} requested but the DNG has no ColorMatrix{k + 1}")
            dng = _OneMatrix(dng, k)
        elif matrix != "interp":
            raise ValueError(matrix)
        self.matrix_mode = matrix
        pcs = xy_to_xyz(D50_XY)

        def norm(m):
            # dng_camera_profile NormalizeColorMatrix: largest camera coordinate of the PCS white = 1
            mx = float(np.max(m @ pcs))
            return m / mx if mx > 0 and (mx < 0.99 or mx > 1.01) else m.copy()
        self.normalised_scale = [None if m is None else float(np.max(m @ pcs)) for m in dng.color_matrix]
        cm = [None if m is None else norm(m) for m in dng.color_matrix]
        cc = [m if m is not None else np.eye(3) for m in dng.camera_calibration]
        fm = dng.forward_matrix
        T = [ILLUMINANT_K.get(i, 0.0) for i in dng.illuminant]
        if cm[1] is None or cm[0] is None or T[0] <= 0 or T[1] <= 0 or T[0] == T[1]:
            k = 0 if cm[0] is not None else 1
            self.single = True
            self.cm = [cm[k]] * 2
            self.T = [T[k] or 5000.0] * 2
            self.cc = [cc[k]] * 2
            self.fm = [fm[k]] * 2
        else:
            self.single = False
            order = [0, 1] if T[0] < T[1] else [1, 0]
            self.cm = [cm[i] for i in order]
            self.T = [T[i] for i in order]
            self.cc = [cc[i] for i in order]
            self.fm = [fm[i] for i in order]
        self.ab = np.diag(dng.analog_balance)
        self.illuminant = list(dng.illuminant)

    def weight(self, xy):
        """Weight g of the lower-temperature calibration at white xy, and the CCT/tint."""
        temp, tint = xy_to_cct(xy)
        if self.single or temp <= self.T[0]:
            g = 1.0
        elif temp >= self.T[1]:
            g = 0.0
        else:
            g = (1.0 / temp - 1.0 / self.T[1]) / (1.0 / self.T[0] - 1.0 / self.T[1])
        return g, temp, tint

    def xyz_to_camera(self, xy):
        g, _, _ = self.weight(xy)
        cm = g * self.cm[0] + (1 - g) * self.cm[1]
        cc = g * self.cc[0] + (1 - g) * self.cc[1]
        return self.ab @ cc @ cm

    def neutral_to_xy(self, neutral, max_pass=30):
        """DNG SDK NeutralToXY: iterate the interpolated matrix from D50 to a fixed point."""
        n = np.asarray(neutral, float)
        last = D50_XY.copy()
        for k in range(max_pass):
            nxt = xyz_to_xy(np.linalg.solve(self.xyz_to_camera(last), n))
            if abs(nxt[0] - last[0]) + abs(nxt[1] - last[1]) < 1e-7:
                return nxt, k + 1, True
            if k == max_pass - 1:
                nxt = 0.5 * (last + nxt)
            last = nxt
        return last, max_pass, False

    def camera_to_pcs(self, white_xy):
        """CameraToPCS (camera -> XYZ adapted to D50) for this white (SDK dng_color_spec::SetWhiteXY)."""
        m = self.xyz_to_camera(white_xy)
        g, _, _ = self.weight(white_xy)
        fm = None
        if self.fm[0] is not None:
            fm = g * self.fm[0] + (1 - g) * self.fm[1] if self.fm[1] is not None else self.fm[0]
        if fm is not None:
            cam_white = m @ xy_to_xyz(white_xy)
            cam_white = np.clip(cam_white / cam_white.max(), 0.001, 1.0)
            cc = g * self.cc[0] + (1 - g) * self.cc[1]
            ind_to_ref = np.linalg.inv(self.ab @ cc)
            ref_white = ind_to_ref @ cam_white
            return fm @ np.diag(1.0 / ref_white) @ ind_to_ref
        p2c = m @ bradford(D50_XY, white_xy)
        p2c = p2c / float(np.max(p2c @ xy_to_xyz(D50_XY)))
        return np.linalg.inv(p2c)

    def camera_to_xyz(self, white_xy, out_white_xy=D65_XY):
        """Camera (normalised raw) -> XYZ chromatically adapted to out_white_xy (Bradford from D50)."""
        return bradford(D50_XY, out_white_xy) @ self.camera_to_pcs(white_xy)

    def white_info(self, white_xy, neutral=None, n_iter=None, converged=None):
        g, temp, tint = self.weight(white_xy)
        return {"white_xy": [float(white_xy[0]), float(white_xy[1])], "cct_K": temp, "tint": tint,
                "weight_cm_low_T": g, "calibration_K": self.T, "illuminants": self.illuminant,
                "neutral": None if neutral is None else [float(v) for v in neutral],
                "iterations": n_iter, "converged": converged}


class _OneMatrix:
    """View of a Dng exposing only calibration k (for DngColour(matrix='cm1'/'cm2'))."""

    def __init__(self, dng, k):
        self.color_matrix = [dng.color_matrix[k], None]
        self.camera_calibration = [dng.camera_calibration[k], None]
        self.forward_matrix = [dng.forward_matrix[k], None]
        self.illuminant = [dng.illuminant[k], 0]
        self.analog_balance = dng.analog_balance


def white_from_neutral(col, neutral):
    n = np.asarray(neutral, float)
    n = n / n.max()
    xy, k, ok = col.neutral_to_xy(n)
    return xy, col.white_info(xy, n, k, ok)


def as_shot_white(dng, col):
    if dng.as_shot_neutral is not None:
        return white_from_neutral(col, dng.as_shot_neutral)
    if dng.as_shot_white_xy is not None:
        xy = dng.as_shot_white_xy
        return xy, col.white_info(xy)
    raise ValueError("DNG has neither AsShotNeutral nor AsShotWhiteXY")


def in_frame_neutral(cams):
    """Mean G-normalised camera RGB of neutral ROIs (each ROI weighted equally)."""
    c = np.array([np.asarray(v, float) / v[1] for v in cams])
    return c.mean(0), c


def propagate_se(M, se):
    """XYZ standard error from per-channel camera standard errors (channels independent)."""
    return np.sqrt((np.asarray(M) ** 2) @ (np.asarray(se, float) ** 2))


# ----------------------------------------------------------------- whole-frame helper

class DngScene:
    """One DNG + its JPEG: mapping (verified), ROI stats, both white references."""

    def __init__(self, dng_path, jpeg_path=None, jpeg_rgb=None, verify=True, auto_offset=True, max_offset_px=8,
                 matrix="interp"):
        self.dng = Dng(dng_path)
        self.col = DngColour(self.dng, matrix)
        if jpeg_path is not None:
            jinfo = jpeg_info(jpeg_path)
        elif jpeg_rgb is not None:
            jinfo = {"size_wh": [int(jpeg_rgb.shape[1]), int(jpeg_rgb.shape[0])], "orientation": 1}
        else:
            jinfo = {"size_wh": list(self.dng.crop_size), "orientation": self.dng.orientation}
        self.jpeg_path = None if jpeg_path is None else Path(jpeg_path)
        self.jpeg_info = jinfo
        self.map = RawMap(self.dng, jinfo["size_wh"], jinfo["orientation"])
        self.verify = None
        if verify and (jpeg_rgb is not None or jpeg_path is not None):
            if jpeg_rgb is None:
                from PIL import Image
                with Image.open(jpeg_path) as im:
                    jpeg_rgb = np.asarray(im.convert("RGB"))
            v = verify_mapping(self.dng, jpeg_rgb, self.map)
            if v.get("ok") and auto_offset:
                off = v["suggested_integer_offset_xy"]
                if max(abs(off[0]), abs(off[1])) > max_offset_px:
                    raise ValueError(f"{self.dng.path.name}: JPEG/raw offset {off} px exceeds {max_offset_px}")
                if off != [0, 0]:
                    self.map = RawMap(self.dng, jinfo["size_wh"], jinfo["orientation"], off)
                    v["after_offset"] = {k: w for k, w in verify_mapping(self.dng, jpeg_rgb, self.map).items()
                                         if k != "tiles"}
            self.verify = v
        self.white_as_shot, self.white_as_shot_info = as_shot_white(self.dng, self.col)

    def stats(self, region):
        ys, xs = roi_pixels(self.map, region)
        return cfa_stats(self.dng, ys, xs)

    def white_in_frame(self, cams):
        n, each = in_frame_neutral(cams)
        xy, info = white_from_neutral(self.col, n)
        info["members_g_normalised"] = each.tolist()
        info["member_spread_rb_sd"] = [float(each[:, 0].std()), float(each[:, 2].std())]
        return xy, info

    def xyz(self, cam, white_xy, se=None):
        """XYZ (D65-adapted, camera scale) and its standard error for camera RGB `cam` under white_xy."""
        M = self.col.camera_to_xyz(white_xy)
        xyz = M @ np.asarray(cam, float)
        return xyz, (None if se is None else propagate_se(M, se))


# ----------------------------------------------------------------- synthetic DNG writer (tests)

def _tiff_entry(tag, typ, values, e=">"):
    if typ == 2:
        raw = values.encode("ascii") + b"\0"
        return tag, typ, len(raw), raw
    if typ in (5, 10):
        parts = []
        for v in values:
            den = 1000000 if typ == 5 else 10000
            parts.extend((int(round(v * den)), den))
        fmt = e + ("I" if typ == 5 else "i") * len(parts)
        return tag, typ, len(values), struct.pack(fmt, *parts)
    fmt = {1: "B", 3: "H", 4: "I", 7: "B", 8: "h", 9: "i"}[typ]
    return tag, typ, len(values), struct.pack(e + fmt * len(values), *values)


def _write_ifd(entries, data_at, e=">"):
    """Serialise one IFD; out-of-line data starts at data_at. Returns (ifd_bytes, data_bytes)."""
    entries = sorted(entries, key=lambda t: t[0])
    ifd = bytearray(struct.pack(e + "H", len(entries)))
    data = bytearray()
    for tag, typ, count, raw in entries:
        if len(raw) <= 4:
            ifd += struct.pack(e + "HHI", tag, typ, count) + raw + b"\0" * (4 - len(raw))
        else:
            ifd += struct.pack(e + "HHII", tag, typ, count, data_at + len(data))
            data += raw
            if len(data) % 2:
                data += b"\0"
    ifd += struct.pack(e + "I", 0)
    return bytes(ifd), bytes(data)


def pack12(m):
    m = np.asarray(m, np.uint16)
    h, w = m.shape
    if w % 2:
        raise ValueError("pack12 needs an even width")
    a, b = m[:, 0::2].astype(np.uint32), m[:, 1::2].astype(np.uint32)
    out = np.empty((h, w // 2, 3), np.uint8)
    out[..., 0] = a >> 4
    out[..., 1] = ((a & 15) << 4) | (b >> 8)
    out[..., 2] = b & 255
    return out.tobytes()


def write_dng(path, mosaic, *, cfa=(0, 1, 1, 2), black=(0.0,), black_dim=(1, 1), white=4095, crop_origin=(8, 7),
              crop_size=None, as_shot_neutral=(1.0, 1.0, 1.0), cm1=None, cm2=None, illuminants=(17, 21),
              orientation=1, lin_table=None, baseline_exposure=0.0, active_area=None, exif=None):
    """Minimal big-endian DNG 1.0 (IFD0 + one 12-bit raw SubIFD [+ Exif IFD]) for synthetic tests."""
    e = ">"
    m = np.asarray(mosaic, np.uint16)
    h, w = m.shape
    rawbytes = pack12(m)
    if crop_size is None:
        aw = w if active_area is None else active_area[3] - active_area[1]
        ah = h if active_area is None else active_area[2] - active_area[0]
        crop_size = (aw - crop_origin[0], ah - crop_origin[1])

    def build(raw_at, sub_at, exif_at):
        sub = [_tiff_entry(254, 4, [0]), _tiff_entry(256, 4, [w]), _tiff_entry(257, 4, [h]), _tiff_entry(258, 3, [12]),
               _tiff_entry(259, 3, [1]), _tiff_entry(262, 3, [32803]), _tiff_entry(273, 4, [raw_at]),
               _tiff_entry(277, 3, [1]), _tiff_entry(278, 4, [h]), _tiff_entry(279, 4, [len(rawbytes)]),
               _tiff_entry(284, 3, [1]), _tiff_entry(33421, 3, [2, 2]), _tiff_entry(33422, 1, list(cfa)),
               _tiff_entry(50710, 1, [0, 1, 2]), _tiff_entry(50711, 3, [1]),
               _tiff_entry(50713, 3, list(black_dim)), _tiff_entry(50714, 5, [float(b) for b in black]),
               _tiff_entry(50717, 3, [int(white)]), _tiff_entry(50718, 5, [1.0, 1.0]),
               _tiff_entry(50719, 5, [float(crop_origin[0]), float(crop_origin[1])]),
               _tiff_entry(50720, 5, [float(crop_size[0]), float(crop_size[1])])]
        if lin_table is not None:
            sub.append(_tiff_entry(50712, 3, [int(v) for v in lin_table]))
        if active_area is not None:
            sub.append(_tiff_entry(50829, 4, [int(v) for v in active_area]))
        root = [_tiff_entry(254, 4, [1]), _tiff_entry(271, 2, "SYNTHETIC"), _tiff_entry(272, 2, "dng_scene test"),
                _tiff_entry(274, 3, [int(orientation)]), _tiff_entry(330, 4, [sub_at]),
                _tiff_entry(50706, 1, [1, 0, 0, 0]), _tiff_entry(50708, 2, "SYNTHETIC CAMERA"),
                _tiff_entry(50727, 5, [1.0, 1.0, 1.0]), _tiff_entry(50728, 5, [float(v) for v in as_shot_neutral]),
                _tiff_entry(50730, 10, [float(baseline_exposure)])]
        if cm1 is not None:
            root += [_tiff_entry(50721, 10, [float(v) for v in np.asarray(cm1).ravel()]),
                     _tiff_entry(50778, 3, [int(illuminants[0])])]
        if cm2 is not None:
            root += [_tiff_entry(50722, 10, [float(v) for v in np.asarray(cm2).ravel()]),
                     _tiff_entry(50779, 3, [int(illuminants[1])])]
        ex = None
        if exif:
            ex = [_tiff_entry(tag, typ, v) for tag, (typ, v) in exif.items()]
            root.append(_tiff_entry(34665, 4, [exif_at]))
        return root, sub, ex

    # pass 1 for sizes (all offsets are fixed width), pass 2 with final offsets
    offs = (0, 0, 0)
    for _ in range(2):
        root, sub, ex = build(*offs)
        ifd0_at = 8
        data0_at = ifd0_at + 2 + 12 * len(root) + 4
        ifd0, d0 = _write_ifd(root, data0_at, e)
        sub_at = data0_at + len(d0)
        sub_at += sub_at % 2
        data1_at = sub_at + 2 + 12 * len(sub) + 4
        ifd1, d1 = _write_ifd(sub, data1_at, e)
        exif_at = data1_at + len(d1)
        exif_at += exif_at % 2
        tail = exif_at
        if ex is not None:
            data2_at = exif_at + 2 + 12 * len(ex) + 4
            ifd2, d2 = _write_ifd(ex, data2_at, e)
            tail = data2_at + len(d2)
        raw_at = (tail + 15) // 16 * 16
        offs = (raw_at, sub_at, exif_at)
    buf = bytearray(b"MM" + struct.pack(e + "HI", 42, 8))
    buf += ifd0 + d0
    buf += b"\0" * (sub_at - len(buf))
    buf += ifd1 + d1
    if ex is not None:
        buf += b"\0" * (exif_at - len(buf))
        buf += ifd2 + d2
    buf += b"\0" * (raw_at - len(buf))
    buf += rawbytes
    Path(path).write_bytes(bytes(buf))
    return Path(path)


def mosaic_from_cam(cam_img, cfa, crop_origin_xy, raw_shape, white=4095.0, black=0.0, rng=None, noise_dn=0.0):
    """Synthetic raw plane: a crop-sized normalised camera-RGB image placed at the crop, sampled on the CFA."""
    H, W = raw_shape
    ox, oy = crop_origin_xy
    ch, cw = cam_img.shape[:2]
    pat = np.asarray(cfa, int).reshape(2, 2)
    out = np.zeros((H, W))
    yy, xx = np.meshgrid(np.arange(oy, oy + ch), np.arange(ox, ox + cw), indexing="ij")
    col = pat[yy % 2, xx % 2]
    v = np.take_along_axis(np.asarray(cam_img, float), col[..., None], axis=2)[..., 0]
    out[oy:oy + ch, ox:ox + cw] = v
    dn = black + out * (white - black)
    if rng is not None and noise_dn > 0:
        dn = dn + rng.normal(0, noise_dn, dn.shape)
    return np.clip(np.rint(dn), 0, white).astype(np.uint16)


# ----------------------------------------------------------------- self-test

INVENTED_CM_A = np.array([[0.90, -0.30, 0.02], [-0.60, 1.40, 0.25], [-0.10, 0.18, 0.70]])
INVENTED_CM_D65 = np.array([[0.75, -0.20, -0.05], [-0.80, 1.55, 0.27], [-0.15, 0.22, 0.78]])


def selftest(capture_dir=None):
    res = {}
    rng = np.random.default_rng(20261020)
    # 1. CCT
    res["cct_K"] = {name: xy_to_cct(xy)[0] for name, xy in (("D65", D65_XY), ("D50", D50_XY), ("A", A_XY))}
    # D50 here is the SDK's rounded xy (0.3457, 0.3585), about 5001 K by Robertson
    ok_cct = (abs(res["cct_K"]["D65"] - 6504) < 3 and abs(res["cct_K"]["D50"] - 5001) < 3
              and abs(res["cct_K"]["A"] - 2856) < 3)
    # 2. Bradford
    B = bradford(D50_XY, D65_XY)
    res["bradford_white_err"] = float(np.max(np.abs(B @ xy_to_xyz(D50_XY) - xy_to_xyz(D65_XY))))
    res["bradford_roundtrip_err"] = float(np.max(np.abs(bradford(D65_XY, D50_XY) @ B - np.eye(3))))
    comp = bradford(D50_XY, D65_XY) @ bradford(A_XY, D50_XY) - bradford(A_XY, D65_XY)
    res["bradford_composition_err"] = float(np.max(np.abs(comp)))
    # 3. phase correlation sign: b(p) = a(p - s) -> s
    a = np.cumsum(np.cumsum(rng.normal(size=(128, 128)), 0), 1)
    b = np.roll(np.roll(a, 3, 0), -5, 1)
    s, _ = _phase_corr(a, b)
    res["phase_corr_expected_dy_dx"] = [3, -5]
    res["phase_corr_found"] = s.tolist()
    ok_pc = abs(s[0] - 3) < 0.2 and abs(s[1] + 5) < 0.2
    # 4. orientation round trips
    pts = rng.uniform(0, 30, (2, 50))
    orr = []
    for o in range(1, 9):
        xd, yd = orient_points(o, 40, 30, pts[0], pts[1])
        xs, ys = unorient_points(o, 40, 30, xd, yd)
        orr.append(float(max(np.abs(xs - pts[0]).max(), np.abs(ys - pts[1]).max())))
    res["orientation_roundtrip_max_err"] = max(orr)
    # 5. synthetic DNG: linearization table, 2x2 black, active area, odd crop origin, another CFA phase
    SELFTEST_TMP.mkdir(parents=True, exist_ok=True)
    Hs, Ws = 64, 96
    lin = np.minimum(np.round(np.linspace(0, 16383, 4096)).astype(int) + (np.arange(4096) // 512), 16383)
    m = rng.integers(200, 3800, (Hs, Ws)).astype(np.uint16)
    black = (64.0, 66.0, 63.0, 65.0)
    pat = (1, 0, 2, 1)
    p = write_dng(SELFTEST_TMP / "lin_black.dng", m, cfa=pat, black=black, black_dim=(2, 2), white=16000,
                  crop_origin=(3, 5), crop_size=(80, 50), active_area=(2, 4, 62, 92), lin_table=lin,
                  as_shot_neutral=(0.5, 1.0, 0.7), cm1=INVENTED_CM_A, cm2=INVENTED_CM_D65)
    d = Dng(p)
    ok_raw = bool(np.array_equal(d.mosaic(), m))
    yy, xx = np.meshgrid(np.arange(Hs), np.arange(Ws), indexing="ij")
    bl = np.array(black).reshape(2, 2)[(yy - 2) % 2, (xx - 4) % 2]
    expect = (lin[m] - bl) / (16000 - bl)
    ok_lin = float(np.max(np.abs(expect - d.normalised_at(yy, xx)))) < 1e-12
    cy0, cx0, ch_, cw_ = d.crop_window()
    ok_crop = (cy0, cx0, ch_, cw_) == (2 + 5, 4 + 3, 50, 80)
    P = np.array(pat).reshape(2, 2)
    exp_phase = [[int(P[(cy0 + i - 2) % 2, (cx0 + j - 4) % 2]) for j in range(2)] for i in range(2)]
    ok_phase = d.crop_cfa_phase().tolist() == exp_phase
    rm = RawMap(d, (80, 50))
    st = cfa_stats(d, *roi_pixels(rm, {"rect": [10, 10, 30, 20]}))
    ys, xs = np.meshgrid(np.arange(10, 20) + cy0, np.arange(10, 30) + cx0, indexing="ij")
    colc = d.cfa_at(ys, xs)
    ref = [float(expect[ys, xs][colc == c].mean()) for c in range(3)]
    ok_stats = max(abs(r - g) for r, g in zip(ref, st["cam"])) < 1e-12
    mask = np.zeros((10, 20), bool)
    mask[2:8, 3:17] = True
    st_m = cfa_stats(d, *roi_pixels(rm, {"mask": mask, "origin_yx": (10, 10)}))
    st_r = cfa_stats(d, *roi_pixels(rm, {"rect": [13, 12, 27, 18]}))
    ok_mask = max(abs(a_ - b_) for a_, b_ in zip(st_m["cam"], st_r["cam"])) < 1e-12
    res["synthetic_dng"] = {"raw_roundtrip": ok_raw, "linearize_and_black": ok_lin, "crop_window": ok_crop,
                            "crop_cfa_phase": ok_phase, "rect_roi_means": ok_stats, "mask_equals_rect": ok_mask}
    # 6. colour round trip with an invented two-illuminant camera
    col = DngColour(d)
    rt = {}
    for name, wxy in (("5200K", np.array([0.3390, 0.3500])), ("A", A_XY), ("D65", D65_XY),
                      ("4000K", np.array([0.3805, 0.3768]))):
        n = col.xyz_to_camera(wxy) @ xy_to_xyz(wxy)
        n = n / n.max()
        xy, k, conv = col.neutral_to_xy(n)
        xyz_scene = rng.uniform(0.05, 0.9, (20, 3))
        cam = (col.xyz_to_camera(wxy) @ xyz_scene.T).T
        M = col.camera_to_xyz(xy)
        got = (M @ cam.T).T
        exp_ = (bradford(wxy, D65_XY) @ xyz_scene.T).T
        sc = float(np.median(got[:, 1] / exp_[:, 1]))
        rt[name] = {"white_xy_err": float(np.max(np.abs(xy - wxy))), "iterations": k, "converged": conv,
                    "xyz_rel_err_after_scale": float(np.max(np.abs(got / sc - exp_)) / np.max(exp_)),
                    "neutral_maps_to_Y": float((M @ n)[1]), "cct_K": col.weight(xy)[1]}
    res["colour_roundtrip"] = rt
    # NeutralToXY stops at |dx| + |dy| < 1e-7 (SDK), so agreement is ~1e-8, not machine precision
    ok_col = all(v["white_xy_err"] < 1e-6 and v["xyz_rel_err_after_scale"] < 1e-6
                 and abs(v["neutral_maps_to_Y"] - 1) < 1e-6 for v in rt.values())
    # 7. capture checks (read-only)
    cap = capture_checks(Path(capture_dir)) if capture_dir is not None and Path(capture_dir).exists() else {}
    res["capture"] = cap
    res["pass"] = bool(ok_cct and ok_pc and max(orr) < 1e-9 and ok_raw and ok_lin and ok_crop and ok_phase
                       and ok_stats and ok_mask and ok_col and res["bradford_white_err"] < 1e-12
                       and res["bradford_composition_err"] < 1e-12 and cap.get("pass", True))
    return res


def capture_checks(cap_dir, stem="R8051160"):
    """Repo reader agreement and stage 2e ROI agreement on a real GXR frame (read-only)."""
    out = {}
    dng_p, jpg_p = cap_dir / f"{stem}.DNG", cap_dir / f"{stem}.JPG"
    if not dng_p.exists():
        return {"skipped": f"{dng_p} not found"}
    before = {p.name: sha256_file(p) for p in (dng_p, jpg_p)}
    d = Dng(dng_p)
    ac = analyze_capture()
    crop, black, white, neutral, _ = ac.decode_raw(ac.Tiff(d.data))
    out["crop_equals_repo_decode_raw"] = bool(np.array_equal(d.crop_mosaic(), crop))
    out["black_white_neutral_equal"] = bool(black == float(d.black_pattern[0, 0]) and white == d.white
                                            and np.allclose(neutral, d.as_shot_neutral))
    out["crop_cfa_phase"] = d.crop_cfa_phase().tolist()
    m2e = ROOT / "research/stage2e_verification/local/measurements.json"
    if m2e.exists():
        fr = json.loads(m2e.read_text())["frames"][stem]
        ji = jpeg_info(jpg_p)
        rm = RawMap(d, ji["size_wh"], ji["orientation"])
        err = 0.0
        for pch in fr["patches"]:
            st = cfa_stats(d, *roi_pixels(rm, {"rect": pch["roi"]}))
            dn = np.array(st["cam"]) * (d.white - d.black_pattern[0, 0]) + d.black_pattern[0, 0]
            err = max(err, float(np.max(np.abs(dn - np.array(pch["raw_dn"])))))
        out["stage2e_raw_dn_max_abs_diff"] = err
    out["unchanged"] = before == {p.name: sha256_file(p) for p in (dng_p, jpg_p)}
    out["pass"] = bool(out["crop_equals_repo_decode_raw"] and out["black_white_neutral_equal"]
                       and out.get("stage2e_raw_dn_max_abs_diff", 0.0) < 1e-9 and out["unchanged"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--capture-dir", default=str(ROOT / "captures/a12-50/2026-10-19/stage2e-colorchecker"))
    ap.add_argument("--verify-map", help="DNG to check against its JPEG (same stem, or --jpeg)")
    ap.add_argument("--jpeg")
    args = ap.parse_args()
    if args.selftest:
        r = selftest(args.capture_dir)
        LOCAL.mkdir(parents=True, exist_ok=True)
        (LOCAL / "dng_scene_selftest.json").write_text(json.dumps(r, indent=1, default=float) + "\n")
        print(json.dumps(r, indent=1, default=float))
        print("PASS" if r["pass"] else "FAIL")
        if not r["pass"]:
            sys.exit(1)
    elif args.verify_map:
        dng = Path(args.verify_map)
        jpg = Path(args.jpeg) if args.jpeg else dng.with_suffix(".JPG")
        sc = DngScene(dng, jpg, auto_offset=False)
        v = dict(sc.verify)
        v.pop("tiles", None)
        print(json.dumps({"dng": {k: w for k, w in sc.dng.summary().items() if k != "as_shot_neutral"},
                          "map": sc.map.describe(), "verify": v}, indent=1, default=float))
    else:
        ap.error("give --selftest or --verify-map")


if __name__ == "__main__":
    main()
