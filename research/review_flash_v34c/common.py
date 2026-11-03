"""Review utilities. No product builder is invoked."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
RES = ROOT / 'firmware/resident_v34c'
ACCEPT = RES / 'acceptance'
PRODUCT = ACCEPT / 'containers/product'
FINAL = ACCEPT / 'local/full-r11'
PACKAGE = ROOT / 'firmware/image_v34c/local/package'
GCC = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, value):
    p = LOCAL / name
    p.resolve().relative_to(LOCAL.resolve())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(args, name, check=True, timeout=180):
    out = LOCAL / 'logs'
    tmp = LOCAL / 'tmp'
    out.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(tmp), CLANG_MODULE_CACHE_PATH=str(tmp / 'modules'),
               ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
               PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0', LC_ALL='C')
    p = subprocess.run([str(x) for x in args], cwd=ROOT, env=env, capture_output=True,
                       text=True, timeout=timeout)
    (out / (name + '.stdout')).write_text(p.stdout)
    (out / (name + '.stderr')).write_text(p.stderr)
    with (LOCAL / 'commands.jsonl').open('a') as f:
        f.write(json.dumps({'name': name, 'argv': list(map(str, args)), 'rc': p.returncode}) + '\n')
    if check and p.returncode:
        raise RuntimeError(name + ': ' + str(p.returncode) + '\n' + (p.stdout + p.stderr)[-3500:])
    return p


class Elf:
    """ELF32 BE section/symbol reader, independent of the firmware builder."""
    def __init__(self, path):
        self.path = Path(path)
        self.raw = self.path.read_bytes()
        assert self.raw[:7] == bytes((127, 69, 76, 70, 1, 2, 1))
        h = struct.unpack_from('>HHIIIIIHHHHHH', self.raw, 16)
        assert h[1] == 88 and h[10] == 40
        self.entry = h[3]
        keys = ('ni', 'kind', 'flags', 'va', 'off', 'size', 'link', 'info', 'align', 'entsize')
        self.sections = [dict(zip(keys, struct.unpack_from('>10I', self.raw, h[5] + 40 * i))) for i in range(h[11])]
        names = self.data(self.sections[h[12]])
        for s in self.sections:
            s['name'] = names[s['ni']:names.index(0, s['ni'])].decode()
        self.by_name = {s['name']: s for s in self.sections}
        self.symbols = {}
        self.tables = {}
        for index, s in enumerate(self.sections):
            if s['kind'] != 2:
                continue
            strings = self.data(self.sections[s['link']])
            table = []
            for at in range(0, s['size'], s['entsize']):
                ni, va, size, info, other, section = struct.unpack_from('>IIIBBH', self.raw, s['off'] + at)
                name = strings[ni:strings.index(0, ni)].decode()
                value = dict(name=name, va=va, size=size, info=info, section=section)
                table.append(value)
                if name:
                    self.symbols[name] = value
            self.tables[index] = table

    def data(self, s):
        assert s['kind'] != 8
        return self.raw[s['off']:s['off'] + s['size']]

    def at(self, va, n):
        hits = [s for s in self.sections if s['kind'] != 8 and s['flags'] & 2 and s['va'] <= va and va + n <= s['va'] + s['size']]
        assert len(hits) == 1, (hex(va), n)
        s = hits[0]
        return self.raw[s['off'] + va - s['va']:s['off'] + va - s['va'] + n]

    def relocs(self):
        for s in self.sections:
            if s['kind'] == 4:
                for at in range(0, s['size'], 12):
                    patch, info, addend = struct.unpack_from('>IIi', self.raw, s['off'] + at)
                    yield dict(patch=patch, kind=info & 255, symbol=self.tables[s['link']][info >> 8]['name'], addend=addend)


def segments(raw):
    return [dict(zip(('source', 'va', 'size', 'bss', 'bss_size'), struct.unpack_from('>5I', raw, 32 + 20 * i))) for i in range(16)]


def offset(raw, va, n):
    hits = [s for s in segments(raw) if s['va'] <= va and va + n <= s['va'] + s['size']]
    assert len(hits) == 1, (hex(va), n)
    s = hits[0]
    return 512 + s['source'] + va - s['va']


def image_at(raw, va, n):
    at = offset(raw, va, n)
    return raw[at:at + n]
