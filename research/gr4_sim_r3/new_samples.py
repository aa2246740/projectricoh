"""Three new DNGs remain complete-frame holdouts, including source recipe."""
from pathlib import Path
import io
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import simulator as sim
from PIL import Image, ImageCms


def main():
    sys.modules['simulator'] = sim
    data = rt.module('r3_existing_sampler', 'research/gr4_analytic_target_r1/data.py')
    base = 'artifacts/downloads/gr4-repos/DoYitNow_gr-custom-tool/gr4_editor/assets/calibration/'
    manifest = rt.read(base + 'samples.json')
    metadata = rt.read('research/gr4_repos_review_r1/local/photo_metadata.json')
    references = {r['path']: r for r in metadata if 'metadata' in r}
    rows, audits = [], []
    for sample in manifest['samples']:
        name = base + sample['path']
        path = rt.inp(name, sample['sha256'])
        t, geometry, raw, clipped, digest = data.decode(path, sample['sha256'])
        reference = references[name]['metadata']
        previews = reference['embedded_previews']
        assert len(previews) == 1
        preview = previews[0]
        content = b''.join(t.data[at:at + count] for at, count in preview['strip_ranges'])
        import hashlib
        assert hashlib.sha256(content).hexdigest() == preview['sha256']
        with Image.open(io.BytesIO(content)) as image:
            assert image.format == 'JPEG' and image.size == tuple(geometry['crop_wh'])
            profile = image.info.get('icc_profile')
            icc_space = None
            if profile:
                src = ImageCms.ImageCmsProfile(io.BytesIO(profile))
                icc_space = ImageCms.getProfileName(src).strip()
                image = ImageCms.profileToProfile(image, src, ImageCms.createProfile('sRGB'), outputMode='RGB')
            img = np.asarray(image.convert('RGB'))
        maker = t.maker()
        control = maker.entries[0x0247]
        values = t.unpack('h' * (control.size // 2), control.offset, control.endian)
        keys = ('saturation', 'hue', 'key', 'contrast', 'highlight', 'shadow', 'sharpness')
        sliders = dict(zip(keys, values[:7]))
        sliders.update(shading=values[9], clarity=values[10])
        assert all(sliders[k] == 0 for k in ('hue', 'sharpness', 'shading', 'clarity'))
        tone = maker.entries[0x004f].value
        assert tone[0] == 256
        assert reference['software'] == 'RICOH GR IV Ver. 1.11'
        raw = data.orient(raw, geometry['orientation'])
        clipped = data.orient(clipped, geometry['orientation'])
        img = data.orient(img, geometry['orientation'])
        h, w = img.shape[:2]
        assert raw.shape[:2] == (h // 2, w // 2)
        matrix, colour_audit = rt.cm.dng_camera_to_xyz(t.tags())
        matrix = np.linalg.inv(rt.cm.SRGB_XYZ) @ rt.cm.cat(rt.cm.D50, rt.cm.D65) @ matrix @ np.diag(geometry['neutral'])
        count = 0
        for y in np.linspace(40, h - 40, 28).astype(int):
            for x in np.linspace(40, w - 40, 40).astype(int):
                x, y = x // 2 * 2, y // 2 * 2
                jj = img[y - 16:y + 16, x - 16:x + 16].astype(float)
                rr = raw[y // 2 - 8:y // 2 + 8, x // 2 - 8:x // 2 + 8]
                if clipped[y // 2 - 8:y // 2 + 8, x // 2 - 8:x // 2 + 8].any(): continue
                if jj.min() <= 2 or jj.max() >= 253 or jj.std(axis=(0, 1)).max() >= 3: continue
                mean = rr.mean(axis=(0, 1))
                if mean.min() <= .001 or (rr.std(axis=(0, 1)) / np.maximum(mean, 1e-8)).max() >= .06: continue
                wb = mean / np.asarray(geometry['neutral'])
                rows.append(dict(frame=path.stem, mode='standard', raw_wb=wb,
                    scene=wb @ matrix.T * 2 ** geometry['baseline_exposure'],
                    radius=np.hypot(x - w / 2, y - h / 2) / np.hypot(w / 2, h / 2),
                    observed=jj.mean(axis=(0, 1)) / 255, x=x, y=y,
                    baseline_exposure=geometry['baseline_exposure'], source_sha256=digest))
                count += 1
        assert count > 0
        audits.append(dict(frame=path.stem, source=name, source_sha256=digest, geometry=geometry,
            sliders=sliders, image_tone=int(tone[0]), samples=count, preview_sha256=preview['sha256'],
            preview_size=[w, h], preview_source='embedded full-size JPEG', icc_profile=icc_space,
            preview_srgb_assumed=profile is None, raw_wb_to_scene_without_be=matrix,
            dng_colorimetry=colour_audit, baseline_exposure_applications=1,
            camera_jpeg_equivalence_verified=False, used_for_fit_or_selection=False,
            upstream_role=sample['role'], current_role='whole-photo holdout'))
        print(path.stem, 'whole-photo holdout', count, 'ROIs', sliders, flush=True)
    np.savez_compressed(rt.LOCAL / 'new_samples.npz', **{k: np.asarray([r[k] for r in rows]) for k in rows[0]})
    rt.dump('new_samples_audit.json', audits)


if __name__ == '__main__': main()
