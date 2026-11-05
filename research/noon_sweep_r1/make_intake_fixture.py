#!/usr/bin/env python3
"""Make a local synthetic DNG+JPEG batch to exercise the complete intake CLI.

The TIFF writer is independent of the product reader. Minimal fixture metadata
borrows an existing MOUNT shot's selector context; no real photo is duplicated.
"""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_noon as n
import datetime as dt
from fractions import Fraction
import struct
import numpy as np
from PIL import Image, ImageDraw


def tiff(raw, meta, w, h):
    data = bytearray(b'II*\0'+struct.pack('<I', 8))
    def alloc(length):
        if len(data) % 2:
            data.append(0)
        at = len(data)
        data.extend(bytes(length))
        return at
    root_tags = [272, 274, 330, 34665, 50706, 50728, 50730]
    ex_tags = [33434, 33437, 34850, 34855, 36867, 37380, 37384, 37500, 40961, 41986, 41987, 42036]
    raw_tags = [256, 257, 258, 259, 262, 266, 273, 279, 33422, 50714, 50717, 50719, 50720]
    root = alloc(2+12*len(root_tags)+4)
    ex = alloc(2+12*len(ex_tags)+4)
    rifd = alloc(2+12*len(raw_tags)+4)
    assert root == 8
    def encoded(typ, value):
        if typ == 2:
            b = value.encode('ascii')+b'\0'
            return len(b), b
        if typ in (1, 7):
            return len(value), bytes(value)
        if typ in (3, 4):
            return len(value), struct.pack('<'+('H' if typ == 3 else 'I')*len(value), *value)
        if typ in (5, 10):
            pairs = []
            for v in value:
                q = Fraction(v).limit_denominator(1000000)
                pairs.extend([q.numerator, q.denominator])
            return len(value), struct.pack('<'+('I' if typ == 5 else 'i')*len(pairs), *pairs)
        raise ValueError(typ)
    def ifd(at, entries):
        entries = sorted(entries)
        struct.pack_into('<H', data, at, len(entries))
        locations = {}
        for i, (tag, typ, value) in enumerate(entries):
            count, payload = encoded(typ, value)
            p = at+2+i*12
            struct.pack_into('<HHI', data, p, tag, typ, count)
            if len(payload) <= 4:
                data[p+8:p+12] = payload+bytes(4-len(payload))
                locations[tag] = p+8
            else:
                destination = alloc(len(payload))
                data[destination:destination+len(payload)] = payload
                struct.pack_into('<I', data, p+8, destination)
                locations[tag] = destination
        return locations
    ifd(root, [(272, 2, 'RICOH GXR synthetic fixture'), (274, 3, [1]), (330, 4, [rifd]), (34665, 4, [ex]),
        (50706, 1, [1, 4, 0, 0]), (50728, 5, meta['as_shot_neutral']), (50730, 10, [0])])
    note = b'Ricoh\0\0\0'+bytes(18)+bytes.fromhex(meta['maker_shot_hex'])
    eloc = ifd(ex, [(33434, 5, [meta['exposure_s']]), (33437, 5, [0]), (34850, 3, [1]), (34855, 3, [200]),
        (36867, 2, meta['time']), (37380, 10, [0]), (37384, 3, [meta['light_source']]), (37500, 7, note),
        (40961, 3, [1]), (41986, 3, [1]), (41987, 3, [meta['wb_exif']]), (42036, 2, 'Synthetic MOUNT fixture')])
    na = eloc[37500]
    struct.pack_into('>H', data, na+8, 1)
    struct.pack_into('>HHII', data, na+10, 0x1001, 7, 224, na+26)
    rloc = ifd(rifd, [(256, 4, [w]), (257, 4, [h]), (258, 3, [12]), (259, 3, [1]), (262, 3, [32803]),
        (266, 3, [1]), (273, 4, [0]), (279, 4, [w*h*3//2]), (33422, 1, [0, 1, 1, 2]),
        (50714, 5, [0]), (50717, 4, [4095]), (50719, 4, [0, 0]), (50720, 4, [w, h])])
    if raw is not None:
        values = np.asarray(raw, np.uint16).ravel()
        a, b = values[::2], values[1::2]
        packed = np.column_stack([a >> 4, ((a & 15) << 4) | (b >> 8), b & 255]).astype(np.uint8).tobytes()
        at = alloc(len(packed))
        data[at:at+len(packed)] = packed
        struct.pack_into('<I', data, rloc[273], at)
    return bytes(data)


def sensor_fill(raw, box, x, neutral):
    x0, y0, x1, y1 = map(int, box)
    for dy in range(2):
        for dx in range(2):
            c = ((0, 1), (1, 2))[(y0+dy)%2][(x0+dx)%2]
            raw[y0+dy:y1:2, x0+dx:x1:2] = np.clip(np.rint(x[c]*neutral[c]), 0, 4095)


def main():
    lock = n.setup()
    out = n.LOCAL/'intake-fixture'
    out.mkdir(exist_ok=True)
    sys.addaudithook(n.guard)
    model = n.Reference()
    field = n.module(n.ROOT/'research/probe_pack_r1/field_20261103.py', 'noon_fixture_raw')
    meta = field.metadata(field.Tiff((n.ROOT/'captures/probe3-field-20261104/R8051955.DNG').read_bytes()))
    pages = n.read(n.ROOT/'research/color_references/screen_chart.json')['pages']
    render = n.read(n.LOCAL/'synthetic-pages/render.json')
    neutral = np.asarray(meta['as_shot_neutral'])
    manifest = dict(schema='noon-sweep-manifest/1', frames={})
    truth, hashes = [], []
    for i in range(83):
        stamp = dt.datetime(2026, 11, 4, 12)+dt.timedelta(seconds=i*3)
        current_meta = dict(meta, time=stamp.strftime('%Y:%m:%d %H:%M:%S'))
        w, h = 1600, 1000
        raw = np.zeros((h, w), np.uint16)
        drift = 1+i*.0001*np.array([1., .8, .5])
        if i < 72:
            pi, group = i % 8, i//8
            setting = n.SETTINGS[group] if group < 8 else '04 Std'
            actual = '06 F-CN' if i == 8 else setting
            item, page = render['pages'][pi], pages[pi]
            image = Image.open(n.LOCAL/'synthetic-pages'/item['filename']).convert('RGB')
            draw = ImageDraw.Draw(image)
            desired = np.array([p['rgb8_srgb'] for p in page['patches']], float)*.55+45
            xx, _ = model.inverse04(desired)
            xx *= drift
            rgb = model.predict(actual, xx)
            for k, roi in enumerate(item['rois']):
                b = roi['box']
                box = [round(b['x']), round(b['y']), round(b['x']+b['width']), round(b['y']+b['height'])]
                draw.rectangle([box[0], box[1], box[2]-1, box[3]-1], fill=tuple(np.rint(rgb[k]).astype(int)))
                sensor_fill(raw, box, xx[k], neutral)
            phase = page['id']
        else:
            k = i-72
            setting = actual = n.SETTINGS[k] if k < 8 else '04 Std'
            image = Image.new('RGB', (w, h), (40, 40, 40))
            draw = ImageDraw.Draw(image)
            desired = np.array([p['rgb8_srgb'] for p in pages[0]['patches'][-27:]], float)*.55+45
            xx, _ = model.inverse04(desired)
            xx *= drift
            rgb = model.predict(actual, xx)
            for p in range(27):
                if p < 24:
                    r, c = divmod(p, 6)
                    box = [80+c*166, 100+r*150, 80+(c+1)*166-10, 100+(r+1)*150-10]
                else:
                    r = p-24
                    box = [1180, 100+r*280, 1480, 350+r*280]
                draw.rectangle([box[0], box[1], box[2]-1, box[3]-1], fill=tuple(np.rint(rgb[p]).astype(int)))
                sensor_fill(raw, box, xx[p], neutral)
            corners = [[75/w, 95/h], [1071/w, 95/h], [1071/w, 695/h], [75/w, 695/h]]
            phase = 'daylight' if k < 9 else 'indoor'
            manifest['frames'][f'F{i:03d}'] = dict(kind='physical', setting=setting, scene=phase,
                chart=dict(cols=6, rows=4, corners=corners, patch_fraction_of_pitch=[156/166, 140/150]),
                rois=[dict(id=name, group=group, box=[1180/w, (100+r*280)/h, 1480/w, (350+r*280)/h])
                      for r, (name, group) in enumerate([('skin', 'memory_skin'), ('blue', 'blue'), ('leaf', 'memory_foliage')])])
        dp, jp = out/f'F{i:03d}.DNG', out/f'F{i:03d}.JPG'
        dp.write_bytes(tiff(raw, current_meta, w, h))
        image.save(jp, quality=98, subsampling=0, exif=b'Exif\0\0'+tiff(None, current_meta, w, h))
        truth.append(dict(frame=jp.stem, setting=setting, actual=actual, phase=phase, synthetic=True))
        hashes.extend([f'{n.sha(dp)}  {dp.name}\n', f'{n.sha(jp)}  {jp.name}\n'])
        print('FIXTURE', jp.stem, phase, actual, flush=True)
    (out/'SHA256SUMS').write_text(''.join(hashes))
    n.dump(n.LOCAL/'intake-fixture-manifest.json', manifest)
    n.dump(n.LOCAL/'intake-fixture-truth.json', dict(synthetic=True, frames=truth, photo_count=83, output_bytes=sum(p.stat().st_size for p in out.iterdir())))


if __name__ == '__main__':
    main()
