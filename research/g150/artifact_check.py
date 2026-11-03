"""Static artifact check for the g150 release and test packages.

- body: ilaunch3 d4fa3b46 and all 29 non-DAT files byte-identical to package_v38_g137;
  the resident ELF content is present in the body at its section address;
- release DAT == the build output, generation 150, 0 user entries, both CRCs valid;
- test DAT differs from the release only in the 1984-byte user extension and the two
  header CRC words, and carries >= 1 user entry;
- main request <= 106,124 B (108,124 budget minus the 2,000 B reserved for 28mm);
- the engine tree's resident/ is byte-identical to firmware/resident_v38/resident;
- new UI copy is 1..8 printable ASCII and present in the engine image.
Output: research/g150/artifact-results.json. /usr/bin/python3 -I -B.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RELEASE = ROOT / 'firmware/package_v38_g150'
TEST = ROOT / 'firmware/package_v38_g150_test'
PREVIOUS = ROOT / 'firmware/package_v38_g137/SD_ROOT'
ENGINE = ROOT / 'firmware/engine_v58_g150'
BUILT = ENGINE / 'candidate/local/full-r13'
BODY_SHA = 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'
LIMIT, BUDGET = 106124, 108124
COPY = ('>Unsaved', ' Error', 'Default', 'Sure?', '--------')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def crcs_ok(dat):
    header = bytearray(dat[:256]); header[20:24] = bytes(4)
    return (struct.unpack_from('>I', dat, 20)[0] == zlib.crc32(header) & 0xffffffff and
            struct.unpack_from('>I', dat, 24)[0] == zlib.crc32(dat[256:]) & 0xffffffff)


def sealed(package):
    sums = dict(reversed(line.split('  ', 1)) for line in (package / 'SHA256SUMS').read_text().splitlines())
    files = sorted((package / 'SD_ROOT').iterdir())
    assert len(files) == 30 and all(p.is_file() for p in files)
    for p in files:
        assert sums[str((package / 'local/SD_ROOT' / p.name).relative_to(ROOT))] == sha(p), p
    fixed = [p.name for p in files if p.name != 'GXRCE.DAT']
    assert len(fixed) == 29 and all((package / 'SD_ROOT' / n).read_bytes() == (PREVIOUS / n).read_bytes() for n in fixed)
    assert sha(package / 'SD_ROOT/ilaunch3') == BODY_SHA
    return (package / 'SD_ROOT/GXRCE.DAT').read_bytes()


def main():
    body = (RELEASE / 'SD_ROOT/ilaunch3').read_bytes()
    checksum = sum(sum(body[0x200 + k::6]) * (k + 2) for k in range(6)) & 0xffffffff
    assert checksum == struct.unpack_from('>I', body, 0x16c)[0]
    legacy = load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'g150_artifact_elf')
    elf = legacy.Elf(ROOT / 'firmware/resident_v38/local/resident/build/resident.elf')
    section = next(x for x in elf.sections if x['name'] == '.resident')
    content = elf.content(section)
    at = section['va'] - 0x2004b000 + 0x200
    assert body[at:at + len(content)] == content
    margin = 0x20054700 - section['va'] - len(content)
    copies = sorted((ENGINE / 'resident').iterdir())
    assert all((ROOT / 'firmware/resident_v38/resident' / p.name).read_bytes() == p.read_bytes() for p in copies)

    release, test = sealed(RELEASE), sealed(TEST)
    assert release == (BUILT / 'GXRCE.DAT').read_bytes() and crcs_ok(release) and crcs_ok(test)
    assert struct.unpack_from('>I', release, 28)[0] == 150 and len(release) <= 98304
    layout = json.loads((BUILT / 'layout.json').read_text())
    request = 7504 + ((len(release) + layout['bss_bytes'] + 3) & ~3)
    assert request <= LIMIT, request
    cli = load(ENGINE / 'candidate/user_entries.py', 'g150_users')
    ext_at, _, release_users = cli.parse(release)
    _, _, test_users = cli.parse(test)
    assert release_users == [] and len(test_users) >= 1 and len(test) == len(release)
    changed = [i for i in range(len(release)) if release[i] != test[i]]
    assert changed and all(20 <= i < 28 or ext_at <= i < ext_at + cli.gxui.EXT_BYTES for i in changed)
    trust = json.loads((ROOT / 'firmware/resident_v38/local/resident/trust.json').read_text())
    assert release[80:112].hex() == trust['resident_build_id'] and release[212:228].hex() == trust['resident_abi_id']

    image = (BUILT / 'engine.bin').read_bytes()
    copy = {}
    for text in COPY:
        assert 1 <= len(text) <= 8 and all(32 <= ord(c) <= 126 for c in text), text
        copy[text] = text.encode() in image
    assert copy['>Unsaved'] and copy[' Error']
    result = dict(status='PASS_STATIC', body_sha256=BODY_SHA, body_checksum=f'{checksum:08x}',
                  fixed_equal_to_v38_g137=29, resident_bytes=len(content), resident_margin=margin,
                  engine_resident_copy_canonical=True, release_dat_sha256=sha(RELEASE / 'SD_ROOT/GXRCE.DAT'),
                  test_dat_sha256=sha(TEST / 'SD_ROOT/GXRCE.DAT'), dat_bytes=len(release), bss_bytes=layout['bss_bytes'],
                  engine_bytes=layout['engine_bytes'], main_request=request, main_limit=LIMIT, design_budget=BUDGET,
                  margin_to_limit=LIMIT - request, margin_to_budget=BUDGET - request, generation=150,
                  release_user_entries=0, test_user_entries=[u['name'] for u in test_users],
                  test_changed_bytes=len(changed), copy_in_image=copy)
    (HERE / 'artifact-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
