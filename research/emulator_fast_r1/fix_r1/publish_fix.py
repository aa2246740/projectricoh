"""Recompute the repair verdict from final receipts and produce its report."""
import datetime,hashlib,json,os,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=HERE.parent
FAST=ROOT/'tools/gxr_emulator_fast/fix_r1'
ACCEPT=HERE/'acceptance'


def read(path):return json.loads(path.read_text())
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=15
    seal=read(HERE/'runs/delivery-candidate.json')
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in seal['files'])
    before=read(HERE/'runs/restart-before-regressions.json');assert before['status']=='FAIL'
    regressions=read(HERE/'runs/verify-regressions.json');assert regressions['status']=='PASS'
    extended=read(HERE/'runs/verify-extended.json');assert extended['status']=='PASS'
    additional=read(HERE/'runs/verify-additional.json');assert additional['status']=='PASS'
    hold=read(HERE/'runs/verify-hold-bindings.json');assert hold['status']=='PASS'
    switches=read(HERE/'runs/verify-switches.json');assert switches['status']=='PASS' and len(switches['rows'])==16
    matrix=read(HERE/'runs/verify-snapshot-matrix.json');assert matrix['status']=='PASS' and len(matrix['checks'])==64
    assert len(set(matrix['keys'].values()))==16
    lane=read(HERE/'runs/verify.json');assert lane['status']=='PASS'
    assert all(read(HERE/'runs'/('verify-wide-snapshot-'+backend+'.json'))['status']=='PASS' for backend in ('native','reference'))
    suite=ACCEPT/'local/verify-suite'
    m2b=read(suite/'m2b-suite-r1.json');old_m2c=read(suite/'m2c-suite-r1.json')
    current=read(ACCEPT/'runs/verify-current-inputs.json')
    assert (m2b['passed'],m2b['total'])==(22,22)
    assert (old_m2c['passed'],old_m2c['total'])==(20,21) and not old_m2c['checks']['fixed_inputs']
    assert (current['passed'],current['total'])==(21,21) and current['status']=='PASS'
    assert current['gitignore']['historical_prefix_matches']
    snapshots=read(ACCEPT/'runs/verify-snapshots.json');assert snapshots['status']=='passed' and len(snapshots['checks'])==3
    assert read(ACCEPT/'runs/verify-snapshot-edges.json')['status']=='passed'
    reviewed=read(HERE/'runs/verify-reviewed.json');assert reviewed['status']=='PASS'
    g145=read(ACCEPT/'runs/verify-g145-comparison.json');assert g145['equal']
    mutation=read(ACCEPT/'runs/verify-mutation.json');assert mutation['status']=='detected'
    codec=read(ACCEPT/'runs/codec-final9.json');assert codec['status']=='passed' and codec['cases']==516
    callback=read(ACCEPT/'runs/verify-callback.json');assert callback['status']=='PASS'
    assert sum(row['calls'] for row in callback['callbacks'].values())==1
    benchmark=read(ACCEPT/'runs/verify-alternating.json');assert benchmark['status']=='complete' and benchmark['repetitions']>=3
    repetitions=benchmark['repetitions']
    repetition_note='' if repetitions>=5 else f'最终统计每项采用 {repetitions} 对完整配对。额外补测组未在截止前全部完成，其记录完整保留，本表不计入该组。'
    raw_records=[read(Path(path)) for path in benchmark['raw']]
    workloads={};checkpoints={};nand=[]
    names={'main':'MAIN 50M','boot':'state 5 → BOOT_RUN','recovery':'官方恢复确认页'}
    for kind,steps in (('main',50000000),('boot',202997601),('recovery',65975242)):
        records=[];loads=[]
        grouped={}
        for row in raw_records:
            if row['kind']==kind:grouped.setdefault(row['name'].rsplit('-',1)[0],{})[row['impl']]=row
        assert len(grouped)==repetitions
        for index,pair in enumerate(grouped.values(),1):
            assert pair['batch']['points']==pair['fast']['points']
            for impl,row in pair.items():
                assert row['status']=='complete' and row['segments'][-1]['end']==steps
                assert all(segment['stop']['reason']=='max_steps' for segment in row['segments'])
                loads += [segment[key][0] for segment in row['segments'] for key in ('load_before','load_after')]
            native=pair['fast']['native_machine']
            assert native['instructions']==steps and native['python_bus_calls']==0 and not native['hle_callbacks']
            assert pair['fast']['library_sha256']==seal['library_sha256']
            if kind=='recovery':
                paths=[ACCEPT/'local'/(pair[impl]['name']+'-confirm-nand.json') for impl in ('batch','fast')]
                assert paths[0].read_bytes()==paths[1].read_bytes()
                nand.append(dict(pair=index,sha256=sha(paths[0]),byte_equal=True))
            records.append(pair)
        summary=benchmark['summary'][kind]
        assert len(summary['batch']['seconds'])==len(summary['fast']['seconds'])==repetitions
        ratio=statistics.median(summary['batch']['seconds'])/statistics.median(summary['fast']['seconds'])
        assert ratio==summary['speedup'] and ratio>=20
        workloads[kind]=dict(steps=steps,speedup=ratio,batch=summary['batch'],native=summary['fast'],load_min=min(loads),load_max=max(loads))
        checkpoints[kind]=records[0]['fast']['points']
    for row in read(HERE/'runs/restart-environment.json')['legacy_entry_files']:
        assert sha(ROOT/row['path'])==row['sha256']
    freeze=read(HERE/'runs/current-protected-inputs.json')['files']
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in freeze)
    callback_native=[row['instructions'] for row in callback['timing'].get('native_machines',[])]
    evidence=dict(status='PASS',ready_for_repair_review=True,default_entry_replaced=False,
        scope='Five P1 repair candidate, host emulator equivalence. Successful complete recovery and physical camera acceptance are not established.',
        when=datetime.datetime.now(datetime.timezone.utc).isoformat(),pairs_per_workload=repetitions,workloads=workloads,checkpoints=checkpoints,
        confirmation_nand=nand,p1_regressions=len(regressions['checks']),
        extended=sum(row['count'] for row in extended['comparisons']),additional=len(additional['checks']),
        correction_combinations=16,correction_full_states=sum(row['full_state_count'] for row in switches['rows']),
        snapshot_identity_changes=64,hold_bindings=len(hold['checks']),m2b=[22,22],historical_m2c=[20,21],current_m2c=[21,21],
        current_input_entries=len(freeze),current_unique_files=len({row['path'] for row in freeze}),
        callback=callback['callbacks'],callback_probe_native_instructions=callback_native,
        library_sha256=seal['library_sha256'],extension_sha256=seal['extension_sha256'])
    (HERE/'runs/final-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    table='\n'.join('| '+names[k]+' | '+f"{row['steps']:,} | {row['batch']['median']:.3f} | {row['native']['median']:.3f} | {row['speedup']:.2f}× | {row['batch']['minimum']:.3f}–{row['batch']['maximum']:.3f} | {row['native']['minimum']:.3f}–{row['native']['maximum']:.3f} | {row['load_min']:.2f}–{row['load_max']:.2f} |" for k,row in workloads.items())
    points='\n'.join('| '+kind+' | '+f"{int(point):,}"+' | `'+row['all']+'` |' for kind,items in checkpoints.items() for point,row in items.items())
    reviews='\n'.join('| '+row['label']+' | '+str(row['points'])+' | '+f"{row['steps']:,}"+' | 相同 |' for row in reviewed['comparisons'])
    callbacks='\n'.join('- `'+name+'` 实测 '+str(row['calls'])+' 次，停止 '+str(row['stops'])+' 次，原函数体合计 '+f"{row['body_seconds']:.9f}"+' 秒。' for name,row in callback['callbacks'].items())
    speed='MAIN '+f"{workloads['main']['speedup']:.2f}"+' 倍；state 5/BOOT_RUN '+f"{workloads['boot']['speedup']:.2f}"+' 倍；恢复确认页 '+f"{workloads['recovery']['speedup']:.2f}"+' 倍'
    text=f'''可以交复审：本轮五个 P1 的反例及扩展检查通过；原入口未替换。
三项同机交替速度：{speed}。
本轮等价检查齐全：M2b 22/22、当前冻结 M2c 21/21；历史 M2c 20/21 保留。
切换：导入 tools/gxr_emulator_fast/fix_r1，或使用该目录 launch.py；后端 native/reference。
成功完整官方恢复本轮未验；实卡、刷写与真实相机不在本次验收内。

# 五个 P1 修复轮报告

## 候选与验收范围

T3 重启后的本轮先用 ps 确认没有残留模拟器进程，再重现原复审反例。被中断的运行和开发期中止的测速均未计入最终证据。所有计算 nice 15，最多两条计算进程。主机为 Apple M1 Pro，10 核、16 GiB，macOS 27.0.1，/usr/bin/python3 3.9.6。环境和原入口冻结见 [重启检查](fix_r1/runs/restart-environment.json) 与 [主机记录](fix_r1/runs/host.json)。

新库只放在 tools/gxr_emulator_fast/fix_r1/build。原 fast 入口的 70 个文件与库在本轮前后相同；其他任务继续使用原路径。本候选没有覆盖原库。原 standby、batch、v310 模拟器副本与官方固件保持只读。没有 Git 写命令、子代理、实卡或相机操作。

本轮没有新增提速。16 个 C 核心、头文件和 inc 文件与父目录逐字节相同，见 [C 源码比较](fix_r1/runs/c-core-unchanged.json)。改动集中在 Python 的原生资格、状态所有权、数值范围、实际模型绑定和快照身份。原剖析留在 [上一轮报告](fix_r1/prior/REPORT.md)，本轮速度以以下重跑为准。

## 五个 P1 的关闭证据

| 问题 | 修复 | 最终证据 |
| --- | --- | --- |
| P1-01 调度链 | 只接受完整且唯一的 storage/base 或 panel/storage/base 顺序，核对代码、闭包、设备与所有者绑定。缺层、重复、错误绑定或缺少设备均回退。已知 ready-hold 特例同样核对完整代码、原推进函数、设备闭包和列表所有权。回退也关闭旧的中间 C 时钟，所有设备由 Python 推进。 | [18 项原反例](fix_r1/runs/verify-regressions.json)、[补充检查](fix_r1/runs/verify-additional.json)。错误 base 绑定的修复前反例计数 0/19，修复后相同。 |
| P1-02 可变引用 | 原生入口遍历状态对象图，检测外部借用、内部别名和容器子类。借出状态保持 Python 所有权；合格原生运行在返回前同步。嵌套普通数据不再因 backend 等键名被跳过。只读快照收集允许普通外部引用，C 执行仍回退；保存和恢复后续跑另有回归。ready-hold 的错误内层函数、错误 peer 和设备列表别名均回退，原始绑定继续在 C 执行。 | [扩展检查](fix_r1/runs/verify-extended.json)、[嵌套反例](fix_r1/runs/verify-additional.json)。字典、列表、集合、字节数组、嵌套列表及面板记录的对象关系和状态相同。 |
| P1-03 大整数 | 进入 C 前检查预算、步数、设备与观察器中参与有界算术的输入，预留增长空间。IRQ 编号与队列容量、MX 通道和时钟寄存器按各自表示范围校验。未知总线或跟踪回调使用参考执行，避免回调改成大整数后重新导入 C。快照只做无损传输，数值与引用检查留在执行入口。超范围、整数子类与未知类型回退；无损传输保留。 | 正负 64/128 位边界、时钟、绝对截止步、IRQ、寄存器、MX 活动请求、观察计数和整数子类均在原反例及补充检查中通过。另有 [516 个编解码样本](fix_r1/acceptance/runs/codec-final9.json)。 |
| P1-04 快照键 | identity 直接绑定实际 cpu.model_revision、位、覆盖层哈希、运行期函数与类定义。改变修正在写入恢复目标前拒绝旧快照。 | [16 个唯一键、64 次单比特变更拒绝](fix_r1/runs/verify-snapshot-matrix.json)，每次目标完整状态不变；文件和源码失效检查继续通过。 |
| P1-05 预装包装 | 核对实际函数代码、默认值、闭包、相关全局值、类及继承链，不依赖名称或继承的标记。未知包装、代码替换、描述符及运行期类定义变化回退。 | 原 wraps 反例、构造前后包装、代码替换、默认值变化和描述符反例通过。真正已移植的 [16 个修正组合](fix_r1/runs/verify-switches.json) 在 C 中通过，共 136 个全状态对照。 |

原入口重跑仍检出五个 P1，见 [修复前失败](fix_r1/runs/restart-before-regressions.json)。补测发现的失败、早期验证器错误和开发测速均留在 fix_r1/runs，未覆盖为通过。最终候选通过原反例 {evidence['p1_regressions']} 项、扩展 {evidence['extended']} 项和补充 {evidence['additional']} 项。浮点补充用例比较寄存器、内存与时钟；其余适用用例使用完整状态比较。缺设备用例先验证资格拒绝，避免进入已知不安全的原生拓扑。

状态借用检测使用本次固定 CPython 运行时的引用计数和对象图。它保留调用方普通容器，并选择保守回退。M2b/M2c 冷启动和重启因调用方把 panel.records 放入结果字典而回退；这部分没有被写成全程 C。三项正式速度工作负载没有触发该回退。

## 三项真实工作负载与速度

每项 {repetitions} 对独立进程，分组内顺序交替。基线为原 batch；BOOT 使用原 standby 的批量入口及原批量桥。计时包含 cpu.run、资格检查和原生状态同步，不含进程启动、构造介质与独立全状态哈希。每次均确实执行到所列步数，正常用尽预算，配对全状态相同。正式原始回执与源文件冻结见 [交替测速](fix_r1/acceptance/runs/verify-alternating.json)。

{repetition_note}

| 工作负载 | 步数 | 批量中位秒 | 候选中位秒 | 倍数 | 批量范围秒 | 候选范围秒 | 1 分钟负载范围 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

三项原生执行均零 Python 总线回调、零 HLE 回调，原生指令数等于完整预算。当前 CPU 负载随其他任务变化，表中保留全部 {repetitions} 对样本；该表不表示空闲主机吞吐。原生设备仍使用上一轮的通用值结构，本轮未改成固定 C 结构。

BOOT 采用 v3.10 g155 包及原 50mm 单元、4096 B 设置输入。该冻结输入的 state 5 安全边界是 35,537,208 步，BOOT_RUN 为 202,997,601 步。恢复确认页为 65,975,242 步，{repetitions} 对虚拟 NAND 分页文件都直接比较完整字节并相同，见 [汇总](fix_r1/runs/final-evidence.json)。

| 工作负载 | 检查点步数 | 配对完整状态 SHA256 |
| --- | ---: | --- |
{points}

完整状态包括寄存器、145 B 架构状态及隐藏 LOCK、全部内存区域与属性、全部设备、观察历史、面板、控制变量、NAND 页与 SD 字节。三点快照分别恢复后再推进 1M/100k/100k，与连续执行相同，见 [快照续跑](fix_r1/acceptance/runs/verify-snapshots.json)。

复审中的实际设备流程也重新从冷启动生成自己的同后端快照，未使用旧复审快照。

| 流程 | 对照点 | 最终步数 | 全状态 |
| --- | ---: | ---: | --- |
{reviews}

g154 首次载入及 8 行图像设置菜单、实际 GPIO 和 SD 写读序列、四项修正后的确认页及后续 20M 段均通过。四修正恢复使用不同机身与启动输入，确认点为 71,387,224 步，与默认确认页的 65,975,242 步分别记录。

g145 实际文件路径回放的 71 次调用、扇区分类、读回结果和最终介质全部相同，介质 SHA256 为 `{g145['card_sha256'][1]}`，见 [逐项比较](fix_r1/acceptance/runs/verify-g145-comparison.json)。实际 C 计时器变异仍被完整状态检查检出，计数 {mutation['expirations'][0]}/{mutation['expirations'][1]}，见 [变异自检](fix_r1/acceptance/runs/verify-mutation.json)。

## 当前输入验收与历史记录

原 M2b/M2c 的 14 项运行全部重新执行，断言未改。M2b 为 22/22，历史基准 M2c 为 20/21，唯一失败仍是 fixed_inputs。新的输入清单在运行前显式冻结当前 {len(freeze)} 个文件，再重新核对全部哈希，并用原 M2c 的全部 21 项断言评估本轮新回执，结果 21/21。见 [当前输入验收](fix_r1/acceptance/runs/verify-current-inputs.json) 和 [当前清单](fix_r1/runs/current-protected-inputs.json)。旧守卫与新守卫对同一份本轮运行结果分别评估，未复用历史运行结果。

历史 protected-inputs.json 没有修改。当前 .gitignore 的历史前缀仍匹配，追加内容如下。

```gitignore
{current['gitignore']['appended_text'].rstrip()}
```

来源为本轮对当前 .gitignore 的实读，内容与独立复审 fixed-inputs-audit.json 相同。追加内容尚未提交，未把作者归属写成已确认事实。历史 20/21 回执与清单保留。旧模拟器和旧研究的封存清单另独立重读，未发现变化。

## 重启 Python 回调

对同一份完成文件操作后的虚拟介质另冷启动一次，只包装实际 input_run.stop_here，调用原函数一次并原样返回其结果。该运行与本轮正式重启的完整 CPU 快照、观察记录、调用记录和介质一致。

{callbacks}

这次停止仍执行 Python。该重启因保留面板状态引用而整段使用设备参考执行，原生执行累计 {sum(callback_native)} 步。原生 HLE 统计不计参考路径中的 Python 调用，因此没有用空的 hle_callbacks 宣称零 Python。见 [实测计数与等价检查](fix_r1/acceptance/runs/verify-callback.json)。本轮未增加新的 C 停止组合声明。

## 构建身份与重跑

最终 CPU 库 SHA256 为 `{seal['library_sha256']}`。传输扩展为 `{seal['extension_sha256']}`。源码、GNU 归档、实际编译命令和编译器见 [最终候选冻结](fix_r1/runs/delivery-candidate.json)。所有最终验证结束后再次复核同一候选身份。

从项目根执行，所有名称换新以保留回执。首次复跑前检查 Workspace 的 APFS、可写状态与 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，再建立指定 Scratch 目录。Python 验证不产生 pycache。

```sh
nice -n 15 mkdir -p /Volumes/Workspace/Scratch/tmp/projectricoh/emulator-fast-fix-r1
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/regressions.py --phase NEW-P1
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/run_extended.py --name NEW-EXTENDED
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/run_additional.py --name NEW-ADDITIONAL
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/switch_matrix.py --name NEW-SWITCHES
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/snapshot_matrix.py --name NEW-SNAPSHOT-KEYS
GIT_OPTIONAL_LOCKS=0 nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/acceptance/scripts/benchmark.py --name NEW-BENCHMARK --repetitions 5
GIT_OPTIONAL_LOCKS=0 nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/acceptance/scripts/suite.py --name NEW-SUITE --jobs 1
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/current_acceptance.py --suite NEW-SUITE --name NEW-CURRENT-INPUTS
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/reviewed_workloads.py --name NEW-REVIEWED
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/fix_r1/callback_probe.py --suite NEW-SUITE --name NEW-CALLBACK
```

验证同时最多两条计算进程。直接使用最终库复跑即可；如果重新构建，给构建进程设置本轮 Scratch 的 TMPDIR，先保存新的库与源码身份，再从头跑验收，旧快照不会跨构建复用。当前输入发生变化时建立新清单并重跑，不修改历史清单。

清单从项目根校验。最终原始回执、修复脚本与最终候选分别有 SHA256SUMS；收尾清理与进程核查见 fix_r1/runs/cleanup.json。

```sh
nice -n 15 shasum -a 256 -c research/emulator_fast_r1/fix_r1/SHA256SUMS
```

本轮没有重跑成功完整官方恢复，也没有把上一轮 1.859B 步的共同失败终点算成本轮新证据。实卡 FAT32、真实 SD、刷写、断电、相机 RTOS/LCD、物理按键与拍摄均未运行。本报告支持提交五个 P1 的修复候选复审，不表示旧入口已切换或设备验收已通过。
'''
    (PARENT/'REPORT.md').write_text(text)
    (HERE/'REPORT.md').write_text(text.replace('](fix_r1/',']('))
    (FAST/'REPORT.md').write_text('可以交复审：五个 P1 修复候选，原入口未替换。\n\n完整回执、速度、边界与重跑方法见 [修复轮报告](../../../research/emulator_fast_r1/REPORT.md)。\n')
    maximum=max(70,*[row['speedup'] for row in workloads.values()])
    bars=''.join('<div class="row"><span>'+names[k]+'</span><div class="track"><i style="width:'+str(row['speedup']/maximum*100)+'%"></i><b style="left:'+str(20/maximum*100)+'%"></b></div><span>'+f"{row['speedup']:.2f}×"+'</span></div>' for k,row in workloads.items())
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>:root{font-family:var(--font-sans);color:var(--foreground)}body{margin:0}.row{display:grid;grid-template-columns:160px 1fr 65px;align-items:center;gap:10px;font-size:13px;margin:16px 0}.track{height:16px;background:var(--secondary);position:relative;border-radius:4px}.track i{display:block;height:100%;background:var(--chart-1);border-radius:4px}.track b{position:absolute;top:-4px;bottom:-4px;border-left:2px dashed var(--warning)}p{font-size:12px;line-height:1.6;color:var(--muted-foreground);margin:14px 0 0}@media(max-width:500px){.row{grid-template-columns:102px 1fr 58px;gap:7px}}</style><body>'''+bars+'''<p>相对原批量版，每项 '''+str(repetitions)+''' 对交替测量，nice 15。计时含运行与状态同步，虚线为 20× 目标。</p></body></html>'''
    (HERE/'performance.html').write_text(html)
    print(json.dumps(dict(status='PASS',speedups={k:row['speedup'] for k,row in workloads.items()},review=True)))


if __name__=='__main__':main()
