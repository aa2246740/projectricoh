"""Check final envelope bytes, linked BSS placement and fixed package contents."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'research/v39_g153'))
from dat_format import sections, strict_effects


def main():
    rows = []
    code = []
    for test, build in [(False, 'boot-off'), (True, 'boot-on')]:
        package = ROOT/'firmware'/('package_v310_g155c_test' if test else 'package_v310_g155c')
        assert {p.name for p in package.iterdir()} == {'GXRCE.DAT', 'MANIFEST'}
        manifest = json.loads((package/'MANIFEST').read_text())
        raw = (package/'GXRCE.DAT').read_bytes()
        directory = sections(raw)
        strict_effects(raw)
        build_root = ROOT/'firmware/engine_v67_g155c/candidate/local'/build
        layout = json.loads((build_root/'layout.json').read_text())
        engine = (build_root/'engine.bin').read_bytes()
        offset, n = directory[0]
        assert raw[offset:offset+n] == engine
        assert manifest['boot'] == int(test) and len(engine) == manifest['code_bytes'] <= 69632
        assert layout['pic_translation_verified'] and layout['file_bytes'] == len(raw)
        elf = build_root/'engine.elf'
        tool = str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump')
        listing = subprocess.check_output([tool, '-h', str(elf)], text=True)
        match = re.search(r'\s+\d+ \.bss\s+([0-9a-f]+)\s+([0-9a-f]+)', listing)
        assert match and int(match[1],16) == manifest['bss_bytes'] and int(match[2],16) == len(raw)
        relocation_listing = subprocess.check_output([tool, '-r', str(elf)], text=True)
        kinds = Counter(re.findall(r'R_M32R_[A-Z0-9_]+', relocation_listing))
        assert sum(n for kind,n in kinds.items() if kind.startswith('R_M32R_GOTOFF_')) > 0
        assert kinds['R_M32R_GOTOFF_HI_SLO'] > 0
        start, count_bytes = directory[1]
        count = struct.unpack_from('>H', raw, 120)[0]
        assert count_bytes == count*8
        for index in range(count):
            patch, target = struct.unpack_from('>II', raw, start+8*index)
            assert struct.unpack_from('>I', raw, patch)[0] == target < len(raw)+manifest['bss_bytes']
        total = 7628+((len(raw)+manifest['bss_bytes']+3)&~3)
        assert total == manifest['main_request'] <= 107612
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == manifest['dat_sha256']
        code.append(engine)
        rows.append(dict(profile='test' if test else 'release', sha256=digest, DAT_bytes=len(raw),
            code_bytes=n, code_headroom=69632-n, bss_bytes=manifest['bss_bytes'], bss_address=len(raw),
            main_bytes=total, main_headroom=107612-total, ordinary_relocations=count,
            ELF_relocation_counts=dict(kinds), pic_translation_verified=True, users=manifest['users']))
    target = HERE/'evidence/artifact-audit.json'
    target.write_text(json.dumps(dict(status='PASS', layer='静态', rows=rows,
        release_test_engine_bytes_equal=code[0]==code[1],
        engine_sha256=[hashlib.sha256(v).hexdigest() for v in code]), indent=2)+'\n')
    print(json.dumps(dict(status='PASS', rows=rows)))


if __name__ == '__main__':
    main()
