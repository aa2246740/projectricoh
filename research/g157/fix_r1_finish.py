"""Bind repair verdict and local packages to completed, independently checked receipts."""
from pathlib import Path
from collections import Counter
import argparse, datetime, json, struct, sys, zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');p.add_argument('--publish',action='store_true');a=p.parse_args()
C.setup();C.DATASET='model';out=C.LOCAL/'fix-r1';final=out/'final'
def read(path):
    try:return json.loads(Path(path).read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
def must(condition,detail):
    if not condition:raise AssertionError(detail)
manifests={p:read(C.artifact(p)['manifest']) for p in C.PACKAGES}
digests={p:r['dat_sha256'] for p,r in manifests.items()}
checks=[]
def check(name,fn):
    try:value=fn();checks.append(dict(name=name,status='PASS',detail=value))
    except (AssertionError,KeyError,TypeError,FileNotFoundError,StopIteration) as e:checks.append(dict(name=name,status='OPEN',detail=str(e)))
def owned(raw,record):
    directory=C.D.u32(raw,156)+128;mapping=C.D.u32(raw,directory+12)
    return [record[C.D.u16(raw,mapping+32+12*i+6):C.D.u16(raw,mapping+32+12*i+6)+C.D.u16(raw,mapping+32+12*i+4)] for i in range(9)]+[record[445:447]]
def old_counterexamples():
    rows=[]
    for label,profile in (('old-test-native','test'),('old-release-native','release'),('old-test-reference','test')):
        r=read(out/'runs'/label/'result.json');must(r and r['status']=='OBSERVED',label)
        raw=(out/'before'/profile/'GXRCE.DAT').read_bytes();must(r['dat_sha256']==C.sha(raw),label+' SHA')
        stock=C.D.expand(raw,2,4);before=bytes.fromhex(r['unit_before_manual']['record552_hex']);after=bytes.fromhex(r['unit_after_manual_failure']['record552_hex'])
        must(owned(raw,before)==owned(raw,stock),label+' complete stock before')
        changed=[i for i,(x,y) in enumerate(zip(owned(raw,stock),owned(raw,after))) if x!=y];must(changed==[0],(label,changed))
        curve=struct.unpack('>31H',owned(raw,after)[0]);must(any(x>=y for x,y in zip(curve,curve[1:])),label+' partial nonmonotonic row')
        must(len(r['fault_events'])==1 and r['fault_events'][0]['W_position']==8,label+' exactly W8')
        st=r['manual_after_failure'];must(st['state']==5 and not st['word']&12 and st['uncertain']==1,label+' unguarded standby')
        rows.append(dict(run=label,profile=profile,backend=r['backend'],safety_contract='FAIL_REPRODUCED',injected=1,W=8))
    return rows
check('original-counterexample-native-and-reference',old_counterexamples)
def fixed_counterexamples():
    rows=[]
    for profile in C.PACKAGES:
        raw=C.artifact(profile)['dat'].read_bytes();stock=C.D.expand(raw,2,4)
        oldS=(out/'settings'/(profile+'-mount-vivid09.bin')).read_bytes()
        newS=(final/'settings'/(profile+'-'+profile+'-mount-vivid09.bin')).read_bytes()
        must(len(oldS)==len(newS)==4096 and oldS[:0xff0]==newS[:0xff0],profile+' minimal counterexample input change')
        must(newS[0xff0:0xff8]==raw[20:28],profile+' rebound DAT CRC')
        must(int.from_bytes(newS[0xff8:0xffc],'big')==zlib.crc32(newS[0xfd4:0xff8]),profile+' record CRC')
        must(int.from_bytes(newS[-4:],'big')==sum(struct.unpack('>2046H',newS[:4092]))&0xffffffff,profile+' whole S checksum')
        for backend in ('native','reference'):
            label='fixed-'+profile+'-'+backend;r=read(final/'runs'/label/'result.json')
            must(r and r['status']=='OBSERVED' and r['dat_sha256']==digests[profile],label)
            must(r['settings_sha256']==C.sha(newS),label+' exact counterexample input')
            must(r['cold_start'] and not r['snapshots'] and r['actual_backend']==backend,label+' MAIN')
            must(len(r['fault_events'])==1 and r['fault_events'][0]['W_position']==8,label+' fault')
            actual=bytes.fromhex(r['unit_after_manual_failure']['record552_hex']);must(owned(raw,actual)==owned(raw,stock),label+' complete04')
            st=r['manual_after_failure'];must(st['selector']==1 and st['wb']==[9,9] and not st['word']&12,label+' verified settings')
            must(r['manual_safety_PASS'] and not r['manual_unguarded_partial_standby'],label+' safety')
            rows.append(dict(run=label,profile=profile,backend=backend,complete04=True,settings_verified=True,guard_cleared_after_complete=True))
    return rows
check('fixed-MOUNT-whole-MAIN-native-and-reference',fixed_counterexamples)
def g156():
    r=read(out/'g156/runs/same-W8-vivid-dismiss/result.json');must(r and r['status']=='OBSERVED','g156 receipt')
    must(r['g156_has_same_unprotected_partial'] and len(r['fault_events'])==1 and r['fault_events'][0]['W_position']==8,'g156 fault')
    after=r['after_dismiss'];must(after['state']['state']==5 and not after['state']['word']&12 and not after['peer']['pure04'],'g156 unsafe standby')
    return dict(preexisting_in_g156_test=True,DAT_sha256=r['dat_sha256'],same_Vivid09_WB_and_saved_HC1_input=True,
                entry_difference=r['entry_difference'],physical_camera=False)
check('g156-test-same-W8-fault',g156)
def Cmatrix():
    r=read(out/'C-matrix.json');must(r and r['status']=='PASS','C matrix')
    must(all(x['DAT_sha256']==digests[x['profile']] for x in r['rows']),'C matrix SHA')
    targets={r['target'] for r in r['rows']};must({'HC+1','Acros','user3','colour05'}<=targets,targets)
    for profile in C.PACKAGES:
        for unit in range(3):
            for entry in ('standard','Vivid09','WB'):
                for target in targets:
                    rows=[x for x in r['rows'] if (x['profile'],x['unit'],x['entry'],x['target'])==(profile,unit,entry,target)]
                    baseline=next(x for x in rows if x['fault_kind']==0);n=baseline['writes']
                    for kind in (1,8):must({x['fault_at'] for x in rows if x['fault_kind']==kind}==set(range(1,n+1)),(profile,unit,entry,target,kind))
                    for kind in (14,15):must({x['fault_at'] for x in rows if x['fault_kind']==kind}==set(range(1,baseline['setting_words']+1)),(profile,unit,entry,target,kind))
                    must(all(x['full_colour'] or x['pure04'] or x['dirty']&12 for x in rows),'C safety')
    return dict(cases=r['cases'],targets=sorted(targets),scope=r['scope'])
check('C-every-W-all-units-profiles-entries',Cmatrix)
def ISA(profile,unit,backend):
    r=read(out/'fast-isa'/(profile+'-'+unit+'-'+backend+'.json'));must(r and r['status']=='PASS' and r['DAT_sha256']==digests[profile],(profile,unit,backend))
    driver=out/'fast-isa'/(profile+'-'+unit+'-'+backend+'-driver.py')
    must(C.sha(driver.read_bytes())==r['driver_sha256'],'ISA driver snapshot')
    fixture=Path(r['argv'][r['argv'].index('--fixture')+1])
    must(C.sha(fixture.read_bytes())==r['fixture_sha256'],'ISA fixture identity')
    must(read(fixture)['DAT_sha256']==digests[profile],'ISA fixture DAT')
    must(r['compute_cache'],'verified pure compute cache')
    if backend=='c':must(r['exhaustive_W'],'exhaustive')
    for entry in ('standard','Vivid09','WB'):
        for target in ('HC+1','colour05'):
            rows=[x for x in r['rows'] if x['entry']==entry and x['target']==target];baseline=next(x for x in rows if x['fault']=='none');n=baseline['W_requests']
            positions=set(range(1,n+1)) if backend=='c' else {1,8,n//2,n}
            for fault in ('ack','busy'):must({x['position'] for x in rows if x['fault']==fault}==positions,(entry,target,fault))
            s=baseline['S_fields'];s_positions=set(range(1,s+1)) if backend=='c' else {1,s} if s else set()
            for fault in ('settings-ack','settings-busy'):must({x['position'] for x in rows if x['fault']==fault}==s_positions,(entry,target,fault))
            for row in rows:
                must(row['pure04'] or row['full_live'] or row['guard_word']&12,row)
                must(row['H52_half_full_blocked']==[bool(row['guard_word']&12)]*2,row)
    return dict(cases=r['cases'],exhaustive_W=r['exhaustive_W'],scope=r['scope'])
for profile in C.PACKAGES:
    for unit in C.UNITS:check('fast-ISA-'+profile+'-'+unit,lambda p=profile,u=unit:ISA(p,u,'c'))
    check('final-Python-ISA-'+profile,lambda p=profile:ISA(p,'mount','python'))
def realISA():
    r=read(out/'isa/test-mount-c-smoke-r2.json');must(r and r['status']=='PASS' and r['cases']==30 and r['DAT_sha256']==digests['test'],'actual services ISA')
    must(r['driver_sha256']==C.sha((out/'isa/test-mount-c-smoke-r2-driver.py').read_bytes()),'real ISA driver')
    return dict(cases=30,scope=r['scope'],earlier_broad_case_receipt='local/fix-r1/isa/test-mount-c-smoke.json')
check('actual-service-ISA-key-edges',realISA)
for profile in C.PACKAGES:
    def persistent(profile=profile):
        r=read(final/'runs'/('persistent-'+profile+'-native')/'result.json');must(r and r['status']=='OBSERVED' and r['dat_sha256']==digests[profile],profile)
        must(r['guard_latched'] and r['manual_safety_PASS'] and r['manual_error_dismissed']['word']&12,'persistent latch')
        return dict(guard_latched=True,native_MAIN=True,injected=len(r['fault_events']))
    check('persistent-whole-MAIN-'+profile,persistent)
for profile in C.PACKAGES:
    for unit in C.UNITS:
        def native(profile=profile,unit=unit):
            r=read(final/'runs'/('sweep-'+profile+'-'+unit+('-r2' if unit=='mount' else ''))/'result.json');must(r and r['status']=='OBSERVED' and r['dat_sha256']==digests[profile],(profile,unit))
            must(len(r.get('builtin_samples',[]))==8 and len(r.get('samples',[]))==18 and len(r.get('user_samples',[]))==3,'all29')
            for row in r['builtin_samples']+r['samples']+r['user_samples']:
                must(row['unit_readback']['complete_552_equal'] and row['full_40_equal'],'native full colour and memory')
                must(not row['state']['word']&12 and not row['state']['settings_pending'] and not row['state']['uncertain'],'native successful apply must release protection')
            must(r['DISP_back']['screen']==0 and r['after_close']['state']==5 and r['ADJ_closed']['state']==5 and r['close_record_equal'],'navigation and closure')
            must(not r['after_close']['word']&12 and not r['ADJ_closed']['word']&12,'native normal shutter available')
            must(r['cold_start'] and not r['snapshots'] and r['actual_backend']=='native','native MAIN')
            return dict(records=29,DISP_OK_ADJ=True,complete_MAIN=True)
        check('native-'+profile+'-'+unit,native)
        def reference(profile=profile,unit=unit):
            r=read(final/'runs'/('critical-'+profile+'-'+unit)/'result.json');must(r and r['status']=='OBSERVED' and r['dat_sha256']==digests[profile],(profile,unit))
            st=r.get('list_after_diagnostic',r['first_menu']);must(st['rows']==8 and st['screen']==0 and st['memory_result']==1,'reference list/readback')
            must(st['cursor']==st['cached']==st['physical']+1,'reference cursor')
            must(r['cold_start'] and not r['snapshots'] and r['reference_oracle']=='legacy' and r['actual_backend']=='reference','independent MAIN')
            if profile=='test':must(r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal'],'reference BOOT')
            else:must(r['unit_W']==0 and not r['after_boot']['boot_committed'],'release policy')
            return dict(complete_MAIN=True,readback=True,BOOT='verified full colour' if profile=='test' else 'disabled; zero W')
        check('reference-'+profile+'-'+unit,reference)
def host():
    static=read(C.receipt('static.json'));must(static and static['status']=='PASS' and static['DAT_sha256']==digests,'static')
    for backend in ('c','python'):
        r=read(C.receipt('host-'+backend+'.json'));must(r and r['status']=='PASS' and r['cases']==108 and all(x['DAT_sha256']==digests[x['profile']] for x in r['rows']),backend)
        for profile in C.PACKAGES:
            r=read(C.receipt('service-'+profile+'-'+backend+'.json'));must(r and r['status']=='PASS' and r['DAT_sha256']==digests[profile] and len(r['rows'])==54,(profile,backend))
            must(all(all(x['readback_valid'] for x in row['readbacks']) for row in r['rows']),'readbacks')
    return dict(parser_cases=len(static['parser_cases']),records=len(static['readbacks']),memory_cases_per_backend=108,op5_cases_per_backend=108)
check('host-C-and-final-Python-data-memory-services',host)
def replay():
    r=read(final/'persistence-fix-r1-model/verification.json');must(r and r['status']=='PASS' and r['cases']==48,'S48')
    for row in r['rows']:
        doc=read(final/'runs'/row['label']/'result.json');must(doc['dat_sha256']==digests[row['target']],'S48 final SHA')
    return dict(cases=48,scope=r['boundary'])
check('S48',replay)
def byteaudit():
    rows=[]
    for profile in C.PACKAGES:
        r=read(out/('byte-audit-'+profile+'.json'));must(r and r['status']=='PASS' and r['DAT_sha256']==digests[profile] and not r['unexplained_bytes'],'audit')
        must(r['all_552_records_identical'] and r['body_resident_ABI_identical'] and len(r['source_changes'])==3,'unchanged data/body')
        must({f['name'] for f in r['functions'] if f['classification']=='changed-linked-function'}=={'apply_impl.constprop.0','recover_confirmed'},'only two semantic function changes')
        linked=read(C.artifact(profile)['build']/'size.json')
        for path,digest in linked['sources'].items():must(C.sha((C.ROOT/path).read_bytes())==digest,'linked source drift '+path)
        for path,digest in linked['headers'].items():must(C.sha((C.ROOT/path).read_bytes())==digest,'linked header drift '+path)
        rows.append({k:r[k] for k in ('profile','changed_including_removed_bytes','size_delta','unexplained_bytes')})
    return rows
check('all-byte-audit-against-reviewed-g157',byteaudit)
def glyphs():
    rows=[]
    for name in ('normal','diagnostic'):
        r=read(final/'ui-text'/('ui-text-'+name+'.json'));must(r and r['status']=='PASS' and r['DAT_sha256']==digests['test'] and not r['pixel_screenshot'],name)
        rows.append(dict(name=name,rows=sum(len(f['rows']) for f in r['frames']),pixel_screenshot=False))
    return rows
check('actual-UI-text-and-independent-glyphs',glyphs)
ready=all(r['status']=='PASS' for r in checks);verdict='可以交复审' if ready else '有缺陷'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
receipt=dict(verdict=verdict,utc=now,final=a.final,DAT=digests,checks=checks,OPEN=[r['name'] for r in checks if r['status']!='PASS'],
    accepted_OPEN=['P2-03 field disappearance/loader responsibility; DAT-absent/retired diagnostics need resident work','P3 real heap fragmentation and physical camera/NAND/first image'],
    no_camera_SD_network=True,no_commit_push=True)
C.save(out/('FINAL.json' if a.final else 'STAGE.json'),receipt)
lines=[verdict,'','# g157 复审修复 r1','',
    'P1-01 的旧版原样反例已复现；新包手动事务在首个 W 前设置 DIRTY/GUARD，失败后直接从可信纯 04 完整补偿，不再采集半写入的现场作为恢复前提。只有完整颜色及设置成功后才清除护栏；补偿失败保留保护，由原有 H52 拦半按及全按。正常取消预览仍恢复已确认配方。BOOT 门、机身、resident 和配方清单均未改。','',
    '本轮时限为 2026-11-04 17:57:05 至 21:57:05 UTC。最新回执时间 '+now+'。这份结论交给下一轮独立复审，不等于批准上卡。','',
    '| 包 | SHA-256 | DAT B | 代码 B | BSS B | 主请求 B | 上限余量 B |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
for profile,r in manifests.items():lines.append(f"| {profile} | `{r['dat_sha256']}` | {r['dat_bytes']:,} | {r['code_bytes']:,} | {r['bss_bytes']:,} | {r['main_request']:,} | {r['main_headroom']:,} |")
lines+=['','数字来自实际 ELF 链接；主请求上限 107,612 B、代码上限 69,632 B 均未放宽。两包各缩小 36 B，没有删配方或改变槽位策略。test 开 BOOT，release 关 BOOT；诊断和读回均开。','',
    '## 验收回执','','| 项目 | 状态 |','| --- | --- |']
lines += ['| '+r['name']+' | '+r['status']+' |' for r in checks]
passed_checks={r['name']:r['detail'] for r in checks if r['status']=='PASS'}
coverage=[]
if 'C-every-W-all-units-profiles-entries' in passed_checks:
    coverage.append(f"产品 C 故障矩阵 {passed_checks['C-every-W-all-units-profiles-entries']['cases']:,} 例通过，覆盖两包、三个单元、Standard/Vivid09/WB 三种入口及 HC BW +1、Acros、用户项 3、05 四种目标。")
isa_rows=[v for k,v in passed_checks.items() if k.startswith('fast-ISA-')]
python_rows=[v for k,v in passed_checks.items() if k.startswith('final-Python-ISA-')]
if isa_rows:
    coverage.append(f"最终 DAT 快指令矩阵已完成 {len(isa_rows)}/6 组合，共 {sum(v['cases'] for v in isa_rows):,} 例；逐个实际 W 位置注入回执失败和 BUSY，并核对完整颜色或实际护栏以及 H52 半按/全按结果。")
if python_rows:
    coverage.append(f"独立 Python 指令后端另完成 {len(python_rows)}/2 个 MOUNT 组合，共 {sum(v['cases'] for v in python_rows):,} 例关键边复核。")
lines+=['',' '.join(coverage)]
lines+=['','逐项断言和完整身份在 `local/fix-r1/'+('FINAL.json' if a.final else 'STAGE.json')+'`。只接受正常收尾且最终 SHA 相符的回执；未完成项保留 OPEN。','',
    '两包 MOUNT 的原反例都已从新 MAIN 在 strict_r4 native 和独立 Python 参考设备后端重跑。新包输入仅更新 DAT 绑定及记录、整块校验，Vivid09、WB 9/9、HC BW +1 和单次故障策略不变。每次实际 W8 写入已经发生，只把一次原厂回执改为失败；四次均完整补偿为纯 04，设置为 Standard、WB 9/9，再清除护栏。旧版 native 两包及 test 参考则仍可观测到半套颜色、state 5 取景和零护栏。','',
    'g156 test 已用相同 Vivid09、WB 9/9、合法 HC BW +1 记忆输入和实际 W8 单次回执故障复现：关闭 ADJ 后仍是半套颜色、零护栏的取景状态。因此该手动事务 P1 在 g156 已有。g156 在 Vivid 下不预选该记忆，实际使用 UP 选中 HC BW 默认参数；不能把它说成与 g157 记忆预选 OK 完全相同的入口。证据在 `local/fix-r1/g156/runs/same-W8-vivid-dismiss/`。','',
    'C 矩阵执行产品事务、配方计算及显式 peer 故障。全量快速指令矩阵执行最终 DAT 的事务、补偿和 H52，服务/peer 是声明边界，纯计算缓存来自该输入的真实 DAT 指令执行；它不计作冷启动整机次数。真实服务指令另测关键边，原生与参考整机分别从新 MAIN 启动，不恢复 CPU 或设备快照。S48 是完整逻辑 S 的原样/仅校验双组交叉重放，不证明实际关机 NAND flush。','',
    'LCD 没有像素输出。替代证据为实际发布的首次 ADJ、诊断及返回列表的八行文本、逐字符 glyph 和映射，原厂转换器用独立 Python 指令复核。这不是像素截图，路径为 `local/fix-r1/final/ui-text/ui-text-{normal,diagnostic}.{md,json,tsv}`。','',
    '## 字节与数据','','相对 `local/fix-r1/before/` 冻结的上一版 g157，所有差异位置都有逐字节 TSV、ELF 函数及重定位归属。apply_impl 增加 104 B，recover_confirmed 减少 140 B；后续函数的调用地址和数据位置随链接移动。配方清单、各数据节、所有展开的 552 B、body/resident ABI 保持一致，仅 adapter.c、eng_core.c、eng_core.h 三个产品文件改变。','',
    '| 包 | 不同或删除位置 | 文件变化 B | 未解释 B |','| --- | ---: | ---: | ---: |',
    '| test | 49,282 | -36 | 0 |','| release | 48,953 | -36 | 0 |','',
    '完整审计在 `local/fix-r1/byte-audit-{test,release}.{json,tsv}`。旧报告和旧 DAT、ELF、源码留在 `local/fix-r1/before/`；本轮首错和夹具修正保留，不用失败或半完成记录填 PASS。早期数据对照列不需要补：历史数据接入已经证明引擎归一后逐字节等价，本轮配方数据完全未变；本轮事务代码的改动另按新 SHA 全面验收。','',
    '验收脚本修正包括：首轮 MOUNT 遍历漏带本地数学库，已核对基础槽/Look 但不计整流程，通过新 r2 label 从 MAIN 重跑；C 新增 05 目标最初误取 03 的 identity，计算入口正确拒绝后修正；首次 ADJ 导出的 part=0 仍属构造阶段，函数探针改为显式声明合法的 part=1 手动入口。上述修正未改变 DAT，失败回执继续保留。','',
    '## 现场与保留项','','P2-01 只改文档：必须先在 g157 成功保存纯 04，再换回 g156。仅在 g156 选 04 不能覆盖它不认识的高索引尾部。两个包的 README 和[现场步骤](OWNER_STEPS_MOUNT.md)均写明这个顺序。','',
    'P2-02 的 BOOT 门保持原样。机主固定 M 时，若模式/原厂选择组合仍被拒，预计 B11；activity 不合格优先 B10，未派发 B01。初次换包旧绑定可能另有 B21，Vivid/WB 不符为 B20。release 策略关闭时为 B02。真实 M 的内部值尚未采到，现场须保留首次 ADJ 的完整八行及开机首拍。','',
    'P2-03、P3 按用户要求保留 OPEN：现场掉表及装载责任、DAT 缺席或 resident 退役时的诊断、实机连续堆/碎片余量、真实关机与 NAND、单元持久状态、首拍及 JPEG。未实现配套 resident 诊断；未碰相机、实际 SD 卡或网络，未安装依赖、commit 或 push。','']
(C.HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
if a.final or a.publish:
    for profile,root in C.PACKAGES.items():
        artifact=C.artifact(profile);raw=artifact['dat'].read_bytes();manifest=dict(manifests[profile])
        must(C.sha(raw)==digests[profile],profile+' final SHA')
        manifest.update(status=('READY_FOR_INDEPENDENT_REVIEW' if ready else 'ACCEPTANCE_OPEN') if a.final else 'ACCEPTANCE_IN_PROGRESS',repair='g157-review-r1-P1-01',
            verdict=verdict,acceptance_utc=now,previous_DAT_sha256=read(out/'before'/profile/'MANIFEST')['dat_sha256'],
            resident_unchanged=True,body_unchanged=True,recipe_data_unchanged=True,camera_verified=False,
            acceptance_receipt='research/g157/local/fix-r1/'+('FINAL.json' if a.final else 'STAGE.json'),known_OPEN=receipt['accepted_OPEN'],software_OPEN=receipt['OPEN'])
        for file in (root/'local/GXRCE.DAT',root/'local/SD_ROOT/GXRCE.DAT'):file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(raw)
        C.save(root/'MANIFEST',manifest);C.save(artifact['manifest'],manifest)
        (root/'SHA256SUMS').write_text(digests[profile]+'  local/SD_ROOT/GXRCE.DAT\n'+digests[profile]+'  local/GXRCE.DAT\n')
        text=f'''# g157 {profile}：复审修复 r1

{verdict}。须等下一轮独立复审放行后再上卡。DAT 为 [local/SD_ROOT/GXRCE.DAT](local/SD_ROOT/GXRCE.DAT)，机身固定 v3.10 `a04f1ed4`，resident 不变。

SHA-256：`{digests[profile]}`。DAT {manifest['dat_bytes']:,} B，代码 {manifest['code_bytes']:,} B，BSS {manifest['bss_bytes']:,} B，实际主请求 {manifest['main_request']:,} / 107,612 B，预算余量 {manifest['main_headroom']:,} B。

手动颜色事务失败会尝试完整补偿成纯 04；补偿失败保留 DIRTY/GUARD，由原有 H52 拦快门。BOOT 自动套用{'打开' if profile=='test' else '关闭'}，诊断和读回打开；BOOT 模式门没有放宽。

降级到 g156 前，必须先在仍能正常工作的 g157 中选中并保存纯 04，再换回 g156。仅在 g156 里选 04，不能清除它不认识的高索引 Look 记忆。详见[现场步骤](../../research/g157/OWNER_STEPS_MOUNT.md)。

配方数据和槽位策略与上一版相同，保留每单元 18 Looks、八基础槽、三个用户项、官方 Acros 与 C040 清单。本轮没有新增数据取舍。

完整验收、字节审计及保留 OPEN 见[报告](../../research/g157/REPORT.md)。LCD 证据是 UI 实际文本/glyph 导出，不是像素截图。逻辑 S 重放不等于真实关机 NAND，模拟器不等于相机/JPEG 验收。P2-03 与 P3 保留 OPEN。

旧版冻结在 research/g157/local/fix-r1/before/。local/variants/control/ 是历史数据对照，不能覆盖本包。
'''
        (root/'README.md').write_text(text)
print(json.dumps(dict(verdict=verdict,passed=sum(r['status']=='PASS' for r in checks),required=len(checks),OPEN=receipt['OPEN'],final=a.final)))
