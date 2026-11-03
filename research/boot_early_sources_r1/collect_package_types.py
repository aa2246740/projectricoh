"""保留官方包原始头部与类型名的机器码分派。"""
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import static_tools as s


def main():
    rows=[]
    for path in sorted((s.ROOT/'artifacts/firmware/gxr-1.51').iterdir()):
        if not path.is_file():
            continue
        data=path.read_bytes()
        rows.append(dict(file=str(path.relative_to(s.ROOT)),sha256=s.sha(data),
                         type_byte=data[16],entry=hex(struct.unpack_from('>I',data,0x160)[0]),
                         header_bytes=data[:512].hex(),header_sha256=s.sha(data[:512])))
    im=s.Image('artifacts/firmware/gxr-1.51/jlaunch3')
    names=[]
    for value in [1,2,5,6,8]:
        table=0x200bf4c8+2*(value-1)
        pc=0x20078a00+struct.unpack('>h',im.raw(table,2))[0]
        high=struct.unpack('>H',im.raw(pc+2,2))[0]
        low=struct.unpack('>H',im.raw(pc+6,2))[0]
        address=(high<<16)|low
        text=im.raw(address,20).split(b'\0')[0]
        names.append(dict(value=value,table=hex(table),table_bytes=im.raw(table,2).hex(),
                          branch=hex(pc),branch_bytes=im.raw(pc,8).hex(),
                          string_address=hex(address),string_bytes=text.hex(),
                          name=text.decode('ascii').strip()))
    assert {x['value']:x['name'] for x in names}=={
        1:'MONITOR',2:'MAIN',5:'ADJCOM',6:'EXTEND',8:'BACKUP'}
    s.save('references/package_types.json',dict(status='静态已证',type_field_offset='0x10',
           files=rows,type_names=names,type_map_source=im.name,type_map_source_sha256=im.sha256,
           note='机身 i 前缀没有 type 1；l06firm5 不能代替机身 MONITOR。'))
    print(dict(files=len(rows),type_names={x['value']:x['name'] for x in names}))


if __name__=='__main__':
    main()
