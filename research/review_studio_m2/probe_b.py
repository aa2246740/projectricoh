"""review-studio-m2-r1 的复审探针 B：相机数据/标定、配方渲染、标签、边界值、理光字节不外泄。
全部在临时目录里跑，进程内（TestClient）。用法：
  studio/.venv/bin/python -I probe_b.py <临时目录> <仓库根>
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from starlette.testclient import TestClient

from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
from gxr_studio.devtools import synthetic_card as sy

T = Path(sys.argv[1])
REPO = Path(sys.argv[2])
PORT = 45124
TOKEN = "tok-" + "y" * 40
audit.forbid_volumes()
audit.forbid_network()
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (("  " + str(detail)[:300]) if detail else ""), flush=True)


vols = T / "vols"
card = sy.make_card(vols, "REVCARD")
dat_src = REPO / "firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT"
dat = dat_src.read_bytes()
cfg = Settings(library_dir=T / "lib", home_dir=T / "home", export_dir=T / "exp", volumes_roots=(vols,),
               token=TOKEN, port=PORT, web_dir=REPO / "studio/web")
app = create_app(cfg)
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
    cid = c.get("/api/cards", headers=A).json()[0]["id"]
    c.post("/api/import", json={"card_id": cid}, headers=A)
    while any(j["running"] for j in c.get("/api/jobs", headers=A).json()):
        time.sleep(0.2)
    shots = c.get("/api/photos?limit=500", headers=A).json()
    real = [s for s in shots if s["name"].startswith("R805")]
    print("真实样本:", [(s["name"], s["iso"], s["lens"], s["unit"], s["width"], s["height"], s["has_raw"], s["has_jpg"]) for s in real])
    st = c.get("/api/camdata/status", headers=A).json()
    check("初始：没有相机数据，ready=false，next=import_camera_data", st["ready"] is False and st["next"] == "import_camera_data", st["next"])

    # 没有相机数据时，对 DNG 渲染/导出：409 且信息是白话
    s0 = real[0]
    r = c.get(f"/api/photos/{s0['id']}/render", headers=A)
    check("没有相机数据 → 预览 409 camera_data_missing", r.status_code == 409 and r.json()["error"] == "camera_data_missing", r.text[:200])
    r = c.post(f"/api/photos/{s0['id']}/export", json={"source": "recipe"}, headers=A)
    check("没有相机数据 → 套配方导出 409", r.status_code == 409, r.text[:160])

    # 导入 DAT（走 import-file，模拟没有卡）
    r = c.post("/api/camdata/import-file", json={"path": str(dat_src)}, headers=A)
    check("导入 g135 DAT", r.status_code == 200 and r.json()["generation"] == 135, r.text[:200])
    r = c.post("/api/camdata/import-file", json={"path": str(dat_src)}, headers=A)
    check("重复导入 → unchanged", r.json().get("unchanged") is True)
    # 损坏的 DAT 不会破坏已导入的
    bad = bytearray(dat); bad[5000] ^= 0xFF
    r = c.post("/api/camdata/import-upload", content=bytes(bad), headers={**A, "X-GXR-Filename": "x.DAT"})
    check("翻转 1 字节的 DAT → 422 且原数据完好", r.status_code == 422, r.text[:200])
    r = c.get("/api/camdata/status", headers=A).json()
    check("原相机数据仍是 g135", r["camera_data"]["generation"] == 135 and r["camera_data"]["state"] == "ready")
    # 截断
    r = c.post("/api/camdata/import-upload", content=dat[:50000], headers=A)
    check("截断的 DAT → 422", r.status_code == 422, r.text[:160])

    # 标定：开发机路径
    r = c.post("/api/calibration/import", json={"path": str(REPO)}, headers=A)
    check("导入标定（开发机：仓库根）", r.status_code == 200, r.text[:200])
    st = c.get("/api/camdata/status", headers=A).json()
    check("现在 ready=true", st["ready"] is True, st.get("next_message"))

    # 渲染 + 标签
    for s in real[:2]:
        r = c.get(f"/api/photos/{s['id']}/render?max_edge=800", headers=A)
        lab = r.headers.get("x-gxr-label")
        from urllib.parse import unquote
        print(f"   {s['name']} ISO {s['iso']} → {r.status_code} label={unquote(lab or '')} cal={r.headers.get('x-gxr-calibrated')} timing={r.headers.get('x-gxr-timing')}")
        check(f"{s['name']} 预览带 X-GXR-Prediction / 标签", r.status_code == 200 and r.headers.get("x-gxr-prediction") == "1" and "电脑预测" in unquote(lab or ""))
        if s["iso"] not in (200, 1600):
            check(f"{s['name']} ISO {s['iso']} 标『未标定』", "未标定" in unquote(lab or ""), unquote(lab or ""))
    s = real[0]
    # 编辑 API 边界
    def edit(body):
        return c.post(f"/api/photos/{s['id']}/render?max_edge=300", json=body, headers=A)
    cases = [
        ("曝光 +5", {"adjust": {"exposure_ev": 5}}, 200), ("曝光 -5", {"adjust": {"exposure_ev": -5}}, 200),
        ("曝光 5.0001", {"adjust": {"exposure_ev": 5.0001}}, 422), ("曝光 -5.0001", {"adjust": {"exposure_ev": -5.0001}}, 422),
        ("曝光 字符串", {"adjust": {"exposure_ev": "1"}}, 422), ("曝光 bool", {"adjust": {"exposure_ev": True}}, 422),
        ("对比 +100", {"adjust": {"contrast": 100}}, 200), ("对比 -100", {"adjust": {"contrast": -100}}, 200), ("对比 101", {"adjust": {"contrast": 101}}, 422),
        ("高光 100 阴影 100 对比 100", {"adjust": {"contrast": 100, "highlight": 100, "shadow": 100}}, 200),
        ("色温 -100 色调 100", {"adjust": {"wb": {"warm": -100, "tint": 100}}}, 200),
        ("色温 101", {"adjust": {"wb": {"warm": 101}}}, 422), ("色温 1.5", {"adjust": {"wb": {"warm": 1.5}}}, 422),
        ("曲线 恒等", {"curve": {"master": [[0, 0], [255, 255]]}}, 200),
        ("曲线 反相", {"curve": {"master": [[0, 255], [255, 0]]}}, 200),
        ("曲线 端点不在 0/255", {"curve": {"master": [[30, 0], [220, 255]]}}, 200),
        ("曲线 16 点", {"curve": {"master": [[i * 17, min(255, i * 17 + 6)] for i in range(16)]}}, 200),
        ("曲线 17 点", {"curve": {"master": [[i * 15, i * 15] for i in range(17)]}}, 422),
        ("曲线 x 重复", {"curve": {"master": [[0, 0], [100, 100], [100, 120], [255, 255]]}}, 422),
        ("曲线 x 倒序", {"curve": {"master": [[0, 0], [200, 100], [100, 120], [255, 255]]}}, 422),
        ("曲线 越界 256", {"curve": {"master": [[0, 0], [256, 255]]}}, 422),
        ("曲线 单点", {"curve": {"master": [[0, 0]]}}, 422),
        ("配方 jlaunch/1 默认", {"recipe": {"unit": "jlaunch", "slot": 1}}, 200),
        ("配方 slot 9", {"recipe": {"unit": "jlaunch", "slot": 9}}, 422),
        ("配方 未知旋钮", {"recipe": {"unit": "jlaunch", "slot": 1, "levels": {"bogus": 1}}}, 422),
        ("配方 qlaunch（跨单元）", {"recipe": {"unit": "qlaunch", "slot": 1}}, 200),
    ]
    for name, body, want in cases:
        r = edit(body)
        ok = r.status_code == want
        if ok and want == 200:
            try:
                im = Image.open(__import__("io").BytesIO(r.content)); im.load(); arr = np.asarray(im)
                ok = arr.ndim == 3 and arr.shape[2] == 3
            except Exception as e:
                ok = False
        check(f"边界 {name} → {want}", ok, (r.status_code, r.text[:140] if r.status_code != 200 else ""))
    # 旋钮极值（用 recipes 目录里的 min/max）
    cat = c.get("/api/recipes", headers=A).json()
    u0 = cat["units"][0]
    print("   recipes 目录首个单元键:", list(u0)[:8])
    # 随便试一个：amount 150, saturation 9 之类，由菜单决定；用 PUT edit 验证 422 不钳位
    r = c.put(f"/api/photos/{s['id']}/edit", json={"recipe": {"unit": "jlaunch", "slot": 1, "levels": {"saturation": 99}}}, headers=A)
    check("旋钮越界 → 422，不钳位", r.status_code == 422, r.text[:160])
    r = c.put(f"/api/photos/{s['id']}/edit", json={"recipe": {"unit": "jlaunch", "slot": 6, "levels": {"contrast": 4}}, "adjust": {"exposure_ev": 0.7}, "curve": {"master": [[0, 10], [128, 120], [255, 250]]}}, headers=A)
    check("写入配方+调整+曲线", r.status_code == 200, r.text[:160])
    # 与引擎一致：烘焙预览 vs exact
    ra = c.get(f"/api/photos/{s['id']}/render?max_edge=600", headers=A)
    rb = c.get(f"/api/photos/{s['id']}/render?max_edge=600&exact=true", headers=A)
    a = np.asarray(Image.open(__import__("io").BytesIO(ra.content)).convert("RGB"), np.int16)
    b = np.asarray(Image.open(__import__("io").BytesIO(rb.content)).convert("RGB"), np.int16)
    d = np.abs(a - b)
    check("烘焙预览 vs 精确链：平均差 < 1.0/255，99.9% 分位 ≤ 4", d.mean() < 1.0 and np.percentile(d, 99.9) <= 4, (round(float(d.mean()), 3), float(np.percentile(d, 99.9)), int(d.max())))
    # 导出：套配方
    r = c.post(f"/api/photos/{s['id']}/export", json={"size": "medium"}, headers=A)
    j = r.json(); print("   export:", json.dumps(j, ensure_ascii=False)[:300])
    check("有编辑 → 自动从 RAW 渲染 = 电脑预测", r.status_code == 200 and j["prediction"] is True and "电脑预测" in Path(j["path"]).name, j.get("path"))
    ex = Image.open(j["path"])
    desc = ex.getexif().get(270)
    check("导出 EXIF 说明是电脑预测", desc and "computer prediction" in desc, desc)
    if s["iso"] not in (200, 1600):
        check("未标定 ISO 的导出：文件名/EXIF 带未标定", "未标定" in Path(j["path"]).name and "NOT calibrated" in desc, (Path(j["path"]).name, desc))
    r = c.post(f"/api/photos/{s['id']}/export", json={"source": "camera-jpg", "size": "medium"}, headers=A)
    check("camera-jpg 导出不带配方标签", r.status_code == 200 and "电脑预测" not in Path(r.json()["path"]).name and r.json()["prediction"] is False)
    # 只有 DNG 的：合成 DNG 是否能渲染
    dngonly = [x for x in shots if x["has_raw"] and not x["has_jpg"]]
    if dngonly:
        r = c.post(f"/api/photos/{dngonly[0]['id']}/export", json={}, headers=A)
        print("   DNG-only 导出:", r.status_code, r.text[:200])
    # 理光字节外泄扫描：用 DAT 的 24 字节窗口去扫导出/缩略图/图库 .studio/日志
    wins = set()
    for i in range(0, len(dat) - 24, 24):
        w = dat[i:i + 24]
        if len(set(w)) >= 12:
            wins.add(w)
    targets = [p for p in list(cfg.export_dir.rglob("*")) + list((cfg.library_dir / ".studio").rglob("*")) if p.is_file()]
    hits = []
    for p in targets:
        data = p.read_bytes()
        for w in wins:
            if w in data:
                hits.append(p.name); break
    check(f"导出文件/缩略图/.studio 里没有 DAT 的 24 字节片段（扫了 {len(targets)} 个文件）", not hits, hits[:5])
    # 理光数据只在应用数据目录
    home_files = [p.relative_to(cfg.home_dir).as_posix() for p in cfg.home_dir.rglob("*") if p.is_file()]
    print("   应用数据目录文件数:", len(home_files), home_files[:6])
    leak = [p for p in cfg.library_dir.rglob("*") if p.is_file() and p.name.upper().endswith((".DAT", ".ENTRY", ".NPZ"))]
    check("图库目录里没有 .dat/.entry/.npz", not leak, leak)

    # 数据版本：换数据后旧缓存失效；换 g127 后标定应判不匹配或仍有效
    r = c.get("/api/photos?limit=3", headers=A).json()
    print("   photo url sample:", r[0]["thumb_url"])

failed = [r for r in results if r[1] is False]
print(f"\n== {len(results)} 项, 失败 {len(failed)}")
for f in failed:
    print("FAILED:", f)
