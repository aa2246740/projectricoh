"""Write the Chinese decision from independently checked review evidence."""
from pathlib import Path
import datetime,json

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
def read(relative):return json.loads((OUT/relative).read_text())
def link(label,relative,line=None):return '['+label+']('+str(ROOT/relative)+(':'+str(line) if line else '')+')'
def own(label,relative):return link(label,'research/review_harness_c_switch_r2/'+relative)

def main():
    d=read('evidence/final-data.json');stored=d['stored'];before=d['before_five']
    probe=read('subprocess-identity-v2/summary.json')['results'][0]
    rows={r['case']:r for r in probe['records']}
    initial_receipt=rows['initial']['receipt_sha256']
    report=f'''修改后再采用

r4 的原导出身份和写事件漏调用问题已修复，但 P1-02 仍有缺口：子进程导入的模块变化后，续跑复用旧 PASS。另发现 P1-04：相同校验失败生成的完整错误产品不同。两项都触及本轮一致性门槛，阻断正式采用。

本报告只判断本机主机回归工具是否可采用。全部检查离线执行，不涉及相机和存储卡，不作固件 DAT 的设备验收结论。

## P1-02 未关闭：子进程模块变化后仍复用旧 PASS

正式 `driver` 入口运行两指令包模型，r0 为 7；测试再启动 Python 子进程，子进程导入 `expectation.py` 核对该值。只把该模块的 `EXPECTED=7` 改成 8，测试本体、子进程脚本、参数、队列和运行名都不变。

| 同一测试的运行方式 | 入口退出码 | 保存结论 | 保存的 expected |
| --- | ---: | --- | ---: |
| 初次 C | 0 | PASS | 7 |
| 相同输入 C 续跑 | 0 | PASS | 7 |
| 模块改为 8 后，C 同名续跑 | 0 | 旧 PASS | 7 |
| 当前模块，新目录 Python | 1 | FAIL | 8 |
| 当前模块，新目录 C | 1 | FAIL | 8 |
| 模块恢复为 7，C 同名续跑 | 0 | PASS | 7 |

变化前后旧收据 SHA256 一直为 `{initial_receipt}`。子进程脚本本身被记录，导入的 `expectation.py` 没有被记录。两侧新目录的 FAIL 产品逐字节相同，SHA256 为 `{d['fresh_fail_products']['python']['sha256']}`，错误消息为 `child register expectation differs`。新 C 实际执行两个原生指令包；旧收据的非零计数不能证明续跑执行过当前断言。

根因在 {link('input_trace.py', 'tools/speedlab/host_regression_r4/run/input_trace.py',57)}：父进程仅记录子进程可执行文件和 argv 中的文件；结束时只遍历自身 `sys.modules`。`backend_launch.py` 没有为任意 driver 的后续子进程安装记录器，{link('run.py', 'tools/speedlab/host_regression_r4/run.py',114)} 收集到父进程的完整收据便允许续用，没有要求后代读取证据完整。

这是上一轮 P1-02 的同类变体。第二套新目录及最终带新 tag 的复跑均得到同一结果。应收齐子进程的依赖身份，无法覆盖的子进程应拒绝复用旧成功结果；只记录启动参数不足以关闭问题。

证据：{own('首次有效汇总','subprocess-identity-v2/summary.json')}、{own('新 tag 复跑','subprocess-repeat-final-repeat/summary.json')}、{own('原始日志','evidence/subprocess-v2.log')}。

## 新 P1-04：正式入口的完整错误产品不同

复跑上一轮未捕获的 `WriteEvent` 校验错误。Python 和 C 都退出 1，都是 `AssertionError('write event validation stopped')`；专项比较中的调用、寄存器、完整映射内存及错误后状态一致。但正式入口保存的 `error-case-.json` 不同：Python 的 `location` 有 9 帧，C 有 10 帧。

C 在 {link('backend.py', 'tools/speedlab/harness_release_r4/ccore/backend.py',366)} 转入 `_python_loop`，错误产品多出这一层调用，`call` 的位置也由原 Python 第 291 行变为 C 适配器第 366 行。仅统一运行目录名称后仍不同；再统一两份基础后端源码路径，帧数、函数名和行号仍不同。

用字典更新并绑定 `functools.partial(validate)` 的新变体也得到 9 对 10 帧。带新 tag 的独立复跑再次确认。该差异改变的是交付器保存的错误产品；本轮门槛没有允许排除 `error/location`，不能只用相同错误类型和消息判作一致。

应让正式入口为相同失败生成与原 Python 相同的错误产品，并把完整错误 JSON 纳入固定门槛。证据：{own('完整错误逐字段比较','evidence/error-product-comparison.json')}、{own('原用例入口结果','event-entry/summary.json')}、{own('partial 变体入口结果','event-entry-variant/summary.json')}、{own('新 tag 复跑','error-product-repeat-sealed/summary.json')}。逐文件原始 SHA 保留在比较证据中。

## 上一轮三项 P1 和新增变体

| 上一轮项目 | 本轮结果 |
| --- | --- |
| P1-01，g139 锁忙变为 FAIL | 原 reporter 断言完整保留，两侧均为 OBSERVED_P1；8,265 个值一致，各执行 20,932,506 个指令包。导出类模块均为 `python_backend`。关闭该反例。 |
| P1-02，改测试本体后复用旧 PASS | 原复审脚本现拒绝复用，当前输入的新 Python/C 都 FAIL；正式参数和 driver 形式各 11 项修复检查通过。但上文子进程模块变体仍复用旧 PASS，整体未关闭。 |
| P1-03，WriteEvent 改绑定后漏调用或漏错误 | 原五项名称解析检查、两项校验抛错控制均一致；原来的 C 通过、Python 失败现象已消失。完整错误产品的剩余差异单列为 P1-04。 |

自己补跑的 MOUNT `unverified-late` 使用 `research/review_g150/previous_state_checks.py` 复制件，原断言和 reporter 保留。两侧均为 OBSERVED_P1，13,644 个值一致，各执行 25,741,581 个指令包，RPC、文件调用、S 区和单元行均按完整产品核对，没有把观察状态改成 PASS。

新增七种事件名称处理方式全部一致：字典更新、partial、可调用对象、可调用对象抛错、删除模块名称后从 builtins 解析、名称缺失、先实际快速写再改成会抛错的 partial。另复跑五项构造函数及写后变更、六项先过滤后改变审计依赖，均一致。

实际编译临时 API6 库，仅关闭事件名称检查，重新出现 Python FAIL、C PASS；比较器检测到差异，关闭快速过滤的控制仍一致。正常候选库未改动。该临时库 SHA256 为 `94979dd1bb18f219a29e1555941b82d65650544f406abf76e6d02ff4c92d3013`。

证据：{own('g139 完整产品比较','busy/comparison.json')}、{own('g150 变体比较','observation/comparison.json')}、{own('原测试本体反例','identity-args-r2/summary.json')}、{own('七项事件变体','event-variants/summary.json')}、{own('构造函数检查','entry/local/repair-events/summary.json')}、{own('实际变异控制','mutation/summary.json')}。

## 额外真实回归

补跑 r4 原 20 组以外的三组，保持完整组内循环、切点、断言和步数上限。两侧使用独立产品目录和私有 Scratch，全部新运行名，不复用旧收据。每个真实组的超时均为 10,800 秒，大于历史时长三倍。

| 完整回归组 | Python 墙钟秒 | C 墙钟秒 | Python CPU 秒 | C CPU 秒 | 每侧指令包 |
| --- | ---: | ---: | ---: | ---: | ---: |
'''
    for r in d['real_groups']:
        t=r['timing']
        report+=f"| {r['job']} | {t['python']['wall_seconds']:.3f} | {t['c']['wall_seconds']:.3f} | {t['python']['cpu_seconds']:.3f} | {t['c']['cpu_seconds']:.3f} | {r['packets']['python']:,} |\n"
    report+=f'''
三组共 67 份验收 JSON、133,190 个值一致，各侧 92,447,052 个指令包；C 原生执行量相同，正常组回退计数为 0。状态、断言数据、S 区、单元行和调用顺序均比较类型和值，仅单列包装结果根 `/seconds`。计时包含入口身份核对和实际测试，不含随后比较；每侧一次观测，不认证稳定倍率。

50mm labels 首次复制件的路径长度不同，参考库链接地址及部分指令字节随之改变；该次全部验收 JSON 已一致，但未计作参考库代码一致。另用等长独立路径完整双跑，验收产品及参考库代码、常量节均一致，上表采用补跑结果。全部原始库 SHA、节数据和首次比较失败保留；不宣称两份 Mach-O 整库逐字节相同。

证据：{own('MOUNT half 比较','comparisons/real/group126-mount-half.json')}、{own('28mm nested 比较','comparisons/real/group126-28mm-nested.json')}、{own('50mm labels 等长路径比较','comparisons/labels/group124+126-50mm-labels-g139.json')}、{own('完整运行收据','real/complete.json')}、{own('labels 补跑收据','real-labels-equal/complete.json')}。

## r4 留存 20 组和提速数据

独立读回最终严格记录器的产品和每进程收据，20 组加前置工具共 {stored['json_files']:,} 份 JSON、{stored['compared_values']:,} 个值一致。20 组本身各侧执行 {stored['packets_each_side']:,} 个指令包，C 原生数量相同，正常组无回退。来源依赖逐项核对实际 SHA，参考库另核对构建身份、数量、代码和常量节。

| 已存单次观测 | Python | 最终 C | 比值 |
| --- | ---: | ---: | ---: |
| 20 组墙钟秒 | {stored['timing']['wall_seconds']['python']:.3f} | {stored['timing']['wall_seconds']['c']:.3f} | {stored['ratios']['wall_seconds']:.4f} |
| 20 组子进程树 CPU 秒 | {stored['timing']['cpu_seconds']['python']:.3f} | {stored['timing']['cpu_seconds']['c']:.3f} | {stored['ratios']['cpu_seconds']:.4f} |

修复前五组也重新比较了完整产品，174 份 JSON、601,716 个值一致，各侧 336,337,630 个指令包。读实际测量收据复算，同一批 Python 墙钟为 3,129.046 秒，API5 C 为 482.624 秒，最终 API6 C 为 482.926 秒，倍率为 6.4834 和 {d['five_after_wall_ratio']:.4f}；C CPU 为 468.517 和 466.408 秒。

实现者的倍率算术成立。计时覆盖实际测试，执行量和产物也成立；未包含随后归档、产品比较和完整入口调度复核的全部耗时。每侧只有一次观测，最终 C 又在严格记录器修复后补跑，存在采样时段和主机负载差异，不能据此证明稳定的 6.82 倍，或把 +0.06% 墙钟变化归因于修复。完整 81 组尚未运行，倍率不能外推。

证据：{own('独立 20 组复核','comparisons/stored/summary.json')}、{own('独立五组修复前复核','comparisons/before/summary.json')}。

## 开关、回退和 SWITCH_CHECKLIST

默认及显式 Python 确实选择原 `tools/native_harness`；直接控制样本与原 Python 产品逐字节一致。正式入口的默认、显式 Python 和显式 C 产品也逐字节一致；正常 C 为 API6，实际执行两个原生指令包。缺清单、缺库、ABI、API、源码 SHA 和库 SHA 不符均明确失败。API 不符使用实际编译的 API4 库验证，没有静默选 Python。

显式 C 的构建身份失败和运行期间方法变化的 Python 回退是两条不同路径。事件依赖变化时，本轮核对了回退后的调用、异常和完整模型状态，完整错误产品的差异仍按 P1-04 保留。

产品树按运行名隔离，同名改后端会拒绝恢复。P2-01：原 {link('legacy_call.py','tools/speedlab/host_regression_r4/run/legacy_call.py',24)} 的 Scratch 仍固定为 `speed-hillclimb/legacy/<job>`，没有包含运行名；不同新名称仍会共用临时路径。本轮真实双跑为复制件另外分配了私有 Scratch，不能把这一点当作原入口已经隔离全部临时状态的证明。

`SWITCH_CHECKLIST.md` 已更新，加入 OBSERVED/FAIL、输入身份、事件名称、实际执行量和后续 81 组要求；目前仍不足。第 3 项需要增加子进程依赖变更且必须拒用旧 PASS 的固定门槛，第 5 项必须比较正式入口完整错误 JSON，第 2 项需要明确临时状态也按运行名隔离。已有“每进程收据”措辞不能替代后代进程覆盖检查。

证据：{own('12 项直接开关控制','controls/switch/summary.json')}、{own('正式入口控制及 worker 错误','entry-controls/verified-summary.json')}、{link('当前切换清单','tools/speedlab/host_regression_r4/SWITCH_CHECKLIST.md',5)}。

## 冻结输入、执行边界和复跑

仓库根为 `{ROOT}`。外置卷已核对为可写 APFS，UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。

| 输入 | SHA256 |
| --- | --- |
| r4 SHA256SUMS，27,802 项 | `{d['initial_manifest']['manifest_sha256']}` |
| 正常 API6 库 | `{d['library_sha256']}` |
'''
    labels={'tools/native_harness/python_backend.py':'原 Python 后端','firmware/package_v38_g139/local/SD_ROOT/GXRCE.DAT':'g139 锁忙 DAT','firmware/package_v38_g150/local/SD_ROOT/GXRCE.DAT':'g150 回归 DAT','firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT':'g150 unverified-late DAT'}
    for path,digest in d['input_identities'].items():report+=f"| {labels[path]} | `{digest}` |\n"
    elapsed=(datetime.datetime.fromisoformat(d['ended_utc'])-datetime.datetime.fromisoformat(d['started_utc'])).total_seconds()/60
    report+=f'''
开始和收尾的 27,802 项均全部匹配，清单本身 SHA 未变。原 Python 工具与已放行批量模拟器的 {d['protected_files']:,} 项文件/符号链接收尾均与本轮基线一致，另核对 {d['copied_external_sources_verified']} 条复制来源记录。受保护工具目录基线在短检查之后采集；此前测试子进程同样受只读规则限制，没有把较晚采样说成任务开始时的全目录快照。

只写本报告目录和指定 Scratch。测试子进程使用 {own('本机离线写入规则','fence.sb')}，禁止网络和其他卷读取，写入仅限这两处及 `/dev/null`。未作 Git 写操作，未启动子代理。模型、编译和比较按批等待退出后继续，计算入口 nice 15，保留运行器再次降低优先级后的 worker 为 nice 20；真实组和锁忙组均使用 10,800 秒超时。开场最多五条只读资料查询曾并发提交，作为流程偏差保留；未将其表述为全程所有命令均严格串行。

准备失败保留且未计作通过：首份复制件解码缓存被旧 research 路径映射，改到私有 Scratch 后用新名称重跑；首版额外子进程脚本的 legacy 控制未形成有效产品，结论使用 driver 形式的独立重复；API 控制的首版核对器只查调度日志，读回 worker 日志后确认 `C core API differs`；labels 路径长度问题已如前补跑；新增错误复跑脚本在 `-I` 下首次缺少本目录导入路径，修正后用新 tag 复跑。原失败日志及收据全部保留。

测试和输入复核数据封存于 `{d['ended_utc']}`，距开始约 {elapsed:.1f} 分钟，自己的计算进程均已退出。Scratch 保留用于独立复跑。未重跑完整 81 组，也未重录 Python/C 的全量 CPU/每次写入 tape；本轮结论绑定上述验收产品和专项状态。

下面命令均在仓库根执行，tag 必须使用未出现过的新值。第一个脚本退出 1 表示已再次确认续跑差异，读取其 `summary.json` 的 `stale_pass_reused`；第二个读取 `complete_error_equal` 和帧数。

```sh
nice -n 15 /usr/bin/sandbox-exec -f research/review_harness_c_switch_r2/fence.sb /usr/bin/python3 -I -B research/review_harness_c_switch_r2/replay_subprocess_identity.py --tag review-next
nice -n 15 /usr/bin/sandbox-exec -f research/review_harness_c_switch_r2/fence.sb /usr/bin/python3 -I -B research/review_harness_c_switch_r2/replay_error_product.py --tag review-next
```

冻结输入及收尾收据：{own('开始校验','evidence/input-initial.json')}、{own('结束校验','evidence/input-final.json')}、{own('原工具收尾校验','evidence/protected-after.json')}、{own('计算进程收尾','evidence/cleanup.json')}。交付 `SHA256SUMS` 覆盖最终报告、复跑脚本和保留证据，路径相对仓库根。
'''
    (OUT/'REVIEW.md').write_text(report)
    print(json.dumps({'report':str(OUT/'REVIEW.md'),'characters':len(report),'lines':len(report.splitlines())}))

if __name__=='__main__':main()
