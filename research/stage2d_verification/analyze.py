#!/usr/bin/env python3
"""Stage 2d colour verification. Read-only on captures and official firmware.

Writes measurements under research/stage2d_verification/ and overlays under
/tmp/gxr_stage2d_verif/. Firmware byte excerpts go in local/ only.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "color_calibration"))
from analyze_capture import Tiff, decode_raw, jpeg_tiff, shot_info  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "captures/a12-50/2026-10-19/stage2d-colorchecker"
FW = ROOT / "artifacts/firmware/gxr-1.51"
HERE = Path(__file__).resolve().parent
LOCAL = HERE / "local"
TMP = Path("/tmp/gxr_stage2d_verif")
FRAMES = (
    ("01_posi", "R8051148"),
    ("02_nega", "R8051149"),
    ("03_hcbw", "R8051150"),
    ("04_std", "R8051151"),
)
# Image row-major, chart rotated 180°: grey row on top, white at top-right.
LABELS = [
    "D6", "D5", "D4", "D3", "D2", "D1",
    "C6", "C5", "C4", "C3", "C2", "C1",
    "B6", "B5", "B4", "B3", "B2", "B1",
    "A6", "A5", "A4", "A3", "A2", "A1",
]
NEUTRAL = {"D1", "D2", "D3", "D4", "D5", "D6"}
MEMORY = {"A1", "A2", "A3", "A4"}  # dark skin, light skin, sky, foliage
# Appearance groups used by reference_analysis relative_mappings (label order D6..A1).
GROUP_LABELS = {
    "orange": ["C4", "B6", "B1"],
    "green": ["C2", "B5", "A6", "A4"],
    "blue": ["C6", "C1", "B2", "A5", "A3"],
    "red": ["C3", "B3", "A2", "A1"],
    "magenta": ["C5", "B4"],
}
MASKS = {
    "orange": (7, 8, 9, 10),
    "green": (12, 13, 14, 15, 16),
    "blue": (18, 19, 20, 21, 22),
    "red": (5, 6),
    "magenta": (1, 2, 3, 4),
}
UNMASKED = (0, 11, 17, 23)
M = np.array([[0.4124564, 0.3575761, 0.1804375],
              [0.2126729, 0.7151522, 0.0721750],
              [0.0193339, 0.1191920, 0.9503041]])
WHITE = np.array([0.95047, 1.0, 1.08883])


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def srgb_to_linear(rgb):
    rgb = np.asarray(rgb, dtype=np.float64)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def lab_from_linear(linear):
    xyz = np.asarray(linear, dtype=np.float64) @ M.T
    t = xyz / WHITE
    delta = 6 / 29
    f = np.where(t > delta ** 3, np.cbrt(t), t / (3 * delta ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                      200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_from_srgb(rgb):
    return lab_from_linear(srgb_to_linear(rgb))


def lch_of(lab):
    lab = np.asarray(lab, dtype=np.float64)
    c = np.hypot(lab[..., 1], lab[..., 2])
    h = np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) % 360
    return lab[..., 0], c, h


def wrap180(deg):
    return (np.asarray(deg, dtype=np.float64) + 180) % 360 - 180


def delta_e00(lab1, lab2):
    """CIEDE2000. Sharma 2005 test pair is asserted in main."""
    lab1 = np.asarray(lab1, dtype=np.float64)
    lab2 = np.asarray(lab2, dtype=np.float64)
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    cbar = 0.5 * (C1 + C2)
    G = 0.5 * (1 - np.sqrt((cbar ** 7) / (cbar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dhp = h2p - h1p
    both = (C1p * C2p) > 0
    dhp = np.where(both, dhp, 0.0)
    dhp = np.where(dhp > 180, dhp - 360, dhp)
    dhp = np.where(dhp < -180, dhp + 360, dhp)
    dHp = 2 * np.sqrt(np.maximum(C1p * C2p, 0)) * np.sin(np.radians(dhp) / 2)
    Lbar = 0.5 * (L1 + L2)
    Cbarp = 0.5 * (C1p + C2p)
    hsum = h1p + h2p
    habs = np.abs(h1p - h2p)
    hbar = np.where(~both, hsum,
                     np.where(habs <= 180, hsum / 2,
                              np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hbar - 30))
         + 0.24 * np.cos(np.radians(2 * hbar))
         + 0.32 * np.cos(np.radians(3 * hbar + 6))
         - 0.20 * np.cos(np.radians(4 * hbar - 63)))
    dtheta = 30 * np.exp(-((hbar - 275) / 25) ** 2)
    Rc = 2 * np.sqrt((Cbarp ** 7) / (Cbarp ** 7 + 25 ** 7))
    Sl = 1 + (0.015 * (Lbar - 50) ** 2) / np.sqrt(20 + (Lbar - 50) ** 2)
    Sc = 1 + 0.045 * Cbarp
    Sh = 1 + 0.015 * Cbarp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                   + Rt * (dCp / Sc) * (dHp / Sh))


def ab_from_ch(c, h_deg):
    rad = np.radians(h_deg)
    return c * np.cos(rad), c * np.sin(rad)


def jlaunch3_off(vma):
    return vma - 0x200F2000 + 0xA7200


def ilaunch3_off(vma, sections):
    for row in sections:
        load = int(row["load_address"])
        size = int(row["initialized_size"])
        if load <= vma < load + size:
            return int(row["file_offset"]) + (vma - load)
    raise KeyError(hex(vma))


def load_sections(path):
    rows = []
    lines = path.read_text().splitlines()
    header = lines[0].split(",")
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        rows.append(dict(zip(header, parts)))
    return rows


def read_curve(blob, a_vma, b_vma):
    a = struct.unpack(">31H", blob[jlaunch3_off(a_vma):jlaunch3_off(a_vma) + 62])
    b = list(blob[jlaunch3_off(b_vma):jlaunch3_off(b_vma) + 33])
    xs = np.array([0, *a, 4095], dtype=np.float64)
    ys = np.array(b, dtype=np.float64)
    return xs, ys


def apply_curve(xs, ys, code):
    return np.interp(np.clip(code, 0, 4095), xs, ys)


def decode_coeff(word_bytes):
    def dec(v):
        return v if v < 128 else -(v - 128)
    a, b, bx, a2 = word_bytes
    if (bx ^ 0x80) != b or a2 != a:
        raise ValueError(word_bytes.hex())
    return dec(a), dec(b)


def encode_coeff(a, b):
    def enc(v):
        v = int(np.clip(np.rint(v), -127, 127))
        return (abs(v) | 0x80) if v < 0 else v
    A, B = enc(a), enc(b)
    return bytes((A, B, B ^ 0x80, A)), int(np.rint(a)) != A and False


def coeff_ab(a, b):
    """Return encoded bytes and the clipped a,b actually stored."""
    def enc_pair(v):
        r = int(np.clip(np.rint(v), -127, 127))
        return r, (abs(r) | 0x80) if r < 0 else r
    ar, A = enc_pair(a)
    br, B = enc_pair(b)
    return bytes((A, B, B ^ 0x80, A)), ar, br, (ar != int(np.rint(np.clip(a, -127, 127))))


def find_plateaus(signal, min_w, max_w, max_std, min_mean):
    sm = np.convolve(signal, np.ones(9) / 9, mode="same")
    deriv = np.abs(np.diff(sm, prepend=sm[0]))
    flat = deriv < 1.4
    out = []
    i, n = 0, len(flat)
    while i < n:
        if not flat[i]:
            i += 1
            continue
        j = i
        while j < n and flat[j]:
            j += 1
        if min_w <= j - i <= max_w:
            seg = sm[i:j]
            if seg.std() <= max_std and seg.mean() >= min_mean:
                out.append(((i + j) // 2, float(seg.mean()), j - i))
        i = j
    return out


def cluster_1d(values, gap):
    values = sorted(values)
    groups = [[values[0]]]
    for v in values[1:]:
        if v - groups[-1][-1] <= gap:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [float(np.median(g)) for g in groups]


def detect_grid(rgb):
    """Return 24 (x, y, half) patch centers. half is the ROI half-size in pixels."""
    L = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    h, w = L.shape
    xs = []
    for y0 in range(800, 2400, 50):
        band = L[y0:y0 + 60].mean(0)
        # min_mean stays low: Positive crushes dark patches toward the gutter.
        for cx, mean, width in find_plateaus(band, 250, 620, 8.0, 8):
            if 200 < cx < w - 40:
                xs.append(cx)
    cols = cluster_1d(xs, 90)
    scored = []
    for c in cols:
        n = sum(1 for x in xs if abs(x - c) <= 90)
        if n >= 10:
            scored.append(c)
    scored.sort()
    if len(scored) < 6:
        raise RuntimeError(f"expected at least 6 columns, got {scored}")
    best = None
    for i in range(len(scored) - 5):
        window = scored[i:i + 6]
        gaps = np.diff(window)
        if not (400 <= float(np.median(gaps)) <= 750):
            continue
        score = float(np.std(gaps))
        # The white table sits past the card. Prefer the tighter window.
        if best is None or score < best[0]:
            best = (score, window)
    if best is None:
        raise RuntimeError(f"no regular 6-column window in {scored}")
    cols = best[1]
    # Row centers from the brighter columns (skip a merged black column).
    ys = []
    for cx in cols[1:]:
        col = L[:, int(cx) - 12:int(cx) + 12].mean(1)
        for cy, mean, width in find_plateaus(col, 250, 620, 10.0, 8):
            if 250 < cy < h - 80:
                ys.append(cy)
    rows = cluster_1d(ys, 80)
    rvotes = []
    for r in rows:
        rvotes.append((sum(1 for y in ys if abs(y - r) <= 80), r))
    rvotes.sort(reverse=True)
    rows = sorted(r for _, r in rvotes[:4])
    if len(rows) != 4:
        raise RuntimeError(f"expected 4 rows, got {rows}")
    # Perspective: x shifts slightly with row. Measure per-row column centers
    # where the row is bright enough, else keep the global column.
    col_at = []
    for ry in rows:
        found = []
        band = L[int(ry) - 30:int(ry) + 30].mean(0)
        plats = find_plateaus(band, 250, 620, 8.0, 8)
        for gx in cols:
            near = [p for p in plats if abs(p[0] - gx) < 70]
            found.append(float(near[0][0]) if near else float(gx))
        col_at.append(found)
    row_at = []
    for cx in cols:
        found = []
        col = L[:, int(cx) - 12:int(cx) + 12].mean(1)
        plats = find_plateaus(col, 250, 620, 10.0, 8)
        for gy in rows:
            near = [p for p in plats if abs(p[0] - gy) < 70]
            found.append(float(near[0][0]) if near else float(gy))
        row_at.append(found)
    pitch_x = float(np.median(np.diff(cols)))
    pitch_y = float(np.median(np.diff(rows)))
    half = int(round(0.16 * min(pitch_x, pitch_y)))
    centers = []
    for r in range(4):
        for c in range(6):
            centers.append((col_at[r][c], row_at[c][r], half))
    return centers, {"columns": cols, "rows": rows, "pitch_x": pitch_x, "pitch_y": pitch_y, "half": half}


def cfa_means(crop, y0, y1, x0, x1, oy, ox):
    roi = crop[y0:y1, x0:x1].astype(np.float64)
    yy = np.arange(y0, y1)[:, None]
    xx = np.arange(x0, x1)[None, :]
    pr = (yy + oy) & 1
    pc = (xx + ox) & 1
    # cfa [[R, G], [G, B]] at even/odd crop+origin, matching G/B/R/G at (8, 7).
    code = np.where(pr == 0, np.where(pc == 0, 0, 1), np.where(pc == 0, 1, 2))
    out = []
    for k in range(3):
        sel = code == k
        out.append(float(roi[sel].mean()) if sel.any() else float("nan"))
    return out


def sample_frame(stem, crop, oy, ox, jpeg, centers):
    patches = []
    h, w = jpeg.shape[:2]
    for i, (cx, cy, half) in enumerate(centers):
        x0 = int(round(cx - half))
        x1 = int(round(cx + half))
        y0 = int(round(cy - half))
        y1 = int(round(cy + half))
        if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
            raise RuntimeError(f"ROI outside frame {stem} {LABELS[i]}")
        raw = cfa_means(crop, y0, y1, x0, x1, oy, ox)
        block = jpeg[y0:y1, x0:x1]
        mean = block.mean(axis=(0, 1)) / 255.0
        std = block.reshape(-1, 3).std(axis=0)
        lab = lab_from_srgb(mean)
        L, C, H = lch_of(lab)
        patches.append({
            "label": LABELS[i],
            "index": i,
            "center_xy": [round(cx, 1), round(cy, 1)],
            "roi": [x0, y0, x1, y1],
            "raw_dn": raw,
            "jpeg_srgb": mean.tolist(),
            "jpeg_std": std.tolist(),
            "lab": lab.tolist(),
            "L": float(L), "C": float(C), "h": float(H),
        })
    return patches


def check_mapping(patches, monochrome=False):
    greys = patches[:6]
    Ls = [p["L"] for p in greys]
    Cs = [p["C"] for p in greys]
    if not all(Cs[i] < 18 for i in range(6)):
        raise RuntimeError(f"top row is not neutral: C={Cs}")
    # Positive's toe crushes the two darkest greys to within a code of each other.
    if not (Ls[-1] > Ls[0] + 30 and Ls[-1] == max(Ls) and all(Ls[i + 1] + 1.5 >= Ls[i] for i in range(5))):
        raise RuntimeError(f"grey row is not dark-to-white: L={Ls}")
    if monochrome:
        chroma = [p["C"] for p in patches]
        if max(chroma) > 12:
            raise RuntimeError(f"B&W frame still has chroma {max(chroma):.1f}")
        return
    # Second image row is cyan, magenta, yellow, red, green, blue.
    hues = [p["h"] for p in patches[6:12]]
    # Yellow (index 2 of this row) should be the highest b, blue the lowest b.
    bs = [p["lab"][2] for p in patches[6:12]]
    if int(np.argmax(bs)) != 2 or int(np.argmin(bs)) != 5:
        raise RuntimeError(f"primary row hue order failed, b={bs} h={hues}")
    # Bottom-right is dark skin: positive a and b, darker than light skin on its left.
    dark, light = patches[23], patches[22]
    if not (dark["lab"][1] > 5 and dark["lab"][2] > 3 and dark["L"] + 5 < light["L"]):
        raise RuntimeError(f"bottom-right is not dark skin: {dark['lab']} vs light {light['lab']}")


def draw_overlay(jpeg_u8, patches, path):
    im = Image.fromarray(jpeg_u8).resize((1072, 712), Image.Resampling.BOX)
    scale = 1072 / jpeg_u8.shape[1]
    draw = ImageDraw.Draw(im)
    for p in patches:
        x0, y0, x1, y1 = p["roi"]
        box = [x0 * scale, y0 * scale, x1 * scale, y1 * scale]
        draw.rectangle(box, outline=(255, 40, 40))
        draw.text((box[0] + 2, box[1] + 2), p["label"], fill=(255, 255, 0))
    im.save(path, quality=85)


def load_gr():
    text = (ROOT / "research/color_references/gr3_chart_targets.csv").read_text().splitlines()
    header = text[0].split(",")
    out = {}
    for line in text[1:]:
        if not line.strip():
            continue
        rec = dict(zip(header, line.split(",")))
        mode = rec["mode"]
        out.setdefault(mode, {})[rec["patch"]] = {
            "L": float(rec["target_L"]),
            "a": float(rec["target_a"]),
            "b": float(rec["target_b"]),
            "jpeg": [float(rec["jpeg_R"]), float(rec["jpeg_G"]), float(rec["jpeg_B"])],
        }
    for mode, patches in out.items():
        for lab in patches.values():
            L, C, H = lch_of([lab["L"], lab["a"], lab["b"]])
            lab["C"] = float(C)
            lab["h"] = float(H)
    return out


def group_of(label):
    for name, labels in GROUP_LABELS.items():
        if label in labels:
            return name
    return "neutral" if label in NEUTRAL else "other"


def med(xs):
    return float(np.median(xs)) if len(xs) else None


def summarize_de(pairs):
    """pairs: list of (group, de)."""
    buckets = {"neutral": [], "memory": [], "rest": [], "all": []}
    for label, de in pairs:
        buckets["all"].append(de)
        if label in NEUTRAL:
            buckets["neutral"].append(de)
        elif label in MEMORY:
            buckets["memory"].append(de)
        else:
            buckets["rest"].append(de)
    return {k: {"n": len(v), "median": med(v), "mean": float(np.mean(v)) if v else None,
                "p90": float(np.percentile(v, 90)) if v else None} for k, v in buckets.items()}


def firmware_checks():
    j3 = (FW / "jlaunch3").read_bytes()
    i3 = (FW / "ilaunch3").read_bytes()
    j8 = (FW / "jlaunch8").read_bytes()
    sections = load_sections(ROOT / "research/firmware/ilaunch3-sections.csv")
    colour = j3[jlaunch3_off(0x2012C5D4):jlaunch3_off(0x2012C5D4) + 96]
    tone_a = j3[jlaunch3_off(0x2012F504):jlaunch3_off(0x2012F504) + 62]
    tone_b = j3[jlaunch3_off(0x2012FFFC):jlaunch3_off(0x2012FFFC) + 33]
    row20_a = j3[jlaunch3_off(0x2012F8A6):jlaunch3_off(0x2012F8A6) + 62]
    row20_b = j3[jlaunch3_off(0x201301EB):jlaunch3_off(0x201301EB) + 33]
    # Contrast display 5 loads T+0x2418: lduh r10,@(9240,r2) = aa b2 24 18.
    off_e900 = jlaunch3_off(0x2010E900)
    insn = j3[off_e900:off_e900 + 4]
    # Standard commit: ldi r4,#1 -> jl r0 = 64 01 1e c0.
    off_std = ilaunch3_off(0x202BB9D8, sections)
    std_insn = i3[off_std:off_std + 4]
    # Setter writes only S+0x36E. 878 = 0x36E. Confirm the nearby stb encoding
    # already cited, by reading the documented setter bytes.
    off_set = ilaunch3_off(0x20268774, sections)
    setter = i3[off_set:off_set + 4]
    script = j8[0xBF00:0xC080]
    v2418 = script.find(b"V2418\r\nW0500")
    # 24 still colour selectors T+0x126C .. T+0x129A step 2, all W0101.
    colour_sel = []
    start = j8.find(b"V126C\r\n")
    blob = j8[start:start + 400]
    for k in range(24):
        addr = 0x126C + 2 * k
        token = f"V{addr:04X}\r\nW".encode()
        at = blob.find(token)
        if at < 0:
            # jlaunch8 script uses the case of the original; try both.
            token = f"V{addr:04X}\r\nW".encode()
        word = blob[at + len(token):at + len(token) + 4] if at >= 0 else b""
        colour_sel.append({"T": f"0x{addr:04X}", "word": word.decode() if word else None})
    words = [decode_coeff(colour[i:i + 4]) for i in range(0, 96, 4)]
    (LOCAL / "official_rows.json").write_text(json.dumps({
        "colour_row1_hex": colour.hex(),
        "tone_row5_A_hex": tone_a.hex(),
        "tone_row5_B_hex": tone_b.hex(),
        "tone_row20_A_hex": row20_a.hex(),
        "tone_row20_B_hex": row20_b.hex(),
        "note": "Copied from official jlaunch3. Gitignored.",
    }, indent=2) + "\n")
    return {
        "jlaunch3_sha256": sha256(FW / "jlaunch3"),
        "ilaunch3_sha256": sha256(FW / "ilaunch3"),
        "jlaunch8_sha256": sha256(FW / "jlaunch8"),
        "contrast5_insn_file": hex(off_e900),
        "contrast5_insn_hex": insn.hex(),
        "contrast5_is_lduh_T_2418": insn == bytes.fromhex("aab22418"),
        "standard_commit_file": hex(off_std),
        "standard_commit_hex": std_insn.hex(),
        "standard_commit_is_ldi_r4_1": std_insn == bytes.fromhex("64011ec0"),
        "setter_file": hex(off_set),
        "setter_hex": setter.hex(),
        "jlaunch8_V2418_W0500_found": v2418 >= 0,
        "colour_selectors_from_126C": colour_sel,
        "colour_selectors_all_0101": all(x["word"] == "0101" for x in colour_sel),
        "stock_coeffs_ab": words,
        "curves": {
            "row5": read_curve(j3, 0x2012F504, 0x2012FFFC),
            "row20": read_curve(j3, 0x2012F8A6, 0x201301EB),
        },
    }


def injected_curves():
    """Our stage-2d curves, from the gitignored generator output. Not firmware bytes."""
    text = (ROOT / "firmware/stage2d_phase1/deep_tables.c").read_text()

    def grab(name):
        at = text.find(f"static const uint8_t {name}[]")
        body = text[at:text.find("};", at)]
        hexs = [int(x, 16) for x in body.split("{", 1)[1].replace("\n", " ").split(",") if x.strip()]
        return bytes(hexs)

    def curve_from(a_bytes, b_bytes):
        nodes = struct.unpack(">" + "H" * (len(a_bytes) // 2), a_bytes)
        xs = np.array([0, *nodes, 4095], dtype=np.float64)
        ys = np.array(list(b_bytes), dtype=np.float64)
        return xs, ys

    return {
        "stock": curve_from(grab("table_0_0"), grab("table_0_1")),
        "posi": curve_from(grab("table_1_0"), grab("table_1_1")),
        "nega": curve_from(grab("table_0_0"), grab("table_2_1")),
        "hc": curve_from(grab("table_3_0"), grab("table_3_1")),
    }


def hue_tables():
    data = json.loads((ROOT / "research/color_calibration/firmware_parameters.json").read_text())
    return (np.array(data["normal_sector_hue_d0"], dtype=np.int16),
            np.array(data["normal_sector_hue_d1"], dtype=np.int16),
            np.array(data["normal_sector_saturation_k_percent"], dtype=np.int16))


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    de_test = float(delta_e00([50, 2.6772, -79.7751], [50, 0, -82.7485]))
    if abs(de_test - 2.0425) > 1e-3:
        raise SystemExit(f"CIEDE2000 self-test failed: {de_test}")
    fw = firmware_checks()
    injected = injected_curves()
    # Stock row in the injected tables must be the official row, or the camera
    # would have refused the write. Compare and record.
    stock_a = struct.pack(">" + "H" * 31, *injected["stock"][0][1:-1].astype(int))
    official_a = bytes.fromhex(json.loads((LOCAL / "official_rows.json").read_text())["tone_row5_A_hex"])
    official_colour = bytes.fromhex(json.loads((LOCAL / "official_rows.json").read_text())["colour_row1_hex"])
    fw["injected_stock_A_matches_official"] = stock_a == official_a
    d0, d1, kperc = hue_tables()
    gr = load_gr()
    frames = {}
    centers0 = None
    for key, stem in FRAMES:
        jpg_path = CAP / f"{stem}.JPG"
        dng_path = CAP / f"{stem}.DNG"
        jpeg = np.asarray(Image.open(jpg_path).convert("RGB"))
        tiff = Tiff(dng_path.read_bytes())
        info = shot_info(jpeg_tiff(jpg_path))
        dinfo = shot_info(tiff)
        if info["color_raw_13"] != dinfo["color_raw_13"] or info["profile_record_selector"] != dinfo["profile_record_selector"]:
            raise SystemExit(f"{stem} DNG/JPEG maker mismatch")
        crop, black, white, neutral, stats = decode_raw(tiff)
        if crop.shape[0] != jpeg.shape[0] or crop.shape[1] != jpeg.shape[1]:
            raise SystemExit(f"{stem} crop/jpeg shape {crop.shape} {jpeg.shape}")
        centers, geom = detect_grid(jpeg.astype(np.float32))
        patches = sample_frame(stem, crop, stats["crop_origin_xy"][1], stats["crop_origin_xy"][0],
                                jpeg.astype(np.float64), centers)
        check_mapping(patches, monochrome=info["profile_record_selector"] == 3)
        asn = np.array(neutral, dtype=np.float64)
        for p in patches:
            dn = np.array(p["raw_dn"], dtype=np.float64)
            cam = (dn - black) / (white - black)
            p["camera_rgb"] = cam.tolist()
            p["camera_rgb_wb"] = (cam / asn).tolist()
            p["u"] = float((cam / asn) @ np.array([0.25, 0.5, 0.25]))
        draw_overlay(jpeg, patches, TMP / f"overlay_{stem}.jpg")
        frames[key] = {
            "file": stem,
            "selector": info["profile_record_selector"],
            "display": info["color_display"],
            "raw13": info["color_raw_13"],
            "asn": asn.tolist(),
            "exposure": {"iso": info["iso"], "t": info["exposure_seconds"], "f": info["f_number"],
                         "when": info["date_time"]},
            "geometry": geom,
            "patches": patches,
        }
        if centers0 is None:
            centers0 = centers
        else:
            shift = [abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(centers, centers0)]
            frames[key]["max_center_shift_from_01_px"] = float(max(shift))
    # Von Kries of each frame's JPEG onto frame 04's neutral mean, in linear sRGB.
    def neutral_white(frame):
        # Mid greys only. Black and white are where the tone curve, not the WB, dominates.
        cols = [srgb_to_linear(p["jpeg_srgb"]) for p in frame["patches"] if p["label"] in {"D4", "D3", "D2"}]
        return np.mean(cols, axis=0)
    white04 = neutral_white(frames["04_std"])
    for key, frame in frames.items():
        src = neutral_white(frame)
        # Chromaticity only. A full-vector gain would cancel the tone curve's lightness.
        gain = (white04 / white04.mean()) / (src / src.mean())
        frame["wb_gain_to_04"] = gain.tolist()
        for p in frame["patches"]:
            lin = srgb_to_linear(p["jpeg_srgb"]) * gain
            lab = lab_from_linear(lin)
            L, C, H = lch_of(lab)
            p["lab_wb"] = lab.tolist()
            p["L_wb"] = float(L)
            p["C_wb"] = float(C)
            p["h_wb"] = float(H)
    # Tone check on the six greys: JPEG Rec.709 vs the curve that was injected.
    curve_for = {"01_posi": injected["posi"], "02_nega": injected["nega"],
                 "03_hcbw": injected["hc"], "04_std": fw["curves"]["row5"]}
    tone_check = {}
    for key, frame in frames.items():
        xs, ys = curve_for[key]
        errs = []
        for p in frame["patches"]:
            if p["label"] not in NEUTRAL:
                continue
            pred = float(apply_curve(xs, ys, p["u"] * 4095))
            jpeg_y = float(np.dot(p["jpeg_srgb"], [0.2126, 0.7152, 0.0722]) * 255)
            p["jpeg_y"] = jpeg_y
            p["curve_y"] = pred
            errs.append(pred - jpeg_y)
        tone_check[key] = {"grey_curve_minus_jpeg": errs,
                           "median_abs": float(np.median(np.abs(errs))),
                           "max_abs": float(np.max(np.abs(errs)))}
    # GR comparison on WB-adapted Lab.
    def by_label(frame):
        return {p["label"]: p for p in frame["patches"]}
    g04 = by_label(frames["04_std"])
    comparisons = {}
    for mode, gr_mode, gxr_key in (("positive", "positive", "01_posi"), ("negative", "negative", "02_nega")):
        gxr = by_label(frames[gxr_key])
        rows = []
        pred_full, pred_tone, pred_colour = [], [], []
        for label in LABELS:
            a = gxr[label]
            b = g04[label]
            gs = gr["standard"][label]
            gm = gr[gr_mode][label]
            dL_gxr = a["L_wb"] - b["L_wb"]
            dL_gr = gm["L"] - gs["L"]
            # Chroma ratio and hue are unstable on neutrals. Record them, and
            # use additive a*, b* for the neutral prediction.
            ratio_gxr = a["C_wb"] / b["C_wb"] if b["C_wb"] > 1 else None
            ratio_gr = gm["C"] / gs["C"] if gs["C"] > 1 else None
            dh_gxr = float(wrap180(a["h_wb"] - b["h_wb"])) if min(a["C_wb"], b["C_wb"]) > 8 else None
            dh_gr = float(wrap180(gm["h"] - gs["h"])) if min(gm["C"], gs["C"]) > 8 else None
            # Full transfer of the GR delta onto GXR 04.
            if label in NEUTRAL or gs["C"] < 8 or b["C_wb"] < 8:
                Lp = b["L_wb"] + dL_gr
                ap = b["lab_wb"][1] + (gm["a"] - gs["a"])
                bp = b["lab_wb"][2] + (gm["b"] - gs["b"])
                Lt, at, bt = b["L_wb"] + dL_gr, b["lab_wb"][1], b["lab_wb"][2]
                Lc, ac, bc = b["L_wb"], ap, bp
            else:
                Lp = b["L_wb"] + dL_gr
                Cp = b["C_wb"] * (gm["C"] / gs["C"])
                hp = (b["h_wb"] + float(wrap180(gm["h"] - gs["h"]))) % 360
                ap, bp = ab_from_ch(Cp, hp)
                Lt, at, bt = Lp, b["lab_wb"][1], b["lab_wb"][2]
                Lc = b["L_wb"]
                ac, bc = ab_from_ch(Cp, hp)
            actual = a["lab_wb"]
            de_full = float(delta_e00(actual, [Lp, ap, bp]))
            de_tone = float(delta_e00(actual, [Lt, at, bt]))
            de_col = float(delta_e00(actual, [Lc, ac, bc]))
            de_pair = float(delta_e00(actual, b["lab_wb"]))
            pred_full.append((label, de_full))
            pred_tone.append((label, de_tone))
            pred_colour.append((label, de_col))
            rows.append({
                "label": label, "group": group_of(label),
                "dL_gxr": dL_gxr, "dL_gr": dL_gr, "dL_minus": dL_gxr - dL_gr,
                "chroma_ratio_gxr": ratio_gxr, "chroma_ratio_gr": ratio_gr,
                "hue_gxr": dh_gxr, "hue_gr": dh_gr,
                "hue_minus": None if dh_gxr is None or dh_gr is None else dh_gxr - dh_gr,
                "de00_pair": de_pair, "de00_full": de_full, "de00_tone_only": de_tone,
                "de00_colour_only": de_col,
                "gxr_L": a["L_wb"], "std_L": b["L_wb"], "gxr_C": a["C_wb"], "std_C": b["C_wb"],
            })
        comparisons[mode] = {
            "patches": rows,
            "de00_full": summarize_de(pred_full),
            "de00_tone_only": summarize_de(pred_tone),
            "de00_colour_only": summarize_de(pred_colour),
            "de00_observed_pair": summarize_de([(r["label"], r["de00_pair"]) for r in rows]),
        }
    # Baseline: hue display 5 vs 4 at k=100. Display 5 is index 4, display 4 is index 3.
    stock = fw["stock_coeffs_ab"]
    level5, level4 = 4, 3
    baseline_sectors = []
    for s, (a, b) in enumerate(stock):
        # k=100, so a' = d0 + a, b' = b + d1.
        a5, b5 = a + int(d0[level5, s]), b + int(d1[level5, s])
        a4, b4 = a + int(d0[level4, s]), b + int(d1[level4, s])
        s5, s4 = float(np.hypot(a5, b5)), float(np.hypot(a4, b4))
        th5 = float(np.degrees(np.arctan2(b5, a5)))
        th4 = float(np.degrees(np.arctan2(b4, a4)))
        baseline_sectors.append({
            "sector": s,
            "mask": next((n for n, ix in MASKS.items() if s in ix), None),
            "da": int(d0[level5, s] - d0[level4, s]),
            "db": int(d1[level5, s] - d1[level4, s]),
            "scale_ratio_5_over_4": s5 / s4 if s4 else None,
            "angle_deg_5_minus_4": float(wrap180(th5 - th4)),
        })
    # Empirical split: O/G patches share hue 5 on both frames. B/R/M do not.
    affected = set(GROUP_LABELS["blue"] + GROUP_LABELS["red"] + GROUP_LABELS["magenta"])
    unaffected = set(GROUP_LABELS["orange"] + GROUP_LABELS["green"])
    baseline_emp = {}
    for mode in ("positive", "negative"):
        rows = comparisons[mode]["patches"]
        def take(labels, field):
            return [r[field] for r in rows if r["label"] in labels and r[field] is not None]
        baseline_emp[mode] = {
            "unaffected_OG_hue_minus_median": med(take(unaffected, "hue_minus")),
            "affected_BRM_hue_minus_median": med(take(affected, "hue_minus")),
            "unaffected_OG_de_colour_median": med([r["de00_colour_only"] for r in rows if r["label"] in unaffected]),
            "affected_BRM_de_colour_median": med([r["de00_colour_only"] for r in rows if r["label"] in affected]),
            "neutral_de_pair_median": med([r["de00_pair"] for r in rows if r["label"] in NEUTRAL]),
        }
    # Colour fit. Group medians from GR, applied as one similarity per mask.
    def gr_delta(mode, label):
        gs, gm = gr["standard"][label], gr[mode][label]
        ratio = gm["C"] / gs["C"] if gs["C"] > 8 else 1.0
        dh = float(wrap180(gm["h"] - gs["h"])) if min(gm["C"], gs["C"]) > 8 else 0.0
        return ratio, dh, gm["L"] - gs["L"]
    group_target = {}
    for mode in ("positive", "negative"):
        group_target[mode] = {}
        for name, labels in GROUP_LABELS.items():
            ratios, dhs = [], []
            for label in labels:
                ratio, dh, _ = gr_delta(mode, label)
                ratios.append(ratio)
                dhs.append(dh)
            group_target[mode][name] = {"chroma_ratio_median": med(ratios),
                                        "hue_deg_median": med(dhs),
                                        "chroma_ratio_span": [min(ratios), max(ratios)],
                                        "hue_deg_span": [min(dhs), max(dhs)]}
    def build_row(mode, per_sector_r_phi):
        words = []
        clipped = []
        for s, (a, b) in enumerate(stock):
            r, phi = per_sector_r_phi[s]
            scale = float(np.hypot(a, b))
            theta = float(np.arctan2(b, a))
            # Matrix rotates by -theta. Additional Lab-hue +phi means new_theta = theta - phi.
            ns = scale * r
            nt = theta - np.radians(phi)
            na, nb = ns * np.cos(nt), ns * np.sin(nt)
            raw, ar, br, _ = coeff_ab(na, nb)
            if abs(ar - na) > 0.6 or abs(br - nb) > 0.6:
                clipped.append(s)
            words.append(raw.hex())
        return words, clipped
    candidates = {}
    residuals = {}
    for mode in ("positive", "negative"):
        rphi = []
        for s in range(24):
            name = next((n for n, ix in MASKS.items() if s in ix), None)
            if name is None:
                rphi.append((1.0, 0.0))
            else:
                t = group_target[mode][name]
                rphi.append((t["chroma_ratio_median"], t["hue_deg_median"]))
        words, clipped = build_row(mode, rphi)
        # Residual of one similarity per group versus each patch's own GR delta,
        # applied to GXR 04. L* uses the GR lightness delta in both, so the
        # difference is only the chroma/hue quantisation.
        gxr04 = by_label(frames["04_std"])
        pair_de, hue_only_de, chroma_only_de, leak = [], [], [], []
        for label in LABELS:
            src = gxr04[label]
            ratio, dh, dL = gr_delta(mode, label)
            name = group_of(label)
            if name in group_target[mode]:
                gratio = group_target[mode][name]["chroma_ratio_median"]
                gdh = group_target[mode][name]["hue_deg_median"]
            else:
                gratio, gdh = 1.0, 0.0
            L = src["L_wb"] + dL
            def lab_of(rr, hh):
                if src["C_wb"] < 8 or label in NEUTRAL:
                    return [L, src["lab_wb"][1], src["lab_wb"][2]]
                aa, bb = ab_from_ch(src["C_wb"] * rr, (src["h_wb"] + hh) % 360)
                return [L, aa, bb]
            ideal = lab_of(ratio, dh)
            grouped = lab_of(gratio, gdh)
            hue_only = lab_of(1.0, gdh)
            chroma_only = lab_of(gratio, 0.0)
            pair_de.append((label, float(delta_e00(ideal, grouped))))
            hue_only_de.append((label, float(delta_e00(ideal, hue_only))))
            chroma_only_de.append((label, float(delta_e00(ideal, chroma_only))))
            # Lightness the neutral tone curve does not explain.
            # Interpolate GR neutral ΔL against GR standard L.
            neut = sorted((gr["standard"][n]["L"], gr[mode][n]["L"] - gr["standard"][n]["L"])
                          for n in ("D6", "D5", "D4", "D3", "D2", "D1"))
            nx, ny = np.array([p[0] for p in neut]), np.array([p[1] for p in neut])
            tone_dL = float(np.interp(gr["standard"][label]["L"], nx, ny))
            leak.append((label, abs(dL - tone_dL)))
        candidates[mode] = {
            "words_hex": words,
            "clipped_sectors": clipped,
            "per_sector_scale_and_hue_deg": [{"sector": i, "scale": rphi[i][0], "hue_deg": rphi[i][1],
                                              "mask": next((n for n, ix in MASKS.items() if i in ix), None)}
                                             for i in range(24)],
            "assumption": "Lab a*b* similarity, one value per verified mask, unmasked sectors left at stock. Sector phase is not measured.",
        }
        residuals[mode] = {
            "group_vs_per_patch": summarize_de(pair_de),
            "hue_only_vs_per_patch": summarize_de(hue_only_de),
            "chroma_only_vs_per_patch": summarize_de(chroma_only_de),
            "lightness_leak_abs_median": {
                "neutral": med([d for lab, d in leak if lab in NEUTRAL]),
                "memory": med([d for lab, d in leak if lab in MEMORY]),
                "rest": med([d for lab, d in leak if lab not in NEUTRAL and lab not in MEMORY]),
                "chromatic": med([d for lab, d in leak if lab not in NEUTRAL]),
            },
        }
    # Probe rows: two sparse, distinct perturbations of stock. Scale 1.30 stays
    # inside the 7-bit magnitude for these coefficients (checked below).
    probe_spec = []
    probe_words = []
    for name, sectors, angles in (
        ("probe_A", (0, 4, 8, 12, 16, 20), (18, 12, 6, -6, -12, -18)),
        ("probe_B", (2, 6, 10, 14, 18, 22), (18, 12, 6, -6, -12, -18)),
    ):
        rphi = [(1.0, 0.0)] * 24
        for s, ang in zip(sectors, angles):
            rphi[s] = (1.30, float(ang))
        words, clipped = build_row("positive", rphi)  # base is stock; mode unused
        # build_row uses group targets only through rphi, which we passed. Good.
        probe_words.append({"name": name, "words_hex": words, "clipped_sectors": clipped,
                            "sectors": list(sectors), "scale": 1.30, "hue_deg": list(angles)})
    # HC greys and alternative curves.
    xs20, ys20 = fw["curves"]["row20"]
    xs5, ys5 = fw["curves"]["row5"]
    def y20_of_stock_code(stock_code):
        # Invert stock roughly by interpolation of the monotone official curve.
        x = np.interp(stock_code, ys5, xs5)
        return apply_curve(xs20, ys20, x), x
    def lifted(amplitude):
        # y = row20 + A * exp(-((stock_code-128)/70)^2), then enforce monotone
        # by a cumulative maximum on a fine grid. Endpoints stay near row 20.
        grid = np.linspace(0, 4095, 4096)
        stock_code = apply_curve(xs5, ys5, grid)
        base = apply_curve(xs20, ys20, grid)
        bell = np.exp(-((stock_code - 128) / 70) ** 2)
        y = np.clip(base + amplitude * bell, 0, 255)
        for i in range(1, len(y)):
            if y[i] < y[i - 1]:
                y[i] = y[i - 1]
        return grid, y
    lifts = {"native_row20": None, "lift_mid_plus40": lifted(40), "lift_mid_plus58": lifted(58)}
    # Choose +58 so the code-128 point lands near 105: 47+58=105.
    hc_rows = []
    greys = [p for p in frames["03_hcbw"]["patches"] if p["label"] in NEUTRAL]
    for p in greys:
        code = p["u"] * 4095
        native = float(apply_curve(xs20, ys20, code))
        inj = float(apply_curve(*injected["hc"], code))
        stock = float(apply_curve(xs5, ys5, code))
        row = {"label": p["label"], "jpeg_y": p["jpeg_y"], "jpeg_rgb_255": [round(c * 255, 2) for c in p["jpeg_srgb"]],
               "L": p["L"], "sensor_code": code, "stock_row5": stock,
               "official_row20": native, "injected_row20": inj}
        for name, curve in lifts.items():
            if curve is None:
                continue
            row[name] = float(np.interp(code, curve[0], curve[1]))
        hc_rows.append(row)
    mid_native, _ = y20_of_stock_code(128)
    hc_summary = {
        "greys_dark_to_white": hc_rows,
        "code128": {
            "stock": 128,
            "official_row20": float(mid_native),
            "lift_plus40": float(np.interp(np.interp(128, ys5, xs5), lifts["lift_mid_plus40"][0], lifts["lift_mid_plus40"][1])),
            "lift_plus58": float(np.interp(np.interp(128, ys5, xs5), lifts["lift_mid_plus58"][0], lifts["lift_mid_plus58"][1])),
        },
    }
    # Drop non-JSON curves from fw before saving.
    fw_out = {k: v for k, v in fw.items() if k != "curves" and k != "stock_coeffs_ab"}
    fw_out["stock_coeffs_ab"] = fw["stock_coeffs_ab"]
    # Patches are large. Save them.
    def slim_frame(frame):
        keep_patch = []
        for p in frame["patches"]:
            keep_patch.append({k: p[k] for k in (
                "label", "index", "center_xy", "roi", "raw_dn", "camera_rgb", "camera_rgb_wb",
                "u", "jpeg_srgb", "jpeg_std", "lab", "L", "C", "h", "lab_wb", "L_wb", "C_wb", "h_wb",
                "jpeg_y", "curve_y") if k in p})
        return {k: frame[k] for k in ("file", "selector", "display", "raw13", "asn", "exposure",
                                      "geometry", "wb_gain_to_04", "max_center_shift_from_01_px")
                if k in frame} | {"patches": keep_patch}
    result = {
        "frames": {k: slim_frame(v) for k, v in frames.items()},
        "tone_check_greys": tone_check,
        "comparisons": comparisons,
        "baseline_coefficient_step": baseline_sectors,
        "baseline_empirical": baseline_emp,
        "group_target": group_target,
        "candidates": candidates,
        "residuals": residuals,
        "probes": probe_words,
        "hc": hc_summary,
        "firmware": fw_out,
        "de00_self_test": de_test,
        "k_percent_display_1_to_9_sector0": kperc[:, 0].tolist() if kperc.ndim == 2 else None,
    }
    (HERE / "measurements.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "tone_check_greys": tone_check,
        "de_full_pos": comparisons["positive"]["de00_full"],
        "de_tone_pos": comparisons["positive"]["de00_tone_only"],
        "de_full_neg": comparisons["negative"]["de00_full"],
        "de_tone_neg": comparisons["negative"]["de00_tone_only"],
        "baseline_emp": baseline_emp,
        "residuals": residuals,
        "hc_code128": hc_summary["code128"],
        "firmware_flags": {k: fw_out[k] for k in (
            "contrast5_is_lduh_T_2418", "standard_commit_is_ldi_r4_1",
            "jlaunch8_V2418_W0500_found", "colour_selectors_all_0101",
            "injected_stock_A_matches_official")},
        "wb_gains": {k: frames[k]["wb_gain_to_04"] for k in frames},
        "centers_04": frames["04_std"]["geometry"],
    }, indent=2))


if __name__ == "__main__":
    main()
