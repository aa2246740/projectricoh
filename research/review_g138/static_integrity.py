"""Bind the reviewed code, package, lock reference and size to this DAT."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BUILD = ROOT / 'firmware/engine_v55_g138/candidate/local/full-r13'
PACKAGE = ROOT / 'firmware/package_v38_g138/SD_ROOT'
PREVIOUS = ROOT / 'firmware/package_v38_g137/SD_ROOT'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def elf_sections(path):
    data = path.read_bytes()
    header = struct.unpack_from('>16sHHIIIIIHHHHHH', data)
    assert data[:6] == b'\x7fELF\x01\x02'
    sections = [struct.unpack_from('>10I', data, header[6] + i * header[11])
                for i in range(header[12])]
    names_header = sections[header[13]]
    names = data[names_header[4]:names_header[4] + names_header[5]]
    result = {}
    for section in sections:
        name = names[section[0]:].split(b'\0', 1)[0].decode()
        result[name] = dict(base=section[3], bytes=section[5], type=section[1],
                            data=data[section[4]:section[4] + section[5]])
    return result


def body_at(data, address, size):
    for index in range(16):
        source, base, count, _, _ = struct.unpack_from('>5I', data, 0x20 + index * 20)
        if base <= address and address + size <= base + count:
            offset = source + 0x200 + address - base
            return data[offset:offset + size]
    raise AssertionError(('address is not initialized', address, size))


dat = (PACKAGE / 'GXRCE.DAT').read_bytes()
old = (PREVIOUS / 'GXRCE.DAT').read_bytes()
elf = elf_sections(BUILD / 'engine.elf')
engine, bss = elf['.engine'], elf['.bss']
assert dat[engine['base']:engine['base'] + engine['bytes']] == engine['data']
assert bss['base'] == len(dat) and bss['type'] == 8
assert bss['bytes'] == struct.unpack_from('>I', dat, 116)[0] == 9124
assert len(dat) == 91432 and struct.unpack_from('>I', dat, 28)[0] == 138
assert sha(dat) == '88a4359b284ba5a9765a3dfb1177679ec4c4da0687d9f9a6fb3d31fe19acb02a'
header = bytearray(dat[:256])
header[20:24] = bytes(4)
assert zlib.crc32(header) & 0xffffffff == struct.unpack_from('>I', dat, 20)[0]
assert zlib.crc32(dat[256:]) & 0xffffffff == struct.unpack_from('>I', dat, 24)[0]
layout = json.loads((BUILD / 'layout.json').read_text())
checked = {}
for kind in ('sources', 'headers'):
    checked[kind] = len(layout[kind])
    for path, digest in layout[kind].items():
        assert sha((ROOT / path).read_bytes()) == digest, path
sections_equal = []
for index in range(1, 7):
    start, count = struct.unpack_from('>II', dat, 132 + index * 12)
    old_start, old_count = struct.unpack_from('>II', old, 132 + index * 12)
    assert count == old_count
    if dat[start:start + count] == old[old_start:old_start + old_count]:
        sections_equal.append(index + 1)
assert sections_equal == [4, 6, 7]
source_diff = subprocess.run(['/usr/bin/diff', '-ru', '-x', 'local', '-x', '__pycache__',
                              str(ROOT / 'firmware/engine_v54_g137/candidate'),
                              str(ROOT / 'firmware/engine_v55_g138/candidate')],
                             capture_output=True, text=True, timeout=120)
assert source_diff.returncode in (0, 1), source_diff.stderr
abi_diff = subprocess.run(['/usr/bin/diff', '-u',
                           str(ROOT / 'firmware/engine_v54_g137/resident/abi.h'),
                           str(ROOT / 'firmware/engine_v55_g138/resident/abi.h')],
                          capture_output=True, text=True, timeout=120)
assert abi_diff.returncode in (0, 1), abi_diff.stderr
source_diff_text = source_diff.stdout + abi_diff.stdout
(OUT / 'local/source-diff.txt').write_text(source_diff_text)


def diff_hunks(value):
    value = value.replace(str(ROOT / 'firmware') + '/', '')
    return '\n'.join(line for line in value.splitlines()
                     if not line.startswith(('diff -', '--- ', '+++ ')))


assert diff_hunks(source_diff_text) == diff_hunks((ROOT / 'research/g138_persist/source-diff.txt').read_text()), 'supplied source diff does not match current source trees'
body = (PACKAGE / 'ilaunch3').read_bytes()
reference = (ROOT / 'research/persist_recipe_r2/local/lock-core.bin').read_bytes()
assert body_at(body, 0x20060b84, len(reference)) == reference
original = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
assert body_at(original, 0x20060b84, len(reference)) == reference
assert body_at(body, 0x20067b2c, 64) == body_at(original, 0x20067b2c, 64)
differences = [p.name for p in PACKAGE.iterdir() if p.read_bytes() != (PREVIOUS / p.name).read_bytes()]
assert differences == ['GXRCE.DAT']
ui = struct.unpack_from('>I', dat, 204)[0] + 1408
user_count = struct.unpack_from('>H', dat, ui + 24)[0]
assert user_count == 0
fixture_path = OUT / 'local/users-fixture/GXRCE.DAT'
fixture = fixture_path.read_bytes()
fixture_ui = struct.unpack_from('>I', fixture, 204)[0] + 1408
assert struct.unpack_from('>H', fixture, fixture_ui + 24)[0] == 32
for index in range(6):
    start, count = struct.unpack_from('>II', dat, 132 + index * 12)
    assert fixture[start:start+count] == dat[start:start+count]
fixture_header = bytearray(fixture[:256])
fixture_header[20:28] = dat[20:28]
assert fixture_header == dat[:256]
main = 7504 + ((len(dat) + bss['bytes'] + 3) & ~3)
assert main == 108060 <= 108124
result = dict(status='PASS_STATIC', dat_sha256=sha(dat), engine_elf_sha256=sha((BUILD / 'engine.elf').read_bytes()),
              code_matches_elf=True, checked_compilation_inputs=checked,
              unchanged_data_sections=sections_equal, package_changed_files=differences,
              source_diff_matches_supplied=True, source_diff_sha256=sha(source_diff_text.encode()),
              source_diff_scope=['candidate excluding local and __pycache__', 'resident/abi.h'],
              published_user_entries=user_count, fixture_user_entries=32,
              users_fixture_sha256=sha(fixture), fixture_first_six_sections_equal=True,
              main_request=main, design_margin=108124-main,
              lock_reference=dict(address='0x20060b84', bytes=len(reference), sha256=sha(reference),
                                  current_body_equal=True, original_body_equal=True,
                                  initialization_caller_equal_to_original=True),
              heap=dict(main_request_delta=-64, inherited_three_leak_remaining=53096,
                        inherited_later_request=77336, closes_inherited_risk=False))
(OUT / 'evidence/static-integrity.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
