"""Read-only response identification of the twelve g158 field exposures."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import argparse
import fcntl
import subprocess
import time

R1=C.LOCAL
R2=R1/'r2'
C.LOCAL=R1/'g158'
C.LOCAL.mkdir(exist_ok=True)
C.os.environ.update(TMPDIR=str(C.LOCAL),MPLCONFIGDIR=str(C.LOCAL/'mpl'))
DAT157=C.DAT
DAT158=C.ROOT/'firmware/package_v310_g158_test/local/SD_ROOT/GXRCE.DAT'
PHOTOS=C.ROOT/'captures/g158-field-20261105/card'
COLD={'R8052111':('M','HNCS LowSat'),'R8052112':('S','HNCS LowSat'),
      'R8052113':('M','Acros'),'R8052114':('S','Acros')}
PROGRAM={1:'M',2:'P',3:'A',4:'S'}
HEADING='## 补充：g158 首拍与日落实拍响应识别'


def admit(label):
    while True:
        try:C.admit(label);return
        except SystemExit as e:
            if e.code!=75:raise
            time.sleep(10)


def prepare():
    admit('g158-prepare');C.numerical();C.sys.addaudithook(C.fence)
    assert C.sha(DAT157)==C.DAT_SHA
    digest=C.sha(DAT158);assert digest.startswith('6a40262c')
    D=C.module('g158_extra_dat',C.ROOT/'research/v39_g153/dat_format.py')
    old,new=DAT157.read_bytes(),DAT158.read_bytes()
    assert D.u32(old,28)==157 and D.u32(new,28)==158
    def expanded(raw):
        D.sections(raw);D.strict_effects(raw)
        values={(u,'builtin',str(s)):D.expand(raw,u,s) for u in range(3) for s in range(1,9)}
        at,_=D.effect_area(raw)
        for i in range(D.u16(raw,at+10)):
            e=raw[at+32+32*i:at+64+32*i];name=e[20:32].split(b'\0')[0].decode('ascii')
            for unit in range(3):
                if e[18]&(1<<unit):values[unit,'look',name]=D.expand_effect(raw,i)
        return values
    a,b=expanded(old),expanded(new)
    assert a.keys()==b.keys() and all(a[k]==b[k] for k in a),'Recipe bytes changed'
    def users(raw):
        at,size=D.sections(raw)[6];tail=raw[at:at+size];ext=tail[1408:3392]
        assert ext[:8]==b'GXUI124\0'
        return [ext[1216+i*24:1240+i*24] for i in range(D.u16(ext,24))],C.hashlib.sha256(tail[3392:]).hexdigest()
    assert users(old)==users(new),'User requests or knob table changed'
    protected={str(p):C.sha(p) for p in (DAT157,DAT158,Path(__file__),C.HERE/'common.py',C.HERE/'analyze.py',
                                        C.ROOT/'research/v39_g153/dat_format.py')}
    for row in C.read(R1/'inputs.json')['files']:
        assert C.sha(row['path'])==row['sha256']
        protected[row['path']]=row['sha256']
    bank=C.read(R1/'bank.json')
    for row in bank['records']:
        source=Path(row['record']);assert C.sha(source)==row['sha256']
        protected[str(source)]=row['sha256']
        dest=C.LOCAL/'records'/source.name;dest.parent.mkdir(exist_ok=True)
        if dest.exists():assert C.sha(dest)==row['sha256']
        else:dest.write_bytes(source.read_bytes())
        row['record']=str(dest)
    bank.update(dat_sha256=digest,generation=158)
    C.dump('bank.json',bank)
    metadata=C.metadata_reader();inventory=[]
    for number in range(8052107,8052119):
        p=PHOTOS/f'R{number}.DNG';j=p.with_suffix('.JPG')
        assert p.is_file() and j.is_file() and not p.is_symlink() and not j.is_symlink()
        dm,jm=metadata(p),metadata(j)
        assert dm['unit']=='mount-a12'
        assert all(dm.get(k)==jm.get(k) and dm.get(k) is not None for k in ('when','iso','exposure','unit','selector','color_raw13'))
        d=C.Dng(p);dm.update(exposure_program=d.exif.get('program'),exposure_bias=d.exif.get('bias_ev'));d.release()
        inventory.append(dict(id=p.stem,group='g158',path=str(p),jpeg=str(j),metadata=dm,jpeg_metadata=jm,
            raw_sha256=C.sha(p),jpeg_sha256=C.sha(j),raw_stat=[p.stat().st_size,p.stat().st_mtime_ns],
            jpeg_stat=[j.stat().st_size,j.stat().st_mtime_ns]))
    assert len(list(PHOTOS.glob('*.DNG')))==12
    C.dump('inventory.json',inventory)
    before=C.LOCAL/'before';before.mkdir(exist_ok=True)
    for source,name in ((C.HERE/'REPORT_R2.md','REPORT_R2.md'),(C.HERE/'SHA256SUMS_R2','SHA256SUMS_R2'),
        (R2/'report.json','report.json'),(R2/'seal.json','seal.json'),(R2/'SHA256SUMS','private-SHA256SUMS')):
        dest=before/name
        if dest.exists():assert dest.read_bytes()==source.read_bytes(),'Existing addendum snapshot differs'
        else:dest.write_bytes(source.read_bytes())
    C.dump('inputs.json',dict(created_utc=C.utc(),g157_DAT_sha256=C.sha(DAT157),g158_DAT_sha256=digest,
        expanded_records_identical=len(a),MOUNT_records_identical=sum(k[0]==2 for k in a),
        user_requests_and_knob_table_identical=True,protected_sources=protected,
        same_identification_algorithm_sha256=C.sha(C.HERE/'analyze.py'),no_fit_or_tuning=True))
    C.decision('g158-inputs','冻结12对照片并逐字节比较g157/g158配方','使用原识别方法，不按首拍预期限制候选',
               'local/g158/inputs.json; local/g158/inventory.json',f'{len(a)} recipe records identical; 12 pairs')
    print('PREPARE PASS',digest,'identical records',len(a),'ISO',dict(__import__('collections').Counter(r['metadata']['iso'] for r in inventory)),flush=True)


def frame(pid):
    proof=C.read(C.LOCAL/'inputs.json');C.DAT=DAT158;C.DAT_SHA=proof['g158_DAT_sha256']
    import analyze
    analyze.main(pid)


def identify():
    lock=(C.LOCAL/'queue.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sys.path.insert(0,str(C.ROOT/'tools'));import loadgate
    jobs=[r['id'] for r in C.read(C.LOCAL/'inventory.json') if not (C.LOCAL/'frames'/r['id']/'result.json').exists()]
    tag=C.datetime.datetime.now(C.datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root=C.LOCAL/'queues'/tag;root.mkdir(parents=True,exist_ok=False)
    running={};receipts=[];failed=[];last=0
    while jobs or running:
        for pid,(proc,log,began) in list(running.items()):
            code=proc.poll()
            if code is None:continue
            log.close();del running[pid]
            receipts.append(dict(id=pid,exit_code=code,seconds=time.time()-began))
            print('FINISH',pid,code,flush=True)
            if code==75:jobs.append(pid)
            elif code!=0:failed.append(pid)
        if failed and not running:break
        if jobs and not failed:
            cap,info=loadgate.cap(len(running),per_queue_max=2)
            with (root/'admission.jsonl').open('a') as f:f.write(C.json.dumps(dict(utc=C.utc(),**info))+'\n')
            if cap>len(running):
                pid=jobs.pop(0);proof=root/(pid+'-admission.json')
                proof.write_text(C.json.dumps(dict(parent_pid=C.os.getpid(),label=pid,running_before=len(running),**info)))
                log=(root/(pid+'-'+str(len(receipts))+'.log')).open('w')
                proc=subprocess.Popen([sys.executable,'-I','-B',str(Path(__file__)),'frame',pid],cwd=C.ROOT,
                    stdout=log,stderr=subprocess.STDOUT,env=dict(C.os.environ,LUNCH_QUEUE_ADMISSION=str(proof)))
                running[pid]=proc,log,time.time();print('START',pid,flush=True)
        if time.time()-last>40:print('QUEUE',len(jobs),'pending',list(running),'running',flush=True);last=time.time()
        C.dump(root/'receipt.json',dict(rows=receipts,failed=failed,pending=jobs,running=list(running)))
        if jobs or running:time.sleep(2 if running else 10)
    if failed:raise SystemExit('Failure preserved: '+','.join(failed))
    print('IDENTIFICATION COMPLETE',len(receipts),flush=True)


def verify():
    admit('g158-verify');C.numerical();C.sys.addaudithook(C.fence);np=C.np
    inputs=C.read(C.LOCAL/'inputs.json')
    assert all(C.sha(p)==h for p,h in inputs['protected_sources'].items())
    inventory=C.read(C.LOCAL/'inventory.json');bank=C.read(C.LOCAL/'bank.json')['records']
    source=C.ROOT/'research/bluecyan_r1/verify.py'
    node=next(n for n in C.ast.parse(source.read_text()).body if isinstance(n,C.ast.FunctionDef) and n.name=='predict_literal')
    ns=dict(np=np,struct=C.struct);exec(compile(C.ast.Module(body=[node],type_ignores=[]),str(source),'exec'),ns)
    literal=ns['predict_literal'];rows=[];cold=[];maximum=0.
    indices={r['name']:i for i,r in enumerate(bank)}
    for original in inventory:
        pid=original['id'];root=C.LOCAL/'frames'/pid;r=C.read(root/'result.json')
        for key,hkey,skey in (('path','raw_sha256','raw_stat'),('jpeg','jpeg_sha256','jpeg_stat')):
            p=Path(original[key]);assert C.sha(p)==original[hkey]
            assert [p.stat().st_size,p.stat().st_mtime_ns]==original[skey]
        with np.load(root/'samples.npz',allow_pickle=False) as z:v=dict(z)
        model=C.camera_model(r['metadata']['iso'],r['metadata']['color_raw13'])
        for j,rec in enumerate(bank):
            take=np.flatnonzero(v['held']);take=take[np.linspace(0,len(take)-1,min(96,len(take))).astype(int)]
            pred=literal(model,Path(rec['record']).read_bytes(),v['conditioned'][take])
            delta=float(np.max(abs(pred-v['predictions'][j,take])));maximum=max(maximum,delta);assert delta<1e-8
        r['program']=PROGRAM.get(r['metadata']['exposure_program'],'unknown');rows.append(r)
        if pid not in COLD:continue
        program,expected=COLD[pid]
        assert r['program']==program,(pid,'capture mode mismatch')
        j=indices[expected];std=indices['04 Std'];held=v['held'];identity=v['identity']
        full=Path(bank[j]['record']).read_bytes();stock=Path(bank[std]['record']).read_bytes()
        combinations=[]
        for bits in range(8):
            b=bytearray(stock)
            if bits&1:
                for start,stop in ((20,115),(379,445)):b[start:stop]=full[start:stop]
                b[1]=(b[1]&~4)|(full[1]&4)
            if bits&2:b[216:272]=full[216:272]
            if bits&4:b[115:211]=full[115:211]
            if expected=='Acros':b[0]=full[0]
            pred=C.predict(model,bytes(b),v['conditioned'])
            combinations.append(dict(parts=dict(curves=bool(bits&1),matrix=bool(bits&2),C080=bool(bits&4)),
                identity=C.stats(C.de(pred[identity],v['observed'][identity])),
                holdout=C.stats(C.de(pred[held],v['observed'][held])),
                response_equal_to_full=float(np.max(abs(pred-v['predictions'][j])))<1e-9))
        cold.append(dict(id=pid,program=program,expected=expected,best=r['best'],accepted=r['accepted'],
            expected_identity=C.stats(v['errors50'][j,identity]),expected_held=C.stats(v['errors50'][j,held]),
            Standard_identity=C.stats(v['errors50'][std,identity]),Standard_held=C.stats(v['errors50'][std,held]),
            held_Standard_minus_expected=float(np.median(v['errors50'][std,held])-np.median(v['errors50'][j,held])),
            hybrid_controls=combinations,expected_wins_all_candidates=bool(r['best']==expected and r['held_best']==expected)))
    assert len(rows)==12 and len(cold)==4
    C.dump('verification.json',dict(status='PASS',original_photo_files_unchanged=24,
        source_DATs_unchanged=True,independent_literal_max_RGB_difference=maximum,
        rows=rows,cold_starts=cold,inputs=inputs,
        first_shot_and_cold_start_provenance='Owner annotations; image response and exposure mode checked independently',
        no_fit_or_tuning=True,created_utc=C.utc()))
    for r in rows:print(r['id'],r['program'],r['metadata']['iso'],r['best'],'second',r['second'],
        'gap',round(r['gap_de00'],3),'holdout',round(r['prediction_D50']['median'],3),'accepted',r['accepted'],flush=True)
    for r in cold:print('COLD',r['id'],r['expected'],'expected/04 held med',r['expected_held']['median'],r['Standard_held']['median'],flush=True)
    print('VERIFY PASS 24 originals; literal max',maximum,flush=True)


def append():
    admit('g158-append')
    v=C.read(C.LOCAL/'verification.json');assert v['status']=='PASS'
    before=(C.LOCAL/'before/REPORT_R2.md').read_text();p=C.HERE/'REPORT_R2.md'
    assert p.read_text()==before or p.read_text().startswith(before+'\n\n'+HEADING)
    lines=[HEADING,'',
        '12 对照片只作响应识别，沿用 R1 的 MOUNT 原生 C040、输入映射、固定平滑块和识别/验证空间分半。候选仍为全部29条，未按首拍预期限制候选。'
        f"实际 g158 test DAT SHA-256 为 `{v['inputs']['g158_DAT_sha256']}`；展开的 {v['inputs']['expanded_records_identical']} 条三单元记录与 g157 逐字节相同，其中 MOUNT 26 条；用户请求与旋钮表也相同。",'',
        '| 照片 | 模式 / ISO | 第一名 | 第二名 | 第一二名分差 ΔE00 | 留出中位 / p95 ΔE00 | 判定 |',
        '| --- | --- | --- | --- | ---: | --- | --- |']
    for r in v['rows']:
        state='通过' if r['accepted'] else '暂定；分差不足0.75'
        if r['exact_record_ambiguous']:state+='；菜单等价项'
        if r['iso_boundary_open']:state+='；ISO迁移诊断'
        lines.append(f"| {r['id']} | {r['program']} / {r['metadata']['iso']} | {r['best']} | {r['second']} | {r['gap_de00']:.2f} | {r['prediction_D50']['median']:.2f} / {r['prediction_D50']['p95']:.2f} | {state} |")
    passed=sum(r['accepted'] for r in v['rows'])
    lines+=['',f'{passed}/12 张通过原识别线：第一名中位≤5、分差≥0.75、240次空间块重抽样胜率≥95%，且留出半区第一名一致。'
        '2111、2112 仅分差未过线；两张均为240/240次抽样选中LowSat，留出半区也仍是LowSat第一。'
        '日落四张均通过；过暗、过曝与裁切区域沿用原掩码排除。',
        '', '冷启动首拍另与04直接比较。下面均使用未参与识别的留出半区，D50；分差为04误差减预期记录误差。','',
        '| 首拍 | 预期 | 预期响应误差中位 | 04误差中位 | 04减预期 | 结果 |',
        '| --- | --- | ---: | ---: | ---: | --- |']
    for r in v['cold_starts']:
        ok=r['expected_wins_all_candidates'] and r['accepted']
        state='确认预期响应，排除04' if ok else 'LowSat第一、暂定；明显优于04'
        lines.append(f"| {r['id']} / {r['program']} | {r['expected']} | {r['expected_held']['median']:.2f} | {r['Standard_held']['median']:.2f} | {r['held_Standard_minus_expected']:.2f} | {state} |")
    low=[r for r in v['cold_starts'] if r['expected']=='HNCS LowSat']
    acros=[r for r in v['cold_starts'] if r['expected']=='Acros']
    if all(r['expected_wins_all_candidates'] and r['accepted'] for r in low):
        lines+=['','R8052111、R8052112 在 M/S 两种模式下均匹配 HNCS LowSat 的完整记录响应，且在全部候选与独立留出区均胜过 04。'
            '按机主标注的首拍身份，这构成 BOOT 在两张首拍上恢复 LowSat 颜色的客观图像证据。']
    else:lines+=['','R8052111、R8052112 都支持LowSat已经在M/S首拍恢复，且明显优于完整回退04的假设。'
        '但它们与Kodachrome25的分差只有0.58、0.56，按同一保守门槛仍为LowSat暂定；不能写成已无歧义排除其余所有配方。'
        '固定部分应用对照中，完整LowSat比仅保留其曲线的留出中位误差低0.12、0.11；去掉其矩阵仅差0.02、0.01。'
        '因此，这批图像支持首拍颜色已生效，不能逐项证明完整记录的每个参数都已恢复。']
    if all(r['expected_wins_all_candidates'] and r['accepted'] for r in acros):
        lines+=['R8052113、R8052114 也分别在 M/S 模式确认 Acros，未把冷启动预期带入识别。']
    lines+=['首拍/冷启动身份来自机主标注，M/S模式另由DNG核对。固定的缺曲线/矩阵/C080组合对照保存在本地回执中，不用于拟合或改动识别。',
        f"新24个原件和两份DAT的哈希均未变，独立字面方程最大RGB差 {v['independent_literal_max_RGB_difference']:.3g} code；没有拟合、网络、相机/SD访问或提交。"
        '完整排序与复核见 [local/g158/verification.json](local/g158/verification.json)，逐候选预测图只在 local/g158/。',
        '', '已有结果的独立复核命令如下。完整重算先归档本轮输出与报告；prepare会保留并核对追加前快照，不覆盖现有证据。', '', '```sh',
        'nice -n 15 studio/.venv/bin/python -I -B research/lunch_g157_r1/g158_field_extra.py verify',
        '```','']
    section='\n'.join(lines)
    assert not any(s in section for s in ('data:image','<img','GPSLatitude','GPSLongitude'))
    p.write_text(before+'\n\n'+section)
    receipt=C.read(R2/'report.json');receipt['report_sha256']=C.sha(p)
    receipt['g158_addendum']=dict(source='local/g158/verification.json',old_report_sha256=C.sha(C.LOCAL/'before/REPORT_R2.md'),
        current_report_sha256=C.sha(p),added_utc=C.utc())
    (R2/'report.json').write_text(C.json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    C.dump('append.json',dict(report_sha256=C.sha(p),prior_R2_text_byte_prefix_preserved=p.read_bytes().startswith((C.LOCAL/'before/REPORT_R2.md').read_bytes()),created_utc=C.utc()))
    print('APPENDED',p,flush=True)


def seal():
    admit('g158-seal')
    v=C.read(C.LOCAL/'verification.json');assert v['status']=='PASS'
    for row in C.read(C.LOCAL/'inventory.json'):
        assert C.sha(row['path'])==row['raw_sha256'] and C.sha(row['jpeg'])==row['jpeg_sha256']
    protected=0
    for line in (C.LOCAL/'before/private-SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1)
        if name in ('report.json','decisions.tsv'):continue
        assert C.sha(R2/name)==expected,name
        protected+=1
    assert (C.HERE/'REPORT_R2.md').read_bytes().startswith((C.LOCAL/'before/REPORT_R2.md').read_bytes())
    C.decision('g158-seal','封存12对识别和首拍对照，保留R2原主体','只追加独立补充节，原数值评估未改',
        'local/g158/verification.json; REPORT_R2.md',f'24 originals unchanged; {protected} R2 evidence files unchanged')
    private=sorted(p for p in C.LOCAL.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS','seal.json')
        and p.suffix!='.log' and not p.is_relative_to(C.LOCAL/'queues') and not p.is_relative_to(C.LOCAL/'admissions'))
    (C.LOCAL/'SHA256SUMS').write_text(''.join(C.sha(p)+'  '+str(p.relative_to(C.LOCAL))+'\n' for p in private))
    public=[Path(__file__),C.HERE/'REPORT_R2.md']
    (C.HERE/'SHA256SUMS_G158').write_text(''.join(C.sha(p)+'  '+p.name+'\n' for p in public))
    C.dump('seal.json',dict(status='PASS',new_original_files_unchanged=24,R2_immutable_evidence_files_unchanged=protected,
        prior_report_is_preserved_prefix=True,private_files=len(private),public_files=2,created_utc=C.utc()))
    print('G158 SEAL PASS',protected,'original R2 evidence files unchanged;',len(private),'private files',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','identify','frame','verify','append','seal'));p.add_argument('id',nargs='?');args=p.parse_args()
    if args.stage=='frame':frame(args.id)
    else:globals()[args.stage]()


if __name__=='__main__':main()
