"""probe_d 的修复后版本（studio-fix-review-r1）。

原 probe_d 里"界面横幅"那一行是探针自己用 Python 抄的旧 import.js 逻辑（`ui = f"导入完成：…现在可以安全弹出卡了。"` 写死在探针里），
所以不管前端怎么改，它都会"复现"——它没有办法变成"通过"。这里保持同样的场景（用 before_verify 把 R0000102.JPG 在暂存文件上翻一个字节，
模拟读卡器不稳），但横幅文字改成用真正的前端模块 `web/assets/import_summary.js`（用 node 直接跑）对后端进度算出来，
再断言：校验失败时不能出现"安全弹出"，不能是绿色，要列出文件名，要建议先别格式化。
  studio/.venv/bin/python -I probe_d_fixed.py <临时目录> <仓库根>
"""
import json
import subprocess
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
REPO = Path(sys.argv[2])
PORT, TOKEN = 45126, "tok-" + "w" * 40
audit.forbid_volumes()
audit.forbid_network()
vols = T / "vols"
card = sy.make_card(vols, "FLAKY", samples=None)
cfg = Settings(library_dir=T / "lib", home_dir=T / "home", export_dir=T / "exp", volumes_roots=(vols,), token=TOKEN, port=PORT)


def corrupt(part, cf):
    if cf.relpath.endswith("R0000102.JPG"):
        with open(part, "r+b") as f:
            f.seek(100); b = f.read(1); f.seek(100); f.write(bytes([b[0] ^ 0xFF]))


def frontend(progress: dict) -> dict:
    mod = (REPO / "studio/web/assets/import_summary.js").as_uri()
    js = (f"import * as S from {json.dumps(mod)};\nconst p = {json.dumps(progress)};\n"
          "console.log(JSON.stringify({s: S.summarizeImport(p), eject: S.canEject(p), status: S.doneStatusText(p)}));")
    return json.loads(subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True).stdout)


app = create_app(cfg, import_options=ImportOptions(before_verify=corrupt))
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
bad = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (("  " + str(detail)[:200]) if detail else ""))
    if not ok:
        bad.append(name)

with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
    cid = c.get("/api/cards", headers=A).json()[0]["id"]
    c.post("/api/import", json={"card_id": cid}, headers=A)
    while any(j["running"] for j in c.get("/api/jobs", headers=A).json()):
        time.sleep(0.2)
    p = c.get("/api/jobs", headers=A).json()[0]["progress"]
    print("后端 message  :", p["message"])
    ui = frontend(p)
    print("界面横幅      :", ui["s"]["kind"] or "(普通)", "|", ui["s"]["text"], "|", ui["s"]["detail"])
    print("状态栏        :", ui["status"])
    check("后端：校验失败的文件被列为失败", p["verify_failed"] == ["DCIM/100RICOH/R0000102.JPG"] and p["failed_shots"] == 1)
    check("后端消息里没有'安全弹出'", "安全弹出" not in p["message"])
    check("界面横幅不是绿色", ui["s"]["kind"] != "ok", ui["s"]["kind"])
    check("界面横幅没有'安全弹出'", "安全弹出" not in ui["s"]["text"])
    check("界面横幅建议先别格式化", "先别格式化" in ui["s"]["text"])
    check("界面横幅列出文件名", "R0000102.JPG" in ui["s"]["detail"], ui["s"]["detail"])
    check("状态栏也不说可以弹出", "安全弹出" not in ui["status"] and ui["eject"] is False)
    check("同一对里好的 DNG 照常导入了", any("R0000102" in r["relpath"] for r in c.app.state.ctx.lib.db.execute("select relpath from files")))
print(f"\n== 失败 {len(bad)}")
sys.exit(1 if bad else 0)
