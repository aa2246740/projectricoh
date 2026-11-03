"""用真实机身装载路径核对与 g153 同一组身份边界。"""
from pathlib import Path
import argparse
import json
import os
import sys
import time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_support import Camera,H,TMP
from dat_format import sha,seal


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case');args=parser.parse_args()
    tick=time.monotonic();root=H.ROOT
    current=dict(body=root/'firmware/package_v39_g153/local/SD_ROOT/ilaunch3',resident=root/'research/v39_g153/local/body/local/resident/build/resident.elf')
    previous=dict(body=root/'firmware/package_v39_g151/local/SD_ROOT/ilaunch3',resident=root/'firmware/resident_v39/local/resident/build/resident.elf')
    v38=dict(body=root/'firmware/package_v38_g152/local/SD_ROOT/ilaunch3',resident=root/'firmware/resident_v38/local/resident/build/resident.elf')
    new=root/'firmware/package_v39_g154_looks18_test/local/build/release-zero-users.DAT'
    variant=bytearray(new.read_bytes());variant[28:32]=(153).to_bytes(4,'big')
    folder=TMP/'fixtures';folder.mkdir(parents=True,exist_ok=True);marker=folder/'previous-marker.DAT';marker.write_bytes(seal(variant))
    cases=[('g154-release',current,new,True,154),('g154-test',current,H.DAT,True,154),
        ('g153-same-body',current,root/'firmware/package_v39_g153/local/SD_ROOT/GXRCE.DAT',True,153),
        ('current-g151',current,root/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT',False,154),
        ('g151body-g154',previous,new,False,154),
        ('current-g152',current,root/'firmware/package_v38_g152/local/SD_ROOT/GXRCE.DAT',False,154),
        ('v38body-g154',v38,new,False,154),('g154-previous-marker',current,marker,False,154),
        ('g151-same-body',previous,root/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT',True,151)]
    for name in ('g137','g139','g150','cpuprobe'):
        old=root/('firmware/package_v38_'+name+'/local/SD_ROOT/GXRCE.DAT')
        if not old.is_file():old=root/('firmware/package_v38_'+name+'/SD_ROOT/GXRCE.DAT')
        assert old.is_file(),old
        cases.append(('current-'+name,current,old,False,154))
    if args.case:
        cases=[row for row in cases if row[0]==args.case];assert len(cases)==1,args.case
    rows=[]
    for name,body,dat,ready,generation in cases:
        H.BODY=body['body'];H.BODY_SHA=sha(H.BODY.read_bytes());H.RESIDENT=body['resident']
        baseline=154 if body is current else 151 if body is previous else 139
        model_generation=generation if ready else baseline
        model_dat=dat if ready else (new if baseline==154 else root/('firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT') if baseline==151 else root/'firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT')
        engine={154:'engine_v63_g154',153:'engine_v62_g153',151:'engine_v59_g151',139:'engine_v56_g139'}[model_generation]
        H.ENGINE=(root/'firmware/package_v39_g154_looks18_test/local/build/engine.elf') if model_generation==154 else root/('firmware/'+engine+'/candidate/local/full-r13/engine.elf')
        cam=Camera('50mm',dat=model_dat)
        cam.p.files.paths['/ATA1/GXRCE.DAT']=dat.read_bytes()
        invocations=[]
        cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'],lambda b:invocations.append(True) or False)
        settings=cam.s_bytes(0,4096);unit_rows=cam.unit_rows();W=cam.writes()
        cam.h.parent();entered=cam.m.fr.native(cam.h,0x20287080,steps=30000000);assert entered['ok'],(name,entered)
        count=cam.h.u(0x2022f5ac,1);state=cam.h.u(H.R+5,1)
        assert count==(8 if ready else 7) and state==(3 if ready else 6),(name,count,state)
        if ready:assert invocations,(name,'没有 DAT 入口')
        else:
            if name=='g154-previous-marker':assert invocations==[True],(name,invocations)
            else:assert not invocations and cam.h.u(H.R+148)==0,(name,invocations)
            assert cam.h.u(0x2022f5a8)==0x2022d610
        if ready and generation==154:assert cam.ui('count')==(30 if name=='g154-test' else 27)
        if not ready or generation!=151:
            assert cam.s_bytes(0,4096)==settings and cam.unit_rows()==unit_rows and cam.writes()==W
        rows.append(dict(case=name,result='ACCEPT' if ready else 'REJECT',rows=count,state=state,
            body_sha256=sha(H.BODY.read_bytes()),dat_sha256=sha(dat.read_bytes()),unit_W=cam.writes()-W,
            S_equal=cam.s_bytes(0,4096)==settings,DAT_entries=len(invocations),entry_serial=cam.h.u(H.R+148),model_dat_sha256=sha(model_dat.read_bytes()),
            rejection_layer='DAT init 代数检查' if name=='g154-previous-marker' else '匹配装载' if ready else 'resident 身份检查',
            control_scope='旧匹配控制只判断装载；S 与 W 如实记录。' if generation==151 and ready else '新匹配与拒收均比较单元和完整 S。'))
        print(json.dumps(rows[-1]),flush=True)
    result=dict(status='PASS',seconds=time.monotonic()-tick,backend=os.environ['GXR_HARNESS_BACKEND'],cases=rows,
        shared_driver='research/v39_g153/cross_checks.py：先构造匹配模型，再在文件边界提供待核对 DAT；拒收必须没有 DAT 入口。')
    suffix='-'+args.case if args.case else ''
    (HERE/'evidence'/('identity-'+os.environ['GXR_HARNESS_BACKEND']+suffix+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',cases=len(rows),seconds=result['seconds'])))


if __name__=='__main__':main()
