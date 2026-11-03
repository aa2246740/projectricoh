"""Disassemble VMA ranges of a GXR MAIN image (body or unit) with the repo's M32R objdump.
usage: dis.py IMAGE START END   (hex VMAs)"""
import hashlib, struct, subprocess, sys, tempfile, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OBJDUMP = ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
def sections(raw):
    return [struct.unpack_from('>5I', raw, 0x20+20*i) for i in range(16)]
def read(raw, address, size):
    for off, base, length, _, _ in sections(raw):
        if base <= address and address+size <= base+length:
            s = off+0x200+address-base
            return raw[s:s+size]
    raise ValueError(hex(address))
def dis(raw, start, end):
    data = read(raw, start, end-start)
    tmp = Path(os.environ.get('TMPDIR', '/tmp'))/f'dis-{start:x}.bin'
    tmp.write_bytes(data)
    out = subprocess.run([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r2', '-EB',
                          f'--adjust-vma={start:#x}', str(tmp)], capture_output=True, text=True, check=True).stdout
    tmp.unlink()
    import re
    return '\n'.join(l for l in out.splitlines() if re.match(r'^\s*[0-9a-f]+:', l))
if __name__ == '__main__':
    raw = Path(sys.argv[1]).read_bytes()
    print('#', sys.argv[1], hashlib.sha256(raw).hexdigest()[:16])
    print(dis(raw, int(sys.argv[2], 16), int(sys.argv[3], 16)))
