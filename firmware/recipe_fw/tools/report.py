#!/usr/bin/env python3
"""Generate the integration report from final linked and verified artifacts."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
OUT = ROOT/"research/stage1b_integration"


def main():
    manifest = json.loads((HERE/"build/manifest.json").read_text())
    hooks = json.loads((HERE/"hooks.json").read_text())
    verification = json.loads((HERE/"build/verification.json").read_text())
    if manifest["payload_sha256"] != verification["payload_sha256"]:
        raise ValueError("report would mix different artifacts")
    package = ROOT / "artifacts/stage1b-candidate/packages" / ("stage1b-16-recipes-" + manifest["payload_sha256"][:12])
    package_status = "当前没有与这份 payload 对应的本地候选包。"
    if (package / "manifest.json").is_file():
        packed = json.loads((package / "manifest.json").read_text())
        if packed["payload_sha256"] != manifest["payload_sha256"]:
            raise ValueError("package and report payload differ")
        package_status = (f"已生成[本地实验候选包](../../{package.relative_to(ROOT)}/README.md)，"
                          "候选和官方恢复目录各 29 文件已读回核验。该候选尚未上卡、未在相机运行。")
    probe = manifest["probe"]
    labels = {
        "force_adj_image":"ADJ 固定进入 Image 分支",
        "init_recipe_cache":"初始化缓存和配方光标",
        "init_cursor_bypass_enum":"跳过七模式光标转换",
        "adj_name_table":"ADJ 名称表",
        "adj_count_16":"ADJ 数量 7→16",
        "adj_empty_details":"16 条空 Detail 表",
        "fn2_no_editor":"Fn2 配方状态拦截",
        "adj_confirm_close":"原厂 apply 与退出函数",
        "live_recipe_commit":"光标即时应用与主菜单旁路",
    }
    rows = []
    for hook in hooks["hooks"]:
        refs = hook["original_disassembly"]
        source = ", ".join(f"S{ref['file'].split('-sec')[1][:2]}:{ref['line']}" for ref in refs)
        if not source:
            source = "原字节直接核对"
        checks = ", ".join(str(check["delta_bytes"])+" B，PASS" if "delta_bytes" in check else "绝对地址，PASS"
                           for check in hook["branch_checks"]) or "数据，等长"
        rows.append(f"| {labels[hook['id']]} | `{hook['va']}` | `{hook['file_offset']}` | {hook['length']} | {source} | {checks} |")
    bridge_rows = []
    for check in manifest["prelink_branches"]:
        bridge_rows.append(f"| `{check['pc']}` | `{check['target']}` | `{check['symbol']}` | {check['delta_bytes']} | PASS |")
    report = f"""# ADJ 16 配方固件整合

已完成可链接的实现与 {hooks['hook_count']} 处等长挂钩规格。最终 payload 为 **{manifest['payload_bytes']} 字节**，位于 `{manifest['payload_base']}..{manifest['payload_end']}`。电脑端验证通过；候选地址、ABI 和相机交互仍待真机验收。{package_status}

日期：2026-10-15。缓存修订之后，本轮把 Fn2 和即时提交挂钩后移到原厂 activity=8 判断之后；非 Image 活动在这两处直接走原厂分支，不进入 payload。输出留在电脑端，未连接相机，未提交 Git。阶段 1 背景见 [COMMON.md](../stage1_brief/COMMON.md)。

## 1. 最终产物与验证

| 项目 | 结果 |
| --- | --- |
| 链接架构 | ELF32、大端、M32R，机器号 88 |
| 编译参数 | `-mmodel=large -msdata=none -G0`，另含 `-Os -ffreestanding -fno-builtin` |
| Payload | {manifest['payload_bytes']} B，SHA-256 `{manifest['payload_sha256']}` |
| 可用候选容量 | {manifest['capacity']} B |
| 探针独占末尾 | `{probe['va_start']}..{probe['va_end_exclusive']}`，{probe['length']} B |
| Payload 到探针间余量 | {probe['additional_free_bytes_before_tail']} B |
| 可写全局节 | 0 B，无 `.data/.bss/.sdata/.sbss`、COMMON、GOT 或初始化器 |
| 未定义符号、剩余重定位 | 均为 0 |
| 原厂堆缓存 | 目标端 {verification['target_layout']['cache_bytes']} B，包含 16×96 B 字形、双解引用表、788 B 库及 1056 B 文件 scratch |
| 宿主行为 | {verification['host'][0]['cases']} 项普通执行通过，同一 {verification['host'][1]['cases']} 项 ASan/UBSan 通过 |
| 汇编桥接模型 | {verification['abi_model_cases']} 项通过，读取最终反汇编，原厂和 C 函数体用 stub |
| 电脑工具与挂钩测试 | {verification['tool_cases']} 项通过 |
| 构建拒绝检查 | 5 项通过：`.data`、`.bss`、未知 section、远地址分支越界、探针空间重叠 |
| 更换链接位置 | `0x20052770`、容量 8336 B，完整重新链接与挂钩解码通过，探针区保持相同地址 |
| 受保护输入 | {verification['protected_inputs']} 个文件在前后保持相同 SHA-256，包括官方镜像及 `recipe_v1/`、`recipe_core/`、`scripts/` |

产物：[payload.bin](../../firmware/recipe_fw/build/payload.bin)、[payload.elf](../../firmware/recipe_fw/build/payload.elf)、[payload.map](../../firmware/recipe_fw/build/payload.map)、[manifest.json](../../firmware/recipe_fw/build/manifest.json)、[verification.json](../../firmware/recipe_fw/build/verification.json)。`payload.bin` 包含已链接代码和只读常量，导出结果逐字节匹配 ELF 的 `.payload`。

## 2. ABI 与平台回调

`abi.S` 在普通函数边界保存 `lr` 与 `r8..r13`。原厂进入 C 时把 `r4..r7` 搬到 `r0..r3`，调用原厂时反向搬移，返回值保持 `r0`。边界只用至多四个标量或指针，不传结构体、浮点或可变参数。中途挂钩额外保存 `r0..r7` 和 PSW；最终反汇编与桥接模型核对了保存、搬移、结果和栈平衡。

原厂调用的 VA、文件偏移及参数沿用 [数据报告第 2 节](../stage1_data/REPORT.md) 与 [代码空间报告第 5、6 节](../stage1_codespace/REPORT.md)。文件函数打开 `0x200A40B4 / 0x592B4`、创建 `0x200A544C / 0x5A64C`、读 `0x200A449C / 0x5969C`、写 `0x200A45E8 / 0x597E8`、关 `0x200A437C / 0x5957C`、删 `0x200A4910 / 0x59B10`、建目录 `0x200A4958 / 0x59B58` 都有独立 GCC ABI 入口。堆使用核心 alloc `0x2005BF5C / 0x1115C`；payload 已删除 free 入口，原厂绘制保留的名称地址不会被本实现释放。

文字绘制 `0x201D7170 / 0x18C370 / S08:25956` 与 ASCII 转换 `0x201D73E0 / 0x18C5E0 / S08:26112` 也有适配层。转换四参数为输入串、长度、输出缓冲、语言；语言取 `0x201DC180 / 0x191380`，与原卡槽菜单 `0x202168A8..B8 / 0x1CBAA8..B8 / S08:90930..90934` 一致。实际列表继续使用原厂 24 字节文字描述块和双解引用消费者 `0x201FE410 / 0x1B3610 / S08:66060`，没有新增资源 ID。

读取每次只占一个原厂 handle，循环完成短块读取，再读 1 字节识别超长文件。任何已打开的 handle 都经过 close，包括读写失败；close 错误也返回 `RV1_IO`。固定路径检查拒绝 PARAM.DAT 等其他目标。

设置回调每次重读 `*(u32*)0x200C0DAC` 与长度单元 `0x200C0DB0`，不会缓存 S 指针。继续调用未修改的 `rv1_apply`，只写 Setting1 的 13 字节、WB 两轴和选择值共 16 字节，最后发布 `S+0x36E=04`。预览桥接到 `0x202D6F38(0) / 0x28C138 / S09:124374`，0 映射 OK，其余映射 IO。下一次拍摄继续由原厂发送 `0x2F02`。

本实现的 busy 标志覆盖配方加载和应用，阻止文件或预览回调中的同任务重入。关闭只清除 opened，不释放内存。原厂拍摄、MY 召回、保存与 UI 是否确实由同一任务串行访问，仍是未知。busy 不充当其他任务或中断的锁。

## 3. 缓存和 UI 行为

缓存由被替换的 ADJ type5 描述符 `0x2022F5A8` 的表指针持有，缓存首字段就是 16 项表。首次打开分配并清零，随后保持表指针，关闭只清除 opened；再次打开复用同一块 3520 B 内存并重新读取配方库。没有新增可写全局地址。分配失败时仍用两份不同地址的编号表记录开关状态，显示 R01..R16。此内存上限成立的前提是原厂描述符保持该指针；段重装载或原厂重置指针是否发生仍未知，不能据此宣称全生命周期只分配一次。

`current()` 在读取缓存内容前检查对齐及原厂堆区间 `*(u32*)0x200D3488..*(u32*)0x200D348C`，要求整个缓存都落在区间内，再核对 `table[0] == &labels[0]`。堆边界来自原厂初始化 `0x2005BF00` 和释放检查 `0x2005C048..0x2005C05C`。NULL、原厂 ROM 表 `0x2022D610`、未对齐或不够长的区间及错误的表内指针均不会被当作可写缓存。它不证明其他任务不会同时重置堆或描述符。

打开先分别读取和完整校验两份库，再重读所选库，核对 generation 与全文件 CRC。名称限定可打印 ASCII，复制最多 32 字节并加 NUL，预转成各自的 96 字节菜单字形缓存。空槽、非 ASCII 名称、全空白名称或无有效库显示 R01..R16。损坏、短、超长、版本不支持、generation 冲突的库不会进入设置对象。

只读 UI 可以使用完整有效的一份库，即使打开另一份返回未分类的 IO。这是 `load_view` 的只读策略，允许电脑只生成 RECIPES0.DAT。它没有把 IO 改成 EMPTY，也没有把此规则用于保存。两份都不可用时列表仍显示编号；选择空槽或不可用库不写设置、不请求预览。

打开时按当前 S 的完整 13 色彩字段、两轴 WB 与选择值查找匹配槽，匹配多个时取编号最小者；找不到则高亮 R01。打开本身不改设置。光标提交与 overlay apply 两条路径都调用 `rfw_select`，选择有效槽后立即请求预览。overlay 的重复回调会去重。首次打开未移动光标而按 OK，也会应用高亮的有效配方。

MENU/OK 退出并保留已应用参数，不恢复旧 Setting1。Fn2 在配方列表中返回原厂 handled=2，跳过 Setting1 编辑与菜单状态切换。通用函数 `0x201C092C..0x201C0CF4` 保持原厂字节。配方页面判断要求 layer2 顶层 tag=33、state 指针=2022F71C 以及该状态的类型字节为 5；原厂在 `0x2028712C` 写入 5，兄弟页面分别在 `0x20285910` 写入 0、`0x20287328` 写入 11。测试遍历其余 255 个类型，全部旁路配方提交。

页面归属与 opened 分开。只要 16 行的配方界面仍可见，就拦住七模式的原厂 setter；库加载失败或加载期间关闭时，提交被消耗但不改设置。页面不是配方时，`ricoh_recipe_action` 保存/恢复寄存器和 PSW，重放原入口 `push lr`，以原 r4 和原栈状态跳到 `0x202871DC`。原厂函数继续自行决定关闭、参数写入和返回值。桥接模型覆盖 keep_open=0/1 的两条分支。

当前 UI 判据来自 `0x201C0840..0x201C0890 / 文件0x175A40..0x175A90 / S08:2840..2860` 的绑定代码及上段 type5 初始化：每 part 16 字节元数据，计数 +8、记录指针 +12，记录每项 8 字节，tag +0、state +4。part2 对应 RAM `0x205A27D4/+4`；活动 part 字节为 `0x205A280F`。宿主与目标运行同一判据，仅内存读取用模拟接口；实际 RAM 和任务时序仍待真机核对。

每屏 9 行的绘制、背景、滚动和原厂按键控制器保留，ADJ 数量改为 16。宿主测试覆盖 1..16、8/9/10、15/16、空槽、无文件、坏文件、重开、S 指针更换、预览失败、重入，以及 100 次开关保持一次申请、零次释放和保留的名称地址可读。另覆盖重新加载时无卡/损坏库不能使用旧值、文字转换失败不能保留旧名称、加载中关闭与申请失败后重试。物理按键、首尾环绕、真实滚动和画面变化尚未执行。

## 4. 等长挂钩清单

[hooks.json](../../firmware/recipe_fw/hooks.json) 保存 VA、唯一文件偏移、原字节、新字节、目标符号、原目标、原指令行、参数准备、返回位置和分支检查。每条都是等长替换；代码区插入另列为 `payload_patch`，不计入 {hooks['hook_count']} 处 UI 挂钩。

| 用途 | VA | 文件偏移 | 替换字节数 | 原反汇编行 | 分支检查 |
| --- | --- | --- | ---: | --- | --- |
{chr(10).join(rows)}

初始化优先改 `0x2028709C/+4` 原有 `seth/or3` 目标构造，保留 `0x202870A4` 的 `jl r0` 和返回地址 `0x202870A8`。后一完整字改成串行 `mv r8,r0 -> bra.s 0x20287118`，保留后面的 part2/tag33 打开、状态和显示操作。Detail 表同样改原有 `seth/or3`，保留 type9 路径。中途分派、共享分支和完整函数入口需要新的续跳，使用 4 字节 BRA24，并记录完整被替换字及其恢复语义。

原厂初始化的 `201C07E0` 有栈上的第五参数；这段调用序列全部保留。函数入口 `202871D8` 在 push lr 之前尾跳，沿用调用者的 lr，保留调用者的 r4 准备与返回位置。构建器拒绝任何 hook 或 payload 覆盖共享界面函数 `0x201C092C..0x201C0CF4` 的 968 B。测试在内存中应用所有修改后逐字节核对该函数，并检查入口、中间和尾部越界会被拒绝。此检查没有证明其他启动/升级路径不受影响。

Fn2 挂钩从 `0x202BE248` 移到 `0x202BE24C`，保留原厂活动判断；非配方页面的回退重放 `seth r0,0x2026` 后续跳 `0x202BE250`。即时提交挂钩从 `0x202BB960` 移到 `0x202BB968`，保留原厂 `ldi r2,8` 和 `bne`；回退重放 `seth r11,0x2022` 后续跳 `0x202BB96C`。构建器保护两段原厂判断的 24 B。ABI 模型从原厂调用点开始，分别检查 257 个非 Image 活动都在进入 payload 前分流，Image 活动进入目标包装；两处包装的活动与非活动路径继续检查全寄存器、PSW 和栈。旧产物在同一调用点用例失败，新产物通过，日志见 `artifacts/development/recipe-fw-native-guards/`。这是最终指令流的电脑模型结果。

原字节核对区分了处理函数与调用指令：`0x202C2ABC / 文件0x277CBC / S09:103607` 是另一个处理函数入口，它内部的 apply 调用在 `0x202C2D70/80 / 文件0x277F70/80 / S09:103780/103784`，分别保留 `ldi r4,1/0 -> jl r0`。光标处理的后续 `0x202C2AB0 / 文件0x277CB0 / S09:103604` 调的是 `0x202C1348`，该函数进入后立即准备自己的 r4=0，不是配方 apply。挂钩清单的调用者示例逐条匹配原有 `seth/or3` 目标和 r4 准备字节，避免把入口当作调用点。即时应用包装保存全部中途寄存器；原厂 keep/close 参数准备保持原字节。

## 5. 分支距离与最终字节

BL24/BRA24 范围为 `-33554432..33554428` B，BL8/BRA8 为 `-512..508` B，条件分支为 `-131072..131068` B，目标须 4 字节对齐。`seth/or3/jl` 使用完整 u32 地址，没有相对距离限制。构建器先按输入 object 的 relocation 与独立布局算距离，再链接，随后解码最终字节并核对请求目标；不会只依赖 GNU ld 的退出码。

以下是 {len(manifest['prelink_branches'])} 条需重定位的 payload 分支。挂钩分支距离已列在上一表。最终代码另核对 {len(manifest['decoded_branch_checks'])} 条编码分支，逐条记录在 [manifest.json 的 decoded_branch_checks](../../firmware/recipe_fw/build/manifest.json)，全部 PASS；只扫描输入 `.text` 范围，不把只读表解成指令。

| PC | 目标 VA | 目标符号 | 距离 B | 结果 |
| --- | --- | --- | ---: | --- |
{chr(10).join(bridge_rows)}

越界负例把链接起点移到 `0x30000000`，在调用 ld 前被距离检查拒绝。另有工具用例覆盖三类分支的正负边界与边界外一字，并拒绝未对齐目标。`--probe-reserve 2048` 超出剩余容量，同样在链接前拒绝；实际 `.data` 与 `.bss` 输入分别被链接脚本拒绝。

## 6. 写回回调的当前边界

原厂 `open=-1` 与 `delete=-1` 的底层原因尚未完成可靠分类。平台保持 IO 状态，禁止由未知删除失败继续创建或截断目标。两份目标已存在且有效时，未修改的 v1 load/save 已在模拟原厂接口上完成交替删除、创建、写入、关闭、重读校验，旧有效库保持不变。

只有一个文件或两个文件都不存在时，相机端 v1 save 的初次建库会保守返回 IO；本轮 ADJ 只读配方，因此不会触发它。电脑工具可生成首份库并被 UI 正常读取。后续若增加相机编辑和保存，需要先实测文件不存在、满卡、拔卡等错误原因，再开放初次创建。建目录、堆、文字等原厂适配函数都已链接，首版 SD 根目录路径不需要建目录。

## 7. 与探针 worker 的接口

- 链接输入是 `--base`、`--capacity` 与 `--probe-reserve`，默认 `0x2005276C`、8340、256。改变地址后重新生成 ELF、map、payload 和 hooks，不能只改 JSON 地址。
- 探针独占 `[{probe['va_start']},{probe['va_end_exclusive']})`，文件 `[{probe['file_offset']},0x9A00)`，{probe['length']} B。本实现不写这一区，输入仍为 FF；链接脚本导出 `__probe_start/__probe_end` 并断言 payload 不越界。
- 当前 payload 到 `{manifest['payload_end']}` 为止，其后 {probe['additional_free_bytes_before_tail']} B 也保持原字节。额外空间由协调 worker 分配；探针不能把独占末尾之外的位置默认当作可覆盖区。
- 用户已选择把候选区执行验证并入完整配方的首次实机测试，暂不另做微型执行探针。仍需核对候选区取指、r8..r13/lr/sp/PSW、3520 B 原厂堆申请、描述符重置/段重装载与缓存生命周期。

## 8. 仍需真机验证

静态已确认的是原字节匹配、已初始化段映射、编译链接、输出哈希、等长规格和分支范围；电脑已观察的是上述模拟行为与工具拒绝结果。`candidate_vma_approved=false`、`camera_verified=false` 均保留在规格中。

未知项目包括候选区的运行时写入和取指权限、PSW 访问与任务栈容量、其他原厂任务的设置访问、缓存内容刷新与异步绘制的时序、段 8 重装载对表指针及累计申请的影响，以及半按快门、连拨、Fn2、模式切换、语言切换的真实事件顺序。35xx B 缓存的实时堆容量和 100 次真实开关也尚未观察。

2026-10-15 的 decisions.tsv 与 captures/a12-50/2026-10-15 记录了 v3 探针显示 OK 8 及恢复官方 1.51 成功。这只覆盖该探针及正常升级入口，不能推广为本 payload 已执行或损坏主程序后必能恢复。P/A/S/M 一键入口、16 项滚动、预览 `0x2F03` 的模块接收、WB 模式限制、JPEG+DNG、正常关机后保留选中配方和本候选的官方恢复仍待实机验收。当前支持电脑编辑配方文件，相机内编辑和保存 UI 尚未接入。

复跑方式见 [recipe_fw README](../../firmware/recipe_fw/README.md)。完整 stdout 在 `build/host-results.txt`、`sanitizers-results.txt`、`abi-results.txt` 和 `tools-results.txt`，拒绝日志与重新链接的证据也在同一 build 目录。
"""
    report = report.replace("35xx B",str(verification['target_layout']['cache_bytes'])+" B")
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"REPORT.md").write_text(report)
    print(json.dumps({"report":str(OUT/"REPORT.md"),"payload_bytes":manifest['payload_bytes'],"hooks":hooks['hook_count']}))


if __name__ == "__main__":
    main()
