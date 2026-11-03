"""Write the Chinese review from actual final-DAT records."""
from pathlib import Path
import datetime
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT, DAT_SHA, START_UTC, DEADLINE_UTC
import collect
import analyze_results as analysis

UNITS=('50mm','28mm','mount')
NAMES=('对比','饱和','高光','阴影')

def read(name):
    path=OUT/name
    return json.loads(path.read_text()) if path.exists() else None

def state(name):
    value=read(name)
    return 'PASS' if value and value.get('status','').startswith('PASS') else 'INCOMPLETE'

def span(values):
    return str(values[0]) if values[0]==values[1] else str(values[0])+'–'+str(values[1])

def main():
    acceptance=collect.main()
    latency=analysis.latency()
    analysis.file_counters()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    lines=['不可以上卡。','',
        'P1-01 足以阻止本次上卡。H07 的原生同步返回后仍执行 resident 写入；同步期间重新进入 H01 也会写原生界面字段，题定三个前提均不成立。',
        '',
        f'审查对象是最终 gen 120b DAT `{DAT_SHA}`，59,128 B，generation 字段为 120。engine 为 `95e36cada1ff26a8a99300c0cf73abceab0a6a056d66bfcf3856221c0ca778e3`，49,576 B；ELF 为 `78486463e282d19966d75279d34aaf0b8630ddc798de14fd1c6dc11c0e8bb508`。采用用户已核验的卡包 30/30 与 28 个官方文件绑定。最终 DAT 的 engine 与 ELF 已逐字节核对。',
        '',
        f'时间盒为 {START_UTC} 至 {DEADLINE_UTC}；本报告生成于 {now}。只写本目录，没有构建固件、操作相机或实际存储卡，也没有联网或启动子代理。Python 均用 `/usr/bin/python3 -I -B`。',
        '',
        'P0：本轮已完成的检查未发现。P1-01 的证据与裁定如下。',
        '',
        '| H07 前提 | 裁定 | 证据 |',
        '| --- | --- | --- |',
        '| (a) 全部 resident / 引擎写入在进入 rv_close_07 前结束 | FAIL | 静态确认：`rv_close_07` 自身在原生调用返回后写 `0x2037F3BC=0`。 |',
        '| (b) 同一次 H07 在原生同步点后不再执行 resident / 引擎代码 | FAIL | 静态确认：`0x20052BFC` 的 `jl r0` 调用 `0x201C092C`，返回地址为 resident 的 `0x20052C00`。 |',
        '| (c) 同步期间重入不通信、不写原生界面字段 | FAIL | 电脑复放：三单元在同步状态执行官方完整 H01 构造器，`owned()=0` 仍进入 `ig_menu`，各有 5 次引擎界面写入。RPC / W / preview 均为 0。 |',
        '',
        '精确路径为 `0x20052BE8 → 0x201C092C → 0x201D83B0 → 0x201D79F4 → 0x2005FF88`。同步返回后，`0x20052C08` 指令包中的 `0x20052C0A` 将覆盖层地址 `0x2037F3BC` 清零，随后才恢复 LR 并返回。`rv_ui_abort` 已在进入该续程之前结束，但不能消除这次后置写入。',
        '',
        '| H01 重入时的写地址 | 写入 PC | 内容 |',
        '| --- | --- | --- |',
        '| `0x2022F726` | `0x2070FDF0` | 光标 04。 |',
        '| `0x2022F725` | `0x2070FDFC` | 小圆点 04。 |',
        '| `0x2022F5A8` | `0x2070FE3C` | 重新绑定八行列表指针。 |',
        '| `0x2022F5AC` | `0x2070FE4C` | 行数 8。 |',
        '| `0x205A2944` | `0x2070A5A0` | 光标缓存 04。 |',
        '',
        '同步状态由官方 part-1 构造分支、父页、配方列表和真实 H07 建立；未预置原生 UI 字段。H01 补例执行完整官方构造器，绘制和系统服务采用与主矩阵相同的模型边界。另逐一执行 H01/H02/H05/H06/H07/H08 的 resident 入口；H01 之外的入口正文观察到零通信、零界面写入，该结果不覆盖其后续原生续程。真实 RTOS 的交错及外层同步之后的完整显示收尾没有在相机上观察。',
        '',
        '关闭尾段的 44 个字节与 gen 117 基线包逐字节相同，原生同步点也没有新增。gen 117 冷开 OK 在 H07 内有 2 次 RPC、ADJ 为 0；本次 H07 配方段为零通信，减少了 OK 的通信让出机会。gen 117 的完整 H01 重入对照每单元有 4 次界面写入，最终 DAT 为 5 次，新增 `0x205A2944` 光标缓存写入，见 [对照记录](h07-sync-gen117-native-50mm.json)。同步后 resident 清零及 H01 归属缺口属于继承问题，本次又多触及一个缓存字段，按题定前提记 P1。',
        '',
        '证据：[关闭机器码](h07-close.txt)、[二进制绑定](h07-static.json)、[50mm](h07-sync-native-50mm.json)、[28mm](h07-sync-native-28mm.json)、[MOUNT](h07-sync-native-mount.json)、[gen117 退出对照](native/gen117-exits-50mm.json)。复放脚本为 [h07_review.py](h07_review.py) 与 [baseline_exits.py](baseline_exits.py)。',
        '',
        f'最终 DAT 的交互复跑记录为 {acceptance["completed"]}/{acceptance["required_records"]}。完整命令与记录哈希见 [acceptance.json](acceptance.json)。',
        '',
        '| 功能组 | 50mm | 28mm | MOUNT |',
        '| --- | --- | --- | --- |']
    groups=[('冷开 04、41 步导航、三种退出、补偿、Fn2 保留与模型冷启动','matrix'),
            ('gen117 a–h 全组','ah'),('H07 全状态零 RPC / W / preview','h07-all'),
            ('Fn2 四参数全部 RPC 点及 preview 点','fn2-four-parameters'),
            ('Fn2 OK / ADJ / 半按保留并重开','fn2-retain'),
            ('Fn2 短暂失败、纯 04 补偿、两类持续失败','fn2-failures'),
            ('原生半按与另一个快门分支','exits'),('keep=0/1 确认及 RPC 前圆点','confirm-paths'),
            ('两类锁定后的全部应用入口','latch-paths'),('八个新名称的原生绘制','names')]
    for title,group in groups:
        lines.append('| '+title+' | '+' | '.join(state('native/'+group+'-'+unit+'.json') for unit in UNITS)+' |')
    extension=[]
    for unit in UNITS:
        rows=[row for row in acceptance['records'] if unit in row['command'] and row['command'][0] in
              ('entry_switch.py','concurrent_menu.py','ui_cutpoints.py','coalescing.py','failure_boundaries.py')]
        extension.append('PASS' if len(rows)==15 and all(row['status'].startswith('PASS') for row in rows) else 'INCOMPLETE')
    lines.append('| gen119b 扩展回归，每单元 15 组 | '+' | '.join(extension)+' |')
    lines += ['',
        '矩阵含冷开 04、连续上下导航、ADJ / OK / 半按离开、短暂失败与完整补偿、补偿再次失败后的纯 04、Fn2 实时预览与保留重开；28mm 另含首次未 ready 的七行原生列表及 ready 后重开。并发回归保留 gen119b 的第 1/6/16/17/140 次 RPC 切换、两个 UI 末端切点、同页连续输入合并及 Fn2 打开时切换；逐例验证完整九行、T、模式与适用的 WB，且不写另一原生菜单。旧 a–h 日志中的 gen117 文字是用例标签，实际 DAT 哈希与 generation 断言均绑定最终 120。',
        '',
        'Fn2 全点检查从 05 的四个零微调参数分别调整一步，完整旧值与完整新值均来自官方路径执行后的全状态快照。每次 RPC 和 preview 边界构造另一个原生菜单，随后继续外层调用；检查结束时单元为完整旧值或完整新值，原生菜单七段内存没有迟到写入。这不表示顺序 W 事务的每个内部半字写入瞬间都是完整配色。',
        '',
        '| Fn2 参数 | 每单元正常一步 RPC | 每单元切换点 | 三单元完成情况 |',
        '| --- | ---: | ---: | --- |']
    for index,name in enumerate(NAMES):
        values=[read('native/fn2-four-parameters-'+unit+'.json') for unit in UNITS]
        present=[v['parameters'][index] for v in values if v and v.get('status')=='PASS']
        rpc=str(present[0]['reference']['RPC']) if present else 'INCOMPLETE'
        points=str(len(present[0]['points'])) if present else 'INCOMPLETE'
        lines.append('| '+name+' | '+rpc+' | '+points+' | '+str(len(present))+'/3 |')
    lines += ['',
        '运行前已搜索用例与夹具的直接写入和固定 getter，结果保存在 [fixture-scan.txt](fixture-scan.txt)。`0x20271FEC` 替身在首个构造器之前移除；没有给 `0x2022F71C`、光标、活动项或视图字段赋值。旧工具中的独立预置入口没有调用。a–h 的 d 场景只在官方构造后改变 resident 独立快照的 magic，作为损坏数据检查。除首次 50mm 矩阵外，后续运行均安装了 [runtime_guard.py](runtime_guard.py) 记录界面写入来源；首次 50mm 的实际脚本已逐行审阅。独立分支只复用整个官方构造后的进程快照，不拼装字段。',
        '',
        '锁定状态的要求按题定保护处理，不要求 H07 建立新确认。两类持续失败都必须保留 `n.failed=1`，H07 及初始化、Fn2、应用、面板事件与退出入口不得增加 RPC / W / preview；重新开页必须实际送出并绘制 `ERR POWER OFF/ON`。三单元执行状态见上表和 [锁定机器码](latch-static.json)。native ELF 不含 `ig_host_reset`；直接写锁定字节的两处都只写 1，初始化的已初始化分支也不清锁。常规入口没有解除路径，冷启动重新装载 BSS 才清除锁定。实体掉电是否复位单元未测。',
        '',
        '最终 DAT 的两条成功初始化请求均为 `0x000E0000`，与 loader 读能力合并后为 `0x000E7FFF`，不含文件写位。21 个文件调用点、固定 native bridges 和所有间接转移已列出；能力 CFG 排除了创建、删除和改名，write 还要求仅 create 能建立的写模式 token。真实最终 dispatcher 中 create / rename / delete / mark 返回 -12，只读 token 的 write 返回 -10，close 返回 0；重复初始化不打开写位。各已执行场景的文件变更计数全零。[静态切点](final-no-write-cutpoints.json)、[能力 CFG](file-gate-cfg.json)、[dispatcher 记录](machine-gates.json)、[计数汇总](zero-file-write-audit.json)。',
        '',
        'P2-01：作者第 6 节的“锐度/色调”是报告笔误。最终 DAT 参数 ID 为 `[1,2,3,4,5,6,0,0]`；面板只循环 1–4，依次是对比、饱和、高光、阴影，实际行名前缀为 `Cont / Satu / HiLt / Shad`。tone 计算使用对比、高光、阴影，饱和调用独立计算；没有锐度参数。原生行名与逐步计数的执行状态见 `native/fn2-step-counts-*.json`。[身份检查](parameter-identity.json)。',
        '',
        '新名称为 `01 GRPos / 02 GRNeg / 03 HC BW / 04 Std / 05 F-CC / 06 F-CN / 07 L-Chr / 08 L-Viv`。三单元八行均到达原生 ASCII 转换及字形提交，文本、编码和位置均匹配。左缘 x=38，最大宽度 98，最大右缘 136，小于下一列 x=219。字体度量来自已审计的官方资源；像素栅格与实体 LCD 未测。',
        '',
        'P2-02：正常列表移动在每次通信 2–3 ms 的假设下可超过 300 ms。按 tick=1 ms、每次 RPC 1–3 ms，等待为 RPC 次数乘通信耗时，逐项取整到 tick；不使用主机解释器耗时推算相机速度。',
        '',
        '| 操作 | RPC 次数 | 每次 1 ms | 每次 2 ms | 每次 3 ms |',
        '| --- | ---: | ---: | ---: | ---: |']
    move=latency['list_move']
    if move:
        lines.append('| 列表移动一格 | '+span(move['RPC'])+' | '+span(move['wait_ms']['1'])+' ms | '+span(move['wait_ms']['2'])+' ms，部分超过 300 | '+span(move['wait_ms']['3'])+' ms，全部超过 300 |')
    for index,name in enumerate(NAMES,1):
        value=latency['fn2'][str(index)]
        if value:lines.append('| 05 Fn2 '+name+'一步 | '+span(value['RPC'])+' | '+span(value['wait_ms']['1'])+' ms | '+span(value['wait_ms']['2'])+' ms | '+span(value['wait_ms']['3'])+' ms |')
        else:lines.append('| 05 Fn2 '+name+'一步 | INCOMPLETE | INCOMPLETE | INCOMPLETE | INCOMPLETE |')
    lines += ['',
        f'列表计数来自 {move["samples"] if move else 0} 次正常移动，覆盖 {len(latency["transitions"])} 种相邻行转换。每次 2 ms 时，RPC 大于 150 的转换超过 300 ms，逐行标记见 [latency-transitions.tsv](latency-transitions.tsv)。Fn2 计数限于 05、四参数各 20 个有效数值步；相机总延迟还要加 CPU、显示和调度。',
        '',
        '| 失败与补偿场景，沿用每次 1–3 ms 假设 | RPC 次数 | 通信等待 | 超过 300 ms |',
        '| --- | ---: | ---: | --- |']
    for label,value in latency['failures'].items():
        flag='每次 1 ms 即全部超过' if value['wait_ms']['1'][0]>300 else '3 ms 时存在超过' if value['wait_ms']['3'][1]>300 else '本计数范围内没有'
        titles={'fn2_after_W_continued':'Fn2 部分 W 后持续失败',
                'fn2_after_W_once':'Fn2 部分 W 后短暂失败并补偿',
                'fn2_before_W_continued':'Fn2 首次 W 前持续失败',
                'fn2_before_W_once':'Fn2 首次 W 前短暂失败并补偿',
                'fn2_fallback04':'Fn2 补偿再失败后纯 04',
                'list_cold_compensation':'列表冷开时短暂失败并补偿 04',
                'list_compensation_1':'列表第 16 次 RPC 失败，写入前返回',
                'list_compensation_2':'列表第 16 次 RPC 先执行再报错',
                'list_compensation_3':'列表第 140 次 RPC 先执行再报错',
                'list_fallback04':'列表补偿再失败后纯 04'}
        lines.append('| '+titles[label]+' | '+span(value['RPC'])+' | '+str(value['wait_ms']['1'][0])+'–'+str(value['wait_ms']['3'][1])+' ms | '+flag+' |')
    lines += ['',
        '失败场景的真实通信超时另计。建议保留零通信确认和完整读回，继续减少尚未 W 的重复预览，并在相机上量出实际方向键到画面更新的时间；本轮没有改实现。[计数与公式](latency.json)。',
        '',
        'P2-03：部分 W 后通信持续失败仍可留下混合单元 RAM。锁定与错误提示并不等于恢复成功；首次 W 前持续失败保留完整旧值。这是题定保护下的已知风险，不能据此声称实体关机后九行与 T 已恢复。',
        '',
        '相对 gen 117，已测试的实时预览事务增加了导航时的通信量与失败机会，也增加等待；Fn2 的通信返回归属保护、短暂失败完整补偿、首次 W 前错误提示和零通信确认降低了对应风险。配方颜色数据、文件写能力、机身与 resident 没有新增变更。H07 固定关闭问题仍在，不能用其他回归通过抵消。',
        '',
        '以上证据均来自电脑上的最终机器码、原生路径复放和静态检查。单元通信、文件服务、字体资源、绘制提交与部分系统服务仍为模型；功能复放保留已验证的 CRC 等价计算边界，原生 getter、事件、事务及写入检查执行真实指令。真实 RTOS 调度、LCD 中间帧、通信时间、物理掉电和重新开机后的九行 / T 仍需相机确认。编译改码闭合由另一审查员负责，本报告没有将其计为通过。',
        '',
        '输入前后核对见 `input-integrity.json` 与 `extra-input-integrity.json`；脚本来源与调整见 `script-provenance.json`、`review-script-changes.json` 和对应 patch。核心用例数量与预期值见 `feature-check.json`。中性用语检查见 `language-check.json`。`SHA256SUMS` 按惯例不含自身，覆盖其余全部普通文件，最终标准自检结果见 `checksum-selfcheck.json`。原始夹具诊断失败保留在日志和对应 case 中，没有计入验收通过。',
        '',
        '把卡上的 GXRCE.DAT 换回 gen 117（35ce20ac…）；若相机异常，用卡 A（Stage2l-50mm）挂 50mm，开机时按住“+”与回放键进入更新。',
        '']
    (OUT/'REVIEW.md').write_text('\n'.join(lines))
    print('WROTE REVIEW',acceptance['completed'],'/',acceptance['required_records'],flush=True)

if __name__=='__main__':main()
