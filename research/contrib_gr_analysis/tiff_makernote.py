#!/usr/bin/env python3
"""Read TIFF/EXIF structure and Ricoh / Pentax maker notes.

Tag names and enumerated values are copied from the public ExifTool tables
(Ricoh.pm ref 3 for the GR, Pentax.pm ImageTone / slider tags) and from
github.com/richadams/ricoh-gr3-metadata Pentax_0x0247.md. This file does not
execute either of those sources.
"""
import struct


TIFF_TYPES = {
    1: ('B', 1), 2: (None, 1), 3: ('H', 2), 4: ('I', 4), 5: ('II', 8),
    6: ('b', 1), 7: (None, 1), 8: ('h', 2), 9: ('i', 4), 10: ('ii', 8),
    11: ('f', 4), 12: ('d', 8),
}

# ExifTool Ricoh.pm, tags annotated #3 (Tim Gray, GR).
GR_IMAGE_EFFECTS = {
    0: 'Standard', 1: 'Vivid', 3: 'Black & White', 5: 'B&W Toning Effect',
    6: 'Setting 1', 7: 'Setting 2', 9: 'High-contrast B&W', 10: 'Cross Process',
    11: 'Positive Film', 12: 'Bleach Bypass', 13: 'Retro', 15: 'Miniature',
    17: 'High Key',
}
GR_VIGNETTING = {0: 'Off', 1: 'Low', 2: 'Medium', 3: 'High'}
GR_TONING = {
    0: 'Off', 1: 'Sepia', 2: 'Red', 3: 'Green', 4: 'Blue', 5: 'Purple',
    6: 'B&W', 7: 'Color',
}
GR_HUE_ADJUST = {
    0: 'Off', 1: 'Basic', 2: 'Magenta', 3: 'Yellow', 4: 'Normal', 5: 'Warm',
    6: 'Cool',
}
GR_WHITE_BALANCE = {
    0: 'Auto', 1: 'Multi-P Auto', 2: 'Daylight', 3: 'Cloudy',
    4: 'Incandescent 1', 5: 'Incandescent 2', 6: 'Daylight Fluorescent',
    7: 'Neutral White Fluorescent', 8: 'Cool White Fluorescent',
    9: 'Warm White Fluorescent', 10: 'Manual', 11: 'Kelvin', 12: 'Shade',
}
GR_EXPOSURE_PROGRAM = {
    1: 'Auto', 2: 'Program AE', 3: 'Aperture-priority AE',
    4: 'Shutter speed priority AE', 5: 'Shutter/aperture priority AE',
    6: 'Manual', 7: 'Movie',
}
GR_NOISE = {0: 'Off', 1: 'Weak', 2: 'Medium', 3: 'Strong'}
GR_DYNAMIC_RANGE = {0: 'Off', 3: 'Weak', 4: 'Medium', 5: 'Strong'}
GR_FOCUS = {
    1: 'Manual', 2: 'Multi AF', 3: 'Spot AF', 4: 'Snap', 5: 'Infinity',
    7: 'Face Detect', 8: 'Subject Tracking', 9: 'Pinpoint AF', 10: 'Movie',
}
GR_RECORDING = {2: 'JPEG', 3: 'DNG'}

# ExifTool Pentax.pm 0x004f. The 256+ names are documented as GR III Image Control.
PENTAX_IMAGE_TONE = {
    0: 'Natural', 1: 'Bright', 2: 'Portrait', 3: 'Landscape', 4: 'Vibrant',
    5: 'Monochrome', 6: 'Muted', 7: 'Reversal Film', 8: 'Bleach Bypass',
    9: 'Radiant', 10: 'Cross Processing', 11: 'Flat',
    256: 'Standard', 257: 'Vivid', 258: 'Monotone', 259: 'Soft Monotone',
    260: 'Hard Monotone', 261: 'Hi-contrast B&W', 262: 'Positive Film',
    263: 'Bleach Bypass 2', 264: 'Retro', 265: 'HDR Tone',
    266: 'Cross Processing 2', 267: 'Negative Film',
    32768: 'Standard', 32769: 'Hard', 32770: 'Soft',
    33024: 'Monochrome',
}
# richadams/ricoh-gr3-metadata Pentax_0x0247.md, GR III firmware 2.10.
BW_TONING = {-1: 'N/A', 0: 'Off', 1: 'Sepia', 2: 'Red', 3: 'Green', 4: 'Blue', 5: 'Purple'}
BLEACH_TONING = {-1: 'N/A', 0: 'Off', 1: 'Cold', 2: 'Warm'}
HDR_TONING = {0: 'Off', 1: 'B&W', 2: 'Sepia'}
HDR_LEVEL = {1: 'Low', 2: 'Med', 3: 'High'}
CROSS_TONE = {-1: 'N/A', 1: 'Blue', 2: 'Magenta', 3: 'Yellow'}
BW_GRAIN = {0: 'Off', 1: '3 (Strong)', 3: '2 (Medium)', 5: '1 (Weak)', 8: 'N/A'}

NAMED = {
    256: 'ImageWidth', 257: 'ImageLength', 258: 'BitsPerSample', 259: 'Compression',
    262: 'PhotometricInterpretation', 270: 'ImageDescription', 271: 'Make',
    272: 'Model', 273: 'StripOffsets', 274: 'Orientation', 277: 'SamplesPerPixel',
    278: 'RowsPerStrip', 279: 'StripByteCounts', 282: 'XResolution',
    283: 'YResolution', 284: 'PlanarConfiguration', 296: 'ResolutionUnit',
    305: 'Software', 306: 'DateTime', 330: 'SubIFD', 513: 'JPEGInterchangeFormat',
    514: 'JPEGInterchangeFormatLength', 531: 'YCbCrPositioning',
    33421: 'CFARepeatPatternDim', 33422: 'CFAPattern', 33434: 'ExposureTime',
    33437: 'FNumber', 34850: 'ExposureProgram', 34855: 'ISOSpeedRatings',
    36864: 'ExifVersion', 36867: 'DateTimeOriginal', 36868: 'DateTimeDigitized',
    37121: 'ComponentsConfiguration', 37377: 'ShutterSpeedValue',
    37378: 'ApertureValue', 37380: 'ExposureBiasValue', 37381: 'MaxApertureValue',
    37383: 'MeteringMode', 37384: 'LightSource', 37385: 'Flash',
    37386: 'FocalLength', 37500: 'MakerNote', 40961: 'ColorSpace',
    40962: 'PixelXDimension', 40963: 'PixelYDimension', 41495: 'SensingMethod',
    41728: 'FileSource', 41729: 'SceneType', 41986: 'ExposureMode',
    41987: 'WhiteBalance', 41989: 'FocalLengthIn35mmFilm',
    41990: 'SceneCaptureType', 42033: 'BodySerialNumber', 42036: 'LensModel',
    50706: 'DNGVersion', 50707: 'DNGBackwardVersion', 50708: 'UniqueCameraModel',
    50714: 'BlackLevel', 50715: 'BlackLevelDeltaH', 50716: 'BlackLevelDeltaV',
    50717: 'WhiteLevel', 50718: 'DefaultScale', 50719: 'DefaultCropOrigin',
    50720: 'DefaultCropSize', 50721: 'ColorMatrix1', 50722: 'ColorMatrix2',
    50723: 'CameraCalibration1', 50728: 'AsShotNeutral', 50739: 'ShadowScale',
    50740: 'DNGPrivateData', 50778: 'CalibrationIlluminant1',
    50779: 'CalibrationIlluminant2', 50829: 'ActiveArea', 50936: 'DefaultUserCrop',
    51008: 'OpcodeList1', 51009: 'OpcodeList2', 51022: 'OpcodeList3',
}


class Tiff:
    def __init__(self, data):
        self.data = data
        if data[:2] not in (b'II', b'MM'):
            raise ValueError('not TIFF')
        self.endian = '<' if data[:2] == b'II' else '>'
        if self._u('H', 2)[0] != 42:
            raise ValueError('not classic TIFF')
        self.root = self._u('I', 4)[0]

    def _u(self, fmt, offset, endian=None):
        return struct.unpack_from((endian or self.endian) + fmt, self.data, offset)

    def ifd(self, offset, endian=None, base=0):
        endian = endian or self.endian
        count = self._u('H', offset, endian)[0]
        if not 0 < count < 512:
            raise ValueError(f'implausible IFD count {count} at {offset}')
        end = offset + 2 + 12 * count + 4
        if end > len(self.data):
            raise ValueError('IFD extends past file')
        entries = []
        for index in range(count):
            pos = offset + 2 + 12 * index
            tag, typ, n = self._u('HHI', pos, endian)
            if typ not in TIFF_TYPES:
                entries.append({'tag': tag, 'type': typ, 'count': n, 'value': None,
                                'raw': b'', 'offset': None, 'inline': True})
                continue
            code, size = TIFF_TYPES[typ]
            nbytes = n * size
            if nbytes <= 4:
                raw_off = pos + 8
                value_off = raw_off
                external = False
            else:
                value_off = self._u('I', pos + 8, endian)[0] + base
                raw_off = value_off
                external = True
            if value_off < 0 or value_off + nbytes > len(self.data):
                raise ValueError(f'tag {tag:#06x} value out of range')
            raw = self.data[value_off:value_off + nbytes]
            if typ == 2:
                value = raw.split(b'\0', 1)[0].decode('latin1')
            elif code is None:
                value = raw
            elif typ in (5, 10):
                parts = self._u(code * n, value_off, endian)
                value = [parts[i] / parts[i + 1] if parts[i + 1] else None
                         for i in range(0, len(parts), 2)]
            else:
                value = list(self._u(code * n, value_off, endian))
            entries.append({'tag': tag, 'type': typ, 'count': n, 'value': value,
                            'raw': raw, 'offset': value_off, 'inline': not external})
        nxt = self._u('I', offset + 2 + 12 * count, endian)[0]
        return entries, (nxt + base if nxt else 0)


def jpeg_exif_tiff(data):
    if data[:2] != b'\xff\xd8':
        raise ValueError('not JPEG')
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xff:
            raise ValueError('marker alignment')
        marker = data[pos + 1]
        if marker == 0xd8:
            pos += 2
            continue
        if marker == 0xd9 or marker == 0xda:
            break
        length = int.from_bytes(data[pos + 2:pos + 4], 'big')
        payload = data[pos + 4:pos + 2 + length]
        if marker == 0xe1 and payload.startswith(b'Exif\0\0'):
            return Tiff(payload[6:]), pos + 10
        pos += 2 + length
    raise ValueError('JPEG has no EXIF')


def _scalar(entry):
    value = entry['value']
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _named_map(enum, value):
    if isinstance(value, list):
        return [_named_map(enum, item) for item in value]
    return {'value': value, 'name': enum.get(value)}


def decode_gr2013(tiff, note_offset):
    """Ricoh GR maker note: 8-byte 'Ricoh\\0\\0\\0' header, then a big-endian IFD.

    ExifTool MakerNotes.pm starts this note at value+8 and does not set a
    private base, so value offsets are TIFF-absolute. Tag 0x0002 then lands
    on the ASCII firmware 'Rev0501'.
    """
    if tiff.data[note_offset:note_offset + 8] != b'Ricoh\0\0\0':
        raise ValueError('not a Ricoh GR 2013 maker note')
    entries, _ = tiff.ifd(note_offset + 8, '>', base=0)
    by_tag = {item['tag']: item for item in entries}
    effect = _scalar(by_tag.get(0x1010, {'value': None}))
    contrast = _scalar(by_tag.get(0x1012, {'value': None}))
    if isinstance(contrast, int) and contrast > 0x7fffffff:
        contrast_signed = contrast - 0x100000000
    else:
        contrast_signed = contrast
    # ExifTool stores Contrast as int32s and prints 2147483647 as MAX.
    contrast_name = 'MAX' if contrast_signed == 2147483647 else contrast_signed
    decoded = {
        'layout': 'Ricoh\\0\\0\\0 + big-endian IFD at +8, offsets TIFF-absolute',
        'source': 'ExifTool Ricoh.pm Main, reference 3 (GR)',
        'firmware': _scalar(by_tag.get(0x0002, {'value': None})),
        'recording_format': _named_map(GR_RECORDING, _scalar(by_tag.get(0x1000, {'value': None}))),
        'exposure_program': _named_map(GR_EXPOSURE_PROGRAM, _scalar(by_tag.get(0x1001, {'value': None}))),
        'white_balance': _named_map(GR_WHITE_BALANCE, _scalar(by_tag.get(0x1003, {'value': None}))),
        'white_balance_fine_tune': list(struct.unpack('>hh', by_tag[0x1004]['raw'])) if 0x1004 in by_tag else None,
        'focus_mode': _named_map(GR_FOCUS, _scalar(by_tag.get(0x1006, {'value': None}))),
        'dynamic_range_expansion': _named_map(GR_DYNAMIC_RANGE, _scalar(by_tag.get(0x100e, {'value': None}))),
        'noise_reduction': _named_map(GR_NOISE, _scalar(by_tag.get(0x100f, {'value': None}))),
        'image_effects': _named_map(GR_IMAGE_EFFECTS, effect),
        'vignetting': _named_map(GR_VIGNETTING, _scalar(by_tag.get(0x1011, {'value': None}))),
        'contrast': {'value': contrast_signed, 'name': contrast_name},
        'saturation': _scalar(by_tag.get(0x1013, {'value': None})),
        'sharpness': _scalar(by_tag.get(0x1014, {'value': None})),
        'toning_effect': _named_map(GR_TONING, _scalar(by_tag.get(0x1015, {'value': None}))),
        'hue_adjust': _named_map(GR_HUE_ADJUST, _scalar(by_tag.get(0x1016, {'value': None}))),
        'nd_filter': _scalar(by_tag.get(0x1019, {'value': None})),
        'color_temp_kelvin': _scalar(by_tag.get(0x1307, {'value': None})),
        'color_temperature': _scalar(by_tag.get(0x1308, {'value': None})),
        'focal_length': _scalar(by_tag.get(0x1500, {'value': None})),
        'sensor_width': _scalar(by_tag.get(0x1601, {'value': None})),
        'sensor_height': _scalar(by_tag.get(0x1602, {'value': None})),
        'cropped_image_width': _scalar(by_tag.get(0x1603, {'value': None})),
        'cropped_image_height': _scalar(by_tag.get(0x1604, {'value': None})),
    }
    # int32s: the IFD type may be LONG. Reinterpret the four raw bytes.
    for tag, key in ((0x1012, 'contrast_raw_i32'), (0x1013, 'saturation_raw_i32'), (0x1014, 'sharpness_raw_i32')):
        raw = by_tag.get(tag, {}).get('raw', b'')
        if len(raw) >= 4:
            decoded[key] = struct.unpack('>i', raw[:4])[0]
    return entries, decoded


def _i16(blob, offset):
    return struct.unpack_from('<h', blob, offset)[0]


def _filter_effect(flags, red, green, blue):
    if flags & 0x08:
        return {'flags': flags, 'name': 'N/A'}
    sign = lambda bit, value: -value if flags & bit else value
    return {
        'flags': flags,
        'on': bool(flags & 0x01),
        'rgb_percent': [sign(0x10, red), sign(0x20, green), sign(0x40, blue)],
    }


def decode_image_control_0247(blob):
    """GR III Image Control blob. GR IV uses the same documented skeleton.

    richadams measured this on GR III firmware 2.10 only, and wrote that GR IV
    official samples mostly follow it, with at least the grain field not fully
    mapped. Callers must label GR IV slider names as inferred.
    """
    if len(blob) < 44:
        return {'length': len(blob), 'hex': blob.hex(), 'decoded': None,
                'tail_hex': None}
    saturation, hue, key, contrast, highlight, shadow, sharpness = (
        _i16(blob, off) for off in (0, 2, 4, 6, 8, 10, 12))
    unknown_14 = _i16(blob, 14)
    retro = _i16(blob, 16)
    shading = _i16(blob, 18)
    clarity = _i16(blob, 20)
    unknown_22 = _i16(blob, 22)
    unknown_24 = _i16(blob, 24)
    bw_toning = _i16(blob, 26)
    bleach = _i16(blob, 28)
    hdr_toning = _i16(blob, 30)
    hdr_level = _i16(blob, 32)
    grain = _i16(blob, 38)
    unknown_40 = _i16(blob, 40)
    cross = _i16(blob, 42)
    menu = lambda value: None if value == -32768 else value
    return {
        'length': len(blob),
        'hex': blob.hex(),
        'saturation': menu(saturation),
        'hue': menu(hue),
        'high_low_key': menu(key),
        'contrast': menu(contrast),
        'contrast_highlight': menu(highlight),
        'contrast_shadow': menu(shadow),
        'sharpness': menu(sharpness),
        'unknown_offset_14': unknown_14,
        'retro_toning': {'value': retro, 'name': None if retro == -32768 else retro},
        'shading': menu(shading),
        'clarity': menu(clarity),
        'unknown_offset_22': unknown_22,
        'unknown_offset_24': unknown_24,
        'bw_toning': {'value': bw_toning, 'name': BW_TONING.get(bw_toning)},
        'bleach_bypass_toning': {'value': bleach, 'name': BLEACH_TONING.get(bleach)},
        'hdr_toning': {'value': hdr_toning, 'name': HDR_TONING.get(hdr_toning)},
        'hdr_tone_level': {'value': hdr_level, 'name': HDR_LEVEL.get(hdr_level)},
        'bw_filter_effect': _filter_effect(blob[34], blob[35], blob[36], blob[37]),
        'bw_grain_effect': {'value': grain, 'name': BW_GRAIN.get(grain),
                            'note': 'GR IV samples have been seen with a second byte that breaks this int16 map'},
        'unknown_offset_40': unknown_40,
        'cross_processing_color_tone': {'value': cross, 'name': CROSS_TONE.get(cross)},
        'tail_hex': blob[44:].hex(),
        'layout_source': 'richadams/ricoh-gr3-metadata Pentax_0x0247.md (GR III fw 2.10)',
    }


def decode_gr3_family(tiff, note_offset):
    """Pentax-family maker note used by GR III and GR IV.

    Header is 'RICOH\\0' plus a TIFF byte-order mark. The IFD starts at byte 8.
    On the GR IV file, value offsets are relative to the maker-note start:
    that base is what puts tag 0x0251 on the ASCII 'MY GR IV' and tag 0x0247
    on the 50-byte image-control record rather than a run of zeros.
    """
    if tiff.data[note_offset:note_offset + 6] != b'RICOH\0':
        raise ValueError('not a RICOH Pentax-family maker note')
    order = tiff.data[note_offset + 6:note_offset + 8]
    if order not in (b'II', b'MM'):
        raise ValueError('missing byte order')
    endian = '<' if order == b'II' else '>'
    entries, _ = tiff.ifd(note_offset + 8, endian, base=note_offset)
    by_tag = {item['tag']: item for item in entries}
    tone = _scalar(by_tag.get(0x004f, {'value': None}))
    control = by_tag.get(0x0247, {}).get('raw', b'')
    decoded = {
        'layout': 'RICOH\\0 + byte order + IFD at +8, offsets relative to note start',
        'byte_order': order.decode('ascii'),
        'image_tone': _named_map(PENTAX_IMAGE_TONE, tone),
        'image_tone_source': 'ExifTool Pentax.pm 0x004f ImageTone / GR III ImageControlMode',
        'saturation_tag_0x001f': by_tag.get(0x001f, {}).get('value'),
        'contrast_tag_0x0020': by_tag.get(0x0020, {}).get('value'),
        'sharpness_tag_0x0021': by_tag.get(0x0021, {}).get('value'),
        'hue_tag_0x0067': by_tag.get(0x0067, {}).get('value'),
        'high_low_key_tag_0x006c': by_tag.get(0x006c, {}).get('value'),
        'contrast_highlight_tag_0x006d': by_tag.get(0x006d, {}).get('value'),
        'contrast_shadow_tag_0x006e': by_tag.get(0x006e, {}).get('value'),
        'monochrome_filter_0x0073': by_tag.get(0x0073, {}).get('value'),
        'monochrome_toning_0x0074': by_tag.get(0x0074, {}).get('value'),
        'clarity_tag_0x0096': by_tag.get(0x0096, {}).get('value'),
        'raw_development_process_0x0062': _scalar(by_tag.get(0x0062, {'value': None})),
        'white_balance_0x0019': _named_map(
            {0: 'Auto', 1: 'Daylight', 2: 'Shade', 3: 'Fluorescent', 4: 'Tungsten',
             5: 'Manual', 6: 'Daylight Fluorescent', 7: 'Day White Fluorescent',
             8: 'White Fluorescent', 9: 'Flash', 10: 'Cloudy',
             11: 'Warm White Fluorescent', 14: 'Multi Auto',
             15: 'Color Temperature Enhancement', 17: 'Kelvin'},
            _scalar(by_tag.get(0x0019, {'value': None}))),
        'pentax_version_0x0000': by_tag.get(0x0000, {}).get('value'),
        'shadow_correction_0x0079': by_tag.get(0x0079, {}).get('value'),
        'dynamic_range_0x0069': by_tag.get(0x0069, {}).get('raw', b'').hex(),
        'crop_mode_0x0098': by_tag.get(0x0098, {}).get('value'),
        'text_0x0251': by_tag.get(0x0251, {}).get('value'),
        'image_control_0x0247': decode_image_control_0247(control) if control else None,
    }
    return entries, decoded


def summarise_ifd(entries):
    out = []
    for item in entries:
        value = item['value']
        if isinstance(value, (bytes, bytearray)):
            shown = {'bytes': len(value), 'sha256_prefix': value[:16].hex(),
                     'hex_prefix': value[:24].hex()}
        else:
            shown = value
        out.append({'tag': item['tag'], 'name': NAMED.get(item['tag']),
                    'type': item['type'], 'count': item['count'], 'value': shown})
    return out


def maker_note_bytes(tiff):
    """Return (source_tag, absolute_offset, raw_bytes) for the maker note."""
    root, _ = tiff.ifd(tiff.root)
    root_map = {item['tag']: item for item in root}
    exif = []
    if 34665 in root_map:
        exif, _ = tiff.ifd(root_map[34665]['value'][0])
    exif_map = {item['tag']: item for item in exif}
    if 37500 in exif_map:
        item = exif_map[37500]
        return 'Exif.MakerNote', item['offset'], item['raw'], root, exif
    if 50740 in root_map:
        item = root_map[50740]
        return 'IFD0.DNGPrivateData', item['offset'], item['raw'], root, exif
    return None, None, b'', root, exif


def subifds(tiff, root_entries):
    root_map = {item['tag']: item for item in root_entries}
    offsets = root_map.get(330, {}).get('value') or []
    found = []
    for offset in offsets:
        entries, _ = tiff.ifd(offset)
        found.append(entries)
    return found
