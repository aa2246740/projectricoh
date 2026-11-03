#!/usr/bin/python3
"""Read the retained native recovery media and both FAT copies without changing bytes."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pickle
import struct
import zipfile
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def sha(data):return hashlib.sha256(data).hexdigest()


def file_table(raw):
    start=struct.unpack_from('<I',raw,0x1c6)[0]
    boot=start*512
    bps=struct.unpack_from('<H',raw,boot+11)[0];spc=raw[boot+13]
    reserved=struct.unpack_from('<H',raw,boot+14)[0];copies=raw[boot+16]
    root_entries=struct.unpack_from('<H',raw,boot+17)[0]
    fat_sectors=struct.unpack_from('<H',raw,boot+22)[0]
    assert bps==512 and copies==2
    first=(start+reserved)*bps;fat_bytes=fat_sectors*bps
    fats=[raw[first+i*fat_bytes:first+(i+1)*fat_bytes] for i in range(2)]
    root=first+copies*fat_bytes;data=root+root_entries*32
    files={}
    for offset in range(root,root+root_entries*32,32):
        entry=raw[offset:offset+32]
        if entry[0]==0:break
        if entry[0]==0xe5 or entry[11]&0x18 or entry[11]==0x0f:continue
        name=entry[:8].decode('ascii').rstrip();ext=entry[8:11].decode('ascii').rstrip()
        if entry[12]&8:name=name.lower()
        if entry[12]&16:ext=ext.lower()
        name+=('.'+ext if ext else '')
        first_cluster=struct.unpack_from('<H',entry,26)[0]
        size=struct.unpack_from('<I',entry,28)[0];parts=[];chain=[];cluster=first_cluster
        while cluster<0xfff8 and cluster>=2:
            assert cluster not in chain and len(chain)<65525
            chain.append(cluster);at=data+(cluster-2)*spc*bps
            parts.append(raw[at:at+spc*bps]);cluster=struct.unpack_from('<H',fats[0],cluster*2)[0]
        content=b''.join(parts)[:size];assert len(content)==size
        files[name]=(content,chain)
    return files,[(i,a,b) for i,(a,b) in enumerate(zip(*fats)) if a!=b]


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    with zipfile.ZipFile(ROOT/'artifacts/downloads/gxr-151.zip') as z:
        prefix='GXR Update/Firmware rel 1.51/'
        official={Path(n).name:z.read(n) for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')}
    assert len(official)==29
    fixture_path=ROOT/'research/emulator_m2b/local/nand-reflector.pages.json'
    fixture_raw=fixture_path.read_bytes();fixture=json.loads(fixture_raw)
    fixture_pages={int(k):bytes.fromhex(v) for k,v in fixture['pages'].items()}
    rows=[]
    for name in ('restore-v310-word','restore-v39-word'):
        receipt=json.loads((HERE/'evidence'/f'recovery-{name}-projection-1994291028.json').read_text())
        path=ROOT/receipt['snapshot'];state=pickle.loads(zlib.decompress(path.read_bytes()))['cpu']
        sd=next(d for t,d in zip(state['device_types'],state['devices']) if t=='SdHost')
        record=sd['medium_record'];medium=HERE/'local/media'/(record['sha256']+'.img')
        raw=medium.read_bytes();assert sha(raw)==record['sha256']
        files,differences=file_table(raw);checks=[]
        for file_name,expected in official.items():
            actual,chain=files[file_name];assert actual==expected,file_name
            checks.append(dict(name=file_name,sha256=sha(actual),bytes=len(actual),clusters=chain))
        assert 'GXRCE.DAT' not in files
        table_at=0x20446140
        for base,data,_ in state['regions']:
            if base<=table_at and table_at+24<=base+len(data):selection=data[table_at-base:table_at-base+24];break
        assert selection.hex()=='000000010000000100000000080000000000000000000000'
        early_name=('recovery-restore-v310-word-checkpoint-1251391202.pkl.z' if name=='restore-v310-word'
            else 'recovery-restore-v39-word-readback-1001391202.pkl.z')
        early_path=HERE/'local'/early_name;early_raw=early_path.read_bytes()
        early=pickle.loads(zlib.decompress(early_raw))['cpu']
        nand=next(d for t,d in zip(early['device_types'],early['devices']) if t=='WordColumnNAND')
        assert all(nand['pages'].get(at)==data for at,data in fixture_pages.items())
        commands=Counter(nand['commands'])
        rows.append(dict(name=name,snapshot=str(path.relative_to(ROOT)),snapshot_sha256=sha(path.read_bytes()),
            medium=str(medium.relative_to(ROOT)),medium_sha256=sha(raw),official_files_equal=29,DAT_absent=True,
            checks=checks,fat_copy_byte_differences=differences,
            read_error_sectors=sorted(record['read_errors']),write_error_sectors=sorted(record['write_errors']),
            native_selection_address=hex(table_at),native_selection_bytes=selection.hex(),
            selection='One selected update: type 8 / slot 0, BACKUP ilaunch0; MAIN and EXTEND absent',
            initial_nand=dict(source=str(fixture_path.relative_to(ROOT)),source_sha256=sha(fixture_raw),
                declared_pages=len(fixture_pages),page_numbers=sorted(fixture_pages),
                actual_early_snapshot=str(early_path.relative_to(ROOT)),actual_snapshot_sha256=sha(early_raw),
                actual_snapshot_step=early['steps'],reflector_pages_equal_fixture=True,
                actual_pages=len(nand['pages']),actual_non_erased_pages=sum(any(b!=255 for b in data) for data in nand['pages'].values()),
                native_erase_confirm_count=commands[0xd0],native_program_confirm_count=commands[0x10],
                boundary='Sparse declared reflector only; not a complete installed v3.9 or v3.10 NAND image'),
            native_state_presets=[]))
    (HERE/'evidence/recovery-media-audit.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(dict(runs=len(rows),official_files_equal_each=29,selection='BACKUP only')))


if __name__=='__main__':main()
