"""独立构造 TIFF 标签，核对渲染路径及只读真机样本。"""

import io
import json
from pathlib import Path
import warnings

import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.cards.session import SessionRegistry
from gxr_studio.config import Settings
from gxr_studio.finish import meta_text
from gxr_studio.lut import scene
from gxr_studio.raw import RawDecodeError, open_dng, render_half
from gxr_studio.raw.codes import half_res_codes
from gxr_studio.raw.tiff import Tiff

from review_support import BASE, ModelProbe, card_at, digest, dng_bytes, options, record, tree


@pytest.mark.parametrize("tag", [50721, 50722, 50723, 50724, 50964, 50965])
@pytest.mark.parametrize("form", ["zero_denominator", "nan", "infinity"])
def test_matrix_nonfinite_values(tag, form):
    if form == "zero_denominator":
        entry = (10, [(0, 0)] + [(1 if i % 4 == 0 else 0, 1) for i in range(1, 9)])
    else:
        entry = (12, [float("nan") if form == "nan" else float("inf")] + [1.0] * 8)
    raw = open_dng(dng_bytes({tag: entry}))
    with pytest.raises(scene.SceneError) as error:
        scene.scene_colour(raw)
    record("matrix_nonfinite_values", {"tag": tag, "form": form, "code": error.value.code})
    assert error.value.code == "bad_matrix"


@pytest.mark.parametrize("tag,count", [(50714, 1), (50715, 12), (50716, 10), (50717, 1),
                                     (50718, 2), (50727, 3), (50730, 1)])
@pytest.mark.parametrize("form", ["zero_denominator", "nan", "infinity"])
def test_other_render_nonfinite_values(tag, count, form):
    entry = (5, [(0, 0)] * count) if form == "zero_denominator" else (12, [float("nan") if form == "nan" else float("inf")] * count)
    with pytest.raises(RawDecodeError) as error:
        open_dng(dng_bytes({tag: entry}))
    record("other_render_nonfinite_values", {"tag": tag, "form": form, "error": str(error.value)})


@pytest.mark.parametrize("form", ["zero_denominator", "nan", "absent"])
def test_white_balance_missing_or_nonfinite(form):
    overrides = {50728: (5, [(0, 0), (1, 1), (1, 1)])}
    if form == "nan":
        overrides = {50728: (12, [float("nan"), 1, 1])}
    raw = open_dng(dng_bytes(overrides, absent=[50728] if form == "absent" else []))
    with pytest.raises(RawDecodeError):
        half_res_codes(raw)
    with pytest.raises(scene.SceneError) as error:
        scene.scene_colour(raw)
    record("white_balance_missing_or_nonfinite", {"form": form, "scene_code": error.value.code})
    assert error.value.code == "no_neutral"


@pytest.mark.parametrize("typ,values", [(5, [(0, 0)] * 16), (12, [float("nan")] * 16), (4, list(range(16)))])
def test_linearization_type(typ, values):
    with pytest.raises(RawDecodeError) as error:
        open_dng(dng_bytes({50712: (typ, values)}))
    record("linearization_type", {"type": typ, "error": str(error.value)})


def test_missing_matrix_and_lens_information():
    data = dng_bytes(absent=[50721])
    raw = open_dng(data)
    tags = Tiff(data).ifd(Tiff(data).root)
    lens = tags[50736]["value"]
    assert np.isnan(lens[2:]).all()
    assert np.isfinite(half_res_codes(raw)).all()
    assert render_half(raw).shape == (5, 6, 3)
    with pytest.raises(scene.SceneError) as error:
        scene.scene_colour(raw)
    record("missing_matrix_and_lens_information", {"scene_code": error.value.code, "raw_rendered": True})
    assert error.value.code == "no_matrix"


@pytest.mark.parametrize("form", ["zero_forward", "equal_levels"])
def test_computed_values_are_finite(form):
    tags = {50964: (10, [(0, 1)] * 9)} if form == "zero_forward" else {50714: (3, [64]), 50717: (4, [64])}
    error = None
    values = None
    rendered = None
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        try:
            raw = open_dng(dng_bytes(tags))
            codes = half_res_codes(raw)
            values = scene.scene_colour(raw).xyz(codes.reshape(-1, 3)) if form == "zero_forward" else codes
            if form == "equal_levels":
                image = render_half(raw)
                rendered = {"shape": list(image.shape), "sha256": digest(image.tobytes())}
        except (RawDecodeError, scene.SceneError, ValueError, np.linalg.LinAlgError, ZeroDivisionError) as exc:
            error = type(exc).__name__ + ": " + str(exc)
    finite = values is None or bool(np.isfinite(values).all())
    record("computed_values_are_finite", {"form": form, "error": error, "finite": finite,
           "rendered": rendered,
           "nonfinite_count": 0 if values is None else int((~np.isfinite(values)).sum()),
           "nan_count": 0 if values is None else int(np.isnan(values).sum()),
           "infinity_count": 0 if values is None else int(np.isinf(values).sum()),
           "warnings": [str(item.message) for item in observed]})
    assert error is not None or finite


def test_mount_sample_import_and_export(tmp_path):
    sample = BASE / "captures/street-g137-20261031/dng/R8051530.DNG"
    audit.protect(sample.parent)
    try:
        original = sample.read_bytes()
        original_stat = sample.stat()
        raw = open_dng(original)
        assert np.isfinite(half_res_codes(raw)).all()
        json.dumps(raw.summary(), allow_nan=False)
        image = render_half(raw)
        assert image.ndim == 3 and image.dtype == np.uint8
        card = card_at(tmp_path, ("dng",))
        source = card.root / "DCIM/100RICOH/R0000001.DNG"
        source.write_bytes(original)
        settings = Settings(library_dir=tmp_path / "library", home_dir=tmp_path / "app-data",
                            export_dir=tmp_path / "exports", volumes_roots=(tmp_path / "volumes",),
                            min_free_bytes=0, token="local-review-token", port=18765)
        app = create_app(settings, sessions=SessionRegistry(probe=ModelProbe()))
        with TestClient(app, base_url="http://127.0.0.1:18765", headers={"X-GXR-Token": settings.token}) as client:
            before = tree(card.root)
            cards = client.get("/api/cards").json()
            response = client.post("/api/import", json={"card_id": cards[0]["id"]})
            assert response.status_code == 202, response.text
            job = app.state.ctx.jobs.get(response.json()["id"])
            job.thread.join(180)
            assert not job.running and job.error is None
            progress = client.get(f"/api/jobs/{job.id}").json()["progress"]
            assert progress["card_id"] == cards[0]["id"] and progress["coverage"]["all_imported"]
            library = app.state.ctx.lib
            shot_id = library.db.execute("SELECT shot_id FROM shots").fetchone()[0]
            shot = library.get_shot(shot_id)
            assert "MOUNT" in (shot.get("lens") or "")
            metadata, _, _ = meta_text.photo_meta(library, shot)
            json.dumps(metadata, allow_nan=False)
            preview = client.get(f"/api/photos/{shot_id}/preview")
            assert preview.status_code == 200, preview.text[:200]
            with Image.open(io.BytesIO(preview.content)) as photo:
                photo.load()
                preview_dimensions = photo.size
            exported = client.post(f"/api/photos/{shot_id}/export", json={"source": "neutral", "long_edge": 768})
            assert exported.status_code == 200, exported.text
            path = Path(exported.json()["path"])
            with Image.open(path) as photo:
                photo.load()
                dimensions = photo.size
                assert max(dimensions) == 768
            record("mount_sample_import_and_export", {"sample": str(sample.relative_to(BASE)), "sample_sha256": digest(original),
                   "raw_shape": [raw.height, raw.width], "half_shape": list(image.shape), "lens": shot.get("lens"),
                   "progress": progress, "preview_dimensions": preview_dimensions,
                   "export_dimensions": dimensions, "export_sha256": digest(path.read_bytes()),
                   "card_unchanged": before == tree(card.root)})
            assert before == tree(card.root)
        assert sample.stat().st_mtime_ns == original_stat.st_mtime_ns
        assert digest(sample.read_bytes()) == digest(original)
    finally:
        audit.unprotect(sample.parent)
