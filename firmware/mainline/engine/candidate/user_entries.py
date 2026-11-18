"""List or build read-only user entries for the current DAT format (gen 137+).

Current-format user CLI for the formal tree (closes g135/P2-01). Entries are
GXUI v1 records in the fixed 1984-byte extension at the start of the
seventh section, after the 1408-byte legacy block. The record encoder is the
frozen GXUI v1 implementation (firmware/engine_v46_ui/candidate/ui_data.py,
loaded read-only); this tool only locates the extension in the current
envelope and reseals the two DAT CRCs. Only the extension may change: every
other byte is checked against the input. Python standard library only.

  user_entries.py list  GXRCE.DAT
  user_entries.py build GXRCE.DAT --manifest entries.txt --output local/.../GXRCE.DAT
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_spec = importlib.util.spec_from_file_location('gxui_v1', HERE / 'ui_data.py')
gxui = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gxui)
SECTION7 = 11296          # 1408 legacy + 1984 GXUI v1 + 7904 R3 knobs
EXTENSION = (1408, 1408 + gxui.EXT_BYTES)


def crc(raw):
    return zlib.crc32(raw) & 0xffffffff


def envelope(raw):
    """Check the current envelope and both CRCs; return the extension start."""
    if len(raw) < 256 or raw[:8] != b'GXRCE001' or struct.unpack_from('>I', raw, 16)[0] != len(raw):
        raise ValueError('not a GXRCE001 DAT of the stated length')
    generation = struct.unpack_from('>I', raw, 28)[0]
    if generation != 157:
        raise ValueError('requires the current generation envelope')
    header = bytearray(raw[:256]); header[20:24] = bytes(4)
    if struct.unpack_from('>I', raw, 20)[0] != crc(header) or struct.unpack_from('>I', raw, 24)[0] != crc(raw[256:]):
        raise ValueError('DAT CRC differs')
    start, length = struct.unpack_from('>II', raw, 132 + 12 * 6)
    if length != SECTION7 or start + length > len(raw):
        raise ValueError('seventh section has an unexpected layout')
    return start + EXTENSION[0], generation


def banks(raw):
    directory = struct.unpack_from('>I', raw, 156)[0]
    return [raw[struct.unpack_from('>I', raw, directory + 64 * m + 16)[0] + 32:][:1024] for m in range(3)]


def entry_limit(raw):
    shared=struct.unpack_from('>I',raw,192)[0]
    area=shared+struct.unpack_from('>I',raw,shared+64)[0]
    count=struct.unpack_from('>H',raw,area+10)[0]
    visible=[sum(bool(raw[area+32+32*i+18] & (1<<unit)) for i in range(count)) for unit in range(3)]
    return min(gxui.CAPACITY,40-max(visible))


def parse(raw):
    at, generation = envelope(raw)
    ext = raw[at:at + gxui.EXT_BYTES]
    count = struct.unpack_from('>H', ext, 24)[0]
    if count > entry_limit(raw):
        raise ValueError('flat list user limit: '+str(entry_limit(raw)))
    users = []
    for i in range(count):
        record = ext[gxui.USER_OFFSET + gxui.ENTRY_BYTES * i:][:gxui.ENTRY_BYTES]
        users.append(dict(base=record[0], levels=list(struct.unpack_from('11b', record, 10)),
                          name=record[2:10].split(b'\0')[0].decode('ascii')))
    rebuilt = gxui.extension(ext[64:gxui.USER_OFFSET], banks(raw), [dict(base=u['base'], levels=u['levels']) for u in users])
    if rebuilt != ext:
        raise ValueError('GXUI v1 record fields differ')
    return at, generation, users


def replace(raw, users):
    if len(users)>entry_limit(raw):
        raise ValueError('flat list user limit: '+str(entry_limit(raw)))
    at, _, _ = parse(raw)
    out = bytearray(raw)
    out[at:at + gxui.EXT_BYTES] = gxui.extension(raw[at + 64:at + gxui.USER_OFFSET], banks(raw), users)
    struct.pack_into('>I', out, 24, crc(out[256:]))
    struct.pack_into('>I', out, 20, 0)
    struct.pack_into('>I', out, 20, crc(out[:256]))
    out = bytes(out)
    changed = [i for i in range(len(raw)) if raw[i] != out[i]]
    if any(not (20 <= i < 28 or at <= i < at + gxui.EXT_BYTES) for i in changed):
        raise ValueError('bytes outside the user extension changed')
    parse(out)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('list', 'build'))
    parser.add_argument('dat', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    raw = args.dat.read_bytes()
    try:
        if args.command == 'build':
            if not args.manifest or not args.output:
                raise ValueError('build requires --manifest and --output')
            if args.output.exists() or args.output.is_symlink() or 'local' not in args.output.resolve().parts:
                raise ValueError('output must be a new file under a local directory')
            raw = replace(raw, gxui.read_manifest(args.manifest.read_text()))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('xb') as stream:
                stream.write(raw)
        _, generation, users = parse(raw)
    except (ValueError, KeyError, TypeError, struct.error) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(dict(status='PASS', generation=generation, count=len(users), capacity=gxui.CAPACITY,
                          entries=[dict(name=u['name'], base=u['base'], levels=dict(zip(gxui.KEYS, u['levels']))) for u in users],
                          bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
