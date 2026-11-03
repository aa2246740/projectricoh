"""Check Mount MakerNotes, RAW saturation and repeated-anchor geometry."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np, s
import json


def main():
    ac = rt.tiff_reader()
    maker = {}
    for n in range(1261, 1269):
        stem = f'R805{n}'
        p = s.source(rt.CAP / (stem + '.DNG'))
        t = ac.Tiff(p.read_bytes())
        root = t.ifd(t.root)
        exif = t.ifd(root[34665]['value'][0])
        note = exif[37500]
        entries = t.ifd(note['offset'] + 8, '>')
        maker[stem] = {'sha256': s.digest(p), 'FNumber': exif[33437]['value'],
            'tags': {f'0x{k:04x}': {'type': v['type'], 'count': v['count'], 'raw_hex': v['raw'].hex()} for k, v in entries.items()}}
        if n == 1268:
            crop, black, white, neutral, stats = ac.decode_raw(t)
            h, w = crop.shape
            cells = []
            for yy in np.linspace(.18, .78, 7):
                for xx in np.linspace(.18, .82, 9):
                    y, x = int(h*yy)//2*2, int(w*xx)//2*2
                    block = crop[y-40:y+40, x-40:x+40].astype(float)
                    ox, oy = stats['crop_origin_xy']
                    py, px = (oy+y-40)%2, (ox+x-40)%2
                    cfa = np.array([[0, 1], [1, 2]])
                    chans = [np.concatenate([block[i::2,j::2].ravel() for i in range(2) for j in range(2)
                        if cfa[(i+py)%2,(j+px)%2] == c]) for c in range(3)]
                    cells.append({'xy': [x/w, y/h], 'raw_mean': [float(np.mean(c-black)/(white-black)) for c in chans],
                        'saturation_fraction': [float(np.mean(c >= white)) for c in chans]})
            rt.dump('white_raw.json', {'stats': stats, 'cells': cells, 'whole_field_flat_usable': False,
                'reason': 'saturated green cannot define a common three-channel white flat'})
    rt.dump('makernotes.json', {'frames': maker, 'mapping_source': 'https://raw.githubusercontent.com/exiftool/exiftool/master/lib/Image/ExifTool/Ricoh.pm',
        'mapping_sha256': s.digest(rt.LOCAL / 'Ricoh.pm'), 'correction_tags_identified': False,
        'status': 'No documented Color Shading Correction or Peripheral illumination mapping found; unknown values are not decoded from zero bytes.'})
    geometries = {}
    for n in range(1261, 1269):
        p = rt.ROOT / f'research/chart_session_20261024/local/analysis-final/frames/R805{n}.json'
        d = s.read(p)
        geometries[d['frame']] = {'geometry': d['geometry'], 'registration': d['raw_jpeg_registration'],
            'patches': [{k: q[k] for k in ('patch_id', 'sample_key', 'class', 'roi_polygon', 'chart_roi_bbox', 'nominal_lab_d65')} for q in d['patches']]}
    rt.dump('geometries.json', geometries)
    rows = [json.loads(l) for l in s.source(rt.EXCHANGE / 'patches.jsonl').read_text().splitlines()]
    from collections import Counter
    print('anchors', Counter(r['sample_key'] for r in rows if r['class'] == 'anchor'))
    print('raw white', stats['raw_saturation_fraction'], 'cells', cells[20:23])
    print('maker tags', [(k, v['type'], v['count']) for k, v in maker['R8051262']['tags'].items()])
    print('registration', geometries['R8051262']['registration'])
    rt.dump('environment.json', {'python': sys.executable, 'numpy': np.__version__, 'preflight': 'APFS UUID and Writable/Media/Volume verified',
        'scope': str(rt.HERE), 'camera_acceptance': False})
    s.finish(rt.LOCAL / 'inspect.inputs.json')


if __name__ == '__main__':
    main()
