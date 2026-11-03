"""保留启动分类器的原始输入、位设置点和模式表。"""
from pathlib import Path
import json
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import static_tools as s


def main():
    image=s.Image()
    reads=[
        (11,0x2005c57e,'sp+0x60'),(25,0x2005c58e,'sp+0x48'),
        (28,0x2005c59e,'sp+0x54'),(29,0x2005c5ae,'fp'),
        (39,0x2005c5be,'sp+0x5c'),(30,0x2005c5ce,'r12'),
        (55,0x2005c5de,'sp+0x44'),(10,0x2005c5ee,'r10，后续特殊分支改写为 1'),
        (12,0x2005c646,'r0，特殊键组合门'),(5,0x2005c676,'sp+0x30'),
        (54,0x2005c686,'sp+0x2c'),(45,0x2005c696,'sp+0x28'),
        (19,0x2005c6a6,'sp+0x50'),(20,0x2005c6b6,'sp+0x4c'),
        (15,0x2005c6c6,'sp+0x40'),(16,0x2005c6d6,'sp+0x3c'),
        (17,0x2005c6e6,'sp+0x20'),(18,0x2005c6f6,'sp+0x24'),
        (22,0x2005c706,'sp+0x68'),(21,0x2005c71a,'sp+0x58'),
        (53,0x2005c72a,'sp+0x34'),(32,0x2005c73a,'sp+0x38'),
        (11,0x2005ca4a,'轮询输入，不与起初输入合并'),
    ]
    flags=[
        (0x10000,0x2005c658,'进入 raw channel 12>0 的特殊组合分支'),
        (0x20000,0x2005c668,'同上'),
        (0x100000,0x2005c794,'该分支内 ch19>0，ch22<=0，ch21<=0'),
        (0x80000,0x2005c7ec,'该分支内 ch20>0，ch22<=0，ch21<=0'),
        (1,0x2005c802,'该分支内 ch15>0'),
        (2,0x2005c816,'该分支内 ch16>0'),
        (0x200000,0x2005c82c,'该分支内 ch32>0'),
        (0x400000,0x2005c844,'该分支内 ch53>0'),
        (8,0x2005c872,'后续组合门通过且 ch18>0'),
        (4,0x2005c88e,'后续组合门通过且 ch17>0'),
        (0x200,0x2005c8cc,'后续组合门通过且 ch22>0、ch19>0'),
        (0x100,0x2005c8fc,'后续组合门通过且 ch22>0、ch20>0'),
        (0x80,0x2005c954,'后续组合门通过且 ch21>0、ch20<=0、ch19<=0'),
        (0x80,0x2005c984,'后续组合门通过且 ch21>0、ch20>0'),
        (0x800,0x2005c9a4,'后续组合门通过且 ch21>0、ch19>0'),
        (0x20,0x2005c9b6,'后续组合门通过且 r10>0；该特殊路径已把 r10 置 1'),
        (0x400,0x2005caa0,'原始 0x20062D78 返回的 bit 3 分支；同时选择 mode 4'),
        (0x20000,0x2005cab0,'同上'),
    ]
    calls=json.loads((s.HERE/'references/calls.json').read_text())
    actual=[x for x in calls if 0x2005c538<=int(x['pc'],16)<0x2005cc7c and int(x['target'],16)==0x20068a68]
    assert {int(x['pc'],16) for x in actual}=={pc for value,pc,note in flags}
    modes=[]
    for i in range(32):
        a=0x200c1650+16*i
        v=struct.unpack('>4I',image.raw(a,16))
        if i and v[0]==0:break
        if not all(x==0 or 0x2004b000<=x<0x20400000 for x in v[1:]):break
        modes.append(dict(address=hex(a),mode=hex(v[0]),init=hex(v[1]),exit=hex(v[2]),run=hex(v[3]),bytes=image.raw(a,16).hex()))
    result=dict(status='静态已证',source_sha256=image.sha256,
                classifier=['0x2005c538','0x2005cc7c'],
                native_key_getter='0x2006439c',raw_power_getter='0x20062d78',
                inputs=[dict(channel=n,call=hex(pc),stored=dest,bytes=image.raw(pc&~3,4).hex()) for n,pc,dest in reads],
                flag_setter='0x20068a68',flag_cell='0x200d6118',
                flags=[dict(flag=hex(value),call=hex(pc),local_condition=note,bytes=image.raw(pc&~3,4).hex()) for value,pc,note in flags],
                shared_gate='上述是各位的局部条件；完整共享前置分支见封存窗口。raw 通道的物理按钮名称不由本表猜测。',
                mode_table=modes,mode_table_bytes=''.join(r['bytes'] for r in modes),
                physical_category_binding='未定；不从模式 ID 或某一位名称推断全部启动类别。')
    s.save('references/boot_flag_map.json',result)
    print(dict(inputs=len(reads),flag_calls=len(flags),mode_rows=len(modes)))


if __name__=='__main__':main()
