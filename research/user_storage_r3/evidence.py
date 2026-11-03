#!/usr/bin/env python3
"""Check mappings, dispatch tables, resident identity and protected inputs."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import collect

EXTRA = (
    'docs/RESEARCH_PROTOCOL.md', 'research/irom_storage/REPORT.md',
    'research/irom_storage/STORAGE_ABI.md', 'firmware/resident_v36/REPORT.md',
    'firmware/resident_v36/native_contract.py',
    'firmware/resident_v36/local/resident/size.json',
    'firmware/resident_v36/local/resident/hooks.json',
    'firmware/resident_v36/local/resident/build/resident.elf',
)

def extra_snapshot():
    return {rel:{'bytes':(collect.ROOT/rel).stat().st_size,'sha256':collect.sha(collect.ROOT/rel)}
            for rel in EXTRA}

def freeze_plan():
    rows = []
    for path in sorted(collect.OUT.glob('*.asm.txt')):
        label = path.name.removesuffix('.asm.txt')
        m = re.search(r'(?m)^([0-9a-f]+) <\.data>:',path.read_text())
        assert m, label
        start = int(m[1],16)
        binary = collect.OUT/(label+'.bin')
        rows.append({'label':label,'start':hex(start),'end':hex(start+binary.stat().st_size),
            'mode':'compare' if (collect.OUT/(label+'.compare.json')).exists() else 'equal'})
    target = HERE/'windows.json'
    assert not target.exists(), 'do not replace the window plan'
    target.write_text(json.dumps(rows,indent=2)+'\n')
    print('window plan:',len(rows))

def input_manifests():
    results = []
    for folder in ('user_storage_r1','user_storage_r2'):
        manifest = collect.ROOT/'research'/folder/'SHA256SUMS'
        count = 0
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            digest, rel = line.split(maxsplit=1)
            rel = rel.removeprefix('*')
            path = collect.ROOT/rel
            assert path.is_file() and collect.sha(path) == digest, rel
            count += 1
        results.append({'manifest':str(manifest.relative_to(collect.ROOT)),
            'sha256':collect.sha(manifest),'verified_entries':count,'status':'PASS'})
    collect.save('input-manifests.json',results)
    return results

def resident(im):
    spec = importlib.util.spec_from_file_location('read_only_elf',
        collect.ROOT/'firmware/stage2l_switch/tools/build.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    elfpath = collect.ROOT/'firmware/resident_v36/local/resident/build/resident.elf'
    elf = mod.Elf(elfpath)
    size = json.loads((collect.ROOT/'firmware/resident_v36/local/resident/size.json').read_text())
    assert collect.sha(elfpath) == size['sha256']
    payload, = [s for s in elf.sections if s['name'] == '.payload']
    data = elf.content(payload)
    offset = im.off(payload['va'],len(data))
    assert data == im.body[offset:offset+len(data)]
    end = elf.symbols['__resident_code_end']['value']
    ceiling = 0x20054700-200
    assert end == ceiling
    assert len(data) == size['payload_bytes'] == 7884
    hooks = json.loads((collect.ROOT/'firmware/resident_v36/local/resident/hooks.json').read_text())
    enabled = [h for h in hooks if h['number'] not in size['removed_hooks']]
    for hook in enabled:
        off = int(hook['file_offset'],16)
        original = bytes.fromhex(hook['original_bytes'])
        assert im.data[off:off+len(original)] == original
    decoded_bytes = 0
    for line in (collect.OUT/'resident-disasm.txt').read_text().splitlines():
        match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s)+)',line)
        if match:
            address, raw = int(match[1],16), bytes.fromhex(match[2])
            at = im.off(address,len(raw))
            assert im.body[at:at+len(raw)] == raw, hex(address)
            decoded_bytes += len(raw)
    assert decoded_bytes > 7000
    return {'elf':str(elfpath.relative_to(collect.ROOT)),'sha256':collect.sha(elfpath),
        'payload_vma':hex(payload['va']),'payload_bytes':len(data),
        'payload_sha256':hashlib.sha256(data).hexdigest(),
        'payload_matches_fixed_body':True,'code_end':hex(end),'link_ceiling':hex(ceiling),
        'mandatory_margin_bytes':200,'additional_code_bytes':ceiling-end,
        'root_bytes':256,'occupied_bytes':size['occupied'],
        'resident_disassembly_bytes_checked':decoded_bytes,
        'enabled_hook_numbers':[h['number'] for h in enabled],
        'removed_hook_numbers':size['removed_hooks']}, enabled

def check():
    im = collect.Image()
    resident_result, enabled = resident(im)
    patch_offsets = set()
    for hook in enabled:
        off = int(hook['file_offset'],16)
        patch_offsets.update(range(off,off+hook['length']))
    windows = []
    for row in json.loads((HERE/'windows.json').read_text()):
        start, end = int(row['start'],16), int(row['end'],16)
        path = collect.OUT/(row['label']+'.bin')
        raw = im.raw(start,end-start)
        assert path.read_bytes() == raw
        off = im.off(start,len(raw))
        body = im.body[off:off+len(raw)]
        differences = [off+i for i,(x,y) in enumerate(zip(raw,body)) if x != y]
        if row['mode'] == 'equal':
            assert not differences, row['label']
        else:
            assert (collect.OUT/(row['label']+'.body.bin')).read_bytes() == body
            assert all(i in patch_offsets for i in differences), row['label']
            sidecar = json.loads((collect.OUT/(row['label']+'.compare.json')).read_text())
            assert [int(r['file'],16) for r in sidecar['differences']] == differences
        windows.append({**row,'file':hex(off),'bytes':len(raw),'sha256':collect.sha(path),
            'official_equals_body':not differences,'changed_bytes':len(differences),
            'differences_are_enabled_resident_hooks':all(i in patch_offsets for i in differences)})
    table = []
    for event in range(11):
        va = 0x201427b4+12*event
        targets = struct.unpack('>3I',im.raw(va,12))
        table.append({'event':event,'vma':hex(va),'file':hex(im.off(va,12)),
            'handlers':[hex(n) for n in targets]})
    assert table[1]['handlers'] == ['0x201106d4','0x2010e5c8','0x2010e5c8']
    assert table[8]['handlers'] == ['0x20111810','0x20111810','0x201106d4']
    assert table[9]['handlers'] == ['0x201106d4']*3
    assert table[10]['handlers'] == ['0x201106d4','0x2010e064','0x2010e064']
    services = []
    for number,target in ((112,0x05003adc),(120,0x0500740c),(124,0x0500a514)):
        va = 0x200d1678+number
        actual, = struct.unpack('>I',im.raw(va,4))
        assert actual == target
        services.append({'trap_service':number,'pointer_vma':hex(va),
            'pointer_file':hex(im.off(va,4)),'handler':hex(target)})
    strings = []
    for va,expected in ((0x201414c8,b'.JPG\0'),(0x201414dc,b'.DNG\0'),
                        (0x201415c9,b'.JPG\0'),(0x201415dd,b'.DNG\0')):
        assert im.raw(va,len(expected)) == expected
        strings.append({'vma':hex(va),'file':hex(im.off(va,len(expected))),
            'value':expected[:-1].decode()})
    collect.save('window-index.json',windows)
    collect.save('dispatch-tables.json',{'storage':table,'rtos':services,'extension_strings':strings})
    collect.save('resident-identity.json',resident_result)
    manifests = input_manifests()
    collect.save('evidence-check.json',{'status':'PASS','windows':len(windows),
        'equal_windows':sum(r['official_equals_body'] for r in windows),
        'compared_windows':sum(r['mode']=='compare' for r in windows),
        'resident':resident_result,'input_manifests':manifests})
    print('PASS evidence:',len(windows),'mapped windows; resident additional code 0 B')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action',choices=('freeze-plan','extra-before','extra-after','check'))
    a = ap.parse_args()
    collect.preflight()
    if a.action == 'freeze-plan':
        freeze_plan()
    elif a.action.startswith('extra-'):
        now = extra_snapshot()
        if a.action == 'extra-before':
            assert not (collect.OUT/'extra-before.json').exists()
            collect.save('extra-before.json',now)
        else:
            old = json.loads((collect.OUT/'extra-before.json').read_text())
            changes = [k for k in old.keys()|now.keys() if old.get(k) != now.get(k)]
            collect.save('extra-after.json',now)
            collect.save('extra-check.json',{'status':'PASS' if not changes else 'FAIL','changes':changes,
                'note':'Supplementary read-only inputs frozen after discovery, not at initial collection.'})
            assert not changes, changes
        print(a.action,len(now),'supplementary inputs')
    else:
        check()

if __name__ == '__main__':
    main()
