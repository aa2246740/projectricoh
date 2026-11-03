"""Bind completed acceptance groups to the final candidate DAT hashes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    packages={}
    for label,name in [('release','package_v310_g155c'),('test','package_v310_g155c_test')]:
        p=ROOT/'firmware'/name
        raw=(p/'GXRCE.DAT').read_bytes()
        manifest=json.loads((p/'MANIFEST').read_text())
        digest=hashlib.sha256(raw).hexdigest()
        assert digest==manifest['dat_sha256'] and manifest['boot']==1
        packages[label]=dict(sha256=digest,bytes=len(raw),code_bytes=manifest['code_bytes'],
            code_headroom=69632-manifest['code_bytes'],main_headroom=manifest['main_headroom'])
    rows=[]
    def read(name):
        p=HERE/'evidence'/(name+'.json')
        return json.loads(p.read_text()) if p.exists() else None
    def positive(label,prefix,cold_suffix,menu_suffix,flow,levels_note,manual_name,profile='test'):
        names=[prefix+'-'+cold_suffix,prefix+'-'+menu_suffix]
        receipts=[read(x) for x in names]
        workflow=read(flow)
        manual=read(manual_name)
        good=all(d and d.get('status')=='PASS' and d['dat_sha256']==packages[profile]['sha256']
            and d.get('complete_552_equal') and d.get('T_equal') and d.get('S_plan_equal')
            and len(d.get('nine_rows',[]))==9 and all(x['equal'] for x in d['nine_rows']) for d in receipts)
        good=good and workflow and workflow.get('status')=='PASS'
        good=bool(good and manual and manual.get('status')=='PASS' and
            any(value!=(100 if index==0 else 0) for index,value in enumerate(manual['levels'])) and
            all(d['levels']==manual['levels'] and d['target_sha256']==manual['target_sha256'] for d in receipts))
        rows.append(dict(case=label,status='PASS' if good else 'OPEN',layer='模拟器实测',
            receipts=names,workflow=flow,levels=receipts[0]['levels'] if receipts[0] else None,note=levels_note))
    positive('MOUNT 内置第一轮','g155c-mount-builtin','cold1-accept','menu1-accept','g155c-mount-builtin-flow','HC BW，Cont/High/Shad 各 +1','g155c-mount-builtin-manual-accept')
    positive('MOUNT 同配方只改微调','g155c-mount-builtin','cold2-accept','menu2-accept','g155c-mount-builtin-flow','只把 Cont +1 改成 +2','g155c-mount-builtin-tweak-only-accept')
    positive('MOUNT Look','resumelook','cold-accept','menu-accept','resumelook-flow','M9 STD，Cont +1','g155c-mount-look-manual-accept')
    positive('MOUNT 用户','finaluser','cold1-accept','menu1-accept','finaluser-flow','用户第 2 条，Cont +1 改成 +2','finaluser-manual-accept')
    positive('28mm 内置','resume28','cold-accept','menu-accept','resume28-flow','GRNeg；先前的导航不同步另列','g155c-28mm-builtin-r2-manual-accept')
    positive('50mm 内置','final50','cold1-accept','menu1-accept','final50-flow','实际条目以记录和收据为准','final50-manual-accept')
    positive('release MOUNT 内置','finalrelease','cold1-accept','menu1-accept','finalrelease-flow','独立正式候选包，同包真实手动记录后重启','finalrelease-manual-accept','release')
    for case in ['bad-crc','cross-unit','not-standard','dat-change','zero']:
        name='gate-'+case+'-result';d=read(name)
        detail=read('gate-'+case+'-detail')
        good=bool(d and d.get('status')=='PASS' and detail and detail['dat_sha256']==packages['test']['sha256'])
        if good and case!='zero':good=d['S_writes']==0 and d['unit_overlay_bytes']==0 and d['boot_detail']==2
        rows.append(dict(case='BOOT '+case,status='PASS' if good else 'OPEN',layer='模拟器实测',receipt=name))
    old_name='old-body-engine-trace-result' if read('old-body-engine-trace-result') else 'old-body-new-test-result'
    old=read(old_name)
    rows.append(dict(case='旧机身执行前拒收',status='PASS' if old and old.get('status')=='PASS' and old.get('engine_entry')==0 and old.get('engine_calls')==[] else 'OPEN',
        layer='模拟器实测',receipt=old_name))
    boundary_rows=[
        dict(case='机主 HC BW 丢失根因',status='OPEN',reason='尚未复现并定位，不能把构建开关变化当成根因'),
        dict(case='完整关机持久化与再开机',status='OPEN',reason='原厂逻辑容量为 0，范围检查返回 0xF0，尚未执行 NAND 编程',receipt='store-guard-check'),
        dict(case='未完整应用后终止',status='OPEN',reason='两个电源时序最终均先完成应用再保存，没有形成中途终止样本'),
        dict(case='半按后续',status='OPEN',reason='单元 RPC 31 的业务应答尚未建模',receipt='b-half-recheck'),
        dict(case='28mm 导航一致性',status='OPEN',reason='曾观察到原生高亮与 DAT 逻辑行相差一行',receipt='navigation-consistency')]
    result=dict(verdict='有缺陷',packages=packages,groups=rows,boundaries=boundary_rows,
        completed_groups=sum(x['status']=='PASS' for x in rows),required_groups=len(rows),
        native_state_presets=[],physical_camera_verified=False,card_accessed=False)
    target=HERE/'evidence/final-matrix.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(verdict=result['verdict'],completed_groups=result['completed_groups'],required_groups=len(rows))))


if __name__=='__main__':main()
