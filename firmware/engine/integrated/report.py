#!/usr/bin/env python3
"""Write the Chinese evidence report from measured final artifacts."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE, ROOT, LOCAL, guard

def main():
    guard();audit=json.loads((LOCAL/'audit.json').read_text())
    base,huzi=audit['artifacts'];code=base['engine_bytes'];over=code-40960
    table='\n'.join(f'| {r["variant"]} | {r["build"]} | {r["file_bytes"]:,} | {r["engine_bytes"]:,} | 8 | {r["bss_bytes"]:,} | {r["image_bss_bytes"]:,} |' for r in audit['artifacts'])
    components='\n'.join(f'| {k} | {v:,} |' for k,v in audit['non_lto_components'].items())
    functions='\n'.join(f'| `{r["name"]}` | {r["bytes"]:,} |' for r in audit['lto_largest_functions'][:8])
    text=f'''三部分已合成一个真实的 M32R PIC 引擎，两份容器通过完整 C 校验，51 项主机验收通过。40 KiB 代码目标未达标：最终代码 {code:,} B，超过目标 {over:,} B，距 48 KiB 硬上限只剩 {49152-code:,} B。这是本任务的明确未达项，不能把本结果称为“40 KiB 压缩完成”。

所有新文件都在 `firmware/engine/integrated/`。未修改上游 core、panel、resident_slim、card_container_v2；未访问相机或存储卡，未生成机身映像、固件更新包，未 commit 或 push。候选只在本目录 `local/`。

已核实的构建与容器结果如下。数字单位均为 B。

| 候选 | build | 文件 | 代码段 | 重定位段 | BSS | 文件+BSS |
|---|---:|---:|---:|---:|---:|---:|
{table}

两份都符合 65,536 / 49,152 / 81,920 B 的文件、代码、文件+BSS 硬门。基础版的数据段合计 7,048 B，胡子版为 7,448 B，均另计 256 B 头。打包按各自最终数据长度重新链接，不能交换两份的 engine 段。最终布局、九个入口偏移和完整源/工具哈希见各候选 `layout.json`。

- 基础版的 50mm 01–06 来自 SHA256 `44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05` 的 DEEPTBL；50mm 07/08、09–16 与 28mm、Mount 的槽均引用各自原厂 stock。
- 胡子版只替换 50mm 07/08，使用 INDEX 指定的 Panasonic S1RII 基底、70%、safe 的 Leica Chrome / Leica VIVID。短名为 `07 Chrome`、`08 Vivid`。打包器核对源 entry 的 SHA、49 B 模板身份及旧 CRC，再重绑槽号、名称、49 B 身份 CRC 和各层容器 CRC。详细身份与来源放在胡子版 `manifest.json`，未把 05 模板身份直接搬到 07/08。
- `GXRCE.DAT` 的 HOST_ONLY 标记为零，engine 是实际链接段，入口在该段内；不是 HOSTSTUB。三单元的完整 C gate 和 semantic 均通过，不使用 `--host-only`。
- 实际重定位仅 1 个内部 BE32 cell。链接脚本拒绝未知重定位、未定义符号和超限。零基址与 `0x21004000` 平移重链后，除该 cell 的基址差异外，整段逐字节相同。主机 loader 也执行了真实的重定位及 BSS 清零路径。
- 相机运行代码未链接 SHA-256。semantic、GXTS 的旧 32 B 摘要宽度统一存 `BE32(CRC32) + 28 个零`。模块 map+stock pin 为 `df2bcaf5 / 6700e6ff / 1b3c7000`。`memcpy`、`memset` 各仅一个符号；core、panel 和服务共用内存函数，CRC 更新共用 `gxr2_crc_add`。

合链包含 core 事务与完整语义、R2 整数算法、panel UI、GXTS A/B 存储、engine_services、native bridge、安装与入口适配。`build.py:sources()` 是实际编译清单。快照中旧的 `eng_entries.c` / `panel_unlinked`、`sha256.c`、各模块独立测试并未进入交付链接。

不用 LTO 时，严格链接因 48 KiB 上限而失败；它的实际 map 测得代码 {audit['non_lto_engine_bytes']:,} B。下表只给出这次非 LTO 诊断 map 的组成，重叠的可合并字符串只计一次，归首个 map 对象。LTO 将函数跨模块内联，不能把下表冒充最终各模块独立大小。LTO 最终减去 {audit['non_lto_engine_bytes']-code:,} B。

| 非 LTO map 组成 | 字节 |
|---|---:|
{components}

其中 `core` 包含其 `eng_semantic.c` 包装编译的完整语义和 CRC 绑定；`container_gate_semantics_GXTS` 这一分组实际包含 gate、公共行/CRC、GXTS 编解码及 I/O。最终 LTO 的大函数如下，只是具名函数大小，不能据此反算被内联代码的源文件归属。

| 最终函数 | 字节 |
|---|---:|
{functions}

试过 `-Oz`、单 LTO 分区、小函数内联限制、关闭部分 IPA，以及显式共享内存叶函数。它们未达到 40 KiB，有的反而增大。最终沿用上游 GCC 13.4.0 的 M32R、medium、无 sdata、PIC、`-Os -flto` 与 `--gc-sections`。失败链接与初次错误保存在 `local/failures/`。当前两份小数据容器能装下，但 25,216 B 最坏数据底座加当前引擎至少为 {25216+code+8:,} B，超过 64 KiB，不能声称已支持三单元所有槽独立满配。

已核实的接口闭合如下。

1. `ig_bootstrap` 接收 resident 的 120 B `RvPrivateContext` ingress，通过 engine 内 `rv_services_init` 取得服务表，再向 context 指定的 40 B entries 输出九个真实入口。init 和各入口都使用同一 context、nonce、lease 与代次；不再把 ingress 当作 core 的旧 40/44 B wire。
2. 最新 resident 按 header 的实际文件+BSS 大小分配主 lease。任务副本已同步这四处变化，原样输入及 SHA 见 `local/upstream-refresh/` 和 `local/upstream-refresh.json`。服务用实际 image span 定位 state/UI 区；主机验证主 lease 长度等于 `rv_block_bytes`，安装用的两个 64 KiB 临时 lease 均释放。
3. relocated 私有 gate 只跳过 resident 已在重定位前核对的整文件 payload CRC，继续验证头 CRC、全部内层边界、三单元 pin 和每个已重定位 cell；随后才进完整 semantic。修过“只构造 view 就调用 semantic”的不安全接法，带有效外层 CRC 的坏目录/坏 GXTM 均被拒绝，未越界。
4. core 的服务调用经 init 保存的 `RvApi`。适配层把 RPC begin 返回的令牌带到后续调用；X/V/W 的 u16 参数仍在 `args[8]`。S release 不夹带无效参数。服务允许按当前 selector 审核只含变动字节的 S plan；写 selector 时仍要求它在最后。
5. 服务以 W 的原生回读值与请求值一致为成功条件；不一致保持 uncertain。成功回读后的 release 才清 resident 的 uncertain。主机模拟了这项 native W 语义，未把它当成新的机上证据。
6. STORAGE 文件上限统一为 64 KiB，GXTS 仍为 256 B 对象上限。回复携带 I/O epoch；op 9 在服务表显式登记；init 成功后 loader 才授予 FILE_WRITE。I/O 代次作废后，仅允许匹配旧令牌的 CLOSE 释放一次句柄，不能再读写。
7. `ps_install` 比较 IROM A/B，写 TMP，完整语义与逐字节回读，改名后复核正式副本；`ig_storage_mark` 再比较当前 DAT 与正式 IROM 的全部字节、原接受文件 CRC 和 16 B SD ID，最后 DAT→OK。失败不删旧正式副本；改名失败保留 DAT。
8. core 1–16 的槽号在列表边界转为原生 0–15。panel 使用真实 core、真实 GXTS codec 和 service dispatch。所有 WB 微调范围置零，两行显示 `Warm off` / `Tint off`，按键不产生写入，直接传入任一非零 WB 微调也被 core 拒绝。
9. IROM 格式化通知只作废代次；下次安全菜单先按私有 stock 恢复七行和 T，撤掉扩展列表，再 fence 当前引擎。重启且无 DAT/IROM 后回原厂。这里没有声称在通知回调中做 RPC 或立即释放在途代码。

已核实的主机验收为 6 次完整 C 校验加 45 个端到端场景，共 51 项，全部用 ASan/UBSan。测试运行的是本任务修改后的 resident loader C、完整引擎 C、原生内存/文件/RPC 模拟层；没有用假 core 或假 service 替换被测代码。测试结果逐例保存在 `local/acceptance.json` 和 `local/logs/e2e-*.log`。

| 场景 | 三个单元的断言 |
|---|---|
| `flow` | 首次菜单从 DAT 加载；init 无 W/文件写；安装 IROM、DAT→OK；重启从 IROM 读；选 06 后回 stock；微调预览、确认保存、取消、Default；重启恢复保存值；槽 16；新版 DAT 替换；选 07/08；格式化后安全菜单恢复原厂及重启回退。 |
| `badcrc` / `truncated` / `readfail` | 卡候选坏 CRC、提前 EOF、读失败时回退有效 IROM，无配方或文件写入。正常读写本身也使用短分块。 |
| `bad-layout` / `bad-tweak` | 外层 CRC 有效、内层目录/GXTM 越界时拒绝 init，无 W、UI 发布或持久写入，ASan/UBSan 无越界。 |
| `image-limit` | 文件+BSS 超 80 KiB 一字节时在 header 门拒绝，未分配主 lease。 |
| `rename-install` | TMP→IROM 失败时旧正式副本仍完整，DAT 保留。 |
| `rename-mark` | DAT→OK 失败时 IROM 已完整，DAT 保留且未假报 delivered。 |
| `alloc-main` / `alloc-work` | 主分配或第二个安装临时 lease 分配失败，均未持久写入；临时资源按已取得的所有权释放。 |
| `notify-load` / `notify-write` | 加载中 heap 作废，或文件写入后 I/O 作废，禁止继续安装/改名，句柄不遗留。 |
| `notify-rpc` / `notify-panel` | W 中 unit 作废只执行到注入点，进入 uncertain；面板预览后 S 作废禁止回放旧 draft，标为 UNKNOWN，无额外 W。 |

`effective-rows.bin` 由 Python 直接从打包模型的原始 448 B entry 和 mask 生成。主机比较 01、06、07、08 及 stock 的七行和 T，未调用 core 的展开函数生成这些期望字节。51 是场景数，日志里几十万次内存/令牌断言不是新增场景。macOS 不支持 LeakSanitizer，因此只开 ASan/UBSan；另核对文件句柄收支、主 lease 边界和成功安装后临时分配的释放。

推断：现有 M32R PIC 段、冻结 wire ABI、官方 1.51 的静态 seed 形状与这些主机结果支持继续做 resident 整合。静态抽查确认 type-5 seed 的 32 B state、72 B descriptor 表及原七项计数，证据在 `local/native-seed-reference.json`。它不证明相机上的绘制、按键、颜色或生命周期安全。

未知和限制：尚未运行 M32R 指令或相机。native 缺失文件返回值到 `RV_UNAVAILABLE` 的映射未得到机上证据，本任务主机适配把 `-2` 定义为 NOT_FOUND，其余负值仍是 I/O 错误。实际 IROM rename/旧代次 CLOSE、W 回读与预览、物理按键 phase、sleep/heap/reset，以及 WB 两轴方向均未在相机验收。新版 DAT 升级测试以重启后的首次菜单为触发，同会话热替换未验证。root 尚未授予 core 独立 32 B grain 发布区，本次候选无 grain mask，保持 grain 发布关闭。胡子 safe 仍是研究条目，不代表已经验证成像。40 KiB 体积目标仍未达到。

常驻层尚需合入的建议如下。本任务只改其副本，未修改 `firmware/resident_slim/`。

1. 在 READY 发布的能力掩码中允许 init 成功返回的 `CAP_FILE_WRITE`。当前上游 loader 仍会滤掉这一位，现有 DAT 不能与它直接组成已闭合的安装交付。
2. 初始化所有 epoch 为非零，避免首次 STORAGE query 或 UI view token 因零代次被适配层拒绝。建议见副本 `resident.c`。
3. 将服务副本的 STORAGE op 9、64 KiB 策略、SD ID/回读检查、S 部分计划、RPC 令牌/uncertain、字符串终止符和 CLOSE 清理路径合回 engine_services。`local/source-differences.patch` 给出相对于当前上游的准确差异，不是自动应用指令。
4. 保持新按实际大小分配的主 lease、120 B ingress 与状态区定位合同。本任务已用该版本验证；后续改 session/state 布局必须同步 engine 服务副本。不要恢复固定 80 KiB 偏移。
5. 将格式化后的安全菜单 fence 接入原生失败/回放分支，待在途调用结束再退休代码 lease；本任务主机验证恢复 stock 后 fence，未验证相机上的安全释放。H10 的物理 phase 到 PRESS/RELEASE/REPEAT 仍需探针或现有机上证据。WB 方向未明前继续保持 off。
6. 合回任何 resident 改动后重新生成真实 resident build/ABI 身份，再重打本地容器。当前候选的身份来自本次捕获的上游 `local/trust.c`，主机 loader 使用同一捕获值；它不是本任务修改后 resident 的可部署身份。
7. 继续压缩至少 {over:,} B 才能满足 40 KiB；优先检查上述大函数和重复的绑定/存储验收调用。不能靠提高 64/48/80 KiB 硬门掩盖未达标。

产出文件：

- `build.py`、`engine.ld`、`adapter.c`、`integrated.h`、`memory.*`、`mark.c`、`native_seed.c`，以及 `src/` 中有来源记录的三方副本。
- `pack.py` / `pack_v1.py` 是本任务的打包器副本，`candidates.py` 核对输入并按最终数据长度合链。`UPSTREAM.json` 保存初始源哈希，后续分配合同刷新单独留档。
- `host_checks.c` / `verify.py` 提供完整 C 校验和 sanitizer 测试；`audit.py` / `report.py` / `checksums.py` 生成审计、报告与 SHA256SUMS。
- `local/candidates/base/GXRCE.DAT`、`local/candidates/huzi/GXRCE.DAT` 及各自的 `trust.bin`、`manifest.json`、`layout.json`、engine/reloc 段、展开条目和独立期望。
- `local/m32r-lto/engine.elf`、map、重定位审计；`local/audit.json`、`local/inputs.json`、`local/acceptance.json`、`local/source-differences.*`、`local/commands.jsonl`、原始失败日志。
- `REPORT.md` 和全任务 `SHA256SUMS`。本报告与所有本地候选、测试证据均纳入清单。

两份容器的 SHA-256：

```text
{base['sha256']}  local/candidates/base/GXRCE.DAT
{huzi['sha256']}  local/candidates/huzi/GXRCE.DAT
```

复核命令，从仓库根执行：

```sh
cd {ROOT}
git check-ignore -v firmware/engine/integrated/local/candidates/base/GXRCE.DAT
python3 -I -B firmware/engine/integrated/checksums.py --check
python3 -I -B firmware/engine/integrated/verify.py
```

如需从源重新打包，先运行下列命令，再跑 verify。重打包会读取当前捕获的 resident 身份；上游发生变化时哈希可以改变。

```sh
python3 -I -B firmware/engine/integrated/candidates.py
python3 -I -B firmware/engine/integrated/verify.py
```

`audit.py` 的组成表还依赖非 LTO 诊断 map；`build.py --data-bytes 7448 --standard` 会写该 map 并按设计因超 48 KiB 返回失败，不会生成超限容器。重新生成报告/校验清单：

```sh
python3 -I -B firmware/engine/integrated/audit.py
python3 -I -B firmware/engine/integrated/report.py
python3 -I -B firmware/engine/integrated/checksums.py
python3 -I -B firmware/engine/integrated/checksums.py --check
```
'''
    (HERE/'REPORT.md').write_text(text)
    print(f'REPORT.md: code={code}, over_40k={over}, checks={audit["checks"]}')

if __name__=='__main__':main()
