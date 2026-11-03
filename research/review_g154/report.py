"""从本轮回执生成复审结论，缺失的必查项明确保留。"""
from pathlib import Path
import datetime
import hashlib
import json

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'


def read(name):return json.loads((E/(name+'.json')).read_text())


def signature(case):
    return [(f['step'],f['sample']['frame']['cur'],f['sample']['frame']['physical'],
             f['sample']['native']['a'],f['sample']['native']['b'],f['sample']['native']['cache'],
             f['sample']['native']['rows'],f['parent_tag'],f['entries']) for f in case['frames']]


def main():
    comparisons=[]
    for unit in ('50mm','mount'):
        suffix='-r2' if unit=='50mm' else ''
        old=read('continuation-g153-'+unit+'-c'+suffix)['details']['cases']
        new=read('continuation-g154-'+unit+'-c'+suffix)['details']['cases']
        for a,b in zip(old,new):
            assert a['kind']==b['kind'] and signature(a)==signature(b)
            comparisons.append(dict(unit=unit,case=a['kind'],g153_g154_same=True))
    c=read('continuation-g154-50mm-c-r2')['details']['cases']
    p=read('continuation-g154-50mm-python')['details']['cases']
    for a,b in zip(c,p):assert signature(a)==signature(b)
    (E/'continuation-comparison.json').write_text(json.dumps(dict(cases=comparisons,python_50mm_same=True,
        python_mount_rerun=False),ensure_ascii=False,indent=2)+'\n')
    start=datetime.datetime.fromisoformat('2026-11-02T06:38:40+08:00')
    now=datetime.datetime.now().astimezone()
    jobs=[]
    for path in E.glob('*.json'):
        d=json.loads(path.read_text())
        if 'group' in d:jobs.append((d['started'],path,d))
    jobs.sort()
    rows=[]
    for _,path,d in jobs:
        result='PASS'
        if d['status']!='PASS':result='准备断言失败；修正后 Python 通过'
        elif d['group']=='continuation':
            result='颜色/S/单元写入检查 PASS；原厂续接仍 OPEN'
            if path.stem in ('continuation-g154-50mm-c','continuation-g153-50mm-c'):
                result='初版输入准备，保留；以 r2 为准'
        backend='主机 C 数学' if d['group']=='equality' else 'Python 静态' if d['group']=='static' else d['backend']
        wall=(datetime.datetime.fromisoformat(d['ended'])-datetime.datetime.fromisoformat(d['started'])).total_seconds()
        rows.append(f"| [{path.stem}](evidence/{path.name}) | {backend} | {d['seconds']:.3f} | {wall:.3f} | {result} |")
    text='''修改后再上卡

结论仅针对已装 `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d` 机身、只替换测试卡 DAT 的场景。测试文件为 `firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT`，SHA-256 `ac4263a0083aff1f04ab1433029b7ba354d67083ad09292f2af49bbc59abb83e`，三个用户条目。发布 DAT `3c63ae08a1387af9aa5c7d30107a17e37ec743b592c6f8833e70374e8b760449` 只作 19 行对照。

没有复现固件颜色或设置写入缺陷。阻断来自尚未闭合的必查复核，不要求先改二进制。

| 级别 | 发现与证据 | 最小修正 |
|---|---|---|
| P1-01，复审门槛 | MOUNT 的完整 keep=1 续接、原始半按后直接 part1 重显均保留 OPEN。本轮只完成 g154/g153 的 C 对照，未按任务要求用 Python 确认这两个非 PASS 观察。50mm 已有本轮 C/Python 一致证据，但不能把它写成 MOUNT 的 Python 结果。见 [对照](evidence/continuation-comparison.json)、两份 MOUNT continuation 回执。墙钟接近两小时，停止新增运行。 | 用本目录入口，在 Python 后端补跑 MOUNT 的 g154、g153 两条 continuation 作业；逐项确认九行/T、552 B、完整 S、单元 W 和事件序列。若仍只有与 g153 相同的高亮差异，关闭本项即可，无需重建 DAT。命令见文末。 |
| P2-01，继承 | 完整 keep=1 后父标记变 0，后续方向键没有 `ig_apply`。两单元的 g153/g154 机械状态序列相同；50mm 的 g154 又在 Python 相同。方向键会移动原厂高亮，DAT 逻辑行和预览仍停在原配方；本轮随后 OK 恢复七行、原游标 5，但缓存留 7。九行/T、完整 S、552 B 与单元 W 均不变。该路径不计入缓存 A 修正通过。 | 后续单独修原厂续接的事件可达性及关闭时序。本次保留此说明。MOUNT 的 Python 确认仍由 P1-01 阻断。 |
| P2-02，继承 | 原始半按后直接 part1 重显，逻辑行 8、物理行 6 保留，原厂游标和缓存变 2；DOWN/UP 变 3/2，DAT 行仍为 8。此后 OK/ADJ 的模型路径仍保留八行。两单元与 g153 相同；50mm 的 g154 在 Python 也相同。机主可能看到高亮与预览对应不上。所测各步完整配方、S 和 W 未变。 | 后续在原厂重显结束后同步高亮并复验原始键序列。此项按既有显示问题记录；MOUNT 的 Python 确认仍待 P1-01。 |
| P2-03，证据边界 | 没有接触相机或存储卡。LCD、物理键、真实拍照、RTOS/IRQ 交错、栈余量、FAT、NAND 与真实断电没有本轮证据；冻结 resident 在 DAT 入口之前自行撤回的缓存限制也未修。 | 在获准的设备阶段记录。主机 PASS 不代表这些层已通过。 |
| P3-01，流程 | 准备阶段把六条只读命令同批提交，未设 nice 10，没有记录实际同时运行峰值。其后原生作业串行、nice 10，运行超时 5400 秒。另保留一条静态脚本错误：把 DAT 头的原厂摘要等同完整修改机身摘要；修正后在 Python 通过。 | 后续准备检查也使用 nice 10 并限制同批数量。本轮后续已收紧；所有失败记录保留，收尾核对输入和临时目录。 |

关键核对结果如下。

| 项 | 证据与结论 |
|---|---|
| 八行与 13 字符 | 50mm/MOUNT 独立跑 19、22、49、41、9 个逻辑行的文件；所有监测到的自有发布均为 8 行，每行不超过 13 字符。卡片、逐项、数值及错误返回也保持八行。`adapter.c:336,341,359` 和 `engine_services/services.c:60` 双层限制。 |
| 数量边界 | `(U,K)=(30,10),(32,8)` 接受并达到 49 行；`(31,10),(32,10)` 整份拒收，原厂七行，完整 S 与单元行/T 不变，单元 W=0。`(32,0),(0,0)` 接受。3392 个窗口组合及 0/50/越界行输入均检查。MOUNT 另比较各容量末条用户配方的完整 552 B 与实际九行/T。 |
| 工具取最大 K | 独立改变可见位并更新校验，三单元 K 为 `[2,10,8]` 时上限 30，32 条拒收；K 为 `[2,8,0]` 时上限 32，32 条接受。运行时按当前单元的 K 检查；工具取三单元最大 K，二者职责不同。 |
| 新行 BUSY | 每单元四例，共八例：首个 Look 持锁、末个 Look 在 S 写入时遇忙、首个用户行在 S 写入时遇忙、末个用户行瞬时忙。前两类返回分别为 `op6=-2`、`op6=0/op2=-2`。持锁/瞬时忙无单元 W；晚忙补偿后逐字节等于实际此前九行/T、完整 4096 B S、56 B 引用与 552 B 台账。退出与重开仍相同，S store 为零。 |
| 跨退出快照 | 50mm/MOUNT 各四例，拒绝后关闭、实际此前改为 04/08、重开后晚忙，以及捕获期间行/T 变化。全部通过。`eng_core.c` 逐字节等于 g153，`expire_previous()` 在 apply 起止、开关页、失效和重绑定处使未建基线的资格失效。原始比较文件保留于 evidence/cross-*。 |
| 导航与旧索引 | 三单元分别抽查行 8/17/18/19/20/21/0，实际九行/T 和完整 552 B 与参照一致。50mm/MOUNT 的内置、Look、用户卡片进出与 `>`、`*` 通过。分组状态和跳转已删除；保留的 group 仅初始化一次，origin/entry_cur/look_cur 无读取，未发现剩余可达路径使用旧索引。 |
| 缓存 A 与 keep_view | 归属检查在 `cursor_cache()` 中；当前 Image 状态或本次快照地址检查、缓存 store 都在 `rv_irq_save/restore` 之间。两单元实际记录的 DAT 缓存 store 均为 IRQ 关闭状态。H07 读取错误经 finish→keep_view，在最后一次 list_bind 后写 home=5，返回 1 后 resident 恢复七行；原厂读取片段仍为 5。重画失败和用户末行正常关闭也通过。完整原厂 keep=1 与 part1 的 OPEN 单列，不算 A 通过。 |
| MOUNT B | 独立编译 g153/g154 查询与计算代码，从最终 DAT 比较三单元共 63 份完整 552 B。61 份相同。仅 MOUNT 用户第 2 条 `FCC*002`，Cont=1，变化 18 字节；第 3 条 `GRN*001`，Cont/High/Shad/Satu=2/5/5/-5，变化 78 字节。24 个内置默认值、30 个 Look 默认值及 MOUNT 04 全部相同，7904 B R3 原块相同。微调后的内置/Look 输出会按设计 B 改变，不能把“仅两条”扩展到全部旋钮状态。 |
| 身份 | 两包各 29 个非 DAT 文件逐字节等于 g153；22 个 resident/services 源文件相同。新测试 DAT 在 8233a1c4 装载。当前机身+g151 DAT、g151 机身+新 DAT、g151 机身+g153 DAT、v3.8 机身+新 DAT 均在 DAT 入口前拒收，七行、S/单元零写。g153 DAT 在同一 8233a1c4 机身仍正常装载，这是匹配组合。 |
| 包与尺寸 | 最终 DAT 代码段逐字节等于交付 ELF `.engine`。代码 64728 B，DAT 89624 B，BSS 9280 B，主请求 `7628+align4(89624+9280)=106532 B`，低于沿用 g153 的 107612 B 上限。 |
| 机主步骤 | OWNER_STEPS.md 为 9 行、5 步。已明确只换 DAT，说明平铺列表和微调返回，并有“移除 GXRCE.DAT、拔电池 10 秒、冷启动”的恢复步骤。步骤所指 SD_ROOT 副本确实存在，字节等于本次测试对象。 |

以下逐项对应 CHECKLIST_NEUTRAL.md。PASS 仅表示列出的层级和抽查范围。

| 主项 | 结果 | 核对与边界 |
|---|---|---|
| 1 流程、进程、中性文字 | P3 | 初始只读准备偏差见 P3-01；后续串行、nice 10，无子代理、网络、Git 写入或设备访问。 |
| 2 Studio 管线 | 不适用 | 未改或验收 Studio。 |
| 3 归属、重入、指针 | PASS，差量 | 核心与 services 不变；缓存写入重验归属；跨退出与错误关闭通过，未重跑全部重入矩阵。 |
| 4 模型与原生分开 | PASS，主机层 | ready/link、单元行/T、S、锁、原厂起始游标及设备叶子是模型输入。构造、发布、导航、关闭执行最终机器码。 |
| 5 原厂时机与隐藏路径 | OPEN | 两项继承观察见 P2-01/02，MOUNT Python 缺口见 P1-01。首次 ready、ISO100 与真实拍照时序未测。 |
| 6 范围、布局、完整回执 | 未完全闭合 | 使用 g154 布局和最终 DAT，所有已启动作业已退出；必需的 MOUNT Python 复核未完成。未把它计为 PASS。 |
| 7 真实基线、未知字节 | PASS，差量 | 实际此前状态和完整 S 逐字节比较；g152 快照修正保持，未知记录与邻接字节规则未改。 |
| 8 原厂续接、八行保护 | PASS/OPEN | 八行与 cap 抽查通过；完整原厂续接的功能观察单列 OPEN。 |
| 9 文件语义、FAT | PASS，差量 | 相机 I/O 路径未改；抽查无 create/write/rename/delete；真实 FAT 和 close 错误语义未测。 |
| 10 失败、退出与恢复 | PASS，所测路径 | BUSY、错误 close、重开及机主恢复文字通过；OPEN 路径不计为正常恢复通过。 |
| 11 物理键与显示 | 未上机 | 原始键消息仍是主机模型，不能证明物理键或 LCD。 |
| 12 返回值、锁与有界循环 | PASS，差量 | 新行锁返回明确断言；49 行、32 条和原 16 轮上界保留。 |
| 13 断电持久状态 | 沿用模型证据 | 读过实现方三单元 power 回执与未变核心；本轮未独立复跑真实断电或完整断电模型。 |
| 14 三单元 | PASS，主机抽查 | 三单元各七个导航点和 63 份输出；50mm/MOUNT 另跑 BUSY、cap、跨退出和缓存。28mm 未重复后四组。 |
| 15 现场变量与官方文件 | PASS，离线 | 明确绑定 body、DAT 和模型；29 个机身文件等于已审 g153。本轮不刷机，未重验官方 ZIP 或 NAND。 |

| 附节一 | 结果 | 核对 |
|---|---|---|
| A1 尺寸门槛 | PASS | 沿用 g153 的 107612/98304 B，不套用旧 g150 原型预算。 |
| A2 硬限与计划余量 | PASS | 报实际大小；代码余 808 B，不另加门槛。 |
| A3 共享代码与等价 | PASS | 核心相同，默认/已存完整输出和原生新行比较。 |
| A4 关闭标准 | 明确，未闭合 | P1-01 要求的两个 MOUNT Python 对照作业可直接复跑。 |
| A5 轮数与字节范围 | PASS | 有界输入；比较完整状态，不只计 W 次数。 |
| A6 先核实前提 | PASS | g153 同一机身是有效组合；DAT 原厂摘要与修改机身摘要已区分。 |
| A7 允许写入字段 | PASS，差量 | 新增缓存只用现有 0x205A2944，受归属、Image/快照、IRQ 条件限制。 |
| A8 原厂钳位 | PASS | home 采用 resident 保存并规范到 1..7 的 ui_restore[11]。 |
| A9 快照语义 | PASS | 不跨事务复用未建基线资格，不声称 RPC 原子快照。 |
| A10 导航记忆与图像设置 | PASS | 普通导航允许记忆记录；BUSY/退出明确比整个 S。未直接跨代比较包含 DAT CRC 的记忆字节。 |
| A11 冻结机身限制 | OPEN | 原厂续接及 resident 自行撤回不写成 DAT 修复通过。 |
| A12 测试卡与正式版 | 明确 | 本轮只判测试 DAT；未闭合必查复核仍阻断。 |
| A13 机主退路 | PASS | 移除 DAT、拔电池 10 秒、冷启动。 |
| A14 模型前提交接 | PASS | 入口、输入、后端、转换和源摘要留在脚本/回执。 |
| A15 分阶段与未跑项 | PASS | 已装机身，只换 DAT；所有未跑层单列。 |
| A16 中性文字、易读性 | PASS | 机主步骤短；复审文字采用中性工程用语。 |

| 附节二 | 结果 | 本轮边界 |
|---|---|---|
| B1 配方选择运行状态 | 仅主机 | 无相机时间线。 |
| B2 实际 open 返回 | 未测设备 | 文件叶子使用模型。 |
| B3 type 5 发布时间 | 仅主机 | 构造器执行，未测设备发布时间。 |
| B4 刷机单元与冷启动 | 未刷机 | 只读已有 8233a1c4 文件。 |
| B5 ISO100 特殊曲线 | 未上机 | 552 B 包含 ISO100 行，未跑真实链路和照片。 |
| B6 03 真实断电 | 未上机 | 未测掉电后照片或 S。 |
| B7 28mm 首次 ADJ | 未上机 | ready=0 的真实时间线未知。 |
| B8 Fn/ADJ/半按原始键码 | 仅模型 | 本轮不证明物理分发。 |
| B9 半按/拍照重显与 part 栈 | 部分主机、OPEN | 原始半按/part1 已比较；实际拍照未执行。 |
| B10 上电 RAM 初值 | 未上机 | 未采集真实上电残留。 |
| B11 H01/H07 RTOS 交错 | 未测设备 | IRQ store 观察不等于调度证明。 |
| B12 LCD/截字/延迟 | 未上机 | 只证文本长度和机器码发布。 |
| B13 RAW+JPEG 连拍 | 未上机 | 没有实拍文件。 |
| B14 原厂同名 FAT 项 | 未上卡 | 本次没有新增创建路径。 |

独立复跑如下。均前台等待。C 通过 `tools/native_harness_c/PythonBackend`、API 5 选择，`GXR_HARNESS_BACKEND=c`；Python 使用同一入口的 python 设置。没有指令计数门槛作业。超时 5400 秒，大于本轮引用的相关历史耗时三倍。

“执行秒”是回执的 monotonic 差；“墙钟秒”是起止时间差。后段两者明显不一致，不能把执行秒之和当成实际总用时。原因未核实，已据墙钟时间盒停止新增测试。

| 复跑 | 后端 | 执行秒 | 墙钟秒 | 结果 |
|---|---|---:|---:|---|
'''+ '\n'.join(rows)+'''

所有回执的退出码、PID、nice、输入摘要和转换说明均保留。初始静态失败不是固件失败；初版续接输入准备只作历史记录。源码、包和实现方证据没有修改。没有重跑实现方 872 项封存校验，只冻结并复核本轮所用的 354 个输入。

未独立完成：P1-01 的 MOUNT Python 复核、g153 的本轮 Python 续接对照、28mm 两项 OPEN，以及全部 144 锁忙、81 组旧回归、int16 全域、所有格式拒收、完整重入/切点、ISO100 全链和首次 ready 时序。物理层未检查项见附节二。本轮未重新构建 DAT，只验证最终 DAT 代码与交付 ELF 相同并执行最终 DAT。

关闭 P1-01 的最小复跑命令。使用新名称，继续遵守磁盘检查、指定 TMPDIR 和清理要求；两个作业串行执行。

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-g154-r1 GXR_HARNESS_BACKEND=python nice -n 10 sandbox-exec -f research/review_g154/offline.sb /usr/bin/python3 -I -B research/review_g154/run.py continuation --unit mount --name mount-python-followup
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/review-g154-r1 GXR_HARNESS_BACKEND=python nice -n 10 sandbox-exec -f research/review_g154/offline.sb /usr/bin/python3 -I -B research/review_g154/run.py continuation --unit mount --control --name mount-g153-python-followup
```

机主步骤已具备所需恢复方法；本轮不改该文件。临时目录清理、输入稳定性和进程收尾见 evidence/cleanup.json、evidence/inputs-after.json。
'''
    text+=f'\n本轮起始 {start.isoformat()}，报告生成 {now.isoformat()}，墙钟 {(now-start).total_seconds()/60:.1f} 分钟。最终收尾时间见 cleanup.json。\n'
    (HERE/'REVIEW.md').write_text(text)
    (E/'run-index.json').write_text(json.dumps([dict(file=str(path.relative_to(HERE)),**d) for _,path,d in jobs],ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(verdict=text.splitlines()[0],jobs=len(jobs),wall_minutes=(now-start).total_seconds()/60),ensure_ascii=False))


if __name__=='__main__':main()
