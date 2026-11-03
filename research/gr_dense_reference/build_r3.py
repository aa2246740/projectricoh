#!/usr/bin/env python3
"""Keep r2 chart samples and rebuild only native image streams and size references."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native as n
import copy
import gzip
import io
import json
import subprocess
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

SIGMAS = (0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12)
MAX_RAW_BYTES = 32_083_249

DESIGN_KEYS = ('geometry', 'colour_matrix', 'matrix_info', 'band', 'acceptance_microtest',
               'pitch', 'patch_side', 'roi_side', 'markers', 'patches', 'prior_radius',
               'prior_gain_ev', 'reference_max_radius', 'background_neutral_level')

def fingerprint(card):
    return n.digest(json.dumps({k:card[k] for k in DESIGN_KEYS}, sort_keys=True,
                              separators=(',', ':'), allow_nan=False).encode())

def baseline():
    path = n.LOCAL / 'r3/input-baseline.json'
    if path.exists():
        verify_baseline()
        return
    paths = set()
    for owner in n.registry.templates():
        base = n.registry.root(owner)
        paths.update(p for p in base.rglob('*') if p.is_file() and
                     p.relative_to(base).parts[0] not in ('r3', 'SEND_r3', 'SEND_r3.zip'))
    # Freeze r2 code/reports and all source modules called by the new builder.
    old_names = ('inject.py', 'dense.py', 'lattice.py', 'readback.py', 'verify.py', 'report.py',
                 'run_all.py', 'coverage.py', 'validate.py', 'instructions.py', 'REPORT.md',
                 'OWNER_ZH_EN.txt', '.gitignore', 'SHA256SUMS', 'DNG_SHA256SUMS',
                 'coverage.json', 'offline_validation.json')
    paths.update(n.HERE / name for name in old_names)
    paths.update((n.ROOT / 'research/gr_incamera_dev').glob('*.py'))
    paths.update(n.ROOT / item[0] for item in n.registry.templates().values())
    record = {str(p.relative_to(n.ROOT)): dict(sha256=n.sha(p), bytes=p.stat().st_size)
              for p in sorted(paths)}
    n.dump(path, dict(schema='gr-dense-r3-input-baseline/1', files=record))

def verify_baseline():
    record = n.read(n.LOCAL / 'r3/input-baseline.json')['files']
    for name, expected in record.items():
        p = n.ROOT / name
        n.require(p.is_file() and n.sha(p) == expected['sha256'] and p.stat().st_size == expected['bytes'],
                  f'read-only input changed: {name}')
    return len(record)

def verify_continuation():
    record = n.read(n.LOCAL / 'r3/continuation-baseline.json')['files']
    for name, expected in record.items():
        p = n.ROOT / name
        n.require(p.is_file() and n.sha(p) == expected['sha256'] and p.stat().st_size == expected['bytes'],
                  f'read-only continuation input changed: {name}')
    return len(record)

def saved_proof(owner):
    """Reuse the already independently verified G1/G2 files without rewriting them."""
    folder = n.registry.root(owner) / 'r3/proof'
    proof = n.read(folder / 'proof.json')
    path, tiff = n.template(owner)
    n.require(proof['G1'] and proof['G2'] and proof['template_sha256'] == n.sha(path),
              'saved G1/G2 proof does not match template')
    for kind, blob in n.extract(tiff).items():
        record = proof['streams'][kind]
        n.require(n.digest(blob) == record['original_sha256'] == record['reencoded_sha256'] and
                  n.sha(folder / f'{kind}.original.jpg') == n.digest(blob) and
                  n.sha(folder / f'{kind}.roundtrip.jpg') == n.digest(blob), 'saved stream proof changed')
    return proof

def sanity(blobs, refs):
    n.require(len(blobs['maker']) <= refs['maker']['capacity'], 'G3 maker preview exceeds original JPEG length')
    n.require(len(blobs['full']) <= refs['full']['capacity'], 'G3 full preview exceeds template length')
    n.require(len(blobs['raw']) <= MAX_RAW_BYTES, 'G3 RAW exceeds largest observed camera-written strip')
    return dict(passed=True, raw_bytes=len(blobs['raw']), raw_limit=MAX_RAW_BYTES,
                full_preview_bytes=len(blobs['full']), full_preview_limit=refs['full']['capacity'],
                full_preview_sigma_px=0, maker_bytes=len(blobs['maker']), maker_limit=refs['maker']['capacity'])

def encode_maker(raster, source, work, limit):
    """Try each sigma on the original RGB raster; preserve the native stream header."""
    rgb, packed = n.output(work / 'maker.rgb'), n.output(work / 'maker.jpg')
    attempts = []
    original = np.asarray(raster, dtype=np.float32)
    for sigma in (0, *SIGMAS):
        pixels = original if sigma == 0 else gaussian_filter(original, (sigma, sigma, 0), mode='reflect', truncate=4.)
        rgb.write_bytes(np.rint(pixels).astype(np.uint8).tobytes())
        n.run('jpeg-encode', source, rgb, packed)
        blob = packed.read_bytes()
        attempts.append(dict(sigma_px=sigma, bytes=len(blob), sha256=n.digest(blob), fits=len(blob) <= limit))
        if sigma == 0:
            n.output(work / 'maker.sharp.jpg').write_bytes(blob)
        if len(blob) <= limit:
            break
    else:
        blob = Path(source).read_bytes()
        packed.write_bytes(blob)
        sigma = None
    return blob, dict(display_only=True, sigma_px=sigma, bytes=len(blob), template_length_bound=limit,
                      unfiltered_bytes=attempts[0]['bytes'], fallback_template_original=sigma is None,
                      gaussian='scipy.ndimage.gaussian_filter; RGB sigma=(s,s,0), reflect, truncate=4',
                      attempts=attempts, smallest_fitting_sigma=True, relocated=False)

def allowed_ranges(t, new, blobs):
    refs, preview, maker = n.streams(t)
    raw_at = refs['raw']['offset']
    raw_end = raw_at + len(blobs['raw'])
    preview_at = (raw_end+255)//256*256
    thumb = t.segments(t.root)[0]
    values = [(t.raw.entries[279].offset, t.raw.entries[279].size, 'raw StripByteCounts'),
              (preview.entries[273].offset, preview.entries[273].size, 'preview StripOffsets'),
              (preview.entries[279].offset, preview.entries[279].size, 'preview StripByteCounts'),
              (maker.entries[3].offset, maker.entries[3].size, 'MakerNote 0x0003 preview length'),
              (thumb['offset'], thumb['capacity'], 'r2 chart RGB thumbnail pixels'),
              (refs['maker']['offset']+len(n.header(blobs['maker'])[0]),
               refs['maker']['capacity']-len(n.header(blobs['maker'])[0]), 'MakerNote native entropy and FF slot filler'),
              (raw_at+len(n.header(blobs['raw'])[0]), len(blobs['raw'])-len(n.header(blobs['raw'])[0]),
               'native RAW entropy and EOI'),
              (raw_end, preview_at-raw_end, 'FF alignment to 256 bytes'),
              (preview_at, len(blobs['full']), 'relocated native full preview'),
              (len(new), max(0,len(t.data)-len(new)), 'removed obsolete RAW allocation and old preview tail')]
    return [dict(start=a, end=a+size, reason=reason) for a,size,reason in sorted(values) if size]

def diff_ranges(before, after, permitted, destination):
    """Exhaustive contiguous byte differences, split at the reason boundaries."""
    common = min(len(before),len(after))
    previous = 0
    totals, count = {}, 0
    with gzip.open(n.output(destination), 'wt', encoding='utf-8', newline='') as out:
        out.write('start\tend_exclusive\toperation\treason\n')
        for r in permitted:
            start,end,reason = r['start'],r['end'],r['reason']
            n.require(start >= previous, 'overlapping permitted mutation ranges')
            gap_end = min(start,common)
            n.require(before[min(previous,common):gap_end] == after[min(previous,common):gap_end],
                      f'G3 unexplained changed bytes before offset {start}')
            a,b = min(start,common),min(end,common)
            if b > a:
                different = np.frombuffer(before, np.uint8, b-a, a) != np.frombuffer(after,np.uint8,b-a,a)
                changes = np.flatnonzero(np.diff(np.r_[False,different,False]))
                for x,y in changes.reshape(-1,2):
                    out.write(f'{a+int(x)}\t{a+int(y)}\treplace\t{reason}\n')
                runs = len(changes)//2
                changed = int(np.count_nonzero(different))
                if changed:
                    totals[reason] = dict(ranges=runs, differing_bytes=changed)
                    count += runs
            if end > common:
                n.require(start >= common or end == max(len(before),len(after)), 'invalid length mutation')
                x,y = max(start,common),min(end,max(len(before),len(after)))
                if y > x:
                    operation = 'remove' if len(before)>len(after) else 'insert'
                    out.write(f'{x}\t{y}\t{operation}\t{reason}\n')
                    totals[reason] = dict(ranges=1,differing_bytes=y-x)
                    count += 1
            previous=end
        n.require(before[min(previous,common):common] == after[min(previous,common):common], 'G3 unexplained tail')
        n.require(previous >= max(len(before),len(after)), 'G3 unaccounted file length change')
    return dict(passed=True, all_differing_ranges=count, reasons=totals,
                diff_file=str(Path(destination).relative_to(n.ROOT)), diff_sha256=n.sha(destination),
                offsets='zero-based, half-open', unexplained_ranges=0)

def apple(path):
    result = subprocess.run([str(n.SCRATCH/'apple_raw'),str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)

def build(owner, number):
    # Import only after preflight and baseline. No legacy entrypoint is executed.
    base = n.registry.root(owner)
    import dense
    dense.LOCAL, dense.TMP = base / 'r3', base / 'r3/work'
    import lattice
    lattice.common.LOCAL, lattice.common.TMP = dense.LOCAL, dense.TMP
    from chart import preview_half
    r2_path = base / 'cards' / f'R090000{number}.json'
    source_card = n.read(r2_path)
    source_dng = Path(source_card['dng_path'])
    n.require(n.sha(source_dng) == source_card['dng_sha256'], 'r2 DNG hash mismatch')
    source_tiff = n.Tiff(source_dng.read_bytes())
    template_path, template = n.template(owner)
    n.require(source_card['template_sha256'] == n.sha(template_path), 'r2 template mismatch')
    name = f'R000{9901+number:04d}'
    existing = base / 'r3/cards' / f'{name}.json'
    if existing.exists():
        card = n.read(existing)
        n.require(card['G3'] and card['G4'] and n.sha(card['dng_path']) == card['dng_sha256'] and
                  card['content_sha256'] == fingerprint(source_card), 'stale completed r3 card')
        refs = n.streams(template)[0]
        sizes = {k: v['bytes'] for k, v in card['native_streams'].items()}
        n.require(sizes['maker'] <= refs['maker']['capacity'] and sizes['full'] <= refs['full']['capacity'] and
                  sizes['raw'] <= MAX_RAW_BYTES, 'completed card fails size gates')
        if 'maker_preview' not in card:
            # The orchestrator already audited this unchanged HDF TEST artifact.
            n.require(n.registry.get(owner).get('legacy', {}).get('r3_card1') and number == 1 and sizes['maker'] == 18902,
                      'unrecognized legacy r3 card')
            card['maker_preview'] = dict(display_only=True, sigma_px=0, bytes=sizes['maker'],
                unfiltered_bytes=sizes['maker'], template_length_bound=refs['maker']['capacity'],
                fallback_template_original=False, smallest_fitting_sigma=True, relocated=False,
                attempts=[dict(sigma_px=0, bytes=sizes['maker'], fits=True,
                               sha256=card['native_streams']['maker']['sha256'])])
            card['size_gates'] = dict(passed=True, raw_bytes=sizes['raw'], raw_limit=MAX_RAW_BYTES,
                full_preview_bytes=sizes['full'], full_preview_limit=refs['full']['capacity'],
                full_preview_sigma_px=0, maker_bytes=sizes['maker'], maker_limit=refs['maker']['capacity'])
            n.dump(existing, card)
        print(owner, name, 'reuse completed G3/G4; DNG unchanged', flush=True)
        return existing
    chart = lattice.mosaic(source_card)
    raw_hash = n.digest(chart.astype('<u2').tobytes())
    n.require(raw_hash == source_card['raw_u16_sha256'], 'r2 intended chart hash differs')
    r2_raw = imagecodecs.ljpeg_decode(n.extract(source_tiff)['raw']).reshape(chart.shape)
    n.require(np.array_equal(r2_raw,chart), 'r2 decoded chart differs')
    del r2_raw
    work = n.output(base / 'r3/work' / name / 'placeholder').parent
    raw_input = n.output(work / 'intended.u16')
    chart.astype('<u2').tofile(raw_input)
    proof = base / 'r3/proof'
    raw_path = n.output(work/'raw.jpg')
    n.run('raw-encode',proof/'raw.original.jpg',raw_input,raw_path)
    blobs = dict(raw=raw_path.read_bytes())
    image = Image.fromarray(np.rint(preview_half(chart,source_card)*255).astype(np.uint8))
    refs, preview, maker = n.streams(template)
    for kind,size in [('full',source_card['geometry']['crop_wh'])]:
        pixels = image.resize(tuple(size),Image.Resampling.LANCZOS).tobytes()
        rgb = n.output(work/f'{kind}.rgb')
        rgb.write_bytes(pixels)
        packed = n.output(work/f'{kind}.jpg')
        n.run('jpeg-encode',proof/f'{kind}.original.jpg',rgb,packed)
        blobs[kind] = packed.read_bytes()
    blobs['maker'], maker_processing = encode_maker(
        image.resize(tuple(maker.entries[2].value), Image.Resampling.LANCZOS),
        proof / 'maker.original.jpg', work, refs['maker']['capacity'])
    size_gates = sanity(blobs, refs)
    old_blobs = n.extract(template)
    checks = {}
    for kind,blob in blobs.items():
        n.require(n.header(blob)[0] == n.header(old_blobs[kind])[0], f'G3 {kind} header changed')
        info,before = n.markers(blob),n.markers(old_blobs[kind])
        n.require(info['restart_count'] == before['restart_count'], f'G3 {kind} restart count')
        checks[kind] = dict(**info, header_byte_identical=True,restart_sequence_identical=True)
    raw_at=refs['raw']['offset']
    data=bytearray(template.data[:raw_at])
    mk_at=refs['maker']['offset']
    data[mk_at:mk_at+refs['maker']['capacity']] = blobs['maker']+b'\xff'*(refs['maker']['capacity']-len(blobs['maker']))
    thumb=template.segments(template.root)[0]
    old_thumb=source_tiff.segments(source_tiff.root)[0]
    n.require(thumb['capacity']==old_thumb['capacity']==57600,'thumbnail slot mismatch')
    data[thumb['offset']:thumb['offset']+thumb['capacity']] = source_tiff.data[old_thumb['offset']:old_thumb['offset']+old_thumb['capacity']]
    data.extend(blobs['raw'])
    raw_end=len(data)
    data.extend(b'\xff'*((-len(data))%256))
    full_at=len(data)
    data.extend(blobs['full'])
    for entry,value in [(template.raw.entries[279],len(blobs['raw'])),
                        (preview.entries[273],full_at),(preview.entries[279],len(blobs['full'])),
                        (maker.entries[3],len(blobs['maker']))]:
        n.write_uint(data,entry,0,value)
    destination=n.output(base/'r3/files'/f'{name}.DNG')
    destination.write_bytes(data)
    after=n.Tiff(data)
    n.require(template.signature()==after.signature() and template.geometry()==after.geometry(),'IFD graph/geometry changed')
    packed=n.extract(after)
    n.require(all(packed[k]==v for k,v in blobs.items()),'packed stream differs')
    decoded=n.output(work/'decoded.u16')
    n.run('raw-decode',raw_path,decoded)
    actual=np.fromfile(decoded,'<u2').reshape(chart.shape)
    n.require(np.array_equal(actual,chart),'G4 own decoder sample mismatch')
    independent=imagecodecs.ljpeg_decode(packed['raw']).reshape(chart.shape)
    n.require(np.array_equal(independent,chart),'G4 independent decoder sample mismatch')
    for kind in ('full','maker'):
        with Image.open(io.BytesIO(packed[kind])) as check:
            check.load()
    changes=allowed_ranges(template,data,blobs)
    diffs=diff_ranges(template.data,data,changes,base/'r3/diffs'/f'{name}.tsv.gz')
    apple_result=apple(destination)
    n.require([apple_result['width'],apple_result['height']]==source_card['geometry']['crop_wh'],'G4 Apple crop differs')
    card=copy.deepcopy(source_card)
    card.update(schema='gr-dense-r3-card/1',task='gr-dense-reference-r3',
                card_id='acceptance-38' if number==1 else f'dense-band-{number-1}',
                content_sha256=fingerprint(source_card),r2_card_number=number,r3_number=9901+number,
                r2_manifest=str(r2_path.relative_to(n.ROOT)),r2_manifest_sha256=n.sha(r2_path),
                r2_dng_sha256=n.sha(source_dng),template_path=str(template_path),
                dng_path=str(destination),dng_sha256=n.sha(destination),raw_u16_sha256=raw_hash,
                file_length_preserved=False,file_bytes=len(data),mutations=changes,
                native_streams=checks,maker_preview=maker_processing,size_gates=size_gates,
                raw_verification=dict(samples=int(chart.size),own_mismatches=0,
                  independent_mismatches=0,r2_mismatches=0,intended_u16_sha256=raw_hash),
                byte_differences=diffs,apple_raw=apple_result,
                layout=dict(raw_at=raw_at,raw_end=raw_end,pad_ff_bytes=full_at-raw_end,
                            preview_at=full_at,preview_end=len(data),file_ends_at_preview_eoi=True),
                privacy='same-owner',camera_handoff_tested=False,camera_acceptance=False,
                G3=True,G4=True,firmware_ready=False,deployable=False)
    path=base/'r3/cards'/f'{name}.json'
    n.dump(path,card)
    print(owner,name,'G3/G4 PASS',len(data),'bytes; maker',len(blobs['maker']),
          'sigma',maker_processing['sigma_px'],'fallback',maker_processing['fallback_template_original'],flush=True)
    return path

import imagecodecs

def compile_apple():
    subprocess.run(['clang','-O2','-Wno-deprecated-declarations',str(n.HERE/'apple_raw.m'),
                    '-framework','Foundation','-framework','CoreImage','-framework','ImageIO',
                    '-framework','CoreGraphics','-o',str(n.output(n.SCRATCH/'apple_raw'))],
                   check=True,capture_output=True)

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner',choices=tuple(n.registry.templates()))
    parser.add_argument('--work-root',type=Path)
    parser.add_argument('--card',type=int,choices=range(1,6))
    parser.add_argument('--proof-only',action='store_true')
    args=parser.parse_args()
    n.preflight()
    if args.work_root:
        n.require(args.owner, '--work-root requires --owner')
        n.registry.set_root(args.owner,args.work_root)
    n.compile_codec()
    compile_apple()
    owners=(args.owner,) if args.owner else tuple(n.registry.templates())
    for owner in owners:
        saved_proof(owner)
    if args.proof_only:
        return
    for owner in owners:
        for card in ((args.card,) if args.card else range(1,6)):
            build(owner,card)

if __name__=='__main__':
    main()
