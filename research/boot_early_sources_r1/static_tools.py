"""本地固件静态取证。只在本研究目录写入派生文件。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import struct
import subprocess

signal.alarm(180)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/boot-early-src-r1')
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
OFFICIAL = 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = 'firmware/package_v39_g153/SD_ROOT/ilaunch3'
EXPECTED = {
    OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
    BODY: '8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d',
}
LINE = re.compile(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)\s*(.*?)\s*$')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(name, data):
    path = HERE / name
    assert path.resolve().is_relative_to(HERE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def progress(message):
    with (HERE / 'PROGRESS.md').open('a') as f:
        f.write(datetime.now(timezone.utc).isoformat(timespec='seconds') + ' | ' + message + '\n')


class Image:
    def __init__(self, name=OFFICIAL):
        self.name = name
        self.data = (ROOT / name).read_bytes()
        self.sha256 = sha(self.data)
        if name in EXPECTED:
            assert self.sha256 == EXPECTED[name], (name, self.sha256)
        self.entry = struct.unpack_from('>I', self.data, 0x160)[0]
        self.sections = []
        if self.data[16] == 8 and self.entry == 0x27e00000:
            assert struct.unpack_from('>I', self.data, 0x164)[0] == len(self.data)-512
            self.sections.append(dict(index=0, file=512, base=self.entry,
                                      size=len(self.data)-512, zero=0, zero_size=0,
                                      mapping_only=True))
            return
        for i in range(16):
            src, base, size, zero, zero_size = struct.unpack_from('>5I', self.data, 32+20*i)
            assert src+512+size <= len(self.data)
            self.sections.append(dict(index=i, file=src+512, base=base, size=size,
                                      zero=zero, zero_size=zero_size))

    def offset(self, address, count):
        found = [s['file']+address-s['base'] for s in self.sections
                 if s['base'] <= address and address+count <= s['base']+s['size']]
        assert len(found) == 1, (self.name, hex(address), count)
        return found[0]

    def raw(self, address, count):
        at = self.offset(address, count)
        return self.data[at:at+count]


def window(label, start, end, name=OFFICIAL):
    assert re.fullmatch(r'[a-z0-9_-]+', label)
    im = Image(name)
    raw = im.raw(start, end-start)
    folder = HERE / 'evidence'
    folder.mkdir(exist_ok=True)
    target = folder / (label+'.bin')
    target.write_bytes(raw)
    env = dict(os.environ, TMPDIR=str(TMP))
    command = [str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
               '--adjust-vma='+hex(start), str(target)]
    run = subprocess.run(command, check=True, text=True, capture_output=True,
                         timeout=30, env=env)
    (folder / (label+'.asm.txt')).write_text(run.stdout)
    rows = []
    for line in run.stdout.splitlines():
        m = LINE.match(line)
        if m:
            address = int(m[1], 16)
            data = bytes.fromhex(m[2])
            assert im.raw(address, len(data)) == data
            rows.append(dict(address=hex(address), bytes=data.hex(), disassembly=m[3]))
    body_equal = None
    if name == OFFICIAL:
        body_equal = Image(BODY).raw(start, end-start) == raw
    meta = dict(source=name, source_sha256=im.sha256, start=hex(start), end=hex(end),
                file_offset=hex(im.offset(start, end-start)), size=len(raw), sha256=sha(raw),
                body_equal=body_equal, instructions=rows)
    save('evidence/'+label+'.json', meta)
    print(json.dumps({k:v for k,v in meta.items() if k != 'instructions'}, ensure_ascii=False))


def instructions():
    im = Image()
    for path in sorted((ROOT/'research/tooling_m32r/disasm').glob('ilaunch3-sec*.disasm.txt')):
        for number, line in enumerate(path.open(), 1):
            m = LINE.match(line)
            if not m:
                continue
            address, data = int(m[1],16), bytes.fromhex(m[2])
            assert im.raw(address, len(data)) == data, (path, number)
            for part, op in enumerate(re.split(r' -> | \|\| ', m[3])):
                yield address+part*2, data if part == 0 else data[2:], op, str(path.relative_to(ROOT)), number


def refs(values):
    targets = {int(x,0) for x in values}
    rows = []
    for address, data, op, source, line in instructions():
        m = re.fullmatch(r'(b\w*|ld24)\s+(?:r\d+,)?(?:r\d+,)?(?:0x)?([0-9a-f]+)', op)
        if m and int(m[2],16) in targets:
            rows.append(dict(address=hex(address), bytes=data.hex(), instruction=op,
                             source=source, line=line, target=hex(int(m[2],16))))
    save('references/latest.json', dict(targets=[hex(x) for x in sorted(targets)], rows=rows,
        boundary='只含直接分支及 ld24 常量；间接表和寄存器调用须另查。'))
    print(json.dumps(rows,ensure_ascii=False,indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['window','refs','progress'])
    p.add_argument('args', nargs='*')
    a=p.parse_args()
    if a.action == 'window':
        window(a.args[0], int(a.args[1],0), int(a.args[2],0), a.args[3] if len(a.args)>3 else OFFICIAL)
    elif a.action == 'refs':
        refs(a.args)
    else:
        progress(' '.join(a.args))


if __name__ == '__main__':
    main()
