"""Verify final r4 evidence, write its report and ledger, and seal file hashes."""
import datetime,json,os,shutil,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,TEMP,enable,emit,sha
from compare_products import compare_values
from resume_identity import verify_inputs

def read(path):return json.loads((HERE/path).read_text())
def total(rows,key,side):return sum(row[key][side] for row in rows)
def rate(rows,key):return total(rows,key,'python')/total(rows,key,'c')
def remove_absolute(path):
    for item in path.iterdir():
        if item.is_dir() and not item.is_symlink():remove_absolute(item)
        else:item.unlink()
    path.rmdir()

def main():
    enable();start=read('evidence/start.json');stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    comparison=read('local/comparisons-strict/summary.json');assert comparison['passed']
    assert read('local/comparisons/summary.json')['passed']
    assert read('local/measurements/complete.json')['passed']
    assert read('local/comparisons-before/summary.json')['passed']
    for path in ('local/gates/summary.json','local/repair-checks/summary.json','local/repair-events/summary.json',
                 'local/busy/comparison.json','local/integration-strict/summary.json','local/comparator-checks.json',
                 'local/tapes/summary.json'):
        assert read(path)['passed'],path
    assert read('local/tapes/mutation.json')['detected']
    for form in ('legacy','driver'):
        value=read('local/identity/strict-final-'+form+'/summary.json');assert value['passed'] and len(value['records'])==11
    assert read('local/temporary-input/before/summary.json')['stale_pass_reproduced']
    for tag in ('after-final','existing-output-final','failed-write-final'):
        value=read('local/temporary-input/'+tag+'/summary.json');assert value['passed'] and not value['stale_pass_reproduced']
    strict=read('local/strict-comparison-final.json');assert strict['equal']
    strict_metric=read('local/measurements/c-strict-final/group126-50mm-cutpoints/measurement.json')
    verify_inputs(strict_metric['runtime_inputs'],HERE/'run/local/inputs/c-strict-final/group126-50mm-cutpoints')
    rows=[row for row in comparison['results'] if row['job']!='user-tool'];assert len(rows)==20
    before=read('local/comparisons-before/summary.json')['results'];assert len(before)==5
    new_controls=[row for row in rows if row['job'] in {item['job'] for item in before}]
    original_names={j['name'] for j in json.loads((ROOT/'tools/speedlab/host_regression_r3/queue.json').read_text())['jobs']}
    original=[row for row in rows if row['job'] in original_names];assert len(original)==15
    build_path=ROOT/'tools/speedlab/harness_release_r4/local/ccore/build.json'
    build=json.loads(build_path.read_text());assert sha(Path(build['library']))==build['sha256']
    assert all(sha(Path(name))==value for name,value in build['sources'].items())
    metrics=[];loads=[];views=[]
    for label in ('python','c','c-before','c-strict-release'):
        for path in sorted((HERE/'local/measurements'/label).glob('*/measurement.json')):
            metric=json.loads(path.read_text());metrics.append(metric)
            loads.extend((metric['load_start'][0],metric['load_end'][0]))
            verify_inputs(metric['runtime_inputs'],HERE/'run/local/inputs'/label/metric['job'])
            assert all(p['nice']>=15 for p in metric['processes'])
            if label in ('c','c-strict-release'):
                assert all(p['native_api']==6 and p['library_sha256']==build['sha256'] for p in metric['processes'])
                assert metric['native_stats'].get('fallback_calls',0)==metric['native_stats'].get('fallback_steps',0)==0
    for unit in ('50mm','28mm','mount'):
        name='group126-'+unit+'-view-reentry';base=HERE/'local/measurements';files={}
        for side in ('python','c'):
            folder=base/('c-strict-release' if side=='c' else side)/name;metric=json.loads((folder/'measurement.json').read_text())
            files[side]={str(p.relative_to(folder/'products')):p for p in (folder/'products').rglob('*.json') if '/local/view-reentry/' in str(p)}
            assert len(files[side])==70 and len(metric['processes'])==71
            assert all(json.loads(p.read_text())['status']=='PASS' for p in files[side].values())
        assert files['python'].keys()==files['c'].keys();values=0
        for name in files['python']:
            proof=compare_values(json.loads(files['python'][name].read_text()),json.loads(files['c'][name].read_text()))
            assert proof['equal'];values+=proof['compared_values']
        views.append({'unit':unit,'children_per_side':70,'process_records_per_side':71,'compared_values':values,'passed':True})
    emit(HERE/'evidence/view-completeness.json',{'passed':True,'checks':views})
    tape_identity=[]
    for option in ('0','1','mutant'):
        prefix='tape-'+option+'-group126-50mm-view-reentry'
        files=list((HERE/'run/local/processes'/prefix).glob('process-*.json'))
        processes=[json.loads(p.read_text()) for p in files]
        expected_library=build['sha256'] if option!='mutant' else read('local/tapes/mutation.json')['library_sha256']
        assert len(processes)==71
        assert all(p['native_api']==6 and p['library_sha256']==expected_library and p['nice']>=15 for p in processes)
        assert sum(p['packets'] for p in processes)==83510395
        tape_identity.append({'option':option,'api':6,'library_sha256':expected_library,'process_records':71,'packets':83510395})
    emit(HERE/'evidence/tape-identity.json',{'passed':True,'checks':tape_identity})
    changed=[name for name,value in start['frozen'].items() if not (ROOT/name).is_file() or sha(ROOT/name)!=value]
    assert not changed,changed[:10]
    emit(HERE/'evidence/frozen-final.json',{'passed':True,'utc':stamp,'files':len(start['frozen']),'changed':[],'api':6,'library_sha256':build['sha256']})
    emit(HERE/'evidence/input-receipts-final.json',{'passed':True,'measurements':len(metrics),'schema':3,'actual_inputs_rehashed':True,'import_candidates_rechecked':True,'strict_input_control':True,'temporary_input_variants':3})
    busy=read('local/busy/comparison.json');tapes=read('local/tapes/summary.json');mutation=read('local/tapes/mutation.json')
    wall=rate(rows,'wall_seconds');cpu=rate(rows,'cpu_seconds')
    normal=[m for m in metrics if m['backend']=='c-strict-release' and m['job']!='user-tool']
    native={key:sum(m['native_stats'].get(key,0) for m in normal) for key in normal[0]['native_stats']}
    stats={'groups':20,'wall_seconds':{s:total(rows,'wall_seconds',s) for s in ('python','c')},'cpu_seconds':{s:total(rows,'cpu_seconds',s) for s in ('python','c')},
           'wall_speedup':wall,'cpu_speedup':cpu,'packets_each_side':sum(r['packets'] for r in rows),'native_stats':native,
           'original_15':{'wall_speedup':rate(original,'wall_seconds'),'cpu_speedup':rate(original,'cpu_seconds')},
           'five_controls':{'before_wall_speedup':rate(before,'wall_seconds'),'after_wall_speedup':rate(new_controls,'wall_seconds'),
                'before_c_wall':total(before,'wall_seconds','c'),'after_c_wall':total(new_controls,'wall_seconds','c'),
                'before_c_cpu':total(before,'cpu_seconds','c'),'after_c_cpu':total(new_controls,'cpu_seconds','c')},'load_samples_1min':[min(loads),max(loads)]}
    emit(HERE/'evidence/performance.json',stats)
    tables=['| 真实回归组 | Python 墙钟秒 | C 墙钟秒 | Python CPU 秒 | C CPU 秒 | 墙钟倍数 | 每侧指令包 | 核对 |','| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for row in rows:
        tables.append('| '+row['job']+' | '+' | '.join(f"{row[key][side]:.3f}" for key,side in [('wall_seconds','python'),('wall_seconds','c'),('cpu_seconds','python'),('cpu_seconds','c')])+f" | {row['speedup_wall']:.2f} | {row['packets']:,} | 一致 |")
    controls=stats['five_controls']
    report=f'''本轮完成：三项 P1 已修复，20 组双跑一致，墙钟提速 {wall:.2f} 倍，CPU 提速 {cpu:.2f} 倍。

本轮交付可选 API6 候选，等待另开复审。原工具、r3、主线运行器及已放行的模拟器均未切换。

## 复审修复

| 问题 | 原因与修复 | 本轮验证 |
| --- | --- | --- |
| P1-01 导出身份 | C 导出类缺少原 `PythonBackend.__module__`。现与原类的模块、名称及限定名一致。原 g139 reporter 的断言完整保留。 | 两侧均为 `OBSERVED_P1`；{busy['comparison']['compared_values']:,} 个值相同，各执行 20,932,506 个指令包。 |
| P1-02 旧 PASS 续用 | 旧身份未绑定测试本体及其依赖。schema 3 绑定完整队列、参数、显式文件、环境、入口和适配器；每进程记录实际文件与模块源码 SHA，以及导入候选路径，续跑逐项重新核对。所有输入收据、产品和日志也必须完整。 | 正式参数和独立 driver 各 11 项；改测试、helper、数据、参数、队列及优先导入包均拒绝复用，恢复原输入后可复用。改断言后的全新 Python/C 均 FAIL。旧版收据拒绝复用。 |
| P1-03 写事件依赖 | 快速写仅保护捕获的事件类，漏查原 write 函数 globals 的 `WriteEvent` 解析结果。现将字典、名称、存在性和对象身份纳入 C 兼容性协议，并在快速写前重查；变化时执行原 Python 写调用。已有构造函数、代码、MRO 和范围保护保留。 | 执行前、断点及写回调换绑定，替换构造函数和代码，以及先快速写后改变校验，调用、错误及完整状态均相同。校验抛错两侧均 FAIL。实际关闭绑定检查的变异库重新出现差异，被核对器抓到。 |

锁忙用例仅排除 `/seconds`、`/started_ns`、`/ended_ns` 三项计时字段；原 `OBSERVED_P1` 判断保留，未改为 PASS。完整比较见 `local/busy/comparison.json`。

续跑原型曾扫描全仓近十万个源码：其他支线修改无关文件会误拒绝恢复，开销也过高，已撤回。改为实际读取依赖、加载模块和导入解析路径；另固定启动时的原生 stat，避免旧运行器的虚拟路径映射被误记为真实文件。先前准备失败及拒绝日志保留。测速驱动移除未经身份校验的 `--resume`，直接调用旧运行器 main 会要求改用 `run.py`。计算槽覆盖执行和产品哈希，避免辅助核对与两个 worker 重叠。

收尾又发现临时目录整体排除会漏掉其中已有的输入，实际复现了改临时 JSON 后仍复用 PASS。最终正式入口使用 `input_trace_strict.py`：既有临时输入也记录 SHA；只有观察到本进程生成且文件状态实际改变的临时产物才可排除，记录生成证据。仅传入 `-o` 的已有文件、写入失败的只读输入均不能豁免。普通临时输入、已有输出参数及失败写入三组各 6 项检查通过；最终双入口各 11 项重新通过。

严格记录器先通过原运行器重跑完整 50mm cutpoints：{strict_metric['wall_seconds']:.3f} 墙钟秒、{strict_metric['cpu_seconds']:.3f} CPU 秒，27,772,968 个指令包、33,529 个产品值与 Python 对照一致。随后 C 侧的 20 组和前置工具全部使用最终严格记录器重跑，与本轮冻结且重新核对输入身份的 Python 基线逐字段比较。本报告速度表使用最终 C 侧数据，内核和正常库 SHA 始终相同。初轮原记录器数据保留在 `local/comparisons/`，最终数据在 `local/comparisons-strict/`。

## 身份和边界

正常 API6 库 SHA256：`{build['sha256']}`。清单为 `tools/speedlab/harness_release_r4/local/ccore/build.json`，绑定当前源码、Python ABI、架构及编译命令。候选在 `tools/speedlab/harness_release_r4/`，报告与证据在本目录。冻结的 {len(start['frozen']):,} 个原文件 SHA 在结束时全部一致。

真实回归使用 g150 正式 DAT `c4878f6600cec8b2dfe973c0888bc9c61bcd3a51e6d20a63e12c7dcceb3f9b78` 和原 `engine_v58_g150`。锁忙反例使用原 g139 包，DAT 为 `aab6c4f8d525dfda94fd33861c0a632b16f4d0df5481c7d9423e2bf820399e21`。实际读取的输入及模块另存于每进程收据，最终已重新核对。

全程离线、只写 speedlab 和指定 Scratch。重负载串行，归档和哈希在测试退出后执行。入口 nice 15，保留运行器再次降优先级后 worker 为 nice 20；所有进程收据均核对优先级。每组超时 10,800 秒，至少历史时长三倍。采样一分负载为 {min(loads):.2f}–{max(loads):.2f}。未联网、未访问相机或存储卡、未作 Git 写操作、未启动子代理。

## 20 组真实双跑

20 组各侧实际执行 {stats['packets_each_side']:,} 个指令包（`total_steps`），C 原生指令包数相同，正常组 fallback_calls 和 fallback_steps 均为 0。前置 user-tool 另跑，不计入 20 组速度合计。

Python 墙钟 {stats['wall_seconds']['python']:.3f} 秒、C {stats['wall_seconds']['c']:.3f} 秒，直接相除为 {wall:.4f} 倍；子进程树 CPU 为 {stats['cpu_seconds']['python']:.3f} 对 {stats['cpu_seconds']['c']:.3f} 秒，即 {cpu:.4f} 倍。计时覆盖复制的原运行器调用、进程启动、完整测试和退出收据，不含随后复制证据和逐字段比较。初轮先后交替对跑，补修输入记录后 C 侧完整重跑；表取已核对身份的原 Python 基线和最终 C 侧。机器外部负载变化，未将倍率外推完整 81 组，也未将工作负载时间冒充完整入口的调度及复核总耗时。

{chr(10).join(tables)}

共核对 {comparison['json_files']} 份产品 JSON、{comparison['compared_values']:,} 个值；包括前置 user-tool 的 12 份、953 个值，20 组本身为 {comparison['json_files']-12} 份、{comparison['compared_values']-953:,} 个值。状态、错误、观察记录、顺序和数值类型严格相同。只排除包装结果根 `/seconds`；验收产品中的 seconds 不排除，变异自检已证明。源码绑定依赖按实际 SHA 单独核对，后端路径差异逐项列出；参考库 PID 安装名、节地址和展开元数据另列，全部原始 SHA 保留，不宣称整库逐字节相同。详细规则及差异表见 `local/comparisons/`。

三单元 view-reentry 每侧均有完整 70 个子进程产品和 71 份进程收据，逐单元核对值数为 {', '.join(v['unit']+' '+format(v['compared_values'],',') for v in views)}。见 `evidence/view-completeness.json`。

## 修复前后测速

旧报告原 15 组墙钟 6.1888 倍、CPU 6.7578 倍；本轮相同 15 组为 {rate(original,'wall_seconds'):.4f}、{rate(original,'cpu_seconds'):.4f} 倍。这是不同时间的单次运行，不能用差值归因修复。

另取 50mm safety、50mm view-reentry、28mm exits、28mm users、MOUNT cutpoints 五组，在本轮同一输入下跑 Python、原 API5 C、新 API6 C，全部产品比较一致。此表最终 API6 含严格输入记录，原 API5 使用初轮记录器：

| 五组直接合计 | 修复前 API5 | 最终 API6 严格记录器 |
| --- | ---: | ---: |
| C 墙钟秒 | {controls['before_c_wall']:.3f} | {controls['after_c_wall']:.3f} |
| C CPU 秒 | {controls['before_c_cpu']:.3f} | {controls['after_c_cpu']:.3f} |
| 同一批 Python / C 墙钟倍数 | {controls['before_wall_speedup']:.4f} | {controls['after_wall_speedup']:.4f} |

C 墙钟变化 {(controls['after_c_wall']/controls['before_c_wall']-1)*100:+.2f}%，CPU 变化 {(controls['after_c_cpu']/controls['before_c_cpu']-1)*100:+.2f}%。单次观测不足以判定这一级别的微小性能变化。未相乘阶段倍率。见 `local/comparisons-before/` 和 `evidence/performance.json`。

## 门槛及变异

方法、接收对象、MRO、属性访问及 trace 共 50 项一致；6,080 条实际编码逐条对拍和 40 个边界一致；七范围边缘 90 项、审计依赖变更 17 项、先过滤再变更 6 项一致。受无符号 32 位地址约定的 20 项错误检查一致；另三个负端点或超大端点 trace 配置的既有差异原样保留，未计入通过数。

事件绑定五项、校验异常两项、构造和写后变更五项均一致。实际漏查事件绑定、漏查解析链及少报审计命中的变异都被结构化比较抓到。默认、显式 Python、新 C 以及缺清单/缺库/ABI/API/源码 SHA/库 SHA 控制 12 项符合预期；错误 API 使用实际编译的版本 4 库。正式入口的默认、实际原生执行、续跑、产品/队列/后端/源码/库变化另有完整控制。

产品核对器 7 项变异/控制通过，覆盖判定、数据类型、重复 JSON 键、验收 seconds、DAT 单字节、执行量，以及允许排除的包装计时字段。所有临时变异均恢复。

最终 API6 的完整 50mm view-reentry 写入录制，过滤关/开各重跑全部 70 子进程。CPU 写 tape 为 {tapes['comparisons']['write']['files']} 文件、{tapes['comparisons']['write']['records']:,} 条、{tapes['comparisons']['write']['bytes']:,} 字节；审计 tape 为 {tapes['comparisons']['audit']['files']} 文件、{tapes['comparisons']['audit']['records']:,} 条、{tapes['comparisons']['audit']['bytes']:,} 字节，两侧逐字节一致。少报一次命中的实际变异从 {mutation['normal_records']} 变为 {mutation['altered_records']} 条，被抓到。这项 tape 是同一 C 核心过滤关/开的比较；Python/C 的真实验收产品比较见前述 20 组，未将其说成 Python/C 全量写 tape。

## 可选入口及复核

```sh
GXR_HARNESS_BACKEND=c nice -n 15 /usr/bin/python3 -I -B tools/speedlab/host_regression_r4/run.py --name c-r4-new --queue tools/speedlab/host_regression_r4/queue.json --slots 1
```

取消该环境变量或设为 `python` 使用原 Python 后端，并选择新运行名。显式 C 的构建身份损坏会停止；执行中方法、事件或审计依赖变化按原 Python 逻辑回退并保留当前指令包剩余 slot 的顺序。`SWITCH_CHECKLIST.md` 已落实复审要求：已知 OBSERVED/FAIL 基线、实际依赖身份、事件校验反例、可执行默认/损坏控制、真实执行计数及后续完整矩阵。

完整 81 组未在本轮执行，待主线空闲且新复审通过后再运行，包含预期失败和观察状态。下一轮先剖析最慢真实组的兼容性检查与回调成本，每次只改一处，继续用同负载全量产品及写入记录核对；本轮未改模拟器或启用快照。
'''
    (HERE/'REPORT.md').write_text(report)
    entries=[['时间','改动','修前指标','修后指标','核对','决定','原因']]
    decisions=[
        ('导出模块身份','Python OBSERVED_P1 / C FAIL','两侧 OBSERVED_P1','8265 值一致','保留','保留原 reporter 断言'),
        ('事件 globals 绑定保护','3 次漏调用；校验 C PASS / Python FAIL','正常样本一致；实际漏查变异被抓到','绑定/函数/错误/状态一致','保留','快速写前核对解析对象'),
        ('全仓源码身份扫描','约 96939 文件；无关支线变化误拒绝','撤回全仓扫描','正常恢复误拒绝','撤回','改为实际依赖与导入候选'),
        ('导入身份使用补丁后 stat','虚拟文件误记为存在','固定原生 stat','双入口各 11 项通过','保留','避免旧路径映射影响真实身份'),
        ('临时目录整体排除','已有临时输入变化后复用 PASS','严格入口绑定已有临时输入','3 组各 6 项；真实 cutpoints 全值相同','撤回','仅排除有生成证据的临时产物'),
        ('最终严格输入记录器','源码/普通输入身份','补充临时输入及生成证明','双入口各 11 项、真实组 33529 值一致','保留','C 核心及正常库未变化'),
        ('绝对路径清理','dir_fd 相对名被自身写入边界拒绝','绝对路径递归清理','原边界未放宽','保留','仅修清理调用方式'),
        ('旧集成测试拒绝优先级','预期产品检查先报错','完整队列身份先拒绝','修正消息控制后全项通过','保留','完整队列变化必须先拒绝'),
        ('最终 API6 20 组',str(stats['wall_seconds']['python']),str(stats['wall_seconds']['c']),'20 组全部产品一致','保留',f'墙钟 {wall:.4f} 倍；不外推 81 组'),
        ('五组修复前后对照',str(controls['before_c_wall']),str(controls['after_c_wall']),'三方产品一致','保留','单次观测，性能差异小'),
        ('最终 API6 全量 tape','过滤关','过滤开','逐字节一致；少报一次变异被抓到','保留','保留全部 70 子进程'),
    ]
    entries.extend([[stamp,*row] for row in decisions])
    for row in rows:
        entries.append([stamp,row['job'],f"P wall={row['wall_seconds']['python']:.6f};cpu={row['cpu_seconds']['python']:.6f}",f"C wall={row['wall_seconds']['c']:.6f};cpu={row['cpu_seconds']['c']:.6f}",'全部产品一致','保留',f"packets={row['packets']}; wall={row['speedup_wall']:.6f}"])
    (HERE/'LEDGER.tsv').write_text('\n'.join('\t'.join(map(str,row)) for row in entries)+'\n')
    process_text=subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,stat=,command='],text=True)
    signatures=('/host_regression_r4/measure.py','/host_regression_r4/tapes_run.py','/host_regression_r4/repair_checks.py','/host_regression_r4/strict_all.py','/host_regression_r4/strict_group.py',
                '/run/backend_launch.py','/run/tape_launch.py','/run/legacy_call.py')
    active=[]
    for line in process_text.splitlines():
        fields=line.strip().split(None,4)
        if len(fields)!=5 or int(fields[0])==os.getpid():continue
        if 'speedlab/host_regression_r4/' in fields[4] and any(value in fields[4] for value in signatures):
            active.append({'pid':int(fields[0]),'ppid':int(fields[1]),'nice':fields[2],'status':fields[3],'command':fields[4]})
    assert not active,active
    emit(HERE/'evidence/process-final.json',{'passed':True,'utc':stamp,'active_workers':active,'inspection':'ps pid/ppid/ni/stat/command; current delivery process excluded'})
    # Retain version-control build bytes before removing the designated temporary tree.
    temporary_version=TEMP/'switch';archive=HERE/'local/controls/retained-version-control'
    if temporary_version.exists():
        archive.mkdir(parents=True,exist_ok=True)
        for path in temporary_version.iterdir():
            if path.is_file():shutil.copyfile(path,archive/path.name)
    assert not TEMP.is_symlink() and TEMP.resolve()==TEMP
    remove_absolute(TEMP)
    emit(HERE/'evidence/cleanup.json',{'utc':stamp,'temporary_root':str(TEMP),'removed':not TEMP.exists(),'worker_loads_finished':True,'measurements':len(metrics),'heavy_slots':1})
    targets=[HERE,ROOT/'tools/speedlab/harness_release_r4']
    paths=sorted(p for folder in targets for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
    manifest=''.join(sha(path)+'  '+str(path.relative_to(ROOT))+'\n' for path in paths)
    (HERE/'SHA256SUMS').write_text(manifest)
    mismatches=[]
    for line in manifest.splitlines():
        digest,name=line.split('  ',1)
        if sha(ROOT/name)!=digest:mismatches.append(name)
    assert not mismatches
    print(json.dumps({'passed':True,'groups':20,'manifest_files':len(paths),'manifest_sha256':sha(HERE/'SHA256SUMS'),'wall_speedup':wall,'cpu_speedup':cpu,'temporary_removed':not TEMP.exists()}),flush=True)

if __name__=='__main__':main()
