#!/usr/bin/env python3
"""Read-only artifact review; all derived bytes and logs stay in local/."""
import hashlib
import importlib.util
import json
import pathlib
import plistlib
import re
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
OFFICIAL = 'artifacts/firmware/gxr-1.51/ilaunch3'
CANDIDATE = 'firmware/image_v3/local/candidate-v3/candidate/SD_ROOT/ilaunch3'
STAGE = 'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/ilaunch3'
ELF = 'firmware/resident_v3/local/resident/build/resident.elf'
ENABLED = (1, 2, 5, 6, 7, 8, 9)


def save(name, value):
    (LOCAL / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def preflight():
    v = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert v['MountPoint'] == '/Volumes/Workspace' and v['FilesystemType'] == 'apfs'
    assert v['WritableVolume'] and v['WritableMedia']
    assert HERE == ROOT / 'research/review_flash_v3'
    p = subprocess.run(['git', 'check-ignore', '-v', str(LOCAL / 'check')], cwd=ROOT,
                       text=True, capture_output=True, check=True)
    assert 'research/review_flash_v3/.gitignore:1:/local/' in p.stdout


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def elf_parse(data):
    assert data[:7] == b'\x7fELF\x01\x02\x01'
    off = struct.unpack_from('>I', data, 32)[0]
    width, count, names = struct.unpack_from('>HHH', data, 46)
    rows = [struct.unpack_from('>10I', data, off+i*width) for i in range(count)]
    names_data = data[rows[names][4]:rows[names][4]+rows[names][5]]
    def string(buf, i):
        return buf[i:buf.index(0, i)].decode()
    sections = {string(names_data, s[0]): dict(type=s[1], flags=s[2], va=s[3], offset=s[4], size=s[5]) for s in rows}
    symbols = {}
    for s in rows:
        if s[1] != 2:
            continue
        st = rows[s[6]]
        strings = data[st[4]:st[4]+st[5]]
        for pos in range(s[4], s[4]+s[5], 16):
            n, v, z, info, other, si = struct.unpack_from('>IIIBBH', data, pos)
            if n:
                symbols[string(strings, n)] = dict(va=v, size=z, info=info, section=si)
    return sections, symbols


def collect():
    inputs = json.loads((LOCAL / 'inputs-before.json').read_text())
    files = [OFFICIAL, CANDIDATE, STAGE, ELF]
    files += [str(p.relative_to(ROOT)) for parent in ('resident', 'engine_services')
              for p in (ROOT / 'firmware/resident_v3' / parent).rglob('*') if p.is_file()]
    files += ['firmware/resident_v3/local/hooks.json', 'firmware/resident_v3/local/patch-manifest.json',
              'firmware/resident_v3/local/resident/build/resident.map',
              'firmware/resident_v3/local/resident/linked_hooks.S',
              'firmware/resident_v3/local/resident/target-layout.json',
              'firmware/resident_v3/local/resident/engine-services/services-linkcheck.elf',
              'firmware/resident_v3/local/stack.json',
              'firmware/resident_v3/local/product/m32r-lto/engine.elf',
              'firmware/resident_v3/containers/product/adapter.c',
              'firmware/resident_v3/containers/probes/engine.c',
              'research/review_flash_v2/review.py', 'research/review_flash_v2/local/m32r_replay.py',
              'research/review_flash_v2/local/review_behaviour.c']
    files += ['firmware/resident_v3/local/probes/build/'+name+'/engine.elf' for name in ('life','notice','view')]
    files += [str(p.relative_to(ROOT)) for p in (ROOT / 'firmware/resident_v3/local').rglob('GXRCE.DAT')
              if '/candidates/' in str(p)]
    files += [str(p.relative_to(ROOT)) for p in (ROOT / 'firmware/resident_v3/local/resident').rglob('*.su')]
    for rel in sorted(set(files)):
        p = ROOT / rel
        raw = p.read_bytes()
        rec = dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if rel in inputs:
            assert inputs[rel] == rec, rel
        inputs[rel] = rec
        dest = LOCAL / 'frozen' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            assert dest.read_bytes() == raw, rel
        else:
            dest.write_bytes(raw)
    save('inputs-before.json', inputs)
    orig, cand, stage, elf = [(LOCAL / 'frozen' / r).read_bytes() for r in (OFFICIAL, CANDIDATE, STAGE, ELF)]
    assert hashlib.sha256(cand).hexdigest() == '104637a935c66e4087d8ab2884a17f308840e11bf27a91652596df1a8871dbe9'
    sections, symbols = elf_parse(elf)
    save('elf.json', dict(sections=sections, symbols=symbols))
    segments = []
    for i in range(16):
        src, va, size, bss, bsize = struct.unpack_from('>5I', orig, 0x20+20*i)
        assert src+512+size <= len(orig)
        segments.append(dict(index=i, offset=src+512, va=va, size=size, bss=bss, bss_size=bsize))
    save('segments.json', segments)
    def mapped(va, n):
        hits = [s for s in segments if s['va'] <= va and va+n <= s['va']+s['size']]
        assert len(hits) == 1, hex(va)
        return hits[0]['offset']+va-hits[0]['va']
    hooks = json.loads((ROOT / 'firmware/resident_v3/local/hooks.json').read_text())
    inventory = []
    for h in hooks:
        n, a, z = h['number'], int(h['va'], 16), h['length']
        off = mapped(a, z)
        assert orig[off:off+z].hex() == h['original_bytes']
        item = dict(number=n, id=h['id'], va=a, length=z, offset=off,
                    original=orig[off:off+z].hex(), candidate=cand[off:off+z].hex(),
                    stage2l=stage[off:off+z].hex(), changed=cand[off:off+z] != orig[off:off+z])
        assert item['changed'] == (n in ENABLED)
        if n in ENABLED:
            w = int.from_bytes(cand[off:off+4], 'big')
            assert w >> 24 == 0xff
            d = w & 0xffffff
            if d & 0x800000:
                d -= 1 << 24
            target = (a & ~3) + 4*d
            assert target == symbols[f'rv_hook_{n:02}']['va']
            pos = sections['.payload']['offset'] + target - sections['.payload']['va'] + 16
            assert elf[pos:pos+z] == orig[off:off+z]
            sw = int.from_bytes(stage[off:off+4], 'big')
            if n in (1, 5):
                starget = ((sw & 65535) << 16) | (int.from_bytes(stage[off+4:off+8], 'big') & 65535)
                skind = 'absolute_call' if n == 1 else 'data_pointer'
            elif n == 2:
                sd = sw & 255
                if sd & 128:
                    sd -= 256
                starget, skind = (a & ~3)+4*sd, 'short_branch'
            else:
                assert sw >> 24 == 0xff
                sd = sw & 0xffffff
                if sd & 0x800000:
                    sd -= 1 << 24
                starget, skind = (a & ~3)+4*sd, 'bra24'
            item.update(target=target, replay=elf[pos:pos+z].hex(), resume=a+z,
                        stage2l_target=starget, stage2l_kind=skind)
        inventory.append(item)
    save('hooks.json', inventory)
    patch_rows = json.loads((ROOT / 'firmware/resident_v3/local/patch-manifest.json').read_text())
    assert len(patch_rows) == len(inventory) == 37
    for h, p in zip(inventory, patch_rows):
        assert p['hook'] == 'H%02d' % h['number'] and int(p['address'],16) == h['va']
        assert p['original'] == h['original'] and p['replacement'] == h['candidate']
        if p['stage2l_reference'] is None:
            assert h['number'] > 9 and h['stage2l'] == h['original']
        else:
            assert p['stage2l_reference'] == h['stage2l']
        assert p['enabled'] == (h['number'] <= 9)
    for name in ('.payload', '.root_pins'):
        s = sections[name]; pos = mapped(s['va'], s['size'])
        assert cand[pos:pos+s['size']] == elf[s['offset']:s['offset']+s['size']]
    assert cand[mapped(0x20054700, 244):mapped(0x20054700, 244)+244] == bytes([255])*244
    checks = {}
    for name, raw in [('official', orig), ('candidate', cand), ('stage2l', stage)]:
        weighted = sum(sum(raw[512+i::6])*(i+2) for i in range(6)) & 0xffffffff
        stored = int.from_bytes(raw[0x16c:0x170], 'big')
        assert weighted == stored
        checks[name] = dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), checksum=weighted)
    checks['root_initial_ff_bytes'] = 244
    checks['removed_symbols'] = [k for k in symbols if re.match(r'rv_(post_|notify|epochs)', k)]
    assert not checks['removed_symbols']
    save('identity.json', checks)
    out = LOCAL / 'disasm'; out.mkdir(exist_ok=True)
    commands = []
    def dump(args, dest):
        cmd = [str(OBJDUMP), *map(str, args)]
        with dest.open('w') as fd:
            p = subprocess.run(cmd, stdout=fd, stderr=subprocess.PIPE, text=True)
        commands.append(dict(argv=cmd, output=str(dest.relative_to(HERE)), returncode=p.returncode, stderr=p.stderr))
        assert p.returncode == 0, p.stderr
    dump(['-d', LOCAL / 'frozen' / ELF], out / 'resident.txt')
    for s in segments:
        p = out / f'official-{s["index"]:02}.bin'
        p.write_bytes(orig[s['offset']:s['offset']+s['size']])
        dump(['-D', '-b', 'binary', '-m', 'm32r', '-EB', f'--adjust-vma={s["va"]}', p], p.with_suffix('.txt'))
    for name, raw in [('candidate', cand), ('stage2l', stage)]:
        for h in inventory:
            if not h['changed']:
                continue
            target = h['target'] if name == 'candidate' else h['stage2l_target']
            site = out / f'{name}-site-h{h["number"]:02}.bin'
            site.write_bytes(raw[h['offset']:h['offset']+h['length']])
            dump(['-D', '-b', 'binary', '-m', 'm32r', '-EB', f'--adjust-vma={h["va"]}', site], site.with_suffix('.txt'))
            p = out / f'{name}-h{h["number"]:02}.bin'
            pos = mapped(target, 128)
            p.write_bytes(raw[pos:pos+128])
            if name == 'candidate' or h['stage2l_kind'] != 'data_pointer':
                dump(['-D', '-b', 'binary', '-m', 'm32r', '-EB', f'--adjust-vma={target}', p], p.with_suffix('.txt'))
    save('commands.json', commands)
    print(json.dumps(dict(frozen_inputs=len(inputs), executed_hooks=len(ENABLED), checksums=checks)))


def xrefs():
    # Audited previous read-only scanner, operating on this review's fresh dumps.
    m = module(LOCAL / 'frozen/research/review_flash_v2/review.py', 'review_v2_scanner')
    m.HERE, m.ROOT, m.LOCAL = HERE, ROOT, LOCAL
    m.xref()
    m.tables()


def verify():
    before = json.loads((LOCAL / 'inputs-before.json').read_text())
    changes = [rel for rel, rec in before.items()
               if not (ROOT / rel).is_file() or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != rec['sha256']]
    save('inputs-verification.json', dict(files=len(before), unchanged=not changes, changed=changes))
    assert not changes, changes
    status = subprocess.check_output(['git','-c','core.fsmonitor=false','--no-optional-locks',
                                     'status','--short','--untracked-files=normal'], cwd=ROOT, text=True)
    (LOCAL/'git-status-final.txt').write_text(status)
    initial = (LOCAL/'git-status-initial.txt').read_text()
    assert status == initial, 'shared checkout status changed; inspect initial/final logs'
    ignore = subprocess.check_output(['git','check-ignore','-v','research/review_flash_v3/local/check'],cwd=ROOT,text=True)
    (LOCAL/'git-check-ignore-final.log').write_text(ignore)
    links = re.findall(r'\]\(([^)]+)\)',(HERE/'REPORT.md').read_text())
    broken = []
    for target in links:
        path = re.sub(r':\d+$','',target.split('#',1)[0])
        if path and path not in ('SHA256SUMS','local/delivery-validation.json') and not (HERE/path).exists():
            broken.append(target)
    assert not broken, broken
    assert all(not p.is_symlink() for p in HERE.rglob('*'))
    save('delivery-validation.json',dict(protected_inputs=len(before),changed_inputs=changes,
         git_status_matches_initial=True,report_links_checked=len(links),broken_links=broken,
         local_ignored=ignore.strip(),outputs_scope='research/review_flash_v3/',
         camera_accessed=False,sd_accessed=False,firmware_built=False,source_modified=False,
         subagents_started=False,commit_or_push=False,
         evidence_limits='Final bytes and host doubles only; native device acceptance and whole-task stack bounds remain unknown.'))
    print('READ_ONLY_INPUTS_UNCHANGED', len(before))


if __name__ == '__main__':
    preflight()
    if sys.argv[1:] == ['collect']:
        collect()
    elif sys.argv[1:] == ['xrefs']:
        xrefs()
    elif sys.argv[1:] == ['verify']:
        verify()
    else:
        raise SystemExit('usage: review.py collect|xrefs|verify')
