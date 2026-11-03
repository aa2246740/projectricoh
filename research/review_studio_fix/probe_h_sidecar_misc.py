"""review-studio-fix-r1 探针 H：编辑记录的"格式没坏但内容怪/来自更新版本"的情形、批量导出里有失效照片 id、卷根目录不让读、.old 恢复。进程内，临时目录。
  studio/.venv/bin/python -I probe_h_sidecar_misc.py <临时目录>
"""
import json, os, subprocess, sys, time
from pathlib import Path
from starlette.testclient import TestClient
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings
from gxr_studio.devtools import synthetic_card as sy

T = Path(sys.argv[1]); PORT, TOKEN = 45128, "tok-" + "h" * 40
audit.forbid_volumes(); audit.forbid_network()
vols = T / "vols"; card = sy.make_card(vols, "C", samples=None)
cfg = Settings(library_dir=T / "lib", home_dir=T / "home", export_dir=T / "exp", volumes_roots=(vols,), token=TOKEN, port=PORT, min_free_bytes=0)
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
bad = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (("  | " + str(detail)[:230]) if detail else ""))
    if not ok: bad.append(name)
def plain(txt): return not any(s in txt for s in (str(T), "Traceback", "Expecting", "JSONDecode", "KeyError", "TypeError", "AttributeError"))

app = create_app(cfg)
with TestClient(app, base_url=f"http://127.0.0.1:{PORT}", raise_server_exceptions=False) as c:
    def req(m, p, **kw): return c.request(m, p, headers=A, **kw)
    cid = req("GET", "/api/cards").json()[0]["id"]
    j = req("POST", "/api/import", json={"card_id": cid}).json()
    while req("GET", f"/api/jobs/{j['id']}").json()["running"]: time.sleep(0.1)
    photos = req("GET", "/api/photos").json()
    p0 = next(p for p in photos if p["name"] == "R0000102")
    sid = p0["id"]
    lib = c.app.state.ctx.lib
    shot = lib.get_shot(sid); spath = lib.sidecar_path_for(shot)
    good = json.loads(spath.read_text())
    media_before = {k: lib.abspath(v["relpath"]).read_bytes() for k, v in shot["files"].items()}

    def sc_with(**over):
        d = json.loads(json.dumps(good)); d.update(over); return d
    cases = {
        "schema 比本程序新": sc_with(schema="gxr-studio/edit/99"),
        "crop 是字符串": sc_with(crop="oops"),
        "crop 缺字段": sc_with(crop={"preset": "3:2"}),
        "crop 数字越界": sc_with(crop={"preset": "3:2", "rect": [5, 5, 9, 9], "angle_deg": 999, "flip": False}),
        "adjust 是列表": sc_with(adjust=[1, 2]),
        "adjust 越界": sc_with(adjust={"exposure": 1e9}),
        "recipe 是数字": sc_with(recipe=5),
        "curve 乱写": sc_with(curve={"master": "x"}),
        "rev 是字符串": sc_with(rev="abc"),
        "顶层是列表": [],
        "顶层是 null": None,
    }
    for name, content in cases.items():
        spath.write_text(json.dumps(content))
        res = {}
        for label, m, path, kw in (("GET crop", "GET", f"/api/photos/{sid}/crop", {}), ("GET edit", "GET", f"/api/photos/{sid}/edit", {}),
                                   ("PUT crop", "PUT", f"/api/photos/{sid}/crop", {"json": {"preset": "1:1"}}),
                                   ("PUT edit", "PUT", f"/api/photos/{sid}/edit", {"json": {"adjust": {"contrast": 3}}}),
                                   ("export", "POST", f"/api/photos/{sid}/export", {"json": {}}),
                                   ("thumb", "GET", f"/api/photos/{sid}/thumb", {}), ("photo", "GET", f"/api/photos/{sid}", {})):
            r = req(m, path, **kw)
            res[label] = r.status_code
            txt = r.text if "json" in r.headers.get("content-type", "") else ""
            if r.status_code >= 500 or (label != "export" and not plain(txt)):
                check(f"[{name}] {label} → {r.status_code} 且回应干净", False, txt[:200])
        check(f"[{name}] 没有 500、回应里没有路径/异常原文", all(v < 500 for v in res.values()), res)
        spath.write_text(json.dumps(good))
    media_after = {k: lib.abspath(v["relpath"]).read_bytes() for k, v in shot["files"].items()}
    check("所有这些情形下照片文件字节不变", media_before == media_after)
    # schema 太新：不能被改写
    spath.write_text(json.dumps(cases["schema 比本程序新"]))
    before = spath.read_bytes()
    r = req("PUT", f"/api/photos/{sid}/crop", json={"preset": "1:1"})
    check("schema 太新：PUT crop 不覆盖（409/4xx，文件不变）", r.status_code in (409, 422) and spath.read_bytes() == before, (r.status_code, r.text[:100]))
    r = req("PUT", f"/api/photos/{sid}/edit", json={"adjust": {"contrast": 3}})
    check("schema 太新：PUT edit 不覆盖", r.status_code in (409, 422) and spath.read_bytes() == before, (r.status_code, r.text[:100]))
    r = req("POST", f"/api/photos/{sid}/export", json={}); check("schema 太新：导出仍可用", r.status_code == 200, (r.status_code, r.text[:100]))
    r = req("POST", "/api/library/rebuild")
    check("schema 太新：rebuild 不覆盖也不报 500", r.status_code < 500 and spath.read_bytes() == before, (r.status_code, r.text[:200]))
    spath.write_text(json.dumps(good))
    # 批量导出里有失效 id
    ids = [p["id"] for p in photos[:3]]
    r = req("POST", "/api/export", json={"ids": ids + ["0" * 16]})
    print("   批量导出含失效 id →", r.status_code, r.text[:120])
    check("批量导出含一个失效 id：整批被拒（记录现状）", r.status_code == 404, r.status_code)
    # 卷根目录不让读
    os.chmod(vols, 0)
    try:
        r1 = req("GET", "/api/cards"); r2 = req("GET", "/api/cards/status")
    finally:
        subprocess.run(["chmod", "755", str(vols)], check=True)
    check("卷根目录 chmod 000：/api/cards 200 且为空，不是 500", r1.status_code == 200 and r1.json() == [], (r1.status_code, r1.text[:80]))
    check("卷根目录 chmod 000：status 明说系统不让读", r2.json().get("access_denied") is True and "允许" in r2.json().get("message", "") or "权限" in r2.json().get("message", ""), r2.text[:260])
    r2 = req("GET", "/api/cards/status")
    check("恢复后提示消失", r2.json().get("access_denied") is False, r2.text[:100])
print(f"\n== FAIL {len(bad)}: {bad}")
sys.exit(1 if bad else 0)
