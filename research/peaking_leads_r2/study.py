#!/usr/bin/env python3
"""Offline evidence collector. All derived data stays in this directory's local/."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
READS = {}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    READS[str(path.relative_to(ROOT))] = digest(data)
    return data


def put(name, value):
    path = LOCAL / name
    assert path.resolve().is_relative_to(LOCAL.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_text(data)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT,
                                   env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}).decode()


def outside_status():
    raw = git('status', '--porcelain=v1', '--untracked-files=all')
    return digest('\n'.join(row for row in raw.splitlines()
                            if 'research/peaking_leads_r2/' not in row).encode())


def load_prior():
    path = ROOT / 'research/peaking_color/analyze.py'
    read(path)
    spec = importlib.util.spec_from_file_location('prior_arithmetic', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.read = read
    return mod


class Image:
    def __init__(self, name):
        self.name = name
        self.data = read(ROOT / 'artifacts/firmware/gxr-1.51' / name)
        self.sections = [(o + 512, v, n) for o, v, n, _, _ in
                         (struct.unpack_from('>IIIII', self.data, 32 + i * 20)
                          for i in range(16))]

    def offset(self, va):
        for off, base, size in self.sections:
            if base <= va < base + size:
                return off + va - base
        raise ValueError(hex(va))

    def bytes(self, va, size):
        off = self.offset(va)
        return self.data[off:off + size]


def listing(name):
    return load_prior().Listing(Image(name))


def window(name, lo, hi, tag):
    lines = listing(name)
    out = []
    for va in sorted(lines.rows):
        if lo <= va < hi:
            size, asm, raw, source, line = lines.get(va)
            out.append(f'{va:08x} file={lines.image.offset(va):#x} {raw.hex(" ")}  {asm}  [{source}:{line}]')
    assert out
    put(f'evidence/{tag}.txt', f'# {name} SHA256 {digest(lines.image.data)}\n' + '\n'.join(out) + '\n')
    return {'path': f'local/evidence/{tag}.txt', 'rows': len(out), 'range': [hex(lo), hex(hi)]}


def freeze():
    paths = [ROOT / 'research/focus_assist', ROOT / 'research/peaking_color',
             ROOT / 'research/peaking_probe', ROOT / 'firmware/peaking_probe',
             ROOT / 'artifacts/firmware/gxr-1.51']
    records = {}
    for base in paths:
        for path in sorted(base.rglob('*')):
            if path.is_file() and not path.is_symlink():
                data = path.read_bytes()
                stat = path.stat()
                records[str(path.relative_to(ROOT))] = {'sha256': digest(data),
                                                       'size': len(data), 'mtime_ns': stat.st_mtime_ns}
    assert not (LOCAL / 'before.json').exists()
    put('before.json', {'head': git('rev-parse', 'HEAD').strip(),
                        'outside_status_sha256': outside_status(), 'files': records})
    print(json.dumps({'frozen_files': len(records)}))


def scan(name, pattern, tag, radius):
    lines = listing(name)
    rows = sorted(lines.rows)
    hits = [va for va in rows if re.search(pattern, lines.rows[va][1], re.I)]
    selected = set()
    for va in hits:
        pos = rows.index(va)
        selected.update(rows[max(0, pos - radius):pos + radius + 1])
    out = []
    for va in sorted(selected):
        size, asm, raw, source, number = lines.get(va)
        out.append(f'{va:08x} file={lines.image.offset(va):#x} {raw.hex(" ")}  {asm}')
    put(f'scans/{tag}.txt', f'# {name} SHA256 {digest(lines.image.data)}\n' + '\n'.join(out) + '\n')
    print(json.dumps({'hits': len(hits), 'rows': len(out), 'path': f'local/scans/{tag}.txt'}))


def audit():
    before = json.loads((LOCAL / 'before.json').read_text())
    changed = []
    for rel, record in before['files'].items():
        path = ROOT / rel
        if not path.is_file() or digest(path.read_bytes()) != record['sha256']:
            changed.append(rel)
    official = []
    for row in read(ROOT / 'research/focus_assist/official-inputs.before.sha256').decode().splitlines():
        expected, rel = row.split(None, 1)
        assert digest(read(ROOT / rel)) == expected, rel
        official.append(rel)
    used = json.loads((LOCAL / 'reads.json').read_text()) if (LOCAL / 'reads.json').exists() else {}
    for rel, expected in used.items():
        assert digest((ROOT / rel).read_bytes()) == expected, rel
    result = {'protected_files': len(before['files']), 'changed_files': changed,
              'official_files': len(official), 'used_files': len(used),
              'head_same': git('rev-parse', 'HEAD').strip() == before['head'],
              'outside_status_same': outside_status() == before['outside_status_sha256']}
    put('audit.json', result)
    assert not changed
    assert result['head_same']
    print(json.dumps(result))


def main():
    assert sys.flags.isolated and sys.dont_write_bytecode
    assert HERE.resolve() == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_leads_r2')
    assert not LOCAL.is_symlink()
    assert (HERE / '.gitignore').read_text() == 'local/\n'
    assert git('check-ignore', str(LOCAL / 'check')).strip()
    LOCAL.mkdir(exist_ok=True)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='op', required=True)
    sub.add_parser('freeze')
    sub.add_parser('audit')
    win = sub.add_parser('window')
    win.add_argument('image')
    win.add_argument('lo', type=lambda x: int(x, 0))
    win.add_argument('hi', type=lambda x: int(x, 0))
    win.add_argument('tag')
    find = sub.add_parser('scan')
    find.add_argument('image')
    find.add_argument('pattern')
    find.add_argument('tag')
    find.add_argument('--radius', type=int, default=5)
    args = parser.parse_args()
    if args.op == 'freeze':
        freeze()
    elif args.op == 'audit':
        audit()
    elif args.op == 'window':
        print(json.dumps(window(args.image, args.lo, args.hi, args.tag)))
    elif args.op == 'scan':
        scan(args.image, args.pattern, args.tag, args.radius)
    path = LOCAL / 'reads.json'
    prior = json.loads(path.read_text()) if path.exists() else {}
    for rel, value in READS.items():
        assert rel not in prior or prior[rel] == value, rel
    put('reads.json', {**prior, **READS})


if __name__ == '__main__':
    main()
