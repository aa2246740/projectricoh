"""Verify the complete package and retained seventh section."""
from pathlib import Path
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'research/g131_merge'
ENGINE = ROOT / 'firmware/engine_v51_g131'
PACKAGE = ROOT / 'firmware/package_v36_g131'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    dat = PACKAGE / 'local/SD_ROOT/GXRCE.DAT'
    assert (PACKAGE / 'SD_ROOT').is_symlink()
    assert (PACKAGE / 'SD_ROOT').readlink() == Path('local/SD_ROOT')
    assert (PACKAGE / 'SD_ROOT').resolve() == (PACKAGE / 'local/SD_ROOT').resolve()
    raw = dat.read_bytes()
    full = ENGINE / 'candidate/local/full-r13'
    assert (full / 'GXRCE.DAT').read_bytes() == raw
    binary = (full / 'engine.bin').read_bytes()
    assert raw.count(binary) == 1
    codegen_path = WORK / 'evidence/codegen-four-categories.json'
    if codegen_path.exists():
        codegen = json.loads(codegen_path.read_text())
        assert codegen['dat_sha256'] == sha(dat)
        assert codegen['elf_sha256'] == sha(full / 'engine.elf')
    previous = (ROOT / 'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()
    assert int.from_bytes(raw[28:32], 'big') == 131
    offset, length = struct.unpack_from('>II', raw, 132 + 6 * 12)
    old_offset, old_length = struct.unpack_from('>II', previous, 132 + 6 * 12)
    assert length == old_length == 20776
    assert raw[offset:offset + length] == previous[old_offset:old_offset + length]
    manifest = json.loads((ENGINE / 'candidate/local/full-r13/manifest.json').read_text())
    bss = int.from_bytes(raw[116:120], 'big')
    request = 7504 + ((len(raw) + bss + 3) & ~3)
    assert manifest['loader_request'] == request and request <= 108124
    files = sorted((PACKAGE / 'local/SD_ROOT').iterdir())
    assert len(files) == 30
    fixed = [p for p in files if p.name != 'GXRCE.DAT']
    assert len(fixed) == 29
    for path in fixed:
        assert sha(path) == sha(ROOT / 'firmware/package_v36_g120b/SD_ROOT' / path.name)
    result = dict(generation=131, dat_sha256=sha(dat), dat_bytes=len(raw),
                  seventh_section_bytes=length, seventh_section_equal_g129=True,
                  components=[1408, 1984, 17384], files=30, fixed_files_equal_g120b=29,
                  bss_bytes=bss, loader_request=request, loader_request_limit=108124)
    (WORK / 'evidence/delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(name='delivery', returncode=0, counts=result)))

if __name__ == '__main__':
    main()
