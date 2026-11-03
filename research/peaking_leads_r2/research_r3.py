#!/usr/bin/env python3
"""Recheck retained evidence and extend bounded offline register studies."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/r3'
READS = {}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    READS[str(path.relative_to(ROOT))] = digest(data)
    return data


def put(name, obj):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else
                    json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def load_file(path, name):
    read(path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def context():
    c = load_file(HERE / 'collect.py', 'retained_collect')
    s = c.S
    s.read = read
    a = s.load_prior()
    unit = a.Listing(s.Image('jlaunch3'))
    body = a.Listing(s.Image('ilaunch3'))
    return a, c, unit, body


def excerpt(lines, lo, hi, tag):
    rows = []
    for va in sorted(lines.rows):
        if lo <= va < hi:
            n, asm, raw, source, number = lines.get(va)
            rows.append(f'{va:08x} file={lines.image.offset(va):#x} '
                        f'{raw.hex(" ")}  {asm}  [{source}:{number}]')
    assert rows, tag
    put('evidence/' + tag + '.txt',
        f'# {lines.image.name} SHA256 {digest(lines.image.data)}\n' +
        '\n'.join(rows) + '\n')
    return {'tag': tag, 'image': lines.image.name, 'lo': hex(lo),
            'hi': hex(hi), 'rows': len(rows)}


def retained_check(unit, body):
    images = {x.image.name: x.image for x in (unit, body)}
    result = {}
    for path in sorted((HERE / 'local/evidence').glob('*.txt')):
        text = read(path).decode()
        first = text.splitlines()[0].split()
        image = images[first[1]]
        assert first[-1] == digest(image.data), path
        count = 0
        for line in text.splitlines()[1:]:
            match = re.match(r'^([0-9a-f]+) file=(0x[0-9a-f]+) '
                             r'((?:[0-9a-f]{2} )+) ', line)
            assert match, (path, line)
            va, off = int(match[1], 16), int(match[2], 16)
            raw = bytes.fromhex(match[3])
            assert image.offset(va) == off
            assert image.bytes(va, len(raw)) == raw
            count += 1
        result[str(path.relative_to(ROOT))] = count
    put('retained_check.json', result)
    return result


def scan_constants(lines):
    keys = sorted(lines.rows)
    positions = [i for i, va in enumerate(keys)
                 if re.search(r'\bseth \w+,#0xf03[56]\b',
                              lines.rows[va][1], re.I)]
    selected = set()
    for i in positions:
        selected.update(keys[max(0, i-5):i+15])
    rows = []
    for va in sorted(selected):
        n, asm, raw, source, number = lines.get(va)
        rows.append(f'{va:08x} file={lines.image.offset(va):#x} '
                    f'{raw.hex(" ")}  {asm}  [{source}:{number}]')
    put('scans/' + lines.image.name + '-f035.txt', '\n'.join(rows) + '\n')
    constants = []
    for off, base, size in lines.image.sections:
        for pos in range(off, off+size-3, 4):
            word = struct.unpack_from('>I', lines.image.data, pos)[0]
            if 0xF0350000 <= word < 0xF0360000:
                constants.append({'file': hex(pos), 'va': hex(base+pos-off),
                                  'word': hex(word)})
    put('scans/' + lines.image.name + '-words.json', constants)
    return {'high_half_hits': len(positions), 'context_rows': len(rows),
            'aligned_constants': len(constants)}


def analyze():
    a, c, unit, body = context()
    verified = retained_check(unit, body)
    defaults, origins = a.script()
    saved = json.loads(read(HERE / 'local/cpu_results.json'))
    prior = json.loads(read(ROOT / 'research/peaking_color/local/register_reconstruction.json'))
    rebuilt = {}
    bases = {}
    for mode in (1, 2):
        base = c.model(a, unit, defaults, mode)
        fast = c.model(a, unit, defaults, mode, fast=True)
        assert base.mmio == {int(k,16):int(v,16) for k,v in
                             prior[f'mode{mode}']['full_registers'].items()}
        assert all(base.mmio[k] == v for k,v in fast.mmio.items())
        bases[mode] = base
        rebuilt[f'mode{mode}'] = {'full_words':len(base.mmio),
                                  'fast_words':len(fast.mmio)}
        for name, changes in [
            ('ramp_node', {0x20024402: bytes([0x3F])}),
            ('block_first', {0x20022B5C: bytes([0x40])}),
            ('block_second', {0x20022BAC: bytes([0x40])})]:
            rebuilt[f'mode{mode}_{name}'] = c.diff(base, c.model(
                a, unit, defaults, mode, changes=changes))
        for field, value in [(0,1),(1,1),(0x25,1),(0x25,4),(0x25,7),
                             (0x29,1),(0x29,2),(0x2A,1),(0x2B,1)]:
            rebuilt[f'mode{mode}_f{field:02x}_{value}'] = c.diff(base,
                c.model(a, unit, defaults, mode, extra_f={field:value}))
    assert rebuilt == saved
    put('cpu_recheck.json', rebuilt)

    ranges = [
        (unit,0x201161B4,0x201162C0,'mode-limits'),
        (unit,0x201163C8,0x20116438,'mode-scalar'),
        (unit,0x2011659C,0x20116674,'mode-fast-fields'),
        (unit,0x201179A0,0x20117AF8,'ramp-source'),
        (unit,0x20117C2C,0x20117DD8,'block-source'),
        (unit,0x20111B00,0x20111C80,'mode-full-fields'),
        (unit,0x201104A0,0x20110598,'general-control'),
        (unit,0x2010E998,0x2010EBE0,'ramp-caller'),
        (unit,0x2024296C,0x20242B68,'address-reader-state'),
        (unit,0x20242D88,0x20242DC8,'word-half-write'),
        (unit,0x20243034,0x20243178,'address-page'),
        (body,0x201D709C,0x201D7440,'body-colour-draw'),
        (body,0x20218C20,0x20218F30,'body-display-flow'),
    ]
    windows = [excerpt(*row) for row in ranges]
    put('evidence_index.json', windows)

    sources = {}
    for va, n in [(0x2012EF68,160),(0x2012D58C,1536),
                  (0x2012DB8C,1536),(0x2012F01A,256)]:
        sources[hex(va)] = {'file':hex(unit.image.offset(va)),
                             'data':unit.image.bytes(va,n).hex(' ')}
    sources['t'] = {}
    for lo,n in [(0x0B4C,96),(0x0BAC,24),(0x0C00,72),
                 (0x2400,16),(0x3B00,20)]:
        assert all(i in defaults for i in range(lo,lo+n))
        sources['t'][hex(lo)] = {
            'data':bytes(defaults[i] for i in range(lo,lo+n)).hex(' '),
            'origins':[origins[i] for i in range(lo,lo+n)]}
    put('sources.json', sources)

    study = {}
    for field,limit in [(0x25,11),(0x29,17),(0x2A,17)]:
        rows = {}
        for value in range(limit):
            vm = c.model(a,unit,defaults,1,extra_f={field:value})
            rows[str(value)] = c.diff(bases[1],vm)
        study[f'f{field:02x}'] = rows
    for label,offset,value in [('ramp_mid',0x2408,0x60),
                               ('first_tail',0x0B5C,0x40),
                               ('second_tail',0x0BBC,0x20)]:
        study[label] = {str(mode):c.diff(bases[mode],c.model(a,unit,defaults,mode,
            changes={0x20022000+offset:bytes([value])})) for mode in (1,2)}
    study['mode_bytes'] = {}
    for mode in (1,2):
        lo = 0x3B00 if mode == 1 else 0x3B0A
        for i in range(10):
            value = defaults[lo+i] ^ 1
            changed = dict(defaults); changed[lo+i] = value
            vm = c.model(a,unit,changed,mode)
            study['mode_bytes'][f'{mode}:{i}'] = c.diff(bases[mode],vm)
    put('scalar_studies.json', study)
    summary = {'retained_files':len(verified),'retained_rows':sum(verified.values()),
               'r2_models_equal':len(rebuilt),'new_windows':len(windows),
               'new_window_rows':sum(x['rows'] for x in windows),
               'scans':{x.image.name:scan_constants(x) for x in (unit,body)}}
    put('summary.json', summary)
    put('reads.json', READS)
    print(json.dumps(summary))


def detail():
    a, c, unit, body = context()
    x = load_file(HERE/'xref.py','retained_xref')
    for rel in ['research/isp_pipeline/REPORT.md',
                'research/isp_pipeline/hardware_types.json',
                'firmware/stage2j/deep_isp.c',
                'research/peaking_probe/操作说明.md']:
        read(ROOT/rel)
    descriptors = {}
    for typ,writer,table in [(27,0x20257490,0x2029C66C),
                              (32,0x20257690,0x2029C720)]:
        found_writer = int.from_bytes(unit.image.bytes(0x2029C194+typ*4,4),'big')
        found_table = int.from_bytes(unit.image.bytes(0x2029DA8C+typ*4,4),'big')
        assert (found_writer,found_table) == (writer,table)
        descriptors[str(typ)] = {'writer':hex(writer),'descriptor':hex(table),
                                 'first_word':hex(int.from_bytes(unit.image.bytes(table,4),'big'))}
    put('descriptors.json',descriptors)
    refs = {}
    for lines, targets in [
        (unit,[0x20383F64,0x20118800,0x20105020,0x2025D5F0,
               0x20242B28,0x20242B38,0x20242B48,0x20242B58]),
        (body,[0x201BA796,0x201BE074,0x201D7EC0])]:
        found = x.references(lines,set(targets))
        pointers = {hex(t):[] for t in targets}
        for off,base,size in lines.image.sections:
            for pos in range(off,off+size-3,4):
                word = struct.unpack_from('>I',lines.image.data,pos)[0]
                if word in targets:
                    pointers[hex(word)].append({'file':hex(pos),
                                               'va':hex(base+pos-off)})
        refs[lines.image.name] = {'constructions':found,'aligned_words':pointers}
    put('references/detail.json',refs)
    windows = [
        (unit,0x20115B58,0x20115E80,'filter-wrapper'),
        (unit,0x20118800,0x20118C20,'auxiliary-filter'),
        (unit,0x20111AD0,0x20111B40,'mode-auxiliary-destination'),
        (unit,0x20110E10,0x20110E70,'mode-structure-choice'),
        (unit,0x2025764C,0x20257690,'type29-control'),
        (unit,0x20108DAC,0x20108F68,'type33-control'),
        (unit,0x20255740,0x20255884,'native-partial-write'),
        (body,0x201BE074,0x201BE134,'body-buffer-choice'),
        (body,0x201D7EC0,0x201D7F3C,'body-pixel-colour'),
        (body,0x20062750,0x20062840,'body-byte-fill'),
        (body,0x201AE780,0x201AE7F0,'histogram-message'),
    ]
    index = [excerpt(*row) for row in windows]
    put('detail_index.json',index)
    values = {}
    for va,n in [(0x20246158,20),(0x2013E558,16),(0x20383F08,96)]:
        try:
            values[hex(va)] = {'file':hex(unit.image.offset(va)),
                              'data':unit.image.bytes(va,n).hex(' ')}
        except ValueError:
            values[hex(va)] = {'mapped':False}
    put('initial_state.json',values)
    prior = json.loads((OUT/'reads.json').read_text())
    for rel,value in READS.items():
        assert rel not in prior or prior[rel] == value,rel
    put('reads.json',{**prior,**READS})
    print(json.dumps({'windows':len(index),'rows':sum(x['rows'] for x in index),
                      'reference_targets':sum(len(r['constructions']) for r in refs.values()),
                      'initial_state':values}))


def probes():
    a, c, unit, body = context()
    defaults, origins = a.script()
    study = {}
    for tag,addr,off,original,changed in [
        ('P2',0xF0353350,0,0x80808080,0x40808080),
        ('P3',0xF0353300,2,0x00800080,0x00800060)]:
        rows = []
        for old,new in [(original,changed),(changed,original)]:
            vm = a.Arithmetic(unit,defaults)
            for i,value in enumerate(old.to_bytes(4,'big')):
                vm.mem[addr+i] = value
            vm.put('r4',addr+off)
            vm.put('r5',(new >> (16 if off == 0 else 0)) & 65535)
            vm.run(0x20242D98)
            assert vm.mmio == {addr:new}
            rows.append({'before':hex(old),'after':hex(new),
                         'writes':{hex(k):hex(v) for k,v in vm.mmio.items()}})
        study[tag] = {'helper':hex(0x20242D98),'round_trip':rows}
    study['P1'] = {}
    for mode in (1,2):
        base = c.model(a,unit,defaults,mode)
        alt = c.model(a,unit,defaults,mode,
                      changes={0x2012EBE0:bytes([0x7F,0xFF])})
        fast = c.model(a,unit,defaults,mode,
                       changes={0x2012EBE0:bytes([0x7F,0xFF])},fast=True)
        delta = c.diff(base,alt)
        assert delta == ({'0xf035311c':['0xff00ff','0x7f00ff']} if mode == 1 else {})
        assert all(alt.mmio[k] == v for k,v in fast.mmio.items())
        study['P1'][f'mode{mode}'] = delta
    study['P1']['source'] = {'va':'0x2012ebe0',
                             'file':hex(unit.image.offset(0x2012EBE0)),
                             'factory':hex(int.from_bytes(unit.image.bytes(0x2012EBE0,2),'big'))}
    assert study['P1']['source']['factory'] == '0xffff'
    old_frames = {}
    import zlib
    for name in ['A','B','R','RALL']:
        path = ROOT/f'firmware/peaking_probe/local/build/P_{name}.bin'
        data = read(path)
        assert len(data) == 436 and zlib.crc32(data) == 0
        old_frames[name] = {'sha256':digest(data),'bytes':len(data),'crc32':0}
    study['existing_frames'] = old_frames
    b_size = len(read(ROOT/'firmware/peaking_probe/local/build/raw_B.bin'))
    r_size = len(read(ROOT/'firmware/peaking_probe/local/build/raw_R.bin'))
    assert (b_size,r_size) == (432,436)
    study['size_estimates'] = {
        'P1':{'base':b_size,'constant_growth':12,'table_reduction':8,'estimated_raw':436},
        'P2':{'base':b_size,'constant_growth':12,'table_reduction':8,'estimated_raw':436},
        'P3':{'base':b_size,'constant_growth':6,'table_reduction':4,'estimated_raw':434},
        'R_each':{'base':r_size,'table_reduction':32,'estimated_raw':404},
        'assembled':False}
    put('probe_studies.json',study)
    prior = json.loads((OUT/'reads.json').read_text())
    put('reads.json',{**prior,**READS})
    print(json.dumps({'P1':study['P1'],'size_estimates':study['size_estimates'],
                      'existing_frames_checked':len(old_frames)}))


def verify():
    before = json.loads(read(OUT / 'before.json'))
    changes = []
    for rel, item in before['files'].items():
        path = ROOT / rel
        if not path.is_file() or digest(path.read_bytes()) != item['sha256']:
            changes.append(rel)
    for rel, value in json.loads(read(OUT / 'reads.json')).items():
        assert digest((ROOT/rel).read_bytes()) == value, rel
    for rel, value in json.loads(read(HERE/'local/reads.json')).items():
        assert digest((ROOT/rel).read_bytes()) == value, rel
    official = read(ROOT/'research/focus_assist/official-inputs.before.sha256').decode().splitlines()
    for line in official:
        value, rel = line.split(None,1)
        assert digest((ROOT/rel).read_bytes()) == value, rel
    assert not changes, changes
    env = {**os.environ,'GIT_OPTIONAL_LOCKS':'0'}
    status = subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],
                                     cwd=ROOT,env=env,text=True)
    outside_sha = digest('\n'.join(row for row in status.splitlines()
                                   if 'research/peaking_leads_r2/' not in row).encode())
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,env=env,text=True).strip()
    ignored = subprocess.run(['git','check-ignore','-q',str(OUT/'check')],
                             cwd=ROOT,env=env).returncode == 0
    assert ignored
    assert head == before['head']
    result = {'protected_files':len(before['files']), 'changed_files':changes,
              'used_inputs_equal':True,'official_files_equal':True,
              'official_files':len(official),'head_same':True,'local_ignored':ignored,
              'outside_status_before':before['outside_status_sha256'],
              'outside_status_after':outside_sha,
              'outside_status_same':outside_sha == before['outside_status_sha256']}
    put('verification.json',result)
    print(json.dumps(result))


def main():
    assert sys.flags.isolated and sys.dont_write_bytecode
    assert HERE == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_leads_r2')
    assert os.environ.get('TMPDIR') == '/Volumes/Workspace/Scratch/tmp/projectricoh/peaking-r3'
    assert not (HERE/'local').is_symlink()
    assert OUT.resolve().is_relative_to(HERE)
    assert (HERE/'.gitignore').read_text() == 'local/\n'
    assert not OUT.is_symlink()
    p = argparse.ArgumentParser()
    p.add_argument('operation',choices=['analyze','detail','probes','verify'])
    args = p.parse_args()
    {'analyze':analyze,'detail':detail,'probes':probes,'verify':verify}[args.operation]()


if __name__ == '__main__':
    main()
