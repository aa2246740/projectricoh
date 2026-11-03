"""Seal the independent review and a repository-root-relative manifest."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

before=json.loads((OUT/'input-before.json').read_text())
after=inputs()
changed=[name for name in before if after.get(name)!=before[name]]
assert not changed and before.keys()==after.keys(),changed
save('input-after.json',after)

def read(name):return json.loads((OUT/name).read_text())

partial=read('local/cases/122-50mm-partial_reset.json')
baseline=read('local/cases/121-50mm-partial_reset.json')
half=read('local/official-half-with-hooks.json')
assert partial['RPC']==20 and partial['W']==0 and not partial['after_recipe5']['matches']
assert baseline['RPC']==805 and baseline['W']==253 and baseline['after_recipe5']['matches']
assert half['status']=='COUNTEREXAMPLE_REPRODUCED' and half['half_RPC']==0 and not half['entry_calls']
assert half['resident_hooks'][0]['hook']==7 and half['resident_hooks'][0]['name']=='owned'
assert half['resident_hooks'][0]['fail']=='0x205a280f'
assert half['native_UI']['host_ui_writes']==0
safety=read('evidence/safety-50mm.json')
suite=read('evidence/suite-122-50mm.json')
assert all(x['wait_status']==0 for x in safety['cases'])
assert all(x['wait_status']==0 for x in suite['results'])
assert read('evidence/machine-sentinel.json')['count']==852
assert read('evidence/machine-read.json')['count']==103
assert read('evidence/codegen-safety.json')['undecoded_executable_bytes']==0
summary=dict(verdict='不可以上测试卡',P0=0,P1=2,P2=0,
    dat_sha256=file_sha(DAT),dat_bytes=DAT.stat().st_size,baseline_sha256=file_sha(BASE_DAT),
    elf_sha256=file_sha(ELF),body_sha256=file_sha(BODY),
    partial_reset=dict(gen122=dict(RPC=20,W=0,recipe5_matches=False),
                       gen121=dict(RPC=805,W=253,recipe5_matches=True),
                       fault=partial['fault']),
    deferred_half=dict(raw=half['half']['raw'],logical=half['half']['logical'],RPC=0,
                       DAT_entries=0,resident_hooks=half['resident_hooks'],
                       rows_before=half['pending']['rows'],cursor_before=half['pending']['cursor'],
                       overlay_after=half['after_half']['native_overlay'],recipe5_matches=False),
    native_safety_cases=len(safety['cases']),native_behavior_cases=len(suite['results']),
    machine_read_cases=103,machine_sentinel_cases=852,
    tested_native_units=['50mm'],data_and_machine_read_units=['50mm','28mm','mount'],
    camera_tested=False,full_capture_tested=False,full_suite_rerun=False)
save('evidence/review-summary.json',summary)
save('integrity.json',dict(protected_files=len(before),changed=changed,dat_sha256=file_sha(DAT),
    dat_bytes=DAT.stat().st_size,write_root=str(OUT),network=False,camera=False,card=False,
    interpreter='/usr/bin/python3 -I -B',r2_written=False))

report='''不可以上测试卡

P0：未发现。

P1-01：哨兵以外的行内部分复位会被当作核对成功，属于相对 gen 121 的回退。

- 位置：`firmware/engine_v44_keep/candidate/containers/product/src/firmware/engine/core/eng_core.c:559`、`:579`、`:589`、`:610`。
- 复现：用官方构造和原生按键选中、确认配方 05，正常重开一次；只把第一条映射行内 `0x2012f540` 的一个半字复位为标准 04，保持哨兵 `0x2012f504`、T 和 epoch 不变，再重开。两处地址均在同一条 62 B 行内，没有涉及邻字节或原生 UI 预置。命令见文末 `partial_reset`。
- 结果：gen 122 只发 20 次 X/V、W=0，八行列表的光标、小圆点仍为 5，`warning=0`、`failed=0`、`retry=0`，但逐字节核对配方 05 失败。同条件 gen 121 发 805 次 X/V/W、其中 W=253，并恢复完整配方 05。
- 影响：部分单元行已是原厂值，界面仍显示已应用配方，后续确认也没有强制完整读回。三个单元的 21 个非 04 默认配方都存在这种未覆盖位置。完整复位到标准 04、或整条已变化行原子复位的检测证明成立；材料没有给出相机复位一定按整行原子发生的证据。本项是明确的模型反例，未声称相机已发生这种部分复位。
- 证据：[gen 122](local/cases/122-50mm-partial_reset.json)、[gen 121 对照](local/cases/121-50mm-partial_reset.json)、[三单元打包数据枚举](evidence/data-audit.json)。应恢复完整核对，或先证明原生复位粒度足以支撑哨兵方案。

P1-02：H01 延迟核对后，半按可以退出而不重试；确认或 ADJ 在持续失败时也会关闭列表。

- 位置：`firmware/engine_v44_keep/candidate/containers/product/adapter.c:353`、`:574`、`:627`，以及固定机身 `firmware/resident_v36/resident/hooks.c:74`、`:96`、`:97`。关机入口 `adapter.c:688` 也没有 `retry_view()`。
- 复现：从官方 ADJ 项目切换进入 Image 列表，原生按键选中配方 05 并退出；将单元九条行与 T 复位到标准 04，在下一次 H01 注入通信失败。gen 122 发布八行，光标、小圆点均为 5，内部 `retry=1`，没有警告或锁定。恢复通信后立即输入原始半按键 `0x0d`，由原生转换得到逻辑 `0x29` 并走原生任务分派。
- 结果：半按确实经过固定机身 H07，但此时 `0x205a280f=0`，`owned()` 拒绝调用 DAT，落到 `h07_close`。`ig_event` 等 DAT 入口调用数为 0，半按 RPC=0；叠层从 32 变为 0，单元仍匹配标准 04、配方 05 核对失败。通信已经恢复也不能补救这个分支。独立直接调用原生半按处理器得到相同结果。
- 另一个退出分支：持续通信失败时按确认或 ADJ，`retry_view()` 只尝试一次读取后失败；DAT 虽返回 CONSUMED，固定机身的 H07 keep=0 收尾仍撤回为七行、关闭叠层，单元没有恢复。
- 影响：用户刚看见配方 05 的已应用状态，就能退出到拍摄流程而未核对或恢复单元。H01 的延后核对不能建立“拍摄前必经一次成功核对”的约束。这里验证到原生半按退出前缀；没有执行实体曝光或声称照片已验收。
- 证据：[完整原生 ADJ/原始半按与 H07 记录](local/official-half-with-hooks.json)、[通信已恢复的直接半按分支](local/cases/122-50mm-deferred_half_recovered.json)、[持续失败确认](local/cases/122-50mm-deferred_confirm_busy.json)、[持续失败 ADJ](local/cases/122-50mm-deferred_adj_busy.json)。在固定机身不变的约束下，未核对的 H01 不能继续显示为“配方已应用”；仅在 H06/H07/H08 加重试不足以覆盖该退出路径。

P2：未发现新增计算类缺陷。未重做既有色彩计算的全域等价证明；不把本轮抽查扩展为该证明。

## 对八项问题的答复

### 1. 通信范围与写入路径

新增 X/V 地址由已验证 GXMP 的 `M+32+12j` 行描述与 T 页/索引产生。每次 V 是协议半字 2 B；九条逻辑行长度依次为 62、33、96、56、62、33、66、62、33 B，总计 503 B，另有 T。三个单元的映射、全部配方记录、metadata 和有效行均与 gen 121 相同。

哨兵使用 `base+offset`，编译码先检查 `offset+2<=bytes`，且地址对齐，读取完全在行内。完整读取仍保留 gen 121 的半字扩边，奇地址行会读到前邻字节，偶地址的 33 B 行会读到后邻字节，比较时忽略行外字节。既有 B5 邻字节入口 `M+24` 在三个单元均等于第二条映射行最后一个逻辑字节的地址。故地址来源闭合，物理访问并非严格仅限逻辑行。

新增代码没有直接发送 W，也没有新文件写入入口。重试、settings 差异修复及补偿仍调用已存在的 `apply_impl()` / `deep()`；`rpc`、`t_read`、`t_store`、`write_word`、`deep`、`apply_impl`、`recover_confirmed`、`settings_match` 与 `compute` 九个源函数逐字相同。本轮实际 W 的行边界和邻字节保留检查均通过。证据见 [静态绑定](evidence/static-audit.json)、[编译读回 103 例](evidence/machine-read.json) 和 `local/safety/` 的逐例 `rpc_audit`。

### 2. H01 先发布、后核对

| 后续路径 | 本轮结果 | 拍摄前核对是否已有保证 |
| --- | --- | --- |
| 方向键 H08，通信恢复 | 先完整恢复 05，再应用目标 06，1032 次事件 RPC，W=459 | 此已执行入口通过。 |
| DISP H06，通信恢复 | 先恢复 05，再打开十一行面板，805 次事件 RPC，W=253 | 此已执行入口通过。 |
| 确认 H07，通信恢复 | 先恢复 05，再确认并关闭，805 次事件 RPC，W=253 | 此已执行入口通过。 |
| 确认或 ADJ H07，通信持续失败 | 一次失败 RPC 后固定机身关闭，单元仍是标准 04 | 不成立，见 P1-02。 |
| 原始半按退出，通信已恢复 | H07 归属检查挡在 DAT 之前，RPC=0 | 不成立，见 P1-02。 |
| 切模式 | 源码只有后续 rebind 发现 mode epoch 变化时强制完整核对；没有覆盖模式切换前的统一拦截 | 未做原生模式切换验收，不能给出保证。 |
| 关机 | 已注册 shutdown/abort 指向 `ig_stop()`；该函数没有重试，列表路径只关闭菜单及工作区 | 未做原生关机验收；这个入口本身不核对。下次开机重新加载不能替代关机前约束。 |

“ready=0”必须区分两个状态。报告 §1 的暖会话测试把单元通信 ready 置 0，`rv_unit()` 失败后 `ig_menu()` 转入 `deferred_menu()`，再调用 `eng_menu_deferred()` / `menu_list()` / `list_bind(1)`；已经初始化的 `g.ready` 仍是 1。本轮实际读数为单元 ready=0、引擎 ready=1，八行及 retry=1，恢复后方向键重试通过。因此该暖会话发布路径正确。若指引擎自己的 `g.ready=0`，`eng_visible_rows()` 返回 0，或 `eng_menu_deferred()` 返回 STALE，不会从该路径发布八行。冷启动时单元未就绪还会在固定 loader 处停止，DAT 尚未运行。

### 3. W 前失败保留视图

列表和面板各连续三次 W 前通信失败，均保持原行数，光标、小圆点、原生行缓存回到最后核对成功的位置；W 不增加，`failed=0`。恢复通信后的下一次方向键先核对，再正确应用配方 06 或面板对比度 +1，retry 清零。初始未提交时回到标准 04、内部 applied=0 的源码分支也正确。

`retry_view()` 每个入口至多调用一次，没有自动无限重试；跨多次用户操作没有累计次数上限。每次内部导航最多 16 轮，补偿至多四次确认配方加两次标准 04。W 后实际发送失败且全部补偿失败时，`record_failure()` 仍按 `uncertain && write_started` 锁定；本轮实测重开为一行 ERR，之后方向键和 DISP 不再发送 RPC。该锁定规则与 gen 121 相同。确认/ADJ 持续失败仍会关闭的限制见 P1-02，不能把方向键的保留结果扩展到所有退出入口。

证据见 [八项原生边界抽查](evidence/safety-50mm.json) 及其 `local/safety/50mm-list_rollback.json`、`50mm-panel_rollback.json`、`50mm-write_latch.json`。

### 4. 哨兵重开

编译码独立执行确认正常哨兵路径为 20 次 X/V；完整读取在 50mm 为 265 次、28mm/MOUNT 为 264 次。数字只计已展开的 RPC，不是相机耗时。T 在每次实际 read_live 中读取；原生 settings 在读取成功且没有行差异时由 `settings_match()` 检查，有行差异时恢复流程也核对并应用 settings。本轮改动 WB 原生设置后重开，20 次 X/V、W=0，设置恢复正确。

完整标准 04 复位、或已变化整行原子复位能检出。标准 04 和共享行在“复位目标恰为同一标准 04”时没有变化，不需要为这次复位重写；这一论证只在该条件内成立。任意行内部分复位、复位到其他原生配置、或没有原子粒度保证时，一条哨兵不能代表整行，见 P1-01。不能把这项条件性证明写成部分复位不会漏检。

### 5. H01 视图切换与 IRQ

改动的 `services.c:189` 检查逻辑正确。最终编译码在 ELF `0x3274` 保存/关闭 IRQ，`0x3284` 核对 activity=8，`0x3294` 核对 state=56；失配在 `0x329c` 取回保存的 PSW，经 `0x2df8` 恢复 IRQ，再返回 STALE。成功路径 `0x3438`、seed 失败路径 `0x348c` 也恢复。新检查本身没有循环；分配在临界区之前，后续复制使用已有行数和长度上限。

分别在 H01 的 RPC 切点用第二个原生任务切到 activity=7，以及用原生状态函数切到 state=55，均正常返回，DAT 对原生 UI 的后续写入为零，保存/恢复参数逐对相等。固定机身后续仍有 26 条原生 UI 写入，其他菜单光标会变化；这属于固定续程边界，不能把 DAT 零写入写成整个界面不变。此处没有发现新增卡住路径；未测真实 RTOS 中断时长。

### 6. 改动函数的编译码

重新生成 gen 121→122 的五文件 patch，与材料逐字相同。30 个构建源文件及工具摘要均匹配，DAT 内 53,828 B 引擎段、engine.bin 与 ELF `.engine` 字节相同。29 个新增或改动 C 函数覆盖 21 个编译函数区间，内联函数逐项映射到实际载体。`rv_call` 中两处跳转表共 27 项均核对目标，三个 objdump `unknown` 位于表数据，没有未分类可执行字节。

| 类别 | 结论与证据 |
| --- | --- |
| 地址和长度 | 新读回生成器按三单元映射执行 103 例，覆盖哨兵全部通信失败切点、完整读取页转换及首尾失败；协议序列、长度、关闭事务与返回值均符合预期。哨兵选择器另执行 852 例，含全部默认配方及奇偶地址单字节边缘差异，返回偏移均在行内。 |
| 文件操作 | 改动没有新增 storage 调用。实际初始化能力为 `0xe7fff`，不含文件写位；最终重定位 dispatcher 的 create/rename/delete/mark 返回 -12，对只读句柄 write 返回 -10，只读 open/close 正常。全部本轮原生案例 create/write/rename/delete/write_open 均为 0。 |
| 原生界面写入 | 光标回退仍经既有列表/面板服务；编译码中的自有字段偏移与布局一致。新增发布检查在原生写入前且在 IRQ 临界区内。两个原生切换反例均无 DAT 迟到写入。 |
| 循环与内存 | 核对九行、每行最多 96 B；哨兵扫描最多 48 个半字。两处导航编译计数器均为 16，补偿 4+2；新增 retry 无循环。有效行最大 `offset+length=551<=552`。Shadow 的 8 字符加 NUL 正好落在 9 B 文本槽，字形容量仍足够。编译 stack-usage 都是静态帧，最大单帧 172 B；这不等于完整 RTOS 栈的实机高水位。 |

四类增量安全边界在本轮静态审查及上述定向执行范围内闭合。P1-01/P1-02 是该编译码实际执行出的行为缺陷，仍阻止放行。未声称整个程序全域翻译等价或相机调度验收。细目见 [编译码边界记录](evidence/codegen-safety.json)，原始反汇编全部放在 `local/compiled/`。

### 7. harness 是否手工预置原生界面

搜索确实找到 `tools/native_harness/scenarios.py:310` 直接调用 `put(0x2022f71c,5,1)`，位于明确标注的 `negative_hand_type()`，用于重现旧代手工设 type=5 的假通过。副本 `firmware/engine_v44_keep/native_harness/scenarios.py:310` 也有同一负例；host C 的 `resident/v3_checks.c:91` 则是独立 host fixture。不能笼统说仓库不存在手工赋值。

gen 122 被抽查的正向原生路径没有调用这些负例，也移除了固定返回的 Image mode getter。它们通过官方构造函数、原生按键处理器建立 UI；本轮完整半按例另外执行原始消息转换和任务分派，ADJ 项目由 1 经原生函数变为 2。本轮记录的 native UI host writes 都为 0。单元行复位、busy、WB 设置输入是明确的设备模型条件；编译 selector/read_live 的单元 fixture 只设置引擎内存，文件门禁 fixture 只补服务 inflight 所有权，都没有手工制造原生 UI。这些边界测试不冒充完整相机开机或拍摄。

搜索结果见 [原生 UI 源码搜索](evidence/native-ui-source-search.txt)，完整原生入口见 `local/official-half-with-hooks.json`。

### 8. 相对 gen 121 的现场风险

新增的部分复位漏检已用相同 50mm 模型在 gen 121/122 做对照，属于确认的回退。新增的延迟发布让尚未恢复的配方以已应用状态出现，半按或持续失败退出可以绕过成功核对，属于新增的误导状态。二者均未在相机上操作复现。

仅替换 DAT 仍无法改变固定 resident 在 inflight/RF_BUSY/rv_check 提前结束 H01 的路径。没有现场读数能判定 gen 121“拍后首次七行、切换项目再回来八行”到底来自哪条分支，所以本轮不能宣称 gen 122 已修复现场根因。用户提供的 gen 121 预览、DISP、照片配方生效事实作为输入保留，没有用主机模型替代 gen 122 实机验收。

## 输入、范围与完整性

- 对象 DAT 为 63,380 B，SHA256 `9724268c3d8a2c8c60650b903db1d536ca6ab594f95144d5991cb3b964ebb262`。
- 基线 DAT SHA256 为 `3b9342ee28c523d7737e320abac1cc37ee3e6c6d122a72d5fe90cd2a3f2ee131`；候选 ELF 为 `1eff4bf291a73dd43227be107277b627aa4dea1fc8ecf8361affb72c3c2a065d`；机身为 `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008`。
- 独立原生抽查使用 50mm；三单元打包数据、selector 和 read_live 编译码均检查。没有重跑整套，也没有把另一位执行者的 r2 结果记作本轮执行。
- 现有 `record-safety.json` 的 FAIL 原样保留。其三处 current-page 错误对应缺少 page 的故障摘要；本轮单列完整 RPC 范围检查通过，不将原 FAIL 改写成 PASS。实现者其余 PASS/INCOMPLETE 只作为待核对材料。
- 290 个冻结输入在结束时摘要不变。只写 `research/review_g122/`，没有相机、存储卡或网络访问，没有启动子代理。原始固件字节、反汇编与含原始值的模型记录均在 `local/`。详见 [完整性记录](integrity.json)。
- [SHA256SUMS](SHA256SUMS) 中路径以仓库根为基准，覆盖冻结输入及本轮全部交付文件，排除清单自身。

## 实际运行的命令

以下列出取证与验收命令。逐次 Python 调用另保存在 [commands.jsonl](commands.jsonl)，反汇编子命令由脚本固定为仓库内的 M32R 工具；没有执行构建、打包或设备命令。

```sh
diskutil info /Volumes/Workspace
shasum -a 256 firmware/package_v36_g122/SD_ROOT/GXRCE.DAT
stat -f '%z %N' firmware/package_v36_g122/SD_ROOT/GXRCE.DAT
git status --short
cat research/g122_keep_list/source-change.patch
nl -ba research/g122_keep_list/REPORT.md
rg -n '2022[fF]71[cC]' research/g122_keep_list firmware/engine_v44_keep/native_binding.py tools/native_harness/harness.py tools/native_harness/scenarios.py -g '*.py' -g '!**/r2/**' -g '!**/local/**'
/usr/bin/python3 -I -B research/review_g122/freeze.py
/usr/bin/python3 -I -B research/review_g122/static_audit.py
/usr/bin/python3 -I -B research/review_g122/run_cases.py partial_reset
/usr/bin/python3 -I -B research/review_g122/run_cases.py partial_reset --generation 121
/usr/bin/python3 -I -B research/review_g122/run_cases.py suite
/usr/bin/python3 -I -B research/review_g122/machine_sentinel.py
/usr/bin/python3 -I -B research/review_g122/machine_read.py
/usr/bin/python3 -I -B research/review_g122/safety_cases.py
/usr/bin/python3 -I -B research/review_g122/data_audit.py
/usr/bin/python3 -I -B research/review_g122/codegen_safety.py
/usr/bin/python3 -I -B research/review_g122/official_half.py
/usr/bin/python3 -I -B research/review_g122/official_half.py --hook-trace
/usr/bin/python3 -I -B research/review_g122/finalize.py
/usr/bin/shasum -a 256 -c research/review_g122/SHA256SUMS
```
'''
(OUT/'REVIEW.md').write_text(report)

# All paths in the manifest are relative to the repository root.
paths={ROOT/name for name in before}
paths.update(p for p in OUT.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
manifest=''.join(file_sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(paths))
(OUT/'SHA256SUMS').write_text(manifest)
command=['/usr/bin/shasum','-a','256','-c','research/review_g122/SHA256SUMS']
result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
assert result.returncode==0,result.stderr+result.stdout[-2000:]
assert len(result.stdout.splitlines())==len(paths)
print(json.dumps(dict(verdict=summary['verdict'],P1=2,protected_files=len(before),
                     manifest_files=len(paths),all_checksums_ok=True,
                     manifest_sha256=file_sha(OUT/'SHA256SUMS')),ensure_ascii=False))
