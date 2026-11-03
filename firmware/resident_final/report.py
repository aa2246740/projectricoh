#!/usr/bin/env python3
"""Write the Chinese handoff from measured artifact and host-acceptance evidence."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'
def read(name):return json.loads((LOCAL/name).read_text())

def main():
    audit=read('delivery.json');size=audit['resident'];identity=audit['identity'];service=audit['service']
    resident=read('resident/host-results.json');product=read('product/acceptance.json')
    probes=read('probes/tests/summary.json');extra=read('full-validator-probes.json')
    assert len(product)==51 and sum(r['kind']=='e2e' for r in product)==45 and len(extra)==9
    rows='\n'.join('| '+r['name']+' | '+str(r['file_bytes'])+' | '+str(r['code_bytes'])+' | '+str(r['bss_bytes'])+
                   ' | '+str(r['image_bss_bytes'])+' | '+str(r['main_lease_bytes'])+' |' for r in audit['containers'])
    hashes='\n'.join(r['sha256']+'  '+r['path'] for r in audit['containers'])
    group_rows='\n'.join('| '+name+' | '+str(n)+' |' for name,n in resident['groups'].items())
    probe_rows='\n'.join('| '+name+' | '+str(v['checks'])+' | '+str(v['captures'])+' | '+str(v['writes'])+
                        ' | '+str(v['rpc_calls'])+' |' for name,v in probes['engines'].items())
    objects='\n'.join('| '+k+' | '+str(v)+' |' for k,v in size['linked_objects'].items())
    text=f'''# resident-final 常驻层与五份容器交付报告

常驻层严格链接通过，代码和只读数据 {size['payload_bytes']} B，root 256 B，总占用 {size['occupied']} B，8340 B 窗口余 {size['margin']} B。唯一服务库源码和五份容器已定稿。最终产物通过 15 次完整 C 校验、45 个产品端到端场景、三份探针检查和常驻边界检查，可以交独立审查与 image_v2 打包。

这是静态、交叉链接和主机证据。没有执行 M32R 指令，没有接触相机或存储卡，没有刷机、生成机身映像、commit 或 push。它不表示相机验收或刷机放行。

## 已核实：交付入口与身份

- 常驻 ELF：`{size['elf']}`。
- 常驻 map：`{size['map']}`。
- 给 image_v2 的 hooks：`local/hooks.json`。它与 resident_slim 的 37 行源格式完全相同，包含原字节和原生续接信息。
- 实际替换字节与启用状态：`local/patch-manifest.json`。其中 26 项启用，含 24 个代码 hook 和 H03、H04 两个原厂数据点；其余 11 项禁用。`installable=false` 保留独立审查边界。
- 身份与策略：`local/resident/trust.json`，主机链接使用的实际常量位于 `local/resident/trust.c`。
- 唯一服务源码：`engine_services/`，共用 root helper 来自 `resident/shared.c`。产品和探针均编译这些实际路径，没有服务副本。
- 服务归档：`{service['archive']}`，单独实链 {service['bytes']} B，平移重链通过。
- 文件索引、大小与哈希：`local/delivery.json`；全任务校验清单：`SHA256SUMS`。

```text
resident build ID  {identity['resident_build_id']}
resident ABI ID    {identity['resident_abi_id']}
resident ELF SHA   {size['sha256']}
service archive   {service['archive_sha256']}
```

build ID 对实际常驻与服务源码、所用头文件、链接脚本、构建脚本及 GCC、ld、objdump 的文件摘要求哈希。ABI ID 对实际 ABI、resident 和服务头文件求哈希。它们不是旧 trust、主机夹具或任意标签。`audit.py` 会重算 build ID，并核对五份最终文件中的身份。

机身只认官方 1.51 的 `ilaunch3` 摘要。三单元 map 与 stock 的 CRC pin 仍为 `df2bcaf5`、`6700e6ff`、`1b3c7000`。公开 wire 大小保持 request 64 B、reply 32 B、ingress 120 B、Session 516 B、root 256 B。

## 已核实：常驻层改动与预算

1. 纯 init 成功后，READY 掩码允许 `CAP_FILE_WRITE`。init 执行期间仍只有只读能力；失败不会发布 READY。
2. reset 把全部 12 个 epoch 设为 1，token 初值仍为 1。
3. 文件、代码、文件加 BSS 兜底分别为 98304、65536、114688 B；独立 LEASE 上限保持 65536 B。目标 GCC 生成的 `local/resident/target-layout.json` 核对了这些常量。
4. 常驻侧 `rv_session()` 在加载与重绑之外检查完整绑定代次。代次失效后，H02 等旧 UI 路径和 `rv_engine()` 不能再进入旧入口；H01 走现有 loader 重绑，再调用菜单入口。服务侧的 `es_session()` 保留 boot、heap 所有权检查，因此旧请求仍能取新快照，修改操作仍核对当前代次。
5. H01 复用 session 的代次检查，`owned()` 返回已核对的 Session，避免随后再查一次。四种 post hook 用等价编号计算替代小索引表，常驻 `rv_equal()` 改用端指针循环。没有删除 hook、校验或扩大窗口。

一级 H01 至 H12、H15 至 H22 保留。二级 H13、H14、H23、H25、H31、H32 仍只增加代次并记事件，不碰 UI、heap 或引擎。三级保持删除。每个启用代码桩的原指令重放、续接分支和新补丁目标，都与最终 ELF 逐字节或逐分支核对。

| 最终 map 对象 | B |
| --- | ---: |
{objects}
| 链接对齐 | {size['link_adjustment_bytes']} |
| payload | {size['payload_bytes']} |
| root，含 12 B pins | 256 |
| 总占用 | {size['occupied']} |
| 余量 | {size['margin']} |

root 仍在 `0x20054700`，三个只读 pin 仍在 `0x200547f4` 至 `0x200547fc`。`.root` 为 244 B NOBITS，`.root_pins` 为 12 B PROGBITS。严格链接继续断言至少 300 B 余量，常驻 ELF 无未定义符号、未处理重定位、服务入口或可写全局段。

主块分配公式保持实际大小：`6916 + align4(file_bytes + bss_bytes)`。96 KiB 文件与 16 KiB BSS 实际请求 121604 B，多 1 B BSS 被拒；文件多 1 B 在申请主块前被拒。64 KiB 代码实际加载通过，再多 4 B 被 gate 拒绝。独立 65536 B LEASE 仍可申请，65537 B 在原生分配前被拒。

## 已核实：统一服务与格式化处理

服务以 integrated 的副本为准，保留其 STORAGE op 9 和描述表、64 KiB 引擎文件服务策略、256 B GXTS 策略、SD ID 核对、完整回读与 DAT 改名确认、S 部分计划、RPC 令牌、W 回读与 uncertain、路径终止符，以及旧 I/O 代次只准 CLOSE 一次的清理。

probes_int 所需的 inspect 目标放在 `args[8]`，输出 lease 仍在 `args[1]`；成功 snapshot 带准确 `reply.actual`；达到 64 KiB 后允许一字节 EOF 探测；观察接口允许刷新代次。这些行为由常驻的针对性检查和三份真实探针 C 入口共同复核。

为脱离产品内部头文件，API 使用公共的 BE32 helper。CRC 更新实现从产品 common.c 移到统一服务，产品与探针共用 `gxr2_crc_add`。独立服务 runtime 使用 `es_*` 符号；DAT 改名校验也移到 `engine_services/mark.c`。这些是源码归属调整，没有恢复旧服务逻辑。

`engine_services/native_seed.c` 是产品配方列表、面板和探针共用的 type-5 状态来源，读取官方 1.51 的 32 B state 与 72 B descriptor，补 108 B 无详情状态，共 212 B。产品列表与探针各把 descriptor 5 接到自己的十六行标签表，发布十六行计数和空隐藏表。探针的主机绘制桥逐行检查传入的文字、私有 descriptor、行数和标签地址；产品菜单验收核对 212 B 状态、descriptor 和十六行指针。两者都未靠测试代码伪造非零 `ui_state_bytes`。

格式化由产品引擎在安全菜单处理。纯 rebind init 发现 IROM 代次改变时只读并返回受限能力，不做 W、文件写或普通 stock 基线重绑。紧随的菜单入口先恢复私有 stock 与 T，撤 UI，再 fence。主机 flow 在三个单元上检查了旧入口被拦、init 无写、恢复 stock、原七项 UI 和重启无引擎回退。

这里没有加常驻回放专用分支。fence 后代码 lease 留到重启，未宣称已经证明相机上所有在途调用结束后的安全释放。H32 同时改变单元代次时不能套用 H31 的 stock 恢复证明，继续按 stale 或 uncertain 收口。

## 已核实：五份容器

| 容器 | 文件 B | 代码 B | BSS B | 文件加 BSS B | 主块申请 B |
| --- | ---: | ---: | ---: | ---: | ---: |
{rows}

五份都含真实 M32R 链接代码，HOST_ONLY 标记为零；均按本轮实际 resident 身份重新打包。全部只有一个内部 BE32 重定位 cell，并通过零基址和平移重链的字节归一化检查。主机 loader 读取实际交付文件，检查外层、重定位并清 BSS；执行入口时分派到同源 C，没有执行其 M32R 指令。

base 与 huzi 的展开条目和独立 `effective-rows.bin` 与 integrated 上游完全一致，包括 huzi 的 50mm 07 Chrome 与 08 Vivid。WB 两轴仍关闭。独立清单记录了 448 B entry 的相同字节，不只比较名称或槽号。

产品代码没有达到先前 40 KiB 压缩目标；本任务没有把放宽兜底称作压缩。产品的私有 gate 和 core 接纳门同步到 96、64、112 KiB，才能接受定稿代码。当前安装流程的两个临时 lease、STORAGE 和 panel store 仍限 64 KiB，未来超过 64 KiB 的产品文件还需要引擎侧安装流程调整。放宽 resident 不证明相机有足够空闲堆。

```text
{hashes}
```

## 已核实：验收

完整 C 校验共 15 次，五份文件各验三个单元。产品端到端共 45 个场景，实际编译 resident loader、统一服务、core、panel 和文件安装代码，覆盖首次安装、DAT 交付、IROM 重启、配方和微调保存、两种改名失败、分配失败、坏内层、坏 CRC、截断、读失败及通知注入。原始结果见 `local/product/acceptance.json`、`local/product/logs/e2e-*.log` 和 `local/full-validator-probes.json`。

常驻侧针对本轮改变及其边界运行八组，共 {resident['checks']} 次断言，其中七次为夹具读取检查，包含真实 loader 与服务 C，原生输送和引擎入口为 double。post hook 的四个真实映射及两个空位也逐个走过。没有把上游的 61352 项直接当作本轮复跑结果。

| 常驻组 | 断言数 |
| --- | ---: |
{group_rows}

三份探针每份都走三个单元的正常路径及故障注入。LIFE 保留 64 KiB 见证，容量块不可读检查使用 ASan poison；NOTICE 与 VIEW 不发 W、不写文件。所有探针都核对移除卡文件且两个机内引擎不存在时回原七项列表。抄录解码另有 {probes['python_checks']} 次 Python 检查。

| 探针主机程序 | C 断言 | 抄录页 | 文件写 | RPC |
| --- | ---: | ---: | ---: | ---: |
{probe_rows}

这些数字是断言数或抄录页数，不是新增独立硬件场景。C 测试均启用 ASan 和 UBSan，macOS 不启用 LeakSanitizer。测试使用 `/usr/bin/python3 -I -B`，环境在 `local/host-environment.json`。

## 与上游的差异及来源

- 相对 resident_slim，常驻 payload 从 7784 B 变为 {size['payload_bytes']} B，root 不变。改动集中在能力、初始代次、边界常量和入口保护，以及抵消其成本的等价缩减。
- 相对 integrated，服务合回唯一源码，seed 和改名核对搬入服务目录，产品列表也改用完整 seed；增加纯 init 与安全菜单的格式化顺序处理，私有容器与 core 门同步到定稿上限。产品配方数据逐字节不变。
- 相对 probes_int，接入定稿身份与唯一服务，使用真实 seed 和十六行私有 descriptor，去掉测试中伪造 renderer 长度的做法。本次交付只含 LIFE、NOTICE、VIEW 三份 64 KiB 配置，不额外打小见证档。

`UPSTREAM.json` 记录 94 个只读来源及初始 SHA，`audit.py` 复核它们未变。完整来源差异在 `local/source-differences.patch`；上游 integrated 提供的原始差异保留为 `local/upstream/source-differences.patch`。工具链沿用上游 GCC、ld、objdump 和各自的选项；常驻不加 LTO，产品保留 LTO，探针保留其原选项。服务归档给探针使用，产品以自身 LTO 选项编译同一套服务源码。

原始失败保留在各 `local/**/failures/`。调试中发现的构建归档短名、map 合并字符串计数、独立 validator 的 CRC 依赖、旧私有门和格式化 init 顺序问题，均已修正；最终构建证据为 `local/rebuild.log` 和 `local/product-rebuild.log`，后者记录产品列表补齐 seed 后的两份重打。完整验收日志为 `local/verify.log`。

## 推断与未知

推断：这些结果支持把此版交给独立审查和 image_v2。源码、服务、容器身份与主机入口已经闭合，仍需要最终映像审查与机上探针来决定是否继续。

未知：实际 M32R 指令执行、相机列表和面板的显示、物理键 phase、任务和原生调用的总栈上界、真正睡眠、回放、USB、堆容量、native 缺失文件错误码、W 回读和 IROM 改名语义均未机上验证。`local/stack.json` 只有静态函数帧，不是完整任务栈上界。nonce 跨冷启动唯一性仍未解决。VIEW 不给 WB 两个原始字命名，刷新完成仍为 UNKNOWN。

`USER_GUIDE_DRAFT.md` 只写探针阶段，给出 LIFE、NOTICE、VIEW 文件、ADJ 与 MENU/OK 操作、手机拍屏和删文件恢复。它按本轮机内两个引擎槽为空的安排撰写；本任务未生成映像，也未核实相机存储。独立审查与打包必须保留这个条件，不能拿已装产品 IROM 的状态套用删卡恢复。

## 复核命令

从仓库根执行。所有生成物继续写在本任务的 local/。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
git check-ignore -v firmware/resident_final/local/check
/usr/bin/python3 -I -B firmware/resident_final/checksums.py --check
/usr/bin/python3 -I -B firmware/resident_final/audit.py
```

从源码完整重建、验收并刷新报告与清单：

```sh
/usr/bin/python3 -I -B firmware/resident_final/build.py
/usr/bin/python3 -I -B firmware/resident_final/verify.py
/usr/bin/python3 -I -B firmware/resident_final/report.py
/usr/bin/python3 -I -B firmware/resident_final/checksums.py
/usr/bin/python3 -I -B firmware/resident_final/checksums.py --check
```

重建会刷新日志和证据，之后再生成校验清单。image_v2 应读取本报告给出的最终 ELF 与 `local/hooks.json`，不能把旧 resident_slim 的 map 或 patch-manifest 当作本轮字节。
'''
    (HERE/'REPORT.md').write_text(text)
    print('WROTE REPORT.md from actual artifact and acceptance JSON')

if __name__=='__main__':main()
