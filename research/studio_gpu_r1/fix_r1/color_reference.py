"""FIX_R1 复跑：把读回的成片和生产 Python（JPEG 压缩之前）逐像素比较，按 tests/gpu_gate.py 的门槛判定。

参考图的算法与复审 r1 的 color_reference.py 相同。冻结列表直接取复审 r1 的独立测量（real-parity-metal.json /
real-parity.json 里 >2 码值的像素，按适配器分开），不是从本次结果里取。

前向量化复算（门槛第 3 条的"解释"）：对每个带外 >2 码值的像素，把 Python 第一段（配方 + 曲线，chroma_u8 的 uint8 输出）
在该像素上偏 1 码值（每通道 −1/0/+1，共 27 种），用生产 finish_array 走完后面的黑点、饱和度、自然饱和度、暗角；
有一种组合逐字节等于显卡结果，就算解释了。只用于没有几何变换的配方路径（逐像素运算，位置不变）。

用法（gxr-studio 工作树的 .venv）：python color_reference.py <metal|swiftshader>
"""

import json
import sqlite3
import sys
from itertools import product
from pathlib import Path

import numpy as np

WT = Path("/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview")
sys.path.insert(0, str(WT / "tests"))

from gpu_gate import evaluate  # noqa: E402
from gxr_studio.finish.compose import finish_array, load_jpeg  # noqa: E402
from gxr_studio.finish.geometry import warp_valid  # noqa: E402
from gxr_studio.finish.spec import factory_frame, factory_stamp, parse_geometry  # noqa: E402
from gxr_studio.gpu.box import final_box  # noqa: E402
from gxr_studio.lut.photo import _apply  # noqa: E402
from gxr_studio.lut.scene import scene_colour  # noqa: E402
from gxr_studio.lut.spaces import DISPLAY  # noqa: E402
from gxr_studio.raw import NEUTRAL, half_res_codes, open_dng, orient_array  # noqa: E402
from gxr_studio.render import chain  # noqa: E402
from gxr_studio.render.params import EditState, parse_adjust, parse_curve, parse_recipe  # noqa: E402
from gxr_studio.render.service import RenderService  # noqa: E402
from gxr_studio.render.tones import channel_gains, display_table  # noqa: E402

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parents[1] / "review_studio_gpu_preview_r1"
TEMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r1/real")


def frozen_from_review(mode):
    """复审 r1 的独立测量：>2 码值的像素 (y, x) → 差值。"""
    name = "real-parity-metal.json" if mode == "metal" else "real-parity.json"
    out = {}
    for row in json.loads((REVIEW / name).read_text()):
        pts = {(e["y"], e["x"]): e["max_code"] for e in row.get("example_differences", []) if e["max_code"] > 2 and not e["edge_band"]}
        if pts:
            assert len(pts) == row["over_2_outside_edge_band"], (row["id"], "复审记录的样例不全")
            out[row["id"]] = pts
    return out


class ReadOnlyLibrary:
    def __init__(self, root):
        self.root = root
        self.db = sqlite3.connect(f"file:{root}/.studio/index.sqlite?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row

    def abspath(self, rel):
        return self.root / rel

    def shot(self, sid):
        d = dict(self.db.execute("SELECT * FROM shots WHERE shot_id=?", (sid,)).fetchone())
        d["files"] = {r["kind"]: dict(r) for r in self.db.execute("SELECT * FROM files WHERE shot_id=?", (sid,))}
        return d


def reference(c, lib, svc):
    """返回 (成片, 第一段 uint8 或 None, finish 参数, 有效区蒙版, 是否显示类 LUT)。"""
    shot = lib.shot(c["photo"])
    adjust = parse_adjust(c.get("adjust") or {})
    master = parse_curve({"master": c["curve"]}) if c.get("curve") else None
    geom = parse_geometry(c.get("geometry") or {})
    sel = parse_recipe(c["recipe"]) if c.get("recipe") else None
    edit = EditState(recipe=sel, adjust=adjust, master=master, geometry=geom)
    raw = False
    needs_raw = bool(sel or "jpg" not in shot["files"])
    target = None
    display_lut = False
    if c.get("lut"):
        target, _ = svc.luts.target(c["lut"])
        display_lut = target.input_space in DISPLAY
        needs_raw = needs_raw or not display_lut
    dng = None
    if needs_raw:
        dng = open_dng(lib.abspath(shot["files"]["dng"]["relpath"]))
        codes = np.ascontiguousarray(orient_array(half_res_codes(dng), dng.orientation), np.float32)
    try:
        if target is not None:
            if not display_lut:
                rgb = _apply(target, NEUTRAL.display(codes), scene_colour(dng).xyz(codes))
            else:
                base = (
                    chain.chroma_u8(codes, svc.preview_bake(svc.plan(shot, EditState(recipe=sel))), None, None)
                    if needs_raw
                    else load_jpeg(lib.abspath(shot["files"]["jpg"]["relpath"]), None)
                )
                rgb = _apply(target, base)
        elif needs_raw:
            rgb = chain.chroma_u8(codes, svc.preview_bake(svc.plan(shot, edit)), channel_gains(adjust), display_table(adjust, master))
            raw = True
        else:
            rgb = load_jpeg(lib.abspath(shot["files"]["jpg"]["relpath"]), None)
    finally:
        if dng is not None:
            dng.release()
    height, width = rgb.shape[:2]
    crop = c.get("crop")
    rect = tuple(crop["rect"]) if crop else None
    kw = dict(stage=c["stage"], frame=factory_frame(), stamp=factory_stamp(), crop_rect=rect, meta={}, taken=None, file_time=None, from_raw=raw)
    kw["crop_preset"] = crop.get("preset") if crop else None
    out, _ = finish_array(rgb, edit, **kw)
    mask = warp_valid(width, height, geom)
    if c["stage"] == "final":
        (x, y, w, h), _ = final_box(width, height, geom, rect, crop.get("preset") if crop else None)
        mask = mask[y : y + h, x : x + w]
    plain = geom.is_identity() and rect is None and target is None
    return np.ascontiguousarray(out), (rgb if plain else None), (edit, kw), mask, display_lut


def replay(stage1, finish, gpu):
    def explain(points):
        if stage1 is None:
            return [False] * len(points)
        edit, kw = finish
        hit = [False] * len(points)
        ys = np.array([p[0] for p in points])
        xs = np.array([p[1] for p in points])
        for delta in product((-1, 0, 1), repeat=3):
            moved = stage1.copy()
            moved[ys, xs] = np.clip(stage1[ys, xs].astype(np.int16) + delta, 0, 255).astype(np.uint8)
            out, _ = finish_array(moved, edit, **kw)
            for i, (y, x) in enumerate(points):
                hit[i] = hit[i] or bool((out[y, x] == gpu[y, x]).all())
            if all(hit):
                break
        return hit

    return explain


def main():
    mode = sys.argv[1]
    lib = ReadOnlyLibrary(TEMP / "studio/library")
    svc = RenderService(TEMP / "studio/app-home", lib)
    cases = json.loads((TEMP / "real-cases.json").read_text())
    frozen = frozen_from_review(mode)
    rows = []
    for c in cases:
        files = list((TEMP / f"readbacks-{mode}").glob(c["id"] + "__*.rgba"))
        if not files:
            rows.append({"id": c["id"], "error": "missing readback"})
            print(json.dumps(rows[-1]), flush=True)
            continue
        w, h = map(int, files[0].stem.split("__")[1].split("x"))
        gpu = np.fromfile(files[0], np.uint8).reshape(h, w, 4)[..., :3]
        ref, stage1, finish, mask, display_lut = reference(c, lib, svc)
        r = evaluate(gpu, ref, mask=mask, frozen=frozen.get(c["id"]), explain=replay(stage1, finish, gpu), display_lut=display_lut)
        row = {"id": c["id"], "w": w, "h": h, "display_lut": display_lut, "frozen": [[y, x, d] for (y, x), d in frozen.get(c["id"], {}).items()], **r}
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k not in ("frozen",)}), flush=True)
    (HERE / f"real-parity-{mode}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print("ALL PASS" if all(r.get("pass") for r in rows) else "FAILURES", flush=True)


if __name__ == "__main__":
    main()
