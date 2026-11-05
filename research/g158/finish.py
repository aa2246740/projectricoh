"""Publish only observed g158 checks; keep the PASM peripheral boundary explicit."""
from pathlib import Path
import argparse,datetime,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent));import common as C
p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args()
C.setup();C.DATASET='model';out=C.LOCAL
def read(path):
    try:return json.loads(Path(path).read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
def require(ok,why):
    if not ok:raise AssertionError(why)
man={p:read(C.artifact(p)['manifest']) for p in C.PACKAGES};sha={p:r['dat_sha256'] for p,r in man.items()}
checks=[]
def check(name,fn,scope):
    try:r=fn();checks.append(dict(name=name,status='PASS',detail=r,scope=scope))
    except (AssertionError,FileNotFoundError,TypeError,KeyError,StopIteration) as e:checks.append(dict(name=name,status='OPEN',detail=str(e),scope=scope))
def doc(path,digest=None):
    r=read(path)
    require(r and r['status'] in ('PASS','OBSERVED'),str(path)+': '+(str(r.get('error',r.get('status'))) if r else 'no completed receipt'))
    if digest:require(r.get('dat_sha256',r.get('DAT_sha256'))==digest,'artifact identity '+str(path))
    return r
def static():
    r=doc(C.receipt('static.json'));require(r['DAT_sha256']==sha and len(r['readbacks'])==156,'static SHA/data')
    return dict(parser_cases=len(r['parser_cases']),records=len(r['readbacks']),sizes=r['arena']['sizes'])
check('静态解析、全部配方与布局',static,'实际 C parser；156 条完整记录；机身/resident 和 arena。')
def gate():
    r=doc(out/'gate/result.json');require(r['cases']==589972,'gate domain count');require(len(r['added_only'])==4,'only four new pairs');return {k:r[k] for k in ('cases','added_only')}
check('模式门全部 uint8 模式/子模式与 N 边界',gate,'实际旧/新 C 门；原许可保持，仅新增四个实测组合。')
for sub,name in enumerate(('P','A','M','S')):
    def matrix(sub=sub):
        r=doc(out/('C-matrix-'+str(sub)+'.json'));require(r['cases']==33996,'C every-W count')
        require(all(x['DAT_sha256']==sha[x['profile']] and x['raw_mode']==4 and x['submode']==sub and (x['full_colour'] or x['pure04'] or x['dirty']&12) for x in r['rows']),'C scope/oracle')
        return dict(cases=r['cases'],three_units=True,both_packages=True,entries=['standard','Vivid09','WB'])
    check('P1 全写入矩阵 '+name,matrix,'实际产品 C/math 和新门；声明 peer/services；每个 W 的写后回执错误/BUSY，逐 S 字段与持续故障。')
def bootmatrix():
    r=doc(out/'BOOT-C-matrix.json',sha['test']);require({x['submode'] for x in r['rows']}==set(range(4)),'BOOT all PASM');return dict(cases=r['cases'])
check('BOOT 独立补偿矩阵',bootmatrix,'test 的 BOOT C 编排；共享 deep/readback，但不调用 apply_impl/recover_confirmed。release 策略关闭。')
for profile in C.PACKAGES:
    for backend in ('c','python'):
        def isa(profile=profile,backend=backend):
            suffix='-smoke' if backend=='c' else ''
            r=doc(out/'fast-isa'/(profile+'-mount-'+backend+'-PASM'+suffix+'.json'),sha[profile])
            require({x['submode'] for x in r['rows']}==set(range(4)),'ISA all four submodes')
            require(all(x['pure04'] or x['full_live'] or x['guard_word']&12 for x in r['rows']),'ISA safety')
            return dict(cases=r['cases'],all_four_submodes=True,exhaustive_W=r['exhaustive_W'])
        check('最终 DAT 指令 '+profile+'/'+backend,isa,'MOUNT，四个实测子模式的关键故障点与实际 H52；声明 services/peer；完整全 W 另由 C 矩阵覆盖。')
for profile in C.PACKAGES:
    for unit in C.UNITS:
        def critical(profile=profile,unit=unit):
            r=doc(out/'runs'/('critical-'+profile+'-'+unit+'-P')/'result.json',sha[profile])
            require(r['actual_backend']=='native' and r['cold_start'] and not r['snapshots'],'new native MAIN')
            s=r['after_boot'];require(s['raw_mode']==4 and s['submode']==0 and s['native_selection']==0x8010,'P entry')
            require(r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal'],'actual BOOT colour')
            if profile=='test':require(s['boot_committed']==1 and r['first_menu']['screen']==0 and 'diagnostic_page' not in r,'Acros and first list')
            else:require(not s['boot_committed'] and r['diagnostic_page']['text'][0].startswith('G158B02'),'release off/B02')
            require(len(r['samples'])==1 and r['samples'][0]['name']=='Acros','one Acros')
            t=r['samples'][0];require(t['full_40_equal'] and t['unit_readback']['complete_552_equal'] and not t['state']['word']&12,'Acros record/colour')
            require(r['close_record_equal'] and r['after_close']['state']==5 and r['ADJ_closed']['state']==5,'DISP/OK/ADJ')
            return dict(mode=4,submode=0,N=0x8010,records=1,full_29=False)
        check('原生 P 档关键流程 '+profile+'/'+unit,critical,'新门 P 档，Acros 单记录、读回、DISP、OK/ADJ 关闭再开；全 29 条回归另列。')
for profile in C.PACKAGES:
    for unit in C.UNITS:
        def native(profile=profile,unit=unit):
            r=doc(out/'runs'/('sweep-'+profile+'-'+unit)/'result.json',sha[profile]);require(r['actual_backend']=='native' and r['cold_start'] and not r['snapshots'],'new MAIN')
            require(len(r.get('builtin_samples',[]))==8 and len(r['samples'])==18 and len(r.get('user_samples',[]))==3,'all29')
            for s in r['builtin_samples']+r['samples']+r['user_samples']:require(s['unit_readback']['complete_552_equal'] and s['full_40_equal'] and not s['state']['word']&12,'all colour/memory')
            require(r['close_record_equal'] and r['after_close']['state']==5 and r['ADJ_closed']['state']==5,'DISP/OK/ADJ')
            return dict(records=29,dial='AUTO',full_navigation=True)
        partial=read(out/'runs'/('sweep-'+profile+'-'+unit)/'result.json') or {}
        observed=len(partial.get('builtin_samples',[]))+len(partial.get('samples',[]))+len(partial.get('user_samples',[]))
        check('原生完整回归 '+profile+'/'+unit,native,'旧许可 AUTO；已逐条验过 '+str(observed)+'/29，整组还要求光标/DISP、OK/ADJ 关闭再开。PASM 新路径单列。')
for dial,sub,name in (('P',0,'Acros'),('A',1,'HC1'),('M',2,'LowSat'),('S',3,'Acros')):
    def boot(dial=dial,sub=sub):
        r=read(out/'runs'/('field-'+dial+'-native')/'result.json');require(r and r['dat_sha256']==sha['test'],'field result')
        # An ADJ peripheral fault does not invalidate the earlier independent
        # unit-row/T readback. It never counts as a completed whole-MAIN case.
        s=r['after_boot'];require(s['raw_mode']==4 and s['submode']==sub and s['native_selection']==(0x8010,0x8020,0x8008,0x8800)[sub],'measured triple')
        require(r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal'] and s['boot_committed']==1 and not s['word']&12,'full applied before ADJ')
        return dict(first_standby_colour=True,first_JPEG_generated=False,whole_run_status=r['status'])
    check('PASM 首次待机实际颜色 '+dial,boot,'快后端新 MAIN；在首次 ADJ 前读取实际九行/T。不是 JPEG 或实机照片。')
    def menu(dial=dial):
        r=doc(out/'runs'/('field-'+dial+'-native')/'result.json',sha['test']);s=r['first_menu'];require(s['screen']==0 and s['rows']==8 and 'diagnostic_page' not in r,'first ADJ directly list');return dict(direct_list=True)
    check('PASM 首次 ADJ 整机 '+dial,menu,'四个实测 N 组合；不替换未声明的单元请求。')
for key,reason in (('SCENE-domain',11),('MY-domain',12),('unknown-submode',11)):
    def negative(key=key,reason=reason):
        r=doc(out/'runs'/key/'result.json',sha['test']);require(r['unit_W']==0 and not r['after_boot']['boot_committed'],'rejected, zero W')
        require(r['diagnostic_page']['text'][0].startswith('G158B'+str(reason)),'B semantics');require(r['BOOT_unit_readback']['complete_552_equal'],'stock04')
        return dict(reason=reason,zero_W=True,pure04=True)
    check('拒绝域诊断 '+key,negative,'声明的 SCENE 非许可域、MY 和未知子模式反例；实际 SCENE/MY 内部编码尚未现场采样。')
for profile in C.PACKAGES:
    for kind in ('','-high'):
        key='reject-g157'+kind+'-'+profile
        def rejection(key=key,profile=profile):
            r=doc(out/'runs'/key/'result.json',sha[profile]);require(r.get('list_after_diagnostic',r['first_menu'])['memory_result']==3,'reject g157 binding');require(r['unit_W']==0,'old record causes no W');return dict(memory_result=3,zero_W=True)
        check('g157 记忆拒收 '+profile+kind,rejection,'当前 g157 r1 的 03 与官方 Acros 高索引记录；保持原生颜色。')
for backend in ('c','python'):
    def host(backend=backend):
        r=doc(C.receipt('host-'+backend+'.json'));require(r['cases']==108 and all(x['DAT_sha256']==sha[x['profile']] for x in r['rows']),'host data/memory');return dict(cases=108)
    check('主机 Look 记忆 '+backend,host,'108 个 Look 的实际指令构建/解码。')
    for profile in C.PACKAGES:
        def op5(profile=profile,backend=backend):
            r=doc(C.receipt('service-'+profile+'-'+backend+'.json'),sha[profile]);require(len(r['rows'])==54 and all(x['op5']==0 for x in r['rows']),'op5')
            require(any(x['case']=='g157-DAT-binding' and x['result']==3 for x in r['decoder']),'old g157 decode')
            return dict(op5=54,old_g157_rejected=True)
        check('实际 op5 '+profile+'/'+backend,op5,'真实服务权限/锁/IRQ；声明合法 part=1/task=0。不是 NAND 提交证明。')
for key,profile,kind in [('reference-test-AUTO','test','normal'),('reference-release-AUTO','release','normal'),('reference-P1-test-AUTO','test','fault'),('reference-P1-release-AUTO','release','fault')]:
    def reference(key=key,profile=profile,kind=kind):
        r=doc(out/'runs'/key/'result.json',sha[profile]);require(r['actual_backend']=='reference' and r['reference_oracle']=='legacy' and r['cold_start'] and not r['snapshots'],'independent MAIN')
        if kind=='fault':require(r['manual_safety_PASS'] and len(r['fault_events'])==1,'W8 once compensated')
        elif profile=='test':require(r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal'],'Acros BOOT')
        else:require(r['unit_W']==0 and not r['after_boot']['boot_committed'],'release off')
        return dict(dial='AUTO',scope=kind)
    check('参考整机 '+key,reference,'独立 Python 设备/指令，新 MAIN；旧许可 AUTO。PASM 参考另列。')
for dial,sub,selection in (('P',0,0x8010),('M',2,0x8008)):
    def pasm_reference(dial=dial,sub=sub,selection=selection):
        r=doc(out/('runs/reference-field-'+dial+'/result.json'),sha['test'])
        require(r['actual_backend']=='reference' and r['reference_oracle']=='legacy' and r['cold_start'] and not r['snapshots'],'independent cold MAIN')
        require(r['after_boot']['raw_mode']==4 and r['after_boot']['submode']==sub and r['after_boot']['native_selection']==selection,'measured entry')
        require(r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal'] and r['first_menu']['screen']==0,'BOOT and first ADJ')
        return dict(mode=4,submode=sub,N=selection)
    check('PASM MOUNT 参考关键路径 '+dial,pasm_reference,'独立 Python 设备/指令；实测 M/U/N，完整 BOOT 到首次 ADJ。')
def replay():
    r=doc(out/'persistence-r1-model/verification.json');require(r['cases']==48,'S48')
    for row in r['rows']:require(read(out/'runs'/row['label']/'result.json')['dat_sha256']==sha[row['target']],'S final SHA')
    return dict(cases=48,dial='AUTO')
check('S 块交叉重放 48 次',replay,'g157 完整关闭 S 源仅换 g158 记录绑定/记录 CRC，保留原 whole-S 校验，再建仅校验双组；实际 48 个新 g158 MAIN；AUTO。不是新 g158 GPIO 源会话。')
def audit():
    r=doc(out/'audit-summary.json');require(all(x['unexplained_bytes']==0 and x['semantic_changes']==['boot_fail_bits'] for x in r['audits']),'only gate semantics');return r['audits']
check('相对 g157 的全部字节审计',audit,'仅门逻辑、代数及其重定位/校验变化；配方全 552 B、body/resident 相同。')
ready=all(x['status']=='PASS' for x in checks);verdict='可以交复审' if ready else '有缺陷';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
replay_inputs=read(out/'persistence-r1-model/inputs.json') or []
replay_progress=[]
for row in replay_inputs:
    r=read(out/'runs'/row['label']/'result.json')
    replay_progress.append(dict(label=row['label'],status=r.get('status') if r else 'NOT_RUN',error=r.get('error') if r else None))
progress=dict(S48_completed=sum(r['status']=='OBSERVED' for r in replay_progress),S48_total=len(replay_inputs),S48=replay_progress)
partial_replay=read(out/'persistence-r1-model/verification-partial.json')
if partial_replay:progress['S48_partial_asserted']=partial_replay['cases']
receipt=dict(verdict=verdict,utc=now,final=a.final,DAT=sha,checks=checks,OPEN=[r['name'] for r in checks if r['status']!='PASS'],progress=progress,deadline='2026-11-05T05:00:24+00:00',no_camera_SD_network=True)
closeout=read(out/'queue-closeout.json')
if closeout:receipt['queue_closeout']=closeout
C.save(out/('FINAL.json' if a.final else 'STAGE.json'),receipt)
lines=[verdict,'','# g158 BOOT PASM 模式门','',
'现场 g157 test 的照片/记录证明：MOUNT 的 P/A/M/S 是模式 04、子模式 0/1/2/3，分别配 N=8010/8020/8008/8800。加载、手动 LowSat/Acros、R03/R5D 跨真实关机保留已由机主确认；绿色 AUTO 已自动套用 Acros并拍出黑白首张。这些是 g157 现场事实，g158 尚未实机验收。','',
'g158 保留原来的 mode=0/N8001 许可，仅增加四个实测 (mode,submode,N) 组合。新的 mode=4 分支要求 sub<4 并精确匹配 N 表，不把 P/A/M/S 都套进旧 N8001。MY、pending、activity、settings/state、原厂图像/WB、记录、锁和 epoch 等门没有放宽；B 码含义未改。release 仍关闭 BOOT。','',
'BOOT 与手动不是同一个高层事务：手动走 apply_impl/recover_confirmed，BOOT 在 eng_boot_run 内单独保存和恢复 S 计划。它们共享 deep 与行/T 读回，失败后完整写 04，失败仍保留护栏。两套 C 源码均与 g157 r1 完全相同；本轮只改模式门和代数。','',
'本轮截止 2026-11-05 05:00:24 UTC。最新回执 '+now+'。','',
'| 包 | SHA-256 | DAT B | 代码 B | 主请求 B | 预算余量 B |','| --- | --- | ---: | ---: | ---: | ---: |']
for profile,r in man.items():lines.append(f"| {profile} | `{sha[profile]}` | {r['dat_bytes']:,} | {r['code_bytes']:,} | {r['main_request']:,} | {r['main_headroom']:,} |")
lines+=['','实际链接：代码上限 69,632 B，主请求上限 107,612 B。test 代码只余 8 B；这是固定代码窗口，主请求预算余量也不是实机可用堆。配方、槽位、18 Looks、三个用户项及全部 552 B 数据与相应 g157 包完全一致，没有新增取舍。','',
'相对 g157 r1 的 test 2b890459、release 3ebc261c，两包各增加 84 B。打包文件差异位置分别为 82,381 和 80,110，均由门代码、158 代数、重定位和校验解释，未解释字节为 0。唯一行为变化函数是 boot_fail_bits；完整逐字节表和函数归一化证据只保存在被忽略的 `local/byte-audit-*.{json,tsv}`。','',
'## 验收','','| 项目 | 状态 | 范围 |','| --- | --- | --- |']
for r in checks:lines.append('| '+r['name']+' | '+r['status']+' | '+r['scope']+' |')
lines+=['','逐项断言见 `local/'+('FINAL.json' if a.final else 'STAGE.json')+'`。所有原始失败、驱动和命令在 `local/`；未完成或错误的整个 MAIN 不计作 PASS。'+('为在时限内封存，队列已于 '+closeout['finished_utc']+' 停止；未完成计划和终止信号见 `local/queue-closeout.json`。' if closeout else ''),
'','S 重放已有 '+str(progress['S48_completed'])+'/'+str(progress['S48_total'])+' 个新 MAIN 正常结束；只有完整 48 次矩阵断言通过才把该项计作 PASS。'+('其中 '+str(progress['S48_partial_asserted'])+' 次已通过逐行重放断言，见 `local/persistence-r1-model/verification-partial.json`。' if partial_replay else ''),'',
'test / 28mm 长扫为给新 P 档六组关键流程留出计算时间而主动 SIGINT，已验过的条目保留，全 29 条整组仍为 OPEN；该中止不能当作事务失败反例。记录见 `local/sweep-28mm-interruption.json`。','',
'## PASM 与 LCD 文本证据','','| 档位 | 实测入口 | BOOT 完整颜色 | 首次 ADJ |','| --- | --- | --- | --- |']
for dial,sub,selection in (('P',0,0x8010),('A',1,0x8020),('M',2,0x8008),('S',3,0x8800)):
    r=read(out/'runs'/('field-'+dial+'-native')/'result.json') or {}
    colour='PASS' if r.get('BOOT_expected_552_equal') and r.get('BOOT_unit_readback',{}).get('complete_552_equal') else 'OPEN'
    menu='PASS，直接列表' if r.get('status')=='OBSERVED' and r.get('first_menu',{}).get('screen')==0 else ('OPEN，HSP slot31 未声明响应' if 'HSP transmit requires a declared packet response' in r.get('error','') else 'OPEN，未完成；详见本地回执')
    lines.append('| '+dial+' | M04 U'+format(sub,'02X')+' N'+format(selection,'04X')+' | '+colour+' | '+menu.replace('|','/')+' |')
reference_m=read(out/'runs/reference-field-M/result.json') or {}
if reference_m:
    reference_colour=reference_m.get('dat_sha256')==sha['test'] and reference_m.get('BOOT_expected_552_equal') and reference_m.get('BOOT_unit_readback',{}).get('complete_552_equal')
    lines+=['','独立参考 M 档在首次 ADJ 前的完整颜色读回为 '+('PASS' if reference_colour else 'OPEN')+'；整个 MAIN 的结果为 '+reference_m.get('status','OPEN')+'。完整错误包保存在 `local/runs/reference-field-M/result.json`，该部分颜色结果不能代替首次 ADJ 通过。']
lines+=['',
'模拟器没有 LCD 像素输出。替代证据是 UI 实际发布的八行文本、每字符 ASCII 与实际 glyph 缓冲，不是像素截图。P/A 首次列表分别见 `local/runs/field-P-native/ui-first-adj.json`、`local/runs/field-A-native/ui-first-adj.json`；B11/B12 诊断见 `local/runs/unknown-submode/ui-first-adj.json`、`local/runs/MY-domain/ui-first-adj.json`。各文件含 row_descriptor、lcd_text_pointer、glyphs_hex 和逐字符映射。','',
'## 严格模拟器边界与 OPEN','',
'P/A 的快后端完整 BOOT 到首次 ADJ 已通过。M/S 在首次 ADJ 前已实际读回完整目标颜色，BOOT 提交且无护栏；随后原厂首次 ADJ 发出未声明的 HSP slot 31 请求，严格后端停止。这不是已证实的 g158 产品缺陷，也不能据此签署 M/S 首次 ADJ 或 JPEG 验收。未猜测成功回执、改 N 回 AUTO、改 resident 或绕过严格设备边界。参考结果以表内最终回执为准。','',
'机主补充确认：SCENE、MY1–3、动态影像没有现场 M/U/N/Y；绿色 AUTO 也未读出原始值，只能从已成功套用判断它落在旧许可内。这些档位的实际内部编码保留 OPEN，按现有模型继续拒绝。SCENE-domain 的 raw01 只是非许可域模型反例，不代表已采到真实 SCENE 编码；该反例保持04，但原厂 ADJ 未进入，不能声称显示了诊断页。[现场步骤](OWNER_STEPS.md)已加入逐档冷启动后由 Status 采集的可选项，页面是启动快照，列表经过配方可能改写记忆。','',
'AUTO 全流程与 PASM 门/颜色/指令探针分别列出。C 全写入矩阵不是逐例整机；实际 DAT 关键指令检查也不是 CPU/设备快照恢复。首次 ADJ 之前的颜色证据为真实 peer 九行/T，不是生成的 JPEG 或 LCD 像素截图。','',
'g157 已有 MOUNT 真实关机记忆证据，本轮没有改其持久化路径。g157 复审保留的 P2-03（关机后整表消失定责及装载失败诊断覆盖）和 P3-01（真实可用堆）继续 OPEN，见 [原复审](../review_g157_r1/REVIEW.md)。g158 的实机 PASM 首拍/ADJ、JPEG，以及 DAT 缺席或 resident 退役的配套诊断仍由后续工作验收；本轮没有操作相机或实际 SD、网络、依赖安装、commit 或 push。','',
'## 换代和降级','',
'g157 记录因 DAT 绑定变化被 g158 干净拒收。首次换入后可能见 B21/R3；需在 g158 手动成功保存一次目标配方，再正常关机重开检查新 BOOT 门。release 的策略原因仍为 B02。','',
'降级前先在当前 g158 保存纯 04，再替换旧 DAT。当前已是 04 时，先离开一行再回到 04，触发实际保存；核对 >4 Std、没有 Unsaved/ERR/护栏，正常关闭再开 ADJ 保持 04。此后不要经过其他配方再关机。','']
(C.HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
for profile,root in C.PACKAGES.items():
    raw=C.artifact(profile)['dat'].read_bytes();require(C.sha(raw)==sha[profile],'publish SHA')
    for target in (root/'local/GXRCE.DAT',root/'local/SD_ROOT/GXRCE.DAT'):target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    manifest=dict(man[profile],status=('READY_FOR_INDEPENDENT_REVIEW' if ready else 'ACCEPTANCE_OPEN') if a.final else 'ACCEPTANCE_IN_PROGRESS',verdict=verdict,acceptance_utc=now,software_OPEN=receipt['OPEN'],body_unchanged=True,resident_unchanged=True,recipe_data_unchanged=True,previous_DAT_sha256=read(out/'before'/profile/'MANIFEST')['dat_sha256'])
    C.save(root/'MANIFEST',manifest)
    (root/'SHA256SUMS').write_text(sha[profile]+'  local/SD_ROOT/GXRCE.DAT\n'+sha[profile]+'  local/GXRCE.DAT\n')
    (root/'README.md').write_text(f'''# g158 {profile}

{verdict}。须经新的独立复审后再上卡。机身 v3.10 a04f1ed4、resident 与配方数据沿用 g157 r1。

SHA-256：`{sha[profile]}`。DAT {manifest['dat_bytes']:,} B，代码 {manifest['code_bytes']:,} B，主请求 {manifest['main_request']:,}/107,612 B，预算余量 {manifest['main_headroom']:,} B。

仅扩展 BOOT：新增 mode 04 的 P0/A1/M2/S3，并分别匹配实测 N=8010/8020/8008/8800；旧 AUTO 许可保留，其他门未放宽。BOOT {'打开' if profile=='test' else '关闭'}；读回、诊断和 P1 护栏保留。代数 158 的 gate.c、eng_data.c、ui_v2_data.c 和 pack.py 已同步。

旧 g157 记忆会因 DAT 绑定变化被拒收，首次换包后需手动重新保存一次。降级前必须先在 g158 保存纯 04；若当前已是 04，先离开一行再回 04 触发实际保存，确认无 Unsaved/ERR/护栏，关闭再开 ADJ 仍是 04，再关机换包。

验收的模式、范围与 OPEN 见 [REPORT.md](../../research/g158/REPORT.md)，可选 Status 采集和降级步骤见 [OWNER_STEPS.md](../../research/g158/OWNER_STEPS.md)。AUTO 的完整回归不能代替 PASM 首次 ADJ；严格模拟器的未声明 HSP slot 31 边界保留原始证据，没有补造成功响应。实际 JPEG、LCD 像素及 g158 实机验收未宣称通过。
''')
print(json.dumps(dict(verdict=verdict,passed=sum(r['status']=='PASS' for r in checks),required=len(checks),OPEN=receipt['OPEN'],final=a.final)))
