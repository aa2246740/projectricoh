"""Resample real DNGs and JPEGs without reusing any fitted color/radial targets."""
from pathlib import Path
import io
import sys
import types
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from PIL import Image, ImageCms, ImageOps
from scipy.ndimage import map_coordinates
import imagecodecs
import simulator as sim


def require(test, message):
    if not test:
        raise ValueError(message)


# The existing parser has no I/O at import; supply only its pure assertion dependency.
stub = types.ModuleType("common")
stub.require = require
sys.modules["common"] = stub
tiff = rt.module("analytic_tiff", "research/gr_incamera_dev/tiff_io.py")


def decode(path, expected=None):
    path = rt.inp(path, expected)
    t = tiff.Tiff(path.read_bytes())
    g = t.geometry()
    mosaic = np.zeros((g["height"], g["width"]), np.uint16)
    for seg in t.segments(t.raw):
        block = imagecodecs.ljpeg_decode(t.data[seg["offset"]:seg["offset"] + seg["capacity"]])
        x, y, w, h = seg["box"]
        block = block.reshape(h, w)
        rh, rw = min(h, g["height"] - y), min(w, g["width"] - x)
        mosaic[y:y + rh, x:x + rw] = block[:rh, :rw]
    x, y = g["crop_xy"]
    w, h = g["crop_wh"]
    crop = mosaic[y:y + h, x:x + w]
    values = crop.astype(np.float32)
    black, white = g["black"], g["white"]
    raw = np.stack([(values[::2, ::2] - black[0]) / (white - black[0]),
        .5 * ((values[::2, 1::2] - black[1]) / (white - black[1]) +
              (values[1::2, ::2] - black[2]) / (white - black[2])),
        (values[1::2, 1::2] - black[3]) / (white - black[3])], axis=-1)
    clipped = crop.reshape(h // 2, 2, w // 2, 2).max(axis=(1, 3)) >= white
    return t, g, raw, clipped, rt.sha(path)


def jpeg(path, expected=None):
    with Image.open(rt.inp(path, expected)) as original:
        original.load()
        exif = original.getexif()
        profile = original.info.get("icc_profile")
        image = ImageOps.exif_transpose(original).convert("RGB")
        if profile:
            image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                ImageCms.createProfile("sRGB"), outputMode="RGB")
        else:
            space = exif.get_ifd(34665).get(40961) if 34665 in exif else exif.get(40961)
            require(space in (None, 1), "unknown JPEG color space")
    return np.asarray(image)


def observe(image, patches, homography):
    means, sd, clip = [], [], []
    # Crop per patch rather than allocating a floating-point full-size RGB frame.
    for patch in patches:
        x1, y1, x2, y2 = patch["roi"]
        yy, xx = np.mgrid[y1 + .5:y2:1., x1 + .5:x2:1.]
        q = np.c_[xx.ravel(), yy.ravel(), np.ones(xx.size)] @ np.asarray(homography).T
        xy = q[:, :2] / q[:, 2:3]
        require(xy.min() >= 0 and xy[:, 0].max() < image.shape[1] - 1 and xy[:, 1].max() < image.shape[0] - 1,
                "ROI outside JPEG")
        left, top = np.floor(xy.min(axis=0)).astype(int)
        right, bottom = np.ceil(xy.max(axis=0)).astype(int) + 1
        crop = image[top:bottom, left:right].astype(float) / 255
        values = np.stack([map_coordinates(crop[..., c], [xy[:, 1] - top, xy[:, 0] - left],
                           order=1, prefilter=False) for c in range(3)], axis=-1)
        means.append(values.mean(axis=0))
        sd.append(values.std(axis=0))
        clip.append(np.mean((values <= 1 / 255) | (values >= 254 / 255), axis=0))
    return np.asarray(means), np.asarray(sd), np.asarray(clip)


def dense():
    rows, audit = [], []
    base = "research/gr_dense_reference/local/private/gr4/r3/camera-returns-20261025-nega"
    sources = rt.read("research/gr4_nega_returns_r1/local/target/manifest.json")["inputs_sha256"]
    for band in range(1, 5):
        source = f"{base}/dense-band-{band}-analysis.json"
        d = rt.read(source, sources[source])
        manifest = Path(d["card_manifest"])
        card = rt.read(manifest, sources[str(manifest.relative_to(rt.ROOT))])
        require(set(d["modes"]) == {"standard", "positive", "negative"}, "incomplete mode set")
        t, g, raw, raw_clip, digest = decode(card["dng_path"], card["dng_sha256"])
        require(digest == d["dng_sha256"], "readback and card DNG hashes differ")
        patches = card["patches"]
        values = {}
        maximum_saved_difference = 0.
        for mode, saved in d["modes"].items():
            rgb = jpeg(saved["path"], saved["sha256"])
            mean, sd, clip = observe(rgb, patches, saved["alignment"]["homography"])
            previous = np.asarray([q["rgb_observed"] for q in saved["patches"]])
            maximum_saved_difference = max(maximum_saved_difference, float(abs(mean - previous).max()))
            require(abs(mean - previous).max() < 2e-6, "JPEG resampling disagrees with previous raw observations")
            values[mode] = mean, sd, clip
            control = saved["metadata"]["control"]
            aliases = (("high_low_key", "key"), ("contrast", "contrast"),
                       ("contrast_highlight", "highlight"), ("contrast_shadow", "shadow"))
            expected = {field: sim.parameters()["sliders"][mode][key] for field, key in aliases}
            expected.update(saturation=0, hue=0, sharpness=0, shading=0, clarity=0)
            require(all(control.get(k) == v for k, v in expected.items()), "nondefault sliders")
        for i, patch in enumerate(patches):
            if patch["role"] not in ("colour", "tone", "reference", "natural", "radial", "validation"):
                continue
            x1, y1, x2, y2 = np.asarray(patch["roi"]) // 2
            block = raw[y1:y2, x1:x2]
            mean = block.mean(axis=(0, 1))
            goodraw = not raw_clip[y1:y2, x1:x2].any() and mean.min() > 0
            row = dict(band=band, id=patch["id"], role=patch["role"], radius=patch["radius"],
                raw_wb=mean / np.asarray(g["neutral"]), raw_valid=goodraw)
            for mode, (mean_jpg, sd, clip) in values.items():
                row[mode] = mean_jpg[i]
                row[mode + "_valid"] = bool(clip[i].max() == 0 and sd[i].max() < .025 and goodraw)
            rows.append(row)
        matrix = np.linalg.inv(rt.cm.SRGB_XYZ) @ rt.cm.cat(rt.cm.D50, rt.cm.D65) @ np.asarray(card["colour_matrix"]) @ np.diag(g["neutral"]) * 2 ** g["baseline_exposure"]
        audit.append(dict(band=band, card_manifest=str(manifest.relative_to(rt.ROOT)), dng_sha256=digest,
            geometry=g, raw_wb_to_scene=matrix, patches=len(patches),
            maximum_saved_observation_difference=maximum_saved_difference,
            mode_paths={k: v["path"] for k, v in d["modes"].items()},
            metadata={k: v["metadata"] for k, v in d["modes"].items()},
            color_radial_corrections_from_previous_runs_used=False))
        print("resampled real GR IV dense page", band, len(patches), flush=True)
    arrays = {k: np.asarray([r[k] for r in rows]) for k in rows[0]}
    np.savez_compressed(rt.LOCAL / "dense.npz", **arrays)
    rt.dump("dense_audit.json", audit)


def orient(value, code):
    if code == 1: return value
    if code == 2: return value[:, ::-1]
    if code == 3: return value[::-1, ::-1]
    if code == 4: return value[::-1]
    if code == 5: return value.swapaxes(0, 1)
    if code == 6: return np.rot90(value, 3)
    if code == 7: return value.swapaxes(0, 1)[::-1, ::-1]
    if code == 8: return np.rot90(value)
    raise ValueError("unsupported EXIF orientation")


def natural():
    root = rt.ROOT / "captures/contrib/2026-10-25-gr4-wechat/extracted/GR4/Other"
    all_rows, audit = [], []
    for path in sorted(root.glob("*.DNG")):
        old = rt.read("research/gr4_dense_returns_r1/local/natural/" + path.stem + ".json")
        rt.inp(path, old["input_dng_sha256"])
        rt.inp(path.with_suffix(".JPG"), old["input_jpeg_sha256"])
        t, g, raw, raw_clip, digest = decode(path)
        raw, raw_clip = orient(raw, g["orientation"]), orient(raw_clip, g["orientation"])
        img = jpeg(path.with_suffix(".JPG"))
        h, w = img.shape[:2]
        require(raw.shape[:2] == (h // 2, w // 2), "RAW and JPEG crop/orientation mismatch")
        matrix, info = rt.cm.dng_camera_to_xyz(t.tags())
        matrix = np.linalg.inv(rt.cm.SRGB_XYZ) @ rt.cm.cat(rt.cm.D50, rt.cm.D65) @ matrix @ np.diag(g["neutral"])
        count = 0
        for y in np.linspace(40, h - 40, 28).astype(int):
            for x in np.linspace(40, w - 40, 40).astype(int):
                x, y = x // 2 * 2, y // 2 * 2
                jj = img[y - 16:y + 16, x - 16:x + 16].astype(float)
                rr = raw[y // 2 - 8:y // 2 + 8, x // 2 - 8:x // 2 + 8]
                if raw_clip[y // 2 - 8:y // 2 + 8, x // 2 - 8:x // 2 + 8].any(): continue
                if jj.min() <= 2 or jj.max() >= 253 or jj.std(axis=(0, 1)).max() >= 3: continue
                mean = rr.mean(axis=(0, 1))
                if mean.min() <= .001 or (rr.std(axis=(0, 1)) / np.maximum(mean, 1e-8)).max() >= .06: continue
                wb = mean / np.array(g["neutral"])
                all_rows.append(dict(frame=path.stem, x=x, y=y, raw_wb=wb, baseline_exposure=g["baseline_exposure"],
                    scene=wb @ matrix.T * 2 ** g["baseline_exposure"], standard=jj.mean(axis=(0, 1)) / 255,
                    radius=np.hypot(x - w / 2, y - h / 2) / np.hypot(w / 2, h / 2)))
                count += 1
        audit.append(dict(frame=path.stem, geometry=g, samples=count, metadata=old["metadata"],
            raw_wb_to_scene=matrix, whole_frame_holdout=True, source_dng_sha256=digest))
        print("resampled real GR IV natural Standard", path.stem, count, flush=True)
    np.savez_compressed(rt.LOCAL / "natural.npz", **{k: np.asarray([r[k] for r in all_rows]) for k in all_rows[0]})
    rt.dump("natural_audit.json", audit)


def natural_modes():
    """Additional untouched donor scenes; no shared colors or tone are fitted here."""
    tm = rt.module("analytic_makernote", "research/contrib_gr_analysis/tiff_makernote.py")
    root = rt.ROOT / "captures/contrib/2026-10-19"
    files = [("donor_A_positive", "positive", root / "gr4-modes/positive.DNG"),
             ("donor_A_negative", "negative", root / "gr4-modes/negative.DNG"),
             ("donor_B_standard", "standard", root / "gr4hdf-set/R0003009_standard.DNG"),
             ("donor_B_positive", "positive", root / "gr4hdf-set/R0003004_positive.DNG"),
             ("donor_B_negative", "negative", root / "gr4hdf-set/R0003006_negative.DNG")]
    all_rows, audit = [], []
    for name, mode, path in files:
        path_jpg = path.with_suffix(".JPG")
        tmeta, _ = tm.jpeg_exif_tiff(rt.inp(path_jpg).read_bytes())
        _, at, note, root_meta, _ = tm.maker_note_bytes(tmeta)
        require(at is not None and note.startswith(b"RICOH\0"), "missing Ricoh metadata")
        entries, decoded = tm.decode_gr3_family(tmeta, at)
        require(decoded["image_tone"]["value"] == {"standard": 256, "positive": 262, "negative": 267}[mode], "wrong ImageTone")
        aliases = (("high_low_key", "key"), ("contrast", "contrast"),
                   ("contrast_highlight", "highlight"), ("contrast_shadow", "shadow"))
        expected = {field: sim.parameters()["sliders"][mode][key] for field, key in aliases}
        expected.update(saturation=0, hue=0, sharpness=0, shading=0, clarity=0)
        default = all(decoded["image_control_0x0247"].get(k) == v for k, v in expected.items())
        t, g, raw, raw_clip, digest = decode(path)
        raw, raw_clip = orient(raw, g["orientation"]), orient(raw_clip, g["orientation"])
        img = jpeg(path_jpg)
        h, w = img.shape[:2]
        require(raw.shape[:2] == (h // 2, w // 2), "natural mode orientation mismatch")
        matrix, _ = rt.cm.dng_camera_to_xyz(t.tags())
        matrix = np.linalg.inv(rt.cm.SRGB_XYZ) @ rt.cm.cat(rt.cm.D50, rt.cm.D65) @ matrix @ np.diag(g["neutral"])
        count = 0
        for y in np.linspace(40, h - 40, 28).astype(int):
            for x in np.linspace(40, w - 40, 40).astype(int):
                x, y = x // 2 * 2, y // 2 * 2
                jj = img[y - 16:y + 16, x - 16:x + 16].astype(float)
                rr = raw[y // 2 - 8:y // 2 + 8, x // 2 - 8:x // 2 + 8]
                if raw_clip[y // 2 - 8:y // 2 + 8, x // 2 - 8:x // 2 + 8].any(): continue
                if jj.min() <= 2 or jj.max() >= 253 or jj.std(axis=(0, 1)).max() >= 3: continue
                mean = rr.mean(axis=(0, 1))
                if mean.min() <= .001 or (rr.std(axis=(0, 1)) / np.maximum(mean, 1e-8)).max() >= .06: continue
                wb = mean / np.array(g["neutral"])
                all_rows.append(dict(frame=name, mode=mode, x=x, y=y, raw_wb=wb, baseline_exposure=g["baseline_exposure"],
                    scene=wb @ matrix.T * 2 ** g["baseline_exposure"],
                    observed=jj.mean(axis=(0, 1)) / 255, defaults_verified=default,
                    radius=np.hypot(x - w / 2, y - h / 2) / np.hypot(w / 2, h / 2)))
                count += 1
        audit.append(dict(frame=name, mode=mode, path=str(path.relative_to(rt.ROOT)), geometry=g,
            samples=count, defaults_verified=default, metadata=decoded, raw_wb_to_scene=matrix,
            source_dng_sha256=digest, whole_frame_holdout=True))
        print("resampled untouched natural", name, count, "defaults", default, flush=True)
    np.savez_compressed(rt.LOCAL / "natural_modes.npz", **{k: np.asarray([r[k] for r in all_rows]) for k in all_rows[0]})
    rt.dump("natural_modes_audit.json", audit)


if __name__ == "__main__":
    if "--modes" in sys.argv:
        natural_modes()
    else:
        dense()
        natural()
