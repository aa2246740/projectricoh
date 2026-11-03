#!/usr/bin/env python3
"""Read-only template parsing and rerunnable native-stream round-trip gates."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local/private'
SCRATCH = LOCAL / '_native-work'
sys.path.insert(0, str(ROOT / 'research/gr_incamera_dev'))
from tiff_io import Tiff, write_uint
import hashlib
import json
import os
import plistlib
import subprocess
import numpy as np
import imagecodecs
sys.path.insert(0, str(HERE))
import owners as registry

def require(ok, message):
    if not ok:
        raise ValueError(message)

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def output(path):
    p = Path(path)
    require(not p.is_symlink(), f'output symlink: {p}')
    p = p.resolve()
    require(p.is_relative_to(HERE) or p.is_relative_to(SCRATCH.resolve()), f'write outside boundary: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def dump(path, value):
    output(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

def read(path):
    return json.loads(Path(path).read_text())

def preflight():
    info = plistlib.loads(subprocess.run(['diskutil', 'info', '-plist', '/Volumes/Workspace'],
                          check=True, capture_output=True).stdout)
    require(info.get('FilesystemType') == 'apfs' and info.get('VolumeUUID', info.get('DiskUUID')) ==
            '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info.get('WritableVolume'), 'workspace mount mismatch')
    require((HERE / '.gitignore').read_text() == 'local/\n', 'local ignore changed')
    require(not (HERE / 'local').is_symlink() and not LOCAL.is_symlink() and LOCAL.resolve().is_relative_to(HERE),
            'private root leaves task folder')
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'probe')], cwd=ROOT, check=True)
    require(not subprocess.run(['git', 'ls-files', '-z', str(HERE / 'local')], cwd=ROOT,
            check=True, capture_output=True).stdout, 'private files in git index')
    for key in ('TMPDIR', 'TMP', 'TEMP'):
        os.environ[key] = str(SCRATCH)

def compile_codec():
    binary = output(SCRATCH / 'native')
    subprocess.run(['clang', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-I/opt/homebrew/include', str(HERE / 'native.c'), '-L/opt/homebrew/lib',
                    '-ljpeg', '-o', str(binary)], check=True, capture_output=True)
    return binary

def run(*args):
    subprocess.run([str(SCRATCH / 'native'), *map(str, args)], check=True, capture_output=True)

def header(blob):
    require(blob[:2] == b'\xff\xd8', 'missing SOI')
    p, records = 2, []
    while p + 4 <= len(blob):
        require(blob[p] == 255, 'unaligned JPEG header')
        marker, n = blob[p+1], int.from_bytes(blob[p+2:p+4], 'big')
        require(n >= 2 and p+2+n <= len(blob), 'JPEG segment bounds')
        records.append(dict(marker=f'FF{marker:02X}', length=n, start=p, end=p+2+n))
        p += 2+n
        if marker == 0xda:
            return blob[:p], records
    raise ValueError('missing SOS')

def markers(blob):
    head, records = header(blob)
    p, restarts, chunks = len(head), [], []
    start = p
    while p < len(blob):
        if blob[p] != 255:
            p += 1
            continue
        require(p+1 < len(blob), 'incomplete marker')
        m = blob[p+1]
        if m == 0:
            p += 2
            continue
        chunks.append((start, p))
        if 0xd0 <= m <= 0xd7:
            require(m == 0xd0 + len(restarts) % 8, 'restart cycle')
            restarts.append(m)
            p += 2
            start = p
        elif m == 0xd9:
            require(p+2 == len(blob), 'bytes after EOI')
            return dict(header_sha256=digest(head), header_bytes=len(head), segments=records,
                        restart_count=len(restarts), entropy_chunks=len(chunks), eoi_at=p,
                        bytes=len(blob), sha256=digest(blob))
        else:
            raise ValueError(f'unexpected scan marker FF{m:02X}')
    raise ValueError('missing EOI')

def streams(tiff):
    raw = tiff.segments(tiff.raw)
    require(len(raw) == 1, 'single RAW strip required')
    previews = [n for n in tiff.ifds if n is not tiff.raw and 256 in n.entries and tiff.scalar(n,259) == 7]
    require(len(previews) == 1, 'one full preview required')
    full = tiff.segments(previews[0])[0]
    m = tiff.maker()
    maker = dict(offset=m.offset-8+m.entries[4].value[0], capacity=m.entries[3].value[0])
    return dict(raw=raw[0], full=full, maker=maker), previews[0], m

def extract(tiff):
    refs, _, _ = streams(tiff)
    return {k: tiff.data[v['offset']:v['offset']+v['capacity']] for k,v in refs.items()}

def template(owner):
    record = registry.get(owner)['template']
    expected = record['sha256']
    p = (ROOT / record['path']).resolve()
    require(p.is_relative_to((ROOT / 'captures/contrib').resolve()), 'template outside contributor captures')
    actual = sha(p)
    require(actual == expected, f'{owner} template hash mismatch: {actual}')
    return p, Tiff(p.read_bytes())

def prove(owner):
    path, tiff = template(owner)
    folder = output(registry.root(owner) / 'r3/proof/placeholder').parent
    result = dict(template=str(path.relative_to(ROOT)), template_sha256=sha(path), streams={})
    for kind, blob in extract(tiff).items():
        source = output(folder / f'{kind}.original.jpg')
        encoded = output(folder / f'{kind}.roundtrip.jpg')
        source.write_bytes(blob)
        gate = 'G1' if kind == 'raw' else 'G2'
        try:
            if kind == 'raw':
                decoded = output(folder / 'raw.decoded.u16')
                run('raw-roundtrip', source, encoded, decoded)
                own = np.fromfile(decoded, '<u2')
                independent = imagecodecs.ljpeg_decode(blob).reshape(-1)
                require(np.array_equal(own, independent), 'independent RAW decode mismatch')
                extra = dict(samples=int(own.size), independent_decoder='imagecodecs.ljpeg_decode',
                             independent_mismatches=0, decoded_u16_sha256=sha(decoded), final_bit_padding='ones')
            else:
                run('jpeg-roundtrip', source, encoded)
                extra = dict(coefficient_reader='libjpeg jpeg_read_coefficients',
                             entropy_encoder='native.c canonical Huffman with DC reset at RST', final_bit_padding='ones')
            encoded_blob = encoded.read_bytes()
            if encoded_blob != blob:
                at = next((i for i, (a, b) in enumerate(zip(blob, encoded_blob)) if a != b),
                          min(len(blob), len(encoded_blob)))
                original_header, segments = header(blob)
                same_header = original_header == header(encoded_blob)[0]
                location = next((r['marker'] for r in segments if r['start'] <= at < r['end']),
                                'SOI' if at < 2 else 'entropy/EOI or stream length')
                raise ValueError(f'byte round-trip mismatch; header_equal={same_header}; '
                                 f'first differing stream byte={at} ({location}); '
                                 f'lengths={len(blob)}/{len(encoded_blob)}')
        except Exception as error:
            detail = error.stderr.decode(errors='replace') if isinstance(error, subprocess.CalledProcessError) else str(error)
            failure = dict(passed=False, gate=gate, stream=kind, reason=detail.strip(),
                           template_sha256=sha(path), original_sha256=digest(blob))
            for label, content in [('original', blob), ('roundtrip', encoded.read_bytes() if encoded.exists() else None)]:
                if content is not None:
                    try:
                        head, segments = header(content)
                        failure[label + '_header'] = dict(sha256=digest(head), bytes=len(head), segments=segments)
                    except ValueError as header_error:
                        failure[label + '_header'] = dict(error=str(header_error))
            dump(folder / 'failure.json', failure)
            raise ValueError(f'{gate} {owner}/{kind}: {detail.strip()}; STOP, possible new firmware layout') from error
        result['streams'][kind] = dict(passed=True, original_sha256=digest(blob),
                                      reencoded_sha256=digest(encoded_blob), differing_bytes=0,
                                      **markers(blob), **extra)
    result.update(G1=True, G2=True)
    dump(folder / 'proof.json', result)
    return result

if __name__ == '__main__':
    preflight()
    compile_codec()
    for owner in registry.templates():
        r = prove(owner)
        print(owner, 'G1/G2 PASS', {k:v['bytes'] for k,v in r['streams'].items()}, flush=True)
