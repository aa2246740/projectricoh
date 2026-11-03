"""Local-only acceptance. Reads third-party files; never copies LUT data into this report.

Run with studio/.venv/bin/python3 -I -B, first --phase before, then --phase after.
Temporary library and arrays live only in the task's Scratch directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/studio-lut-ident-r1')
os.environ['TMPDIR'] = str(SCRATCH)
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'studio/src'))

import numpy as np

from gxr_studio import audit
from gxr_studio.engine.colour import delta_e00, lab_from_codes
from gxr_studio.lut.library import LutLibrary
from gxr_studio.lut.photo import color_image
from gxr_studio.lut.scene import ANCHOR, scene_colour
from gxr_studio.lut.spaces import xyz_to_encoded
from gxr_studio.raw import open_dng, orient_array
from gxr_studio.render.params import EditState
from gxr_studio.render.service import RenderService


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def metric(values):
    values = np.asarray(values, float)
    assert np.isfinite(values).all()
    return {'n': values.size, 'median': float(np.median(values)),
            'p95': float(np.percentile(values, 95)), 'max': float(values.max())}


def colour_error(a, b):
    return metric(delta_e00(lab_from_codes(a), lab_from_codes(b)))


class ReadLibrary:
    root = ROOT / 'captures'

    def abspath(self, relative):
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT / 'captures'):
            raise ValueError('Only repository captures are allowed')
        return path


def sparse_reference(meta, dng):
    """The frozen research/data.py 2x2 sampling, with its recorded DNG matrix.

    The reference XYZ formula is independent of scene_colour().xyz(). The anchor
    and per-DNG matrices come from the completed evaluation, never a new fit.
    """
    y0, x0, height, width = dng.crop_window()
    sample_width = 96
    sample_height = max(2, round(height * sample_width / width))
    ys = y0 + 2 * np.linspace(0, (height - 2) // 2, sample_height).astype(int)
    xs = x0 + 2 * np.linspace(0, (width - 2) // 2, sample_width).astype(int)
    yy, xx = np.meshgrid(ys, xs, indexing='ij')
    raw = np.zeros((sample_height, sample_width, 3))
    counts = np.zeros_like(raw)
    clipped = np.zeros(raw.shape[:2], bool)
    for dy in (0, 1):
        for dx in (0, 1):
            colour = dng.cfa_at(yy + dy, xx + dx)
            value = dng.normalised_at(yy + dy, xx + dx)
            clipped |= value >= .98
            for channel in range(3):
                mask = colour == channel
                raw[..., channel] += value * mask
                counts[..., channel] += mask
    neutral = np.asarray(meta['neutral'])
    matrix = np.asarray(meta['matrix'])
    codes = raw / counts / neutral * 4095
    anchor = json.loads((ROOT / 'research/color_fit_v2/05_classic_chrome/round4/local/fit_v4_noT1.json').read_text())['anchor']
    u, f = anchor['u_m'], anchor['f']
    assert u == ANCHOR['u_m'] and f == ANCHOR['f']
    white_y = (neutral @ matrix.T)[1]
    xyz = ((codes / 4095 - f) * neutral) @ matrix.T * (.18 / ((u - f) * white_y))
    return codes, xyz, ~clipped, ((yy - y0) // 2, (xx - x0) // 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['before', 'after'], required=True)
    phase = parser.parse_args().phase
    SCRATCH.mkdir(parents=True, exist_ok=True)
    audit.forbid_network(True)
    audit.forbid_volumes()
    for path in (Path('/Users/wu/Pictures/GXR Studio'), Path('/Users/wu/Pictures/GXR 导出'),
                 Path('/Users/wu/Library/Application Support/GXR Studio')):
        audit.forbid_reads(path)
        audit.protect(path)
    audit.protect(ROOT / 'captures')
    audit.protect(ROOT / 'artifacts/downloads')
    run = Path(tempfile.mkdtemp(prefix=f'{phase}-validation-', dir=SCRATCH))
    imports = json.loads((ROOT / 'research/vlog_alchemy_eval/studio_imports.json').read_text())
    library = LutLibrary(run / 'library')
    rows = []
    for original in imports:
        path = ROOT / original['path']
        raw = path.read_bytes()
        item = library.add(raw, path.name)
        assert item['cube_id'] == original['sha256'] == digest(path)
        assert (library.home / 'luts' / item['file']).read_bytes() == raw
        rows.append({'path': original['path'], 'sha256': item['cube_id'],
                     **{key: item.get(key) for key in ('input_space', 'input_space_state', 'input_space_guess',
                                                       'output_space', 'output_space_state', 'space_evidence')},
                     'raw_bytes_preserved': True})
    dump(f'{phase}-imports.json', rows)
    print(f'{phase}: {len(rows)} LUT imports', flush=True)
    photos = json.loads((ROOT / 'research/vlog_alchemy_eval/selected_dngs.json').read_text())
    photos = [photos[0], photos[1], photos[10], photos[11], photos[13], photos[15], photos[18]]
    photo_library = ReadLibrary()
    render = RenderService(run / 'photos', photo_library, proxy_bytes=8 << 20,
                           result_bytes=8 << 20, max_concurrent=1)
    cube_path = ROOT / 'artifacts/downloads/v-log-alchemy-e51ba9a2/Luts/Hasselblad/Hasselblad_Standard_Phocus_X2D_VLog_sRGB_65.cube'
    item = render.luts.add(cube_path.read_bytes(), cube_path.name)
    render.luts.patch(item['cube_id'], {'input_space': 'vlog', 'output_space': 'srgb'})
    target, _ = render.luts.target(item['cube_id'])
    results = []
    for index, meta in enumerate(photos):
        path = ROOT / meta['path']
        assert digest(path) == meta['sha256']
        shot = {'id': f'local-{index}', 'lens': meta['unique_model'], 'iso': meta['iso'],
                'files': {'dng': {'relpath': meta['path']}}}
        row = {'path': meta['path'], 'sha256': meta['sha256'], 'unit': meta['unit'], 'iso': meta['iso']}
        if phase == 'before' and meta['unit'] == 'mount-a12':
            continue
        image, _, labels = color_image(render, photo_library, shot, EditState(lut=item['cube_id']),
                                       max_edge=None, quality=100, base='auto', full=False)
        row['half_sha256'] = hashlib.sha256(image.tobytes()).hexdigest()
        row['half_shape'] = list(image.shape)
        row['label'] = labels['text']
        if index == 0 or (phase == 'after' and index == 5):
            full, _, _ = color_image(render, photo_library, shot, EditState(lut=item['cube_id']),
                                     max_edge=None, quality=100, base='auto', full=True)
            row['full_sha256'] = hashlib.sha256(full.tobytes()).hexdigest()
            row['full_shape'] = list(full.shape)
            del full
        dng = open_dng(path)
        try:
            codes, xyz, valid, indices = sparse_reference(meta, dng)
            actual_xyz = scene_colour(dng).xyz(codes)
            row['xyz_max_abs_error'] = float(np.max(np.abs(actual_xyz - xyz)))
            ideal = target.render(np.zeros_like(codes), xyz)
            rounded = np.floor(np.clip(ideal, 0, 255) + .5).astype(np.uint8)
            inverse = {6: 8, 8: 6}.get(dng.orientation, dng.orientation)
            samples = orient_array(image, inverse)[indices]
            row['research_half_de00'] = colour_error(samples[valid], rounded[valid])
            row['research_float_quantisation_de00'] = colour_error(samples[valid], ideal[valid])
            neutral_codes = np.full((1, 3), ANCHOR['u_m'] * 4095)
            gray_xyz = scene_colour(dng).xyz(neutral_codes)
            row['gray_xyz'] = gray_xyz.tolist()[0]
            row['gray_vlog'] = xyz_to_encoded(gray_xyz, 'vlog').tolist()[0]
            row['gray_y_error'] = abs(float(gray_xyz[0, 1]) - .18)
            assert row['xyz_max_abs_error'] < 1e-12 and row['gray_y_error'] < 1e-12
        finally:
            dng.release()
        results.append(row)
        print(f"{phase}: {meta['unit']} {path.name} {row['research_half_de00']}", flush=True)
        del image
    dump(f'{phase}-photos.json', results)
    if phase == 'after':
        # Re-run all successful 50mm cases from the supplied evaluation receipt,
        # in addition to the newly frozen half/full-resolution before hashes.
        previous = json.loads((ROOT / 'research/vlog_alchemy_eval/studio_photo_checks.json').read_text())
        import_paths = {row['sha256']: ROOT / row['path'] for row in imports}
        receipt_checks = []
        for prior in previous:
            if prior['unit'] != 'a12-50':
                continue
            is_display = 'render_sha256' in prior
            cid = prior['labels']['description'].split('LUT ', 1)[1].split(',', 1)[0]
            source = import_paths[cid]
            entry = render.luts.add(source.read_bytes(), source.name)
            space = 'srgb' if is_display else 'vlog'
            render.luts.patch(entry['cube_id'], {'input_space': space, 'output_space': 'srgb'})
            meta = next(row for row in photos if row['path'] == prior['photo'])
            files = {'dng': {'relpath': prior['photo']}}
            if is_display:
                files['jpg'] = {'relpath': prior['jpeg']}
            shot = {'id': 'receipt-' + cid[:12], 'lens': meta['unique_model'], 'iso': meta['iso'], 'files': files}
            image, _, _ = color_image(render, photo_library, shot, EditState(lut=cid),
                                      max_edge=320, quality=90, base='auto', full=False)
            actual = hashlib.sha256(image.tobytes()).hexdigest()
            expected = prior['render_sha256'] if is_display else prior['sha256']
            assert actual == expected, (prior.get('name', 'log RAW'), actual, expected)
            receipt_checks.append({'case': prior.get('name', 'log RAW'), 'sha256': actual, 'unchanged': True})
        dump('50mm-existing-receipts.json', receipt_checks)
    sources = ['src/gxr_studio/lut/identify.py', 'src/gxr_studio/lut/photo.py',
               'src/gxr_studio/lut/library.py', 'src/gxr_studio/lut/cube.py',
               'src/gxr_studio/lut/spaces.py', 'src/gxr_studio/lut/scene.py',
               'src/gxr_studio/api/render_routes.py']
    dump(f'{phase}-sources.json', {name: digest(ROOT / 'studio' / name) for name in sources})
    references = ['research/vlog_alchemy_eval/studio_imports.json', 'research/vlog_alchemy_eval/studio_photo_checks.json',
                  'research/vlog_alchemy_eval/selected_dngs.json', 'research/vlog_alchemy_eval/data.py',
                  'research/color_fit_v2/05_classic_chrome/round4/local/fit_v4_noT1.json']
    dump('reference-inputs.json', {name: digest(ROOT / name) for name in references})
    if phase == 'after':
        before = {row['path']: row for row in json.loads((HERE / 'before-photos.json').read_text())}
        for row in results:
            if row['path'] in before:
                for key in ('half_sha256', 'full_sha256'):
                    if key in before[row['path']]:
                        assert row[key] == before[row['path']][key], (row['path'], key)
        old = {row['path']: row for row in json.loads((HERE / 'before-imports.json').read_text())}
        fixes = [row['path'] for row in rows if '/v-log-alchemy-' in row['path']
                 and old[row['path']]['input_space'] != 'vlog' and row['input_space'] == 'vlog']
        assert len(fixes) == 14
        assert all(row['input_space'] == 'vlog' for row in rows if '/v-log-alchemy-' in row['path'])
        assert all(row['input_space_state'] == 'unknown' for row in rows if '/panasonic-25th-' in row['path'])
        for row in rows:
            name = Path(row['path']).name
            if 'BT1886' in name:
                assert row['output_space'] == 'gamma24', name
            elif 'Hasselblad' in name and 'Rec709' in name:
                assert row['output_space'] == 'rec709', name
            elif 'sRGB' in name:
                assert row['output_space'] == 'srgb', name
        dump('comparison.json', {'input_corrections': len(fixes), 'corrected_paths': fixes,
                                '50mm_hashes_unchanged': True,
                                '50mm_existing_receipts_unchanged': len(receipt_checks),
                                'mount_photos': sum(row['unit'] == 'mount-a12' for row in results),
                                'output_changes': [{'path': row['path'], 'before': old[row['path']]['output_space'],
                                                    'after': row['output_space']} for row in rows
                                                   if old[row['path']]['output_space'] != row['output_space']]})
    assert audit.network_attempts() == []
    shutil.rmtree(run)


if __name__ == '__main__':
    main()
