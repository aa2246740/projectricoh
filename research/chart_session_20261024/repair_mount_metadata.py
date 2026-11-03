"""Repair only the metadata interpretation in session copies of Mount frame records."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
import session_runtime as s


def apply(a, chain):
    mod = chain.ar.s2d()
    # Imported jpeg_tiff keeps its defining module globals, which may differ from S.Tiff.
    s.patch_tiff(mod.jpeg_tiff.__globals__['Tiff'])
    for cls in {mod.Tiff, mod.jpeg_tiff.__globals__['Tiff'], chain.dng.analyze_capture().Tiff}:
        original_ratio = cls.ifd.__globals__['_session_ratio']
        def ratio(tag, numerator, denominator, original=original_ratio):
            if tag == 42034 and denominator == 0:
                return None
            return original(tag, numerator, denominator)
        cls.ifd.__globals__['_session_ratio'] = ratio
    reader = chain.ar.read_meta
    def safe_meta(jpg, dng, sidecar):
        value = reader(jpg, dng, sidecar)
        with Image.open(jpg) as im:
            model = str(im.getexif().get(272, ''))
        if 'MOUNT' in model and value.get('f') in (None, 0):
            value['f'] = None
            value['aperture_status'] = 'unknown; JPEG 0/0 or DNG zero EXIF is not actual ring aperture'
        return value
    chain.ar.read_meta = safe_meta
    lens = a.lens_meta
    def safe_lens(path):
        value = lens(path)
        if 'MOUNT' in value.get('model', '') and value.get('focal_length_mm') in (None, 0):
            value['focal_length_mm'] = None
        return value
    a.lens_meta = safe_lens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extraction', default='extraction')
    ap.add_argument('--out', default='mount_repaired')
    args = ap.parse_args()
    src, out = s.LOCAL / args.extraction, (s.LOCAL / args.out).resolve()
    assert out.is_relative_to(s.LOCAL) and not out.exists()
    a, chain, p = s.setup(src, freeze=False)
    apply(a, chain)
    summary = []
    for n in range(1261, 1269):
        stem = f'R805{n}'
        f = json.loads((src / 'frames' / (stem + '.json')).read_text())
        pair = {k: Path(v) for k, v in f['paths'].items()}
        pair['frame'] = stem
        for path in pair.values():
            if isinstance(path, Path):
                p.add(path)
        meta, errors = a.metadata(chain, pair, f['manifest'])
        assert meta['f'] is None and not errors, (stem, errors)
        old = f['metadata_errors']
        f['meta'], f['metadata_errors'] = meta, errors
        f['metadata_adapter'] = {'source': 'repair_mount_metadata.py', 'old_errors': old,
                                 'unknown_aperture_preserved': True, 'sampling_reused_without_change': True}
        for q in f['patches']:
            q['flags'] = [v for v in q['flags'] if v != 'frame-metadata-or-manifest-error']
            q['valid'] = not q['flags']
        registration = f['raw_jpeg_registration']
        f['status'] = 'ok' if registration.get('ok') and registration.get('after_offset', {'ok': True}).get('ok') else 'quality-failed'
        f['valid_patches'] = sum(q['valid'] for q in f['patches'])
        s.dump(out / 'frames' / (stem + '.json'), f)
        summary.append({'frame': stem, 'page': f['page'], 'kind': f['kind'], 'shutter_s': meta['t'],
                        'aperture_f': None, 'valid_patches': f['valid_patches'], 'status': f['status'],
                        'old_metadata_error_count': len(old), 'new_metadata_errors': errors})
    s.dump(out / 'summary.json', summary)
    s.dump(out / 'provenance.json', p.finish())
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
