"""核对最终 DAT、源码增量、原生区间和历史模拟器结果。"""
from pathlib import Path
import hashlib
import json
import re
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()
ROOT, OUT = scope.ROOT, scope.HERE
TREE = ROOT / 'firmware/engine_diag_v38_g145'
BUILD = TREE / 'candidate/local/full-r1'
DAT = ROOT / 'firmware/package_v38_diag145/SD_ROOT/GXRCE.DAT'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
listing = scope.load(ROOT / 'research/unit28_stock/m32r_listing.py', 'review145_listing')

def dis(raw, start, end):
    tmp = scope.SCRATCH / ('dis-%x.bin' % start)
    tmp.write_bytes(listing.read(raw, start, end - start))
    p = subprocess.run([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r2', '-EB',
                        '--adjust-vma=%#x' % start, str(tmp)], capture_output=True,
                       text=True, check=True, timeout=4200)
    tmp.unlink()
    return p.stdout

def main():
    static = scope.load(ROOT / 'research/unit28_stock/static_check.py', 'review145_static')
    static.HERE = OUT
    sys.argv = ['static_check.py', '145']
    static.main()
    dat = DAT.read_bytes()
    assert scope.sha(DAT) == '222ccf4b4f7975bc758160e184742631d4f8bf05fed968ce72483071b1a06a2b'
    assert dat == (BUILD / 'GXRCE.DAT').read_bytes()
    assert len(dat) == 29164
    code_at, code_len = struct.unpack_from('>II', dat, 132)
    engine = dat[code_at:code_at + code_len]
    text = subprocess.check_output([str(OBJDUMP), '-d', str(BUILD / 'engine.elf')], text=True)
    (OUT / 'engine-disassembly.txt').write_text(text)
    forbidden = {'create': 0x200a544c, 'create2': 0x200a41ac,
                 'rename': 0x200a49d8, 'delete': 0x200a4910}
    occurrences = {k: [m.start() for m in re.finditer(re.escape(struct.pack('>I', v)), dat)]
                   for k, v in forbidden.items()}
    assert not any(occurrences.values())
    split_immediates = {k: bool(re.search(r'seth r(\d+),#0x200a\s*\|?\|?.{0,150}?or3 r\1,r\1,#0x%x' % (v & 65535), text, re.S))
                        for k, v in forbidden.items()}
    assert not any(split_immediates.values())
    symbols = scope.load(ROOT / 'firmware/stage2l_switch/tools/build.py', 'review145_elf').Elf(BUILD / 'engine.elf').symbols
    trace_functions = {k: {'elf': hex(v['value']), 'DAT': hex(code_at + v['value'] - 256), 'bytes': v['size']}
                       for k, v in symbols.items() if k.startswith('trace_') or k.startswith('dg_file_')}
    body_path = ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
    official_path = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
    body, official = body_path.read_bytes(), official_path.read_bytes()
    regions = {}
    for name, lo, hi in [('file-api', 0x200a3000, 0x200bc000),
                         ('sd-driver', 0x20057000, 0x20060000),
                         ('file-semaphore', 0x0500d418, 0x0500d520),
                         ('kernel-semaphores', 0x05002000, 0x05003000)]:
        b, o = listing.read(body, lo, hi - lo), listing.read(official, lo, hi - lo)
        regions[name] = dict(start=hex(lo), end_exclusive=hex(hi), equal=b == o,
                             sha256=hashlib.sha256(b).hexdigest())
        assert b == o, name
    diffs = [i for i, (a, b) in enumerate(zip(body, official)) if a != b]
    runs = []
    for at in diffs:
        if runs and runs[-1][1] == at:
            runs[-1][1] = at + 1
        else:
            runs.append([at, at + 1])
    for name, lo, hi in [('open',0x200a40b4,0x200a41ac), ('rw-close',0x200a437c,0x200a4910),
                         ('file-core',0x200a5600,0x200a5800), ('constructor',0x20286f80,0x20287200),
                         ('file-semaphore',0x0500d418,0x0500d520),
                         ('kernel-wait',0x05002600,0x05002b00),
                         ('ui-lock',0x2005f100,0x2005f300)]:
        (OUT / ('native-' + name + '.txt')).write_text(dis(body, lo, hi))
    previous = ROOT / 'firmware/engine_diag_v38_g144'
    changes = []
    for p in sorted(TREE.rglob('*')):
        rel = p.relative_to(TREE)
        if not p.is_file() or 'local' in rel.parts or '__pycache__' in rel.parts:
            continue
        q = previous / rel
        if not q.exists() or q.read_bytes() != p.read_bytes():
            changes.append(str(rel))
    p = subprocess.run(['diff','-ru','--exclude=local','--exclude=__pycache__',str(previous),str(TREE)],
                       capture_output=True,text=True,timeout=4200)
    assert p.returncode in (0,1)
    (OUT / 'source-diff.txt').write_text(p.stdout)
    package = ROOT / 'firmware/package_v38_diag145/SD_ROOT'
    package_files = {p.name: dict(bytes=p.stat().st_size, sha256=scope.sha(p)) for p in sorted(package.iterdir())}
    assert set(package_files) == {'GXRCE.DAT','GXRTRACE.BIN'}
    assert package_files['GXRTRACE.BIN']['sha256'] == 'd207116ca69b55ecc91dd5be07ef5441009ee1758c29d953e4b2f333c37c9cae'
    scope.save(OUT / 'static-review.json', dict(package=package_files, code_offset=code_at, code_bytes=code_len,
        engine_sha256=hashlib.sha256(engine).hexdigest(), forbidden_addresses=occurrences,
        forbidden_split_immediates=split_immediates, trace_functions=trace_functions,
        body_sha256=scope.sha(body_path), official_sha256=scope.sha(official_path),
        identical_regions=regions, body_diff_runs=runs, source_changed_files=changes,
        g137_sha256=scope.sha(ROOT / 'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT')))
    print('最终 DAT 静态核对通过', code_len, len(changes))

if __name__ == '__main__':
    main()
