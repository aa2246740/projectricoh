"""Freeze r1 and construct explicitly unvalidated diagnostic targets from GXR RAW."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np

PREFIX = {'01': 'research/gr4_dense_returns_r1', '02': 'research/gr4_nega_returns_r1'}
MODES = {'01': 'positive', '02': 'negative'}


def main():
    parent = rt.ROOT / 'research/gr4_analytic_target_r1'
    checked = []
    for line in rt.inp(parent / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        rt.inp(parent / name.lstrip('*'), digest)
        checked.append(name)
    assert len(checked) == 19
    tiff = rt.module('diagnostic_tiff', 'research/gr_incamera_dev/tiff_io.py')
    frames = rt.read(rt.DATA / 'frames.json')['frames']
    state = rt.read(parent / 'local/calibration/primary_pre_hard.json')
    common = state['common']
    options = rt.sim.Options(**state['options'])
    metadata = {}
    rows = []
    for slot, prefix in PREFIX.items():
        a = rt.arrays(prefix + '/local/fit/data.npz')
        records = rt.read(prefix + '/local/fit/records.json')
        scene = np.zeros_like(a['raw'])
        for frame in sorted({r['frame'] for r in records}):
            name = 'captures/a12-50/2026-10-24/chart-v2-R8051229-1311/' + frame + '.DNG'
            path = rt.inp(name, frames[frame]['hashes']['DNG'])
            tags = tiff.Tiff(path.read_bytes()).tags()
            camera_to_xyz, audit = rt.cm.dng_camera_to_xyz(tags)
            neutral = np.asarray(tags[50728])
            assert np.max(abs(neutral * frames[frame]['white_balance']['gains'] - 1)) < 1e-12
            matrix = np.linalg.inv(rt.cm.SRGB_XYZ) @ rt.cm.cat(rt.cm.D50, rt.cm.D65) @ camera_to_xyz @ np.diag(neutral)
            be = float(tags.get(50730, [0])[0])
            use = np.array([r['frame'] == frame for r in records])
            scene[use] = a['raw'][use] @ matrix.T * 2 ** be
            metadata[frame] = dict(path=name, sha256=rt.sha(path), baseline_exposure=be,
                raw_wb_to_scene_without_BE=matrix, dng_colorimetry=audit,
                baseline_exposure_applications=1, no_camera_bridge=True)
        assert np.isfinite(scene).all()
        target_rgb = rt.sim.render_scene(scene, MODES[slot], common, options)
        standard = rt.sim.render_scene(scene, 'standard', common, options)
        target = rt.lab(target_rgb)
        folder = rt.LOCAL / 'data'
        folder.mkdir(exist_ok=True)
        np.savez_compressed(folder / (slot + '.npz'), scene=scene, target_rgb=target_rgb, target=target,
            standard_rgb=standard, raw=a['raw'], old_target=np.nan_to_num(a['new_target']),
            base_rgb=a['base_rgb'], observed_rgb=a['observed_rgb'], supported=a['supported'],
            fit_usable=a['fit_usable'], pages=a['pages'], hue_group=a['hue_group'])
        valid = a['supported']
        rows.append(dict(slot=slot, evidence='电脑预测', label='未验证的模拟目标，仅作诊断',
            n=int(valid.sum()), n_original=len(scene), n_train_eligible=int((valid & a['fit_usable']).sum()),
            new_to_old=rt.stats(rt.cm.delta_e00(target[valid], a['new_target'][valid])),
            measured04_to_new=rt.stats(rt.cm.delta_e00(rt.lab(a['base_rgb'][valid] / 255), target[valid])),
            measured04_to_old=rt.stats(rt.cm.delta_e00(rt.lab(a['base_rgb'][valid] / 255), a['new_target'][valid])),
            simulated_standard_to_measured04=rt.stats(rt.de(standard[valid], a['base_rgb'][valid] / 255)),
            clipped_target_fraction=float(np.mean(((target_rgb <= 0) | (target_rgb >= 1))[valid].any(axis=1))),
            sensor_spectral_difference_modelled=False, analytic_model_accepted=False))
        rt.dump('data/' + slot + '_records.json', records)
        print(rt.plain(rows[-1]), flush=True)
    rt.dump('gxrdng_metadata.json', metadata)
    rt.dump('target_summary.json', rows)
    rt.dump('parent_verification.json', dict(count=len(checked), all_ok=True, files=checked))
    rt.finish('prepare')


if __name__ == '__main__':
    main()
