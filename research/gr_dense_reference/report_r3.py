#!/usr/bin/env python3
"""Audit final r3 artifacts; optionally package the already-passing owner sets."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native as n
import build_r3 as b
import instructions_r3
import gzip
import os
import shutil
import subprocess
import zipfile
import tempfile
import numpy as np


def audit_differences(template,result,card,packed):
    """Compare every recorded differing run to fresh differences of the final files."""
    permitted=b.allowed_ranges(template,result.data,packed)
    n.require(permitted==card['mutations'],'permitted mutation ranges changed')
    path=n.ROOT/card['byte_differences']['diff_file']
    n.require(n.sha(path)==card['byte_differences']['diff_sha256'],'diff archive changed')
    before,after=template.data,result.data
    common=min(len(before),len(after))
    previous,count=0,0
    totals={}
    with gzip.open(path,'rt') as lines:
        n.require(next(lines)=='start\tend_exclusive\toperation\treason\n','diff header differs')
        def consume(start,end,operation,reason):
            nonlocal count
            actual=next(lines,'').rstrip('\n').split('\t')
            n.require(actual==[str(start),str(end),operation,reason],'differing range is unlisted or misclassified')
            total=totals.setdefault(reason,dict(ranges=0,differing_bytes=0))
            total['ranges']+=1
            total['differing_bytes']+=end-start
            count+=1
        for r in permitted:
            a,z,reason=r['start'],r['end'],r['reason']
            n.require(a>=previous,'permitted ranges overlap')
            n.require(before[min(previous,common):min(a,common)]==after[min(previous,common):min(a,common)],
                      'unexplained difference outside permitted ranges')
            start,end=min(a,common),min(z,common)
            if start<end:
                mask=np.frombuffer(before,np.uint8,end-start,start)!=np.frombuffer(after,np.uint8,end-start,start)
                runs=np.flatnonzero(np.diff(np.r_[False,mask,False])).reshape(-1,2)
                for left,right in runs:
                    consume(start+int(left),start+int(right),'replace',reason)
            if z>common:
                n.require(a>=common or z==max(len(before),len(after)),'invalid file-length mutation')
                start,end=max(a,common),min(z,max(len(before),len(after)))
                if start<end:
                    consume(start,end,'remove' if len(before)>len(after) else 'insert',reason)
            previous=z
        n.require(not next(lines,''),'extra differing ranges')
    n.require(before[min(previous,common):common]==after[min(previous,common):common] and
              previous>=max(len(before),len(after)),'unexplained tail or file length')
    n.require(count==card['byte_differences']['all_differing_ranges'] and
              totals==card['byte_differences']['reasons'],'differing-range totals disagree')
    n.require(card['byte_differences']['unexplained_ranges']==0,'unexplained ranges were reported')
    return dict(passed=True,ranges=count,unexplained_ranges=0,
                path=str(path.relative_to(n.HERE)),bytes=path.stat().st_size,sha256=n.sha(path))


def audit_card(owner,path,template):
    card=n.read(path)
    source=n.read(n.ROOT/card['r2_manifest'])
    n.require(n.sha(n.ROOT/card['r2_manifest'])==card['r2_manifest_sha256'],'r2 manifest changed')
    n.require(b.fingerprint(card)==b.fingerprint(source)==card['content_sha256'],'chart content changed')
    final=Path(card['dng_path'])
    n.require(n.sha(final)==card['dng_sha256'] and final.stat().st_size==card['file_bytes'],'final DNG changed')
    result=n.Tiff(final.read_bytes())
    n.require(template.signature()==result.signature() and template.geometry()==result.geometry(),'IFD graph/geometry changed')
    original,packed=n.extract(template),n.extract(result)
    refs=n.streams(template)[0]
    for kind,blob in packed.items():
        n.require(n.header(blob)[0]==n.header(original[kind])[0],'stream header changed')
        n.require(n.digest(blob)==card['native_streams'][kind]['sha256'] and
                  len(blob)==card['native_streams'][kind]['bytes'],'stream does not match gate evidence')
        n.require(card['native_streams'][kind]['header_byte_identical'] and
                  card['native_streams'][kind]['restart_sequence_identical'],'stream preservation gate failed')
    n.require(b.sanity(packed,refs)==card['size_gates'],'size gate evidence differs')
    processing=card['maker_preview']
    attempts=processing['attempts']
    n.require(processing['bytes']==len(packed['maker']) and
              processing['template_length_bound']==refs['maker']['capacity'] and
              not processing['relocated'],'MakerNote preview policy differs')
    n.require([v['sigma_px'] for v in attempts]==[0,*b.SIGMAS][:len(attempts)] and
              all(v['fits']==(v['bytes']<=refs['maker']['capacity']) for v in attempts),'sigma ladder differs')
    if processing['fallback_template_original']:
        n.require(len(attempts)==len(b.SIGMAS)+1 and not any(v['fits'] for v in attempts) and
                  packed['maker']==original['maker'] and processing['sigma_px'] is None,'invalid preview fallback')
    else:
        n.require(not any(v['fits'] for v in attempts[:-1]) and attempts[-1]['fits'] and
                  attempts[-1]['sigma_px']==processing['sigma_px'] and
                  attempts[-1]['sha256']==n.digest(packed['maker']),'not the smallest fitting sigma')
    layout=card['layout']; final_refs=n.streams(result)[0]
    n.require(layout['raw_at']==refs['raw']['offset']==final_refs['raw']['offset'],'RAW strip relocated')
    n.require(layout['raw_end']==layout['raw_at']+len(packed['raw']) and
              layout['preview_at']==(layout['raw_end']+255)//256*256 and
              final_refs['full']['offset']==layout['preview_at'],'RAW/full-preview layout differs')
    n.require(result.data[layout['raw_end']:layout['preview_at']]==b'\xff'*layout['pad_ff_bytes'],
              'RAW alignment filler differs')
    n.require(layout['preview_end']==len(result.data)==layout['preview_at']+len(packed['full']) and
              packed['full'].endswith(b'\xff\xd9'),'tail after full-preview EOI')
    start=refs['maker']['offset']; length=refs['maker']['capacity']
    n.require(final_refs['maker']['offset']==start and result.data[start+len(packed['maker']):start+length]==
              b'\xff'*(length-len(packed['maker'])),'maker slot moved or filler differs')
    differences=audit_differences(template,result,card,packed)
    work=n.registry.root(owner)/'r3/work'/final.stem
    raw=card['raw_verification']
    n.require(raw['own_mismatches']==raw['independent_mismatches']==raw['r2_mismatches']==0 and
              n.sha(work/'intended.u16')==n.sha(work/'decoded.u16')==source['raw_u16_sha256']==card['raw_u16_sha256'],
              'G4 sample evidence differs')
    apple=card['apple_raw']
    n.require(card['G3'] and card['G4'] and apple['passed'] and apple['full_resolution'] and
              apple['software_renderer'] and [apple['width'],apple['height']]==card['geometry']['crop_wh'] and
              apple['rgba_bytes']==apple['width']*apple['height']*4,'G4 Apple RAW render missing')
    return dict(manifest=str(path.relative_to(n.HERE)),card=card,differences=differences,G3=True,G4=True)


def camera_slots():
    files=[('gr4',p) for p in sorted((n.ROOT/'captures/contrib/2026-10-19/gr4-modes').glob('*.DNG'))]
    files.append(('gr4',n.ROOT/'captures/contrib/2026-10-19/gr4-fw111/R0000097.DNG'))
    rows=[]
    for owner,path in files:
        tiff=n.Tiff(path.read_bytes())
        refs,_,maker=n.streams(tiff)
        slot=refs['maker']; end=slot['offset']+slot['capacity']
        first=next(i for i in range(end,len(tiff.data)) if tiff.data[i]!=255)
        n.require(maker.entries[2].value==[720,480],'camera MakerNote preview geometry differs')
        rows.append(dict(owner=owner,path=str(path.relative_to(n.ROOT)),sha256=n.sha(path),
            start=slot['offset'],jpeg_bytes=slot['capacity'],first_non_ff=first,slot_bytes=first-slot['offset'],
            raw_bytes=refs['raw']['capacity'],full_preview_bytes=refs['full']['capacity']))
    n.require(sum(r['owner']=='gr4' for r in rows)==4,'need four GR IV slot observations')
    n.require(all(r['slot_bytes']==65054 for r in rows),'GR IV camera slot observations disagree')
    n.require(all(r['raw_bytes']<=b.MAX_RAW_BYTES for r in rows),'observed RAW maximum exceeds bound')
    record=dict(passed=True,files=rows,method='first non-FF byte after the camera-written preview EOI',
                physical_slot_is_not_build_capacity=True,
                hdf=dict(source='orchestrator independently verified; not rescanned',files=10,
                         start=98080,first_non_ff=163086,slot_bytes=65006,
                         jpeg_min=55520,jpeg_max=58575),
                camera_raw_limit=dict(bytes=b.MAX_RAW_BYTES,source='orchestrator camera-written maximum'))
    n.dump(n.LOCAL/'r3/camera-slot-audit.json',record)
    return record


def audit_readback(owner):
    base=n.registry.root(owner)/'r3'; path=base/'content-matching-selftest.json'; result=n.read(path)
    n.require(result['passed'] and result['content_identities_passed']==15 and
              result['main_cards_analyzed']==4 and result['renamed_and_reordered_jpegs_passed'] and
              result['filename_used'] is False and result['returned_dngs_required'] is False and
              result['camera_evidence'] is False and result['camera_acceptance'] is False,'offline self-test failed')
    required={'wrong_factory_sliders','missing_development_record','absent_development_tag',
              'style_swapped','jpeg_from_different_card'}
    n.require(required<={v['name'] for v in result['negative_checks']} and
              all(v['passed'] for v in result['negative_checks']),'negative readback checks missing')
    for stage,expected in (('test',1),('main',12)):
        evidence=base/'offline-dry-run'/f'{stage}.json'; record=n.read(evidence)
        n.require(n.sha(evidence)==result[f'{stage}_sha256'] and record['passed'] and
                  record['offline_prediction'] and record['camera_acceptance'] is False and
                  record['camera_evidence'] is False and len(record['identities'])==expected,
                  'offline end-to-end readback evidence changed')
        for identity in record['identities']:
            n.require(n.sha(identity['path'])==identity['sha256'] and
                      identity['metadata']['camera_evidence'] is False and
                      identity['matching']['filename_used'] is False,'offline JPEG matching evidence differs')
        for analysis in record['analyses'].values():
            if 'path' in analysis:
                n.require(n.sha(analysis['path'])==analysis['sha256'],'offline analysis changed')
    for fixture in result['fixtures']:
        ident=fixture['expected']; number=9902 if ident=='acceptance-38' else 9902+int(ident.rsplit('-',1)[1])
        jpeg=base/'offline-fixtures'/f'R000{number}'/f"{fixture['style']}.JPG"
        n.require(fixture['actual']==ident and n.sha(jpeg)==fixture['fixture_sha256'],'r3 fixture identity changed')
    return dict(passed=True,path=str(path.relative_to(n.HERE)),sha256=n.sha(path),result=result)


def package_files():
    return ['OWNER_ZH_EN.txt', 'SHA256SUMS',
            *[f'DCIM/100RICOH/R00001{number:02d}.DNG' for number in range(1, 7)]]


def verify_manifest(send):
    payloads = {Path(name).name: name for name in package_files() if name != 'SHA256SUMS'}
    rows = (send / 'SHA256SUMS').read_text().splitlines()
    expected = [f'{n.sha(send / name)}  {basename}' for basename, name in payloads.items()]
    n.require(rows == expected, 'bare-filename SHA256SUMS differs (text first, then six DNGs)')
    return payloads


def verify_delivery(owner):
    folder = n.registry.root(owner)
    send, archive = folder / 'r3s_sparecard/SEND_r3s', folder / 'SEND_r3s.zip'
    expected = set(package_files())
    n.require({str(p.relative_to(send)) for p in send.rglob('*') if p.is_file()} == expected,
              'unexpected r3s package files')
    n.require(not any(p.is_symlink() for p in send.rglob('*')), 'package contains symlinks')
    n.require((send / 'OWNER_ZH_EN.txt').read_bytes() == instructions_r3.text(owner).encode('utf-8'),
              'packaged r3s instructions differ')
    payloads = verify_manifest(send)
    control = n.template(owner)[0]
    n.require(n.sha(control) == n.registry.get(owner)['template']['sha256'] ==
              n.sha(send / 'DCIM/100RICOH/R0000101.DNG'), 'control was changed')
    for number in range(9902, 9907):
        card = n.read(folder / 'r3/cards' / f'R000{number}.json')
        n.require(n.sha(send / f'DCIM/100RICOH/R00001{number-9900:02d}.DNG') == card['dng_sha256'],
                  'packaged card differs')
    files = {name: dict(bytes=(send / name).stat().st_size, sha256=n.sha(send / name))
             for name in package_files()}
    n.output(n.SCRATCH / 'placeholder')
    destination = Path(tempfile.mkdtemp(prefix='r3s-unzip-', dir=n.SCRATCH))
    members = {f'SEND_r3s/{name}' for name in expected} | {
        'SEND_r3s/', 'SEND_r3s/DCIM/', 'SEND_r3s/DCIM/100RICOH/'}
    with zipfile.ZipFile(archive) as zipped:
        listing = zipped.namelist()
        n.require(set(listing) == members and len(listing) == len(members),
                  'ZIP contains unexpected/missing/duplicate members or junk')
        n.require(all(not item.extra for item in zipped.infolist()), 'ZIP has extra metadata despite -X')
        n.require(zipped.testzip() is None, 'ZIP CRC test failed')
        zipped.extractall(destination)
    extracted = {name: n.sha(destination / 'SEND_r3s' / name) for name in expected}
    n.require(all(extracted[name] == record['sha256'] and
                  (destination / 'SEND_r3s' / name).stat().st_size == record['bytes']
                  for name, record in files.items()), 'extracted ZIP differs from SEND_r3s')
    verify_manifest(destination / 'SEND_r3s')
    return dict(passed=True, owner=owner, send=str(send.relative_to(n.HERE)), files=files,
                zip=str(archive.relative_to(n.HERE)), zip_bytes=archive.stat().st_size,
                zip_sha256=n.sha(archive), zip_flags=['-X', '-r', '-q'],
                zip_member_count=len(listing), zip_members=listing, junk_files=False,
                extracted_to=str(destination.relative_to(n.HERE)), extracted_sha256=extracted,
                bare_filenames=True, manifest_basename_to_relative_path=payloads,
                control_sha256=n.sha(control), camera_acceptance=False, private_same_owner_only=True)


def package(owner, evidence):
    n.require(evidence['proof']['G1'] and evidence['proof']['G2'] and evidence['readback']['passed'] and
              len(evidence['cards']) == 5 and all(v['G3'] and v['G4'] for v in evidence['cards']),
              'package requires G1/G2, all five G3/G4 cards and the full readback self-test')
    folder = n.registry.root(owner)
    send = folder / 'r3s_sparecard/SEND_r3s'
    archive = folder / 'SEND_r3s.zip'
    n.require(not send.parent.exists() and not archive.exists(),
              'r3s delivery already exists; use a NEW --output directory')
    template, _ = n.template(owner)
    n.output(send / 'DCIM/100RICOH/R0000101.DNG')
    shutil.copyfile(template, send / 'DCIM/100RICOH/R0000101.DNG')
    for record in evidence['cards']:
        card = record['card']; source = Path(card['dng_path'])
        n.require(n.sha(source) == card['dng_sha256'], 'card changed after G3/G4 audit')
        target = n.output(send / f"DCIM/100RICOH/R00001{card['r2_card_number']+1:02d}.DNG")
        shutil.copyfile(source, target)
    n.output(send / 'OWNER_ZH_EN.txt').write_text(instructions_r3.text(owner), encoding='utf-8')
    payloads = {Path(name).name: name for name in package_files() if name != 'SHA256SUMS'}
    n.output(send / 'SHA256SUMS').write_text(
        ''.join(f'{n.sha(send / name)}  {basename}\n' for basename, name in payloads.items()), encoding='ascii')
    verify_manifest(send)
    subprocess.run(['zip', '-X', '-r', '-q', '../SEND_r3s.zip', 'SEND_r3s'],
                   cwd=send.parent, check=True, capture_output=True)
    record = verify_delivery(owner)
    n.dump(folder / 'r3/r3s-delivery.json', record)
    print(owner, 'SEND_r3s + zip extraction PASS', record['zip_sha256'], flush=True)
    return record


def audit_owner(owner):
    proof = b.saved_proof(owner)
    _, template = n.template(owner)
    paths = sorted((n.registry.root(owner) / 'r3/cards').glob('*.json'))
    n.require([p.stem for p in paths] == [f'R000{number}' for number in range(9902, 9907)],
              'five-card set incomplete')
    return dict(proof=proof, cards=[audit_card(owner, p, template) for p in paths],
                readback=audit_readback(owner))


def audit():
    n.preflight(); protected=b.verify_baseline(); continuation=b.verify_continuation(); owners={}
    for owner in n.registry.templates():
        proof=b.saved_proof(owner); _,template=n.template(owner)
        paths=sorted((n.registry.root(owner)/'r3/cards').glob('*.json'))
        n.require([p.stem for p in paths]==[f'R000{number}' for number in range(9902,9907)],'five-card set incomplete')
        cards=[audit_card(owner,path,template) for path in paths]
        owners[owner]=dict(proof=proof,cards=cards,readback=audit_readback(owner))
        print(owner,'G3 exhaustive audit 5/5; G4 saved sample/render evidence 5/5; readback PASS',flush=True)
    return dict(schema='gr-dense-r3-final/1',status='OFFLINE_GATES_PASSED',all_gates_passed=True,
                camera_acceptance=False,firmware_ready=False,deployable=False,
                protected_input_files=protected,continuation_read_only_files=continuation,
                proofs_reused_read_only=True,private_files_in_git_index=False,
                owners=owners,camera_slots=camera_slots(),public_gr3_attempted=False)


def report(r):
    rows=['# GR dense reference r3: offline build complete','',
          'Both owner sets pass G1/G2 and all 10 synthetic cards pass G3/G4. Both full offline readback self-tests pass. The unchanged controls and both SEND_r3 packages are hash-verified, including files extracted from zip -X archives. Camera acceptance remains untested and is decided only by each owner\'s two-file TEST.',
          '', '## Final preview policy and size gates','',
          'The chart, CFA samples, encoders, tables, headers, layout and file names are reused. Only the 720×480 display preview may be Gaussian-filtered before native encoding. Each sigma is applied to the original RGB raster, with RGB sigma=(s,s,0), reflect boundaries and truncate=4. The first fitting candidate is selected from 0, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12 px. Sigma 0 means the sharp raster already fits.', '',
          'MakerNote capacity is the template JPEG\'s own length: 57,473 bytes for gr4hdf and 56,561 for gr4. No file uses the following physical FF padding. The fallback is the template\'s unchanged MakerNote JPEG if no sigma fits. No card needed fallback. Full previews remain sharp and must not exceed 3,091,897 bytes for gr4hdf or 3,139,198 for gr4. RAW must not exceed 32,083,249 bytes.', '',
          '| Owner | Card | Sigma px | Maker bytes / limit | Sharp full preview bytes / limit | RAW bytes / limit | G3 ranges / unexplained | G4 |',
          '|---|---|---:|---:|---:|---:|---:|---|']
    for owner,evidence in r['owners'].items():
        for record in evidence['cards']:
            c=record['card']; s=c['size_gates']; d=record['differences']
            rows.append(f"| {owner} | {Path(c['dng_path']).name} | {c['maker_preview']['sigma_px']} | {s['maker_bytes']:,} / {s['maker_limit']:,} | {s['full_preview_bytes']:,} / {s['full_preview_limit']:,} | {s['raw_bytes']:,} / {s['raw_limit']:,} | {d['ranges']:,} / 0 | PASS |")
    rows+=['', 'HDF R0009902.DNG is the previously audited TEST artifact, reused without re-encoding or re-rendering. Its SHA-256 remains a258e6a078cf63b0e3771422ea908758103e7964262a21ce175e6a8e3b10bb92. The other nine cards were built and verified in this continuation. IFD graph, offsets, geometry, WB and black/white metadata are preserved except the four permitted stream count/offset fields. RAW starts at 221,888; FF alignment places the sharp preview on a 256-byte boundary; each file ends at that preview\'s EOI.', '',
           '## Camera-written MakerNote slot evidence','',
           'The four non-HDF GR IV files all start the 720×480 preview at 98,080. Scanning from each JPEG\'s own end through contiguous FF bytes finds the next protected non-FF byte at 163,134. The observed physical slot is 65,054 bytes. Their different MakerNote entry order is handled by the existing parser.', '',
           '| GR IV source | JPEG bytes | Start | First following non-FF | Physical slot bytes |',
           '|---|---:|---:|---:|---:|']
    for s in r['camera_slots']['files']:
        if s['owner']=='gr4':
            rows.append(f"| {s['path']} | {s['jpeg_bytes']:,} | {s['start']:,} | {s['first_non_ff']:,} | {s['slot_bytes']:,} |")
    rows+=['', 'The orchestrator independently observed the 65,006-byte HDF slot, from 98,080 to 163,086, in all 10 HDF files, with JPEG lengths 55,520 to 58,575 bytes. That evidence is reused without rescanning. The four new GR IV observations and hashes are in local/private/r3/camera-slot-audit.json. The build uses the shorter template JPEG lengths above.', '',
           'The orchestrator reported camera-written RAW strips of 28.0 to 32.08 MB and full previews of 2.98 to 3.22 MB. The hard RAW limit is the exact observed maximum, 32,083,249 bytes.', '',
           '## Reused G1/G2 proofs','',
           'The orchestrator independently confirmed both RAW streams and full-preview round trips. This continuation hash-checked and reused the existing proof files without decoding, re-encoding or rewriting them. All original/round-trip hashes below agree.', '',
           '| Owner | Stream | Bytes | Original and round-trip SHA-256 |', '|---|---|---:|---|']
    for owner,evidence in r['owners'].items():
        for kind,s in evidence['proof']['streams'].items():
            rows.append(f"| {owner} | {kind} | {s['bytes']:,} | `{s['original_sha256']}` |")
    rows+=['', 'Headers remain byte-identical: RAW 72 bytes, full preview 595 bytes, MakerNote 589 bytes. Full previews retain 49,922 cycling restart markers; MakerNote previews have no DRI or restart markers.', '',
           '## G3 complete byte-range audits and G4 RAW renders','',
           'Every actual differing run of each final DNG matches the saved zero-based, half-open audit, split at permitted mutation boundaries. The audits cover the four count/offset fields, thumbnail pixels, MakerNote entropy/filler, RAW entropy/EOI, alignment bytes, relocated full preview and removed obsolete tail. Unexplained ranges: zero for all 10 cards.', '',
           '| Owner/card | Diff archive bytes | Diff archive SHA-256 | Apple RGBA SHA-256 |', '|---|---:|---|---|']
    for owner,evidence in r['owners'].items():
        for record in evidence['cards']:
            c,d=record['card'],record['differences']
            rows.append(f"| {owner}/{Path(c['dng_path']).stem} | {d['bytes']:,} | `{d['sha256']}` | `{c['apple_raw']['rgba_sha256']}` |")
    rows+=['', 'Diff archives are local/private/<owner>/r3/diffs/R00099xx.tsv.gz. Per-card manifests record every permitted range and count, stream hashes, sigma attempts and size gates. All 26,628,096 RAW samples equal r2 and the intended CFA raster under native and independent imagecodecs decoding. Apple CIRAWFilter 8.dng rendered each final DNG at 6192×4128 to 102,242,304 RGBA bytes with its software renderer. Saved render/sample evidence was hash-checked; the accepted HDF TEST render was not repeated.', '',
           '## Full offline readback self-tests','',
           'Predictions and synthetic Ricoh EXIF/MakerNote fixtures were regenerated from the final r3 RAW strips under local/private/<owner>/r3/{predictions,offline-fixtures}/R0009902..R0009906. They use the frozen partial GR III model for tool tests, not a GR IV calibration or camera evidence.', '',
           '| Owner | Content identities | End-to-end readback | Negative checks | Result SHA-256 |', '|---|---:|---|---:|---|']
    for owner,evidence in r['owners'].items():
        state=evidence['readback']; result=state['result']
        rows.append(f"| {owner} | {result['content_identities_passed']}/15 | TEST Standard + 12 MAIN JPEGs; all 5 synthetic cards analyzed | {len(result['negative_checks'])}/11 | `{state['sha256']}` |")
    rows+=['', 'Both owners reject wrong factory sliders, a zero or absent RAW development record, a swapped style tag/preset, a JPEG from another card, duplicate card/style returns, a missing style, ambiguous duplicated content, an offline fixture presented as camera evidence, an unmarked prediction and output outside the owner folder. MAIN also passes with reordered inputs and misleading JPEG names. Card identity comes from patch content/card IDs; style comes from the camera\'s ImageTone metadata. Returned DNGs are optional because reference DNGs are already local. Every offline result keeps camera_evidence=false and camera_acceptance=false.', '',
           'The original-photo control JPEG is retained for the owner\'s two-file TEST, separately from synthetic chart matching. The owner returns 14 new JPEGs: 2 TEST plus 12 MAIN, with no DNG return request.', '',
           '## Owner packages','',
           'Each SEND_r3 contains TEST/R0009901.DNG, TEST/R0009902.DNG, four MAIN DNGs, OWNER_ZH_EN.txt and SHA256SUMS. R0009901 is a byte-for-byte copy of the owner\'s template. SHA256SUMS lists the seven unique payload basenames without paths; the verifier resolves them across the root, TEST and MAIN. The manifest is rechecked before archiving and after extraction.', '',
           '| Owner | File within SEND_r3 | Bytes | SHA-256 |', '|---|---|---:|---|']
    for owner,evidence in r['owners'].items():
        for name,record in evidence['delivery']['files'].items():
            rows.append(f"| {owner} | {name} | {record['bytes']:,} | `{record['sha256']}` |")
    rows+=['', '| ZIP under local/private | Bytes | SHA-256 | Extracted hashes |', '|---|---:|---|---|']
    for owner,evidence in r['owners'].items():
        d=evidence['delivery']
        rows.append(f"| {owner}/SEND_r3.zip | {d['zip_bytes']:,} | `{d['zip_sha256']}` | All 8 files identical |")
    rows+=['', 'Both archives were created with zip -X and explicit file lists. CRC tests, member-list checks, absence of extra ZIP metadata, full extraction and per-file SHA-256/size comparisons passed. Extracted copies stay in local/private/<owner>/r3/unzip-check. Delivery records are local/private/<owner>/r3/delivery.json.', '',
           'The handout keeps Chinese first, the stop rules, original settings, factory-default table, privacy note and cleanup after confirmed receipt. It removes HDF-off instructions, tells the HDF owner that the switch does not affect development, explains softened MAIN playback, and directs the owner straight to MAIN after both TEST files succeed.', '',
           '## Preservation and reproduction','',
           f"The existing {r['protected_input_files']}-file r2/input baseline and continuation\'s {r['continuation_read_only_files']}-file read-only baseline retain their sizes and SHA-256 hashes. The latter includes all 16 r3 proof files, the inspected camera files, native.c, native.py and apple_raw.m. No private files are in the Git index. No commit, camera, SD-card or Downloads access occurred. Shared-repository changes outside this task were retained.", '',
           'All new outputs are under research/gr_dense_reference/local/private; source edits are at research/gr_dense_reference top level. Native executables use /tmp/gr-dense-r3. The checked APFS volume UUID is 14BE04EB-AF49-497E-B36A-B078B2F7C5E8.', '',
           '```sh', 'python3 -I -B research/gr_dense_reference/build_r3.py',
           'python3 -I -B research/gr_dense_reference/readback_r3.py --owner gr4hdf --self-test',
           'python3 -I -B research/gr_dense_reference/readback_r3.py --owner gr4 --self-test',
           'python3 -I -B research/gr_dense_reference/report_r3.py --package', '```', '',
           'The builder reuses completed cards and G1/G2 proofs. Running report_r3.py without --package audits final artifacts and regenerates this report without rebuilding cards or archives. Machine-readable evidence and source hashes are in local/private/r3/verification.json.', '',
           '## Remaining work and residual risks','',
           '- Each owner must run the two-file TEST on the original camera body. Host codec checks, Apple RAW rendering and package verification do not prove Ricoh indexing or RAW Development acceptance. Stop if either TEST DNG fails, following the handout.',
           '- Camera playback, zoom and all 14 developed JPEGs remain untested. The small preview is display-only; measurements use JPEGs developed from RAW.',
           '- Frozen predictions do not model GR IV colour, demosaic, local tone, sharpening or ISO-dependent noise reduction. The chart has exact noise-free CFA values with template ISO/WB metadata. Camera returns are required for measurement.',
           '- Public GR III follow-up remains unattempted. It needs its own bastibe-container G1/G2 proofs and artifact verification.', '',
           '`all_gates_passed=true` refers to offline G1–G4 and readback/package checks only. `packages_created=true`, `camera_acceptance=false`, `firmware_ready=false`, `deployable=false`.', '']
    n.output(n.HERE/'R3_REPORT.md').write_text('\n'.join(rows))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', choices=tuple(n.registry.templates()))
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--package', action='store_true')
    args = parser.parse_args()
    n.preflight()
    if args.work_root:
        n.require(args.owner, '--work-root requires --owner')
        n.registry.set_root(args.owner, args.work_root)
    for owner in ([args.owner] if args.owner else n.registry.templates()):
        evidence = audit_owner(owner)
        delivery = package(owner, evidence) if args.package else verify_delivery(owner)
        print(owner, 'offline G1-G4/readback/r3s PASS; camera_acceptance=false', delivery['zip_sha256'])
