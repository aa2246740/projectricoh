"""Decode the per-unit recipe model (records, entries, refs, ranges) from a gen 13x/14x GXRCE.DAT.

Same reader as firmware/engine_v53_g135/candidate/build135.py model(), with the source path as a parameter.
Read-only. /usr/bin/python3 -I -B.
"""
from pathlib import Path
import importlib.util
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'firmware/engine_v53_g135/candidate/containers/product/pack.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pack = load(PACK, 'g139m_decode_pack')
ROW_NAMES = ('A5', 'B5', 'C080', 'C100', 'A20', 'B20', 'C', 'D', 'A14', 'B14')


def modules(raw):
    u16, u32 = pack.u16, pack.u32
    shared = u32(raw, 192); out = []
    for mi, name in enumerate(pack.NAMES):
        d = raw[u32(raw, 156) + 64 * mi:u32(raw, 156) + 64 * (mi + 1)]
        mapping = raw[u32(d, 12):u32(d, 12) + 152]
        records = [raw[u32(d, 16) + 32 + 64 * i:u32(d, 16) + 96 + 64 * i] for i in range(16)]
        table = u32(d, 20); entries = {}; owners = []
        for i in range(d[30]):
            desc = raw[table + 16 + 20 * i:table + 36 + 20 * i]; slot = desc[0]; owners.append(slot)
            entry = bytearray(552); entry[:2] = desc[:2]; entry[4:8] = desc[4:8]; entry[445:447] = desc[2:4]
            for off, size, kind, index in zip(pack.OFFSETS, pack.ROW_BYTES, pack.KINDS, desc[8:18]):
                pool = shared + 16 + 12 * kind; assert u16(raw, pool + 2) == size
                at = shared + u32(raw, pool + 4) + index * size; entry[off:off + size] = raw[at:at + size]
            for off, size, crc_off in ((20, 62, 8), (82, 33, 12), (115, 96, 16), (216, 56, 212), (284, 62, 272),
                                       (346, 33, 276), (379, 66, 280), (456, 62, 448), (518, 33, 452)):
                pack.p32(entry, crc_off, pack.crc(entry[off:off + size]))
            entries[slot] = bytes(entry)
        refs = []; ranges = []
        for i in range(16):
            meta = raw[u32(d, 24) + 28 * i:u32(d, 24) + 28 * (i + 1)]; refs.append(owners[meta[24]])
            ranges.append([struct.unpack('bbb', meta[3 * j:3 * j + 3]) for j in range(8)])
        stock = entries[4]
        raw_stock = b''.join(stock[off:off + size] for off, size in zip(pack.OFFSETS, pack.ROW_BYTES)) + stock[445:447]
        pin = pack.crc(mapping + raw_stock); assert pin == pack.PIN_CRC32[mi] and u32(d, 32) == pin
        out.append(dict(name=name, map=mapping, records=records, entries=entries, refs=refs, ranges=ranges,
                        raw_stock=raw_stock, entry=stock, crc_pin=pin, pin=d[32:64]))
    return out


def rows(entry):
    return {n: entry[o:o + s] for n, o, s in zip(ROW_NAMES, pack.OFFSETS, pack.ROW_BYTES)}


def control(entry):
    return pack.u16(entry, 445)
