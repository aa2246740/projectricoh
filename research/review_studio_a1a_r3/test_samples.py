"""只读真机样本的 RAW 渲染、导入、预览与导出。"""

import io
import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from gxr_studio import audit, meta
from gxr_studio.app import create_app
from gxr_studio.cards.importer import ImportOptions
from gxr_studio.cards.session import SessionRegistry
from gxr_studio.config import Settings
from gxr_studio.lut.scene import scene_colour
from gxr_studio.raw import half_res_codes, open_dng, render_full, render_half

from review_support import BASE, ModelProbe, card_at, digest, record, tree


def test_real_mount_and_50mm_paths(tmp_path):
    directory = BASE / "captures/street-g137-20261031/dng"
    audit.forbid_volumes()
    audit.forbid_network()
    audit.protect(directory)
    selected = {}
    inventory = []
    try:
        for path in sorted(directory.glob("*.DNG")):
            before = path.stat()
            info = meta.read_dng_meta(path)
            assert info.error is None
            unit = "mount" if "MOUNT" in (info.lens or "") else "50mm" if "50mm" in (info.lens or "") else "other"
            inventory.append({"name": path.name, "lens": info.lens, "unit": unit, "size": before.st_size,
                              "sha256": digest(path.read_bytes()), "mtime_ns": before.st_mtime_ns,
                              "ctime_ns": before.st_ctime_ns})
            if unit in ("mount", "50mm") and unit not in selected:
                selected[unit] = path
        record("sample_inventory", {"files": inventory, "selected": {key: path.name for key, path in selected.items()}})
        if "50mm" not in selected:
            additional = BASE / "captures/a12-50"
            for path in sorted(additional.rglob("*.DNG")):
                info = meta.read_dng_meta(path)
                if info.error is None and "50mm" in (info.lens or ""):
                    selected["50mm"] = path
                    st = path.stat()
                    record("sample_inventory_additional", {"sample": str(path.relative_to(BASE)), "lens": info.lens,
                           "size": st.st_size, "sha256": digest(path.read_bytes()),
                           "mtime_ns": st.st_mtime_ns, "ctime_ns": st.st_ctime_ns})
                    break
        assert set(selected) == {"mount", "50mm"}, selected
        for unit, sample in selected.items():
            audit.protect(sample)
            data = sample.read_bytes()
            original_stat = sample.stat()
            raw = open_dng(data)
            codes = half_res_codes(raw)
            assert np.isfinite(codes).all()
            half = render_half(raw)
            full = render_full(raw)
            assert half.dtype == np.uint8 and full.dtype == np.uint8
            assert full.shape[0] >= half.shape[0] * 2 and full.shape[1] >= half.shape[1] * 2
            json.dumps(raw.summary(), allow_nan=False)
            xyz = scene_colour(raw).xyz(codes[::64, ::64].reshape(-1, 3))
            assert np.isfinite(xyz).all()
            area = tmp_path / unit
            card = card_at(area, ("dng",))
            source = card.root / "DCIM/100RICOH/R0000001.DNG"
            source.write_bytes(data)
            settings = Settings(library_dir=area / "library", home_dir=area / "app-data", export_dir=area / "exports",
                                volumes_roots=(area / "volumes",), min_free_bytes=0, token="local-review", port=18765)
            app = create_app(settings, sessions=SessionRegistry(probe=ModelProbe()),
                             import_options=ImportOptions(min_free_bytes=0, make_thumbs=False))
            with TestClient(app, base_url="http://127.0.0.1:18765", headers={"X-GXR-Token": settings.token}) as client:
                before_card = tree(card.root)
                cards = client.get("/api/cards").json()
                response = client.post("/api/import", json={"card_id": cards[0]["id"]})
                assert response.status_code == 202, response.text
                job = app.state.ctx.jobs.get(response.json()["id"])
                job.thread.join(540)
                assert not job.running and job.error is None
                progress = client.get(f"/api/jobs/{job.id}").json()["progress"]
                assert progress["coverage"]["all_imported"]
                shot = app.state.ctx.lib.list_shots()[0]
                shot_id = shot["shot_id"]
                preview = client.get(f"/api/photos/{shot_id}/preview")
                assert preview.status_code == 200
                with Image.open(io.BytesIO(preview.content)) as photo:
                    photo.load()
                    preview_size = photo.size
                exported = client.post(f"/api/photos/{shot_id}/export", json={"source": "neutral", "long_edge": 768})
                assert exported.status_code == 200, exported.text
                output = Path(exported.json()["path"])
                with Image.open(output) as photo:
                    photo.load()
                    export_size = photo.size
                    assert max(export_size) == 768
                assert before_card == tree(card.root)
                record("real_camera_render", {"unit": unit, "sample": str(sample.relative_to(BASE)),
                       "sample_sha256": digest(data), "half_shape": list(half.shape), "full_shape": list(full.shape),
                       "half_sha256": digest(half.tobytes()), "full_sha256": digest(full.tobytes()),
                       "xyz_finite": True, "lens": shot["lens"], "progress": progress,
                       "preview_size": preview_size, "export_size": export_size,
                       "export_sha256": digest(output.read_bytes()), "card_unchanged": True})
            assert sample.stat().st_mtime_ns == original_stat.st_mtime_ns
            assert sample.stat().st_ctime_ns == original_stat.st_ctime_ns
            assert digest(sample.read_bytes()) == digest(data)
            audit.unprotect(card.root)
    finally:
        audit.unprotect(directory)
