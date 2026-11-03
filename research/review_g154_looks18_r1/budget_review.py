"""Recompute row-pool space from actual byte equality, independent of packer."""
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common_review import *
import bytes_review as B

def compact(raw,count):
    pool=B.U32(raw,192);builtin=[]
    for kind,length in enumerate(B.LENGTHS):
        number=B.U16(raw,pool+16+12*kind);at=pool+B.U32(raw,pool+20+12*kind)
        builtin.append({raw[at+j*length:at+(j+1)*length] for j in range(number)})
    extra=[set() for _ in B.LENGTHS]
    for i in range(count):
        full=B.look(raw,i)
        for kind,off in zip(B.KINDS,B.OFFSETS):
            row=full[off:off+B.LENGTHS[kind]]
            if row not in builtin[kind]:extra[kind].add(row)
    caps=list(map(len,extra))
    return dict(count=count,capacities=caps,bytes=32+32*count+sum(B.align(c*n) for c,n in zip(caps,B.LENGTHS)))

def main():
    guard();raw=dat();old=dat(True);before=B.area(old)[1];ten=compact(raw,10);eighteen=compact(raw,18)
    assert before==6636 and ten['bytes']==2108 and eighteen['bytes']==3748
    assert ten['capacities']==[0,10,9,10] and eighteen['capacities']==[0,18,16,18]
    assert len(old)-len(raw)==2888
    result=dict(status='PASS',original_GXFX_bytes=before,compacted10=ten,compacted18=eighteen,
                reclaimed=before-ten['bytes'],added_for_eight=eighteen['bytes']-ten['bytes'],DAT_shrink=len(old)-len(raw))
    save('evidence/budget-check.json',result);print(json.dumps(result))

if __name__=='__main__':main()
