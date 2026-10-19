#!/usr/bin/env python3
"""Dump maker-note modes for the contributed GR and GR IV files."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tiff_makernote import (
    Tiff, decode_gr2013, decode_gr3_family, jpeg_exif_tiff, maker_note_bytes,
    subifds, summarise_ifd,
)


def load_tiff(path):
    data = Path(path).read_bytes()
    if data[:2] == b'\xff\xd8':
        tiff, _ = jpeg_exif_tiff(data)
        return tiff
    return Tiff(data)


def one(path):
    tiff = load_tiff(path)
    source, offset, note, root, exif = maker_note_bytes(tiff)
    record = {
        'file': str(path),
        'header_hex': note[:32].hex() if note else None,
        'maker_source': source,
        'maker_length': len(note),
        'ifd0': summarise_ifd(root),
        'exif': summarise_ifd(exif),
    }
    if path.suffix.upper() == '.DNG':
        record['subifds'] = [summarise_ifd(item) for item in subifds(tiff, root)]
    if note.startswith(b'Ricoh\0\0\0'):
        entries, decoded = decode_gr2013(tiff, offset)
        record['maker_tags'] = summarise_ifd(entries)
        record['decoded'] = decoded
    elif note.startswith(b'RICOH\0'):
        entries, decoded = decode_gr3_family(tiff, offset)
        record['maker_tags'] = summarise_ifd(entries)
        record['decoded'] = decoded
    else:
        record['decoded'] = None
    return record


def main():
    paths = [Path(item) for item in sys.argv[1:]]
    print(json.dumps([one(path) for path in paths], indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
