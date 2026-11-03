#!/usr/bin/python3
"""Read the retained FAT16 recovery cards and compare all official files."""
import hashlib
import json
import os
from pathlib import Path
import struct
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BODY=ROOT/'research/v310_body'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def files_from(raw,fat_index):
    start=struct.unpack_from('<I',raw,454)[0]
    boot=start*512
    bps=struct.unpack_from('<H',raw,boot+11)[0];spc=raw[boot+13]
    reserved=struct.unpack_from('<H',raw,boot+14)[0];fats=raw[boot+16]
    entries=struct.unpack_from('<H',raw,boot+17)[0]
    fat_size=struct.unpack_from('<H',raw,boot+22)[0]*bps
    assert bps==512 and fats==2 and len(raw)==67108864
    fat0=(start+reserved)*bps
    fat=raw[fat0+fat_index*fat_size:fat0+(fat_index+1)*fat_size]
    root=fat0+fats*fat_size;root_size=((entries*32+bps-1)//bps)*bps
    data=root+root_size;cluster_bytes=spc*bps
    result={}
    for off in range(root,root+entries*32,32):
        row=raw[off:off+32]
        if row[0]==0:break
        if row[0]==0xe5 or row[11]&0x18 or row[11]==15:continue
        base=row[:8].decode('ascii').rstrip();ext=row[8:11].decode('ascii').rstrip()
        name=(base+('.'+ext if ext else '')).lower()
        length=struct.unpack_from('<I',row,28)[0];cluster=struct.unpack_from('<H',row,26)[0]
        chain=[];parts=[]
        while cluster<0xfff8:
            assert 2<=cluster<(len(raw)-data)//cluster_bytes+2 and cluster not in chain
            chain.append(cluster)
            pos=data+(cluster-2)*cluster_bytes;parts.append(raw[pos:pos+cluster_bytes])
            cluster=struct.unpack_from('<H',fat,2*cluster)[0]
            assert len(chain)<=4096
        content=b''.join(parts)[:length]
        assert len(content)==length
        result[name]=(content,chain)
    return result,dict(start_sector=start,bytes_per_cluster=cluster_bytes,
                      FAT_bytes=fat_size,FAT0_start=fat0)


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    target=HERE/'evidence/recovery-media.json';assert not target.exists()
    with zipfile.ZipFile(ROOT/'artifacts/downloads/gxr-151.zip') as z:
        expected={Path(i.filename).name:z.read(i) for i in z.infolist() if not i.is_dir()}
    rows=[]
    for flow in ('official','v310'):
        receipt=json.loads((HERE/'evidence'/(flow+'-tail-batch-r2.json')).read_text())
        path=ROOT/receipt['medium_source'];raw=path.read_bytes()
        assert sha(raw)==receipt['medium_sha256']
        first,geometry=files_from(raw,0);second,_=files_from(raw,1)
        checks=[]
        for name,content in expected.items():
            assert first[name][0]==second[name][0]==content
            checks.append(dict(name=name,bytes=len(content),sha256=sha(content),
                chain_equal=first[name][1]==second[name][1],clusters=len(first[name][1])))
        assert 'gxrce.dat' not in first and 'gxrce.ctl' not in first
        pos=geometry['FAT0_start'];n=geometry['FAT_bytes']
        a=raw[pos:pos+n];b=raw[pos+n:pos+2*n]
        differences=[dict(entry=i//2,FAT0=int.from_bytes(a[i:i+2],'little'),
            FAT1=int.from_bytes(b[i:i+2],'little')) for i in range(0,n,2) if a[i:i+2]!=b[i:i+2]]
        rows.append(dict(flow=flow,source=str(path.relative_to(ROOT)),sha256=sha(raw),
            geometry=geometry,all_29_files_equal_in_both_FATs=True,checks=checks,
            FAT_differences=differences,DAT_absent=True))
    target.write_text(json.dumps(dict(status='PASS',cards=rows),indent=2)+'\n')
    print(json.dumps(dict(status='PASS',cards=len(rows),files_each=29)))


if __name__=='__main__':main()
