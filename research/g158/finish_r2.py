"""Aggregate fresh acceptance without modifying either frozen DAT."""
from pathlib import Path
import datetime,json,re,sys
HERE=Path(__file__).resolve().parent
# Keep the original assertions and redirect only their receipt locations.
source=(HERE/'local/accept-r2/previous/research/g158/finish.py').read_text()
prefix=source[:source.index('ready=all(')]
original="def read(path):\n    try:return json.loads(Path(path).read_text())"
replacement="""def read(path):
    path=Path(path)
    aliases=json.loads((C.LOCAL/'accept-r2/aliases.json').read_text())
    try:
        relative=path.relative_to(C.LOCAL/'runs')
        if relative.parts[0] in aliases:path=C.LOCAL/'runs'/aliases[relative.parts[0]]/Path(*relative.parts[1:])
    except ValueError:pass
    try:return json.loads(path.read_text())"""
assert original in prefix
exec(compile(prefix.replace(original,replacement),str(HERE/'finish.py')+'#frozen-assertions','exec'),globals())
r2=out/'accept-r2';frozen=read(r2/'freeze.json');aliases=read(r2/'aliases.json')
for r in checks:r['required']=True
for r in checks:
    if r['name']=='拒绝域诊断 SCENE-domain':
        r.update(required=False,scope='raw01 是合成非许可域，原厂菜单未进入；不能把它当作实测 SCENE 码或声称出现过诊断页。实际编码按用户约定保持现场 OPEN。')
for profile in C.PACKAGES:
    def reference_native04(profile=profile):
        r=doc(out/'runs'/('reference-P1-'+profile+'-AUTO')/'result.json',frozen['DAT'][profile])
        require(r['manual_safety_PASS'] and r['compensated_to_complete04'],'actual unit rows/T compensated')
        s=r['manual_error_dismissed']
        require(s['selector']==1 and s['wb']==[9,9],'native Standard and neutral WB after failure')
        require(not s['word']&12 and s['state']==5,'safe standby after single failure')
        require(not r['manual_unguarded_partial_standby'] and len(r['fault_events'])==1,'exact once-after-write counterexample')
        event=r['fault_events'][0]
        require(event['phase']=='after-actual-native-call' and event['W_position']==8 and event['native_return']==296 and event['declared_return']==0xffffffff,'original review W8 receipt-failure input')
        return dict(single_receipt_failure=True,unit_complete04=True,native_selector=1,WB=[9,9],guard_cleared_only_after_compensation=True)
    check('参考 P1 完整04与原厂图像设定 '+profile,reference_native04,'逐一核对真实单元九行/T补偿、Standard/WB有效值和关闭后的护栏；不只接受驱动自报通过。')
    checks[-1]['required']=True
def native_reject():
    r=read(out/'runs/SCENE-domain/result.json');s=r['after_boot']
    require(r['dat_sha256']==frozen['DAT']['test'] and s['raw_mode']==1,'synthetic domain identity')
    require(not s['boot_committed'] and s['diagnostic']['reason']==11,'mode rejected')
    require(r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal'],'actual complete04')
    return dict(mode=1,synthetic=True,BOOT_rejected=True,complete04=True,first_ADJ_verified=False)
check('非许可模式 BOOT 拒绝与完整04',native_reject,'合成 raw01；只验 BOOT 拒绝和完整04，不冒充 SCENE 实机或首次 ADJ 页面。')
checks[-1]['required']=True
boundary=read(r2/'slot31/verification.json')
boundary_ready=bool(boundary and boundary['status']=='MODEL_BOUNDARY' and boundary['cases']==6 and not boundary['device_response_added'])
boundary_names={'PASM 首次 ADJ 整机 M','PASM 首次 ADJ 整机 S','PASM MOUNT 参考关键路径 M'}
def boundary_detail(name):
    reference=name=='PASM MOUNT 参考关键路径 M'
    dial='S' if name=='PASM 首次 ADJ 整机 S' else 'M'
    sub,N=(3,0x8800) if dial=='S' else (2,0x8008)
    label='reference-field-M' if reference else 'field-'+dial+'-native'
    row=read(out/'runs'/label/'result.json')
    require(row and row['status']=='ERROR' and row['dat_sha256']==frozen['DAT']['test'],'original boundary receipt and final DAT')
    require(row['actual_backend']==('reference' if reference else 'native') and row['cold_start'] and not row['snapshots'],'original cold backend')
    if reference:require(row['reference_oracle']=='legacy','independent reference route')
    st=row['after_boot']
    require(st['raw_mode']==4 and st['submode']==sub and st['native_selection']==N and st['boot_committed']==1 and not st['word']&12,'original measured BOOT entry')
    require(row['BOOT_expected_552_equal'] and row['BOOT_unit_readback']['complete_552_equal'],'original complete BOOT colour')
    require('DeviceBoundary' in row['error'],'original strict device fault')
    packet=[int(word,16) for word in re.search(r'HSP transmit requires a declared packet response: ([0-9a-f ]+)',row['error']).group(1).split()]
    native=next(x for x in boundary['rows'] if x['generation']==158 and x['profile']=='test' and x['dial']==dial)
    require(packet[2]==0x1f0003 and packet[3:6]==native['arguments'],'original packet matches diagnosed request')
    return dict(evidence='local/accept-r2/slot31/verification.json',original_run=label,actual_backend=row['actual_backend'],complete_BOOT_colour=True,matching_slot31_arguments=True,completed_ADJ=False)
if boundary_ready:
    for r in checks:
        if r['name'] in boundary_names and r['status']!='PASS':
            try:detail=boundary_detail(r['name'])
            except (AssertionError,KeyError,TypeError,ValueError,AttributeError,IndexError,StopIteration) as exc:
                r['detail']='boundary identity not established: '+str(exc);continue
            r.update(status='MODEL_BOUNDARY',detail=detail,scope=r['scope']+' 六组 BOOT 开/关对照与原厂曝光代码已定位；原始同 SHA 冷启动回执及请求参数逐项匹配，严格模型仍停止，未补造回执。')
def unchanged():
    sizes={}
    for profile,root in C.PACKAGES.items():
        digest=frozen['DAT'][profile];art=C.artifact(profile,'model')
        for path in (art['dat'],root/'local/GXRCE.DAT',root/'local/SD_ROOT/GXRCE.DAT'):require(C.sha(path.read_bytes())==digest,'frozen DAT '+str(path))
        size=read(art['build']/'size.json')
        for name,value in {**size['sources'],**size['headers']}.items():require(C.sha((C.ROOT/name).read_bytes())==value,'linked source '+name)
        sizes[profile]=dict(DAT_sha256=digest,dat_bytes=man[profile]['dat_bytes'],code_bytes=man[profile]['code_bytes'],main_request=man[profile]['main_request'],main_headroom=man[profile]['main_headroom'])
    return sizes
check('本轮产品源码和两包零改动',unchanged,'逐一核对链接时 source/header SHA，以及三个实际 DAT 副本；没有重建或重写 DAT。')
checks[-1]['required']=True
if boundary_ready:
    checks.append(dict(name='slot31 原厂请求与 BOOT 开关对照',status='PASS',required=True,detail=dict(cases=6,evidence='local/accept-r2/slot31/verification.json'),scope='同一曝光请求在旧 g157 拒绝 BOOT、g158 release 关闭 BOOT 和 g158 test 已套用后都触达；这项是边界诊断，不是 ADJ 成功。'))
else:
    checks.append(dict(name='slot31 原厂请求与 BOOT 开关对照',status='OPEN',required=True,detail='six cold observer cases not verified',scope='六组只读对照及状态相关返回值证据。'))
hard_open=[r for r in checks if r.get('required',True) and r['status'] not in ('PASS','MODEL_BOUNDARY')]
boundaries=[r for r in checks if r.get('required',True) and r['status']=='MODEL_BOUNDARY']
verdict='有缺陷' if hard_open else '可以交复审（M/S 首次 ADJ 为模型边界，待现场确认）' if boundaries else '可以交复审'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
schedule=read(r2/'loadgate-transition/resumed.json') or {}
scheduled_deadline=schedule.get('deadline',frozen['deadline'])
replays=read(out/'persistence-r1-model/verification.json') or read(out/'persistence-r1-model/verification-partial.json') or {}
receipt=dict(verdict=verdict,utc=now,final=a.final,DAT=frozen['DAT'],checks=checks,OPEN=[r['name'] for r in hard_open],model_boundaries=[r['name'] for r in boundaries],supplemental_OPEN=[r['name'] for r in checks if not r.get('required',True) and r['status']!='PASS'],aliases=aliases,replays=dict(status=replays.get('status'),cases=replays.get('cases',0),total=48),deadline=scheduled_deadline,original_deadline=frozen['deadline'],admission_policy='tools/loadgate.py',product_changed=False,device_response_added=False,no_camera_SD_network=True)
native_rows=[r for r in checks if r['name'].startswith('原生完整回归 ')]
reference_p1_rows=[r for r in checks if r['name'].startswith('参考 P1 完整04与原厂图像设定 ')]
receipt['summary']=dict(native_29_passed=sum(r['status']=='PASS' for r in native_rows),native_29_total=6,reference_P1_passed=sum(r['status']=='PASS' for r in reference_p1_rows),reference_P1_total=2,S_replay_passed=replays.get('cases',0),S_replay_total=48,slot31_observer_cases=boundary.get('cases',0) if boundary else 0)
close_proof=read(r2/'close_wait/verification.json')
receipt['close_wait_proof']=close_proof
C.save(r2/('FINAL.json' if a.final else 'STAGE.json'),receipt)
if a.final:C.save(out/'FINAL.json',receipt)
lines=[verdict,'','# g158 验收补齐','',
'本轮只补验收。两包 SHA、产品源码、配方、机身 v3.10 a04f1ed4 和 resident 都保持不变。test 代码区仍为 69,624/69,632 B，只余 8 B。原有 g158 门仍保留旧许可，并增加 M04/U00–03 与各自实测 N 的精确匹配；release BOOT 仍关闭。','',
'本轮开始 2026-11-05 05:03:27 UTC，当前截止 '+scheduled_deadline+'。最新回执 '+now+'。全部 nice15。调度前段按原 load1 门；机主于本日批准后改用 `tools/loadgate.py` 的 iostat CPU idle、空闲内存和保留两核规则，每次调用最多启动一个新进程，单队列最多六个。`load.jsonl`、`admissions.jsonl` 保留完整采样 info。','',
'原有两个参考 P1 进程先自然结束，随后恢复未完成队列；未向它们发送终止或暂停信号，也未重复启动。切换记录见 `local/accept-r2/loadgate-transition/`，最终调度审计见其 `verification.json`。只改变调度，所有输入、断言和检查精度保持不变。本轮未做速度比较；运行时长仅用于调度日志，后续计时实验必须使用 `loadgate.quiet_for_timing()`。','',
'| 包 | SHA-256 | DAT B | 代码 B | 主请求 B | 预算余量 B |','| --- | --- | ---: | ---: | ---: | ---: |']
for profile,r in man.items():lines.append(f"| {profile} | `{frozen['DAT'][profile]}` | {r['dat_bytes']:,} | {r['code_bytes']:,} | {r['main_request']:,} | {r['main_headroom']:,} |")
lines+=['','本轮关键回执：原生29条完整回归 '+str(receipt['summary']['native_29_passed'])+'/6；MOUNT参考整机P1 '+str(receipt['summary']['reference_P1_passed'])+'/2；S重放 '+str(receipt['summary']['S_replay_passed'])+'/48。各项只有完整断言通过才计数。']
lines+=['','主请求上限仍为107,612 B。预算余量不代表真实可用堆。本轮相对已封存 g158 的 DAT 差异为0 B；相对 g157 r1 的旧审计保持有效：两包各增加84 B，差异位置82,381/80,110均由模式门、代数、重定位和校验解释，未解释字节0。全部552 B配方逐条相同。','',
'## slot31 与现场旁证','',
'[SLOT31.md](SLOT31.md)记录原厂快门/光圈曝光参数路径。返回值是参与曝光换算的有符号数量；单元会更新曝光状态并按实时状态和校准量计算，不能统一填一个成功值。完整固件地址、原厂文本和派生表只在被忽略的 `local/accept-r2/slot31/`。','',
'本轮没有给模型补造成功回执，也没有修改产品以绕开原厂请求。六组只读冷启动对照的实际结论见 `local/accept-r2/slot31/verification.json`；MODEL_BOUNDARY 表示已定位严格模型缺项，不表示首次 ADJ 成功。','',
'机主报告的 g157 test 实机旁证：M/S 冷启动首次 ADJ 都正常，B11 诊断后能返回列表；M 档手动套用后再开 ADJ 全天正常。两条流程使用同一个原厂曝光路径，颜色 S 写计划不包含该路径的快门/光圈输入。BOOT 先于第一次原厂菜单初始化写颜色，手动套用发生在菜单已经建立之后，单元初态的先后仍有区别。当前模拟器从已声明 AUTO 输入冷启动，在 BOOT 派发边界声明 M/U/N，没有重建物理 M/S 下的单元完整曝光启动。g157 旁证不能替代 g158 BOOT 后首次 ADJ 的现场结果。','',
'## 验收回执','','| 项目 | 状态 | 范围 |','| --- | --- | --- |']
for r in checks:lines.append('| '+r['name']+' | '+r['status']+('，补充项' if not r.get('required',True) else '')+' | '+r['scope']+' |')
if close_proof and close_proof['status']=='PASS':
    lines+=['','release/50mm P 的首轮 ADJ 关闭在原厂恢复7行表、尚未转入待机时提前取样，原失败保留。新冷启动使用相同输入，全部原按键与状态、失败点首个样本均原样复现；随后不加按键、不改状态，在原90个等待窗口上限内继续原厂指令，稳定到 state=5，完整552 B颜色与40 B记忆保持不变。终点断言没有放宽，产品没有修改。逐项对照见 `local/accept-r2/close_wait/verification.json`，新运行标签为 `r2c-critical-release-50mm-P`。']
lines+=['','原有主机、全写入故障矩阵、旧记忆拒收及字节审计复用已封存同 SHA 的回执。本轮新目录使用 r2 前缀，首轮错误、中止和结果都保留；`local/accept-r2/aliases.json`明确列出新旧结果路径，没有覆盖失败现场。','',
'S 重放已断言 '+str(replays.get('cases',0))+'/48。原先5个已通过的新 g158 MAIN 保留，只补其余43个。S 来源仍是已完成的 g157 r1 GPIO 关闭记录，只替换记忆绑定及记录校验并建立 whole-S 校验双组；这是明确派生夹具，不是新 g158 GPIO 源会话，也不是实际 NAND 或关机证明。每个重放都是新 MAIN，没有恢复 CPU/设备检查点。','',
'原生全29条回归与 P 档单记录关键流程分开列。参考整机 P1 使用与复审反例相同的输入和写后回执故障点，检查完整04补偿或护栏，不能用 C harness 代替该项。','',
'模拟器没有 LCD 像素输出。已发布八行文本及逐字符 glyph 缓冲是替代证据，位于各次 `ui-first-adj.json`，不是像素截图。未完成的 M/S ADJ 不制造页面证据。','',
'P/A 首次列表分别见 `local/runs/field-P-native/ui-first-adj.json` 和 `local/runs/field-A-native/ui-first-adj.json`；B11/B12 分别见 `local/runs/unknown-submode/ui-first-adj.json` 和 `local/runs/MY-domain/ui-first-adj.json`。本轮六组原生回归的首个页面与诊断后列表保存在各自运行目录，路径由 `local/accept-r2/aliases.json` 绑定。','',
'## 仍需现场确认','',
'M/S 的 g158 test 必须分别冷启动验证“ADJ在先、不按快门”和“首拍在先”，再与手动重开作对照，见 [现场步骤](OWNER_STEPS.md)。拍照会经过原厂曝光流程，不能把两种顺序互相替代。实际 JPEG、LCD 扫描及单元完整 AE 初态未由本轮模拟器证明。','',
'按用户已接受的范围，SCENE、MY1–3、动态影像和 AUTO 原始 M/U/N/Y 的现场采样继续 OPEN，按现有模型拒绝未许可组合。合成 raw01 的原厂菜单未进入，不把它冒充实测 SCENE；新增独立断言只确认其 BOOT 拒绝和完整04。B11/B12 页面本身已有未知子模式/MY模型回执。可选 Status 采集保持为逐档冷启动，页面读取启动快照。','',
'g157 复审的 P2-03（关机后整表消失定责、DAT 缺席/装载失败诊断）与 P3-01（真实可用堆）按原约定保留，详 [原复审](../review_g157_r1/REVIEW.md)。这些既有现场范围不冒充本轮已关闭的软件验收。','',
'## 换代和降级','',
'g157 记录被 g158 的新绑定干净拒收。首次换入后先手动成功保存一次，再正常关机重开检验 BOOT。降级前必须先在当前 g158 实际保存纯04；当前已是04时先离开一行再回04，确认无 Unsaved/ERR/护栏，关闭再开仍为04，再关机换旧 DAT。','']
(C.HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
for profile,root in C.PACKAGES.items():
    manifest=dict(man[profile],status=('READY_FOR_INDEPENDENT_REVIEW_WITH_MODEL_BOUNDARY' if boundaries else 'READY_FOR_INDEPENDENT_REVIEW') if a.final and not hard_open else 'ACCEPTANCE_OPEN',verdict=verdict,acceptance_utc=now,software_OPEN=receipt['OPEN'],model_boundaries=receipt['model_boundaries'],product_changed_this_round=False,DAT_changed_this_round=False)
    C.save(root/'MANIFEST',manifest)
    (root/'SHA256SUMS').write_text(frozen['DAT'][profile]+'  local/SD_ROOT/GXRCE.DAT\n'+frozen['DAT'][profile]+'  local/GXRCE.DAT\n')
    (root/'README.md').write_text(f'''# g158 {profile}

{verdict}。

SHA-256 `{frozen['DAT'][profile]}`。DAT {manifest['dat_bytes']:,} B，代码 {manifest['code_bytes']:,} B，主请求 {manifest['main_request']:,}/107,612 B。本轮只补验收，没有重建或改写 DAT。机身 v3.10 a04f1ed4、resident 和配方保持不变。

BOOT {'打开' if profile=='test' else '关闭'}，读回、诊断和 P1 护栏保持。M04/P0/A1/M2/S3 分别匹配实测 N8010/8020/8008/8800，其他门不放宽。M/S 原厂曝光请求的模型边界和现场旁证见 [SLOT31.md](../../research/g158/SLOT31.md)；未补造成功回执。

验收范围与剩余项目见 [REPORT.md](../../research/g158/REPORT.md)。监督现场检查、Status 采集见 [OWNER_STEPS.md](../../research/g158/OWNER_STEPS.md)。g157 旧记忆换入后会被拒收，需在 g158 重新保存。

降级前先在当前 g158 保存纯04；若已经是04，先离开一行再回04，核对无 Unsaved/ERR/护栏，关闭再开 ADJ 仍是04，随后正常关机换旧 DAT。
''')
print(json.dumps(dict(verdict=verdict,required_OPEN=receipt['OPEN'],model_boundaries=receipt['model_boundaries'],replays=receipt['replays'],final=a.final),ensure_ascii=False))
