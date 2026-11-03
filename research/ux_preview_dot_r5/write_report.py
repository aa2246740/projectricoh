"""Write the final Chinese handoff without promoting incomplete checks."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,PACKAGE,save,file_sha,START_UTC,DEADLINE_UTC
read=lambda name:json.loads((OUT/name).read_text())
identity=read('identity.json')['120'];old=read('implementation-candidate/identity.json')['120']
acceptance=read('acceptance.json');assert acceptance['status']=='NOT_ACCEPTED'
rows=read('fn2-step-summary.json');audit=read('zero-file-write-audit.json');integrity=read('input-integrity.json');name_integrity=read('name-input-integrity.json')
closure=read('codegen-closure.json');named=read('data-name-equality.json')
assert integrity['status']==name_integrity['status']==audit['status']==named['status']=='PASS'
for unit in ('50mm','28mm','mount'):
 assert read('remaining-suite-'+unit+'.json')['status']=='PASS'
 assert read('native/names-'+unit+'.json')['status']=='PASS'
time=datetime.now(timezone.utc).isoformat()
text=f"""未通过交付验收，主修复已按“无法仅在配方包内解决时停止”的边界交回。已产出含统一短名称的 gen 120b 候选；运行时只更换配方 DAT，v3.6 resident 和机身文件均未改动。尚未满足的是完整 H07 关闭链的“无让出点”要求、锁定态建立新确认，以及全部编译改码的 A/B/C 闭合。

| 项目 | 状态 | 实际验证范围 |
| --- | --- | --- |
| Fn2 方向键边调边看，OK、ADJ、半按保留 live | PASS | 三单元主修复候选的原生事件、九行及 T 检查。 |
| H07 在指定状态零 RPC / W / preview | PASS | 50mm 28 条、28mm 32 条、MOUNT 28 条，共 88 条。 |
| H07 所有状态 confirmed←live | 未全部满足 | 锁定态当前只保持锁定，没有建立新确认。 |
| H07 配方处理段无通信和让出调用 | PASS | 最终引擎的 22 个 typed 正文及只读 ready 入口。 |
| H07 含固定原生关闭续程的全部调用均无让出点 | 未满足 | keep=0 的固定关闭续程可达 UI 任务同步。 |
| Fn2 并发切换后完整配色、零其他菜单写入 | 部分完成 | 05 对比度 +1 的全部 42 次 RPC 和 preview 边界，三单元均通过；未展开其他参数的全部通信点。 |
| 首次 W 前与部分 W 后持续失败均显示错误行 | PASS | 两类锁定、反复开页及各入口检查。 |
| gen 119b 功能矩阵 | PASS，见范围说明 | 三单元完整前缀与余项，以及每单元 21 组扩展检查；旧 32 步性能采集未重跑。 |
| 三单元新名称、身份 CRC、216 行颜色等价 | PASS | 最终短名称候选的独立数据检查及三单元原生字形提交。 |
| 零文件写入审计 | PASS | {audit['native_files']} 份记录、{audit['counter_observations']} 处计数观察全零；静态门禁另核对。 |
| 全部改码函数 A/B/C 闭合 | INCOMPLETE | 136 个逐名义务已列出；未把采样通过记作完整闭合。 |
| 卡包结构、28 个官方伴随文件、CARD_SHA256SUMS | PASS | 30/30 文件；最终候选仍为 NOT_ACCEPTED。 |

1. 候选身份与写入范围

| 对象 | SHA-256 / 数值 |
| --- | --- |
| 最终短名称 DAT | `{identity['dat']}`；{identity['bytes']:,} B；generation 120。 |
| 已跑主交互矩阵的 DAT | `{old['dat']}`，保存在 [implementation-candidate](implementation-candidate/)。 |
| 两份候选共同的 engine | `{identity['engine']}`；49,576 B。 |
| 两份候选共同的 ELF | `{identity['elf']}`。 |
| BSS / 文件余量 | 9,720 B / 6,408 B。 |
| v3.6 ilaunch3 | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。 |
| resident build id | `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`。 |
| ABI | `d7387c3670059c325186de3af1b3d5c6`。 |
| 官方 ZIP | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。 |
| ZIP 中的原版 ilaunch3 | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。 |

构建树为 `firmware/engine_v42_ux`，从只读 `engine_v41_ux` 复制；卡包为 `firmware/package_v36_g120b/SD_ROOT`。既有 `package_v36_g120` 未使用、未改动。最终包除 DAT 外的 29 个文件与 gen 119 包相同，其中 28 个与官方 ZIP 逐字节相同。信任绑定来自原有 `resident_v36/local/resident/trust.json`。

仅在题定三个目录写入。冻结输入 {integrity['files']:,} 项及后补名称数据 {name_integrity['files']} 项前后哈希均相同。卷身份为已挂载 APFS，UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。没有操作相机、实际存储卡或启动子代理。Python 均通过 `/usr/bin/python3 -I -B` 执行。

时间盒开始 `{START_UTC}`，截止 `{DEADLINE_UTC}`；本报告生成于 `{time}`。主修复在发现固定关闭边界后停止功能改动；随后只并入用户另行授权的名称数据并封存证据。

2. 用户决定与实现

2026-10-27 21:45 的决定“也边调边看”已落到自定义 Fn2 路径。方向键使用 `eng_preview_saved`，与 H08 共用受保护事务。每次 RPC 返回后重查归属；归属变化时停止后续 UI 写入，并把已经开始的单元写入收尾为完整配色。Fn2 数字行不参与配方列表的行合并，避免把数值光标当成配方槽号。

`eng_confirm_live` 只复制 current / tweak 到 confirmed，不执行 fresh、RPC、preview 或文件服务。冷开 04 先建立纯 RAM 的原厂身份；H07 不为建立确认而重写单元。可确认状态的列表和 Fn2 都接受当前 live；锁定态继续保留锁定。锁定态的用例验证零通信，没有声称为不确定单元建立新的有效确认。

OK、ADJ、半按均保留已经看到的值。旧 `fn2_half_exit` 的“放弃草稿”断言已改为保留 live：先接受 +1，再调整 +1，半按后重开仍为 +2。这是用户明确选择的行为变化。独立的 Fn2 保留用例还逐条验证退出没有额外 RPC / W / preview。

临时失败先恢复已确认的配方及微调；补偿再失败但通信恢复时，写完整纯 04、零微调，并锁定错误提示。`finish` / `ui_finish` 通过通信失败标记，把首次 W 前的持续失败也纳入锁定。沿用 `ERR POWER OFF/ON`，因为它保留已通过原生绘制检查的短提示，恢复动作也仍是断电重启；没有扩展提示文本。

实现差异见 [source.patch](source.patch)、[source-scope.json](source-scope.json)、[interaction-decision.json](interaction-decision.json)。原始差异字节另以十六进制保存在 [source-patch-provenance.json](source-patch-provenance.json)。

3. 停止原因：固定 H07 关闭链仍可达任务同步

H07 配方处理树的直接执行调用已逐一列在 [h07-recipe-callgraph.json](h07-recipe-callgraph.json)。22 个 typed 正文中没有间接调用，也不调用 `rv_call`、单元 RPC、preview、分配或文件 API。ingress 会保存服务函数地址，但此处不调用它。唯一原生叶节点是 ready getter `0x2009359C`，正文只读取 `0x200D7FD8`。

完整退出还包含固定 resident 的关闭续程。`keep=0` 时，四种合法配方返回值都不能取消该续程：

```text
rv_close_07      0x20052BE8
native layer    0x201C092C
layer transfer  0x201D83B0
show part 1     0x201D79F4
UI task service 0x2005FF88
service body    0x2005FDFC
state scheduler 0x20060300
```

原生底层 part 1 已登记时，flags=3、kind=2。关闭 part 2 会选择显示 part 1，并在绘图前进入 UI 任务同步。三个单元的补例都执行官方 part 1 构造分支 `0x2030E8CC..0x2030E8E4`，再走正常父页、配方列表和 H07；没有直接给原生 UI 字段赋值。三者均记录到上述同步入口，单元 RPC 仍为 0。

这组补例证明入口可达；同步函数后面的绘图因未提供完整字体/显示环境而停止。原始 FAIL 记录完整保留，没有计为整条原生关闭验收通过。真实 RTOS 调度和相机在此处切换菜单均未观察。固定代码本身允许调度，因此不能把模型中的同步返回当成“所有调用均无让出点”的证明。

证据为 [h07-close-boundary.json](h07-close-boundary.json)、[native-static](native-static/)。下一步需要主任务决定完整关闭续程是否属于该验收边界，或另定固定关闭代码的修改范围；本轮没有改 resident，也没有改原生显示层状态来消除该分支。

4. 原生回归与并发检查

下表针对主修复 DAT `{old['dat']}`；记录索引和实际哈希在 [acceptance.json](acceptance.json)。正常 UI、光标和 resident 状态由原生构造器、方向键及退出事件建立。`0x20271FEC` 固定返回替身已移除。设备通信、文件系统、字体资源、绘制提交和部分系统边界仍是模型；此处没有相机或 LCD 验收。

| 功能组 | 50mm | 28mm | MOUNT |
| --- | --- | --- | --- |
| 冷开 04、零 W、重启模型 04、a–h | PASS | PASS | PASS |
| 首次未 ready / ready 后再开 | 不适用 | PASS | 不适用 |
| 连续 41 步、九行 / T / 圆点、正常 ADJ / OK / 半按 | PASS | PASS | PASS |
| 短暂失败、完整补偿、补偿再失败后纯 04 | PASS | PASS | PASS |
| Fn2 live、接受、半按保留和重开 | PASS | PASS | PASS |
| 首次 W 前持续失败的单行提示 | PASS | PASS | PASS |
| 部分 W 后持续失败的单行提示、各入口继续锁定 | PASS | PASS | PASS |
| H07 全状态、keep=0/1 × OK/ADJ，RPC/W/preview=0 | 28 条 | 32 条 | 28 条 |
| Fn2 05 对比度 +1，全部 RPC + preview 切换点 | 43 点 | 43 点 | 43 点 |
| H08 第 1/6/16/17/140 次通信、重开 Fn2 | PASS | PASS | PASS |
| op3 / 光标缓存两个末端检查点 | PASS | PASS | PASS |
| 第 1/16 次通信发生连续导航合并 | PASS | PASS | PASS |

H07 状态包括冷开 04、H08 成功、补偿成功、Fn2 已 live、Fn2 打开未调，以及两类持续失败锁定；28mm 另加首次未就绪。三单元 88 条确认记录的 RPC、W、preview 均为 0。

Fn2 全点检查覆盖 05 对比度从 0 到 +1 的 42 次 RPC 和 preview 调用；在每个位置执行另一个原生菜单的构造器。七段 UI 范围均无迟到写入，结束时 activity=7、overlay=21，单元是完整的 05 或完整的 05/+1。其他三个参数做了逐步 live / 九行一致性检查和通信统计，但停止后没有继续展开它们的每个通信点组合。嵌套 OK、ADJ、半按的九条结果另按完整 04 和无二次配方入口核对，范围见 [nested-event-check.json](nested-event-check.json)。

矩阵的旧辅助函数把重新开页固定断言为 8 行，与新增锁定后的 1 行提示不符。原始失败前缀保存在 `partial-runs/matrix-prefix-*.json`；相同 DAT 的独立原生余项和必需提示检查组成 `native/matrix-complete-*.json`。没有把未执行的余项算进通过。旧 a–h 输出中的 generation 117 是沿用的文字标签，实际 DAT 与 JSON 的 generation 已核对为 120。

后补名称没有改变 engine、ELF、重定位、trust 或有效颜色字节，见 [name-code-binding.json](name-code-binding.json)。最终短名称 DAT 单独重跑三单元名称构造/绘制与文件门禁，没有重新跑第二遍完整交互矩阵。这层边界不以数据等价取代最终整包交互验收。

5. 名称与 gen 117 的数据等价

```text
01 GRPos    02 GRNeg    03 HC BW    04 Std
05 F-CC     06 F-CN     07 L-Chr    08 L-Viv
```

先复核名称交接目录的 127 项清单，再调用它的只读数据适配函数；该函数会拒绝与 gen 117 不同的源 record / entry / map。18 个可见 record 改名，03、04 和隐藏槽保留原记录。entry552 仅重绑 +4 的 identity CRC，九行及其 CRC、T/control、map、pin 和 metadata 均不变。

[独立等价检查](data-name-equality.json) 对三单元 24 个可见 entry 的 216 行逐字节比较；含隐藏别名展开共 432 行。相对已测试的主修复 DAT，最终 DAT 仅有 {named['changed_bytes']} 个字节不同，全部位于名称、长度、record/bank/descriptor CRC、identity CRC 和容器 CRC 的允许位置。没有并入新的颜色系数。

| 原生名称绘制 | 实际记录 |
| --- | --- |
| 三单元八个新名称 | [50mm](native/names-50mm.json)、[28mm](native/names-28mm.json)、[MOUNT](native/names-mount.json)，均 PASS。 |
| 转换与字形 | 真实 `0x201D73E0` 输入匹配新 ASCII 名；绘制提交的编码字形匹配官方转换表。 |
| 名称左缘 / 纵坐标 | x=38；y=132..398，38 的行高预算不超过 480。 |
| 最大名称宽度 / 最大右缘 | 98 / 136；右缘小于下一列 x=219。最窄 101 的预算也满足。 |

字体步进来自已审计的官方字体资源，实际字形与坐标来自原生绘制提交。像素栅格化和实体 LCD 未测。早期测试误用了值列 x=219，并在加载前用未重定位地址挂文字记录点；两项均只修正测试，原始输出保存在 `partial-runs/name-*`，最终三组检查从原生构造器重新执行。

6. Fn2 每一步通信与等待估算

05 配方的四个参数各走 20 个有效数值步，三单元共 {rows['steps']} 步。逐步 TSV 与九行哈希见 [fn2-step-counts.tsv](fn2-step-counts.tsv)、[fn2-step-summary.json](fn2-step-summary.json) 及 `native/fn2-step-counts-*.json`。

| 参数，三单元结果相同 | 每步 RPC | 每步 W | 单元写入字节 | 每步 RPC 等待估算 |
| --- | ---: | ---: | ---: | ---: |
| 对比度 | 42 | 34 | 68 B | 42–126 ms。 |
| 饱和度 | 32–82 | 28–76 | 56–152 B | 32–246 ms。 |
| 锐度 | 42 | 34 | 68 B | 42–126 ms。 |
| 色调 | 42 | 34 | 68 B | 42–126 ms。 |

每步均记录 1 次 preview。按用户给定 tick=1 ms、每次通信 1–3 ms，以 RPC 次数相乘计算等待范围。这只是通信等待之和，CPU/CRC、preview 和原生绘制另计；没有测相机总延迟，也没有据此推算 CPU MHz。

7. 编译改码状态

[逐名 A/B/C 表](codegen-closure.tsv) 和 [结构化状态](codegen-closure.json) 覆盖 136 项义务：96 个改码共享符号、31 个同码共享符号、5 个新增和 4 个删除。114 项通过局部 A，含真实 GAS 标签给出的完整匿名数据区间、非地址立即数、packet、栈、分支和依赖目标检查；没有把尾部填充裁短后签为相同。

15 组 B 各跑 10,000 随机加 64 边界，共 150,960 对。比较返回、r8–r15/SP/LR 和按对象映射的公共逐字节写值历史，C 投影及共同 callee 合同保存在对应脚本和结果。包括旧 `apply_impl` 对新 specialization 的正文执行；RAM 辅助函数另有三组 literal 期望检查。

这些不是完整闭合。119→120 尚有 {closure['open_current_outcomes']} 个 PC+方向结果未逐一签定 C 切点或冻结不变式；118→119 的 `rv_call` 遗留项另有 {closure['open_previous_outcomes']} 个未裁决结果。后者已追加 45,504 对通信服务边界、8,058 对 UI 边界、20,571 对字段边界和 213 对定向边界；未返回的 fixture 范围单列，未计入通过。候选调用域 CFG 仍需证明调用者约束，没有用它提前关闭结果。

完整未解释清单在 [codegen-open-outcomes.json](codegen-open-outcomes.json) 与 [previous_delta/rv-coverage-current.json](previous_delta/rv-coverage-current.json)。本轮停止后没有把它们改为 CLOSED，也没有把局部 A 或有限 B 当作递归依赖闭合。

8. 零文件写入、遗留风险与自检

最终代码的两条成功初始化请求均为 `0x000E0000`，合并读能力后 `0x000E7FFF`，不含 `CAP_FILE_WRITE=0x00010000`。21 个文件调用点、固定 native bridges 和能力控制流已核对。最终短名称 DAT 的真实 dispatcher 重放中，create/rename/delete/mark 返回 -12、只读 token 的 write 返回 -10、close 返回 0；重复初始化没有打开写位。证据为 [machine-gates.json](machine-gates.json)、[file-gate-cfg.json](file-gate-cfg.json)、[zero-file-write-audit.json](zero-file-write-audit.json)。文件变更计数与单元 RPC 的 W 分开统计。

部分 W 后通信持续失败仍可能留下混合单元 RAM；本轮保留既有锁定和断电提示路径，没有把提示等同于已经恢复纯 04。模型冷启动回到 04，实体掉电后的九行和 T 读回未测。短暂失败可恢复已确认值；第二次补偿失败且通信随后可用时才验证完整纯 04。

交回时尚缺：完整 H07 关闭链的验收边界决定、锁定态新确认的要求落实、全部 A/B/C 裁决、其他 Fn2 参数的全通信点组合，以及最终短名称整包的第二遍完整交互检查。相机、卡、真实 RTOS、LCD 和物理掉电均没有新增验收。

冻结输入见 [input-integrity.json](input-integrity.json)、[name-input-integrity.json](name-input-integrity.json)。卡包自检为 `firmware/package_v36_g120b/CARD_SHA256SUMS`，覆盖 30 个 SD_ROOT 文件。另有构建树和卡包的 `EVIDENCE_SHA256SUMS`，以及本目录 [SHA256SUMS](SHA256SUMS)。

[seal.py](seal.py) 生成清单后分别执行标准 `shasum -a 256 -c`。每份清单的哈希、退出码和 OK 数量保存在 [checksum-selfcheck.json](checksum-selfcheck.json)；自检记录本身不纳入自己的清单。复跑检查会更新本目录记录，之后需重新运行 seal.py。
"""
(OUT/'REPORT.md').write_text(text)
(PACKAGE/'STATUS.txt').write_text('NOT_ACCEPTED / STOPPED\nOnly the recipe DAT changes; body and resident are unchanged.\nFixed H07 native close no-yield requirement, locked-state confirmation and full compiled-function closure remain incomplete.\nDAT SHA256 '+identity['dat']+'\nReport: research/ux_preview_dot_r5/REPORT.md\n')
save('task-status.json',dict(status='STOPPED_NOT_ACCEPTED',implementation_dat=old['dat'],named_dat=identity['dat'],resident_modified=False,body_modified=False,short_names_included=True,main_stop_reason='h07-close-boundary.json',codegen='INCOMPLETE',report='REPORT.md',start_utc=START_UTC,deadline_utc=DEADLINE_UTC,report_utc=time))
print('WROTE Chinese handoff; candidate NOT_ACCEPTED; names included',flush=True)
