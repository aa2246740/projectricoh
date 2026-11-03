"""Check auto correction against a generated, originally level photograph."""
from __future__ import annotations
import json
from pathlib import Path
import httpx
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r2")
ready = json.loads((SCRATCH / "server-ready.json").read_text())
assert ready["port"] != 49667
folder = SCRATCH / "library/2026/2026-10-31"
folder.mkdir(parents=True, exist_ok=True)
image = Image.new("RGB", (640, 480), (30, 30, 30))
draw = ImageDraw.Draw(image)
for y in (100, 220, 340):
    draw.line((50, y, 590, y), fill=(220, 220, 220), width=4)
image.save(folder / "REVIEW_LINES.JPG", quality=97)
Image.new("RGB", (640, 480), (128, 128, 128)).save(folder / "REVIEW_FLAT.JPG", quality=97)
with httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}",
                  headers={"X-GXR-Token": "independent-review-browser"},
                  limits=httpx.Limits(max_keepalive_connections=0), timeout=180) as c:
    rebuilt = c.post("/api/library/rebuild", json={})
    assert rebuilt.status_code == 200, rebuilt.text
    sid = next(p["id"] for p in c.get("/api/photos").json() if p["name"] == "REVIEW_LINES")
    results = []
    for angle in (0, 10):
        assert c.put(f"/api/photos/{sid}/edit", json={"geometry": {"straighten": angle}}).status_code == 200
        found = c.post(f"/api/photos/{sid}/geometry/auto").json()
        results.append({"current": angle, "suggested": found})
        if angle == 10 and found["confident"]:
            applied = c.put(f"/api/photos/{sid}/edit", json={"geometry": {"straighten": found["straighten"], "vertical": found["vertical"]}})
            actual = c.get(f"/api/photos/{sid}/edit").json()["geometry"]
            again = c.post(f"/api/photos/{sid}/geometry/auto").json()
            results.append({"apply_status": applied.status_code, "apply_result": applied.json(), "actual_current": actual, "suggested": again})
    flat = next(p["id"] for p in c.get("/api/photos").json() if p["name"] == "REVIEW_FLAT")
    c.put(f"/api/photos/{flat}/edit", json={"geometry": {"straighten": 0, "vertical": 0}})
    miss = c.post(f"/api/photos/{flat}/geometry/auto")
    results.append({"no_lines_status": miss.status_code, "no_lines": miss.json()})
(HERE / "auto-level-lines.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(results, ensure_ascii=False, indent=2))
