"""Recompute the final evidence verdict and write the implementation report."""
import argparse,datetime,hashlib,json,os,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE,FAST,ROOT
enable()


def read(path):return json.loads(Path(path).read_text())
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--benchmark',default='alternating-final9');a=p.parse_args()
    runs=HERE/'runs';bench=read(runs/(a.benchmark+'.json'));assert bench['status']=='complete'
    build=read(FAST/'build/native-build.json')
    assert all(sha(FAST/name)==digest for name,digest in build['source_hashes'].items())
    assert sha(FAST/'build/libgxr_m32r.dylib')==build['library_sha256']
    assert all(sha(FAST/name)==digest for name,digest in bench['source_hashes'].items())
    extension=next((FAST/'build').glob('_gxr_wire.cpython-*.so'))
    assert sha(extension)==build['extension_sha256']
    snapshots=read(runs/'snapshots-final9.json');assert snapshots['status']=='passed' and len(snapshots['checks'])==3
    assert read(runs/'snapshot-edges-final9.json')['status']=='passed'
    assert read(runs/'codec-final9.json')['status']=='passed'
    switches=read(runs/'model-switch-matrix-final11.json');assert switches['status']=='PASS' and len(switches['comparisons'])==6
    serial=read(runs/'serial-final9.json');parallel=read(runs/'parallel-final9.json')
    assert serial==parallel and (runs/'serial-final9.json').read_bytes()==(runs/'parallel-final9.json').read_bytes()
    assert len(serial['cases'])==14 and all(case['exit_code']==0 for case in serial['cases'])
    m2b=read(HERE/'local/parallel-final9/m2b-suite-r1.json');m2c=read(HERE/'local/parallel-final9/m2c-suite-r1.json')
    assert (m2b['passed'],m2b['total'])==(22,22)
    assert (m2c['passed'],m2c['total'])==(20,21) and [k for k,v in m2c['checks'].items() if not v]==['fixed_inputs']
    guard=read(HERE/'local/parallel-final9/final-input-guard.json');assert guard['changed_inputs']==['.gitignore']
    g145=read(runs/'g145-comparison-final9.json');assert g145['equal'] and g145['card_equal']
    mutation=read(runs/'mutation-final11.json');assert mutation['status']=='detected'
    assert read(runs/'compatibility-final9.json')['passed']
    native=read(runs/'recovery-default-final9.json');reference=read(runs/'recovery-batch-continuous-final1.json')
    assert native['steps']==reference['steps']==1859053607
    assert native['final']['fingerprint']==reference['fingerprint']
    assert native['final']['nand_sha256']==reference['nand_sha256']
    first=read(native['segments'][0]['receipt']);assert first['confirmation']['fingerprint']==reference['confirmation']
    assert not native['complete'] and not reference['complete'] and native['final']['signed_r0']==-1
    full_segments=[read(row['receipt']) for row in native['segments']]
    assert all(row['native_machine']['python_bus_calls']==0 and not row['native_machine']['hle_callbacks'] for row in full_segments)
    workloads={};checkpoints={}
    for kind in ('main','boot','recovery'):
        raw=[read(path) for path in bench['raw'] if read(path)['kind']==kind]
        baseline=[r for r in raw if r['impl']=='batch'];candidate=[r for r in raw if r['impl']=='fast']
        assert len(baseline)==len(candidate)==bench['repetitions']
        assert all(x['points']==y['points'] for x,y in zip(baseline,candidate))
        assert all(r['native_machine']['python_bus_calls']==0 and not r['native_machine']['hle_callbacks'] and r['native_machine']['instructions']==r['segments'][-1]['end'] for r in candidate)
        result=bench['summary'][kind]
        steps=candidate[0]['segments'][-1]['end'];speed=steps/result['fast']['median']
        loads=[v for r in raw for s in r['segments'] for v in (s['load_before'][0],s['load_after'][0])]
        workloads[kind]=dict(steps=steps,batch_seconds=result['batch']['median'],native_seconds=result['fast']['median'],
            paired_speedup=result['speedup'],native_steps_per_second=speed,idle_baseline_ratio=speed/741230,
            load_min=min(loads),load_max=max(loads),batch_samples=result['batch']['seconds'],native_samples=result['fast']['seconds'])
        checkpoints[kind]=candidate[0]['points']
    frozen=read(HERE/'frozen-inputs.json')['paths'];differences={}
    for name,digest in frozen.items():
        path=ROOT/name
        if not path.is_file() or sha(path)!=digest:differences[name]=dict(initial=digest,current=sha(path) if path.is_file() else None)
    changed_tools=[name for name in differences if name.startswith('tools/gxr_emulator')]
    assert not changed_tools,changed_tools
    seal=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files={str(path.relative_to(ROOT)):sha(path) for path in sorted(FAST.iterdir()) if path.is_file()},
        library_sha256=build['library_sha256'],extension_sha256=build['extension_sha256'],archives=build['archives'],
        compiler=build['compiler'],python=sys.version,host=os.uname()._asdict() if hasattr(os.uname(),'_asdict') else list(os.uname()),
        frozen_input_changes=differences,protected_emulator_inputs_unchanged=True)
    write(runs/'native-seal-final9.json',seal)
    serial_time=read(runs/'serial-final9.timings.json');parallel_time=read(runs/'parallel-final9.timings.json')
    callback_rows=[]
    for path in sorted((HERE/'local/parallel-final9').glob('*-timing.json')):
        record=read(path)
        for machine in record.get('native_machines',[]):
            if machine.get('hle_callbacks'):callback_rows.append(dict(receipt=str(path.relative_to(ROOT)),callbacks=machine['hle_callbacks'],callback_body_seconds=machine['hle_seconds'],shell_seconds=machine['shell_seconds'],case_seconds=record['seconds']))
    evidence=dict(status='incomplete-acceptance',performance=workloads,checkpoints=checkpoints,
        primary_speed_floor_20x=all(v['paired_speedup']>=20 for v in workloads.values()),
        desired_idle_speed_100x=all(v['idle_baseline_ratio']>=100 for v in workloads.values()),
        m2b=dict(passed=22,total=22),m2c=dict(passed=20,total=21,failed=['fixed_inputs']),
        snapshots=True,parallel_serial_identical=True,g145=True,mutation=True,model_revisions=True,compatibility=True,
        complete_successful_official_recovery=False,default_terminal_equal=True,default_terminal_steps=native['steps'],
        default_terminal_hash=native['final']['fingerprint']['all'],default_terminal_nand_sha256=native['final']['nand_sha256'],
        default_recovery_wall_seconds=native['seconds'],reference_recovery_wall_seconds=reference['wall_seconds'],
        default_recovery_run_seconds=sum(sum(s['seconds'] for s in row['segments']) for row in full_segments),
        default_recovery_shell_seconds=sum(row['native_machine']['shell_seconds'] for row in full_segments),
        serial_seconds=serial_time['seconds'],parallel_seconds=parallel_time['seconds'],
        compatibility_python_boundaries=callback_rows,ready_for_full_acceptance_review=False)
    write(runs/'final-evidence.json',evidence)
    names={'main':'MAIN 冷启动','boot':'state 5 → BOOT_RUN（从冷启动计）','recovery':'恢复确认页'}
    table='\n'.join('| '+names[k]+' | '+f"{v['steps']:,} | {v['batch_seconds']:.3f} | {v['native_seconds']:.3f} | {v['paired_speedup']:.2f}× | {v['native_steps_per_second']/1e6:.2f} M/s | {v['idle_baseline_ratio']:.2f}× | {v['load_min']:.2f}–{v['load_max']:.2f} |" for k,v in workloads.items())
    point_table='\n'.join('| '+kind+' '+point+' | `'+state['all']+'` |' for kind,points in checkpoints.items() for point,state in points.items())
    snapshot_table='\n'.join('| '+row['point']+' | '+f"{row['steps']:,} | {row['continued_steps']:,} | {row['load_seconds']:.3f}"+' | `'+row['snapshot']['sha256']+'` |' for row in snapshots['checks'])
    callback_text='\n'.join('- `'+name+'`：'+str(count)+' 次，函数体 '+f"{row['callback_body_seconds']:.9f}"+' 秒，占该用例 '+f"{100*row['callback_body_seconds']/row['case_seconds']:.6f}"+'%；该实例全部状态同步 '+f"{row['shell_seconds']:.6f}"+' 秒。' for row in callback_rows for name,count in row['callbacks'].items()) or '无。'
    text=f'''三项同机交替速度：MAIN {workloads['main']['paired_speedup']:.2f} 倍；state 5/BOOT_RUN {workloads['boot']['paired_speedup']:.2f} 倍；恢复确认页 {workloads['recovery']['paired_speedup']:.2f} 倍。
等价证据未齐：M2b 22/22、M2c 20/21；默认恢复失败终点逐位相同，成功完整恢复未闭合。
切换：导入 tools/gxr_emulator_fast；GXR_FAST_BACKEND=native/reference；四项模型修正默认全关。
不能按全部验收项交复审；原目录保持只读，清理状态见 runs/cleanup.json。

# 实现与验收报告

## 测量范围

主机为 Apple M1 Pro、10 个物理/逻辑核、16 GiB RAM、arm64 macOS；Python 为 /usr/bin/python3 3.9.6，Apple clang 21.0.0。全部任务 nice 15。每个重计算入口先记录 ps、负载与进程分配；指定外部任务存在时最多两个测试进程，结束后最多六个。记录在 runs/process-allocation.jsonl。

每项两组，顺序 B/F、F/B。表中是 CPU.run 与该段状态同步的合计中位数，计时包含初始化原生状态的首次调用；进程启动、构造介质和独立全状态哈希单列在原始回执。没有跳过指令、停用验收观察或丢弃历史记录。正式原始数据为 runs/{a.benchmark}.json 及其列出的逐次回执；较早的 final1–final4 是开发或被中止的测量，不计入表。

| 工作负载 | 步数 | 批量秒 | 原生秒 | 同机倍数 | 原生吞吐 | 对 741,230/s 的倍数 | 1 分钟负载范围 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

三项全状态在每组配对都相同。BOOT 使用 firmware/package_v310_g155_test/local/SD_ROOT 的实际机身与 DAT、50mm 单元和既有 4096 B 设置输入；这组输入的 BOOT_RUN 是 202,997,601 步，state 5 写入完成后的安全边界为 35,537,208 步。原写入观察标签是 35,537,207。任务中的约 183M 是近似值，未改输入来凑步数。MAIN、恢复以原 tools/gxr_emulator_batch 对照；BOOT 使用原 standby 的批量模式与原批量 C 桥。

## 剖析与改动

初始 10M 批量剖析为 23.618 秒、423,412 步/秒。cProfile 的 _run_batch 内部时间为 20.978 秒；独立原生采样的 875 个主线程样本中，826 个落在 getrusage、sigprocmask、sigreturn、sigaltstack，约 94.4%。逐条 GNU sim_resume 的调试单步和 setjmp/longjmp 才是首要成本，扩大 Python 批量窗口不足以消除它。

bridge.c 使用整段故障边界，104 条标量语义由 GNU GDB 16.3 生成；未覆盖的并行组合仍执行 GNU 语义。解码缓存有 16,384 项并核对原字节，支持自修改代码。普通 RAM、对齐访问、RTE 寄存器组完成、断点和跟踪页判断均在 C。

machine*.inc 包括现有全部 19 类设备及其状态推进：定时器、IRQ、GPIO、串行、NAND、缓存/系统/NAND 控制器、HSP/RPC/三种单元链路、模拟输入、DMA、板级握手、视频/调色板、SIO/I2C、SD/FIFO/DMA、面板、按键与截止步调度。SD 块读写在 C，FAT 和文件服务仍由官方固件指令执行。Python FAT 工具在运行前后建立、检查虚拟介质。

Python 启动外壳保存原 API；读取状态时同步，连续预算调用保留 C 状态。Monitor 历史在 C 使用紧凑表示，导出仍是原列表。任意精度整数以二进制传输。wire_python.c 提供状态传输与规范哈希；516 个确定性样本与 Python 定义逐字节匹配，含大整数、容器、中文和 PreviewLink。未声明的钩子、方法替换或设备覆盖层保持参考执行；历史钩子反例四组全部通过，见 compatibility-final9.json。

100 倍目标未达到。单独采样 MAIN 1M 后的 200M 原生段，1456 个主线程样本的栈顶为 scalar_step 270（18.5%）、gxr_machine_run 226（15.5%）、动态值查找/哈希/比较/更新辅助函数 419（28.8%）、mark/vgc 124（8.5%）；其余为内存、分配和库调用等。原始采样在 runs/profile-whole-native-final9.txt。下一步应把高频设备字段从通用值字典改成固定 C 结构，合并调度访问，减少分配/GC，再评估带写入失效的基本块缓存。此处没有把后续方案计入速度。

## Python 运行边界

三项正式工作负载、默认恢复至失败终点、g145 原生回放的 Python 设备回调及 HLE 回调均为 0。文件服务本身不回 Python。g145 副本只给原停止条件增加原生声明，断言、固件调用和参数均保留。

M2b+M2c 的重启用例保留一次宿主停止断点兼容边界。它来自 input_run.run 的 stop_here，经动态观察器包装；包装调用已有 Python 断点并丢弃其返回值，随后按当前任务和 PSW 判断停止。执行器保留该任意 Python 断点语义，未把它当作设备模型跳过。逐项记录为：

{callback_text}

函数体计时不包含状态同步；同步值是该实例所有 API 边界的合计，不能全部归因于这一回调。严格的全套运行零 Python 条件仍有这一项缺口。后续可为丢弃前驱返回值的停止组合增加 C 声明，并重跑对应反例。

## 全状态等价

哈希覆盖公开寄存器、完整 145 B 架构状态（GR、CR、累加器、PSW 各组及隐藏 LOCK）、所有内存区域及属性、全部设备状态、观察历史、面板、动态返回记录、介质字节和外壳控制状态。各分项哈希在原始 JSON 中，以下列总哈希。每个点均与原批量侧相同。

| 检查点 | 全状态 SHA256 |
| --- | --- |
{point_table}

M2b 22/22。M2c 20/21，唯一失败是 fixed_inputs：历史 protected-inputs.json 中的根 .gitignore 与当前文件不同；原断言、失败回执和历史目录校验保留，未改范围外文件或放宽判定。当前旧模拟器输入与本任务起始 frozen-inputs.json 一致；其他任务可变文档的差异另列于最终冻结清单。

g145 的 71 次实际文件调用、全部扇区分类、读回结果和最终媒体完全相同，媒体 SHA256 为 `{g145['card_sha256'][1]}`。见 runs/g145-comparison-final9.json。

计时器 C 变异将 expirations 每次增加 1 改成增加 2。两侧各跑 50M、均零 Python 回调；寄存器和内存相同，设备和总哈希不同，计数为 13742/27484。见 runs/mutation-final11.json。开发期失败及修正后的结果均保留，没有将旧失败回执覆盖为通过。

## 开机快照

快照包含整机状态、全部 NAND 页、相对已哈希 SD 种子的扇区差异、观察器、面板、控制变量和可移植原生回调声明。键绑定实际机身、DAT、单元/ROM、卡种子、设置输入、模型名称及覆盖层 SHA、模拟器全部运行源码/配置、实际 CPU/传输库与运行时。输入或版本变化就拒绝；恢复目标必须是新建实例。可选面板和隐藏 LOCK 边界已检查。

| 点 | 保存步数 | 恢复后再跑 | 加载秒 | 快照 SHA256 |
| --- | ---: | ---: | ---: | --- |
{snapshot_table}

三个点恢复后继续运行的全状态均与从头直接运行一致。单元、DAT 和模型版本失效检查保留在 snapshots-final9.json。Cache(root) 按输入键保存，不复用已过期状态。

## 并行与实际流程耗时

运行器 parallel.py 支持参数 jobs、依赖关系、独立进程媒体与输出、每项最多 1800 秒、固定回执顺序；计时/日志单列。重新读取 ps 调整分配上限。它按用例退出状态收集结果；验收项判定仍以 M2b/M2c 的 checks 为准。

预热缓存后，M2b+M2c 的 14 项运行器耗时：串行 {serial_time['seconds']:.3f} 秒、两进程 {parallel_time['seconds']:.3f} 秒；含外层启动为 71.791/53.078 秒。固定顺序结果 JSON 逐字节相同。六个 prepared 用例中五个命中缓存；readback 绑定本次新生成检查点哈希，保持未命中。缓存预热为另一次完整串行执行，不隐藏其 73.049 秒成本。

成功完整官方恢复的实际耗时尚不能给出。默认模型从冷启动，经确认页和实际按键，到失败终点 {native['steps']:,} 步耗时 {native['seconds']:.3f} 秒；该原生运行使用八段输入绑定快照。原批量独立连续执行耗时 {reference['wall_seconds']:.3f} 秒。两种驱动的保存开销不同，这组耗时不作为正式速度倍数。

失败终点全状态 `{native['final']['fingerprint']['all']}`、虚拟 NAND `{native['final']['nand_sha256']}` 逐位相同，确认页严格为 65,975,242 步。CPU.run 与同步合计 {evidence['default_recovery_run_seconds']:.3f} 秒；原生外壳全部同步统计 {evidence['default_recovery_shell_seconds']:.3f} 秒，已包含于相应段计时；构造/全状态哈希/保存等余项约 {native['seconds']-evidence['default_recovery_run_seconds']:.3f} 秒。长流程仍受不断增长的历史记录导出和保存影响。

该终点在 0x2005ccf0、r0=-1，不能写成恢复成功。独立读取的 v310 r3 recovery-final-gate.json 也将修正模型的正常结束门标为 OPEN；其约 7.292B 步结果不是本交付重跑，不计入本交付全状态证明。

## 四项模型修正

默认 GXR_FAST_MODEL_FIXES 为空。可独立选择 nand-word、preview-link、sd-long-response、nand-read-tail，位分别为 0/1/2/3。新旧后端载入同一只读覆盖层并记录 SHA。原生只接受本次已移植的四个源码哈希，源码变化时选择参考后端；快照键同时变化。

| 修正 | C 设备行为 | 对照 |
| --- | --- | --- |
| nand-word | READSTART/PROGRAMCONFIRM 列地址乘二；越界错误保留。 | 原覆盖层及实际 guest 字节写入、页内容。 |
| preview-link | queue 15、144 B 的 2f03 请求返回 48 B 2003，status=0；三单元原构造器证据保持原文。 | 三单元回复、帧、事件和非法布局 ValueError。 |
| sd-long-response | 仅 CMD2/CMD9 的响应寄存器取原 128 位右移 8；原 response 属性和事件值保留。 | sd-response-check-c.json、sd-response-check-python.json；实际 guest 命令与官方容量代码。 |
| nand-read-tail | READ0/READSTART 合法数据口读过 2048+64 B 后返回 FF，累计 cursor/reads；正常页、READID 和非法端口保留。 | nand-tail-check-c.json、nand-tail-check-python.json；页尾跨界和官方判空分支。 |

修正检查引用 research/v310_body/fix/emulator/PORTING.md 的只读证据。SD 三种容量得到 65,536/131,072/262,144 扇区；默认 64 MiB 仍复现 7682。官方容量微型 harness 与整机调用的步数口径不同，原生与参考整机的 collector/formula 都是 40/37 步，寄存器和容量与微型证据相同；报告不把两种计数混为一谈。官方 NAND 判空片段三种字节均执行 9 步并得到相同最终寄存器，栈临时字节保留各自输入。

model-switch-matrix-final11.json 覆盖全关、四项分别单开和全部开启六组；每组 C/Python 在每个检查后的整机全状态相同，所有 C 侧检查均零 Python 运行回调。完整修正恢复尚未重跑。之后移植修正需新增名称/位、精确参考方法绑定、C 分支和源码哈希，再跑本组差分及默认检查点；未知覆盖层保持参考执行。panel_lever 等未请求修正没有移植。

## 构建、重跑与校验

最终 CPU 库 SHA256：`{build['library_sha256']}`。传输扩展：`{build['extension_sha256']}`。GNU 归档校验在 tools/gxr_emulator_fast/GNU_ARCHIVES.sha256；构建命令、编译器和源码哈希在 build/native-build.json。只链接副本中冻结归档，不运行复制来的 GNU Makefile。原目录、research/v310_body 内模拟器副本、官方固件及存储卡均未写；没有 Git 写操作或子代理。

从项目根目录执行，名称每次更换；脚本拒绝覆盖正式回执。

```sh
nice -n 15 /usr/bin/python3 -I -B tools/gxr_emulator_fast/build.py
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/scripts/limit.py 6500 research/emulator_fast_r1/scripts/benchmark.py --name rerun-alternating-01 --repetitions 2
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/scripts/limit.py 600 research/emulator_fast_r1/scripts/snapshot_check.py --name rerun-snapshots-01
GXR_FAST_CASE_CACHE="$PWD/research/emulator_fast_r1/local/rerun-cache-01" nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/scripts/limit.py 1700 research/emulator_fast_r1/scripts/suite.py --name rerun-serial-01 --jobs 1
GXR_FAST_CASE_CACHE="$PWD/research/emulator_fast_r1/local/rerun-cache-01" nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/scripts/limit.py 1700 research/emulator_fast_r1/scripts/suite.py --name rerun-parallel-01 --jobs 2
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/scripts/limit.py 180 research/emulator_fast_r1/scripts/mutation_check.py --name rerun-mutation-01
nice -n 15 /usr/bin/python3 -I -B research/emulator_fast_r1/scripts/limit.py 1700 research/emulator_fast_r1/scripts/full_recovery.py --impl fast --name rerun-default-recovery-01 --budget 2000000000
GXR_FAST_MODEL_FIXES=sd-long-response,nand-read-tail nice -n 15 /usr/bin/python3 -I -B tools/gxr_emulator_fast/launch.py --backend native CALLER.py ARGUMENTS
```

修正对照可用 native_corrections.py --backend native/reference --fixes 逗号列表 --name 新名称。g145 用 g145_replay.py --impl batch 新名称，再以 g145_compare.py 比较原存档与新输出。完整批量连续对照命令为 scripts/limit.py 8000 scripts/recovery_reference.py --name 新名称；该单次预期超过 30 分钟的原因和缩短替代已写在 PROGRESS：参考侧没有本快照机制，用独立连续执行闭合终点，避免两侧共用恢复器造成共同错误。

SHA256SUMS 从项目根目录校验，覆盖两个交付目录的文件（清单自身除外）：

```sh
nice -n 15 shasum -a 256 -c research/emulator_fast_r1/SHA256SUMS
```

约 10 小时扩展时间盒已超出；收尾阶段未继续扩展优化或新增完整修正恢复。开发失败、中止测量和最终证据分别保留。最终可重算判定见 runs/final-evidence.json；临时目录删除和残留进程检查见 runs/cleanup.json。
'''
    (HERE/'REPORT.md').write_text(text)
    max_ratio=max(v['paired_speedup'] for v in workloads.values())
    rows=''.join('<div class="row"><span>'+names[k]+'</span><div class="track"><div class="bar" style="width:'+str(min(100,v['paired_speedup']))+'%"></div><i class="minimum"></i></div><b>'+f"{v['paired_speedup']:.2f}×"+'</b></div>' for k,v in workloads.items())
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>:root{color:var(--foreground);font-family:var(--font-sans)}body{margin:0}.row{display:grid;grid-template-columns:205px 1fr 72px;align-items:center;gap:10px;margin:18px 0;font-size:13px}.track{height:18px;background:var(--secondary);position:relative;border-radius:4px}.bar{height:100%;background:var(--chart-1);border-radius:4px}.minimum{position:absolute;top:-5px;bottom:-5px;left:20%;border-left:2px solid var(--warning)}small{display:block;color:var(--muted-foreground);line-height:1.6}@media(max-width:500px){.row{grid-template-columns:120px 1fr 58px;font-size:11px;gap:6px}}</style><body>'''+rows+'''<small>同机交替测量，两组；横轴上限 100×，竖线为最低目标 20×。<br>完整恢复成功与 M2c 全通过尚未闭合。</small></body></html>'''
    (HERE/'speedup.html').write_text(html)
    print(json.dumps(dict(status=evidence['status'],speedups={k:v['paired_speedup'] for k,v in workloads.items()},review=False)))


if __name__=='__main__':main()
