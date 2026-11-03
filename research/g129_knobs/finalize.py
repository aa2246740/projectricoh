"""Bind focused evidence to the final artifact and seal the delivery."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fences import ROOT,WORK,ENGINE,PACKAGE,enable,check_inputs

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--incomplete');args=parser.parse_args()
    enable();frozen=check_inputs();dat=PACKAGE/'SD_ROOT/GXRCE.DAT';digest=sha(dat)
    raw=dat.read_bytes();bss=int.from_bytes(raw[116:120],'big');engine=int.from_bytes(raw[136:140],'big')
    request=7504+((len(raw)+bss+3)&~3);assert request<=108124
    evidence={};missing=[];folder=WORK/'local/release129/review_g126'
    def collect(name,path,valid):
        if path.exists():
            value=read(path)
            if valid(value):evidence[name]=value;return
        missing.append(name)
    collect('host',WORK/'host-results.json',lambda d:d.get('status')=='PASS' and d.get('dat_sha256')==digest)
    collect('codegen',WORK/'codegen.json',lambda d:d.get('status')=='PASS' and d.get('dat_sha256')==digest and
            all(row.get('coverage') and row['coverage']!='UNMAPPED' for row in d['changed_functions'].values()))
    for unit,name in enumerate(('50mm','28mm','mount')):
        collect('target-'+name,WORK/f'target-{unit}.json',lambda d:d.get('status')=='PASS' and d.get('dat_sha256')==digest and d.get('cases',0)>=1000)
        for script in ('ownership_settings','cold_reentry'):
            collect(script+'-'+name,folder/f'{script}---generation-129---unit-{name}.json',
                    lambda d:d.get('returncode')==0 and d.get('dat_sha256')==digest)
        collect('product-'+name,folder/f'product-{name}.json',lambda d:d.get('status')=='PASS' and d.get('dat_sha256')==digest and
                d.get('screens')==list(range(7)) and d.get('endpoint_checks')==8 and len(d.get('sequence_steps',[]))>=19)
    collect('communications',WORK/'communications.json',lambda d:d.get('status')=='PASS' and d.get('dat_sha256')==digest and d.get('records',0)>0)
    if missing and not args.incomplete:raise RuntimeError('INCOMPLETE: '+', '.join(missing))
    status='有缺陷' if missing or args.incomplete else '可以交复审'
    fixed=ROOT/'firmware/package_v36_g120b/SD_ROOT';files=list((PACKAGE/'SD_ROOT').iterdir());assert len(files)==30
    assert all(sha(path)==sha(fixed/path.name) for path in files if path.name!='GXRCE.DAT')
    host=evidence.get('host',{});targets=[evidence.get('target-'+name,{}) for name in ('50mm','28mm','mount')]
    products=[evidence.get('product-'+name,{}) for name in ('50mm','28mm','mount')]
    stack=[]
    for name in ('50mm','28mm','mount'):
        path=folder/f'product-stack-{name}.json'
        if path.exists():stack+=read(path)
    outer=max((row['stack_bytes'] for row in stack if row['initial_sp'] and row['stack_bytes']>=0),default=0)
    assert args.incomplete or outer>0
    sizes=[('DAT',len(raw),88700,98304),('引擎段',engine,59524,65536),('BSS',bss,11920,114688-len(raw)),
           ('DAT 与 BSS',len(raw)+bss,100620,114688),('loader 主请求',request,108124,122192)]
    table='\n'.join(f'| {name} | {actual:,} | {budget:,} | {limit:,} | {limit-actual:,} |' for name,actual,budget,limit in sizes)
    counts=' / '.join(str(value.get('cases','INCOMPLETE')) for value in targets)
    compiled=evidence.get('codegen',{})
    code_count=len(compiled.get('changed_functions',{}));frames=compiled.get('math_maximum_frame','INCOMPLETE')
    sequence_count=sum(len(value.get('sequence_steps',[])) for value in products)
    frame_count=sum(len(value.get('frames',[])) for value in products)
    reference_units=[value['unit'] for value in products if value.get('compute_reference_leaf')]
    reference_note=('、'.join(reference_units)+' 的菜单专项复用该单元已通过目标执行的完整计算结果。') if reference_units else '已完成的菜单专项未使用计算结果叶函数。'
    summary={'status':status,'dat_sha256':digest,'frozen_inputs':frozen,'missing':missing,'reason':args.incomplete,
             'evidence':{name:{key:value for key,value in item.items() if key in ('status','returncode','dat_sha256','cases','frames') and key!='frames'}
                         for name,item in evidence.items()},'outer_stack_bytes':outer,'target_cases':[item.get('cases',0) for item in targets]}
    (WORK/'acceptance.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    report=f'''{status}

# gen 129 knobs v2 集成报告

本轮以指定 gen 127 快照接入已验收的数据、菜单和数学模块。结论只覆盖本任务的聚焦检查，完整历史回归由独立验收承担。没有连接或操作相机、存储卡，也没有使用网络或启动子代理。

最终 DAT 为 `{digest}`，generation 为 129。基线 DAT 为 `9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6`。

## 接线与冻结边界

运行态统一使用 `UvLevels` 的 `int16_t v[10]`。默认 Amount 为 100，其他项目为 0；会话、八个配方缓存、32 条只读条目的会话草稿、当前态和确认态都保存完整 20 B。补偿默认向量也保留 Amount=100，4+2 次边界保持原样。

`compute` 和 `project_compute` 从不可变配方重新展开，经 `kv_data_request` 后调用 `kv_apply_work`。2,288 B 的 `KvWork` 放在会话 BSS；先复制原配方，避免共用展开缓冲造成两份底子同址。旧调节数学不再进入最终符号表。没有增加目标堆分配或额外租约。

第七段为 `1,408 + 1,984 + 17,384 = 20,776 B`，三个长度 gate 同步更新。GXTM 与 GXUI v1 继续独立校验，新整数块按原 SHA 使用。旧只读记录仍校验 11 个字段，转换为新向量后再调用 `kv_data_request`。

S 计划保留 gen 127 的 Image 与配方 WB 对，顺序和值都不随新向量变化。`make_plan`、`settings_match` 和归属相关函数的冻结检查见 [编译复核](codegen.json)；`engine_services/services.c` 与基线逐字节相同。

## 尺寸

| 项目 | 实际 B | 设计估算或预算 B | 有效上限 B | 距有效上限 B |
|---|---:|---:|---:|---:|
{table}

主请求另受本任务 108,124 B 预算约束，余量为 {108124-request:,} B。引擎段比设计估算多 {engine-59524:,} B，BSS 比估算少 {11920-bss:,} B；合计满足主请求预算。BSS 的有效上限随 DAT 长度变化。重定位表为 1 项、8 B，新整数块没有逐项指针。

本构建采用 `-Oz`，固定八行界面的字形与引用数组容量缩为八，较十六容量减少 720 B BSS。真实空闲连续堆尚未确认，不能用上述静态余量代替。

## 聚焦检查

| 证据层 | 检查与结果 |
|---|---|
| 主机已证 | 同一数学源码完整比较 {host.get('golden','INCOMPLETE'):,} 例 r2 金标准和 {host.get('domain','INCOMPLETE'):,} 例扩展剂量请求，包含完整 552 B、返回码与统计。 |
| 主机已证 | 集成计算路径检查 3,430 个菜单点，24 个默认值与 gen 127 应用原配方逐字节相同；3,430 个 S 计划均与基线相同。 |
| 主机已证 | 已开放 Amount 的 18 组零值恢复原厂 04；66 组 A、B、A 回零序列等于只改 B。非法预览 slot 在缩窄前拒绝。 |
| M32R 模型已证 | 三个单元分别执行 {counts} 个完整菜单点，覆盖每个配方和项目；原解释后端另核对每单元 15 例。 |
| M32R 模型已证 | 04 与 06 的 Splt 序列及 06 的 Amount 序列，共记录 {sequence_count} 次状态核对；每次核对九行、C/D、T 和完整向量，并检查重开。 |
| M32R 模型已证 | 实际适配器记录 {frame_count} 个发布帧，七种视图均为八行，每行至多八字符；L1 十个逻辑行，03 与 04 项目集合、端点停留和标记通过。 |
| M32R 模型已证 | 三单元按原路径运行归属与冷重入检查，失去归属后设置写入和预览请求为零，下次打开恢复。 |
| 静态与编译码已证 | 复核清单含 {code_count} 个新增或修改的源码函数，覆盖地址与长度、文件操作、原生界面写入、循环与内存。主机分支和未进入最终映像的函数单独标明，不计作执行覆盖。 |
| 静态已证 | 最终 ELF 没有未解析符号，没有系统 libc 或浮点依赖；代码与 DAT 引擎段相同，平移检查通过。 |

计算入口连同外层调用链的最大实测栈深为 {max((item.get('maximum_stack_bytes',0) for item in targets),default=0)} B，数学相关具名函数最大帧为 {frames} B。包含适配器、服务及模型中原生路径的 SP 观察最大为 {outer} B。这些是模型观测，真实 RTOS 最深调用与全局水位未知。

目标批量检查使用只读 `tools/native_harness` 解码最终字节，再由本任务 C 执行器运行实际 M32R 指令；数学、展开、CRC 和整数辅助函数均执行目标指令。原解释后端独立复核样本。菜单与 T 专项使用最终适配器入口，对冻结 CRC 使用已与目标链式输入核对的主机叶函数。{reference_note}实际适配器、状态保存、T 与 RPC 路径仍执行目标代码。详见 [专项模型边界](MODEL_BOUNDARY.md)。

通信复核按原路径调用 `research/g122_keep_list/audit_records.py`，没有使用哨兵选项。结果见 [通信汇总](communications.json)。

## 证据与未知项

数学结果、完整深层条目与模型写入已分开核对。Amount=0 只表示深层条目恢复原厂 04，S 计划仍保留该配方原有 WB 对。06 的 Splt 回零保持自己的 C/D 和 T=0。

LCD、JPEG、真实堆余量、RTOS 水位和实际操作延迟均未知。没有把主机表的可见性预测作为相机验收。基线复审仍按用户安排独立处理，本轮没有合并其他变更。

源码差异见 [相对 gen 127 的差异](source-vs-g127.patch)，入口见 [复核步骤](REPRODUCE.md)，过程修正见 [开发记录](development.tsv)。[用户上机清单草稿](CAMERA_CHECK_DRAFT.md) 限定 50mm、9 分钟。

30 文件包位于 `firmware/package_v36_g129/SD_ROOT`，其中 29 个固定文件与 gen 120b 相同。理光派生字节只保存在被忽略的 `local/`；`SD_ROOT` 指向包内的该目录。`SHA256SUMS` 以仓库根为基准。
'''
    if missing or args.incomplete:
        start=report.index('## 聚焦检查');end=report.index('## 证据与未知项',start)
        available='\n'.join(f'| {name} | 已完成，绑定最终 DAT |' for name in evidence)
        unavailable='\n'.join(f'| {name} | INCOMPLETE |' for name in missing)
        report=report[:start]+f'''## 聚焦检查

在三小时时间盒内未收齐聚焦验收。没有观察到产品行为断言失败；“有缺陷”表示仍有验收缺项，不能标为“可以交复审”。下列结果只采用最终 DAT 的证据。

主机同一源码完整比较 {host.get('golden',0):,} 例 r2 金标准及 {host.get('domain',0):,} 例扩展请求，逐例比较 552 B、返回码及统计。集成路径检查 {host.get('integrated_points',0):,} 个菜单点，24 个默认值、{host.get('plans',0):,} 个 S 计划与 gen 127 相同；18 组 Amount=0 和 66 组回零序列通过。

三个单元的实际 M32R 计算路径分别完成 {counts} 例，覆盖每个配方和项目。计算入口含外层调用链的最大观测栈深为 {max((item.get('maximum_stack_bytes',0) for item in targets),default=0)} B；数学相关具名函数最大帧 {frames} B。适配器与原生模型路径的 SP 最大观测为 {outer} B。编译码四类清单覆盖 {code_count} 个函数，最终 ELF 没有未解析符号、系统 libc 或浮点依赖。

已完成的菜单专项记录 {sequence_count} 次九行、C/D、T 和完整向量核对，以及 {frame_count} 个实际适配器发布帧。50mm 七种视图与八个端点检查通过。28mm 与 mount 各完成 04、06 的 Splt 序列；其余菜单项目未收齐，详见 [部分运行记录](partial-menu.json)。

数值目标执行、菜单模型叶函数和物理相机的边界见 [专项模型边界](MODEL_BOUNDARY.md)。通信状态及流覆盖范围见 [通信结果](communications.json)。

| 检查 | 状态 |
|---|---|
{available}
{unavailable}

'''+report[end:]
        report+='\n## 未完成项\n\n'+(args.incomplete or '聚焦检查尚未全部完成。')+'\n\n'+', '.join(missing)+'\n'
    (WORK/'REPORT.md').write_text(report)
    (PACKAGE/'DELIVERY.md').write_text(f'''{status}

generation 129，30 个文件，29 个固定文件与 gen 120b 相同。

DAT SHA256：`{digest}`。

DAT {len(raw):,} B；引擎段 {engine:,} B；BSS {bss:,} B；loader 主请求 {request:,} B。

聚焦检查和证据边界见 [集成报告](../../research/g129_knobs/REPORT.md)。本任务没有执行相机、存储卡或成像验收。
''')
    selected=set()
    for directory in (ENGINE,PACKAGE,WORK):
        for path in directory.rglob('*'):
            if path.is_file() and 'local' not in path.relative_to(directory).parts and '__pycache__' not in path.parts and path.name!='SHA256SUMS':selected.add(path)
    selected.update(path for path in (PACKAGE/'local/SD_ROOT').iterdir() if path.is_file())
    selected.update(path for path in (ENGINE/'candidate/local/full-r13').iterdir() if path.is_file())
    selected.update(path for path in (ENGINE/'candidate/local/product-r13/m32r-lto-oz').glob('*.su') if path.name.startswith('engine.elf') or path.name.endswith(('-kv_i64.su','-eng_mem.su')))
    selected.update(path for path in folder.rglob('*.json') if not path.name.endswith('-diagnostic.json'))
    for directory in folder.glob('target-state-*-0'):
        selected.update(path for path in directory.iterdir() if path.is_file())
    selected.update((WORK/'local').glob('target-cases-*.bin'))
    sums=''.join(f'{sha(path)}  {path.relative_to(ROOT).as_posix()}\n' for path in sorted(selected))
    (WORK/'SHA256SUMS').write_text(sums);check_inputs()
    print(json.dumps({'status':status,'dat_sha256':digest,'files':len(selected),'frozen_inputs':frozen},ensure_ascii=False))

if __name__=='__main__':main()
