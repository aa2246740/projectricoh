"""Read existing firmware bytes and retain focused M32R listings."""
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, ROOT, save, sha, verify_pins

OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
SPANS = {
    'link-publication': (0x20063798, 0x20063980),
    'unit-read': (0x2006c65c, 0x2006c6f0),
    'ready-publication': (0x20093590, 0x20093610),
    'image-constructor': (0x20287060, 0x20287218),
    'image-entry-dispatch': (0x202ba700, 0x202ba7d0),
    'image-arrow': (0x202bb930, 0x202bb990),
    'image-panel': (0x202be220, 0x202be284),
    'common-render': (0x201febbc, 0x201fec20),
    'grain-call': (0x20170968, 0x201709b4),
    'image-getter': (0x20271fec, 0x20272014),
    'image-mode-store': (0x20268710, 0x20268820),
}


def run():
    verify_pins()
    image = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
    raw = image.read_bytes()
    sections = [struct.unpack_from('>5I', raw, 0x20 + 20*i) for i in range(16)]
    def read_at(address, size):
        s = next(s for s in sections if s[1] <= address and address+size <= s[1]+s[2])
        offset = s[0]+0x200+address-s[1]
        return raw[offset:offset+size]
    result = dict(image_sha256=sha(raw), ranges={}, direct_constructor_calls=[],
                  constructor_address_pairs=[], address_words=[])
    for name, (start, end) in SPANS.items():
        section = next(s for s in sections if s[1] <= start and end <= s[1]+s[2])
        offset = section[0]+0x200+start-section[1]
        data = raw[offset:offset+end-start]
        binary = OUT / 'static' / (name+'.bin')
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(data)
        cmd = [str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
               '--adjust-vma='+hex(start), str(binary)]
        done = subprocess.run(cmd, capture_output=True, text=True, check=True)
        listing = binary.with_suffix('.txt')
        listing.write_text(done.stdout)
        result['ranges'][name] = dict(start=hex(start), end=hex(end), file_offset=offset,
                                     bytes=len(data), sha256=sha(data), listing=str(listing.relative_to(OUT)))
    # Direct BL24 encodings are decoded from every aligned halfword candidate.
    # Candidates are checked against GNU decoding at the matching source address.
    target = 0x20287080
    for index, s in enumerate(sections):
        source, base, size, _, _ = s
        data = raw[source+0x200:source+0x200+size]
        for off in range(0, len(data)-3, 2):
            pc = base+off
            op = data[off:off+4]
            if op[0] == 0xfe:
                disp = int.from_bytes(op[1:], 'big')
                if disp & 0x800000:
                    disp -= 0x1000000
                if ((pc & ~3) + 4*disp) & 0xffffffff == target:
                    result['direct_constructor_calls'].append(dict(section=index, pc=hex(pc), bytes=op.hex()))
            for reg in range(16):
                pair = bytes((0xd0+reg, 0xc0, 0x20, 0x28, 0x80+reg, 0xe0+reg, 0x70, 0x80))
                if data[off:off+8] == pair:
                    result['constructor_address_pairs'].append(dict(section=index, pc=hex(pc), register=reg,
                                                                   following=data[off:off+16].hex()))
        needle = target.to_bytes(4, 'big')
        for off in range(0, len(data)-3, 4):
            if data[off:off+4] == needle:
                result['address_words'].append(dict(section=index, pc=hex(base+off)))
    elf = ROOT / 'firmware/resident_v36/local/resident/build/resident.elf'
    done = subprocess.run([str(OBJDUMP), '-d', str(elf)], capture_output=True, text=True, check=True)
    listing = '\n'.join('Disassembly of executable section:' if line.startswith('Disassembly of section')
                        else line for line in done.stdout.splitlines())+'\n'
    (OUT / 'static/resident.txt').write_text(listing)
    result['resident_elf_sha256'] = sha(elf.read_bytes())
    state56_table = int.from_bytes(read_at(0x2037f658+56*4, 4), 'big')
    events = []
    for i in range(128):
        key, pre, post = struct.unpack('>3I', read_at(state56_table+12*i, 12))
        if not key:
            break
        events.append(dict(key=hex(key), pre=hex(pre), post=hex(post)))
    result['state56_table'] = dict(address=hex(state56_table), events=events)
    offsets = struct.unpack('>22h', read_at(0x20377434, 44))
    result['native_item_dispatch'] = [dict(item=i+1, target=hex(0x202ba72c+n)) for i, n in enumerate(offsets)]
    body = (ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3').read_bytes()
    start, end = SPANS['image-constructor']
    s = next(s for s in sections if s[1] <= start and end <= s[1]+s[2])
    offset = s[0]+0x200+start-s[1]
    binary = OUT / 'static/patched-image-constructor.bin'
    binary.write_bytes(body[offset:offset+end-start])
    done = subprocess.run([str(OBJDUMP), '-D', '-b', 'binary', '-m', 'm32r', '-EB',
                           '--adjust-vma='+hex(start), str(binary)], capture_output=True, text=True, check=True)
    binary.with_suffix('.txt').write_text(done.stdout)
    save('static-paths.json', result)
    print(json.dumps(dict(status='PASS', ranges=len(result['ranges']),
                          constructor_calls=result['direct_constructor_calls'],
                          address_pairs=result['constructor_address_pairs'])))


if __name__ == '__main__':
    run()
