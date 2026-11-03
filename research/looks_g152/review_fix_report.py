"""Write the review-correction report using only the final DAT receipts."""
from pathlib import Path
import datetime,json,time
HERE=Path(__file__).resolve().parent
def read(name):
    p=HERE/name;return json.loads(p.read_text()) if p.is_file() else {}
def main():
    package=read('package.json');release=package['release']['dat_sha256'];test=package['test']['dat_sha256']
    jobs=read('queue-fix-required.json');audit=read('evidence/final_audit.json');build=read('review_fix/build.json')
    done=[];pending=[];child_seconds=0
    for job in jobs:
        r=read('evidence/jobs/'+job['name']+'.json')
        (done if r.get('status')=='PASS' and r.get('dat_sha256')==test else pending).append(job['name'])
        if r.get('status')=='PASS' and r.get('dat_sha256')==test:child_seconds+=r['seconds']
    if audit.get('status')!='PASS' or audit.get('test_dat_sha256')!=test or audit.get('started_ns',0)<build['ended_ns']:pending.append('final_audit')
    verdict='有缺陷' if pending else '可以交复审'
    regs=[read('evidence/regressions-'+u+'.json') for u in ('50mm','mount','28mm')]
    regs=[r for r in regs if r.get('status')=='PASS' and r.get('dat_sha256')==test]
    service=read('evidence/review-service-six-matrix-mount.json')
    service_ok=service.get('status')=='PASS' and service.get('dat_sha256')==test
    reg_count=sum(r['cases'] for r in regs)+int(service_ok)
    seconds=sum(r['seconds'] for r in regs)+(service.get('seconds',0) if service_ok else 0)
    def status(name):
        r=read(name)
        identities=(r.get('dat_sha256'),r.get('final_dat_sha256'),r.get('test_dat_sha256'))
        return '通过' if r.get('status')=='PASS' and any(v in (test,release) for v in identities) else '待完成'
    matrix=sum(read('evidence/lock-reviewfix-'+u+'.json').get('cases',0) for u in ('50mm','mount'))
    scores=[]
    for row in read('evidence/final_predictions.json').get('effects',[]):
        scores.append(f"| {row['index']} | `{row['name']}` | {row['interpretation']} | {100*row['synthetic_holdout']['similarity']:.2f}% | {100*row['scene_holdout']['similarity']:.2f}% |")
    changed=build['engine_changes'][0]['path']
    generated=time.time_ns();started=datetime.datetime(2026,11,1,12,35,42,tzinfo=datetime.timezone.utc).timestamp()
    wall_minutes=(generated/1e9-started)/60
    source=HERE/'local/review-fix-prior/research/looks_g152/REPORT.md'
    original=source.read_text();tail=original[original.index('## 复审 2 对照'):]
    tail=tail.replace('未建基线不再把 04 模板当真实此前状态。','未建基线每次事务重新捕获，事务结束及退出、重开、失归属时撤销资格；不把历史观测当当前事实。')
    tail=tail.replace('g150 复审的新 P1 已在本候选修正；','g150 原 P1 与 g152 快照有效期 P1 均按本报告复审修复节验证；')
    tail=tail.replace('必答：本轮改变 DAT 的数据解码、菜单和配方事务，不改变机身。','必答：g152 相对 g150 改变 DAT 的数据解码、菜单和配方事务；本次复审修复仅调整事务快照有效期，不改变机身。')
    text=f'''{verdict}

g152 复审修复，2026-11-01。用户已有 v3.8 机身，本次只更换 DAT。全程本机离线，没有访问存储卡、刷机、联网、Git 写操作或子代理。g150 源码和包保持只读。

本轮最终候选已通过 {len(done)}/{len(jobs)} 个计划作业；未完成要求见 [FINAL_GAPS.md](FINAL_GAPS.md)。旧候选 559 项清单和复审 153 项清单已逐项核对，旧报告、源码、DAT 与回执保存在 `local/review-fix-prior`。旧候选不能上卡的结论不改写；旧 DAT 的通过项不计作新 DAT 的执行结果。

## 复审修复

P1-01 的根因是未提交快照跨事务保留。`live_verified=1` 只能证明过去读过，不能证明仍是本次事务的实际此前状态。

本次把未建基线的快照限制在一次 `apply_impl` 内：开始时清除旧资格，每次重新读取实际九行和 T，验证行结构、二次读回、epoch 和归属；只有本次捕获成功才允许补偿。事务结束、退出、重开、失去归属、失效和重绑定边界都撤销未提交快照资格。写 S 才遇 BUSY 时写回本次快照，逐字节读回九行和 T；S 零写、完整 S 保持此前状态。捕获或补偿不可信则进入 ERR，保留 `snapshot_fault` 和 uncertainty。

同类状态也已检查：未建基线时的 `t_checked`、`t_pending`、`neighbor_valid` 同时过期；确认入口须已有配方基线；`validate_live` 不把未提交观测当配方台账。已验证的原厂基线即使尚未提交，也须在菜单重开时重新比对实际单元行。`s_busy` 按键重置；`s_refused` 是保留实际 S 的恢复策略，直到新有效选择才解除；它不提供任何行快照资格。当前/确认配方引用仅描述已提交配方，不从未知初态推定身份。详见 [SNAPSHOT.md](SNAPSHOT.md)。

供 g153 同步的引擎文件清单只有一项：

| 文件 | 修后 SHA256 |
|---|---|
| `{changed}` | `{build['engine_changes'][0]['new_sha256']}` |

精确文本差异见 [engine-change.diff](review_fix/engine-change.diff)，构建对应关系见 [build.json](review_fix/build.json)。其他引擎源文件、头文件、机身和数据表未改。测试、报告及打包清单的变动另列 [REVIEW_FIX_FILES.md](REVIEW_FIX_FILES.md)，不属于 g153 的引擎移植范围。

先用旧 DAT 原样复现 MOUNT 的两次事务反例，记录在 `review_fix/evidence/observed-mount-8.json`。新 DAT 分别覆盖 50mm/MOUNT、退出后变成 04/08 的四条原复审合同；复制源码逐字保留，仅把“首次拒绝后快照资格仍为 1”的内部断言更新为资格已撤销，物理状态合同加严到九行、T、完整 S 在按键和重开后相同。原文件摘要和实际执行文本摘要都保留。

同类变体另覆盖退出后变成效果、原生半按退出后模拟拍摄恢复单元行再打开、首次拒绝后再三次 late BUSY、最后成功（共四次拒绝）。拍摄组执行原生退出/重开，把关闭期间单元行恢复作为明确模型输入，并保持 epoch 不变；没有执行真实快门、照片写卡或单元 ISP。原 g150 非原厂首轮、T=0、快照变化时零写入及补偿失败 ERR 组都重跑，见 `review_fix/evidence` 与 `evidence/unverified-*`。

恢复成功后的完整 S 另由原始 S 见证和最终 DAT 的设置、40 B 记忆记录重算，并比较全部 4,096 B 的摘要及 56 B 当前引用；没有只用槽号或成功标志代替完整目标。最终审计的 `final_S_and_reference_checks` 保留六个变体的对应关系。

拍摄恢复夹具初版及其增加父界面调用的重试都停在“应立即为原厂 7 行”的前置断言，未进入后续单元行变化事务。旧锁忙夹具没有该即时 7 行假设；行数元数据不能用作半按后的归属证明。最终版 `review_fix_photo_v3.py` 沿用旧矩阵的两个原生半按处理入口，逐项检查九行/T、完整 S 和 W 不变、快照资格为 0，再按原流程模拟单元行恢复并重新构造菜单。只将错误的 7 行前提换为快照资格断言，所有后续 late BUSY、完整实际此前状态及成功断言均保留，并记录原/实际函数文本摘要。四条失败 JSON/日志不改写，新回执另存 `photo-final-*`，未把旧失败计入本轮通过数；准确清单见 `review_fix/fixture_revision.json` 和最终审计的 `retired_fixture_failures`。

P2-01 已修正正式 `format_checks.py`：只改变一个合法名称字节，保持效果头 CRC 和 DAT 外层 CRC 有效，让区 CRC 单独错误。仅修复 CRC 后三单元解析均有效；在临时主机参考解析器中只移除区 CRC 检查，错误块会被接受，证明夹具能够发现该检查缺失。正式 M32R 对该夹具仍要求原厂 7 行、S/单元零写。许可、画质和现场边界按复审第 4 节保留，没有扩大证据范围。

g150 复审的旧计数仍按 2 个旧 g139 对照、7 个旧期望、1 个继承清理字段差异记录，没有改写成 4+5+1。“本键首次 BUSY 后不再尝试 S/记录”与空闲路径允许 op 6、op 2、op 5 的顺序分别说明。`legacy/g139_check.py` 和本轮回归页脚继续从实际 `Camera.dat_path` 记录身份，双包组分别列源 DAT 与执行 DAT。

## 两包与尺寸

| 包 | 用户条目 | 效果 | DAT SHA256 |
|---|---:|---:|---|
| [发布包](../../firmware/package_v38_g152/MANIFEST.json) | 0 | 10 | `{release}` |
| [测试包](../../firmware/package_v38_g152_test/MANIFEST.json) | 3，与 g150 测试扩展相同 | 10 | `{test}` |

每包 29 个机身文件与 g150 逐字节相同。GXUI v1，K=32，效果区 8,000 B，容量 8/48/32/32，实际使用 0/10/9/10。R3、内置展开行和十个效果与复审候选逐字节相同；数学回执从这次最终包重新回读并绑定上述 SHA256。

| 项 | 最终值 B | 限制 B | 到限制的余量 B |
|---|---:|---:|---:|
| 文件 | {package['release']['dat_bytes']} | 97,792 | {package['file_limit_headroom']} |
| 代码段 | {package['code_bytes']} | 65,536 | {package['code_margin']} |
| BSS | {package['bss_bytes']} | 按实际链接计入 | — |
| 主请求 | {package['main_request']} | 107,612 | {package['main_limit_headroom']} |

v3.8 固定开销 7,504 B，session 1,104 B。主请求 = 7,504 + align4(DAT+BSS)。相对 108,124 B 预算参照还余 {package['main_margin']} B，相对 98,304 B 文件格式上限余 {package['file_margin']} B，两者均守住 512 B 余量。

## 最终候选验证

| 范围 | 结果与边界 |
|---|---|
| kv2 完整合同 | {status('evidence/kv_equivalence.json')}；3×8×10×65,536=15,728,640 个单控制输入；状态、52 B 请求、拒绝不改输出；组合性证明与 15,050 次完整 552 B。见 [KV_EQUIVALENCE.md](KV_EQUIVALENCE.md)。 |
| 整数与预测 | {status('evidence/control_parity.json')}；8,521 次 C/Python 完整整数对照。这里只用主机 C 作算法参考，相机路径仍是 Python 指令后端。 |
| R3 与效果拒收 | 形式解析 {status('evidence/format_checks.json')}；31 个格式变体、93 个名称字符、61,250 个窗口；9 个原生零写拒收全部按本轮队列执行，含已隔离的区 CRC。 |
| 三单元十效果 | 50mm {status('evidence/apply-50mm.json')}，MOUNT {status('evidence/apply-mount.json')}，28mm {status('evidence/apply-28mm.json')}；九行/T、完整 S、552 B 和黑白 C080 逐字节比较；A14/B14=各自 A5/B5，MOUNT 保留自己的原厂 04。 |
| 快照有效期 | 原复审 04/08 两次事务合同、效果/拍摄恢复/多次拒绝变体，以及首轮非原厂、T=0、捕获不稳定和补偿失败组，均以本轮队列实际回执为准。 |
| 锁忙矩阵 | 本轮完成 {matrix}/48；4 种切换×held/race-at-s/transient×OK/半按×50mm/MOUNT；所有原生回执绑定新 DAT。完整 144 项仍留给发布复审，旧候选的完整通过记录保留。 |
| 错误页与归属 | MOUNT 错误页 {status('evidence/ui-error-mount.json')}，50mm 失归属 {status('evidence/ui-ownership-50mm.json')}；自有帧恰好 8 行。空列表/49 行/标点长名组未重跑，理由逐项列在 REVIEW_FIX_SCOPE.md；三单元实际长名随十效果组重新验证。 |
| 旧回归 | 当前 {reg_count}/10 次执行，子作业累计 {seconds/60:.1f} 分钟；另有两次 T=0 专项不重复计数。99 条旧用例和 81 个全量组逐项范围见 REGRESSION_SCOPE.md / CORE_REGRESSION_SCOPE.md。 |
| 未重跑的已有组 | 两个正常微调组、独立身份组及相同机身的模拟器两次冷启动保留原回执，并列明不受本改动影响的依据。它们没有计入本轮 {len(jobs)} 作业；模拟器原本就不执行 DAT。 |

本轮时间盒约三小时，从 12:35:42 UTC 起。所有测试子进程经 `nice -n 10` 启动，同一时刻最多两个；本轮清点实测 NI=20，因为已为 NI=10 的控制器再次使用增量 10，命令和实际值分别保留在 `review_fix/evidence/process_priorities.json`。每批控制器正常退出后，文件租约和进程清点都确认前批已结束才切换。回执含起止时间、脚本/最终 DAT/日志摘要、产物生成时间。最终审计、报告、封存顺序执行；Scratch 在测试全部退出后清理。前轮 25.194 秒四进程事件和旧失败仍保留，没有改写为通过。

本次报告生成时，任务墙钟 {wall_minutes:.2f} 分钟；本轮计划中已通过作业累计 {child_seconds/60:.2f} 分钟子作业用时，旧 DAT 反例和四条初版夹具用时另计，它们仍参与本轮最大并发核对。逐项秒数和完整命令回执见 [RUNS.md](review_fix/RUNS.md)，并行作业的用时不能直接当墙钟相加。

## 电脑预测相似度与署名

以下分数按本次最终 DAT 编码行重算：`1−median(预测对目标 ΔE00)/median(04 对目标 ΔE00)`，表示相对 04 的误差改善，不是实机还原率。模型为 50mm ISO200，没有独立的 28mm/MOUNT 画质标定。

| 序 | 名称 | 输入解释 | 合成留出 | 场景留出 |
|---|---|---|---:|---:|
'''+ '\n'.join(scores)+'''

保留 `Problem.quantize` 的整数结果，按最终编码行计算预测和 CRC。Tri-X 使用 03 的 96 B 全零 C080；直接由编码系数得到严格 R=G=B，原生三单元也读回该零行。第 14 行等于第 5 行，MOUNT 使用 50mm 拟合行并保留自己的原厂 04。九个彩色效果的扇区模型限制仍见 fit_results.json，未以均值分数代替实拍。

Fotufilm，https://fotufilm.com，Copyright 2026 MUAStudio Inc.。七个 Fotufilm 派生整数效果按 CC BY-SA 4.0 提供，由 GXR project 从本地 sRGB LUT 适配；许可 https://creativecommons.org/licenses/by-sa/4.0/ 。署名、来源摘要和修改说明随报告及两包清单交付，DAT 内没有长文本。M9 STD、HNCS HiCon、HNCS LowSat 只按用户本地文件处理，没有扩大分发许可。原始 LUT 均未改动或执行。

'''+tail
    (HERE/'REPORT.md').write_text(text)
    result=dict(verdict=verdict,pending=pending,dat_sha256=release,test_dat_sha256=test,required_jobs=len(jobs),
                passing_jobs=len(done),lock_cases=matrix,regression_cases=reg_count,regression_child_seconds=seconds,
                maximum_concurrent_tests=audit.get('maximum_concurrent_tests') if audit.get('test_dat_sha256')==test else None,engine_changes=build['engine_changes'],task_wall_minutes=wall_minutes,accepted_child_seconds=child_seconds,generated_ns=generated)
    (HERE/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
