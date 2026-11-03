"""探针 J：只有 DNG 的真实照片，导入相机数据+标定包之后，缩略图/大图是不是正常的图（不是黑的），和相机自己的 JPG 比有多大差别。
  studio/.venv/bin/python -I probe_j_rawonly_brightness.py <临时目录> <仓库根>"""
import io, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image
from starlette.testclient import TestClient
sys.path.insert(0, str(Path(sys.argv[2]) / "studio/tests"))
import e0_support as t
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.camdata import calib, store
from gxr_studio.config import Settings
from gxr_studio.devtools import synthetic_card as sy
T = Path(sys.argv[1]); PORT, TOKEN = 45130, "tok-" + "j" * 40
audit.forbid_volumes(); audit.forbid_network()
vols = T / "vols"; card = sy.make_card(vols, "C", samples=None)
dng = next(d for d in sorted(sy.DEFAULT_SAMPLES.glob("*.DNG")) if len(sys.argv) < 4 or d.stem == sys.argv[3])
shutil.copy2(dng, card.root / "DCIM/100RICOH/R0000900.DNG")
home = T / "home"
store.import_from_dat(t.fixture_dat(127), home); calib.import_calibration(home, calib.dev_sources(t.REPO))
cfg = Settings(library_dir=T / "lib", home_dir=home, export_dir=T / "exp", volumes_roots=(vols,), token=TOKEN, port=PORT, min_free_bytes=0)
A = {"Host": f"127.0.0.1:{PORT}", "X-GXR-Token": TOKEN}
with TestClient(create_app(cfg), base_url=f"http://127.0.0.1:{PORT}") as c:
    cid = c.get("/api/cards", headers=A).json()[0]["id"]
    j = c.post("/api/import", json={"card_id": cid}, headers=A).json()
    while c.get(f"/api/jobs/{j['id']}", headers=A).json()["running"]: time.sleep(0.1)
    p = next(x for x in c.get("/api/photos", headers=A).json() if x["name"] == "R0000900")
    print("preview_look:", p["preview_look"])
    ref = np.asarray(Image.open(dng.with_suffix(".JPG")).convert("RGB").resize((256, 192)), float)
    for kind in ("thumb", "preview"):
        r = c.get(f"/api/photos/{p['id']}/{kind}", headers=A)
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
        a = np.asarray(im.resize((256, 192)), float)
        print(kind, r.status_code, im.size, "平均亮度", round(a.mean(), 1), "相机 JPG 平均亮度", round(ref.mean(), 1), "平均绝对差", round(abs(a - ref).mean(), 1),
              "头：", {k: v for k, v in r.headers.items() if k.startswith("x-gxr")})
