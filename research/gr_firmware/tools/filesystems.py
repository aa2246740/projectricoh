"""Read-only SquashFS v4/LZ4 and gzip/newc readers, implemented for this study.

Only regular file bytes are written under /tmp/gxr_gr_firmware. Symlinks,
devices and executables are never created as active filesystem objects/run.
"""
import argparse
import hashlib
import json
import pathlib
import stat
import struct
import zlib

SCRATCH = pathlib.Path('/tmp/gxr_gr_firmware')


def lz4(data):
    output, pos = bytearray(), 0
    while pos < len(data):
        token = data[pos]
        pos += 1
        length = token >> 4
        if length == 15:
            while True:
                value = data[pos]
                pos += 1
                length += value
                if value != 255:
                    break
        output.extend(data[pos:pos + length])
        pos += length
        if pos == len(data):
            break
        distance = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        length = token & 15
        if length == 15:
            while True:
                value = data[pos]
                pos += 1
                length += value
                if value != 255:
                    break
        length += 4
        if not 0 < distance <= len(output):
            raise ValueError('bad LZ4 distance')
        pattern = bytes(output[-distance:])
        output.extend((pattern * ((length + distance - 1) // distance))[:length])
        if len(output) > 1024 * 1024:
            raise ValueError('LZ4 block exceeds SquashFS maximum')
    if pos != len(data):
        raise ValueError('LZ4 boundary mismatch')
    return bytes(output)


def safe_path(root, name):
    parts = pathlib.PurePosixPath(name).parts
    if name.startswith('/') or any(p in ('..', '') for p in parts):
        raise ValueError('unsafe member name')
    dest = root.joinpath(*parts)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


class Squash:
    def __init__(self, data, base, output):
        self.data, self.base, self.output = data, base, output
        h = struct.unpack_from('<5I6H8Q', data, base)
        if (h[0], h[5], h[9], h[10]) != (0x73717368, 5, 4, 0):
            raise ValueError('expected SquashFS v4 with LZ4')
        self.block_size, self.fragments, self.root = h[3], h[4], h[11]
        self.inodes, self.dirs, self.frags = h[15], h[16], h[17]
        self.cache, self.records = {}, []

    def metadata(self, offset):
        if offset not in self.cache:
            tag = struct.unpack_from('<H', self.data, self.base + offset)[0]
            size = tag & 32767
            raw = self.data[self.base + offset + 2:self.base + offset + 2 + size]
            decoded = raw if tag & 32768 else lz4(raw)
            if len(decoded) > 8192:
                raise ValueError('oversized metadata block')
            self.cache[offset] = decoded, offset + 2 + size
        return self.cache[offset]

    def meta_read(self, start, inner, length):
        output = bytearray()
        while len(output) < length:
            data, nxt = self.metadata(start)
            if inner >= len(data):
                inner -= len(data)
                start = nxt
                continue
            part = data[inner:inner + length - len(output)]
            output.extend(part)
            inner, start = 0, nxt
        return bytes(output)

    def data_block(self, offset, descriptor):
        size = descriptor & 0xFFFFFF
        raw = self.data[self.base + offset:self.base + offset + size]
        return raw if descriptor & 0x1000000 else lz4(raw)

    def regular(self, header, ref, name):
        kind = struct.unpack_from('<H', header)[0]
        if kind == 2:
            start, fragment, inner, length = struct.unpack_from('<IIII', header, 16)
            header_size = 32
        elif kind == 9:
            start, length = struct.unpack_from('<QQ', header, 16)
            fragment, inner = struct.unpack_from('<II', header, 44)
            header_size = 56
        else:
            raise ValueError('not regular')
        count = length // self.block_size + int(fragment == 0xFFFFFFFF and length % self.block_size != 0)
        descriptors = self.meta_read(self.inodes + (ref >> 16), (ref & 65535) + header_size, count * 4)
        result, extents = bytearray(), []
        for (desc,) in struct.iter_unpack('<I', descriptors):
            if desc == 0:
                result.extend(b'\0' * min(self.block_size, length - len(result)))
                continue
            decoded = self.data_block(start, desc)
            extents.append(dict(payload_offset=self.base + start, compressed_size=desc & 0xFFFFFF, output_offset=len(result), decoded_size=len(decoded), compressed=not bool(desc & 0x1000000)))
            result.extend(decoded)
            start += desc & 0xFFFFFF
        if len(result) < length and fragment != 0xFFFFFFFF:
            ptr_offset = self.base + self.frags + (fragment // 512) * 8
            metadata_start = struct.unpack_from('<Q', self.data, ptr_offset)[0]
            entry = self.meta_read(metadata_start, (fragment % 512) * 16, 16)
            start, desc = struct.unpack_from('<QI', entry)
            decoded = self.data_block(start, desc)
            result.extend(decoded[inner:inner + length - len(result)])
            extents.append(dict(payload_offset=self.base + start, compressed_size=desc & 0xFFFFFF, fragment=fragment, fragment_inner_offset=inner, decoded_size=len(decoded), compressed=not bool(desc & 0x1000000)))
        if len(result) != length:
            raise ValueError(f'SquashFS size mismatch {name}: {len(result)} != {length}')
        safe_path(self.output, name).write_bytes(result)
        return dict(name=name, kind='regular', size=length, sha256=hashlib.sha256(result).hexdigest(), inode_ref=ref, extents=extents)

    def walk(self, ref, prefix='', depth=0):
        if depth > 40:
            raise ValueError('directory depth limit')
        header = self.meta_read(self.inodes + (ref >> 16), ref & 65535, 64)
        kind = struct.unpack_from('<H', header)[0]
        if kind == 1:
            block = struct.unpack_from('<I', header, 16)[0]
            size, inner = struct.unpack_from('<HH', header, 24)
        elif kind == 8:
            size, block = struct.unpack_from('<II', header, 20)
            inner = struct.unpack_from('<H', header, 34)[0]
        else:
            raise ValueError('expected directory')
        directory = self.meta_read(self.dirs + block, inner, max(0, size - 3))
        cursor = 0
        while cursor < len(directory):
            count, inode_block, _ = struct.unpack_from('<III', directory, cursor)
            cursor += 12
            for _ in range(count + 1):
                offset, _, typ, n = struct.unpack_from('<HHHH', directory, cursor)
                cursor += 8
                name = directory[cursor:cursor + n + 1].decode('utf-8', 'surrogateescape')
                cursor += n + 1
                path = prefix + name
                child_ref = (inode_block << 16) | offset
                if typ in (1, 8):
                    self.walk(child_ref, path + '/', depth + 1)
                elif typ in (2, 9):
                    child = self.meta_read(self.inodes + inode_block, offset, 64)
                    self.records.append(self.regular(child, child_ref, path))
                else:
                    self.records.append(dict(name=path, kind=f'nonregular-{typ}', inode_ref=child_ref, extracted=False))
        return self.records


def cpio_newc(data, output):
    cursor, records = 0, []
    while cursor + 110 <= len(data):
        if data[cursor:cursor + 6] not in (b'070701', b'070702'):
            raise ValueError(f'not newc at {cursor:#x}')
        fields = [int(data[cursor + 6 + 8 * i:cursor + 14 + 8 * i], 16) for i in range(13)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        name = data[cursor + 110:cursor + 110 + name_size - 1].decode('utf-8', 'surrogateescape')
        start = (cursor + 110 + name_size + 3) & ~3
        raw = data[start:start + size]
        cursor = (start + size + 3) & ~3
        if name == 'TRAILER!!!':
            break
        name = name.removeprefix('./')
        if stat.S_ISREG(mode):
            safe_path(output, name).write_bytes(raw)
            records.append(dict(name=name, kind='regular', size=size, sha256=hashlib.sha256(raw).hexdigest(), cpio_offset=start))
        else:
            records.append(dict(name=name, kind=f'nonregular-{mode:o}', extracted=False))
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    results = []
    for image in json.loads(pathlib.Path(args.manifest).read_text()):
        if image['model'] not in ('gr3', 'gr3x', 'gr4') or not image.get('images'):
            continue
        source = image['images'][0]
        payload = pathlib.Path(source['path']).read_bytes()
        output = pathlib.Path(source['path']).parent / 'rootfs'
        record = dict(model=image['model'], version=image['version'], payload_sha256=source['sha256'], filesystems=[], gzip_streams=[])
        for sig in source['signatures']:
            try:
                if sig['kind'] == 'squashfs':
                    squash = Squash(payload, sig['offset'], output)
                    files = squash.walk(squash.root)
                    record['filesystems'].append(dict(kind='SquashFS-LZ4', payload_offset=sig['offset'], output=str(output), files=files))
                    print(image['model'], 'SquashFS', len(files), flush=True)
                elif sig['kind'] == 'gzip':
                    decoder = zlib.decompressobj(31)
                    raw = decoder.decompress(payload[sig['offset']:], 512 * 1024 * 1024)
                    if not decoder.eof:
                        raise ValueError('gzip output limit or incomplete stream')
                    dest = pathlib.Path(source['path']).parent / f'gzip-{sig["offset"]:x}.bin'
                    dest.write_bytes(raw)
                    record['gzip_streams'].append(dict(payload_offset=sig['offset'], path=str(dest), size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
                    if raw[:6] in (b'070701', b'070702'):
                        files = cpio_newc(raw, output)
                        record['filesystems'].append(dict(kind='gzip-newc', payload_offset=sig['offset'], output=str(output), files=files))
                        print(image['model'], 'newc', len(files), flush=True)
            except Exception as error:
                record.setdefault('errors', []).append(dict(kind=sig['kind'], offset=sig['offset'], error=str(error)))
        results.append(record)
    pathlib.Path(args.output).write_text(json.dumps(results, indent=2) + '\n')
