"""Write the Chinese review report from final artifact receipts."""
from pathlib import Path
import json
import time

HERE=Path(__file__).resolve().parent

def read(name):
    path=HERE/name
    return json.loads(path.read_text()) if path.is_file() else {}

def main():
    if (HERE/'review_fix/start.json').is_file():
        import sys
        sys.path.insert(0,str(HERE))
        from review_fix_report import main as review_main
        return review_main()
    package=read('package.json');release=package['release']['dat_sha256'];test=package['test']['dat_sha256']
    jobs=read('queue-required.json');resume=read('resume.json');audit=read('evidence/final_audit.json')
    resume_peak=audit.get('maximum_concurrent_tests') if audit.get('started_ns',0)>=resume['started_ns'] else '待核对'
    receipts=[read('evidence/jobs/'+j['name']+'.json') for j in jobs]
    pending=[j['name'] for j,r in zip(jobs,receipts) if r.get('status')!='PASS' or r.get('dat_sha256')!=test]
    scheduling=read('interrupted-final.json').get('process_limit_violation',{})
    if audit.get('started_ns',0)<resume['started_ns']:pending.append('resume_final_audit')
    elif audit.get('maximum_concurrent_tests',99)>2:pending.append('resume_test_process_limit')
    for name in ('evidence/final_audit.json','cleanup.json'):
        status=read(name).get('status')
        if status!='PASS' and not (name=='evidence/final_audit.json' and status=='PARTIAL'):pending.append(name)
    if read('cleanup.json').get('ended_ns',0)<resume['started_ns']:pending.append('resume_cleanup')
    verdict='可以交复审' if not pending else '有缺陷'
    passed=lambda name:'通过' if read(name).get('status')=='PASS' else '待完成'
    eq=read('evidence/kv_equivalence.json');fmt=read('evidence/format_checks.json');parity=read('evidence/control_parity.json')
    predictions=read('evidence/final_predictions.json');fit=read('fit_results.json')
    name12_units=[]
    for unit in ('50mm','mount','28mm'):
        applied=read('evidence/apply-'+unit+'.json')
        if applied.get('status')=='PASS' and applied.get('dat_sha256')==test:
            frame=applied['effects'][5]['frame']
            assert '>Kodachrome25' in frame['labels'] and frame['rows']==8
            name12_units.append(unit)
    scores=[];quality=[]
    for row in predictions.get('effects',[]):
        scores.append(f"| {row['index']} | `{row['name']}` | {row['interpretation']} | {100*row['synthetic_holdout']['similarity']:.2f}% | {100*row['scene_holdout']['similarity']:.2f}% |")
        source=fit[row['index']-1];option=next(x for x in source['options'] if x['interpretation']==source['selected'])
        safety=option.get('sector_safety')
        if safety and not safety.get('passes'):quality.append(row['name'])
    locks=[read('evidence/lock-testcard-'+u+'.json') for u in ('50mm','mount')]
    lock_count=sum(x.get('cases',0) for x in locks)
    regressions=[read('evidence/regressions-'+u+'.json') for u in ('50mm','mount','28mm')]
    extra=read('evidence/review-service-six-matrix-mount.json')
    t0=[read('evidence/t0-'+u+'.json') for u in ('50mm','mount')]
    reg_count=sum(x.get('cases',0) for x in regressions)+(1 if extra.get('status')=='PASS' else 0)
    reg_seconds=sum(x.get('seconds',0) for x in regressions)+extra.get('seconds',0)
    artifact=read('evidence/artifacts.json');emu=read('evidence/emu_boot.json')
    native_rejections=sum(r.get('status')=='PASS' and r.get('final_dat_sha256')==test
                          for r in (read('evidence/'+p.name) for p in (HERE/'evidence').glob('reject-*.json')))
    text=f'''{verdict}

g152 离线实现，2026-11-01。机身为用户已有 v3.8，本次只更换 DAT。源码位于 `firmware/engine_v60_g152`；g150 源码和包保持只读。没有联网、Git 写操作、子代理、存储卡访问或刷机。本轮只做离线实现和验证，不代替实机验收。

当前最终摘要通过 {sum(r.get('status')=='PASS' and r.get('dat_sha256')==test for r in receipts)}/{len(jobs)} 个计划作业。本轮要求项及留给发布复审的范围见 [FINAL_GAPS.md](FINAL_GAPS.md)，完整机器记录见 `acceptance.json`。

续轮新增 21 个作业，即 19 个快组和两单元各一组缩减矩阵；其余 37 个沿用前轮同一最终 DAT 的回执，收尾审计再次核对其源文件、摘要和产物，没有把旧候选的通过项算入最终摘要。

## 最终候选与时间盒

前一候选 `159de059…` / `eb04787d…` 的 144 项锁忙和 30 项效果应用通过，但其后旧回归 `t-boot` 发现新增快照校验过严：原厂九行伴随启动 T=0 时，被目标效果专用的 C/D 尾值规则拒绝，选择 Default 后仍停在 T=0。原失败、已完成回执及两份 DAT 保留在 `local/earlier-candidate-159d`；它们不计为本报告最终摘要的通过项。

最终源码只把观测快照的行校验改为与目标效果 T/C/D 关系独立；T 仍只接受 0/2，行结构、二次读回、epoch 和归属仍须全部通过。正式效果区的校验没有放宽。原始 `t-boot` 用例未改，最终包的专项结果为：50mm {passed('evidence/t0-50mm.json')}，MOUNT {passed('evidence/t0-mount.json')}。

T=0 实际此前状态的 late-BUSY 补偿另测：50mm {passed('evidence/t0-late-50mm.json')}，MOUNT {passed('evidence/t0-late-mount.json')}。此组要求真实此前 T=0、九行和完整 S 在退出重开后保留。

第一轮为 02:47–08:47 UTC，续轮从 08:52:57 UTC 起约三小时。最终 DAT 没有再改。续轮按用户新要求先补齐 19 个快组，再跑 48 项测试卡缩减矩阵。旧候选完整 144 项已经全部通过；本次核对最终改动有没有破坏同一类路径。完整 144 项明确留给发布复审，本轮仍只用 Python 指令后端，未用仍在复审的 C 后端。范围依据见 `resume.json`，历史记录见 `CANDIDATE_HISTORY.json`。

前轮有一次明确违反进程约束：切队列时未检查停止失败，约 {scheduling.get('seconds',0):.3f} 秒出现 4 个测试进程；原记录保留在 `interrupted-final.json`，没有改写为通过。续轮改用单控制器文件锁，测试子进程继承租约，启动前检查存活进程；收到终止信号后等待子进程退出。四项独立调度夹具均通过。续轮按作业起止时间核对的最大并发为 {resume_peak}，测试子进程均 nice 10；快组全部退出后才启动缩减矩阵，交接证据见 `evidence/phase_handoff.json`。

## 包与尺寸

| 包 | 用户条目 | 效果 | DAT SHA256 |
|---|---:|---:|---|
| [发布包](../../firmware/package_v38_g152/MANIFEST.json) | 0 | 10 | `{release}` |
| [测试包](../../firmware/package_v38_g152_test/MANIFEST.json) | 3，与 g150 测试扩展逐字节相同 | 10 | `{test}` |

两个包的 29 个机身文件与 g150 逐字节相同；每包根目录附署名和许可文件，SD_ROOT 仅含原有机身文件与 DAT。完整校验表见本目录及两个包的 `SHA256SUMS`。冻结输入复核：{artifact.get('frozen_inputs_unchanged','待完成')} 项；补充复审输入：{artifact.get('review_inputs_unchanged','待完成')} 项。

| 项 | 最终值 B | 本次限制 B | 到本次限制的余量 B |
|---|---:|---:|---:|
| DAT 文件 | {package['release']['dat_bytes']} | 97,792 | {package['file_limit_headroom']} |
| 代码段 | {package['code_bytes']} | 65,536 | {package['code_margin']} |
| BSS | {package['bss_bytes']} | 按实际链接计入主请求 | — |
| 主请求 | {package['main_request']} | 107,612 | {package['main_limit_headroom']} |

M32R 对象核对 v3.8 的 session 为 1,104 B、固定开销为 7,504 B。主请求 = 7,504 + align4(DAT+BSS)。相对 108,124 B 预算参照，余 {package['main_margin']} B；相对 98,304 B 文件格式上限，余 {package['file_margin']} B，均超过规定的 512 B。BSS 比 g150 增加 {package['bss_bytes']-9152} B，已包含全部效果引用副本、Looks 状态和两套 14 B 文本数组，没有套用原型的 +110 B 估计。

K=32，GXFX 区 8,000 B，容量 C=8/48/32/32，实用 N=0/10/9/10，10 个效果全部装入，没有截去末尾效果。GXDP v2 头长 80 B；GXUI 保留 v1。

## g150 第 0 节 P1 与 P2

首次事务将实际九行与 T 读入快照，校验每行格式，再次读回逐字节比对，并核对 epoch 和归属。只有成功后才设置 `live_verified`。写 S 才遇 BUSY 时，完整写回这份实际快照并读回；成功才普通拒绝并清 uncertainty。捕获或补偿失败会锁存 `snapshot_fault` 与 uncertainty，明确进入 ERR，普通重试不能清掉。细节及证据边界见 [SNAPSHOT.md](SNAPSHOT.md)。

另修正了拒绝后退出/重开自动归一化 S 的路径。BUSY 拒绝会锁存实际 S 保留状态，新有效目标计算成功后才恢复同步；三种退出都不能把实际此前 WB=10 改成模板 WB=9。旧夹具允许这次差异，已收紧为逐字节相同，旧候选回执不计入本候选通过项。

复审的 `previous_state_checks.py` 已逐字复制到本目录 legacy。其 late 分支原本断言第三种状态出现；本轮要求该旧断言在原位置失败，并用正常合同断言真实 02 九行、T=2、S=4 保留。另测四种来源/目标的未建基线事务。该组的单元行和 S 是明确模型输入；效果目标在真实按键到达函数调用边界时提供，不预置 UI 或引擎变量。缩减锁忙矩阵另外使用真实方向键、OK 和原生退出入口建立确认态，二者范围分别记录。

旧 g150 复审所说的 10 个旧组失败，应分为 2 个旧 g139 对照、7 个旧期望、1 个继承的清理字段差异，不能写成 4+5+1。本报告的本轮计数从回执汇总，旧失败不改记通过。锁措辞为“本键首次 BUSY 后，不再尝试 S/记录”；空闲成功路径可以依次调用 op 6、op 2、op 5。

本目录 `legacy/g139_check.py` 页脚已从实际 `Camera.dat_path` 记录 DAT。多 DAT 组列出全部实际路径和摘要；`regressions.py` 也按实际创建的 Camera 记录，避免把固定默认 DAT 填进每组结果。

## 强制验收

| 项 | 最终回执及结果 |
|---|---|
| kv2 完整输入合同 | {passed('evidence/kv_equivalence.json')}；单控制 int16 {eq.get('int16_single_control_cases',0):,} 次，状态/52 B/拒绝不改输出；另有 {eq.get('api_boundary_rejections',0)} 个 API 边界和 201 个点尾拒绝。 |
| 组合性与最终字节 | [KV_EQUIVALENCE.md](KV_EQUIVALENCE.md)；完整点序列、元数据和不变的请求组合函数给出任意合法向量的证明。{eq.get('pair_extrema_cases',0):,} 次两两端点补充检查；{eq.get('final_552_cases',0):,} 次完整 552 B，包括九行、T、14 行与 CRC。保留“请求相同但基底改变”的灵敏度对照。 |
| 最终包回读 | 等价、格式、预测和 C/Python 回执绑定上述两份 DAT。独立 C/Python 整数对照 {parity.get('cases',0):,} 次。 |
| R3 与效果区拒收 | 形式解析 {passed('evidence/format_checks.json')}；{len(fmt.get('rejected',[]))} 个格式变体，{fmt.get('name_character_cases',0)} 个允许名字字符，{fmt.get('window_cases',0):,} 个窗口。本候选原生拒收完成 {native_rejections}/9，已完成组均断言原厂 7 行、S=0 写、单元 W=0。 |
| 四种切换锁忙 | 当前缩减版完成 {lock_count}/48 项；50mm、MOUNT 各 4×3×2=24 项。时序为按键前已忙、写 S 才忙、瞬时忙，分别 OK/半按退出并重开。两个独立 lock sample 另计，不覆盖这 48 项的回执；完整 144 项留给发布复审。 |
| 三单元十效果 | 50mm：{passed('evidence/apply-50mm.json')}；28mm：{passed('evidence/apply-28mm.json')}；MOUNT：{passed('evidence/apply-mount.json')}。每个效果比九行/T、完整 S、运行中 552 B；断电模型恢复 04。 |
| 8 行与名字 | 空列表 {passed('evidence/ui-empty-mount.json')}；49 行 {passed('evidence/ui-rows49-50mm.json')}；错误页专组 {passed('evidence/ui-error-mount.json')}；失归属 {passed('evidence/ui-ownership-50mm.json')}；12 个标点字符专组 {passed('evidence/ui-name12-50mm.json')}。本批实际 12 字符名字 Kodachrome25 已在 {len(name12_units)}/3 单元的原生列表回执中验证，含标记共 13 字符、物理 8 行。 |
| 微调与计算拒绝 | 50mm 正常微调 {passed('evidence/knobs-normal-50mm.json')}；MOUNT 正常微调 {passed('evidence/knobs-normal-mount.json')}；50mm 计算拒绝 {passed('evidence/knobs-refusal-50mm.json')}。受控基底组要求最终 M32R 在 W 前返回 −2，S、W、live/staging 均不变。 |
| 相关旧回归 | 选定组当前 {reg_count}/19 次用例执行，累计 {reg_seconds/60:.1f} 分钟子作业用时；此前 T=0 专项两次单列，不重复加入此数。99 个旧用例的选择见 [REGRESSION_SCOPE.md](REGRESSION_SCOPE.md)，81 组全量矩阵延期理由见 [CORE_REGRESSION_SCOPE.md](CORE_REGRESSION_SCOPE.md)。50mm/MOUNT 为主，28mm 抽样。 |
| 两次模拟器冷启动 | {passed('evidence/emu_boot.json')}；快速模式、GXR_EMULATOR_BATCH=1、显式输出目录，检查 batch_stats 和实际介质写调用。 |

R3 正式有效点区为 `[3664,7902)`，2,119 个存储剂量点、117 串；最大引用尾必须等于 7902，块长必须等于 align4(7902)=7904，两个填充字节全零，引用区间并集必须覆盖整个有效区。R2 标记被本版拒收。正常区共享完整串，生成器与独立严格读取器都检查引用。

效果头 CRC 和区域 CRC 在相机入口校验；表项内容 CRC 按设计作为效果身份，电脑严格读取器另重算其内容。两者的校验范围分别记录。

主机 C 比较只作为算法/格式参考。相机路径测试均为 `tools/native_harness` Python 指令后端，执行最终 M32R 与原生构造器，记录 host UI 写入为 0，没有使用 C 后端替代。测试子进程均 nice 10；续轮单控制器和子进程租约守住全局 2 个测试进程上限，前轮 4 进程事件单列保留。控制器按完成事件等待，无后台 sleep 轮询。每组回执记录开始/结束、耗时、DAT、脚本摘要及产物生成时间。

正常基底的 15,050 个数学样本均成功，没有观察到 −2。原生拒绝专项使用满足行格式的受控零 Y 基底，最终候选的执行状态以上表为准；它用于检查 −2 在真实 W 之前返回且不改输出，不能解释为所有生产效果的十维组合都不会返回 −2。

## 电脑预测相似度与署名

以下为最终 DAT 编码行重新计算的留出集结果，定义为 `1−median(预测对目标 ΔE00)/median(04 对目标 ΔE00)`，表示相对 04 的误差改善，不能解释为实机百分比还原率。模型为 50mm ISO 200；没有独立的 28mm/MOUNT 画质标定。

| 序 | 名称 | 输入解释 | 合成留出 | 场景留出 |
|---|---|---|---:|---:|
{chr(10).join(scores)}

七个 Fotufilm 来源均使用本地 `_srgb.cube`，比较 after04 与 scene 后选择。求解器 `Problem.quantize` 的整数结果保存在 `local/fits`，矩阵 row/row2 共 56 B；没有从浮点预测反推行。CRC 与分数均按最终编码行重算。Tri-X 使用 03 的 96 B 全零 C080，保留自己的量化矩阵；直接按最终系数计算，两个留出集均严格 R=G=B。三单元实际写入也核对该行全零。所有新效果 A14/B14 分别等于 A5/B5。MOUNT 用 50mm 拟合行，自己的 04 与 pin 保留。

扇区模型检查未通过的效果为：{', '.join(quality) if quality else '无'}。这些量化行保留求解器原结果，具体扇区指标见 `fit_results.json`；该画质限制没有用模型名称或均值分数隐藏。原测量模型自身也有非单调区，实机照片仍待发布复审安排。

Fotufilm，https://fotufilm.com，Copyright 2026 MUAStudio Inc.。Tri-X 400、Portra 400、Velvia 50、Kodachrome25、Vision3 500T、instax mini、Metropolis 的派生整数效果数据按 CC BY-SA 4.0 提供，由 GXR project 从本地 sRGB LUT 适配；许可为 https://creativecommons.org/licenses/by-sa/4.0/ 。署名、来源摘要、修改说明写在报告与包清单，DAT 内没有长许可文本。M9 STD、HNCS HiCon、HNCS LowSat 只按用户本地文件处理，没有扩大其分发许可。10 个原始 LUT 未改动、未执行，副本位于被忽略的 `local/luts`。

## 复审 2 对照

| 编号 | 落实 |
|---|---|
| P1-R2-01 | 有效尾/对齐/零填充/全引用覆盖进入正式解析器；格式与原生零写拒收分别留回执。 |
| P1-R2-02 | 1 全 int16；2 完整点序列与组合证明；3 同 stock/base 完整 552 B；4 最终包回读并绑定 DAT 摘要。计算拒绝另走真实 W 前路径验证。 |
| P2-R2-01 | 用最终链接 BSS 和三项尺寸核对 K=32；保持 512 B 余量，没有扩大主请求。 |
| P2-R2-02 | 正式识别 R3，拒绝 R2；CRC、空洞、末尾填充、越界、共享区间和长度公式分别测试。 |
| P2-R2-03 | g150 复审的新 P1 已在本候选修正；没有改动或替 g150 宣告放行。冻结输入身份另查。 |

## 复审 1 的 P2 对照

| 编号 | 落实 |
|---|---|
| P2-01 | 仅 v3.8；固定开销 7504，session 1104。没有用此数给 v3.9 出包。 |
| P2-02 | 12 B 定长名限长复制补 NUL；显示行为 1+12+1=14 B，12 个允许标点的原生页面另测。 |
| P2-03 | KvUiFrame.text 与 adapter.text 均为 8×14；复制、清零、局部数组、服务长度同步改，短常量按 NUL 限长读取。 |
| P2-04 | 文本服务源长最多 13、紧跟 NUL；每行字形区 70 B，超过最长文本所需的 27 B，冻结 resident 快照为 96 B。LCD 实拍不在本轮。 |
| P2-05 | 先用实际段长验证 FX 头/偏移/总长公式，再看 CRC、索引与行规则，错误整体拒收。 |
| P2-06 | 实际文件、代码、BSS、主请求同时检查；两项预算余量均超过 512 B。 |
| P2-07 | K 计全局 32 项，B 容量 48，只多 16 条，不能据此承诺一半 T1；本批没有新增 T1 条目。 |
| P2-08 | GXUI v1 保留，效果不写成长用户条目或内置恢复记录；不实施 GXUI v2。 |
| P2-09 | 代数 152，gate/eng_data/ui_v2_data 与打包条件同步；EngRecipeRef 56 B 的构造/比较/确认/恢复覆盖效果号与内容 CRC。四种切换单测。 |
| P2-10 | 堆观察器已撤下，本候选没有此功能，也没有观察结果驱动放行入口。 |
| P2-11 | 没有把估计的指令/毫秒或保存任务栈水位当菜单证明；回执耗时只表示本机测试用时。 |

## 交复审前自查

按 CHECKLIST_NEUTRAL 的类别逐项检查：

以下结构检查与运行验收分开看。最终摘要的运行结果以上方强制验收表和 FINAL_GAPS 为准；没有完成的入口仍留给发布复审。

| 类别 | 本轮检查与边界 |
|---|---|
| 平台与进程 | 中性用语扫描；任务目录和唯一 Scratch；前轮并发事件保留，续轮互斥与起止时间另验；结束检查本任务进程并清 Scratch。 |
| 两条结果路径 | R2/R3 与 C/Python 都比最终完整字节；不用预测函数代替相机写入参考。Studio 图像 UI 不在本次改动。 |
| 归属与重入 | 真实菜单建立状态；失归属后恢复原厂 7 行，继承的四个清理字段单列；不能把原厂 7 行算作自有帧。 |
| 指针寿命 | 效果名先限长复制，服务接收自有持久 14 B 行；FX 视图只指向已整体验证的 DAT。 |
| 夹具预置 | UI/引擎变量不预置；S/单元实际行/锁/明确请求参数属于记录的模型输入；每组有 native UI 写入来源审计。 |
| 原厂时机 | 原生构造器、按键和退出函数执行；实际机身与 RTOS、28mm 首次开机时间线未知。 |
| 验收与旧期望 | 99 个旧组逐条说明本轮选择或留给发布复审的理由；旧失败、设置错误、被替代候选分别保留。 |
| 未核实状态 | 新增 live_verified 与 snapshot_fault；未建基线不再把 04 模板当真实此前状态。 |
| 未知尾部/相邻字节 | 完整 S 比较；首尾未知记录字节抽样；奇地址行只复制自有字节，深层写入保留相邻字节。 |
| 原厂续接 | 两个包机身完全相同；完整 S 和退出重开单测，不以主机退出函数返回成功代替 S 比较。 |
| 8 行 | 空、49 行、错误、过渡、退出、失归属和长名；同时测试正式窗口函数和原生发布。 |
| 打不开/失败提示 | 新块任一格式错误整体拒收；快照或补偿失败进 ERR 并保留 uncertainty。存储服务未增加。 |
| 返回值与锁 | 比实际目标计划；BUSY 后本键停止 S/记录重试；九行/T 补偿成功才普通拒绝。 |
| 有界工作与资源 | K≤48、C≤127、固定区长；R3 覆盖循环最多 201 轮；正式包实际 K32 且符合三项限制。 |
| 断电 | 效果 selector=1，清已知内置记忆，断电模型是纯 04；没有保存效果为用户条目 v2。 |
| 三个单元与现场变量 | 三单元全部十效果，50mm/MOUNT 锁忙主测；28mm 旧回归抽样；没有实机照片或存储卡操作。 |

必答：本轮改变 DAT 的数据解码、菜单和配方事务，不改变机身。原生构造器先初始化列表与归属，再执行自有绑定；主机不提前写 UI 指针，也不替换原厂 getter。效果首次事务的边界参数组已单独说明，不能称为物理 Looks 导航证明。

## 仍待发布复审的边界

本轮未上机。主机 M32R 通过不能证明真实 LCD 截字、预览延时、RPC 传输时序、RTOS 并发或 28mm 冷启动第一次打开的时机。50mm 模型也不能成为 MOUNT/28mm 的独立画质标定。

CHECKLIST 提到的真实 ISO100 单元分支和 `rpc_ready=0` 的开机首次打开，本轮未测，留给发布复审。前者工具不执行单元固件分支，本轮只核对编码的 14=5；后者属于冻结机身的启动时序，不能从 ready=1 的构造器通过推出。

失归属场景保留 g150/冻结机身的四个清理字段写入；持续通信错误可能留下部分单元行，但必须显示 ERR 并保留不确定状态。原有失归属时 S 待写边界另留给发布复审，没有改成普通完整状态通过。

批量模拟器仅验证官方 MAIN 的两个冷启动、挂载边界和合成介质零写入；它不执行 ADJ 内的 DAT 路径。使用已有 DCIM 的已初始化合成介质并核对来源摘要，首次准备数据发生在计量前；两次计量均要求实际写调用为 0、整个镜像不变。模拟器结论不替代 native_harness 的 DAT 执行。
'''
    (HERE/'REPORT.md').write_text(text)
    summary=dict(verdict=verdict,pending=pending,dat_sha256=release,test_dat_sha256=test,required_jobs=len(jobs),
                 passing_jobs=sum(r.get('status')=='PASS' and r.get('dat_sha256')==test for r in receipts),
                 lock_cases=lock_count,regression_cases=reg_count,regression_child_seconds=reg_seconds,generated_ns=time.time_ns())
    summary.update(dedicated_t0_cases=sum(x.get('status')=='PASS' for x in t0),
                   lock_sample_cases=sum(read('evidence/lock-matrix-'+u+'.json').get('cases',0) for u in ('50mm','mount')),
                   resume_maximum_concurrent_tests=resume_peak,full_lock_matrix_deferred=144)
    summary['name12_actual_units']=name12_units
    (HERE/'acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
