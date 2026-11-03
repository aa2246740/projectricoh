#!/usr/bin/python3
"""Summarize only records bound to the delivered DAT."""
from pathlib import Path
import collections,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'research/g127_fix'
RUNS=WORK/'local/release127'
pkg=json.loads((WORK/'evidence/package.json').read_text());PIN=pkg['dat_sha256']
commands=[]
for p in (WORK/'evidence').glob('*commands.jsonl'):
 for line in p.read_text().splitlines():
  try:x=json.loads(line)
  except ValueError:continue
  if x.get('dat_sha256')==PIN:commands.append(x)
(WORK/'commands.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in commands))
primary={}
for unit in ('50mm','28mm','mount'):
 base=RUNS/'review_g126'
 own=json.loads((base/'evidence'/('ownership-settings-127-'+unit+'.json')).read_text())
 opened=json.loads((base/'evidence'/('ownership-reopen-127-'+unit+'.json')).read_text())
 assert own['dat_sha256']==PIN and opened['dat_sha256']==PIN
 assert not own['stores_after_switch'] and not own['services_after_switch']
 assert opened['status']=='PASS' and opened['pending_before']==1 and opened['pending_after']==0
 cold=[]
 for p in (base/'local/cold-reentry').glob('127-'+unit+'-*.json'):
  x=json.loads(p.read_text())
  if x.get('dat_sha256')==PIN:
   cold.append({'file':str(p.relative_to(ROOT)),'status':x.get('status'),'published':x.get('published_plan',{}).get('matches'),'exit':x.get('exit_plan',{}).get('matches')})
 assert len(cold)==4 and all(x['status']=='PASS' and x['published'] and x['exit'] for x in cold)
 primary[unit]={'settings_writes_after_loss':0,'preview_requests_after_loss':0,'reopen':'PASS','cold_reentry':cold}
case_counts={}
for family in (122,123,124,126):
 result={}
 for unit in ('50mm','28mm','mount'):
  count=collections.Counter()
  for p in (RUNS/f'review_g{family}/local/cases').glob('*-'+unit+'-*.json'):
   try:x=json.loads(p.read_text())
   except ValueError:continue
   identity=x.get('dat_sha256') or x.get('artifact',{}).get('dat_sha256')
   if identity==PIN:count[x.get('status','unknown')]+=1
  result[unit]=dict(count)
 case_counts[str(family)]=result
common=('safety','locked','nested','cutpoints','exits','transitions','values','view-reentry','reentry-six','users','project','labels','half')
groups=[]
for family in (124,126):
 for unit in ('50mm','28mm','mount'):
  for part in common+(('other-users',) if family==126 else ()):
   name=f'group{family}-{unit}-{part}'
   rows=[x for x in commands if x['name']==name]
   complete=any(x['returncode']==0 for x in rows)
   if part=='users':complete|=any(x['name']==f'users{family}-{unit}-user_acceptance' and x['returncode']==0 for x in commands)
   if part=='other-users':complete|=any(x['name']==f'users{family}-{unit}-other_users' and x['returncode']==0 for x in commands)
   groups.append({'family':family,'unit':unit,'group':part,'complete':bool(complete),'returncodes':[x['returncode'] for x in rows]})
summary={'status':'INCOMPLETE','generation':127,'dat_sha256':PIN,'primary':primary,'case_counts':case_counts,'groups':groups,
         'command_returncodes':dict(collections.Counter(str(x['returncode']) for x in commands)),
         'groups_complete':sum(x['complete'] for x in groups),'groups_required':len(groups),
         'history122_expectations':'原脚本的 121 基线期望分支；模型加载最终 gen 127 DAT；保留 OBSERVED 标记。',
         'regression_crc':'常规回归使用现有 CRC 主机叶函数；关键归属及 cold_reentry 保留原生 CRC。'}
(WORK/'evidence/acceptance.json').write_text(json.dumps(summary,indent=2)+'\n')
for name in ('compiled-tables.json','binary-inventory.json'):
 shutil.copy2(RUNS/'review_g126/evidence'/name,WORK/'evidence'/name)
code=json.loads((WORK/'evidence/codegen-four-categories.json').read_text())
code['primary_runtime_verified']=True
code['status']='SCOPED_CATEGORIES_CLOSED_FULL_REGRESSION_INCOMPLETE'
(WORK/'evidence/codegen-four-categories.json').write_text(json.dumps(code,indent=2)+'\n')
rows=[]
for family in (124,126):
 for unit in ('50mm','28mm','mount'):
  items=[x for x in groups if x['family']==family and x['unit']==unit]
  rows.append(f"| gen {family} / {unit} | {sum(x['complete'] for x in items)}/{len(items)} 组闭合 | 未完成 |")
report=f'''有缺陷

已产出 gen 127，指定的迟到设置写入切点已修复，三个单元的关键路径均通过。1.5 小时时间盒内，全量回归没有闭合，不能写成“可以交复审”。这项结论包含验收缺口，不把超时直接判成真机故障。

最终 DAT 为 {pkg['file_bytes']:,} B，generation 127，SHA256 `{PIN}`。源码在 `firmware/engine_v48_own`，30 文件包在 `firmware/package_v36_g127`。29 个固定文件与 gen 120b 逐字一致；有效配方行与 gen 126 逐字一致。包内实际字节均在 `local/SD_ROOT`，`SD_ROOT` 是相对链接。

## 修复与范围

`eng_settings_owned()` 复用列表的 `rv_view_owned()`，核对 activity=8、state=56、当前 view token、当前会话租约、发布列表、快照及原生视图。H01 使用列表构造阶段的原有规则，H07 使用已发布视图规则。

`eng_check_settings()` 在失去归属时只设置私有 `settings_pending` 标记。`apply_impl()` 保留原九行及 T 恢复，将未归属时的设置及预览尾部延后，不再因此触发补偿重试或永久锁定。待核对期间不发布 grain。下一次 H01 发布后按现有计划恢复；即使设置已经匹配，标记也会补做被延后的预览。

settings op 2 的最终写入在原 IRQ 保护区内再次核对请求的 view epoch 和原生归属。preview op 1 在原生预览入口前再次核对。RPC 类型、S 偏移、映射、通信实现、存储实现及锁定条件未改。`validate_live`、`list_bind_impl`、`ig_event` 和其他保留函数的源码逐字一致。延后恢复会再次进入现有核对路径；全量调用数和全部错误路径仍缺验收，不能宣称行为已经全部等价。

源码差异见 [source-change-vs-g126.patch](source-change-vs-g126.patch)。实际改动九个 C 函数，其中三处只更新 generation；头文件增加两个声明，私有状态增加一个标记。构建工具只同步本代路径和 generation，GXUI124 格式标识保留。

## 已通过的最终 DAT 验证

| 验证 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| 失去归属后的设置写入 | 0 | 0 | 0 |
| 失去归属后的预览请求 | 0 | 0 | 0 |
| 同一模型下一次打开 | PASS | PASS | PASS |
| 待核对标记 | 1 清为 0 | 1 清为 0 | 1 清为 0 |
| 下一次打开设置 | mode=1，WB=9/9 | mode=1，WB=9/9 | mode=1，WB=9/9 |
| cold_reentry 发布及确认退出 | 4/4 PASS | 4/4 PASS | 4/4 PASS |

以上记录全部绑定本报告的最终 SHA。原生切菜单及按键仍由固定机身指令执行，Image getter 没有假返回。详见 [acceptance.json](evidence/acceptance.json) 和 `local/release127/review_g126/`。

## 未闭合的回归

独立组共 {len(groups)} 组，目前 {summary['groups_complete']} 组完成。实际命令、返回码和逐组缺口见 [commands.jsonl](commands.jsonl) 及 [acceptance.json](evidence/acceptance.json)。六个整套回归达到超时，另有独立组及用户条目未完成；不以启动过命令代替通过。

| 原套件与单元 | 独立组结果 | 整套结果 |
| --- | --- | --- |
'''+'\n'.join(rows)+'''

历次反例仍按原路径调用。gen 122 原脚本使用 121 的正确结果期望分支，模型实际加载最终 gen 127；其记录保留 OBSERVED，不改写成 PASS。gen 123 原套件未在时间盒内全部完成。逐单元记录数、状态和实际返回码保留在 acceptance.json。部分早期组因缺少用户工具前置结果失败；前置结果随后已生成，但相应重跑仍未全部完成。

常规回归使用模型已有的 CRC 主机叶函数，归属切点、同一模型重开和 cold_reentry 使用原生 CRC。旧脚本未复制到新测试文件。包装入口在运行时重绑代号、DAT SHA、路径及旧代模型接口；不关闭断言，不伪造设置读取。

## 编译码与通信

最终 DAT 内引擎与 ELF `.engine` 逐字一致。九个改动 C 函数均绑定最终编译跨度，地址与长度、文件操作、原生界面写入、循环与内存四类检查见 [codegen-four-categories.json](evidence/codegen-four-categories.json)。新增归属分支没有循环或分配；既有计划 16 项、九行及 4+2 次补偿界限保持不变。

引擎 47,236 B，BSS 8,848 B，DAT+BSS 67,620 B。最大单函数静态帧 260 B；这不代表调用链或 RTOS 总栈没有变化。五个跳表、45 个目标已核对，未分类可执行异常为零，PIC 平移检查通过。额外编译变化包括清零函数的合并及表基址平移，见 [binary-inventory.json](evidence/binary-inventory.json) 和 [compiled-tables.json](evidence/compiled-tables.json)。

通信使用未修改的 `research/g122_keep_list/audit_records.py`，不传哨兵选项。只将含 cmd、value、page、result 的完整记录送审，按 DAT SHA 区分，结果见 [rpc-summary.json](evidence/rpc-summary.json)。它只证明所送完整流的地址、长度及边缘保留，不补足未完成的回归。

## 保留窗口

S 写入使用与列表服务相同的 IRQ 边界。preview 的最后一次归属判断返回后，到 `rv_native_preview` 真正进入之间仍有指令和调度窗口；本轮没有把它当作原子操作，也没有复现这个最末端的预览切点。

它与 P2-01 末端重绘窗口同属“检查后、动作前”的窗口，但这里的动作是预览入口，不能描述成只改像素。P2-01 原生重绘仍可能写全局 `0x205d4f64`，本轮没有修改该路径。普通 preview 服务失败后是否重开补刷，仍沿用原错误路径；新标记针对归属丢失，不把这项继承限制算作已修复。

## 输入与证据边界

初始冻结 527,663 项。复核发现任务范围外的旧复审日志和模拟器研究文件发生变化，详情见 [protected-inputs.json](evidence/protected-inputs.json)。构建与验证由仅允许三个交付目录写入、禁止网络的系统围栏执行；未回写这些旧路径。构建源、工具及最终产物绑定另由 source-and-binary.json 和构建记录核对。依赖记录保留在各运行目录，不能把全仓库监测变化写成零。

本报告证明源码、编译、打包和所列 M32R 主机重放结果。没有访问相机、存储卡或网络，没有启动子代理。原生预览图形叶函数由模型承接，没有验实体 LCD、拍摄完成、真实调度或实体断电。
'''
(WORK/'REPORT.md').write_text(report)
(ROOT/'firmware/engine_v48_own/STATUS.txt').write_text('gen 127 ownership fix\nDAT SHA256 '+PIN+'\n关键归属和 cold_reentry 通过；全量回归未闭合。详见 research/g127_fix/REPORT.md。\n')
(ROOT/'firmware/package_v36_g127/DELIVERY.md').write_text('gen 127 复审候选\n\nDAT SHA256 `'+PIN+'`。30 个文件，29 个固定文件与 gen 120b 相同。实际字节在 local/SD_ROOT。全量回归未闭合，不代表设备验收。\n')
print(json.dumps({'primary':'PASS','groups_complete':summary['groups_complete'],'groups_required':len(groups),'status':'INCOMPLETE','dat_sha256':PIN}))
