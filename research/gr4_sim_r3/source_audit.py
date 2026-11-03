"""Record capture/development state without estimating new calibration values."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
import simulator as sim


def main():
    sys.modules['simulator'] = sim
    sampler = rt.module('r3_source_sampler', 'research/gr4_analytic_target_r1/data.py')
    sources = []
    for row in rt.read('research/gr4_analytic_target_r1/local/dense_audit.json'):
        card = rt.read(row['card_manifest'])
        sources.append(('dense_page' + str(row['band']), card['dng_path'], row['dng_sha256']))
    for row in rt.read('research/gr4_analytic_target_r1/local/natural_audit.json'):
        path = 'captures/contrib/2026-10-25-gr4-wechat/extracted/GR4/Other/' + row['frame'] + '.DNG'
        sources.append(('other_' + row['frame'], path, row['source_dng_sha256']))
    for row in rt.read('research/gr4_analytic_target_r1/local/natural_modes_audit.json'):
        sources.append((row['frame'], row['path'], row['source_dng_sha256']))
    for row in rt.read(rt.LOCAL / 'new_samples_audit.json'):
        sources.append(('new_' + row['frame'], row['source'], row['source_sha256']))
    rows = []
    for label, path, digest in sources:
        t = sampler.tiff.Tiff(rt.inp(path, digest).read_bytes())
        g, maker = t.geometry(), t.maker()
        def field(tag):
            e = maker.entries.get(tag)
            if e is None: return None
            if e.typ == 7: return t.data[e.offset:e.offset + e.size].hex()
            return e.value
        exif = {}
        for node in t.ifds:
            for tag, name in ((34855, 'iso'), (33437, 'f_number'), (33434, 'exposure_seconds'), (305, 'software')):
                if tag in node.entries: exif[name] = node.entries[tag].value
        rows.append(dict(label=label, source=str(path), source_sha256=digest,
            baseline_exposure=g['baseline_exposure'], white=g['white'], geometry=g['crop_wh'],
            raw_development=field(0x0062), dynamic_range=field(0x0069),
            shadow_correction=field(0x0079), image_tone=field(0x004f), exif=exif,
            calibration_eligibility='training Standard only' if label in ('dense_page1', 'dense_page2', 'dense_page3') else 'none',
            state_fully_resolved=False))
    rt.dump('source_states.json', rows)
    print('Source metadata states saved without any new calibration.', flush=True)


if __name__ == '__main__': main()
