"""review-studio-fix-r1 探针 I：导入相机数据/标定包会清掉"只有 DNG 的缩略图缓存"；浏览器同时在取缩略图时，会不会出 500。
进程内（TestClient 多线程），临时目录。
  studio/.venv/bin/python -I probe_i_thumb_race.py <临时目录> <仓库根>
"""
import shutil, sys, threading, time
from pathlib import Path
from starlette.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
from gxr_studio.devtools import synthetic_card as sy
from gxr_studio.library import thumbs

T = Path(sys.argv[1]); REPO = Path(sys.argv[2]); PORT, TOKEN = 45129, "tok-" + "i" * 40
audit.forbid_volumes(); audit.forbid_network()
vols = T / "vols"; card = sy.make_card(vols, "C", samples=None)
real = sorted(sy.DEFAULT_SAMPLES.glob("*.DNG"))[:2]
for i, d in enumerate(real):
    shutil.copy2(d, card.root / "DCIM/100RICOH" / f"R000090{i}.DNG")     # 只有 DNG 的真实照片
cfg = Settings(library_dir=T / "lib", home_dir=T / "home", export_dir=T / "exp", volumes_roots=(vols,), token=TOKEN, port=PORT, min_free_bytes=0)
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
app = create_app(cfg)
stop = threading.Event(); counts = {"ok": 0, "500": 0, "other": 0}; bad = []
with TestClient(app, base_url=f"http://127.0.0.1:{PORT}", raise_server_exceptions=False) as c0:
    cid = c0.get("/api/cards", headers=A).json()[0]["id"]
    j = c0.post("/api/import", json={"card_id": cid}, headers=A).json()
    while c0.get(f"/api/jobs/{j['id']}", headers=A).json()["running"]: time.sleep(0.1)
    ids = [p["id"] for p in c0.get("/api/photos", headers=A).json() if p["name"].startswith("R00009")]
    print("只有 DNG 的真实照片：", ids)
    lib = c0.app.state.ctx.lib
    lock = threading.Lock()
    def getter():
        with TestClient(app, base_url=f"http://127.0.0.1:{PORT}", raise_server_exceptions=False) as c:
            while not stop.is_set():
                for i in ids:
                    r = c.get(f"/api/photos/{i}/thumb", headers=A)
                    with lock:
                        if r.status_code == 200: counts["ok"] += 1
                        elif r.status_code >= 500: counts["500"] += 1; bad.append(r.text[:120])
                        else: counts["other"] += 1
    def purger():
        while not stop.is_set():
            thumbs.purge_variants(lib)
            time.sleep(0.001)
    ths = [threading.Thread(target=getter) for _ in range(3)] + [threading.Thread(target=purger)]
    for t in ths: t.start()
    time.sleep(25); stop.set()
    for t in ths: t.join()
print(counts, bad[:2])
print("== 复现" if counts["500"] else "== 未复现（25 秒）")
