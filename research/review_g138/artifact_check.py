"""Static artifact check for package_v38_g138 (gen 138 DAT + unchanged v3.8 body).

Same checks as research/emptystack_v38/artifact_check.py, retargeted: the body
must be byte-identical to package_v38_g137's, and the DAT must stay within the
108,124 B main-request budget. Output: research/review_g138/artifact-results.json.
/usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / 'firmware/package_v38_g138/SD_ROOT'
PREVIOUS = ROOT / 'firmware/package_v38_g137/SD_ROOT'
BUILT = ROOT / 'firmware/engine_v55_g138/candidate/local/full-r13'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
LIMIT = 108124


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    files = sorted(PACKAGE.iterdir())
    assert len(files) == 30 and all(p.is_file() for p in files)
    body = (PACKAGE / 'ilaunch3').read_bytes()
    assert sha(PACKAGE / 'ilaunch3') == BODY_SHA and body == (PREVIOUS / 'ilaunch3').read_bytes()
    checksum = sum(sum(body[0x200 + k::6]) * (k + 2) for k in range(6)) & 0xffffffff
    assert checksum == struct.unpack_from('>I', body, 0x16c)[0]
    legacy = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'g138_artifact_elf')
    elf_path = ROOT / 'firmware/resident_v38/local/resident/build/resident.elf'
    elf = legacy.Elf(elf_path)
    section = next(x for x in elf.sections if x['name'] == '.resident')
    offset = lambda address: address - 0x2004b000 + 0x200
    content = elf.content(section)
    assert body[offset(section['va']):offset(section['va']) + len(content)] == content
    margin = 0x20054700 - section['va'] - len(content)
    fixed = [p.name for p in files if p.name != 'GXRCE.DAT']
    assert len(fixed) == 29 and all((PACKAGE / n).read_bytes() == (PREVIOUS / n).read_bytes() for n in fixed)
    dat = (PACKAGE / 'GXRCE.DAT').read_bytes()
    assert dat == (BUILT / 'GXRCE.DAT').read_bytes()
    layout = json.loads((BUILT / 'layout.json').read_text())
    request = 7504 + ((len(dat) + layout['bss_bytes'] + 3) & ~3)
    assert request <= LIMIT, request
    sections = [struct.unpack_from('>II', dat, 132 + 12 * i) for i in range(7)]
    assert sections[6][1] == 20776 and struct.unpack_from('>I', dat, 28)[0] == 138
    assert len(dat) <= 98304 and len(dat) + layout['bss_bytes'] <= 114688
    trust = json.loads((ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
    assert dat[80:112].hex() == trust['resident_build_id'] and dat[212:228].hex() == trust['resident_abi_id']
    header = bytearray(dat[:256]); header[20:24] = bytes(4)
    import zlib
    assert struct.unpack_from('>I', dat, 20)[0] == zlib.crc32(header) & 0xffffffff
    assert struct.unpack_from('>I', dat, 24)[0] == zlib.crc32(dat[256:]) & 0xffffffff
    result = dict(status='PASS_STATIC', files=30, fixed_equal_to_v38_g137=29, body_sha256=BODY_SHA,
                  dat_sha256=sha(PACKAGE / 'GXRCE.DAT'), dat_bytes=len(dat), bss_bytes=layout['bss_bytes'],
                  engine_bytes=layout['engine_bytes'], main_request=request, main_limit=LIMIT,
                  design_margin=LIMIT - request, resident_bytes=len(content), resident_margin=margin,
                  body_checksum=f'{checksum:08x}', generation=138, resident_build_id=trust['resident_build_id'])
    (HERE / 'artifact-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
