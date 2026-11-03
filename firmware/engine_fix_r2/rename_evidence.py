"""Extract official 1.51 rename instructions without executing the firmware."""
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c


def image_at(raw, address, size):
    for i in range(16):
        source, base, length, _, _ = struct.unpack_from('>5I', raw, 32 + 20*i)
        if base <= address and address + size <= base + length:
            off = 512 + source + address - base
            return raw[off:off+size]
    raise ValueError(hex(address))


def main():
    c.guard()
    path = c.ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
    assert c.sha(path) == 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    out = c.LOCAL / 'rename'
    out.mkdir(exist_ok=True)
    rows = []
    for name, address, size in (
        ('wrapper', 0x200a49d8, 0x80), ('inner', 0x200a6cb8, 0x500),
        ('lookup', 0x200b4824, 0x4c0), ('create-target', 0x200b6d08, 0x4a8),
        ('prepare-target', 0x200b3ccc, 0x800), ('check-source', 0x200b52b4, 0x500),
        ('lookup-name', 0x200b62a8, 0xa60), ('error', 0x200af4ec, 0x168),
        ('directory-op', 0x200b8b40, 0x448), ('directory-pointer', 0x200b78f4, 0x3c),
        ('parse-path', 0x200af654, 0x264)):
        target = out / (name + '.bin')
        target.write_bytes(image_at(path.read_bytes(), address, size))
        c.run([c.OBJDUMP, '-D', '-b', 'binary', '-m', 'm32r', '-EB',
               '--adjust-vma='+hex(address), target], 'rename-'+name)
        rows.append(dict(name=name, address=hex(address), bytes=size, sha256=c.sha(target)))
    c.save(out / 'regions.json', dict(official_sha256=c.sha(path), regions=rows,
                                    method='static objdump; M32R not executed'))
    print('PASS official identity and rename instruction extraction')


if __name__ == '__main__':
    main()
