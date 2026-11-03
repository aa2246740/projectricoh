"""GR IV analytic candidate. Firmware arrays are loaded into ignored local/ only.

Primary order follows gr3-film-mods work/films_v16/refit16.py, read as data.
The hardware chroma/level interpolation remains a hypothesis, exposed in Options.
"""
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np

MODES = {"standard": "Standard", "positive": "Positive_Film", "negative": "Negative_Film"}


@lru_cache(maxsize=1)
def parameters():
    d = rt.read("research/gr_firmware/data/gr4-1.11-tables.json")
    gamma = rt.read("research/gr_complete_pipeline/gr3_gr4_effective_curves.json")
    findings = rt.inp("artifacts/downloads/gr3-film-mods/repo/FINDINGS.md").read_text()
    match = re.search(r"edges ([0-9.,\s]+) deg; sector g", findings)
    assert match, "public sector geometry not found in pinned source"
    sector_edges = np.fromstring(match.group(1).replace(",", " "), sep=" ")
    assert len(sector_edges) == 12
    tables = {x["id"]: x for x in d["tables"]}
    for table in tables.values():
        fmt = table["format"].split(" x ", 1)[1]
        code = {"u8": "B", "u16LE": "H", "i16LE": "h", "u32LE": "I", "i32LE": "i"}[fmt]
        blob = struct.pack("<" + code * len(table["values"]), *table["values"])
        assert len(blob) == table["size"] and hashlib.sha256(blob).hexdigest() == table["sha256"]
    blocks = {}
    families = [[None for _ in range(5)] for _ in range(3)]
    for x in gamma["source_blocks"]:
        blob = bytes.fromhex(x["bytes_hex"])
        assert len(blob) == x["size"] and hashlib.sha256(blob).hexdigest() == x["sha256"]
        if x["model"] != "gr4":
            continue
        blocks[x["meaning"]] = blob
        m = re.fullmatch(r"base family (\d) band (\d)", x["meaning"])
        if m:
            families[int(m[1])][int(m[2])] = np.frombuffer(blob, "<u2").astype(int).tolist()
    p = dict(modes={}, gamma=dict(families=families,
        keys=list(struct.unpack("<9i", blocks["signed-key lookup"])),
        smoothing=list(struct.unpack("<97H", blocks["97x u16 transition smoothing"])),
        unit=struct.unpack("<H", blocks["normalization/anchor base unit"])[0]),
        source_payload_sha256=d["payload_sha256"], sector_edges=sector_edges)
    for mode, prefix in MODES.items():
        def value(suffix):
            return tables[prefix + "-" + suffix]["values"]
        p["modes"][mode] = dict(look=value("look-matrix"), sensor=value("sensor-ccm"),
            saturation=value("saturation-+0"), ma=value("multiaxial-matrix-bank-0"),
            control=value("multiaxial-controls"), ycc=value("multiaxial-ycc"),
            gamma_flags=tables[prefix + "-gamma-descriptor"]["values"][1])
    p["sliders"] = {}
    names = {"standard": "Standard", "positive": "PositiveFilm", "negative": "NegativeFilm"}
    for mode, name in names.items():
        p["sliders"][mode] = next(x["sliders"] for x in gamma["effective_curves"]
            if x["model"] == "gr4" and x["mode"] == name)
    rt.dump("parameters.json", p)
    return p


def _blend(a, b, w):
    return (a * w + b * (512 - w) + 256) >> 9


@lru_cache(maxsize=256)
def curve(mode, gain):
    """Integer reconstruction from arm_gamma_model.effective_curve, using GR IV blocks."""
    p = parameters()
    t = p["gamma"]
    s = p["sliders"][mode]
    key, contrast, highlight, shadow = (s[x] for x in ("key", "contrast", "highlight", "shadow"))
    gain = int(gain)
    if not 0 <= gain <= 65535:
        raise ValueError("gain outside original u16 boundary")
    knee = max(128, min(2048, ((t["keys"][key + 4] * 2 * gain & 0xffffffff) >> 13)))
    low = 0 if knee <= 255 else 1 if knee < 512 else 2 if knee < 1024 else 3
    high, index = low + 1, knee >> 4
    target = (t["unit"] * 118) & 65535
    regions = []
    for adj in (highlight, 0, -shadow):
        k = max(-12, min(12, 2 * contrast + adj))
        a, b, w = (0, 1, k * 512 // 12) if k > 0 else (1, 2, (k + 12) * 512 // 12)
        yl = _blend(t["families"][a][low][index], t["families"][b][low][index], w)
        yh = _blend(t["families"][a][high][index], t["families"][b][high][index], w)
        bw = 512 if yl <= yh else 0 if yh >= target else ((target - yh) << 9) // (yl - yh)
        regions.append((a, b, w, bw))
    def y(region, i):
        a, b, w, bw = region
        return _blend(_blend(t["families"][a][low][i], t["families"][b][low][i], w),
                      _blend(t["families"][a][high][i], t["families"][b][high][i], w), bw)
    out = []
    for i in range(256):
        x = i * 16
        middle = y(regions[1], i)
        selected = y(regions[2 if x <= knee else 0], i)
        v = middle
        if x > knee and highlight:
            if x >= 4 * knee:
                v = selected
            else:
                w = t["smoothing"][max(0, min(96, i * 512 // knee - 32))]
                v = (selected * w + middle * (2048 - w) + 1024) >> 11
        if x < knee and shadow:
            if x <= knee // 4:
                v = selected
            else:
                w = t["smoothing"][max(0, min(96, knee * 32 // x - 32))]
                v = (selected * w + middle * (2048 - w) + 1024) >> 11
        out.append(min(16384, (v << 14) // (0x3f02 * (t["unit"] >> 6))))
    return np.array(out, float) / 16384


@dataclass(frozen=True)
class Options:
    order: str = "before_gamma"
    sectors: str = "hard"
    level: int = 0
    quantize_front: bool = False


def sector_of(value, mode):
    p = parameters()["modes"][mode]
    ycc = np.asarray(p["ycc"], float).reshape(3, 3) / 256
    chroma = value @ ycc.T
    angle = np.degrees(np.arctan2(chroma[..., 2], chroma[..., 1])) % 360
    boundaries = np.asarray(parameters()["sector_edges"])
    unwrapped = (angle - boundaries[0]) % 360
    edges = (boundaries - boundaries[0]) % 360
    sector = np.clip(np.searchsorted(edges, unwrapped, side="right") - 1, 0, 11)
    return sector, unwrapped, edges


def multiaxial(value, mode, options):
    p = parameters()["modes"][mode]
    # Enable semantics follow FINDINGS 29-30a. Other active-control combinations are unmodelled.
    if p["control"][10:14] != [1024] * 4 or options.sectors == "off":
        return value
    sector, unwrapped, edges = sector_of(value, mode)
    mats = np.asarray(p["ma"], float).reshape(12, 5, 3, 3)[:, options.level] / 1024
    result = np.einsum("...ij,...j->...i", mats[sector], value)
    if options.sectors == "linear":
        upper = np.r_[edges[1:], 360.]
        weight = (unwrapped - edges[sector]) / (upper[sector] - edges[sector])
        next_value = np.einsum("...ij,...j->...i", mats[(sector + 1) % 12], value)
        result = result * (1 - weight[..., None]) + next_value * weight[..., None]
    elif options.sectors != "hard":
        raise ValueError("unknown sector hypothesis")
    return result


def render(raw_wb, mode, common, options=Options()):
    """Black-subtracted, white-normalized camera RGB already divided by AsShotNeutral."""
    p = parameters()["modes"][mode]
    front = np.asarray(p["saturation"], float).reshape(3, 3) / 8192
    front = front @ (np.asarray(p["look"], float).reshape(3, 3) / 8192) @ np.asarray(common["matrix"])
    source = np.asarray(raw_wb, float)
    if options.quantize_front:
        front = (np.asarray(p["saturation"], float).reshape(3, 3) / 8192) @ (np.asarray(p["look"], float).reshape(3, 3) / 8192) @ np.asarray(common["matrix_base"])
        source = source * np.asarray(common["wb_correction"])
        q = np.trunc(front * 256)
        for i in range(3):
            q[i, i] = 256 - sum(q[i, j] for j in range(3) if j != i)
        front = np.clip(q, -2048, 2047) / 256
    z = source @ front.T * 2 ** common["exposure_ev"]
    if options.order == "before_gamma":
        z = multiaxial(z, mode, options)
    elif options.order != "after_gamma":
        raise ValueError("unknown pipeline order")
    out = np.interp(np.clip(z * 4095, 0, 4080), np.arange(256) * 16, curve(mode, int(common["gain"])))
    # These three stock modes have no enabled channel override in the extracted descriptor.
    assert p["gamma_flags"] == 0
    post = np.asarray(common.get("post_matrix", np.eye(3)))
    out = out @ post.T
    if options.order == "after_gamma":
        out = multiaxial(out, mode, options)
    return np.clip(out, 0, 1)


def render_scene(linear_srgb, mode, common, options=Options()):
    """Scene-linear sRGB/D65 -> encoded sRGB; camera-independent target candidate.

    The DNG colorimetric map only defines the scene coordinate. It does not measure
    spectral metamerism. Exposure convention is inherited from the Standard fit.
    """
    if "raw_wb_to_scene" not in common:
        raise ValueError("calibration has no explicit scene coordinate")
    raw_wb = np.asarray(linear_srgb, float) @ np.linalg.inv(common["raw_wb_to_scene"]).T
    return render(raw_wb, mode, common, options)


if __name__ == "__main__":
    parameters()
    d = rt.read("research/gr_complete_pipeline/gr3_gr4_effective_curves.json")
    errors = []
    for old in d["effective_curves"]:
        if old["model"] != "gr4" or old["mode"] == "HighContrastBW":
            continue
        name = {"Standard": "standard", "PositiveFilm": "positive", "NegativeFilm": "negative"}[old["mode"]]
        errors.append(float(np.max(np.abs(curve(name, old["gain"]) * 16384 - old["curve_u16_256"]))))
    assert errors and max(errors) == 0
    rt.dump("formula_verification.json", dict(curves_checked=len(errors), maximum_node_error=max(errors)))
    print("GR IV integer gamma: all six stored states match exactly")
