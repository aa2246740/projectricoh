"""Render a scene-linear sRGB/D65 array using the frozen research model."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='.npy RGB or .npz with linear_srgb; DNG exposure already applied once')
    parser.add_argument('--output', default='render.npz', help='filename under local/')
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    gate = rt.read(rt.LOCAL / 'gate.json')
    if not gate['accepted'] and not args.diagnostic:
        raise SystemExit('Accuracy gate did not pass; --diagnostic is required for research rendering.')
    source = rt.inp(args.input)
    if source.suffix == '.npy': scene = np.load(source, allow_pickle=False)
    else:
        with np.load(source, allow_pickle=False) as data: scene = data['linear_srgb']
    if scene.ndim < 2 or scene.shape[-1] != 3 or not np.isfinite(scene).all():
        raise ValueError('finite scene RGB required')
    output = (rt.LOCAL / args.output).resolve()
    if not output.is_relative_to(rt.LOCAL) or output.suffix != '.npz':
        raise ValueError('output must be an npz under local/')
    state = rt.read(rt.LOCAL / 'calibration/P2.json')
    common, options = state['common'], sim.Options(**state['options'])
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **{m: sim.render_scene(scene, m, common, options) for m in sim.MODES})
    rt.dump(str(output.relative_to(rt.LOCAL)) + '.json', dict(evidence='电脑预测',
        source_sha256=rt.sha(source), model_accepted=gate['accepted'],
        diagnostic_only=not gate['accepted'], shape=scene.shape,
        coordinate='scene-linear sRGB/D65 with source BaselineExposure already applied once', encoding='sRGB'))
    print(output)


if __name__ == '__main__': main()
