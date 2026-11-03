"""用最终文件和独立编译的查询/数学 C，逐字节比较 g154 的全部现有条目。"""
from pathlib import Path
import hashlib
import json
import sys
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
from reference import Reference,user_record
from dat_format import expand,expand_effect,strict_effects,u32

def main():
    start=time.monotonic();old=Reference(154);new=Reference(155);rows=[]
    a=(ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    b=(ROOT/'firmware/package_v310_g155_test/GXRCE.DAT').read_bytes()
    release=(ROOT/'firmware/package_v310_g155/GXRCE.DAT').read_bytes()
    outputs=HERE/'evidence/outputs';outputs.mkdir(exist_ok=True)
    assert strict_effects(a)['count']==strict_effects(b)['count']==10
    for unit in range(3):
        for kind,number in [('builtin',i) for i in range(1,9)]+[('look',i) for i in range(1,11)]+[('user',i) for i in range(1,4)]:
            levels=[100]+[0]*9
            if kind=='look':abase,bbase=expand_effect(a,number-1),expand_effect(b,number-1)
            else:
                slot=number
                if kind=='user':slot,levels,_=user_record(b,number)
                abase,bbase=expand(a,unit,slot),expand(b,unit,slot)
            sa,pa=old.compute(a,unit,abase,levels);sb,pb=new.compute(b,unit,bbase,levels)
            assert sa==sb==0 and pa==pb,(unit,kind,number)
            stem=f'{unit}-{kind}-{number}'
            (outputs/(stem+'-g154.bin')).write_bytes(pa);(outputs/(stem+'-g155.bin')).write_bytes(pb)
            if kind!='user':
                release_base=expand_effect(release,number-1) if kind=='look' else expand(release,unit,number)
                sr,pr=new.compute(release,unit,release_base,levels);assert sr==0 and pr==pb
            rows.append(dict(unit=unit,kind=kind,number=number,bytes=552,sha256=hashlib.sha256(pb).hexdigest(),equal=True))
    # User extension and R3 controls are retained exactly; only GXFX spare rows shrink.
    assert b[u32(b,204)+1408:u32(b,204)+3392]==a[u32(a,204)+1408:u32(a,204)+3392]
    assert b[u32(b,204)+3392:]==a[u32(a,204)+3392:]
    result=dict(status='PASS',backend='host C',seconds=time.monotonic()-start,rows=rows,
        compared=63,release_compared=54,builtin=24,looks=30,users=9,spare_bytes_removed=3932)
    (HERE/'evidence/equality.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
