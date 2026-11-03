"""逐档核对 MOUNT 映射和 552 B 结果，保留实际单元的 04 端点。"""
from pathlib import Path
import itertools
import json
import sys
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import H
from reference import Reference
from dat_format import expand,expand_effect,sha


def main():
    tick=time.monotonic();old=Reference(153);new=Reference(154)
    a=(H.ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT').read_bytes();b=H.DAT.read_bytes()
    controls=[];same=0;alias=0;changed=0;amount_endpoints=0;pair_count=0;legal={}
    for unit in range(3):
        for slot in range(1,9):
            for control in range(10):
                levels_old=[];levels_new=[];diff=[]
                for value in (range(151) if control==0 else range(-9,10)):
                    levels=[100]+[0]*9;levels[control]=value
                    sa,ra=old.request(a,unit,slot,levels);sb,rb=new.request(b,unit,slot,levels)
                    if sa==0:levels_old.append(value)
                    if sb==0:levels_new.append(value)
                    if unit!=2 or slot==4:
                        assert sa==sb and (sa or bytes(ra)==bytes(rb))
                        if not sa:
                            xa,pa=old.compute(a,unit,expand(a,unit,slot),levels);xb,pb=new.compute(b,unit,expand(b,unit,slot),levels)
                            assert xa==xb and pa==pb;same+=1
                    elif not sb:
                        s50,r50=new.request(b,0,slot,levels);assert s50==0 and bytes(rb)==bytes(r50);alias+=1
                        xb,pb=new.compute(b,unit,expand(b,unit,slot),levels)
                        xr,pr=new.apply(expand(b,unit,4),expand(b,unit,slot),r50)
                        assert xb==xr and pb==pr
                        if control==0 and value!=100:amount_endpoints+=1
                        if not sa:
                            xa,pa=old.compute(a,unit,expand(a,unit,slot),levels)
                            if xa!=xb or pa!=pb:changed+=1;diff.append(value)
                    if not sa and not sb and (bytes(ra)!=bytes(rb) or sa!=sb) and value not in diff:diff.append(value)
                legal[unit,slot,control]=levels_new
                if levels_old!=levels_new or diff:
                    controls.append(dict(unit=unit,slot=slot,control=control,old_levels=levels_old,new_levels=levels_new,changed_values=diff))
    for slot in (1,2,3,5,6,7,8):
        visible=[c for c in range(10) if len(legal[2,slot,c])>1]
        for left,right in itertools.combinations(visible,2):
            al=legal[2,slot,left];ar=legal[2,slot,right]
            for x,y in itertools.product(sorted(set((al[0],al[len(al)//2],al[-1]))),sorted(set((ar[0],ar[len(ar)//2],ar[-1])))):
                levels=[100]+[0]*9;levels[left]=x;levels[right]=y
                s2,r2=new.request(b,2,slot,levels);s0,r0=new.request(b,0,slot,levels)
                assert s2==s0==0 and bytes(r2)==bytes(r0)
                status,out=new.compute(b,2,expand(b,2,slot),levels)
                reference_status,reference=new.apply(expand(b,2,4),expand(b,2,slot),r0)
                assert status==reference_status and out==reference;pair_count+=1
    look_cases=0
    for unit in range(3):
        for number in range(10):
            base=expand_effect(b,number);slot=base[0]
            for control in range(10):
                for value in legal[unit,slot,control]:
                    levels=[100]+[0]*9;levels[control]=value
                    xa,pa=old.compute(a,unit,expand_effect(a,number),levels)
                    xb,pb=new.compute(b,unit,base,levels)
                    if unit!=2:assert xa==xb and pa==pb
                    else:
                        status,r0=new.request(b,0,slot,levels);assert status==0
                        xr,pr=new.apply(expand(b,unit,4),base,r0);assert xb==xr and pb==pr
                    look_cases+=1
    result=dict(status='PASS',seconds=time.monotonic()-tick,request_bytes=52,unchanged_single_control_cases=same,
        MOUNT_alias_single_control_cases=alias,MOUNT_changed_output_cases=changed,MOUNT_amount_non100_cases=amount_endpoints,
        MOUNT_pair_552_cases=pair_count,look_single_control_552_cases=look_cases,changed_controls=controls,
        math_sha256=sha((H.ROOT/'firmware/engine_v63_g154/candidate/containers/product/kv2/kv_math.c').read_bytes()))
    (HERE/'evidence/knobs.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='changed_controls'}))


if __name__=='__main__':main()
