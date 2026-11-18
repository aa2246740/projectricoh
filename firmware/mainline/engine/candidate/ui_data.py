"""GXUI v1: fixed-size ranges and read-only user entries."""
import json
import struct
import zlib

MAGIC = b'GXUI124\0'
LEGACY_BYTES = 1408
CONFIG_BYTES = 48
ENTRY_BYTES = 24
CAPACITY = 32
USER_OFFSET = 64 + 24 * CONFIG_BYTES
EXT_BYTES = USER_OFFSET + CAPACITY * ENTRY_BYTES
KEYS = ('Cont', 'High', 'Shad', 'Satu', 'Fade', 'Warm', 'Tint', 'Splt', 'Filt', 'Tone', 'Amt')
GROUPS = ('GRP', 'GRN', 'HCB', 'STD', 'FCC', 'FCN', 'LCH', 'LVI')
LEGACY_IDS = (1, 3, 4, 2)

def u16(p, at):
    return struct.unpack_from('>H', p, at)[0]

def u32(p, at):
    return struct.unpack_from('>I', p, at)[0]

def crc(p):
    return zlib.crc32(p) & 0xffffffff

def zero_crc(p, at):
    q = bytearray(p)
    q[at:at+4] = bytes(4)
    return crc(q)

def config(modules):
    result = bytearray()
    for mi, module in enumerate(modules):
        for slot in range(1, 9):
            record = bytearray(CONFIG_BYTES)
            order = (1, 2, 3) if slot == 3 else (1, 2, 3, 4)
            record[:4] = bytes((mi, slot, len(order), 0))
            record[4:4+len(order)] = bytes(order)
            for k in range(11):
                domain = (-10, 5, 0) if k == 10 else (-9, 9, 0)
                if k < 4:
                    domain = module['ranges'][slot-1][LEGACY_IDS[k]-1]
                struct.pack_into('bbb', record, 15+3*k, *domain)
            result += record
    return bytes(result)

def make_extension(modules, users=()):
    banks = [b''.join(m['records']) for m in modules]
    return extension(config(modules), banks, users)

def extension(configs, banks, users):
    if len(configs) != 24 * CONFIG_BYTES or len(users) > CAPACITY:
        raise ValueError('invalid config size or more than 32 user entries')
    out = bytearray(EXT_BYTES)
    out[:8] = MAGIC
    struct.pack_into('>HHIIHHHHHH', out, 8, 1, 64, EXT_BYTES, 0,
                     24, CONFIG_BYTES, len(users), ENTRY_BYTES, 11, CAPACITY)
    struct.pack_into('>II', out, 32, 64, USER_OFFSET)
    for i, bank in enumerate(banks):
        struct.pack_into('>I', out, 40+4*i, crc(bank))
    out[64:USER_OFFSET] = configs
    ordinals = [0] * 8
    for i, item in enumerate(users):
        slot = item['base']
        levels = item['levels']
        if not isinstance(slot, int) or isinstance(slot, bool) or not 1 <= slot <= 8 or len(levels) != 11:
            raise ValueError('base must be 1..8 and levels must have 11 entries')
        if any(not isinstance(v, int) or isinstance(v, bool) for v in levels):
            raise ValueError('levels must be integers')
        for mi in range(3):
            c = configs[(mi*8+slot-1)*CONFIG_BYTES:][:CONFIG_BYTES]
            visible = set(c[4:4+c[2]])
            for k, value in enumerate(levels):
                lo, hi, default = struct.unpack_from('bbb', c, 15+3*k)
                if not lo <= value <= hi or (k+1 not in visible and value != default):
                    raise ValueError(f'{KEYS[k]}={value} outside active range for base {slot}, unit {mi}')
        ordinals[slot-1] += 1
        ordinal = ordinals[slot-1]
        mark = '*' if any(levels) else '-'
        name = f'{GROUPS[slot-1]}{mark}{ordinal:03d}'
        at = USER_OFFSET + i*ENTRY_BYTES
        out[at] = slot
        out[at+2:at+10] = name.encode('ascii') + b'\0'
        struct.pack_into('11b', out, at+10, *levels)
        struct.pack_into('>H', out, at+22, ordinal)
    struct.pack_into('>I', out, 16, zero_crc(out, 16))
    return bytes(out)

def read_manifest(text):
    if text.lstrip().startswith(('[', '{')):
        source = json.loads(text)
        source = source['entries'] if isinstance(source, dict) else source
    else:
        source = []
        for line in text.splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            pieces = line.split()
            source.append(dict(base=int(pieces[0]), levels={k: int(v) for k, v in (p.split('=', 1) for p in pieces[1:])}))
    result = []
    if not isinstance(source, list):
        raise ValueError('manifest must be a list or an entries object')
    for row in source:
        if set(row) - {'base', 'levels'}:
            raise ValueError('unknown entry field')
        values = row.get('levels', {})
        if isinstance(values, dict):
            if set(values) - set(KEYS):
                raise ValueError('unknown parameter name')
            values = [values.get(k, 0) for k in KEYS]
        result.append(dict(base=row['base'], levels=values))
    return result
