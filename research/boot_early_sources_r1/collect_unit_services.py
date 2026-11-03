"""收集单元服务登记候选；逐字节核对本地官方反汇编。"""
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import static_tools as s


def main():
    im=s.Image('artifacts/firmware/gxr-1.51/jlaunch3')
    regs={}
    found=[]
    for path in sorted((s.ROOT/'research/tooling_m32r/disasm').glob('jlaunch3-sec*.disasm.txt')):
        for line in path.open():
            match=s.LINE.match(line)
            if not match:
                continue
            pc=int(match[1],16)
            raw=bytes.fromhex(match[2])
            assert im.raw(pc,len(raw))==raw
            for n,op in enumerate(re.split(r' -> | \|\| ',match[3])):
                code,_,tail=op.partition(' ')
                args=re.findall(r'@\([^)]*\)|[^,]+',tail)
                dest=args[0] if args else ''
                if code=='jl' and regs.get(dest)==0x2007cba8:
                    found.append(dict(pc=hex(pc+2*n),
                                      args={r:hex(regs[r]) for r in ['r4','r5','r6'] if r in regs}))
                try:
                    if code=='seth':
                        regs[dest]=int(args[1].lstrip('#'),0)<<16
                    elif code in ('ldi','ld24'):
                        regs[dest]=int(args[1].lstrip('#'),0)&0xffffffff
                    elif code=='or3' and args[1] in regs:
                        regs[dest]=regs[args[1]]|int(args[2].lstrip('#'),0)
                    elif code=='mv' and args[1] in regs:
                        regs[dest]=regs[args[1]]
                    elif code=='jl':
                        for i in range(8):
                            regs.pop('r'+str(i),None)
                    elif code.startswith('b') or code in ('jmp','rte'):
                        regs.clear()
                    elif code not in ('nop','st','sth','stb','cmp','cmpi','cmpui','cmpu','push'):
                        regs.pop(dest,None)
                except (ValueError,IndexError):
                    regs.clear()
    s.save('references/unit_service_registrations.json',
           dict(status='候选',source=im.name,source_sha256=im.sha256,
                register_function='0x2007cba8',resolved=found,
                note='直线常量传播只作为登记点检索，不是完整目标枚举。'))
    print([row for row in found if row['args'].get('r4') in ['0x52','0x53']])


if __name__=='__main__':
    main()
