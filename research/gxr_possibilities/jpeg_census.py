#!/usr/bin/env python3
"""Census of main-image JPEG structure in the user's own GXR photos, to judge
whether two shots can be joined at MCU level without decoding.  Reads only the
marker segments of the primary image (skips the EXIF APP1 thumbnail).

usage: python3 -I jpeg_census.py <out-json> <jpg>...
"""
import hashlib, json, struct, sys
from pathlib import Path


def primary_markers(data):
    """Walk markers of the top-level image; APPn payloads are skipped whole,
    so the embedded EXIF thumbnail is not mistaken for the main image."""
    assert data[:2] == b"\xff\xd8"
    i, out = 2, {"dqt": [], "dht": 0, "dri": None, "sof": None, "app": []}
    while i < len(data):
        if data[i] != 0xFF:
            raise ValueError(f"marker expected at {i:#x}")
        m = data[i + 1]
        if m == 0xD9:
            break
        seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + seglen]
        if 0xE0 <= m <= 0xEF:
            out["app"].append(f"APP{m - 0xE0}:{seglen}")
        elif m == 0xDB:
            j = 0
            while j < len(seg):
                pq, tq = seg[j] >> 4, seg[j] & 15
                n = 128 if pq else 64
                out["dqt"].append({"id": tq, "sha1": hashlib.sha1(seg[j + 1:j + 1 + n]).hexdigest()[:12]})
                j += 1 + n
        elif m == 0xC4:
            out["dht"] += 1
        elif m == 0xDD:
            out["dri"] = struct.unpack(">H", seg[:2])[0]
        elif m in (0xC0, 0xC1, 0xC2):
            p, h, w, nc = seg[0], *struct.unpack(">HH", seg[1:5]), seg[5]
            comps = [(seg[6 + 3 * k], seg[7 + 3 * k] >> 4, seg[7 + 3 * k] & 15, seg[8 + 3 * k]) for k in range(nc)]
            out["sof"] = {"type": hex(m), "w": w, "h": h, "comps": comps}
        elif m == 0xDA:
            out["sos_at"] = i
            out["scan_bytes"] = len(data) - i
            break
        i += 2 + seglen
    return out


def main():
    res = []
    for p in sys.argv[2:]:
        d = Path(p).read_bytes()
        try:
            r = primary_markers(d)
        except Exception as e:  # report and continue
            r = {"error": str(e)}
        r["file"] = Path(p).name
        r["bytes"] = len(d)
        res.append(r)
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
    qsets = {}
    for r in res:
        if "dqt" in r:
            key = "/".join(q["sha1"] for q in r["dqt"])
            qsets.setdefault(key, []).append(r["file"])
        print(r["file"], r.get("sof"), "DRI", r.get("dri"), "DQT", [q["sha1"][:6] for q in r.get("dqt", [])], r.get("app"))
    print("distinct quant-table sets:", len(qsets), {k[:20]: len(v) for k, v in qsets.items()})


if __name__ == "__main__":
    main()
