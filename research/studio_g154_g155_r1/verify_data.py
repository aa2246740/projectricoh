"""复跑四包的完整 552 B 对照，并与基线比较旧代数。仅保存摘要。"""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO = ROOT / "studio"
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g154-g155-r1")
sys.path.insert(0, str(STUDIO / "tests"))

from e0_support import FIXTURE_DATS
from g152_support import CameraReference, UNITS, dat_path
from gxr_studio.camdata import datcodec as dc, store
from gxr_studio.render.params import RecipeSel
from gxr_studio.render.recipes import CameraData


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_baseline(module_name, path):
    source = subprocess.check_output(["git", "show", f"e6738e8:{path}"], cwd=STUDIO, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    target = SCRATCH / "baseline" / Path(path).name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)
    spec = importlib.util.spec_from_file_location(module_name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def new_packages():
    packages, rows, skipped = [], [], []
    point_comparisons = 0
    references = {}
    for gen in (154, 155):
        try:
            references[gen] = CameraReference(gen, SCRATCH / f"equality/reference-{gen}")
        except pytest.skip.Exception as exc:
            skipped.append({"generation": gen, "reason": str(exc)})
    for gen in (154, 155):
        for test in (False, True):
            path = dat_path(gen, test)
            if gen not in references or not path.is_file():
                skipped.append({"generation": gen, "test": test, "reason": "本机缺少 DAT 或相机 C 参考"})
                continue
            raw = path.read_bytes()
            dat = dc.parse(raw)
            assert dc.pack(dat) == raw
            home = SCRATCH / f"equality/home-{gen}-{test}"
            store.import_from_dat(raw, home)
            cam, ref = CameraData(home), references[gen]
            (SCRATCH / f"catalog-{gen}-{int(test)}.json").write_text(json.dumps({"units": cam.listing()}, ensure_ascii=False))
            packages.append({"generation": gen, "test": test, "path": str(path.relative_to(ROOT)), "bytes": len(raw),
                             "sha256": digest(raw), "round_trip": True, "looks": len(dat.looks), "users": len(dat.users),
                             "engine_bytes": len(dat.engine), "effect_bytes": len(dat.effect_area),
                             "row_capacity": list(dat.effect_area[16:20]), "row_used": list(dat.effect_area[20:24])})
            for unit, catalog in enumerate(cam.listing()):
                assert ref.validate(raw, unit)
                for group in ("recipes", "looks", "users"):
                    for index, info in enumerate(catalog[group]):
                        kind = {"recipes": "builtin", "looks": "look", "users": "camera_user"}[group]
                        sel = RecipeSel(UNITS[unit], info["slot"], kind=kind, id=info.get("id"))
                        got = cam.resolve(sel).entry
                        expected = ref.builtin(raw, unit, info["slot"], {}) if kind == "builtin" else (
                            ref.resolve(raw, unit, index, {}) if kind == "look" else ref.user(raw, unit, index))
                        assert len(got) == len(expected) == 552 and got == expected, (gen, test, unit, group, index)
                        rows.append({"generation": gen, "test": test, "unit": UNITS[unit], "kind": kind,
                                     "index": index, "name": info.get("name", info.get("number")), "bytes": 552,
                                     "studio_sha256": digest(got), "camera_sha256": digest(expected), "equal": True})
                        if kind == "camera_user":
                            continue
                        for control in info["controls"]:
                            for level in control["levels"]:
                                levels = {control["name"]: level}
                                selected = replace(sel, levels=tuple(levels.items()))
                                expected = ref.builtin(raw, unit, info["slot"], levels) if kind == "builtin" else ref.resolve(raw, unit, index, levels)
                                assert cam.resolve(selected).entry == expected, (gen, test, unit, group, index, levels)
                                point_comparisons += 1
    result = {"status": "INCOMPLETE" if skipped else "PASS", "skipped": skipped, "packages": packages, "default_comparisons": len(rows),
              "look_comparisons": sum(r["kind"] == "look" for r in rows), "user_comparisons": sum(r["kind"] == "camera_user" for r in rows),
              "builtin_comparisons": sum(r["kind"] == "builtin" for r in rows), "single_control_comparisons": point_comparisons, "rows": rows}
    (HERE / "byte-equality.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "packages")}, ensure_ascii=False))


def old_generations():
    baseline_dc = load_baseline("baseline_datcodec", "src/gxr_studio/camdata/datcodec.py")
    baseline_knobs = load_baseline("gxr_studio.camdata.baseline_knob_table", "src/gxr_studio/camdata/knob_table.py")
    baseline = load_baseline("gxr_studio.render.baseline_recipes", "src/gxr_studio/render/recipes.py")
    baseline.datcodec, baseline.knob_table = baseline_dc, baseline_knobs
    paths = {**FIXTURE_DATS, 137: ROOT / "firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT",
             138: ROOT / "firmware/package_v38_g138/SD_ROOT/GXRCE.DAT"}
    paths.update({g: dat_path(g) for g in (150, 152, 153)})
    packages, skipped, comparisons = [], [], 0
    for gen, path in paths.items():
        if not path.is_file():
            skipped.append({"generation": gen, "path": str(path.relative_to(ROOT)), "reason": "本机缺少 DAT"})
            continue
        raw = path.read_bytes()
        assert asdict(dc.parse(raw)) == asdict(baseline_dc.parse(raw))
        assert dc.pack(dc.parse(raw)) == baseline_dc.pack(baseline_dc.parse(raw)) == raw
        home = SCRATCH / f"legacy/home-{gen}"
        store.import_from_dat(raw, home)
        cam, old = CameraData(home), baseline.CameraData(home)
        assert cam.menu == old.menu and cam.listing() == old.listing()
        count = 0
        for unit, catalog in enumerate(cam.listing()):
            for info in catalog["recipes"]:
                sel = RecipeSel(UNITS[unit], info["slot"])
                assert cam.resolve(sel).entry == old.resolve(sel).entry
                count += 1
                for control in info["controls"]:
                    for level in (control["min"], control["max"]):
                        selected = replace(sel, levels=((control["name"], level),))
                        assert cam.resolve(selected).entry == old.resolve(selected).entry
                        count += 1
        comparisons += count
        packages.append({"generation": gen, "path": str(path.relative_to(ROOT)), "sha256": digest(raw),
                         "round_trip": True, "parsed_fields_equal": True, "menu_equal": True, "comparisons": count})
    result = {"status": "INCOMPLETE" if skipped else "PASS", "skipped": skipped, "packages": packages, "comparisons": comparisons}
    (HERE / "old-generations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"old_generations": [p["generation"] for p in packages], "comparisons": comparisons,
                      "status": result["status"], "skipped": skipped}))


if __name__ == "__main__":
    new_packages()
    old_generations()
