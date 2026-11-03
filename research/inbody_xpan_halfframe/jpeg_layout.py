#!/usr/bin/python3 -I -B
"""Read-only: list JPEG marker segments, EXIF pixel dimensions, the IFD1
thumbnail and any embedded JPEG streams (APPn previews) of camera JPEGs.
Usage: jpeg_layout.py FILE...   (stdout only, JSON lines)"""
import json
import struct
import sys


def tiff_tags(t, off, le):
    e = '<' if le else '>'
    n = struct.unpack_from(e + 'H', t, off)[0]
    out = {}
    for i in range(n):
        tag, typ, cnt, val = struct.unpack_from(e + 'HHII', t, off + 2 + 12 * i)
        if typ == 3 and cnt == 1:
            val = struct.unpack_from(e + 'H', t, off + 2 + 12 * i + 8)[0]
        out[tag] = (typ, cnt, val)
    nxt = struct.unpack_from(e + 'I', t, off + 2 + 12 * n)[0]
    return out, nxt


def sof_dims(b, start):
    i = start + 2
    while i + 4 <= len(b):
        if b[i] != 0xFF:
            return None
        m = b[i + 1]
        ln = struct.unpack_from('>H', b, i + 2)[0]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack_from('>HH', b, i + 5)
            return [w, h]
        if m == 0xDA:
            return None
        i += 2 + ln
    return None


def main(path):
    b = open(path, 'rb').read()
    rec = {'file': path, 'bytes': len(b), 'segments': []}
    i = 2
    while i + 4 <= len(b):
        if b[i] != 0xFF:
            break
        m = b[i + 1]
        ln = struct.unpack_from('>H', b, i + 2)[0]
        seg = {'marker': f'{m:02X}', 'offset': i, 'len': ln}
        body = b[i + 4:i + 2 + ln]
        if m == 0xE1 and body[:6] == b'Exif\x00\x00':
            t = body[6:]
            le = t[:2] == b'II'
            e = '<' if le else '>'
            ifd0 = struct.unpack_from(e + 'I', t, 4)[0]
            tags0, ifd1 = tiff_tags(t, ifd0, le)
            if 0x8769 in tags0:
                ex, _ = tiff_tags(t, tags0[0x8769][2], le)
                seg['exif_pixel_xy'] = [ex.get(0xA002, (0, 0, None))[2], ex.get(0xA003, (0, 0, None))[2]]
                if 0x927C in ex:
                    seg['makernote_len'] = ex[0x927C][1]
            if ifd1:
                tags1, _ = tiff_tags(t, ifd1, le)
                if 0x0201 in tags1:
                    o, n = tags1[0x0201][2], tags1[0x0202][2]
                    seg['ifd1_thumb'] = {'len': n, 'sof': sof_dims(t, o)}
        if m == 0xC0:
            seg['sof'] = list(struct.unpack_from('>HH', b, i + 5))[::-1]
        rec['segments'].append(seg)
        if m == 0xDA:
            break
        i += 2 + ln
    # every SOI that starts a nested stream, with its SOF size
    nested = []
    j = 2
    while True:
        j = b.find(b'\xFF\xD8\xFF', j)
        if j < 0:
            break
        nested.append({'offset': j, 'sof': sof_dims(b, j)})
        j += 3
    rec['embedded_soi'] = nested
    print(json.dumps(rec))


for p in sys.argv[1:]:
    main(p)
