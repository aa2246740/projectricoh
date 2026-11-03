"""Render scene-linear sRGB arrays; a failed gate requires explicit diagnostic use."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help=".npy RGB or .npz with linear_srgb; DNG exposure normalization already applied")
    parser.add_argument("--output", default="diagnostic_scene.npz", help="filename under local/")
    parser.add_argument("--diagnostic", action="store_true", help="acknowledge an unaccepted analytic model")
    args = parser.parse_args()
    gate = rt.read(rt.LOCAL / "gate.json")
    if not gate["accepted"] and not args.diagnostic:
        raise SystemExit("Validation gate failed. Use --diagnostic only for research; no accepted GXR target exists.")
    path = rt.inp(args.input)
    if path.suffix == ".npy":
        scene = np.load(path, allow_pickle=False)
    else:
        with np.load(path, allow_pickle=False) as doc:
            scene = doc["linear_srgb"]
    if scene.ndim < 2 or scene.shape[-1] != 3 or not np.isfinite(scene).all():
        raise ValueError("finite RGB array required")
    output = (rt.LOCAL / args.output).resolve()
    if not rt.within(output, rt.LOCAL) or output.suffix != ".npz":
        raise ValueError("output must be an npz under local/")
    output.parent.mkdir(parents=True, exist_ok=True)
    state = rt.read(rt.LOCAL / "calibration/primary_pre_hard.json")
    modes = {mode: sim.render_scene(scene, mode, state["common"], sim.Options(**state["options"])) for mode in sim.MODES}
    np.savez_compressed(output, **modes)
    rt.dump(str(output.relative_to(rt.LOCAL)) + ".json", dict(input_sha256=rt.sha(path),
        evidence="电脑预测", analytic_model_accepted=gate["accepted"], diagnostic_only=not gate["accepted"],
        modes=list(modes), shape=scene.shape, encoding="sRGB", input_coordinate="scene-linear sRGB/D65"))
    print(output)


if __name__ == "__main__":
    main()
