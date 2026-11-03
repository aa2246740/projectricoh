"""只读核对本设计的输入、DAT 尺寸、行布局及文档引用，不执行目标代码。"""
from pathlib import Path
import hashlib
import json
import re
import signal
import sys
import zlib

signal.alarm(45)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def read(name):
    return (ROOT / name).read_bytes()
def u16(b, at):
    return int.from_bytes(b[at:at+2], 'big')
def u32(b, at):
    return int.from_bytes(b[at:at+4], 'big')
def align4(n):
    return (n + 3) & ~3

def main():
    receipt = json.loads((HERE / 'input_receipt.json').read_text())
    changed = [p for p, v in receipt['inputs'].items()
               if hashlib.sha256(read(p)).hexdigest() != v['sha256']]
    assert not changed, changed
    core = 'candidate/containers/product/src/firmware/engine/core/eng_core.c'
    record = 'candidate/engine_services/settings_record.h'
    same = {p: read('firmware/engine_v60_g152/' + p) == read('firmware/engine_v62_g153/' + p)
            for p in [core, record]}
    assert all(same.values())
    b = read('firmware/package_v39_g153/local/SD_ROOT/GXRCE.DAT')
    assert hashlib.sha256(b).hexdigest() == 'e6dab16235dd6fad870c6c6f4935a078351de10334e2145cc94e940598b7083b'
    code, bss = u32(b,136), u32(b,116)
    assert (len(b), code, bss) == (90164, 65268, 9280)
    start, length = u32(b,192), u32(b,196)
    pool = b[start:start+length]
    fx = pool[u32(pool,64):]
    assert len(fx) == u32(pool,68)
    assert fx[:4] == b'GXFX'
    capacity, count = u16(fx,8), u16(fx,10)
    caps, used = list(fx[16:20]), list(fx[20:24])
    assert (capacity,count,caps,used) == (10,10,[8,28,32,32],[0,10,9,10])
    lengths = [62,33,96,56]
    old_size = 32 + 32*capacity + sum(align4(a*n) for a,n in zip(caps,lengths))
    new_caps = [0,16,12,12]
    assert all(n <= c for n,c in zip(used,new_caps))
    new_size = 32 + 32*capacity + sum(align4(a*n) for a,n in zip(new_caps,lengths))
    assert len(fx) == old_size == 6636 and new_size == 2704
    active_hashes = []
    at = 32 + 32*capacity
    for c,n,width in zip(caps,used,lengths):
        active_hashes.append(hashlib.sha256(fx[at:at+n*width]).hexdigest())
        assert not any(fx[at+n*width:at+align4(c*width)])
        at += align4(c*width)
    maps = []
    directory = u32(b,156)
    for i,name in enumerate(['50mm','28mm','MOUNT']):
        d = b[directory+64*i:directory+64*(i+1)]
        m = b[u32(d,12):u32(d,12)+152]
        rows = []
        for j in range(9):
            r = m[32+12*j:44+12*j]
            address,n = u32(r,0),u16(r,4)
            rows.append(dict(address=hex(address),bytes=n,
                             words=(n+(address&1)+1)//2,
                             extra_X=((address+n-1)>>16)-(address>>16)))
        words = sum(r['words'] for r in rows)
        extra = sum(r['extra_X'] for r in rows)
        one_read = 9 + words + extra + 4
        full_write_T2 = 27 + 2*words + extra + 2 + 4
        maps.append(dict(unit=name,rows=rows,owned_bytes=sum(r['bytes'] for r in rows),
                         one_read_XVW=one_read,full_write_verify_T2_XVW=full_write_T2,
                         full_write_verify_T0_XVW=full_write_T2+4,
                         two_reads_plus_full_write_XVW=[2*one_read+full_write_T2,2*one_read+full_write_T2+4]))
    assert [x['one_read_XVW'] for x in maps] == [267,266,266]
    assert all(x['owned_bytes'] == 503 for x in maps)
    source_map = json.loads(read('research/boot_early_sources_r1/source_map.json'))
    assert len(source_map['items']) == 69
    doc = (HERE/'DESIGN.md').read_text()
    links = re.findall(r'\]\(([^)]+)\)', doc)
    checked = []
    for link in links:
        if '://' in link or link.startswith('#'):
            continue
        target,_,anchor = link.partition('#')
        q = (HERE/target).resolve()
        if target == 'AUDIT.json' and '--write' in sys.argv and not q.exists():
            checked.append(link)
            continue
        assert q.is_file(), link
        if re.fullmatch(r'L[0-9]+',anchor):
            assert 0 < int(anchor[1:]) <= len(q.read_text().splitlines()), link
        checked.append(link)
    assert doc.splitlines()[0] == '可行（需现场核对 5 项）'
    assert re.findall(r'^\| ([1-5]) \|', doc, re.M) == ['1','2','3','4','5']
    result = dict(status='PASS_STATIC_DESIGN_AUDIT', scope='输入和算术核对；不是功能、链接或设备验收',
                  design_sha256=hashlib.sha256((HERE/'DESIGN.md').read_bytes()).hexdigest(),
                  audit_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  input_files=len(receipt['inputs']), input_changes=changed, identical_sources=same,
                  g153=dict(file=len(b),code=code,bss=bss,main=7628+align4(len(b)+bss)),
                  fx=dict(K=capacity,count=count,old_caps=caps,used=used,new_caps=new_caps,
                          old_bytes=old_size,new_bytes=new_size,saved=old_size-new_size,
                          active_pool_sha256=active_hashes), rpc_static=maps,
                  estimate=dict(added_dat_code=2048,added_dat_bss=192,
                                file=len(b)-(old_size-new_size)+2048,bss=bss+192,
                                main=7628+align4(len(b)-(old_size-new_size)+2048+bss+192),
                                code=code+2048,proposed_code_cap=69632,
                                added_body_code_range=[512,768],body_current_margin=20,
                                required_body_reduction_range=[492,748]),
                  source_map_counts=source_map['counts'],checked_links=len(checked),
                  device_code_executed=False,builds_run=False)
    if '--write' in sys.argv:
        (HERE/'AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
