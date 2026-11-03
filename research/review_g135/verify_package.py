"""Independent identity/format check of the gen 135 package (read-only; writes only package-check.json in this directory)."""
from pathlib import Path
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
PKG = ROOT / 'firmware/package_v37_g135/local/SD_ROOT'
sha = lambda b: hashlib.sha256(b).hexdigest()
u32 = lambda b, o: struct.unpack_from('>I', b, o)[0]
u16 = lambda b, o: struct.unpack_from('>H', b, o)[0]

def sections(blob):
    return [(u32(blob, 132 + 12 * i), u32(blob, 136 + 12 * i)) for i in range(7)]

def check(blob, label):
    h = blob[:256]
    z = bytearray(h); z[20:24] = bytes(4)
    out = dict(label=label, bytes=len(blob), sha256=sha(blob), magic=h[:8].decode(), generation=u32(h, 28),
               length_field_ok=u32(h, 16) == len(blob),
               header_crc_ok=u32(h, 20) == zlib.crc32(bytes(z)) & 0xffffffff,
               body_crc_ok=u32(h, 24) == zlib.crc32(blob[256:]) & 0xffffffff,
               source_hash=h[48:80].hex(), resident_id=h[80:112].hex(), entry=u32(h, 112), bss=u32(h, 116),
               abi_id=h[212:228].hex(), sections=[])
    for i, (start, length) in enumerate(sections(blob)):
        out['sections'].append(dict(index=i, start=start, length=length, sha256=sha(blob[256 + start:256 + start + length]) if 256 + start + length <= len(blob) else None))
    return out

def main():
    dat = (PKG / 'GXRCE.DAT').read_bytes()
    old = (ROOT / 'firmware/package_v36_g131/local/SD_ROOT/GXRCE.DAT').read_bytes()
    now, before = check(dat, 'g135'), check(old, 'g131')
    trust = json.loads((ROOT / 'firmware/resident_v37/local/resident/trust.json').read_text())
    result = dict(g135=now, g131=before)
    result['resident_id_matches_v37_trust'] = now['resident_id'] == trust['resident_build_id']
    result['abi_matches_v37_trust'] = now['abi_id'] == trust['resident_abi_id']
    result['section_equal_to_g131'] = [a['sha256'] == b['sha256'] for a, b in zip(now['sections'], before['sections'])]
    result['header_bytes_different'] = sum(x != y for x, y in zip(dat[:256], old[:256]))
    # main request: loader.c budget = 1104 + align4(dat + bss) + 6144 + 256
    request = 1104 + ((len(dat) + now['bss'] + 3) // 4) * 4 + 6144 + 256
    result['main_request'] = request
    result['main_request_limit'] = 108124
    result['main_request_headroom'] = 108124 - request
    sums = {}
    for line in (ROOT / 'firmware/package_v37_g135/CARD_SHA256SUMS').read_text().splitlines():
        digest, name = line.split(None, 1)
        sums[name.strip()] = digest
    files = sorted(p.name for p in PKG.iterdir() if p.is_file())
    result['files'] = len(files)
    result['card_sums_ok'] = all(sha((PKG / n).read_bytes()) == sums.get(n) for n in files) and set(files) == set(sums)
    g120 = ROOT / 'firmware/package_v36_g120b/SD_ROOT'
    equal = [n for n in files if (g120 / n).is_file() and (g120 / n).read_bytes() == (PKG / n).read_bytes()]
    result['equal_to_g120b'] = len(equal)
    result['differs_from_g120b'] = [n for n in files if n not in equal]
    result['ilaunch3_equals_package_v37_redisplay'] = None
    redis = ROOT / 'firmware/package_v37_redisplay/SD_ROOT/ilaunch3'
    if redis.is_file():
        result['ilaunch3_equals_package_v37_redisplay'] = redis.read_bytes() == (PKG / 'ilaunch3').read_bytes()
    (WORK / 'package-check.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('g135', 'g131')}, indent=1))

if __name__ == '__main__':
    main()
