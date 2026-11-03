不可以上测试卡

本轮尚不足以支持测试卡放行，未闭合项列在下表。结论只针对下列 DAT 与 v3.7 机身这一对文件。相机、存储卡、RTOS 调度、LCD、拍摄与持久性未实测。

| 对象 | 身份 |
| --- | --- |
| DAT | `firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT`；89,572 B；generation 135 |
| DAT SHA256 | `57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a` |
| v3.7 ilaunch3 SHA256 | `d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283` |
| 最终 ELF SHA256 | `1ca0b9ab37375ec6e7ef3c2c5609820c71ac7c6efcdf190743428b4e82bc9e99` |

静态已证：身份、CRC、DAT 与 engine.bin、源码差异、目标编译器布局。主机已证：本目录逐组回归与最终 M32R 指令模型；设备和图形叶函数仍按既有模型处理。推断及未知另列，不以主机结果替代相机验收。

## 本轮结果

| 范围 | 结果 |
| --- | --- |
| 首轮未闭合的 27 组 | 已闭合 22/27；逐组原始返回码、替代检查和未闭合项见 REGRESSIONS.md |
| users / other-users | 执行闭合 3/9；原组通过 1/9；2 组保留卡片标题差异 |
| 首轮 24 组分类 | 8 组旧显示、5 组旧入口、2 组旧读取、9 组工具前提；每组依据见 CLASSIFICATION.md |
| 实际 M32R 窗口 | uv_window 19,074 例通过，覆盖 count=1…33、所有 current、previous=0…33 |
| 计算边界 | 18,484 个非法值被拒，输出保持不变；另有 3,510 个未开放控制检查与 18 个非法 slot 检查 |
| 目标编译器布局 | 核心 28 字段、适配层 28 字段与当前记录一致；ready=4844，uncertain=4848，write_started=4859 |
| H07 独立复跑 | 完成且返回 0 0/6；均未启动，见附表 |
| v3.7 part 检查 | 完成且返回 0 0/3；均未启动；计划调用原 accept_parts.py 的 0…7 检查 |

300 例完整抽样通过：50mm、28mm、mount 各 100 例，覆盖 24 个单元配方组合。种子为 20261030135，每例比较完整 552 B，总计 165,600 B；执行 266,037,162 条目标指令。目标为最终 ELF 的 eng_project_compute，入口按各冻结快照中的实际 DAT 基址绑定；参考来自独立的原始 r2 C 源码。另核对输入向量、边界标记、保存寄存器、SP 和 DAT 不变。见 evidence/sample300.json、sample300-cases.jsonl、artifact-verification.json。

27 组中严格闭合 22 组；另三组 values 的完整内容可复核，但外层退出回执未留存，仍列为未闭合。它们各有六个子项通过，最后一个子项因旧光标期望 (1,1) 失败；逐组事件显示实际 (1,2)，与新设计的每层光标记忆一致。另两组 values 与六个用户组未启动。见 evidence/recovered-groups.json 和 evidence/interruption.json。

## 源码与三项合并

相对 gen 131，七个既有路径不同，另以 build135.py 替换 build131.py。五个 C 文件中，services.c 与 native_seed.c 扩展 part 取值，gate.c、eng_data.c、ui_v2_data.c 更新构建号。七个 kv2 文件与第七段 20,776 B 均与 gen 131 逐字节相同。实际 resident_v37 与引擎服务层协调接受 part 1、2，仍检查列表、栈、名称和活动状态；DAT 的 resident id 在配套机身中恰好出现一次。

H07 的严格归属链保留 inflight、nonce、entry_serial 和入口编号核对；只有 H01 使用构造期间规则。H07 修复与半按恢复的验证状态按上表和附表分别记账，不用其中一项代替另一项。

## 首轮判断的修正

24 组原始错误不能直接当作固件断言失败，但分类依据有一处错误：uv_levels 缺少旧入口，uv_window 仍在最终 ELF 的偏移 0x250，大小 100 B。首轮称两者都已退役不成立。本轮分别用实际集成计算边界和实际 M32R 窗口补证，不把原 project 组的 KeyError 改写为 PASS。

旧显示八组的依据分别落实到新卡片布局、十个 int16 的向量、Amount=100、实际点表及 03 的五项控件。两家族对应函数合同相同，适配未减少原断言。现有三单元菜单轨迹另按数据独立核过：314、316、316 帧，均为八行、每行最多八个 ASCII 字符，逻辑光标没有进入填充范围；这些是既有模型轨迹的复核，未计作本轮新执行。

三条旧 safety 失败采用 g129 triage 已说明的读取修正：ready 不再读 g+2523，锁存字段读当前布局，Cont=-1 的完整结果以 r2 参考计算。当前修正组与原失败分开记账。

## 用户条目

gen 135 正式源码树仍缺少可直接使用的用户条目 CLI，旧 ui_data.py 也不接受这份 DAT。复审目录新增 users_gxui.py，按路径调用既有编码和 CLI，只替换当前 DAT 的读取与条目更新。它绑定指定基线，保留 GXUI v1 的 32 条、24 B 记录及十一字节旧向量，只改用户区和相关 CRC；不改代码、配置、身份与整数块。工具已通过 32 条往返、空条目逐字节恢复、163 种无效输入、代码字节不变等检查。

用户界面的四处向量期望与一处 Default 行号按新设计重绑。50mm 的两组 users 另观察到卡片标题为 `<5 F-CC`，历史断言要求 `<FCC-001`。设计未单独说明这项用户标识变化，本轮保留为显示契约差异。标题检查记录后继续；只有其余断言全部完成且组末仍按失败退出时，才归为“标题差异已记录，其余断言完成”。具体实际状态和原始退出码均保留，不记整组 PASS。

正式交付仍需补入当前格式的 parse/replace 与 CLI 路径，保留旧条目四控制到新 1/2/3/5 的转换和全部旧保留位校验；再明确用户卡片标题契约。复审工具可用，不等于这些改动已经进入 gen 135 源码树。

## 问题表

P0：本轮未确认新的 P0。下表的“继承”不表示已经关闭。

| 级别 / 编号 | 新或继承 | 状态与依据 |
| --- | --- | --- |
| P1-01 | 继承 | OPEN。首次八行发布之前仍有原生七行窗口；真实调度可达性未定。本轮未重跑 cold_reentry，沿用既有记录。 |
| P2-03 | 继承 | OPEN。最终归属核对后、原生预览前换视图的窗口仍须保留；H07 父层修复不能关闭它。本轮单列观察组。 |
| g124/P2-01 | 继承 | OPEN。末端重绘窗口；本轮未把绘制正文相同当作重跑绘制本体。 |
| P2-04 | 继承 | 普通预览 I/O 失败后的重开刷新仍待核对；归属丢失后的 pending/read 证据不覆盖全部普通失败。 |
| g129/P2-01 | 继承 | 连续堆风险。主请求 107,760 B，需要连续块；108,124 B 预算余量 364 B，不是相机真实剩余堆。 |
| g135/P2-01 | 新，首轮已列 | 正式树的用户条目工具和解析器没有跟上 DAT；本轮只在复审目录补齐工具和验证。 |
| g135/P2-02 | 新，首轮已列 | 交付整洁：resident/ 仍为旧副本、candidate 下保留 Python 3.14 的 pyc、实现报告帧数把 28mm/mount 的 316 写成 314。实际包已核对绑定 resident_v37，旧副本未进入本次产物。 |
| g135/P2-03 | 新，首轮已列 | 旧套件的布局、偏移与显示读取需要当前适配；本轮的读取和目录转接见 WRAPPER.md。 |
| gpt/P2-01 | 新，复审说明 | 首轮关于 uv_window 已退役的解释错误；本轮已以最终符号与 19,074 例目标执行更正并补证。 |
| UI/P2-01 | 继承，本轮新观察 | 用户卡片标题改为基底配方名，历史用户编号标题断言不成立；相关 adapter/kv_ui 源码与 g131 相同。设计契约待确认，具体用户组保留非零退出码。 |
| 验收/P1-01 | 新，验证未闭合 | 下列要求组在本轮仍未闭合；不记通过。 |

## 未闭合项

- group124-28mm-values。
- group124-mount-values。
- group126-50mm-values。
- group126-28mm-values。
- group126-mount-values。
- group124-28mm-users。
- group124-mount-users。
- group126-28mm-users。
- group126-28mm-other-users。
- group126-mount-users。
- group126-mount-other-users。

## 附加组的实际状态

| 组 | 返回码 | 执行状态 | 秒 |
| --- | --- | --- | --- |
| focused-h07-parent-50mm |  | NOT_STARTED |  |
| focused-h07-parent-preview-50mm |  | NOT_STARTED |  |
| focused-h07-parent-28mm |  | NOT_STARTED |  |
| focused-h07-parent-preview-28mm |  | NOT_STARTED |  |
| focused-h07-parent-mount |  | NOT_STARTED |  |
| focused-h07-parent-preview-mount |  | NOT_STARTED |  |
| half-redisplay-50mm |  | NOT_STARTED |  |
| half-redisplay-mount |  | NOT_STARTED |  |
| observed-preview-window |  | NOT_STARTED |  |
| half-redisplay-28mm |  | NOT_STARTED |  |

## 输入与执行边界

全过程只写本目录及旧辅助层必要的 research/g135_v37/local/ 例外。未访问相机、存储卡或网络，未启动子代理。Python 为 /usr/bin/python3 -I -B；理光字节均放在被忽略的 local。一个调度器实现、最多三个工作槽、每组 4200 秒；全局时间盒 UTC 2026-10-29 23:24:12 至 2026-10-30 02:54:12。首批准备错误与同一脚本顺次再启动的记录、旧源码终端输出偏差、抽样驱动早期变量错误均如实保留，见 WRAPPER.md 和 evidence/runs.jsonl。

交互中断后调度器停止，已派发的三组 values 继续写出报告，末份结果时间为 UTC 02:16:15、02:19:50、02:20:22，均早于原截止；没有后续派发。恢复时已过原时间盒，未追加回归，仅核对既有证据并整理交付。三组原始报告保留返回码 1，但 OS 退出回执缺失，二者分开列示；当前没有残留调度器或工作进程。

收尾：首轮清单 16,140 项通过，缺失 0、变化 0；624 个受保护文件与开工一致：一致。 校验清单以仓库根为基准。

报告生成 UTC 2026-10-30T03:16:05.147442+00:00。
