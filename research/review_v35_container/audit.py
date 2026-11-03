"""Read-only gen 116 review helpers. All writes stay beside this script."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED = {
    'artifacts/downloads/gxr-151.zip': '3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898',
    'artifacts/firmware/gxr-1.51/ilaunch3': 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    'firmware/image_v35/local/package/SD_ROOT/GXRCE.DAT': '1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864',
}
PROTECTED = ('firmware/engine_v37', 'firmware/resident_v35', 'firmware/image_v35',
             'tools/native_harness', 'artifacts/firmware/gxr-1.51')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(name, obj):
    path = HERE / name
    path.resolve().relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def run(argv, label, timeout=300, check=True, cwd=None, env=None):
    logs = HERE / 'logs'
    logs.mkdir(exist_ok=True)
    tmp = HERE / 'tmp'
    tmp.mkdir(exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(tmp), PYTHONDONTWRITEBYTECODE='1',
                       LC_ALL='C', GIT_OPTIONAL_LOCKS='0',
                       CLANG_MODULE_CACHE_PATH=str(tmp / 'modules'),
                       ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                       UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    environment.update(env or {})
    p = subprocess.run([str(x) for x in argv], cwd=cwd or HERE, env=environment,
                       capture_output=True, timeout=timeout)
    (logs / (label + '.stdout')).write_bytes(p.stdout)
    (logs / (label + '.stderr')).write_bytes(p.stderr)
    with (HERE / 'commands.jsonl').open('a') as f:
        f.write(json.dumps(dict(label=label, argv=[str(x) for x in argv],
                               cwd=str(cwd or HERE), returncode=p.returncode)) + '\n')
    if check and p.returncode:
        raise RuntimeError(label + ': ' + p.stderr[-1500:].decode(errors='replace'))
    return p

def preflight():
    info = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['FilesystemType'] == 'apfs' and info['WritableVolume'] and info['WritableMedia']
    assert HERE == ROOT / 'research/review_v35_container'
    for path, digest in EXPECTED.items():
        assert sha(ROOT / path) == digest, path
    dump('identity.json', {p: dict(sha256=sha(ROOT / p), bytes=(ROOT / p).stat().st_size) for p in EXPECTED})
    before = {str(p.relative_to(ROOT)): sha(p) for rel in PROTECTED
              for p in sorted((ROOT / rel).rglob('*')) if p.is_file() and not p.is_symlink()}
    before.update({p: sha(ROOT / p) for p in EXPECTED})
    dump('protected-before.json', before)
    p = run(['git', 'status', '--porcelain=v1', '--untracked-files=no'], 'git-before', cwd=ROOT)
    print('PASS identities; protected files', len(before))

def disassemble():
    raw = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED['artifacts/firmware/gxr-1.51/ilaunch3']
    objdump = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    ranges = [('file_api', 0x200a3e00, 0x200a5c00),
              ('fat_open_write', 0x200aa800, 0x200abe00),
              ('fat_dispatch', 0x200b4800, 0x200b4e00),
              ('fat_lookup_create', 0x200b6200, 0x200b7400),
              ('file_lower', 0x200a5300, 0x200a6b00),
              ('file_open_lower', 0x200aa000, 0x200aad38),
              ('fat_io_lower', 0x200b7400, 0x200b9200),
              ('fat_alloc', 0x200b0000, 0x200b4800),
              ('fat_meta', 0x200b9200, 0x200ba400),
              ('file_lookup', 0x200a6b00, 0x200aa000),
              ('file_state', 0x200abe00, 0x200afb00)]
    evidence = []
    for name, start, end in ranges:
        out = HERE / 'native' / name
        out.parent.mkdir(exist_ok=True)
        data = raw[start - 0x2004ae00:end - 0x2004ae00]
        out.with_suffix('.bin').write_bytes(data)
        p = run([objdump, '-D', '-EB', '-b', 'binary', '-m', 'm32r',
                 '--adjust-vma=' + hex(start), out.with_suffix('.bin')], 'disasm-' + name)
        out.with_suffix('.txt').write_bytes(p.stdout)
        evidence.append(dict(name=name, vma_start=hex(start), vma_end=hex(end),
                             file_offset=hex(start - 0x2004ae00), sha256=sha(out.with_suffix('.bin'))))
    dump('native/ranges.json', evidence)
    print('PASS fresh official disassembly', len(ranges))

def verify_protected():
    before = json.loads((HERE / 'protected-before.json').read_text())
    changes = [{ 'path': p, 'before': h, 'after': sha(ROOT / p) if (ROOT / p).is_file() else None}
               for p, h in before.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    dump('protected-after.json', dict(files=len(before), changed=changes))
    print('protected changes', len(changes))
    return changes

if __name__ == '__main__':
    {'preflight': preflight, 'disasm': disassemble, 'check': verify_protected}[sys.argv[1]]()
