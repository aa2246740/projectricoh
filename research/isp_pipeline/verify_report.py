#!/usr/bin/env python3
"""Check literal data invariants, retained instruction bytes, links, and protected hashes."""
import hashlib
import json
import re
import runpy
from pathlib import Path

HERE=Path(__file__).resolve().parent
M=runpy.run_path(str(HERE/'analyze.py'))
im=M['Image']()
rows=json.loads((HERE/'register_layouts.json').read_text())
assert [r['type'] for r in rows]==list(range(39))
expected={0:5,1:21,2:0,3:0,4:0,8:514,13:1070,14:1955,21:278,23:68,24:28,25:5,26:44,27:25,28:54,32:251,34:71,37:31,38:192}
for k,v in expected.items():assert rows[k]['payload_u32_count']==v,(k,v)
assert rows[26]['payload_registers']==[f'0x{x:08X}' for x in range(0xF0349000,0xF03490B0,4)]
assert rows[23]['payload_registers']==[f'0x{x:08X}' for x in range(0xF0342000,0xF0342110,4)]
assert rows[28]['payload_registers'][14:38]==[f'0x{x:08X}' for x in range(0xF034C080,0xF034C0E0,4)]
mat=json.loads((HERE/'matrix_candidates.json').read_text())
assert mat[0]['raw_u16'][:9]==[306,601,117,2221,2387,512,512,2476,2132]
assert mat[3]['raw_u16'][:9]==[1024,0,0,0,1024,0,0,0,1024]
assert mat[0]['row_sums_raw']==[1024,0,0]
tables=json.loads((HERE/'decoded_tables.json').read_text())
assert [a['values'] for a in tables['type26']['auxiliary']]==[[0]*33,[0]*33]

captures=json.loads((HERE/'capture_metadata.json').read_text())
dng=[r for r in captures if r['path'].endswith('.DNG')]
assert len(dng)==3
def tags(rec):return {t['tag']:t for i in rec['ifds'] for t in i['tags']}
for r in dng:
    ts=tags(r)
    assert all(50933 not in i['all_tag_ids'] for i in r['ifds']), 'Untraced ExtraCameraProfiles IFD'
    assert 50964 not in ts and 50965 not in ts
    assert 50723 not in ts and 50724 not in ts
    assert ts[50721]['value']==tags(dng[0])[50721]['value']
    assert ts[50722]['value']==tags(dng[0])[50722]['value']

index=[];instruction_count=0
for p in sorted((HERE/'evidence').glob('*.txt')):
    vas=[];count=0
    for line in p.read_text().splitlines():
        q=re.match(r'file=0x([0-9A-Fa-f]+) ([0-9a-f]{8}):\s+((?:[0-9a-f]{2} ){1,4})',line)
        if q:
            off,a=int(q[1],16),int(q[2],16)
            b=bytes.fromhex(q[3])
            assert im.offset(a)==off
            assert im.data[off:off+len(b)]==b
            vas.append(a);count+=1
    assert count,p
    index.append({'file':str(p.relative_to(HERE)),'first_vma':hex(min(vas)),
                  'last_instruction_vma':hex(max(vas)),'byte_checked_disassembly_rows':count,
                  'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    instruction_count+=count
M['save']('evidence_index.json',index)

report=(HERE/'REPORT.md').read_text()
stage_table=report.split('| type |',1)[1].split('### 3.2',1)[0]
assert [int(x) for x in re.findall(r'^\| (\d+) \|',stage_table,re.M)]==list(range(39))
before=json.loads((HERE/'inputs_before.json').read_text())
assert all(row['sha256'] in report for row in before.values())
after=M['manifest']()
assert before==after
M['save']('inputs_after.json',after)
links=[]
for href in re.findall(r'\]\(([^)]+)\)',report):
    if href.startswith(('https://','http://','#')):continue
    path=href.split('#',1)[0]
    if path!='verification.json':assert (HERE/path).exists(),href
    links.append(href)
result={'all_inputs_unchanged':True,'file_count':len(before),'before':before,'after':after,
        'hardware_type_count':len(rows),'retained_evidence_files':len(index),
        'byte_checked_excerpt_rows':instruction_count,'all_parseable_disassembly_rows_checked':len(im.lines),
        'local_report_links_checked':len(links),'DNG_matrix_comparison_passed':True,
        'camera_execution':False,'hardware_register_semantics_validated_on_camera':False,
        'report_claim_boundary':'Static payload decoding is not a silicon specification or a live camera validation.'}
M['save']('verification.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ('before','after')},ensure_ascii=False,indent=2))
