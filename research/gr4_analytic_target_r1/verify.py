"""Verify real artifacts, input immutability, holdout separation and output hashes."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
from validate import fit, load_arrays, predict


def public_files():
    return sorted(p for p in rt.HERE.rglob("*") if p.is_file() and
                  not rt.within(p, rt.LOCAL) and "__pycache__" not in p.parts and p.name != "SHA256SUMS")


def checksums(seal=False):
    path = rt.HERE / "SHA256SUMS"
    if seal:
        path.write_text("".join(f"{rt.sha(p)}  {p.relative_to(rt.HERE)}\n" for p in public_files()))
    names, checked = [], []
    for line in path.read_text().splitlines():
        digest, name = line.split("  ", 1)
        p = (rt.HERE / name).resolve()
        assert rt.within(p, rt.HERE) and not rt.within(p, rt.LOCAL)
        assert rt.sha(p) == digest, "checksum mismatch: " + name
        names.append(name)
        checked.append(name + ": OK")
    assert names == [str(p.relative_to(rt.HERE)) for p in public_files()], "checksum coverage mismatch"
    rt.dump("checksum_verification.json", dict(files=len(names), all_OK=True, covered=names))
    print("\n".join(checked))
    print(f"SHA256SUMS: {len(names)} files, all OK")


def verify(leakage_probe=False):
    changed = [name for name, digest in rt.INPUTS.items() if rt.sha(rt.ROOT / name) != digest]
    assert not changed, "frozen inputs changed: " + str(changed)
    a = load_arrays("dense.npz")
    state = rt.read(rt.LOCAL / "calibration/primary_pre_hard.json")
    common, options = state["common"], sim.Options(**state["options"])
    with np.load(rt.LOCAL / "predictions_primary_pre_hard.npz", allow_pickle=False) as saved:
        replay_error = max(float(np.max(np.abs(predict(a, mode, common, options) - saved[mode]))) for mode in sim.MODES)
    assert replay_error == 0, "saved predictions do not match current source"
    curve_doc = rt.read("research/gr_complete_pipeline/gr3_gr4_effective_curves.json")
    checked = 0
    for prior in curve_doc["effective_curves"]:
        if prior["model"] != "gr4" or prior["mode"] == "HighContrastBW": continue
        mode = {"Standard": "standard", "PositiveFilm": "positive", "NegativeFilm": "negative"}[prior["mode"]]
        assert np.array_equal(sim.curve(mode, prior["gain"]) * 16384, prior["curve_u16_256"])
        checked += 1
    # Published CIEDE2000 example pairs, independent of camera-fit outputs.
    de_test = rt.cm.delta_e00(np.array([[50., 2.6772, -79.7751], [50., 3.1571, -77.2803]]),
                            np.array([[50., 0., -82.7485], [50., 0., -82.7485]]))
    assert np.allclose(de_test, [2.0425, 2.8615], atol=5e-5, rtol=0)
    guards = {}
    outside = rt.ROOT / ".gr4-analytic-boundary-probe"
    assert not outside.exists()
    try:
        outside.write_text("must not be written")
    except PermissionError:
        guards["outside_write_denied"] = True
    assert guards.get("outside_write_denied") and not outside.exists()
    try:
        sys.audit("socket.connect", None, ("example.invalid", 443))
    except PermissionError:
        guards["network_audit_denied"] = True
    try:
        code = compile("pass", str(rt.ROOT / "artifacts/downloads/synthetic-boundary-probe.py"), "exec")
        sys.audit("exec", code)
    except PermissionError:
        guards["downloaded_code_execution_denied"] = True
    assert len(guards) == 3
    scene = a["raw_wb"][:18] @ np.asarray(common["raw_wb_to_scene"]).T
    rt.LOCAL.joinpath("verification").mkdir(exist_ok=True)
    source = rt.LOCAL / "verification/render_input.npy"
    np.save(source, scene)
    command = [sys.executable, "-I", "-B", str(rt.HERE / "render.py"), str(source),
               "--output", "verification/render_output.npz"]
    blocked = subprocess.run(command, capture_output=True, text=True)
    assert blocked.returncode != 0 and "Validation gate failed" in blocked.stderr
    run = subprocess.run(command + ["--diagnostic"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    with np.load(rt.LOCAL / "verification/render_output.npz", allow_pickle=False) as out:
        assert set(out.files) == set(sim.MODES)
        for mode in sim.MODES:
            direct = sim.render(a["raw_wb"][:18], mode, common, options)
            assert np.allclose(out[mode], direct, atol=2e-13, rtol=0), "scene/camera coordinate mismatch"
    rt.dump("verification/render_cli.json", dict(failed_gate_blocked_without_diagnostic=True,
        diagnostic_subprocess_returncode=run.returncode, exact_saved_arrays_replayed=True))
    leakage = None
    if leakage_probe:
        counterfactual = {k: v.copy() for k, v in a.items()}
        held = a["band"] == 4
        for name in ("raw_wb", "standard", "radius"):
            counterfactual[name][held] = .234
        counterfactual["standard_valid"][held] = False
        for mode in ("positive", "negative"):
            counterfactual[mode][:] = .876
            counterfactual[mode + "_valid"][:] = False
        probe = fit(counterfactual, options, "leakage_probe")
        assert rt.plain(probe) == rt.plain(common), "heldout/style pixels changed Standard-only calibration"
        leakage = dict(all_style_pixels_and_heldpage_raw_and_JPEG_replaced=True,
            resulting_calibration_bit_identical=True)
        rt.dump("verification/leakage.json", leakage)
    elif (rt.LOCAL / "verification/leakage.json").exists():
        leakage = rt.read(rt.LOCAL / "verification/leakage.json")
    ignored = subprocess.run(["git", "-C", str(rt.ROOT), "check-ignore", str(rt.LOCAL / "privacy-probe")], capture_output=True, text=True)
    assert ignored.returncode == 0
    import scipy, PIL, imagecodecs
    doc = dict(status="PASS_RESEARCH_INTEGRITY_ONLY", analytic_model_accepted=False,
        firmware_built=False, camera_or_card_access=False, network_used=False,
        protected_inputs=len(rt.INPUTS), changed_inputs=changed, saved_prediction_replay_max_error=replay_error,
        integer_gamma_states_checked=checked, CIEDE2000_reference_pairs_checked=2,
        guards=guards, local_ignored=True, leakage_probe=leakage,
        environment=dict(python=sys.version.split()[0], executable=sys.executable,
            numpy=np.__version__, scipy=scipy.__version__, pillow=PIL.__version__, imagecodecs=imagecodecs.__version__))
    rt.dump("verification/integrity.json", doc)
    (rt.HERE / "verification.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print("frozen inputs unchanged:", len(rt.INPUTS))
    print("research integrity checks passed; analytic accuracy gate remains failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leakage-probe", action="store_true")
    parser.add_argument("--checksums", action="store_true")
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    if args.checksums or args.seal:
        checksums(args.seal)
    else:
        verify(args.leakage_probe)
