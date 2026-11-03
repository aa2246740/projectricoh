"""Compare an observed in-flight unit state with its complete computed target."""
import argparse
import json
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from runtime import load_snapshot, sha
from reference import Reference, expand


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    a=p.parse_args()
    source=HERE/'evidence'/(a.name+'.json')
    observed=json.loads(source.read_text())
    cut=observed['at_cut']
    saved=load_snapshot(ROOT/observed['cut_snapshot']['path'])
    dat=Path(saved['dat_path']).read_bytes()
    assert sha(dat)==saved['dat_sha256']
    target=Path(cut['staging_path']).read_bytes()
    before=observed['before']
    assert before['slot']==3 and before['param']==3 and before['effect']==0
    levels=before['engine_levels'][:]
    levels[3]+=1
    math=Reference('engine_v67_g155c')
    status,expected=math.compute(dat,2,expand(dat,2,3),levels)
    assert status==0 and expected==target
    cpu=saved['cpu']
    native=next(d for t,d in zip(cpu['device_types'],cpu['devices']) if t=='StartupRegisters')['rpc_state']
    overlay={int(k):v for k,v in native['overlay'].items()}
    image=(ROOT/'artifacts/firmware/gxr-1.51/l08firm3').read_bytes()
    segments=[struct.unpack_from('>5I',image,32+20*i) for i in range(16)]
    def actual(at):
        if at&~1 in overlay:return overlay[at&~1]>>(0 if at&1 else 8)&255
        for off,base,n,_,_ in segments:
            if base<=at<base+n:return image[512+off+at-base]
        raise ValueError(hex(at))
    u32=lambda at:int.from_bytes(dat[at:at+4],'big')
    directory=u32(156)+128
    mapping=dat[u32(directory+12):][:152]
    rows=[]
    for i in range(9):
        address,n,off=struct.unpack_from('>IHH',mapping,32+12*i)
        got=bytes(actual(address+j) for j in range(n))
        rows.append(dict(row=i,bytes=n,equal=got==target[off:off+n],sha256=sha(got)))
    settings=Path(cut['settings_path']).read_bytes()
    final=observed.get('after',{})
    stores=[x for x in observed['native_settings'] if x['call']=='native-settings-store']
    result=dict(status='OBSERVED',layer='模拟器事务快照与独立主机目标核对',source=str(source),
        target_levels=levels,target_sha256=sha(target),nine_rows=rows,
        nine_rows_equal=all(x['equal'] for x in rows),T_equal=native['t']==int.from_bytes(target[445:447],'big'),
        S_selector=settings[0x36e],S_WB=[settings[0x6dd],settings[0x6de]],
        old_record=before['record'],cut_record=cut['state']['record'],
        after_record=final.get('record'),stores=stores,native_state_presets=[])
    path=HERE/'evidence'/(a.name+'-audit.json')
    assert not path.exists()
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
