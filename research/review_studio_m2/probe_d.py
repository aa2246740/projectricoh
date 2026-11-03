"""review-studio-m2-r1 的复审探针 D：复制后校验失败（读卡器不稳）时，界面拿到的是什么。
用测试钩子 before_verify 在暂存文件上翻转一个字节，模拟“读回来哈希对不上”。临时目录，进程内。
  studio/.venv/bin/python -I probe_d.py <临时目录>
"""
import sys
import time
from pathlib import Path

from starlette.testclient import TestClient

from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.cards.importer import ImportOptions
from gxr_studio.config import Settings
from gxr_studio.devtools import synthetic_card as sy

T = Path(sys.argv[1])
PORT, TOKEN = 45126, "tok-" + "w" * 40
audit.forbid_volumes()
audit.forbid_network()
vols = T / "vols"
card = sy.make_card(vols, "FLAKY", samples=None)
cfg = Settings(library_dir=T / "lib", home_dir=T / "home", export_dir=T / "exp", volumes_roots=(vols,), token=TOKEN, port=PORT)


def corrupt(part, cf):
    if cf.relpath.endswith("R0000102.JPG"):  # 只让这一个文件“读回来不一致”
        with open(part, "r+b") as f:
            f.seek(100); b = f.read(1); f.seek(100); f.write(bytes([b[0] ^ 0xFF]))


app = create_app(cfg, import_options=ImportOptions(before_verify=corrupt))
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
    cid = c.get("/api/cards", headers=A).json()[0]["id"]
    c.post("/api/import", json={"card_id": cid}, headers=A)
    while any(j["running"] for j in c.get("/api/jobs", headers=A).json()):
        time.sleep(0.2)
    p = c.get("/api/jobs", headers=A).json()[0]["progress"]
    print("state          :", p["state"])
    print("imported_shots :", p["imported_shots"], "  verify_failed:", p["verify_failed"], "  unreadable:", p["unreadable"])
    print("后端 message   :", p["message"])
    # 界面 import.js summarize() 只看 unreadable，所以这里它会显示成：
    skipped = p["seen_shots"] + p["duplicate_shots"]
    ui = f"导入完成：新增 {p['imported_shots']} 张，跳过 {skipped} 张（之前导入过或内容重复）。现在可以安全弹出卡了。"
    print("界面横幅(按 import.js 逻辑，kind=%s) :" % ("ok（绿色）" if not p["unreadable"] else "普通"), ui)
    ok = bool(p["verify_failed"]) and "安全弹出" in ui
    print("\n结论：", "校验失败的文件没有进图库，但界面是绿色的『可以安全弹出卡了』且一个字没提它" if ok else "未复现")
