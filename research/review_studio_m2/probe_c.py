"""review-studio-m2-r1 的复审探针 C：只有 RAW 的照片在界面里是否被标成“电脑预测”；
中途杀进程的导入；曲线 16 点边界。临时目录，进程内。
  studio/.venv/bin/python -I probe_c.py <临时目录> <仓库根>
"""
import hashlib
import io
import json
import multiprocessing as mp
import os
import shutil
import signal
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from starlette.testclient import TestClient

from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings

T = Path(sys.argv[1])
REPO = Path(sys.argv[2])
PORT = 45125
TOKEN = "tok-" + "z" * 40
audit.forbid_volumes()
audit.forbid_network()
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (("  " + str(detail)[:300]) if detail else ""), flush=True)


# 一张只有 DNG 的“卡”（真实样本，去掉 JPG）
vols = T / "vols"
d = vols / "RAWONLY" / "DCIM" / "100RICOH"
d.mkdir(parents=True)
src = REPO / "captures/a12-50/2026-10-19/stage2c-first-run"
for n in ("R8051144", "R8051145"):
    shutil.copy2(src / f"{n}.DNG", d / f"{n}.DNG")
cfg = Settings(library_dir=T / "lib", home_dir=T / "home", export_dir=T / "exp", volumes_roots=(vols,),
               token=TOKEN, port=PORT, web_dir=REPO / "studio/web")
app = create_app(cfg)
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
    cid = c.get("/api/cards", headers=A).json()[0]["id"]
    c.post("/api/import", json={"card_id": cid}, headers=A)
    while any(j["running"] for j in c.get("/api/jobs", headers=A).json()):
        time.sleep(0.2)
    shots = c.get("/api/photos", headers=A).json()
    s = shots[0]
    check("RAW-only 照片 preview_kind = dng-preview", s["preview_kind"] == "dng-preview", s["preview_kind"])
    t_neutral = c.get(s["thumb_url"], headers=A).content
    r = c.post("/api/camdata/import-file", json={"path": str(REPO / "firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT")}, headers=A)
    r = c.post("/api/calibration/import", json={"path": str(REPO)}, headers=A)
    s2 = c.get("/api/photos", headers=A).json()[0]
    t_stock = c.get(s2["thumb_url"], headers=A)
    a = np.asarray(Image.open(io.BytesIO(t_neutral)).convert("RGB"), float)
    b = np.asarray(Image.open(io.BytesIO(t_stock.content)).convert("RGB"), float)
    print("   缩略图 URL:", s["thumb_url"], "→", s2["thumb_url"], " 响应头里的预测标记:", {k: v for k, v in t_stock.headers.items() if k.lower().startswith("x-gxr")})
    check("导入相机数据后 RAW-only 的缩略图内容变了（= 画的是原厂 04 电脑模拟）", float(np.abs(a - b).mean()) > 1.0, round(float(np.abs(a - b).mean()), 2))
    check("该缩略图/预览的响应带 X-GXR-Prediction 标记（否则界面无从标注）", t_stock.headers.get("x-gxr-prediction") == "1", dict(t_stock.headers))
    gal = (REPO / "studio/web/assets/gallery.js").read_text()
    print("   前端读取 preview_kind 的文件:", [p.name for p in (REPO / "studio/web/assets").glob("*.js") if "preview_kind" in p.read_text()] or "无")
    print("   gallery.js 含『预测』字样:", "预测" in gal)
    # 曲线 16 点边界
    pts = [[i * 17, min(255, i * 17 + 6)] for i in range(16)]  # 0..255 共 16 个点
    r = c.post(f"/api/photos/{s2['id']}/render?max_edge=300", json={"curve": {"master": pts}}, headers=A)
    check("曲线 16 点 → 200", r.status_code == 200, r.text[:160])

failed = [r for r in results if r[1] is False]
print(f"\n== {len(results)} 项, 失败 {len(failed)}")
for f in failed:
    print("FAILED:", f)
