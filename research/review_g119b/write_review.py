"""Write the Chinese review only after the explicit collection gates complete."""
from pathlib import Path
from datetime import datetime,timezone
import collections
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,START_UTC,DEADLINE_UTC,save

def read(name):return json.loads((OUT/name).read_text())
a=read('acceptance.json');identity=read('identity.json');cg=read('codegen-closure.json')
branches=read('branch-dispositions.json');latency=read('latency.json')
integrity=read('input-integrity.json');runtime=read('runtime-input-integrity.json')
assert a['status']=='REVIEW_COMPLETE_WITH_FINDINGS' and integrity['ok'] and runtime['ok']
assert cg['open_functions']==['rv_call']
assert all(r['late_writes']==(8 if r['entry']=='fn2' else 9) for r in a['other_entry_menu_changes'])
open_rows=[r for r in branches['outcomes'] if r['kind']=='OPEN']
assert all(r['function']=='rv_call' for r in open_rows)
save('open-rv-call.json',dict(function='rv_call',status='OPEN',outcomes=open_rows,
    evidence=['A-first-attempts.json','rv_call-results.json','service-targets.json','service-more.json','file-gate-cfg.json'],
    conclusion='具体函数的剩余改码尚未达到题定 A/B/C 标准；没有据此声称已经证明编译器生成了错误行为。'))
new=identity['119'];finish=datetime.now(timezone.utc).isoformat()
line=[]
def add(s=''):line.append(s)
add('不可以上卡。')
add()
add('两个确定的验收失败仍在：并发切换时，Fn2 和 H07 会改写原生其他菜单；首次 W 前持续通信失败时，下次开页没有错误提示。编译改码另有一个具体函数 `rv_call` 尚未闭合。H08 的指定切换点、正常预览、退出接受和短暂故障补偿已通过三单元回归。')
add()
add('1. 范围与证据')
add()
add(f'本轮从 {START_UTC} 开始，三小时截止为 {DEADLINE_UTC}；报告生成于 {finish}。只写 `research/review_g119b/`，未编译、链接或打包固件，未操作相机或存储卡，未启动子代理。所有 Python 均使用 `/usr/bin/python3 -I -B`。DAT、ELF 和重定位字节文件是既有输入的证据副本或分析结果。')
add()
add('执行的是最终 DAT、v3.6 resident 及原生菜单的 M32R 指令。单元通信、文件系统、字体资源、绘制提交和部分系统边界仍由模型提供。正常长矩阵使用既有 CRC-32 等价计算边界；持续失败和合并补例执行实际 CRC 位循环。原生 getter、事件、setter 和预览事务均执行原指令，通信计数不受 CRC 计算方式影响。并发切换使用与作者相同的第二 CPU 上下文及独立栈、共享 RAM；没有手工设置正常菜单光标、活动项或 resident 状态。真实 RTOS 是否允许所有这些交错、实体 LCD 和实际掉电均未测。')
add()
add('| 对象 | 本轮核实值 |')
add('| --- | --- |')
for title,value in (
 ('gen 119 DAT',new['dat']+'；58,908 B'),('gen 119 ELF',new['elf']),
 ('卡包 ilaunch3','50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'),
 ('resident build id',new['resident_id']),('ABI',new['abi']),
 ('官方 ZIP','3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898'),
 ('ZIP 内原版 ilaunch3','da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7')):
    add('| '+title+' | `'+value+'` |')
add()
add(f'作者清单 7,650/7,650、卡包清单 30/30 均重新核验。28 个官方伴随文件等于官方 ZIP，除 DAT 外另 29 个卡包文件与基线相同。48 份配方、records、metadata 及三份 map、pin 与 gen 117/118 相同。engine 为 {new["engine_bytes"]:,} B，BSS 为 {new["bss"]:,} B；DAT 距 65,536 B 限制余 6,628 B。[身份](identity.json)、[卡包](package.json)、[数据](data-equality.json)、[源码范围](source-scope.json)。')
add()
add(f'任务输入 {integrity["files"]:,} 项和运行依赖 {runtime["files"]} 项前后核对均未变。历史未完成审查仅用作脚本阅读参考，其结果没有计入本轮结论。本轮早期脚本前提失败和中断诊断保留在 `partial-runs/` 与 `commands/`，原生结论只使用 `acceptance.json` 绑定的最终记录；未到达通信点的 117 ADJ 对照明确记为不适用，不计作并发反例或通过。应用户要求，本目录统一使用中性质检用语；历史路径和命令以十六进制编码保留。[输入核对](input-integrity.json)、[运行依赖](runtime-input-integrity.json)、[词语调整记录](neutral-terms-normalization.json)、[脚本来源](harness-provenance.json)。')
add()
add('2. P1-01：并发保护只覆盖 H08，Fn2 与 H07 仍会改变原生其他菜单')
add()
add('在冷开 04 模型中经原生代码进入 Fn2，在第一次 RPC 边界执行官方 item-7 arm `0x202BA380→0x202BA3C8` 和另一列表构造器 `0x20285E00`。该菜单形成后 activity=7、overlay=21。外层调用继续，`ui_finish(RV_FAULT)` 导致 resident 退役并执行 `rv_ui_abort`，随后出现以下真实机器写入。')
add()
add('| 地址 | 写入 PC | 影响 |')
add('| --- | --- | --- |')
for address,pc,impact in (
 ('0x2022F5A8','0x20053DB0','恢复旧 Image 列表指针'),('0x2022F5AC','0x20053DC0','把行数改成 7'),
 ('0x2022F725','0x20053DD4','写选中标记'),('0x2022F726','0x20053DE4','写高亮行'),
 ('0x205A2811','0x201C0BEC','写原生撤页状态'),('0x205A280E','0x201C0CD4','清原生页面状态'),('0x205A280F','0x201C0CE0','清原生菜单类型'),
 ('0x2037F3BC','0x20052A88','把 overlay 从 21 清成 0')):
    add('| `'+address+'` | `'+pc+'` | '+impact+' |')
add()
add('扩大到七段 UI 内存后，三个单元的 Fn2 均复现 8 次迟到写入，root 最终为 DISABLED=6。OK、ADJ 的首次 RPC 切换也均复现菜单被关闭，各有 9 次迟到写入。此组仅有两次只读 RPC、零 W，完整 04 保留，没有误用另一菜单的第 7 行作为配方；失败点是明确要求的“零原生其他菜单写入”。')
add()
add('根因是 `n.watch_view=1` 只在 `ig_apply` 设置。`ig_panel_open` 与 `ig_event` 也会调用预览／应用路径，却没有同样的通信返回归属处理；后续失败或关闭结果仍走 resident 的恢复／撤页收尾。`release_view` 已解决的 H08 路径没有覆盖这两个入口。')
add()
add('gen 117 的 50mm 同样复现 Fn2 和 OK 的菜单写入问题，因此这两条属于继承缺陷。同一冷开 ADJ 在 117 中不发 RPC，没有到达指定切换点，记为不适用；不能将它列为 117 的并发反例。119 的 ADJ 新增确认事务，因此该入口也暴露相同收尾问题。上述对照不改变本次“零原生其他菜单写入”的验收标准。[50mm Fn2](native/entry-switch-50mm-fn2-at1.json)、[28mm Fn2](native/entry-switch-28mm-fn2-at1.json)、[MOUNT Fn2](native/entry-switch-mount-fn2-at1.json)、[OK](native/entry-switch-50mm-ok-at1.json)、[ADJ](native/entry-switch-50mm-adj-at1.json)、[117 Fn2](native/baseline-entry-switch-50mm-fn2-at1.json)、[117 OK](native/baseline-entry-switch-50mm-ok-at1.json)、[117 ADJ](native/baseline-entry-switch-50mm-adj-at1.json)。')
add()
add('3. P1-02：首次 W 前持续通信失败，没有错误行')
add()
add('把第 1 次或第 6 次通信及后续通信全部设为失败，三个单元结果相同。第 1 次场景共 3 次 RPC，第 6 次场景共 8 次 RPC，均为零 W、完整 04。engine 直接退役为 root state=6；下次原生 Image 构造器只打开原生七行列表，没有 `ERR POWER OFF/ON`。应用已经停用，但提示不可见，按题定标准是 P1。')
add()
add('`finish` 和 `ui_finish` 只有在 `eng_uncertain()` 为真时才置 `n.failed` 并保留提示入口。首次 W 前该标志仍为零，持续失败走原有停用路径，不能进入新增的一行错误列表。[50mm 第 1 次](native/failure-boundary-50mm-at1.json)、[第 6 次](native/failure-boundary-50mm-at6.json)、[28mm](native/failure-boundary-28mm-at1.json)、[MOUNT](native/failure-boundary-mount-at1.json)。')
add()
add('部分 W 后的持续失败单独按 P2 处理。第 16 次通信先执行 W 再返回错误，其后始终失败，三个单元均留下混合 RAM，但应用锁定有效，下一次真实开页显示一行错误提示。实际传给原生文字转换器的是完整 `ERR POWER OFF/ON`，并到达原生字形绘制调用。重复 init、Fn2、面板事件／abort、应用入口及 H07 保留／关闭均未增加 RPC 或 preview，提示仍能重开。[50mm](native/persistent-50mm.json)、[28mm](native/persistent-28mm.json)、[MOUNT](native/persistent-mount.json)、[全部入口检查](native/latch-paths-50mm.json)。')
add()
add('恢复到默认 04 的依据分层列明。静态确认配方路径只发 X/V/W，不发 UEE00／UEE53 等 U 提交命令；单元表和参数修改在 RAM，engine 状态在本次加载的 BSS，冷启动模型三单元均为纯 04。结合既有 [t_persistence](../t_persistence/REPORT.md) 与 [t_recovery](../t_recovery/REPORT.md)，完整掉电后回到 04 有静态依据；工厂 adjust 的提交例外仍存在。物理电源开关是否完成单元掉电、断链时复位和断电后九行／T 读回均未实机验证。本轮不把这些未测项另立为阻断，部分 W 后混合 RAM 保留为已知 P2。')
add()
add('4. 三单元完整回归与 H08 切换闭合表')
add()
add('| 场景 | 50mm | 28mm | MOUNT |')
add('| --- | --- | --- | --- |')
for title,result in (
 ('冷开 04、零 W、重启模型 04','PASS'),('gen 117 a–h 全组','PASS'),
 ('H08 坏快照不进入 Setting2 续体；01/02 经 H07 保持完整','PASS'),
 ('28mm 首次未 ready 七行、第二次 ready 八行','PASS'),
 ('41 次连续上下移动，逐步核对九行／T／圆点','PASS'),
 ('ADJ、OK、半按离开保留当前预览，重新打开同一行','PASS'),
 ('H07 原生 keep=0/1 × OK/ADJ 四条确认路径，零额外 RPC','PASS'),
 ('第 16/140 次错误、完整补偿、补偿再失败后纯 04','PASS'),
 ('Fn2 RAM 微调、半按重开和同页嵌套事件','PASS'),
 ('部分 W 后持续失败的锁定／提示／入口检查','PASS'),
 ('首次 W 前持续失败的错误提示','FAIL'),
 ('Fn2、OK、ADJ 并发切换后零其他菜单写入','FAIL')):
    cells=('N/A',result,'N/A') if title.startswith('28mm 首次') else (result,result,result)
    add('| '+title+' | '+' | '.join(cells)+' |')
add()
add('28mm 的未 ready 首次开页仅对 28mm 适用。所有正常路径均移除了 `0x20271FEC` 固定返回替身，执行需要的原生 getter。坏快照、坏包、旧文件属于明确标识的负例数据；正常状态没有手工预置。')
add()
add('| H08 切换点，三个单元都重跑 | 结束时完整配方 | 切换后迟到 UI 写入 |')
add('| --- | --- | ---: |')
for point,slot in (('第 1 次通信','04'),('新增：第 6 次通信，首次 W 前','04'),('第 16 次通信','05'),('新增：第 17 次通信，已有 W','05'),('第 140 次通信','05'),('op3 重画入口','04'),('光标缓存入口','04')):
    add('| '+point+' | '+slot+' | 0 |')
add()
add('RPC 返回后、op3 写入前、缓存同步前的检查均按最终机器码执行。首次 W 前取消目标，已有 W 时收尾成完整目标，未把另一菜单的行号作为配方。op3 与缓存检查位于各自 IRQ 临界区。追加确认路径还逐次检查移动中的 RPC 开始时圆点等于高亮行，三个单元均覆盖全部八行；未用最终重画结果代替通信等待期间的缓存状态。追加跟踪覆盖原生列表状态、视图数组／栈、活动项、overlay 和光标缓存七段内存；五个通信边界、两处 UI 边界和三个入口均按该范围重跑。切换后的普通原生导航、确认及重开本功能再使用 Fn2 也经过实际指令验证。记录中的零迟到写入窗口在后续合法原生导航之前截断。[完整结果索引](acceptance.json)、[50mm 矩阵](native/matrix-50mm.json)、[28mm 矩阵](native/matrix-28mm.json)、[MOUNT 矩阵](native/matrix-mount.json)、[原生确认路径](native/confirm-paths-50mm.json)。')
add()
add('5. 最终 DAT 的文件写入门禁')
add()
add('未发现本配方路径可达的文件创建、写入、删除或改名。两条 `ig_init` 成功路径请求 `0x000E0000`；与 loader 的读能力合并后为 `0x000E7FFF`，不含 `CAP_FILE_WRITE=0x00010000`。能力查询、create、rename、delete、mark、只读 token 的 write 和 close 均在真实最终 dispatcher 上重放；创建及名称变更返回 -12，只读 token 写入返回 -10，close 返回 0，重复初始化没有打开写位。')
add()
add(f'最终 code 与 DAT 逐字节核对，21 个文件调用点、固定 native bridges、间接转移和三个文件能力条件均已列出。只有 create 能产生 write-mode token，该入口被能力门禁排除，write 还要求该 token。{a["required_records"]} 份选定 native 记录中，{a["file_mutation_observations"]} 处文件变更计数观察全部为零；观察次数不是独立场景数。[机器码切点](final-no-write-cutpoints.json)、[调用点](final-file-calls.json)、[dispatcher 执行](machine-gates.json)、[门禁控制流](file-gate-cfg.json)。')
add()
add('6. P1-CG01：rv_call 仍未闭合，其余本地改码义务已逐项处理')
add()
add('编译比较链为 gen 117→118→119。117→118 复用用户提供的已完成审查，本轮重验其完整清单、DAT／ELF 绑定、全部改码分类及未解释分支为空；118→119 在本轮重新分析和执行。此处复用的是已完成的 g118 基线。[基线绑定](codegen-baseline-chain.json)、[既有闭合表](../review_g118/codegen-closure.json)。')
add()
add(f'118→119 的 127 个共享 typed 符号中 96 个改码、31 个同码，另有 4 个新增和 1 个旧 specialization 删除，共 132 个逐名义务。改码分类为 A=77、纯 B=5、C+B=13、C=1。同地址别名逐名保留。19 组 B 共 {cg["B_pairs"]:,} 对，每组均为 10,000 随机加 64 边界输入，比较返回、r8–r15／SP／LR，以及按对象映射的公共逐字节写值序列，零差异。另重跑服务、错误返回和定向边界。')
add()
add('作者留下的 14 个函数先对 gen 117 和 gen 118 尝试整函数 A，均存在规范化后仍不同的非 NOP 指令，需要 B/C。A 的其它项保留非地址立即数、寄存器、分支目标、packet、栈及完整数据对象范围，已核对标签 ELF 的 engine 等于冻结最终代码；没有重新链接。')
add()
add(f'本轮把未覆盖结果逐 PC 分为有意 C、已证明不可达或 OPEN。参数 ID、固定八行、occupied、文本 NUL 等不变式重新从冻结数据／正文核实；文件能力控制流另关闭一批不可能路径。18 组 B/C 的本地改码义务已闭合，唯一仍 OPEN 的具体函数是 `rv_call`，两代合计 {len(open_rows)} 个 PC＋方向结果。其全函数 A 不成立；剩余寄存器／控制流改码没有被当前 B 与不变式全部覆盖。例如 gen 119 相对 PC `0x95AC` 的 `beqz r0` 非跳转结果，对应只读文件 close 返回错误；当前 B 没有覆盖，也没有证明它不可达。故第 5 项未达到 gen 117 r2 标准。这里没有把“未覆盖”声称为实际错码。[A 首轮](A-first-attempts.json)、[逐 PC 审定](branch-dispositions.json)、[具体未闭合项](open-rv-call.json)、[完整表](codegen-closure.tsv)、[依赖图](codegen-dependencies.json)。')
add()
add('逐名闭合表如下。CLOSED_LOCAL 指本项编译改码已闭合；有意功能变化的安全性由前述验收单独裁决。')
add()
add('| 函数／符号 | 变化 | 方法 | 本地闭合 | 证据 |')
add('| --- | --- | --- | --- | --- |')
for row in cg['obligations']:
    evidence=row['evidence'][0]
    add('| `'+row['function']+'` | '+row['status']+' | '+row['category']+' | '+('CLOSED_LOCAL' if row['local_closed'] else 'OPEN')+' | [记录]('+evidence+') |')
add()
add('7. P2：操作延迟')
add()
add(f'从三单元已完成的 123 次正常移动独立统计，共 16 种相邻转移，每格 {latency["rpc_range"][0]}–{latency["rpc_range"][1]} 次通信、{latency["unit_bytes_range"][0]}–{latency["unit_bytes_range"][1]} B 单元写入，RPC 错误均为零。按 tick=1 ms，给定每次通信平均 1–3 ms，仅通信等待为：')
add()
add('| 每次通信平均耗时 | 每格通信等待 |')
add('| --- | ---: |')
for row in latency['scenarios']:
    lo,hi=row['communication_wait_ms'];add(f'| {row["mean_rpc_ms"]} ms | {lo}–{hi} ms |')
add()
add('整格还要加 CPU、内存、调度和显示时间，因此会明显拖慢滚动。平均 2 ms 时，仅通信就约四分之一至近半秒。没有采用未核实的 CPU MHz，也没有拿解释器在主机上的耗时换算相机速度。[计数及公式](latency.json)、[16 种转移](cost-table.md)。建议继续合并尚未 W 的连续输入，减少重复预览；退出时仍须完成最后目标，不削减归属或读回检查。本轮只提建议，没有修改实现。')
add()
add('8. 相对 gen 117 的风险变化')
add()
add('减少：短暂通信故障后能完整补偿；已部分写入时可完成纯 04 回退；H08 在原生菜单切换后停止解释共享行号并保护重画／缓存；部分 W 后持续失败有明确锁定和错误页；首次 W 前能够合并已处理的连续输入。')
add()
add('增加：每次移动光标都执行单元写事务，通信失败窗口和滚动等待随之增多。首次 W 前持续失败没有提示的情况也会在导航中暴露。Fn2／OK 的其他菜单收尾问题在 117 对照中已存在，本次没有关闭；ADJ 在本冷开对照中由不发 RPC 变为发起确认事务，新增了这一切换窗口。文件写能力、配方数据和 body resident 没有增加风险；共享 dispatcher 的编译改码证明仍缺上述具体义务。')
add()
add('P0：未发现新的可达文件改动或正常路径混合设置结果。P1-01、P1-02 和 P1-CG01 均保留。P2 为满足锁定条件后的混合 RAM、操作延迟及未实测的 LCD 中间帧。静态和模型结论不替代实机的通信时间、图形锁／调度、LCD 和物理断电验收。')
add()
add('9. 恢复说明')
add()
add('把卡上的 GXRCE.DAT 换回 gen 117（35ce20ac…）；若相机异常，用卡 A（Stage2l-50mm）挂 50mm，开机时按住"+"与回放键进入更新。')
add()
add('10. 重放与清单')
add()
add('以下脚本只写本审查目录，不调用编译器或设备。已存在的命令记录不会覆盖，重放命令需使用新的记录标签。')
add()
add('```sh')
add('/usr/bin/python3 -I -B research/review_g119b/setup.py')
add('/usr/bin/python3 -I -B research/review_g119b/artifacts.py')
add('/usr/bin/python3 -I -B research/review_g119b/run_native.py matrix 50mm')
add('/usr/bin/python3 -I -B research/review_g119b/concurrent_menu.py other_menu 50mm --at 6 --reopen-fn2')
add('/usr/bin/python3 -I -B research/review_g119b/entry_switch.py 50mm fn2')
add('/usr/bin/python3 -I -B research/review_g119b/failure_boundaries.py 50mm 1')
add('/usr/bin/python3 -I -B research/review_g119b/coverage_collect.py')
add('/usr/bin/python3 -I -B research/review_g119b/branch_notes.py')
add('/usr/bin/python3 -I -B research/review_g119b/close_codegen.py')
add('```')
add()
add('`SHA256SUMS` 覆盖本目录全部普通文件，按惯例不含清单自身；最终自检全部 OK。路径及报告链接另经检查。[自检结果](checksum-selfcheck.json)、[完整证据索引](acceptance.json)。')
(OUT/'REVIEW.md').write_text('\n'.join(line)+'\n')
save('report-facts.json',dict(verdict='不可以上卡。',generated_utc=finish,native_records=a['required_records'],
    open_codegen_function='rv_call',open_outcomes=len(open_rows),body_hash_unchanged=True,source_build=False,device_access=False))
print('WROTE REVIEW.md; native collection and protected input gates complete',flush=True)
