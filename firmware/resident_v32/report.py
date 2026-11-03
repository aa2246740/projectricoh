#!/usr/bin/env python3
"""Generate the Chinese report from the recorded artifacts and gates."""
import importlib.util
import hashlib
import json
from pathlib import Path
import re
HERE=Path(__file__).resolve().parent
def load(name):return json.loads((HERE/'local'/name).read_text())

def main():
    spec=importlib.util.spec_from_file_location('report_guard',HERE/'resident/build.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);guard.preflight()
    d=load('delivery.json');s=d['resident'];t=d['identity'];host=load('resident/host-results.json')
    product=load('product/acceptance.json');probes=load('probes/tests/summary.json')
    irq=load('irq-machine.json');pairs=load('irq-pairs-machine.json');h07=load('h07-machine.json')
    p=load('policy-machine/results.json');full=load('full-checks/results.json')
    regression=load('regression/results.json');scope=load('inputs-verification.json');stack=load('stack/comparison.json')
    assert load('verification/summary.json')['status']=='OFFLINE_PASS_HARDWARE_UNTESTED'
    assert all(x['status']=='PASS' for x in (p,full,regression,scope))
    assert p['negative_controls']['status']=='PASS' and p['F03']['status']=='PASS'
    assert guard.build_identity().hex()==t['resident_build_id'] and s['margin']>=300
    census=[]
    for variant in ('base','full'):
        for unit in range(3):
            path=HERE/f'local/product/logs/e2e-{variant}-flow-{unit}.log';text=path.read_text()
            match=re.search(r'IROM_CENSUS old_generation=(\d+) new_generation=(\d+) valid_A=(\d+) valid_B=(\d+) install=(-?\d+)',text)
            assert match and 'FLOW_PASS' in text and f'OK scenario=flow unit={unit} ' in text
            census.append(dict(variant=variant,unit=unit,old_generation=int(match[1]),new_generation=int(match[2]),
                               valid_A=int(match[3]),valid_B=int(match[4]),install=int(match[5]),
                               source=str(path.relative_to(HERE)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (HERE/'local/evidence/final-install-census.json').write_text(json.dumps(dict(status='PASS',cases=census),indent=2)+'\n')
    lines=[
        f'F08 已收窄为唯一固定原生 view 数组，F09–F11 已修正，六份容器的离线检查通过。常驻层严格链接余量为 {s["margin"]} B。`full` 已按指定来源重绑并通过完整 C 校验与端到端流程。本轮未生成机身映像，未做实机验收。','',
        '# resident_v32 实现与离线验证报告','',
        '日期为 2026-10-24。目标是用户的 GXR 机身 1.51，以及官方 1.51 的 GR LENS A12 50mm、A12 28mm、MOUNT A12。本目录从只读 `firmware/resident_v31/` 复制起步，完整阅读了 `research/review_flash_v31/REPORT.md`。所有写入限定在本目录；官方固件、v31、Stage2l 与三轮审查保持只读。','',
        '## 1. 已核实：交付与写入边界','',
        f'payload 为 {s["payload_bytes"]} B，root 为 {s["root_bytes"]} B，合计 {s["occupied"]} B，窗口为 8340 B。链接脚本与 v31 逐字节相同，保留 `--no-undefined --orphan-handling=error` 和至少 300 B 的断言。没有常驻可变 BSS、未解析重定位或新增系统 hook。','',
        '```text',
        'official ilaunch3 SHA256: da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
        'resident ELF SHA256: '+s['sha256'],
        'resident build ID: '+t['resident_build_id'],
        'resident ABI ID: '+t['resident_abi_id'],
        'root version: 32',
        'service archive SHA256: '+d['service']['archive_sha256'],'```','',
        '六份容器均绑定上述 build/ABI，使用同一服务归档；v31 容器不属于这组交付。','',
        '| 容器 | 文件 B | 引擎 B | BSS B | image+BSS B | SHA-256 |',
        '|---|---:|---:|---:|---:|---|'
    ]
    for c in d['containers']:
        lines.append(f'| [{c["name"]}]({c["path"]}) | {c["file_bytes"]} | {c["code_bytes"]} | {c["bss_bytes"]} | {c["image_bss_bytes"]} | `{c["sha256"]}` |')
    lines += [
        '', '后续 `firmware/image_v3` 的输入为 [resident.elf](local/resident/build/resident.elf) 和 [patch-manifest.json](local/resident/patch-manifest.json)，必须带 `--patch-manifest`。本轮没有运行映像工具。容器、字节切片、反汇编、主机程序与日志均只在 `local/`。','',
        f'已核对外置卷为已挂载、可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。`.gitignore` 第一行为 `/local/`，已执行 `git check-ignore -v`，见 [ignore.log](local/ignore.log)。{scope["checked_files"]} 份保护输入的摘要均未改变。没有访问相机或存储卡，没有刷机、安装包、子代理、sleep、轮询、commit 或 push。','',
        'Python 全部使用系统 `/usr/bin/python3 -I -B`。GCC 为 `research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc`，ld 为 `research/tooling_m32r_asm/prefix/bin/m32r-elf-ld`，objdump 为 `research/tooling_m32r/prefix/bin/m32r-elf-objdump`，与 v31 相同。resident C 文件仍追加原有 `-mmodel=medium`，服务和产品保留原有 PIC/LTO 选项。命令见 [cross-commands.json](local/resident/cross-commands.json)。','',
        '```text',' '.join(s['flags']),'```','',
        '## 2. 已核实：F08 只接受固定数组，撤回不跟随旧槽位地址','',
        '已重新从官方映像取字节并用指定 objdump 核对。见 [初始化](local/evidence/native-view-init.disasm)、[push 与计数](local/evidence/native-view-push.disasm)，同目录保留命令与原始切片。','',
        '```text','201C05E4  seth r0,#0x205a','201C05E8  seth r2,#0x205a',
        '201C05EC  or3 r0,r0,#0x279c','201C05F0  or3 r2,r2,#0x27d8','201C05F4  st r0,@r2',
        '*0x205A27D8 = 0x205A279C','```','',
        'part 2 记录基址为 `0x205A27CC`；`+8` 是计数 byte `0x205A27D4`，`+12` 是数组指针 `0x205A27D8`。官方 push 对 part 2 限制两条记录，每条 8 B，tag 在 +0，state 指针在 +4。因此唯一数组是 `0x205A279C`，两个 state 槽是 `0x205A27A0`、`0x205A27A8`。','',
        '[shared.c](resident/shared.c) 的 `rv_ui_capture` 只接受该数组且计数为 1..2。`RV_UI_LIST`、`RV_UI_VIEW` 两个入口均检查其结果，VIEW 在读 top 前也检查固定地址。`owned` 与 FF-root 回退同步删除宽泛 RAM 范围支持。其它地址和堆数组一律拒绝自有发布，走原厂路径。','',
        '`rv_ui_abort` 删除了动态槽位地址的保存和使用，只遍历两个固定 state 字段。tag 为 33 且仍引用本次发布快照时，写回常量原厂 state `0x2022F71C`；原生新 state 保留。它不读当前数组、不解引用失效快照，也不跟随旧槽位记录。名称表、七项数量和两个原厂 cursor 保持原有恢复合同；恢复失败时保留记录并停用到重启。','',
        'resident 与服务归档编译同一份 shared.c。root 保持 256 B，旧槽位字段与旧 grain 缓存字段作为保留空间，不再参与恢复/H09。首版严格链接失败日志保留在 `local/resident/failures/`；最终靠继续删除动态槽位逻辑过门，没有放宽链接器。','',
        '两个原反例现在都在真实 UI_LIST 服务处返回 `RV_STALE`，未发布自有页。释放后撤回不读写 dead array；同址复用的新对象 word 保留。一层、两层、底层引用、原生替换、快照失效和堆边界移动仍通过。对照见 [v31 原始失败](local/regression/v31/expired-slot.log)、[v32 expired-slot](local/regression/v32/expired-slot.log)、[v32 reused-slot](local/regression/v32/reused-slot.log)。','',
        '## 3. 已核实：F09 native 强制关闭优先','',
        '选择代码改动最少的方案，保留当前正确路由，收紧 [abi.h](resident/abi.h) 和 [ig_event](containers/product/adapter.c) 合同。H07 的 native r4=0 即 args[9]=0 时，引擎先做完保存或撤销，随后无论哪态都关闭；CONSUMED 只在 native 允许保持时保持页面。没有新增 KEEP/CLOSE/PASS 枚举。','',
        '| native r4 | 引擎结果 | 撤回 | 最终桩 |','|---:|---|---|---|',
        '| 0 | PASS / CONSUMED / CLOSE_AND_PASS | 是 | close |',
        '| 0 | FAULT | 是，另停用 | close |',
        '| 1 | PASS | 是 | keep，返回 caller |',
        '| 1 | CONSUMED | 否 | keep |',
        '| 1 | CLOSE_AND_PASS / FAULT | 是，FAULT 另停用 | close |','',
        'A4 的 OK 按已核实 key/caller 保存，MENU 与其它强制退出撤销草稿。产品 flow 还覆盖 native keep=1 的 OK 和 MENU，均按引擎 CLOSE_AND_PASS 关闭。实际关闭桩调用 native hide `(2,1,0)` 并清 overlay，保持桩清 overlay；两者返回 native 1，跳过原厂七项 setter。','',
        '## 4. 已核实：F10 与 Stage2l 的当前值规则一致','',
        '提交时只保留已提交 grain 资格和基底模式，不缓存 S、尺寸或等级。每次 H09 重新读当前 S、长度、selector、尺寸与 `S+0xC9D`。','',
        '| 条件/动作 | 共同规则 |','|---|---|',
        '| 有效资格 | 已提交有效 GRAIN、无 uncertain/stop；S 非空、长度至少 `0xC9E`，selector 匹配已提交基底模式。 |',
        '| category | 0 或 4。 |',
        '| packet 门限 | +0x1A、+0x14、+0x75、+0x1E、+0x26 均为 0。 |',
        '| 当前尺寸 | `{1,2,5,8,12,16}`，即 `0x11126`；变化到另一个允许尺寸仍应用。 |',
        '| 写入 | +0x1A=21、+0x10=0、+0x32=1、+0x6F=当前等级；等级非 1..3 时写 1，其它字节保留。 |','',
        '原反例中，提交等级 3 后改为 1，packet 现在是 1；尺寸 1 改成允许的 2 后仍应用。H09 仍没有引擎、文件、分配、free、自检或 retire 调用。见 [h09-differences.log](local/regression/v32/h09-differences.log)。','',
        f'最终 v32 与 Stage2l 指令在主机子集执行器中比较 {p["H09"]["packet_cases"]:,} 组完整 128 B packet，包括 256×256 等级/尺寸、256 个 category、五门限、S 空值/长度/迁移、六个默认条目的 selector。每组另核对字面值预期。旧 v31 机器码的过期槽位和缓存等级/尺寸作为负对照，均被检出。见 [机器码结果](local/policy-machine/results.json)。','',
        '## 5. 已核实：F11 与 full 来源','',
        '更正旧说明：三个产品引擎长度相同，但字节不同。每个 variant 的 ELF `.engine` 已分别匹配其容器与 engine.bin，不能用一个 variant 的 ELF 代替另一份。','',
        '| 产品 | 对应 ELF | ELF SHA-256 |','|---|---|---|'
    ]
    for name,digest in full['variants']['ELFs'].items():lines.append(f'| {name} | [engine.elf](local/product/candidates/{name}/engine.elf) | `{digest}` |')
    lines += ['', '| 比较 | 差异 B | BSS 重定位 word | BSS 基址差 B |','|---|---:|---:|---:|']
    for c in full['variants']['comparisons']:lines.append(f'| base / {c["variant"]} | {c["different_bytes"]} | {c["BSS_relocation_sites"]} | {c["BSS_delta"]} |')
    lines += [
        '', '差异全部为类型 64 的 BSS 重定位低半部，其余引擎字节相同。探针分别保留在 `local/probes/build/{life,notice,view}/engine.elf`。证据见 [full-checks/results.json](local/full-checks/results.json)。','',
        '`full` build=103，以 huzi 为基础；v6 按条目内槽号查找，没有假定物理顺序为 01..08。','',
        '```text','artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/DEEPTBL0.DAT:',
        '44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05',
        'research/refit_50mm_r7/local/v6/candidate_v6.DEEPTBL:',
        '21159c8143a87680b624adfae6b34e8ab4b4d730a8720907cf2e448dd43b1592','```','',
        '| 50mm 槽位 | 短名 | 来源 |','|---|---|---|',
        '| 01、02 | 01 Posi、02 Nega | 原版 448 B 逐字节不变。 |',
        '| 03、04 | 03 HC BW、04 Std | 与 base 不变。 |',
        '| 05、06 | 05Chrome、06ClsNeg | v6 的 05、06。 |',
        '| 07、08 | 07 Chrome、08 Vivid | huzi 的 Panasonic S1RII、safe、70% 条目。 |',
        '| 09、10 | 09 Posi6、10 Nega6 | v6 的 01、02，重绑到 09、10。 |',
        '| 11..16 | 11 Stock..16 Stock | 原厂别名。 |','',
        '28mm、Mount 的 16 槽均为各自原厂别名。替换条目按最终 record 重绑 49 B 身份、槽号、身份 CRC 和 record CRC；打包器重算 bank/header/payload CRC。完整 C 校验器接受 full 三单元，另由 C 展开全部 48 条，与固定来源逐字节比较。flow 实际应用 01..16 并检查 native 表，覆盖新 05/06/09/10。条目原始路径、摘要和重绑身份见 [full manifest](local/product/candidates/full/manifest.json)。','',
        '## 6. 已核实：历轮反例、机器码与端到端','',
        '| 检查 | 结果 |','|---|---|',
        f'| resident C | {len(host["cases"])} 个具名用例，{host["checks"]:,} 次断言，ASan/UBSan。 |',
        '| 历轮原反例 | 原 v31 夹具保留并复跑；v32 主流程及 7 分支、前轮 v3 的 F04–F07 全部通过修复后断言；适配 diff 见 local/regression。 |',
        f'| F01 | IRQ 共 {irq["total_raw_vectors"]:,} 个 PSW 向量，覆盖 resident/服务/六容器；旧 OR3 极性 8 个负对照拒绝；{sum(len(v) for v in pairs["artifacts"].values())} 个编译后函数 save/restore token 与分支配对通过。 |',
        '| F02/F03 | 固定双槽与底层视图恢复，快照保留；最终无 post/notify/epochs，H10..H37 保持官方字节。四个旧 post hook 号不影响 frame/root。旧 post 反例无可执行入口，没有人为重建它充当复测。 |',
        f'| F08 指令 | {len(p["F08"])} 组准入/撤回，含过期/复用槽、双槽、替换、失效快照、伪造旧记录；禁止地址一旦读写，立即失败。 |',
        f'| H07 指令 | {len(p["H07"])} 组真实 observer 指令矩阵；另 {h07["vectors"]} 组关闭/保持桩检查 hide、overlay、返回值与栈。 |',
        f'| 产品 | {sum(r["kind"]=="full-c-validator" for r in product)} 组完整 C 单元校验；base→huzi 18×3，full flow/S 迁移 2×3，共 {sum(r["kind"]=="e2e" for r in product)} 组端到端。 |',
        f'| 探针 | {probes["c_checks"]:,} 次 C 断言、{probes["python_checks"]} 个编解码检查，另 9 组完整 C 单元校验。 |',
        '| 空文件 | 卡与 IROM 均无文件，保持原厂 frame/名称/七项数，0 分配/0 引擎调用，后续不重试。 |','',
        '产品 flow 覆盖首行 01/末行 16、A4 进入/上下/四参数循环/OK 保存/MENU 取消/强制退出/native keep=1、IROM 安装、同代重装确认、重启和模拟格式化回退。同代相同内容可确认已有一个有效槽，更高代更新才要求双槽；见 [最终槽位统计](local/evidence/final-install-census.json) 与 panel_store.c。','',
        '最终 [runs.json](local/verification/runs.json) 与 [summary.json](local/verification/summary.json) 为通过记录。`local/**/failures/` 保留原 bug 的预期失败与开发中测试器/夹具失败，不能把历史红日志都当作最终候选缺陷。','',
        '机器码使用最终 ELF 实际字节及指定 objdump，显示字节逐项对回 ELF；执行器是主机指令子集。H07 的会话/引擎调用、native hide 本体及 C 流程中的文件、分配器、UI、设置/RPC 均有明确 double。没有模拟真实中断、缓存、并发或物理格式化，不能据此声称相机执行和拍摄已验收。','',
        '## 7. 已核实：与 Stage2l 的 hook、行号对照','',
        'Stage2l 的九点含名称指针/项数两个数据点，v32 保留七个相同位置的执行 hook，以服务运行时发布名称/项数；H03/H04 不改官方字节，H10..H37 也均不改。七处默认重放共 896 组向量通过，没有需要修正 PC 相对寻址的原指令。','',
        '| Hook | 官方位置 / 覆盖 B | Stage2l 与 v32 的处理 |',
        '|---|---|---|',
        '| H01 | 0x2028709C / 8 | Stage2l 替换 getter；v32 默认到 0x202870A4，owned 到 H02，native cursor 加 1。 |',
        '| H02 | 0x202870A8 / 4 | v32 默认到 0x202870AC，owned 到 0x20287118，与 Stage2l 绕过枚举目标相同。 |',
        '| H05 | 0x201FEBE4 / 8 | Stage2l 静态空 details；v32 owned 用空 details，默认恢复官方指针并到 0x201FEBEC。 |',
        '| H06 | 0x202BE24C / 4 | 活动 8 门限保留；v32 默认到 0x202BE250，owned 到 0x202BE6A8，转 A4。 |',
        '| H07 | 0x202871D8 / 4 | 默认 push LR 后到 0x202871DC；自有关闭/保持返回原 caller，补齐 Stage2l hide/overlay 收尾。 |',
        '| H08 | 0x202BB968 / 4 | 活动 8 门限保留；v32 默认到 0x202BB96C，owned 到 0x202BCF58；行号减 1 交引擎。 |',
        '| H09 | 0x2017098C / 4 | 与 Stage2l 同一 sender；默认 push LR 后到 0x20170990，颗粒门见第 4 节。 |','',
        '最终桩地址与逐点比较保存在 [patch-manifest.json](local/patch-manifest.json)、[hooks.json](local/hooks.json)、[hook-comparison.json](local/hook-comparison.json)。H06 的自有 r8=0、Stage2l 为 2，仍是原有策略差异；没有据此声称全部按键语义相同。','',
        '| 边界 | Stage2l | v32 |','|---|---|---|',
        '| 配方列表 native 首/末 | 1 / 16 | 1 / 16；引擎内部 0 / 15。 |',
        '| H01/H02 | 原生 1 基 | 发布时内部 cursor 加 1。 |',
        '| H08 | 原生 1 基 | 校验 1..rows 后减 1；0、17 拒绝，不进入原厂 setter。 |',
        '| A4 数值页 | 无此页 | native 1/6/11，内部 0/5/10，数值 -5/0/+5。 |','',
        '## 8. 已核实、推断与未知：栈和恢复','',
        '已核实：第三轮审查已把栈降为可恢复条件下的设备实测项；本轮独立复核栈研究的 227 项摘要通过。没有新增私有栈或改变 PSW。最终 `.su` 与 ELF 静态模型如下，原生任务 6 的栈按已核实研究为 16 KiB。','',
        '| Hook | v32 已建模增量 B | Stage2l B |','|---|---:|---:|'
    ]
    for r in stack['rows']:lines.append(f'| H{r["hook"]:02} | {r["candidate_modeled_peak"]} | {r["stage2l_modeled_peak"]} |')
    lines += [
        '', '这些数未闭合全部 native callee、异步/中断与实际峰值。增量高于 Stage2l，但不再沿用旧版“不得超过 Stage2l”的单独阻断；verify.py 保留比较并退出 0。本批未新增入口 SP 记录器，入口水位也不能单独证明完整峰值。','',
        '推断：固定数组准入、撤回仅访问两个固定字段，可消除 F08 的堆数组释放/同址复用时序；依据是准入拒绝、旧代码负对照和最终指令检查，未新增设备时序证据。','',
        '未知：真实 native UI 生命周期、原生剩余堆、深层 RPC/文件/绘制开销、完整任务栈峰值、照片效果、休眠/USB/换单元及 RAM 损坏后更新菜单是否仍可达。root 整体丢失仍会丢掉一次加载和恢复记录。没有新增独立 boot/service 救援链，产品安装 IROM 后单删卡文件不足以禁用。','',
        '## 9. 刷机后第一步检查清单，按第三轮审查 §9 分阶段恢复','',
        '供后续映像独立审查并另行授权刷机后人工执行，本轮没有执行。','',
        '1. 确认卡和 IROM 两槽都没有 GXRCE 引擎。冷启动先别进 ADJ，也别装 full。先看版本，进官方更新界面，再取消回来，先确认恢复入口能走通。',
        '2. 现在才测原厂七项 ADJ，试首项、末项、确认、取消、Fn2 和关闭重开。有一处不对，就先关机，必要时断电，移除卡上扩展后冷启动，别继续触发它。',
        '3. 拍一张并回放，再试休眠/唤醒、USB 接断和正常关机。关机后换 28mm、Mount，各自重做版本/更新取消、七项 ADJ、拍摄回放。空文件阶段没过就停下。',
        '4. 通过后先用不写 IROM 的只读探针。按第三轮审查另审带入口 SP 记录的容器，记同次开机的 base/end、task ID、PSW.SM、build、hook/phase、最小入口 SP 与样本数。普通 LIFE/NOTICE/VIEW 不是这份 SP 记录。',
        '5. 探针有异常就去掉卡上探针并冷启动，先别开 ADJ，直接进设置刷回已验证官方包；这个阶段 IROM 必须一直为空。',
        '6. 先亲自证明能用原生入口清空/禁用 IROM，或能绕过扩展进设置刷回官方，再测 full/A4/持久化。主机格式化用例只是清空 IROM double，不能当作真机格式化一定清得掉。写过 IROM 后只移卡不够。',
        '7. 产品阶段再测 01/16、full 的 05/06/09/10、A4 上下/换参数/OK 保存/MENU 取消/强制退出、冷启动与 IROM 回退。前一阶段正常且恢复办法已验证，才往下走。',
        '8. 冷启动后仍进不了设置/更新，就停止继续触发扩展。现有证据没有另一条已验证自主救援链，不能把过去一次菜单回退当作此时一定能救。','',
        '## 10. 复跑与摘要','',
        '从仓库根执行；build.py 只生成 resident、服务归档与六份 local 容器。','',
        '```sh','/usr/bin/python3 -I -B firmware/resident_v32/build.py',
        '/usr/bin/python3 -I -B firmware/resident_v32/verify.py',
        '/usr/bin/python3 -I -B firmware/resident_v32/report.py',
        '/usr/bin/python3 -I -B firmware/resident_v32/checksums.py',
        '/usr/bin/python3 -I -B firmware/resident_v32/checksums.py --verify','```','',
        '可单独复跑 regression.py、policy_machine.py、full_checks.py。原夹具的固定地址、已删除字段和缺陷断言适配均保留在 `local/regression/*-port.patch`，未改原审查。F03 以最终入口已删除证明关闭，不假称运行已不存在的 post。','',
        '交付摘要见 [SHA256SUMS](SHA256SUMS)，保护输入见 [inputs-verification.json](local/inputs-verification.json)，相对 v31 的源码差异见 [v31-v32-source.patch](local/v31-v32-source.patch)。'
    ]
    (HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('WROTE REPORT.md: six containers, F08-F11 offline PASS; hardware untested')
if __name__=='__main__':main()
