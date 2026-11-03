"""Focused follow-ups against temp_server.py, after browser acceptance has ended."""
from __future__ import annotations
import cProfile
import hashlib
import io
import json
import os
from pathlib import Path
import pstats
import sys
import time

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "studio"
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2")
sys.path.insert(0, str(STUDIO / "src"))
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from gxr_studio.finish.geometry import warp, normalized_valid_rect
from gxr_studio.finish.spec import Geometry
from gxr_studio.engine import colour


def arr(response):
    assert response.status_code == 200, (response.status_code, response.text[:200])
    return np.asarray(Image.open(io.BytesIO(response.content)).convert("RGB"))


def main():
    ready = json.loads((SCRATCH / "server-ready.json").read_text())
    assert ready["port"] != 49667
    c = httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}", headers={"X-GXR-Token": "independent-review-browser"},
                     timeout=180, limits=httpx.Limits(max_keepalive_connections=0))
    results = {}
    photos = {p["name"]: p for p in c.get("/api/photos").json()}
    jpg, raw, pristine = (photos[name]["id"] for name in ("REVIEW", "R8051219", "R8051148"))
    def reset(sid):
        assert c.delete(f"/api/photos/{sid}/edit").status_code == 200
        assert c.delete(f"/api/photos/{sid}/crop").status_code == 200
    def defaults(style):
        return c.put("/api/defaults/finish", json={"frame": {"style": style}, "stamp": {"enabled": False}})
    def put(sid, body):
        return c.put(f"/api/photos/{sid}/edit", json=body)
    defaults("none")
    original_thumb = c.get(f"/api/photos/{pristine}/thumb").content
    defaults("gallery")
    with_defaults = c.get(f"/api/photos/{pristine}/thumb")
    results["pristine_defaults"] = {"sidecar_rev": photos["R8051148"]["sidecar_rev"],
        "thumbnail_unchanged": original_thumb == with_defaults.content,
        "thumbnail_cache": with_defaults.headers.get("cache-control"),
        "preview_shape": list(arr(c.get(f"/api/photos/{pristine}/render?stage=final&size=preview")).shape)}
    defaults("none")
    reset(jpg)
    for preset in ("1:1", "16:9"):
        c.put(f"/api/photos/{jpg}/crop", json={"preset": preset})
        saved = c.get(f"/api/photos/{jpg}/crop").json()
        preview = arr(c.get(f"/api/photos/{jpg}/render?stage=final&size=full"))
        output = c.post(f"/api/photos/{jpg}/export", json={"quality": 95}).json()
        with Image.open(output["path"]) as im:
            results["jpg_crop_" + preset] = {"orientation": saved["orientation"], "preview_wh": [preview.shape[1], preview.shape[0]],
                                            "export_wh": list(im.size), "rect": saved["rect"]}
    reset(raw)
    pv = arr(c.get(f"/api/photos/{raw}/render?stage=final&size=full&quality=95"))
    output = c.post(f"/api/photos/{raw}/export", json={"quality": 95}).json()
    with Image.open(output["path"]) as im:
        exif = dict(im.getexif())
        cjpg = np.asarray(im.resize((pv.shape[1], pv.shape[0]), Image.Resampling.LANCZOS))
    results["plain_raw_preview_export"] = {"preview_wh": [pv.shape[1], pv.shape[0]],
        "export_wh": [output["width"], output["height"]],
        "mean_de00": float(colour.delta_e00(colour.lab_from_codes(pv), colour.lab_from_codes(cjpg)).mean()),
        "plain_exif_tags": sorted(exif)}
    put(raw, {"geometry": {"straighten": 0}})
    timings = {}
    # HTTP timings use the actual browser query, changed geometry and completed image decode.
    for size in ("preview", "full"):
        elapsed = []
        for n in range(5):
            start = time.perf_counter()
            image = arr(c.post(f"/api/photos/{raw}/render?stage=uncropped&size={size}", json={"geometry": {"straighten": 6 + n / 10}}))
            elapsed.append(round(time.perf_counter() - start, 4))
        timings[size] = {"seconds": elapsed, "median": float(np.median(elapsed)), "shape": list(image.shape), "failures": 0}
    results["loopback_latency"] = timings
    (HERE / "focused.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    # Separate profile, never part of the reported timings.
    with cProfile.Profile() as profile:
        warped, valid = warp(np.full((1424, 2144, 3), 100, np.uint8), Geometry(straighten=6))
        normalized_valid_rect(valid)
    with (HERE / "geometry-profile.txt").open("w") as stream:
        pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(15)
    reset(jpg)
    put(jpg, {"frame": {"style": "gallery"}})
    results["bad_format"] = {"status": c.post(f"/api/photos/{jpg}/export", json={"format": "tiff"}).status_code}
    bad = put(jpg, {"stamp": {"enabled": True, "date_override": "2026-99-99"}})
    results["saved_bad_date"] = {"save_status": bad.status_code,
        "preview_status": c.get(f"/api/photos/{jpg}/render?stage=final&size=preview").status_code,
        "export_status": c.post(f"/api/photos/{jpg}/export", json={}).status_code}
    reset(jpg)
    put(jpg, {"geometry": {"rotate90": 1}, "stamp": {"enabled": True, "content": "text", "text": "W" * 24,
                                                             "font": "sans", "size": "large", "glow": False}})
    text = arr(c.get(f"/api/photos/{jpg}/render?stage=final&size=full&quality=95"))
    Image.fromarray(text).save(HERE / "stamp-long-text.png")
    face = ImageFont.truetype(str(STUDIO / "src/gxr_studio/assets/fonts/AtkinsonHyperlegible-Regular.ttf"), round(480 * .078))
    length = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength("W" * 24, font=face)
    results["long_text"] = {"image_width": text.shape[1], "text_width": length, "text_length": 24}
    # Every finishing tool is visible through the actual API, not just its pure helper.
    reset(jpg)
    baseline = arr(c.get(f"/api/photos/{jpg}/render?stage=final&size=full&quality=95"))
    finishing = {}
    for name, body in (("gallery", {"frame": {"style": "gallery"}}),
                       ("leica", {"frame": {"style": "leica"}}),
                       ("hasselblad", {"frame": {"style": "hasselblad"}}),
                       ("film", {"frame": {"style": "film"}}),
                       ("instant", {"frame": {"style": "instant", "text": "GXR"}}),
                       ("canvas", {"frame": {"style": "canvas", "canvas_ratio": "4:5"}}),
                       ("stamp", {"stamp": {"enabled": True, "content": "date", "date_override": "2026-10-31"}})):
        reset(jpg)
        assert put(jpg, body).status_code == 200
        preview = arr(c.get(f"/api/photos/{jpg}/render?stage=final&size=full&quality=95"))
        output = c.post(f"/api/photos/{jpg}/export", json={"quality": 95}).json()
        exported = np.asarray(Image.open(output["path"]).convert("RGB"))
        finishing[name] = {"preview_wh": [preview.shape[1], preview.shape[0]], "export_wh": [exported.shape[1], exported.shape[0]],
            "visible": preview.shape != baseline.shape or not np.array_equal(preview, baseline),
            "preview_export_mae": float(np.abs(preview.astype(float) - exported.astype(float)).mean()) if preview.shape == exported.shape else None}
    results["finish_visibility"] = finishing
    reset(jpg)
    defaults("none")
    c.close()
    (HERE / "focused.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
