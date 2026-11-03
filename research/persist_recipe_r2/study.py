"""Retain bounded offline firmware evidence within this study."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local'
sys.path.append(str(ROOT / 'research/persist_recipe'))
from collect import Image, OBJDUMP, sha


def save(name, value):
    assert re.fullmatch(r'[A-Za-z0-9_.-]+', name)
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def tree_hash(folder):
    state = hashlib.sha256()
    count = 0
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or any(part in ('local', '__pycache__')
                                     for part in path.relative_to(folder).parts):
            continue
        state.update(str(path.relative_to(folder)).encode() + b'\0')
        state.update(bytes.fromhex(sha(path)))
        count += 1
    return dict(files=count, sha256=state.hexdigest())


def inputs():
    folders = ('firmware/engine_v53_g135/candidate', 'firmware/resident_v37',
               'tools/gxr_emulator', 'research/persist_recipe')
    result = {rel: tree_hash(ROOT / rel) for rel in folders}
    files = ('artifacts/firmware/gxr-1.51/ilaunch3',
             'artifacts/downloads/gxr-151.zip',
             'firmware/package_v37_g135/local/SD_ROOT/ilaunch3',
             'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT',
             'tools/gxr_emulator/build/libgxr_m32r.dylib')
    result.update({rel: dict(size=(ROOT/rel).stat().st_size, sha256=sha(ROOT/rel))
                   for rel in files})
    return result


def window(label, start, end):
    assert re.fullmatch(r'[a-z0-9_-]+', label)
    im = Image()
    raw = im.raw(start, end-start)
    target = OUT / (label + '.bin')
    target.write_bytes(raw)
    assembly = subprocess.check_output([str(OBJDUMP), '-D', '-b', 'binary', '-m',
        'm32r', '-EB', '--adjust-vma='+hex(start), str(target)], text=True)
    (OUT / (label + '.asm.txt')).write_text(assembly)
    other = (ROOT/'firmware/package_v37_g135/local/SD_ROOT/ilaunch3').read_bytes()
    at = im.offset(start, len(raw))
    meta = dict(start=hex(start), end=hex(end), file=hex(at), size=len(raw),
                sha256=sha(target), current_body_equal=raw == other[at:at+len(raw)])
    save(label + '.meta.json', meta)
    print(json.dumps(meta))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('before', 'after', 'window', 'refs'))
    parser.add_argument('rest', nargs='*')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.action == 'before':
        assert not (OUT/'inputs-before.json').exists()
        save('inputs-before.json', inputs())
        denied = False
        try:
            (ROOT/'research/.r2-scope-check').write_text('check\n')
        except PermissionError:
            denied = True
        assert denied
        save('scope-check.json', dict(outside_write_denied=denied,
             output='research/persist_recipe_r2', network_denied=True))
        print('Input hashes recorded; write boundary checked.')
    elif args.action == 'after':
        old = json.loads((OUT/'inputs-before.json').read_text())
        now = inputs()
        changed = [key for key in old if old[key] != now.get(key)]
        save('inputs-after.json', dict(equal=not changed, changed=changed,
                                     trees_and_files=len(now)))
        assert not changed
        print('Protected input hashes remain equal.')
    elif args.action == 'window':
        window(args.rest[0], int(args.rest[1], 0), int(args.rest[2], 0))
    else:
        targets = {int(item, 0) for item in args.rest}
        rows = []
        for address, raw, code, source, line in Image().instructions():
            for part, item in enumerate(re.split(r' -> | \|\| ', code)):
                match = re.match(r'(b\w*|ld24)\s+(?:r\d+,)?(?:r\d+,)?(?:0x)?([0-9a-f]+)', item)
                if match and int(match[2], 16) in targets:
                    rows.append(dict(address=hex(address+2*part), code=item,
                                     source=source, line=line))
        save('refs.json', dict(targets=[hex(item) for item in sorted(targets)], rows=rows))
        print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
