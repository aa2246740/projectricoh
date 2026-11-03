"""复跑六包往返和相机 C 的 552 B 比较；报告只保存摘要。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1")
sys.path.insert(0, str(ROOT / "studio/tests"))

from g152_support import PACKAGES, UNITS, CameraReference, dat_path
from gxr_studio.camdata import datcodec as dc, store
from gxr_studio.render.params import RecipeSel
from gxr_studio.render.recipes import CameraData


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    paths = [dat_path(g, t) for g, t in PACKAGES]
    for generation, version in ((152, 60), (153, 62)):
        base = ROOT / f"firmware/engine_v{version}_g{generation}/candidate"
        paths.extend(p for p in base.rglob("*") if p.is_file() and p.suffix in (".c", ".h"))
    paths += [ROOT / p for p in ("research/looks_g152/dat_format.py", "research/looks_g152/control_parity.py",
                                "research/looks_g152/REPORT.md", "research/v39_g153/REPORT.md",
                                "research/looks_expansion_design/DESIGN.md")]
    initial = {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}
    references = {g: CameraReference(g, SCRATCH / f"proof/reference-{g}") for g in (152, 153)}
    packages, rows, users = [], [], []
    for generation, test in PACKAGES:
        path = dat_path(generation, test)
        raw = path.read_bytes()
        dat = dc.parse(raw)
        assert dc.pack(dat) == raw
        home = SCRATCH / f"proof/home-{generation}-{test}"
        store.import_from_dat(raw, home)
        camera = CameraData(home)
        packages.append({"generation": generation, "test": test, "path": str(path.relative_to(ROOT)), "bytes": len(raw),
                         "sha256": digest(path), "round_trip": True, "looks": len(dat.looks), "users": len(dat.users)})
        for unit, catalog in enumerate(camera.listing()):
            for index, info in enumerate(catalog["looks"]):
                selection = RecipeSel(UNITS[unit], info["slot"], kind="look", id=info["id"])
                actual = camera.resolve(selection).entry
                expected = references[generation].resolve(raw, unit, index, {})
                assert actual == expected and len(actual) == 552
                rows.append({"generation": generation, "test": test, "unit": UNITS[unit], "index": index,
                             "name": info["name"], "bytes": 552, "equal": True,
                             "studio_sha256": hashlib.sha256(actual).hexdigest(), "camera_sha256": hashlib.sha256(expected).hexdigest()})
            if generation in references:
                for index, info in enumerate(catalog["users"]):
                    selection = RecipeSel(UNITS[unit], info["slot"], kind="camera_user", id=info["id"])
                    actual = camera.resolve(selection).entry
                    assert actual == references[generation].user(raw, unit, index)
                    users.append({"generation": generation, "unit": UNITS[unit], "name": info["name"],
                                  "equal": True, "sha256": hashlib.sha256(actual).hexdigest()})
        if generation == 152 and test:
            (SCRATCH / "ui_catalog.json").write_text(json.dumps({"units": camera.listing()}, ensure_ascii=False))
    final = {str(p.relative_to(ROOT)): digest(p) for p in sorted(set(paths))}
    assert initial == final
    result = {"status": "PASS", "packages": packages, "look_comparisons": len(rows), "rows": rows,
              "user_comparisons": len(users), "users": users, "inputs_unchanged": True, "input_sha256": final}
    (HERE / "byte_equality.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "users", "input_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
