#!/usr/bin/python3
"""Write the review from retained counts and independently checked evidence."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_g127'
PIN='9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'

def read(path,default=None):
    return json.loads(path.read_text()) if path.exists() else default

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--allow',action='store_true')
    args=parser.parse_args()
    r=read(OUT/'regressions.json')
    source=read(OUT/'source-audit.json')
    extra=read(OUT/'additional.json',[])
    remaining=[row['name'] for row in r['groups'] if row['status']!='PASS']
    extra_done=sum(row['status']=='PASS' for row in r['extra'])
    extra_bad=[row['name'] for row in extra if row['status']!='PASS']
    control=read(ROOT/'research/g127_fix/local/release127/review_g126/evidence/crc-native-ownership.json')
    h07=read(OUT/'evidence/h07-parent-native-50mm.json',{})
    residual=bool(h07.get('settings_stores_after_switch'))
    pending_path=OUT/'evidence/pending-read-native-50mm-reopened.json'
    pending_case=read(pending_path,{})
    first=pending_case.get('one_read_error_return',{})
    restored=pending_case.get('reopened',{})
    deferred=pending_case.get('after',{})
    query_errors=pending_case.get('settings_query_error',[])
    pending_lost=bool(query_errors and query_errors[0].get('restored') and
        query_errors[0].get('service_status',0)<0 and deferred.get('pending')==1 and first.get('pending')==0 and
        restored.get('pending')==0 and restored.get('rows')==8 and restored.get('mode')==1 and
        restored.get('previews',-1)==deferred.get('previews',-2) and
        not any(restored.get(key,1) for key in ('busy','uncertain','failed')))
    findings=[]
    if residual:
        witness=OUT/'evidence/h07-parent-native-50mm.json'
        findings.append(dict(id='P1-02',origin='inherited',status='OPEN',
            generation=127,dat_sha256=PIN,evidence=str(witness.relative_to(ROOT)),
            evidence_sha256=hashlib.sha256(witness.read_bytes()).hexdigest(),
            strict_owned=0,constructing_owned=1,settings_stores=len(h07['settings_stores_after_switch']),
            scope='M32R host model; RTOS reachability unverified'))
    if pending_lost:
        findings.append(dict(id='P2-05',origin='new',status='OPEN',generation=127,
            dat_sha256=PIN,evidence=str(pending_path.relative_to(ROOT)),
            evidence_sha256=hashlib.sha256(pending_path.read_bytes()).hexdigest(),
            scope='M32R host model; preview body and pixels unverified'))
    (OUT/'findings.json').write_text(json.dumps(findings,indent=2)+'\n')
    ready=(not remaining and extra_done==6 and not r['label_check']['bad'] and control
           and extra and not extra_bad and not residual and not pending_lost)
    if args.allow:
        assert ready
    verdict='可以上测试卡' if args.allow else '不可以上测试卡'
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    lines=[verdict,'',
        'P1-02 修复仍未闭合：H07 的父层重构切点中，严格归属为 0，服务层的构造期间归属却为 1，随后仍写 S。这是既有 P1-02 的残留，按继承问题列出，阻断本轮测试卡放行。即使常规回归全部通过，也不能关闭该定点正例。' if residual else '完整回归与补充控制仍需按本报告的结果表核对。',
        '',f'质量复审对象为 gen 127，DAT SHA256 `{PIN}`，58,772 B。引擎路径为 `firmware/engine_v48_own`，包的实际文件为 `firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT`。',
        '', '任务为 review-g127-r1。总时间盒为 2026-10-28 19:13:37 至 22:43:37 UTC；主矩阵截止 22:36，追加检查截止 22:42，其余时间用于汇总与最终校验。',
        '',f'当前 81 组中闭合 {r["groups_complete"]} 组，失败 {r["groups_failed"]} 组，未闭合 {len(remaining)} 组；history123 与 settings_cases 的六个附加单元闭合 {extra_done}/6。gen 122 历史记录保持 27 条 OBSERVED，逐条判断见 [历史表](HISTORY122.md)。',
        '', '本报告的原生执行指固定机身与最终 DAT 的 M32R 指令在主机模型中执行。设备与图形叶函数由模型承接。没有访问相机、存储卡或网络，没有启动子代理；不能把这些结果当作 LCD、拍摄、真实 RTOS 调度或实体断电验收。',
        '', '问题按严重度列出如下；继承问题的复现与边界在后文单列。未发现 P0。',
        '', '| 级别 | 标记 | 问题 | 当前状态 |',
        '| --- | --- | --- | --- |',
        '| P1-02 | 继承 | H07 父层重构后仍写 S | 主机已复现，修复未闭合，OPEN |',
        '| P1-01 | 继承 | 首次发布前的七行窗口 | 真实调度可达性未定，OPEN |',
        '| g127/P2-01 | 新，验证工具 | 重绑放宽两处 ASCII 断言 | 原上限独立补查无异常，工具未改 |',
        '| g127/P2-02 | 新，验证工具 | CRC 参数名称与实际路径相反 | 按实际回调计数核对，工具未改 |',
        '| P2-03 | 继承 | 最终归属核对后的预览窗口 | 主机已复现，OPEN |',
        '| g124/P2-01 | 继承 | 末端重绘窗口 | 引用既有指令证据，OPEN |',
        '| P2-04 | 继承 | 普通预览服务失败后的重开刷新 | gen 127 专门记录待核对 |',
        '', '## 本版问题与验证工具',
        '', '未发现新的固件 P0。原 g126/P1-02 的常见归属丢失切点已获得修复证据，但 H07 父层重构仍有晚到 S store，不能宣称 P1-02 已关闭。最末端预览窗口另按继承 P2 保留。超时和缺少结果不直接计为固件 FAIL。',
        '', '### g127/P2-01，新，重绑改变了两处 ASCII 断言上限',
        '', '`research/g127_fix/run_existing.py` 的 `target_code()` 递归把所有整数 126 改为 127。`research/review_g126/ui_test_support.py:34` 与 `:84` 的可打印字符上限也随之从 126 变成 127。断言指令没有被删除，但这两处语义变宽，因此不能称为完全忠实的重绑。',
        '', '复现方式是在仓库根分别运行下面两个控制；直接调用应返回 0，重绑调用应返回 1。第二个返回码是预期控制结果，不是固件用例失败。',
        '', '```sh',
        '/usr/bin/python3 -I -B research/review_g127/binding_probe.py',
        'TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/g127_fix/run_existing.py research/review_g127/binding_probe.py',
        '```',
        '',f'本轮以原上限 126 独立检查了记录中的标签，共 {r["label_check"]["strings"]} 次出现，包含重复值，异常 {len(r["label_check"]["bad"])} 个。最终固件 UI_TEXT 的字符边界也仍是 32 到 126，未受 Python 重绑影响。结构化检查详见 `regressions.json` 的 `label_check`。运行器未修改；本次已记录数据的补证与运行器自身修复是两件事。',
        '', '### g127/P2-02，新，CRC 参数名称与实际回调路径相反',
        '', '`--fast-crc` 在 boot 后设置 `Product.crc_fast=True`，底层 `accelerate_crc()` 遇到此值直接返回，主机 CRC 回调因此没有安装。去掉参数后，底层会在首次发布后安装主机 CRC 回调。三条独立设置恢复路径的结论相同。',
        '', '| 控制方式 | CRC 回调数 | 主机 CRC 调用数 | 原生入口访问数 | 设置恢复结论 |',
        '| --- | --- | --- | --- | --- |']
    for mode in ('flag','default','native'):
        data=read(OUT/f'evidence/crc-settings-{mode}-50mm.json')
        if data:
            c=data['crc_observation']
            lines.append(f'| {mode} | {c["callbacks"]} | {c["host_calls"]} | {c["entry_visits"]} | {data["status"]} |')
    lines+=['', '入口访问数包含首次装载及原生校验，不是性能数据。`flag` 对应设置参数后的状态，`default` 对应不设置该参数，`native` 显式保持原生 CRC。',
        '', '按题定要求，另用 `run_existing.py` 去掉 `--fast-crc`，在重开检查前移除自动安装的 CRC 回调，禁止重新安装，再执行原来的 `ownership_reopen` 断言。复现命令如下。',
        '', '```sh',
        'TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/g127_fix/run_existing.py --postcheck research/review_g127/crc_reopen.py research/review_g126/ownership_settings.py --generation 127 --unit 50mm',
        '```']
    if control:
        lines+=['',f'该次控制为 {control["status"]}：重开阶段原生 CRC 入口访问 {control["native_entry_visits"]} 次，主机回调调用 {control["host_calls"]} 次，回调剩余 {control["callbacks_after"]} 个；pending={control["pending"]}，mode={control["mode"]}。与有参数的归属及重开检查结论一致。']
    else:
        lines+=['', '该次追加控制尚未结束，不能仅凭去掉参数宣称全程使用原生 CRC。']
    lines+=['', '## 九个函数的独立复审',
        '',f'`source-audit.json` 独立核对了 9 个变化函数与 {len(source["unchanged_functions"])} 个保持不变的函数。DAT 内 47,236 B 引擎与 ELF `.engine` 完全相同，ELF SHA256 为 `13ecc74e2a23089fda0fbe6e694a3ce8cf74bc6233e357902e95b5c3cae12bae`。',
        '', '| 函数 | 结论 |', '| --- | --- |',
        '| eng_settings_owned | 选择当前列表或面板。H01 使用构造期间规则；H07、H06、H08 使用严格视图规则。 |',
        '| gxr2_tweak_layout | 仅把 3392 B 扩展布局的代号从 126 改为 127，既有长度和界限未放宽。 |',
        '| apply_impl | 九行和 T 的完成规则不变；首次检查发现失去归属时延后尾部、释放设置 token、清 busy；H07 服务二次核对的缺口见 P1-02。 |',
        '| eng_check_settings | 未归属时置 pending 并返回；归属恢复后清标记，再核对 S；即使 S 已匹配，保存的 pending 也会触发 apply 和预览。 |',
        '| eng_data_accept | 仅更新扩展布局的代号条件，仍要求其余段长和总长合法。 |',
        '| uv_validate | 仅更新版本 127，扩展 CRC、bank CRC、用户条目、范围和保留字节检查保持。 |',
        '| rv_settings_owned | 从当前会话重建 lease、view、source 与 rows，但固定使用构造期间规则；对 H07 过宽。 |',
        '| settings | op 2 的二次核对确实在 IRQ 保护区内，但沿用上述过宽规则，H07 父层切点仍可写 S。op 1 和 op 3 只取信息或释放 token。 |',
        '| rv_service | preview op 1 新增最终归属核对；核对至原生入口之间仍有指令窗口。 |',
        '', '`settings_pending` 在 apply 的两次引擎归属核对失败、服务返回 RV_STALE 且 freshness 仍成立并失去归属，以及 eng_check_settings 的入口归属失败时置 1。拥有归属的 apply 在设置写入前清 0；eng_check_settings 在 settings_match 之前清 0。正常延后会清 uncertain/write_started、释放设置 token、清 busy，并保留已完成的行数据账本，等待下一次 H01。H07 服务规则的残留另见 P1-02。',
        '', '这些新分支没有增加无界循环。epoch 失效与普通服务错误继续走既有失败边界，原补偿上限仍为四次当前配方、两次 04。设置读取失败发生在 pending 清零之后，源码不会当场恢复该标记；一次读取失败后的后续 H01 补充检查单独记录，不能只凭正常重开路径宣称所有失败分支都会补做预览。',
        '', '`apply_impl` 在深层处理前 disarm，pending 期间跳过 publish。成功补做尾部后才允许 publish。最终 DAT 三个单元的描述符均未启用 grain 位，因此本次运行中的 grain=0 不能代替启用 grain 配方后的功能验收；禁止发布的分支另由源码和最终 ELF 绑定核对。',
        '', '原生 Standard 04 规则保持不变，三个单元的 04 都要求 mode=1。正常 04 切点要求九行与 T 匹配、WB 为 9/9；模拟原厂输入留下 mode=5 时，正常持有归属的发布后核对会恢复为 1。原厂七行方向键主动选中其他选项时，不把原厂自身的设置变化记作 DAT 写入。',
        '', '归属丢失后的返回与重开状态、S 已匹配时的延后预览，以及一次设置读取失败后的状态，另保存在 [补充结果表](CONTROLS.md)。命令正常结束与切点后果分开计数，观察记录不会因返回码为 0 而变成固件 PASS。',
        '', '## 继承问题与边界',
        '', '### P1-02，继承，H07 父层重构后仍写 S，OPEN',
        '', '`eng_settings_owned()` 只有 H01 传 constructing=1；H07 使用 0。但服务层 `rv_settings_owned()` 固定传 1。H07 的引擎检查通过后、settings op 2 服务执行前，原生列表可先隐藏，再由原厂 `0x202856d0` 重建父层。此时只有 tag 32 父层，H07 的严格规则不认定归属，服务的 H01 例外却仍认定归属。',
        '', '源码还有一处同类差异：tag 33 路径在 constructing=1 时不要求 overlay=32。该差异由源码确认，本轮定点正例使用父层重构，没有把另一种视图形态也写成已复现。',
        '', '50mm 主机切点记录为 strict_owned=0、constructing_owned=1。随后 CPU 在 `0x2070f530` 写 `S+0x36e=1`，写前为 5；对应最终 ELF 的 `0xa65c`，是 settings 的 byte store 循环。没有晚到预览。返回后 busy=0、uncertain=0、failed=0、pending=1，说明标记在 S 已写入后才延后剩余尾部。',
        '', '```sh',
        'TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/native_checks.py --case h07-parent --unit 50mm',
        '```',
        '', '证据在 `evidence/h07-parent-native-50mm.json`，命令与时长在 `priority.json`。需让服务层在 IRQ 保护区内复核与当前入口一致的归属规则；H01 的构造例外不能用于 H07。单纯保留 IRQ 区间不能修正判定规则本身。gen 126 原服务没有归属检查，本例的后果不是 gen 127 新增；它说明本次修复没有覆盖这个变体。',
        '', '该正例仍使用第二个主机执行上下文运行原厂指令，没有建立真实 RTOS 调度链。因此这里只判定题定归属合同尚未守住，不给真机发生概率，也不把主机模型写成相机实测。观察型命令返回 0 只表示执行结束，不把这条 OBSERVED 正例改记为固件 PASS。',
        '', '### P1-01，继承，首次发布前的七行窗口，OPEN',
        '', '原 `review_g124` 的切点可在主机第二执行上下文中让原厂 setter 瞬时写 `S+0x36e`。gen 127 正常持有归属的发布后恢复已补上最终 04 核对，不能据此声称原厂瞬时写入消失。`research/reentry_reachability/REPORT.md` 对普通按键重叠切点的结论仍是未定、偏向不可达；它没有建立真实 RTOS 第二个普通按键消费者。',
        '', '复现观察路径为 `run_existing.py research/review_g126/cold_reentry.py --generation 127 --unit 50mm`，按本目录围栏和 TMPDIR 运行，查看发布前方向键案例中的原厂 store 与发布后的恢复。旧代的最终错误 mode 不直接当作 gen 127 的新问题。',
        '', '### P2-03，继承，最终归属核对之后仍可进入预览，OPEN',
        '', '最终 ELF 的 `rv_call+0x1488`，即引擎偏移 `0xa358`，检查归属返回值；`0xa35c` 设置预览参数 0；`0xa360` 调 `rv_native_preview`。在 `0xa35c` 切点，用第二个主机执行上下文运行原厂菜单转换，令 activity=7、overlay=21，外层仍会到达 `0x202d6f38`。',
        '', '`instruction-sites.json` 另把这些位置与最终 DAT 的实际指令字节绑定；恢复检查使用 `0xa354` 的归属函数调用前切点。',
        '', '| 单元 | 失去归属后的 S store | 失去归属后的预览入口 | 状态 |',
        '| --- | --- | --- | --- |']
    for unit in ('50mm','28mm','mount'):
        data=read(OUT/f'evidence/preview-window-native-{unit}.json')
        if data and data.get('status')=='OBSERVED':
            lines.append(f'| {unit} | {len(data["settings_stores_after_switch"])} | {len(data["preview_entries"])} | OBSERVED |')
        else:
            lines.append(f'| {unit} | 未结束 | 未结束 | INCOMPLETE |')
    lines+=['', '```sh',
        'TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/native_checks.py --case preview-window --unit 50mm',
        '```',
        '', '将单元换为 28mm 或 mount 可复查同一点。原生预览的最外层在固定参数 0 下还会准备一个原生请求结构并调用 `0x201709cc(0x8000, ...)`；本轮没有执行完整预览本体，不能给后续副作用设上限，也不能把它描述成只改像素。`local/preview-entry.asm` 保存该静态片段。',
        '', '这个窗口在 gen 126 的未检查路径中已经存在。gen 127 缩小了窗口，没有新增该调用后果，故列为继承项。切点中的第二执行上下文不是原厂 RTOS 调度正例；普通 task 6 串行处理会排除部分重叠情形，当前证据未穷尽其他执行者。',
        '', '### g124/P2-01，继承，末端重绘窗口，OPEN',
        '', '原 `review_g126/evidence/native-draw-consequences.json` 的八案显示：失去归属后进入旧行绘制器，并由原厂 PC `0x201fd392` 写全局 `0x205d4f64=0`。`ui_list` 和 `rv_view_owned` 源码在本版保持不变。本轮引用这些既有记录，没有宣称重新执行了该绘制本体。复现路径为 `run_existing.py research/review_g126/window_consequences.py --generation 127 --unit 50mm`。',
        '', '二者都是检查后、动作前的窗口。重绘项已有一处全局 store 的指令证据；预览项当前只证明未归属时进入预览，完整本体仍由模型承接，证据层级和已知后果不同。',
        '', '### P2-04，继承，普通预览服务失败后的重开刷新，待核对',
        '', 'gen 126 与 gen 124 的旧记录观察到 S 已恢复、下一次打开却没有补做失败的预览。gen 127 新标记只明确处理归属丢失的 RV_STALE，不把普通 RV_IO 自动记为 pending。本轮不因继承的错误分支还在就断言 gen 127 已复现全部旧后果。复现路径为 `run_existing.py research/review_g126/preview_reopen.py --generation 127 --unit 50mm`；未取得本版该专门记录时，保持未定。',
        '', '## 回归与历史记录',
        '', '完整 81 组及 history123、settings_cases 表在 [REGRESSIONS.md](REGRESSIONS.md)。有用例清单的组按 wait_status 计数；没有逐例清单的完整套件计 PASS 1，不把断言数或内部条目数当成用例数。nested 的十条、cutpoints 的八条已移除调用点记 NA。',
        '', 'gen 122 的全部 27 条仍为 OBSERVED，没有改为 PASS。部分行被改回原厂值时，gen 127 完整读回并恢复已确认 05，符合设计；恢复失败后撤下八行，后续键沿原厂七行处理，也符合撤下规则。原始半按与直接半按记录不证明拍摄完成。逐条依据和原始记录哈希在 [HISTORY122.md](HISTORY122.md) 与 `history122.json`。',
        '', '本轮使用自有 `write-fence.sb`，仅允许 `research/review_g127`、`research/g127_fix/local` 以及 `/dev/null` 写入，禁止网络。每组配置 4200 秒，直接调用各组入口，避免旧 batch 内部 1500 秒上限；TMPDIR 固定为题定目录。全局时间盒停止造成的未结束不记固件失败。',
        '', '执行偏差保留在 `queue-change.json`：重排队列时误启动第二调度器，短暂出现六组重叠；已停止两批未结束任务并重新排队，此后单调度器最多三组。该偏差不能描述成全程满足三进程上限。mount 的独立补充模型曾漏登记映像而返回 KeyError，修正后的补跑单列在 `additional.json`；这三条前置错误不计作固件失败。',
        '', '早期独立检查记录中的 output_counts 是输出字段词频，包含值为零的 FAIL 字段名，不能作为用例失败数。正式结果表以结构化状态为准。已有通过结果的八组沿用题定最终 DAT 证据；本轮运行命令、返回码和用时在 `runs.jsonl`，补充命令在 `additional.json`。',
        '', '另用退出事件提前运行 history123、settings_cases 的其余单元，记录在 `priority-batch-runs.jsonl`；活动验证命令总数仍最多三个。主协调器暂停启动和收集时，已有进程继续运行。主日志秒数是启动到收回结果的墙钟时间，包含这段收集等待；原验证的退出时刻保留在 `priority-batch.json`。已完成的同一 DAT 结果不被随后未启动或超时的重复排队项覆盖；真正的新非零退出仍保留。',
        '', '实现者旧依赖快照中的运行器哈希与其最终清单不同；当前运行器与最终 SHA256SUMS、本轮初始快照一致。这是旧快照差异，没有当作本轮源码漂移。输入最终对照见 `integrity.json`。允许更新的 local 结果已重新绑定，本轮不会声称旧的 13,055 项清单仍覆盖补跑后的所有可变记录。',
        '', 'SHA256SUMS 以仓库根为基准，覆盖本目录交付、选用的回归记录与本次输入身份文件；不包含清单自身。']
    if remaining:
        lines+=['', '未闭合组：','']+['- '+name+'。' for name in remaining]
    if extra_bad:
        lines+=['', '补充检查未闭合：','']+['- '+name+'。' for name in extra_bad]
    h07_rows=[]
    for unit in ('50mm','28mm','mount'):
        for kind in ('h07-parent','h07-parent-preview'):
            data=read(OUT/f'evidence/{kind}-native-{unit}.json',{})
            rebuilt=next((event for event in data.get('events',[]) if event.get('phase')=='parent_rebuilt'),None)
            if data.get('status')=='OBSERVED' and rebuilt:
                h07_rows.append((unit,kind,rebuilt,len(data['settings_stores_after_switch']),
                                 len(data['preview_entries']),data['after']['pending']))
    if h07_rows:
        details=['', '父层重构两种服务切点的实际观察：','',
            '| 单元 | 服务切点 | 严格归属 / 构造归属 | 晚到 S store | 晚到预览 | 返回 pending |',
            '| --- | --- | --- | --- | --- | --- |']
        for unit,kind,owned,stores,previews,pending in h07_rows:
            details.append(f'| {unit} | {kind} | {owned["strict_owned"]} / {owned["constructing_owned"]} | {stores} | {previews} | {pending} |')
        if any(row[1]=='h07-parent-preview' for row in h07_rows):
            details+=['', '这里的预览切点在服务层最终归属核对之前。服务仍因构造期间规则而接受预览；它属于 H07 规则错误，与后文核对完成后的末端窗口分开。']
        details+=['', '设置服务切点与预览服务切点分开运行。仅隐藏列表、未重建父层的早期控制不列入该表。','']
        index=lines.index('### P1-01，继承，首次发布前的七行窗口，OPEN')
        lines[index:index]=details
    if pending_lost:
        table_index=lines.index('| g127/P2-01 | 新，验证工具 | 重绑放宽两处 ASCII 断言 | 原上限独立补查无异常，工具未改 |')
        lines.insert(table_index,'| P2-05 | 新，固件 | 一次设置读取失败后丢失待补预览 | 主机已复现，OPEN |')
        detail=['### P2-05，新，一次设置读取失败后丢失待补预览，OPEN','',
            '先在最终归属检查前切换到另一菜单，预览尾部正确延后，S 已为 04 的 mode=1、pending=1。下一次 H01 在 settings_match 的 RV_SETTINGS op 1 入口暂时把设置元数据地址设为 0，让最终 DAT 的实际服务返回范围错误，并在返回时恢复地址。eng_check_settings 已先清 pending，错误返回后没有恢复它。再一次 H01 发布八行时，S 已匹配且 pending=0，因此不再请求预览。',
            '', f'实际记录：延后时 previews={deferred["previews"]}、pending=1；一次读取失败后 previews={first["previews"]}、pending={first["pending"]}；再开后 previews={restored["previews"]}、pending=0、rows=8、mode=1，busy/uncertain/failed 均为 0。没有永久锁定，但待补预览已丢失。',
            '', '```sh',
            'TMPDIR="$PWD/research/g127_fix/local/tmp" /usr/bin/sandbox-exec -f research/review_g127/write-fence.sb /usr/bin/python3 -I -B research/review_g127/native_checks.py --case pending-read --unit 50mm',
            '```',
            '', f'实际服务状态为 {query_errors[0]["service_status"]}，元数据已恢复。该命令的预览补做断言返回 1，属于行为失败。证据在 `evidence/pending-read-native-50mm-reopened.json`。预期返回 1 的 ASCII/断言控制另按控制结果计数。应在设置核对及补做成功后清标记，或在核对错误时保留待补状态。这个新问题由 gen 127 的延后路径产生，与普通 RV_IO 预览失败的继承项分开。此为主机元数据暂不可用的失败情形，未建立真机操作的可达链；完整预览本体与像素结果仍未验。','']
        index=lines.index('### g127/P2-01，新，重绑改变了两处 ASCII 断言上限')
        lines[index:index]=detail
        index=next(i for i,line in enumerate(lines) if line.startswith('当前 81 组中闭合'))
        lines[index]+=' 补充检查另复现一条新的预览待补状态丢失问题，见 P2-05。'
    normal=[]
    for unit in ('50mm','28mm','mount'):
        data=read(OUT/f'evidence/preview-deferred-native-{unit}.json',{})
        if data.get('status')=='PASS':
            normal.append(f'{unit} 预览增加 {data["reopened"]["previews"]-data["after"]["previews"]} 次、pending 从 {data["after"]["pending"]} 清为 {data["reopened"]["pending"]}')
    recovery=read(OUT/'evidence/pending-read-native-50mm.json',{})
    details=[]
    if normal:
        details+=['', 'S 已匹配时，延后预览的实际恢复结果：'+'；'.join(normal)+'。']
    if recovery.get('status')=='PASS':
        first_error=recovery['one_read_error_return']
        reopened=recovery['reopened']
        details+=['', f'一次设置查询失败情形也已通过：实际服务返回 {recovery["settings_query_error"][0]["service_status"]}，恢复元数据后，当次为 rows={first_error["rows"]}、pending={first_error["pending"]}、previews={first_error["previews"]}；下一次 H01 为 rows={reopened["rows"]}、pending={reopened["pending"]}、previews={reopened["previews"]}，busy/uncertain/failed 均为 0。本例先撤下再重建，仍补做了预览，没有把先清 pending 的静态疑点列为已复现问题。']
    if details:
        index=lines.index('## 继承问题与边界')
        lines[index:index]=details+['']
    lines+=['',f'汇总时间：{now}。']
    (OUT/'REVIEW.md').write_text('\n'.join(lines)+'\n')
    print(verdict,'groups',r['groups_complete'],'extra',extra_done,'additional',len(extra))

if __name__=='__main__':
    main()
