#!/usr/bin/env python3
"""Render the handoff report from measured local evidence."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import HERE,ROOT,LOCAL,guard,sha

def main():
    guard()
    std=json.loads((LOCAL/'size.json').read_text());lto=json.loads((LOCAL/'lto/size.json').read_text())
    tests=json.loads((LOCAL/'tests.json').read_text());legacy=json.loads((LOCAL/'legacy-tests.json').read_text())
    for result in (std,lto):
        for name,expected in {**result['source_hashes'],**result['upstream_hashes']}.items():
            if sha(ROOT/name)!=expected:raise RuntimeError('build source drift: '+name)
    for name,expected in tests['source_hashes'].items():
        if sha(ROOT/name)!=expected:raise RuntimeError('test source drift: '+name)
    flags=dict(core_implemented=True,host_sanitizers_pass=True,core_processes=tests['total'],
        legacy_cases=legacy['cases'],runtime_sha256=False,combined_engine_limit_bytes=32768,
        core_delivery_engine_bytes=std['engine_bytes'],core_delivery_lto_bytes=lto['engine_bytes'],
        core_measurement_within_limit=std['engine_bytes']<=32768 and lto['engine_bytes']<=32768,
        core_projected_container_fits=std['container_fits'] and lto['container_fits'],
        combined_engine_bytes=None,combined_engine_budget_verified=False,engine_services_linked=False,
        packaged_delivery=False,panel_linked=False,resident_live_integration=False,camera_acceptance=False)
    (LOCAL/'handoff.json').write_text(json.dumps(flags,indent=2)+'\n')
    table='\n'.join(f"| {name} | {r['engine_bytes']} | {r['bss_bytes']} | {r['projected_container_bytes']} | {32768-r['engine_bytes']} | {49152-r['projected_container_bytes']} |" for name,r in [('标准 PIC',std),('LTO PIC',lto)])
    parts=std['component_engine_bytes']
    text=f'''core 已按服务内移合同核查：所有生产服务调用均经 init 保存的 RvApi 表，不假设服务在机身里，也不直接调用原生地址。core 交付范围实测标准 M32R PIC {std['engine_bytes']:,} B、LTO PIC {lto['engine_bytes']:,} B，包含完整容器语义校验与 R2 微调，尚未链接 panel/GXTS 和 `firmware/resident_slim/engine_services`。32 KiB 是这些部分合计的代码上限，合并体积尚未验证。

按已验证的 48 套独立配方数据上界链接，当前投影文件尺寸分别为 {std['projected_container_bytes']:,} B 和 {lto['projected_container_bytes']:,} B。48 KiB 文件门给其余代码和 relocation 留下 {49152-std['projected_container_bytes']:,} B / {49152-lto['projected_container_bytes']:,} B，比 32 KiB 代码门的余量更紧。最终合并链接由主任务处理。

验证对象为真实生产 C。{tests['total']} 个新核心测试进程通过 ASan、UBSan；原封不动复跑 Stage2l 的 {legacy['cases']} 项用例，也通过同样的 sanitizer。相机、存储卡、刷机、预览帧与真实 RPC 均未访问或验收。

## 已核实

- `eng_core.h` 与委派的四个 API、八位向量、49 B identity、状态枚举一致。unit=0/1/2 分别是 50mm、28mm、Mount，slot=1..16。
- 服务路径为 core 的 `EngPort.call` → 入口适配 → init 保存的 `RvApi.call`。入口测试实际由传入的 API 执行 RPC、S、预览、租约、UI 等服务；换入另一个 API 表在调用前拒绝。服务库移入引擎不改变 core 的分发方式；冻结 ABI 未修改。
- 容器直接使用上游 `gxrce.h`、`common.c` 和 `semantic.c`。已删除先前的独立最小解析器，改由 `eng_data.c` 接受 resident 的受保护 gate view，再调用上游完整语义层。没有改 `firmware/card_container_v2/`。
- `eng_semantic.c` 通过薄编译适配把 SHA 绑定调用换为 CRC32。相机目标不链接 `sha256.c`，最终 ELF 没有 SHA 实现或导入。主机来源审计和 SHA256SUMS 继续使用 SHA-256。
- READY 前按当前单元计算 CRC32(map128 || stock410)，与 `rv_unit_pin(unit)` 的独立常量比较。上游完整语义层同时核验全部三单元。旧 stock entry448 CRC 另行核验，不作为 map pin。
- init 只做语义、单元、代次、stock 和 T 读取，不写 S、W、文件或 native UI。有效非 2 的 T 留到安全菜单有界修复；失败 X/V 可重试。有效 t_checked、告警和提交历史独立于列表开关。
- 列表有 16 行稳定名称/字形租约、光标和应用状态。`!4` 只绑定经 entry CRC 约束的 canonical stock。失败选择将 core 和 native 列表 descriptor 的光标退回上一成功槽；没有历史时不显示成功 04。
- 七行写入地址从当前单元 map 取得。始终从不可变默认条目重算，未启用可选行从该单元私有 RAM stock 取得。同配方微调只写改变的行，S plan 也只含实际变化的字节。
- T1 先定位/确认旧控制值，必要时先恢复 T=2，再按 A5、B5、colour、matrix、A20、B20、C/D 顺序写。目标 T=0 最后单独 X/V/W/V；C/D 写入只在 T=2。没有 U 或 T commit 命令。
- B5 的最后低字节来自真实 B6[0] 快照；B20 的首高字节来自当次实读 B19[32]，不触及 B21。跨页 W 利用完整 cursor，重新绑定的只读审计显式切换 X 页。
- 第一次 W 尝试前置 sticky uncertain。任何 W、S patch、preview request 或 release 未能确认完整事务，保留实际阶段，不发布新 applied_slot/向量/颗粒。关页、重开、作废绑定和 abort 不清除 uncertain，不原地重发 W。
- 颗粒先撤 armed，完整提交后才向 resident 明确授予的 32 B 快照发布。独立 `eng_grain.c` 保留 category 0/4、五个 packet 零门、JPEG size、S 长度、selector/base_mode、同代次检查；只改四个指定 packet 字段。
- `eng_restore_stock` 不读卡。正常 shutdown/abort 经同一有界事务恢复 RAM stock，失败返回 RV_FAULT。uncertain 时不尝试恢复写入。重新绑定先只读核验全部 stock halfword 和 T=2，拒绝把脏重连当新 stock。
- WB 的物理 lane/sign 默认未知。native init 拒绝伪造绑定；非零 WB 编辑在无绑定时拒绝，零编辑保持 canonical 物理顺序。已绑定的主机夹具验证 ±16 逻辑范围仍限幅到 native 1..17，且不产生深层 W。

三单元两种 CRC 的关系如下，CRC 值按八位十六进制列出。

| 单元 | READY 使用的 map128+stock410 pin | Stage2l stock entry448 CRC |
|---|---|---|
| 50mm | df2bcaf5 | 0d2b0ea9 |
| 28mm | 6700e6ff | 341ddbee |
| Mount | 1b3c7000 | 4686301b |

## 主机证据

结果见 [local/tests.json](local/tests.json)、[local/legacy-tests.json](local/legacy-tests.json) 和逐项 `local/host-*.log`。

| 覆盖对象 | 实际检查 |
|---|---|
| 三单元、16 槽 | 48 次全槽应用、stock 恢复、各单元地址/stock、T=0 配方重开 UI。 |
| 微调重算 | 375 个边界组合；90 组六参数向量的全部 408 行字节与独立 Python 一致；回零恢复默认。 |
| 写入预算 | 单纯 tone 改动只写 B5 的 17 个 halfword；WB 编辑 0 次深层 W。 |
| 不确定失败 | 三单元分别在控制配方事务的 158 个 W 位置注入失败，共 474 个场景；另覆盖 8 个 X、9 个 V 位置、链路换代、S、preview、release、end 失败。 |
| T1、邻接字节 | 禁用 T 后写行、最后启用、C/D 写入门、B5 跨页、B6/B19/B21 的非 stock 哨兵。 |
| 颗粒 | 每单元 120 个 category/size 组合，逐项 packet 门、S 长度、selector、epoch 和失效快照；拒绝时 packet 全部不动，WB/style 保持。 |
| 身份与元数据 | 49 个 identity 字节逐一变化；错误 unit/slot；重排 param_id、非零 Default、两保留位；短 S；纯 init/rebind/native 回调重入。 |
| CRC 与尺寸 | 独立 pin 错误、非 CRC tag、stock identity 改动导致旧 entry CRC 不符、stock 范围不含零均在 T/S/W 前拒绝。24,576 B、32,768 B engine 形状和 41,600 B 容器通过 core 语义；32,772 B engine 拒绝。旧上游 gate 仍按旧门拒绝。 |
| 解析层 | 全部短头、未知参数 ID、带重封 CRC 的 bank/table 变异，经真实 gate/完整语义分层处理；host fixture 使用上游 GXDP/GXDT v5 格式。 |
| 原 Stage2l | 只读编译原生产源码与原测试，复跑 {legacy['cases']} 项；所有新二进制、日志都写入本任务 local/。 |

ASan 与 UBSan 同时启用，`-fno-sanitize-recover=all`。Darwin 不支持 LeakSanitizer，因此 `detect_leaks=0`；最初不支持时的原始失败和后续失败日志保留在 `local/failures/`。本报告没有声称内存泄漏检测通过。

压力夹具的 48 个槽均占用，但部分行刻意复用，以验证槽、事务和差分；它不是三单元色彩校准。最坏行数据夹具直接复用 container worker 已验证的 25,216 B 构造，本任务只在 local/ 改为 CRC tag 和惰性测试头，没有生成可安装文件。

## M32R 体积与重定位

| 构建 | core 交付 engine B | BSS B | 最坏数据投影文件 B | 32 KiB 代码余量 B | 48 KiB 文件余量 B |
|---|---:|---:|---:|---:|---:|
{table}

标准 PIC 的实际链接 map 分项：core 自有对象 {parts['core']:,} B，容器完整语义/CRC/common {parts['container_semantic_crc']:,} B，R2 微调 {parts['recipe_tweak']:,} B，链接对齐/保留区 {parts['link_padding']:,} B，合计 {std['engine_bytes']:,} B。这是已进入最终 engine 段的贡献，剔除了被回收的函数。LTO 跨文件内联，只报告合计，不按源文件虚分。

这里的数据底座为 25,216 B，含 256 B 头；`--data-bytes=24960` 不含头。因此最坏数据条件下，总 engine 加 relocation 实际最多为 23,936 B，仍须同时遵守 32 KiB 代码门。UI 另租 1,920 B，不计入 engine BSS。core 的表暂存只保留 stock/live/staging 和单条展开 scratch，没有展开 48 套条目。

沿用既有 M32R GCC/ld 工具链及 `-Os -ffreestanding -m32r -mmodel=medium -msdata=none -G0`，为本任务的位置无关要求改为 `-fpic`。LTO 是可选测量，不替代标准 PIC 结果。`engine.ld` 严格限制 32 KiB 总 engine、48 KiB file、4 KiB BSS。当前测量没有服务库和 panel，不能据此宣布合并预算通过。

两个构建都无未解析符号，runtime relocation={std['relocations']}。GOTPC/GOTOFF 和内部相对分支由静态链接解析；将相同对象整体平移到 0x21004000 后，engine 字节完全一致。bootstrap/所有入口均检查 4 B 对齐和完整落在 engine；GOT 不允许漏记指针。静态 ELF 的保留 relocation 只作审计，不是容器 relocation。

BSS 的 GOTOFF 常量依赖最终文件长度。实际打包按最终数据大小重链，不能把本次最坏数据预算的 engine 直接放进另一个长度的容器。这里只交 engine 段、空 relocation 段和测量 ELF，没有交 DAT、固件更新包或 SD_ROOT。

- 标准 engine SHA256：`{std['engine_sha256']}`。
- LTO engine SHA256：`{lto['engine_sha256']}`。
- 完整大小、输入及工具链 SHA、入口和 relocation 审计分别见 [local/size.json](local/size.json)、[local/lto/size.json](local/lto/size.json)、`local/relocation-audit.json`。

## 推断

核心在主机和静态 M32R 证据下，能按当前 map/数据接口支持三单元、每单元 16 槽和六参数事务。当前部分低于代码与文件门；服务内移后还要容纳服务库、panel、GXTS，合并链接后才能判断总预算是否通过。最坏数据情况下应按文件余量规划新增代码。

CRC tag 沿用原 32 B 字段宽度，仅改变含义，因此暂时不必重排目录或 GXTS 结构。它不是上游工具已经采用的新格式；当前上游原 SHA 语义实现不能直接接收本任务的 CRC tag。

## 未知及主任务集成项

1. `rv_unit_pin` 是用户指定的纯常量弱桩，不做服务调用，返回批准的三个独立常量。常量来源由常驻层负责人决定；若改为服务查询，仍须经 init 的 RvApi，不添加裸地址导入或新服务编号。`firmware/resident_slim/engine_services` 的库与 panel/GXTS 尚未参与当前链接，总体代码、BSS 和最终容器体积未知。
2. root 的 32 B `EngGrain` 位置、临界区与 H09 常驻链接由 resident_impl 确定。core 只写明确授予的地址，不抢 root.flags。实际 hook、inflight 和 code lease 生命周期尚未做硬件证明。
3. `EngInitWire` 需要受保护 `Gxr2View` 地址。旧上游 gate/packer 仍有 32768/10240 的文件/engine 硬门，且目录仍写 SHA tag。必须按补充决定统一为 49152/32768 和 CRC tag。需要 card_container_v2 配合的文件和字段见 [INTEGRATION.md](INTEGRATION.md)。
4. panel 三个入口目前是显式未链接入口，返回 RV_UNSUPPORTED/CLOSE_AND_PASS。panel、GXTS 保存事务、0x25/0x22 物理键映射尚未链接到这个核心。GXTS 的绑定也必须编译为 CRC，排除 `sha256.c`。
5. GXTM 尚无经过验证的 WB lane/sign 字段。非零 WB 的实际相机能力保持关闭；两轴方向、模式使能和视觉效果仍未知。
6. 原生 UI 字形/滚动、RPC 超时通道、preview 实际帧、模式/回放四 caller 的故障分支、任务栈与连续可执行堆租约均未上机。主机返回成功只证明请求与状态机，不证明预览帧、真实颗粒或相机接受。

## 产出与复核

| 文件 | 用途 |
|---|---|
| `eng_core.h` | 与 panel/storage 冻结的四个接口。 |
| `eng_internal.h`、`eng_core.c` | 事务、元数据、16 槽、恢复、作废和重新绑定。 |
| `eng_data.c` | Gxr2 gate view 接入、完整语义调用、展开访问器、CRC pin/entry CRC 和算法能力检查。 |
| `eng_crc_bindings.h`、`eng_crc_compat.c`、`eng_semantic.c`、`eng_pin_stub.c` | CRC 编译适配、上游语义链接和 resident pin 查询桩。 |
| `eng_entries.h/c`、`eng_grain.c`、`eng_mem.c` | 44 B init 合同、九入口、native 服务/列表适配、独立常驻颗粒门和 freestanding 内存辅助。 |
| `engine.ld`、`build.py` | 严格体积、PIC 平移、入口/符号/GOT/重定位与无 SHA 审计。 |
| `test_host.c`、`fixture.py`、`verify.py`、`legacy_verify.py` | 真实生产 C 的 sanitizer 测试和原 Stage2l 复跑。 |
| `runtime.py`、`report.py`、`checksums.py` | 外置卷/范围守卫、证据报告和 SHA256SUMS。 |
| `INTEGRATION.md` | 给 resident、panel、container worker 的接入合同和必要修改清单。 |
| `local/` | 所有提取字节、测试夹具、二进制段、ELF、反汇编、原始失败和机读证据。 |

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
python3 -I -B firmware/engine/core/verify.py
python3 -I -B firmware/engine/core/build.py
python3 -I -B firmware/engine/core/build.py --profile lto
python3 -I -B firmware/engine/core/report.py
python3 -I -B firmware/engine/core/checksums.py
python3 -I -B firmware/engine/core/checksums.py --check
git check-ignore -v firmware/engine/core/local/engine-measurement.bin
```

写入前及脚本运行时均确认 Workspace 为可写 APFS，UUID 为 14BE04EB-AF49-497E-B36A-B078B2F7C5E8。`local/` 由本任务 `.gitignore` 的 `/local/` 忽略，已用 git check-ignore -v 核实。所有新写入在 `firmware/engine/core/`；官方固件及其它 worker 目录只读，没有删除、移动或改写共享研究/制品，没有 git commit/push。
'''
    (HERE/'REPORT.md').write_text(text)
    print(f"REPORT.md: {tests['total']} core processes, {legacy['cases']} legacy cases; engine {std['engine_bytes']}/{lto['engine_bytes']} B")
if __name__=='__main__':main()
