"""本机对拍：用 studio 的生产函数算参考图，和浏览器读回的成片逐像素比 ΔE2000。只在本机跑（真实 DNG + 理光派生的配方表）。

用法（在 gxr-studio 工作树里）：.venv/bin/python parity_ref.py <应用数据目录> <图库目录> <读回目录> <cases.json> <输出 JSON>
"""
import json
import sys
from pathlib import Path

import numpy as np

from gxr_studio.engine.colour import delta_e00, lab_from_codes
from gxr_studio.finish.compose import finish_array, load_jpeg
from gxr_studio.finish.spec import factory_frame, factory_stamp, parse_geometry
from gxr_studio.library.store import Library
from gxr_studio.lut.library import LutLibrary
from gxr_studio.lut.photo import _apply
from gxr_studio.lut.scene import scene_colour
from gxr_studio.lut.spaces import DISPLAY
from gxr_studio.raw import NEUTRAL, half_res_codes, open_dng, orient_array
from gxr_studio.render import chain
from gxr_studio.render.params import EditState, parse_adjust, parse_curve, parse_recipe
from gxr_studio.render.service import RenderService
from gxr_studio.render.tones import channel_gains, display_table

home, libdir, rbdir, cases_path, out_path = (Path(a) for a in sys.argv[1:6])


class Lib:
    """只读：照片记录和绝对路径（不拿图库锁）。"""

    def __init__(self, root):
        self.root = root
        import sqlite3

        self.db = sqlite3.connect(f"file:{root / '.studio' / 'index.sqlite'}?mode=ro", uri=True)

    def abspath(self, rel):
        return self.root / rel


lib = Lib(libdir)
svc = RenderService(home, lib)
luts = LutLibrary(home, (libdir,))


def shot_of(sid):
    row = lib.db.execute("SELECT name, iso, lens FROM shots WHERE shot_id=?", (sid,)).fetchone()
    files = {k: {"relpath": rel} for k, rel in lib.db.execute("SELECT kind, relpath FROM files WHERE shot_id=?", (sid,)).fetchall()}
    return {"shot_id": sid, "name": row[0], "iso": row[1], "lens": row[2], "files": files}


def stats(a, b):
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    a2, b2 = a.reshape(-1, 3), b.reshape(-1, 3)
    diff = np.abs(a2.astype(int) - b2.astype(int)).max(axis=1)
    de = np.concatenate([delta_e00(lab_from_codes(a2[s : s + (1 << 20)]), lab_from_codes(b2[s : s + (1 << 20)])) for s in range(0, len(a2), 1 << 20)])
    return {
        "mean": round(float(de.mean()), 5), "p95": round(float(np.percentile(de, 95)), 4), "max": round(float(de.max()), 3),
        "identical": round(float((diff == 0).mean()), 6), "within_1": round(float((diff <= 1).mean()), 6), "max_code": int(diff.max()),
    }


rows = []
for c in json.loads(cases_path.read_text()):
    files = list(rbdir.glob(f"{c['id']}__*.rgba"))
    if not files:
        rows.append({"id": c["id"], "error": "no readback"})
        continue
    w, h = (int(v) for v in files[0].stem.split("__")[1].split("x"))
    gpu = np.frombuffer(files[0].read_bytes(), np.uint8).reshape(h, w, 4)[..., :3]
    shot = shot_of(c["photo"])
    adjust = parse_adjust(c.get("adjust") or {})
    master = parse_curve({"master": c["curve"]}) if c.get("curve") else None
    geom = parse_geometry(c.get("geometry") or {})
    sel = parse_recipe(c["recipe"]) if c.get("recipe") else None
    edit = EditState(recipe=sel, adjust=adjust, master=master, geometry=geom)
    from_raw = False
    if c.get("lut"):
        target, _ = luts.target(c["lut"])
        if target.input_space in DISPLAY:
            if sel is not None or "jpg" not in shot["files"]:
                dng = open_dng(lib.abspath(shot["files"]["dng"]["relpath"]))
                codes = np.ascontiguousarray(orient_array(half_res_codes(dng), dng.orientation), np.float32)
                base = chain.chroma_u8(codes, svc.preview_bake(svc.plan(shot, EditState(recipe=sel))), None, None)
            else:
                base = load_jpeg(lib.abspath(shot["files"]["jpg"]["relpath"]), None)
            rgb = _apply(target, base)
        else:
            dng = open_dng(lib.abspath(shot["files"]["dng"]["relpath"]))
            codes = np.ascontiguousarray(orient_array(half_res_codes(dng), dng.orientation), np.float32)
            rgb = _apply(target, NEUTRAL.display(codes), scene_colour(dng).xyz(codes))
    elif sel is None and "jpg" in shot["files"]:
        rgb = load_jpeg(lib.abspath(shot["files"]["jpg"]["relpath"]), None)
    else:
        dng = open_dng(lib.abspath(shot["files"]["dng"]["relpath"]))
        codes = np.ascontiguousarray(orient_array(half_res_codes(dng), dng.orientation), np.float32)
        rgb = chain.chroma_u8(codes, svc.preview_bake(svc.plan(shot, edit)), channel_gains(adjust), display_table(adjust, master))
        from_raw = True
    crop = c.get("crop")
    rect = tuple(crop["rect"]) if crop else None
    ref, _valid = finish_array(
        rgb, edit, stage=c["stage"], frame=factory_frame(), stamp=factory_stamp(), crop_rect=rect, meta={}, taken=None,
        file_time=None, from_raw=from_raw, crop_preset=crop.get("preset") if crop else None,
    )
    row = {"id": c["id"], "w": w, "h": h, **stats(gpu, np.ascontiguousarray(ref))}
    rows.append(row)
    print(json.dumps(row), flush=True)
out_path.write_text(json.dumps(rows, indent=1))
