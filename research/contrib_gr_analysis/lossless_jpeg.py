#!/usr/bin/env python3
"""ITU-T T.81 lossless sequential JPEG (SOF3, process 14).

Supports predictor 1 and point transform 0, one shared DC Huffman table,
and one or two components at 1x1 sampling. Restart intervals are rejected.
The two-component layout used by these Ricoh DNGs interleaves one sample
of each component, so the mosaic width is SOF width times the component count.

Prediction follows T.81 Annex H.1.2.1:
the first sample of the image is predicted as 2^(P-Pt-1);
the rest of the first line uses Ra (the left sample of the same component);
the first sample of every later line uses Rb (the sample above);
every other sample uses the selected predictor. Predictor 1 is Ra.
Each component keeps its own reconstructed neighbours.
"""
import numpy as np


def _dht(payload, tables):
    pos = 0
    while pos < len(payload):
        ident = payload[pos]
        counts = list(payload[pos + 1:pos + 17])
        pos += 17
        total = sum(counts)
        symbols = list(payload[pos:pos + total])
        pos += total
        if ident >> 4:
            raise ValueError('AC Huffman table in a lossless scan')
        lengths = np.zeros(65536, np.uint8)
        syms = np.zeros(65536, np.uint8)
        code = 0
        seen = 0
        for size, count in enumerate(counts, 1):
            for _ in range(count):
                start = code << (16 - size)
                stop = (code + 1) << (16 - size)
                lengths[start:stop] = size
                syms[start:stop] = symbols[seen]
                seen += 1
                code += 1
            code <<= 1
        tables[ident & 15] = (lengths, syms)


def _unstuff(entropy):
    out = bytearray()
    pos = 0
    while pos < len(entropy):
        byte = entropy[pos]
        if byte != 0xff:
            out.append(byte)
            pos += 1
            continue
        if pos + 1 >= len(entropy):
            break
        nxt = entropy[pos + 1]
        if nxt == 0x00:
            out.append(0xff)
            pos += 2
            continue
        if nxt == 0xd9:
            break
        raise ValueError(f'unexpected marker FF{nxt:02X} in the scan')
    return out


def decode(data, max_samples=None):
    if data[:2] != b'\xff\xd8':
        raise ValueError('missing SOI')
    pos = 2
    tables = {}
    frame = None
    scan = None
    predictor = None
    point = None
    while pos + 4 <= len(data):
        if data[pos] != 0xff:
            raise ValueError('marker alignment')
        while data[pos + 1] == 0xff:
            pos += 1
        marker = data[pos + 1]
        if marker == 0xd9:
            raise ValueError('EOI before SOS')
        if marker == 0xda:
            length = int.from_bytes(data[pos + 2:pos + 4], 'big')
            payload = data[pos + 4:pos + 2 + length]
            count = payload[0]
            # SOS bytes per component are Cs, then Td (high nibble) / Ta.
            ids = [payload[2 + 2 * index] >> 4 for index in range(count)]
            selector = payload[1 + 2 * count]
            end = payload[2 + 2 * count]
            successive = payload[3 + 2 * count]
            if end != 0 or successive & 0xf0:
                raise ValueError('not a lossless sequential scan')
            predictor = selector
            point = successive & 0x0f
            scan = ids
            pos += 2 + length
            break
        length = int.from_bytes(data[pos + 2:pos + 4], 'big')
        payload = data[pos + 4:pos + 2 + length]
        pos += 2 + length
        if marker == 0xc3:
            precision = payload[0]
            height = int.from_bytes(payload[1:3], 'big')
            width = int.from_bytes(payload[3:5], 'big')
            components = payload[5]
            if len(payload) != 6 + 3 * components:
                raise ValueError('bad SOF3 length')
            if any(payload[7 + 3 * i] != 0x11 for i in range(components)):
                raise ValueError('only 1x1 sampling is decoded')
            frame = (precision, height, width, components)
        elif marker == 0xc4:
            _dht(payload, tables)
        elif marker == 0xdd:
            raise ValueError('restart intervals are not decoded')
        elif marker in (0xc0, 0xc1, 0xc2):
            raise ValueError('lossy SOF in a frame this decoder treats as raw')
    if frame is None or scan is None:
        raise ValueError('missing SOF3 or SOS')
    if predictor != 1 or point != 0:
        raise ValueError(f'only predictor 1 and Pt 0, got predictor {predictor} Pt {point}')
    precision, height, width, components = frame
    if len(scan) != components or any(item not in tables for item in scan):
        raise ValueError('scan tables do not match the frame')
    if len(set(scan)) != 1:
        raise ValueError('components use different Huffman tables')
    entropy = _unstuff(data[pos:]) + b'\x00\x00\x00\x00'
    lengths, symbols = tables[scan[0]]
    total = height * width * components
    if max_samples is not None:
        total = min(total, max_samples)
    diffs = np.empty(total, np.int32)
    buf = 0
    bits = 0
    cursor = 0
    for index in range(total):
        while bits < 16:
            buf = (buf << 8) | entropy[cursor]
            cursor += 1
            bits += 8
        prefix = (buf >> (bits - 16)) & 65535
        length = int(lengths[prefix])
        symbol = int(symbols[prefix])
        if length == 0:
            raise ValueError('invalid Huffman prefix')
        bits -= length
        if symbol == 0:
            diff = 0
        elif symbol == 16:
            diff = -32768
        else:
            while bits < symbol:
                buf = (buf << 8) | entropy[cursor]
                cursor += 1
                bits += 8
            bits -= symbol
            magnitude = (buf >> bits) & ((1 << symbol) - 1)
            diff = magnitude if magnitude >= (1 << (symbol - 1)) else magnitude - ((1 << symbol) - 1)
        if bits:
            buf &= (1 << bits) - 1
        else:
            buf = 0
        diffs[index] = diff
    if max_samples is not None and max_samples < height * width * components:
        return diffs, {'precision': precision, 'sof_wh': [width, height],
                       'components': components, 'predictor': predictor,
                       'point_transform': point, 'partial_samples': int(total)}
    diffs = diffs.reshape(height, width, components)
    mask = (1 << precision) - 1
    seed = 1 << (precision - 1)
    raw = np.empty_like(diffs)
    for component in range(components):
        plane = diffs[:, :, component]
        out = np.empty_like(plane)
        out[0, 0] = (seed + int(plane[0, 0])) & mask
        if width > 1:
            out[0, 1:] = (out[0, 0] + np.cumsum(plane[0, 1:], dtype=np.int64)) & mask
        for y in range(1, height):
            out[y, 0] = (int(out[y - 1, 0]) + int(plane[y, 0])) & mask
            if width > 1:
                out[y, 1:] = (out[y, 0] + np.cumsum(plane[y, 1:], dtype=np.int64)) & mask
        raw[:, :, component] = out
    mosaic = raw.reshape(height, width * components)
    info = {'precision': precision, 'sof_wh': [width, height], 'components': components,
            'predictor': predictor, 'point_transform': point, 'samples': int(mosaic.size),
            'mosaic_wh': [width * components, height]}
    return mosaic.astype(np.uint16), info


def _encode_difference(value):
    if value == 0:
        return 0, 0
    if value == -32768:
        return 16, 0
    magnitude = abs(value)
    symbol = magnitude.bit_length()
    bits = value if value > 0 else value + (1 << symbol) - 1
    return symbol, bits


def encode_test_image(planes, precision=8):
    """Build a tiny SOF3 stream. planes is a list of equal 2-D uint arrays."""
    components = len(planes)
    height, width = planes[0].shape
    counts = [0] * 16
    counts[3] = 9  # 4-bit codes for symbols 0..8
    symbols = list(range(9))
    dht = bytes([0x00]) + bytes(counts) + bytes(symbols)
    sof = bytes([precision]) + height.to_bytes(2, 'big') + width.to_bytes(2, 'big') + bytes([components])
    for index in range(components):
        sof += bytes([index, 0x11, 0])
    sos = bytes([components])
    for index in range(components):
        sos += bytes([index, 0x00])
    sos += bytes([1, 0, 0])
    seed = 1 << (precision - 1)
    mask = (1 << precision) - 1
    words = []
    for y in range(height):
        for x in range(width):
            for component, plane in enumerate(planes):
                sample = int(plane[y, x]) & mask
                if y == 0 and x == 0:
                    prediction = seed
                elif y == 0:
                    prediction = int(plane[y, x - 1]) & mask
                elif x == 0:
                    prediction = int(plane[y - 1, 0]) & mask
                else:
                    prediction = int(plane[y, x - 1]) & mask
                diff = (sample - prediction) & mask
                if diff >= (1 << (precision - 1)):
                    diff -= 1 << precision
                symbol, extra = _encode_difference(diff)
                if symbol > 8:
                    raise ValueError('test image needs a category above 8')
                words.append((4, symbol))
                if symbol and symbol != 16:
                    words.append((symbol, extra))
    acc = 0
    bits = 0
    out = bytearray()
    for length, value in words:
        acc = (acc << length) | value
        bits += length
        while bits >= 8:
            bits -= 8
            byte = (acc >> bits) & 255
            out.append(byte)
            if byte == 0xff:
                out.append(0)
    if bits:
        out.append(((acc << (8 - bits)) | ((1 << (8 - bits)) - 1)) & 255)
    def segment(marker, payload):
        return bytes([0xff, marker]) + (len(payload) + 2).to_bytes(2, 'big') + payload
    return b'\xff\xd8' + segment(0xc3, sof) + segment(0xc4, dht) + segment(0xda, sos) + bytes(out) + b'\xff\xd9'


def self_test():
    constant = [np.full((3, 5), 128, np.uint16), np.full((3, 5), 128, np.uint16)]
    decoded, info = decode(encode_test_image(constant))
    if decoded.shape != (3, 10) or not np.all(decoded == 128):
        raise SystemExit(f'constant test failed {decoded}')
    ramp0 = np.arange(18, dtype=np.uint16).reshape(3, 6) + 40
    ramp1 = (np.arange(18, dtype=np.uint16).reshape(3, 6) * 3 + 20) & 255
    decoded, info = decode(encode_test_image([ramp0, ramp1]))
    expect = np.empty((3, 12), np.uint16)
    expect[:, 0::2] = ramp0
    expect[:, 1::2] = ramp1
    if not np.array_equal(decoded, expect):
        raise SystemExit('ramp test failed')
    return {'self_test': 'constant-128 and 3x6 dual-component ramp', 'predictor': info['predictor']}


if __name__ == '__main__':
    print(self_test())
