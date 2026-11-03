"""真实接口核对：改选 LUT 输入空间后，缩略图和图片链接都必须变化。"""

import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings

OUT = Path(__file__).resolve().parent
LABEL = os.environ.get("LUT_CHECK_LABEL", "cache_probe")
TMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut") / LABEL


def main():
    audit.forbid_volumes()
    audit.forbid_network(True)
    volumes = TMP / "volumes"
    dcim = volumes / "SYNTHETIC/DCIM/100RICOH"
    dcim.mkdir(parents=True)
    Image.new("RGB", (300, 200), (40, 100, 180)).save(dcim / "SYNTHETIC.JPG", quality=100, subsampling=0)
    settings = Settings(library_dir=TMP / "library", home_dir=TMP / "app", export_dir=TMP / "exports",
                        volumes_roots=(volumes,), token="cache-probe-token", port=8765, min_free_bytes=0)
    rows = "\n".join(f"{r*.5} {g*.8} {b}" for b in (0, 1) for g in (0, 1) for r in (0, 1))
    data = f'TITLE "synthetic"\nLUT_3D_SIZE 2\n{rows}\n'.encode()
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8765", headers={"X-GXR-Token": settings.token}) as client:
        card = client.get("/api/cards").json()[0]
        job = client.post("/api/import", json={"card_id": card["id"]}).json()
        for _ in range(1000):
            result = client.get(f"/api/jobs/{job['id']}").json()
            if not result["running"]:
                break
            time.sleep(0.01)
        assert result["error"] is None
        photo = client.get("/api/photos").json()[0]
        lut = client.post("/api/lut/upload", content=data, headers={"X-GXR-Filename": "sample.cube"}).json()
        cid = lut["cube_id"]
        assert client.patch(f"/api/luts/{cid}", json={"input_space": "srgb"}).status_code == 200
        assert client.put(f"/api/photos/{photo['id']}/edit", json={"lut": cid}).status_code == 200
        before = client.get(f"/api/photos/{photo['id']}").json()
        first = client.get(before["thumb_url"])
        assert first.status_code == 200
        assert client.patch(f"/api/luts/{cid}", json={"input_space": "gamma24"}).status_code == 200
        after = client.get(f"/api/photos/{photo['id']}").json()
        second = client.get(after["thumb_url"])
        direct = client.get(f"/api/photos/{photo['id']}/render?stage=final&max_edge=240")
        assert second.status_code == 200 and direct.status_code == 200
        record = {
            "before_url": before["thumb_url"], "after_url": after["thumb_url"],
            "url_changed": before["thumb_url"] != after["thumb_url"],
            "thumb_changed": first.content != second.content,
            "before_sha256": hashlib.sha256(first.content).hexdigest(),
            "after_sha256": hashlib.sha256(second.content).hexdigest(),
            "before_mean_rgb": np.asarray(Image.open(io.BytesIO(first.content))).mean(axis=(0, 1)).tolist(),
            "after_mean_rgb": np.asarray(Image.open(io.BytesIO(second.content))).mean(axis=(0, 1)).tolist(),
            "direct_mean_rgb": np.asarray(Image.open(io.BytesIO(direct.content))).mean(axis=(0, 1)).tolist(),
        }
        (OUT / f"{LABEL}.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        assert record["url_changed"] and record["thumb_changed"], "LUT 空间改选后缩略图仍使用旧缓存"


if __name__ == "__main__":
    main()
