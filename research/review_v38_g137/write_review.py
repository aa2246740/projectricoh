import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
reg=json.loads((OUT/'regressions.json').read_text())
art=json.loads((OUT/'evidence/artifact-review.json').read_text())
source=json.loads((OUT/'evidence/source-review.json').read_text())
required=['empty-28mm','empty-mount','h07-parent-50mm','list-windows','menu-edges-28mm']
focus={r['name']:r for r in reg['focused']}
ready=reg['closed']==11 and all(focus[name].get('returncode')==0 and focus[name]['status']=='DONE' for name in required)
verdict='可以刷机' if ready else '不可以刷机'
counts={key:sum(r['status']==key for r in reg['groups']) for key in ['PASS','CLOSED_KNOWN_P2']}
def load(name):
    p=OUT/'evidence'/name
    return json.loads(p.read_text()) if p.exists() else {}
owner=load('ownership-host.json')
native=load('native-events.json')
parts=[verdict,'',
    '本结论只绑定下表这一对文件，属于刷机前的离线质量复审。未操作相机、存储卡或网络；相机上的 v3.8 显示、调度、拍摄和持久性仍未验收。',
    '', '| 对象 | 固定身份 |','| --- | --- |',
    f'| GXRCE.DAT | gen 137，89,936 B，`{art["dat_sha256"]}` |',
    f'| ilaunch3 | v3.8，3,993,340 B，`{art["body_sha256"]}`，存储校验字 `6a7d99ef` |',
    f'| 引擎 ELF | `{art["engine_elf_sha256"]}` |','',
    '静态已证：包哈希、DAT 头部和数据 CRC、resident 信任数据、ELF 与包内代码一致、段界限、源码差异及入口调用位置。',
    '主机已证：本轮实际执行结果见下表和 REGRESSIONS.md。完整菜单组使用 M32R 指令模型，设备、图形和通信叶函数仍有模型；C 谓词、窗口和事件检查另行标明主机层。',
    '推断：已识别的 Image 构造调用链与当前归属条件共同限制空栈例外；不能由空栈字段本身证明所有原生界面和 RTOS 时序都唯一。',
    '未知：真实 RTOS 切换窗口、LCD 瞬时高亮、拍摄峰值堆，以及现场一次诊断程序冻结的原因。','',
    '## 回归与抽样','',
    f'要求的 11 组闭合 {reg["closed"]}/11；整组 PASS {counts["PASS"]} 组，已知标题差异下闭合 {counts["CLOSED_KNOWN_P2"]} 组。后者保留原始退出码 1，只有其余断言全部执行完才计闭合。用户已明确将标题差异定为本轮不阻断的 P2。',
    '', 'values 每组有 7 个子项：四项数值的步进与两端夹紧、L1 滚动、Default、第二对控制返回光标。返回光标期望改为 (1,2)。本版 L1 和条目页的旧夹紧期望也按循环设计更新，并增加一次反向按键返回原位置，原有数值、完整设置、只读元数据、归属、RPC 和退出断言继续执行。读取合同见 PORT_NOTES.md。',
    '', '| 抽样 | 运行与结果依据 |','| --- | --- |']
for name in required:
    item=focus[name]
    parts.append(f'| {name} | OS 返回码 {item.get("returncode","")}，{item["status"]}；`evidence/{name}.json` |')
parts+=['',
    '用户工具按路径调用 `research/review_g135_gpt/users_gxui.py`，仅绑定到当前 gen 137 基线；32 条往返、163 类无效条目、空区逐字节恢复和代码不变检查通过。正式源码树的用户 CLI 交付问题仍按继承 P2 保留。',
    '', '## 源码与空栈边界','',
    '复核到的固件运行差异分为两项：空栈构造规则，以及列表循环与填充行。generation 和 resident 身份同步。文件树还裁剪了旧辅助文件、清理了中性命名及段名，并将机身链接余量门槛从 200 B 调到 176 B，不能把它概括成“整个目录只有两处改动”。完整文件及行区间见 `evidence/source-review.json`。',
    '', '| 范围 | 本轮差异 |','| --- | --- |',
    '| v3.8 机身 | `resident/hooks.c` 的空栈接受限于 H01/H02，且要求原生列表为 8 行；根、状态、名称表、活动 8、原生状态 56、part 1/2、固定数组条件仍在。`shared.c` 增加构造参数，其他服务调用传 0。 |',
    '| gen 137 DAT | `rv_view_owned` 的 count 0 只接受 constructing==1。设置路径由实际入口 1、当前 entry_serial、nonce 和会话绑定限制。UI_LIST op1 在 IRQ 边界核对当前入口；首发还要求库存名称表和 7 行，已有本列表时要求当前私有名称表和 8 行。 |',
    '| 严格路径 | H05–H08 不使用空栈例外。DAT 的更新、重绘和普通归属检查传 0；设置路径的入口 6/7/8 也传 0。tag 33、顶层状态、列表、会话与 view/lease 检查保留。H07 父层复跑单独记账。 |',
    '| 列表 | 前四类页面由 kv_ui_move 处理，数值页夹紧，其余取模；分组和条目页在适配层取模。第一条填充行显示 `--------`，后续留空，填充行不成为逻辑可选项。uv_window 未改变。 |','',
    f'主机谓词矩阵结果：{owner.get("status","尚无完整回执")}；机身 {owner.get("body_cases","")} 例、DAT {owner.get("data_cases","")} 例、严格路径与基线相等 {owner.get("strict_equal","")} 例，另有 24 项 DAT 单条件负例和入口上下文检查。会话有效性在这项 C 检查中由模型提供。见 `evidence/ownership-host.json`。','',
    'count 0 时没有可用的栈顶状态，因此本版确实不靠 tag/state 区分界面。普通其他界面只满足 count 0 不能通过：还必须同时保持上述活动、状态、part、固定数组、当前私有列表与会话条件，且处于实际 Image 入口。当前机身中已识别的构造链为状态 56 的 ADJ 回调 `0x202BA5C8`，在 `0x202BA76C` 调用 `0x20287080`；H01/H02 均在该构造器内。独立扫描找到一个该形式的绝对调用、没有直接相对链接候选；这不是对所有间接调用的穷举证明。见 `evidence/native-entry.json`。',
    '', '若另一段原生切换过程保持全部同值并在 H01 尚未结束时复用这组字段，逻辑上仍可能误认构造归属，后果可包括错误发布 8 行列表，以及在 H01 设置或预览阶段继续操作。没有发现该路径的现场复现，不能写成已确认的产品缺陷。空栈情况下 H05–H08 仍拒绝进入 DAT 的严格处理；本次复审没有关闭首发和最后核对后的既有时序窗口。','',
    '## 问题表','',
    'P0：本轮未确认新的 P0。下表“继承”表示仍需跟踪，未表示已关闭。','',
    '| 级别 / 编号 | 新或继承 | 状态与复现方式 |','| --- | --- | --- |']
if not ready:
    parts.append('| P1-R1 | 新，验证未闭合 | 要求组或抽样仍有未闭合结果，见 REGRESSIONS.md；按该表对应路径和固定包重跑。当前不放行。 |')
parts +=[
    '| P1-01 | 继承 | OPEN。首发 8 行之前的原生 7 行窗口。复现方法：在 `research/review_g126/cold_reentry.py` 的首发前按键切点触发方向键，再观察原生 store、发布和恢复。真实调度可达性仍未定；本轮没有重跑该组。 |',
    '| P2-03 | 继承 | OPEN。最后一次归属检查之后、原生预览之前仍有窗口。当前最终 ELF 中，rv_call 内的原生预览调用偏移为 0xD388，前一条准备指令在 0xD384，IRQ restore 在 0xD380。复现方法：在 0xD384 切换视图再继续；本轮只独立重绑切点，未重新执行该旧问题。见 `evidence/elf-calls.json`。 |',
    '| g124/P2-01 | 继承 | OPEN。末端重绘窗口。复现方法：在当前 `ui_list` 的原生绘制调用 0xBEAC 之前改变归属，继续观察原生行绘制与 0x201FD392 的 store。本轮未重跑绘制本体。 |',
    '| P2-04 | 继承 | OPEN。普通预览 I/O 失败后重开刷新。复现方法：保留视图归属，让一次普通预览服务返回失败，关闭后重开并比较完整设置和 8 行；归属丢失的 pending/read 用例不能替代它。本轮未重跑。 |',
    '| g129/P2-01 | 继承 | OPEN，连续堆风险。当前主块请求 108,124 B，另有加载区和 UI 快照。复现方法：在原生堆模型中保留 3 个 32 KiB 读取块后，再请求 77,336 B；当前静态余额约 53,032 B，不足。真实并存可达性未知。三次诊断现场读数均为 204,280 B 连续空闲，只证明那三个时刻。 |',
    '| v38/P2-01 | 新，预算 | 主块设计余量 0 B，机身代码距 root 176 B，当前仍在静态界限内。复现方法：运行 `artifact_review.py`，检查 main_request=108124、design_margin=0、resident_margin=176。后续增加代码或 BSS 需重新核算。 |',
    '| UI/P2-01 | 继承，用户已定 | 用户条目卡片显示底子名，例如 `<5 F-CC`，本轮不阻断，下一版改条目名。复现方法：进入 FCC 用户条目后打开卡片；旧 `<FCC-001` 期望和实际标题在各组 user-display.json 中并存。 |',
    '| g135/P2-01 | 继承 | 正式源码树缺少当前格式用户 CLI。本轮工具能工作，未写回正式树。复现方法：检查当前 candidate 交付文件集，再按 PORT_NOTES.md 调用复审工具处理本版 DAT。 |',
    '| g135/P2-02 | 继承 | 引擎树的 resident 副本仍不能代替 canonical resident_v38。复现方法：比较两者 hooks.c。实际包已按 resident_v38 ELF 与身份独立核对，不受该副本影响。 |',
    '| g135/P2-03 | 继承 | 旧套件需要当前布局、整数向量、generation、循环及光标记忆的读取适配。复现方法：比较本轮 binding JSON 与 PORT_NOTES.md 后调用原路径；不带适配的旧套件会停在旧期望。 |',
    '| list/P2-01 | 继承，本轮确认 | 前四类页面的非相邻物理事件仍可移动多行，分组和条目页则只重绑。复现方法：L1 current 0、physical 0 时送 physical 2，得到 current 2。该映射函数与 gen 135 逐字节相同，设计 T4 的统一表述与现代码不一致。是否存在真实单次按键路径仍未证。见 `evidence/native-events.json`。 |',
    '', '## 堆与现场读数','',
    '本版 108,124 B 是从最终 DAT 长度和 BSS 独立算出的加载请求，等于设计预算，不是相机剩余堆。现场诊断主块跨度为 57,244 B；若替换为当前主块跨度 108,136 B，并计入 1,980 B 独立 UI 快照，且其余分配不变，204,280 B 现场连续空闲对应约 151,408 B 剩余。这个值是条件推算。见 `evidence/heap-review.json`。',
    '', '同份现场记录还有一次诊断程序在连续拍摄时冻结，第二次未复现，原因未定。没有把它归因于本版或堆，也没有把三个空闲快照当作所有拍摄时序的峰值证明。',
    '', '## 输入与交付边界','',
    '本轮只写本复审目录和指定 Scratch；旧 wrapper 的唯一允许例外仍限 `research/emptystack_v38/local`。没有源码、包、Git、相机、卡或网络写入。一个调度器、最多 3 个验证工作槽、每组 4,200 秒；完整启动和停止回执见 `evidence/runs.jsonl`。准备错误和主动停止保留，未用旧组的非零返回码冒充通过。',
    '', '全局时间盒为 UTC 2026-10-30 05:26:28 至 08:56:28。临时目录按任务要求在结束时删除。输入前后和清单结果见 `evidence/seal.json`，SHA256SUMS 中的路径均相对仓库根。',
    '', '本轮没有补跑完整 81 组，没有从头重建固件。旧 safety 三条失败继续采用 `research/g129_safety_triage/REPORT.md` 的已定测试侧结论，不重新记为产品缺陷。']
(OUT/'REVIEW.md').write_text('\n'.join(parts)+'\n')
print(verdict)
