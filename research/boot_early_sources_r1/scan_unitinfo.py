"""从逐字节核对的反汇编收集直接调用、常量引用及参数访问候选。"""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_tools as s


def imm(value):
    value=value.lstrip('#')
    return int(value, 0)


def main():
    regs={}
    calls=[]
    fields=[]
    refs=[]
    indirect=[]
    count=0
    for pc, raw, op, source, line in s.instructions():
        count+=1
        name, _, tail=op.partition(' ')
        args=re.findall(r'@\([^)]*\)|[^,]+',tail)
        d=args[0] if args else ''
        row=dict(pc=hex(pc), bytes=raw.hex(), instruction=op, source=source, line=line)
        effective=None
        if name in ('jl','bl'):
            target=regs.get(d) if name=='jl' else int(d,16)
            info=dict(row,args={k:v for k,v in regs.items() if k in ('r4','r5','r6','r7')})
            if isinstance(target,int): calls.append(dict(info,target=hex(target)))
            else:indirect.append(info)
        if name in ('ld','ldh','lduh','ldb','ldub','st','sth','stb') and len(args)>1:
            m=re.fullmatch(r'@\((-?\d+),(\w+)\)',args[1])
            base=m[2] if m else args[1].removeprefix('@').rstrip('+')
            delta=int(m[1]) if m else 0
            value=regs.get(base)
            width=4 if name in ('ld','st') else 2 if name in ('ldh','lduh','sth') else 1
            kind='写' if name.startswith('st') else '读'
            if isinstance(value,int) and 0x2040f818<=value<0x20410018:value=('unit_info',value-0x2040f818)
            if isinstance(value,tuple):
                effective=(value[0],value[1]+delta)
                fields.append(dict(row,object=effective[0],offset=hex(effective[1]),width=width,kind=kind))
            elif isinstance(value,int):
                effective=(value+delta)&0xffffffff
                if (0x205d9800<=effective<0x205db000 or 0x204104e0<=effective<0x20410530
                    or 0x200c0d90<=effective<0x200c0e00):
                    refs.append(dict(row,address=hex(effective),width=width,kind=kind,value=regs.get(d) if kind=='写' else None))
        try:
            if name=='seth':regs[d]=imm(args[1])<<16
            elif name in ('ldi','ld24'):regs[d]=imm(args[1])&0xffffffff
            elif name=='mv':
                if args[1] in regs:regs[d]=regs[args[1]]
                else:regs.pop(d,None)
            elif name=='ld' and effective==0x200c0dac:regs[d]=('S',0)
            elif name in ('or3','add3','and3') and args[1] in regs:
                x,y=regs[args[1]],imm(args[2])
                if name=='add3' and 0x8000<=y<=0xffff:y-=65536
                if isinstance(x,tuple) and name=='add3':regs[d]=(x[0],x[1]+y)
                elif isinstance(x,int):regs[d]=(x|y if name=='or3' else x+y if name=='add3' else x&y)&0xffffffff
                else:regs.pop(d,None)
            elif name in ('addi','slli','srli') and d in regs:
                x,y=regs[d],imm(args[1])
                if isinstance(x,tuple) and name=='addi':regs[d]=(x[0],x[1]+y)
                elif isinstance(x,int):regs[d]=(x+y if name=='addi' else x<<y if name=='slli' else x>>y)&0xffffffff
                else:regs.pop(d,None)
            elif name=='add' and d in regs and args[1] in regs:
                x,y=regs[d],regs[args[1]]
                if isinstance(x,tuple) and isinstance(y,int):regs[d]=(x[0],x[1]+y)
                elif isinstance(x,int) and isinstance(y,tuple):regs[d]=(y[0],x+y[1])
                elif isinstance(x,int) and isinstance(y,int):regs[d]=(x+y)&0xffffffff
                else:regs.pop(d,None)
            elif name in ('jl','bl'):
                selected=regs.get('r4')
                for n in range(8):regs.pop('r'+str(n),None)
                if target==0x20063f64:regs['r0']=('unit_info' if selected==1 else 'info_unspecified',0)
            elif name.startswith('b') or name in ('jmp','rte'):regs.clear()
            elif name not in ('nop','cmp','cmpu','cmpi','cmpui','cmpeq','st','sth','stb','push'):
                regs.pop(d,None)
        except (ValueError,IndexError):regs.clear()
    s.save('references/uinfo-fields.json',fields)
    summary=dict(instructions=count,calls=len(calls),fields=len(fields),globals=len(refs),unresolved_calls=len(indirect),
                 boundary='直线常量传播；跨分支、索引、内存别名和间接调用须人工追踪。候选集合不能充当穷尽证明。')
    s.save('references/uinfo-scan_summary.json',summary)
    s.progress('已核对机身单元信息 getter 的直接字段使用候选。')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
