"""Report the completed subset and the explicit scope cancellation."""
from pathlib import Path
import datetime,difflib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT,OUT,TREE,PACKAGE,DAT,save,file_sha
UNITS=('50mm','28mm','mount')
NAMES={'50mm':'A12 50mm','28mm':'A12 28mm','mount':'MOUNT A12'}
PIN='9724268c3d8a2c8c60650b903db1d536ca6ab594f95144d5991cb3b964ebb262'
HERE=OUT/'r2'
def read(name):return json.loads((OUT/name).read_text())

def main():
    initial=read('r2/before/acceptance.json');audit=read('r2/record-safety.json');matrix=read('r2/matrix-record-safety.json')
    evidence=read('r2/evidence-manifest.json');reuse=read('r2/reuse-gen121.json');stop=read('r2/scope-stop.json')
    assert audit['status']==matrix['status']==evidence['status']==reuse['status']=='PASS'
    assert stop['status']=='STOPPED_USER_SCOPE' and file_sha(DAT)==PIN and DAT.stat().st_size==63380
    frozen=read('r2/inputs-before.json');changed=[];missing=[]
    for row in frozen['files']:
        p=ROOT/row['path']
        if not p.is_file():missing.append(row['path'])
        elif file_sha(p)!=row['sha256']:changed.append(row['path'])
    engine=[n for n in changed if n.startswith('firmware/engine_v44_keep/')]
    assert engine==['firmware/engine_v44_keep/EVIDENCE_SHA256SUMS']
    assert not any(n.startswith('firmware/package_v36_g122/') for n in changed)
    assert not any(n.startswith(('firmware/engine_v44_keep/','firmware/package_v36_g122/')) for n in missing)
    old_names={r['path'] for r in frozen['files']}
    assert not [p for folder in (TREE,PACKAGE) for p in folder.rglob('*') if p.is_file() and str(p.relative_to(ROOT)) not in old_names]
    save('r2/input-stability.json',dict(status='PASS',dat_sha256=PIN,dat_bytes=63380,firmware_source_changes=[],engine_changed_files=engine,package_changed_files=[],card_files=30,compared_files=len(frozen['files'])))
    queues={};remaining={};checks=[]
    for u in UNITS:
        q=read('r2/commands-'+u+'.json');rows=q['commands'];assert len(rows)==5
        assert all(r['returncode']==0 and r['dat_sha256']==PIN and r['sources_unchanged'] for r in rows)
        for r in rows:assert file_sha(OUT/r['log'])==r['log_sha256']
        queues[u]=rows;current={tuple(r['command']):r for r in rows};updated=[]
        for old in initial['remaining_commands'][u]:
            row=dict(old);r=current.get(tuple(row['command']))
            if r:row.update(status='PASS',record=r,provenance='Executed in r2 before scope cancellation.')
            elif row['record'] is None:row.update(status='NOT_RUN_SCOPE_STOPPED',reason='Further gen 122 regression cancelled after two P1 findings.')
            else:row['provenance']='Previously verified same-DAT evidence; not rerun in r2.'
            updated.append(row)
        assert sum(r['status']=='PASS' for r in updated)==7 and sum(r['record'] is None for r in updated)==17
        remaining[u]=updated
        for name in ('ah','h07-all','fn2-failures','exits','confirm-paths'):
            p='native/'+name+'-'+u+'.json';v=read(p);assert v['status']=='PASS'
            checks.append(dict(unit=u,file=p,sha256=file_sha(OUT/p),status='PASS'))
    save('r2/completed-check.json',dict(status='PASS_COMPLETED_SUBSET',dat_sha256=PIN,executed_new_commands=15,not_run_commands=51,command_artifacts=checks,full_regression_status='STOPPED_USER_SCOPE',new_functional_groups='NOT_RUN',full_keep_cases='NOT_RUN; previous 12 core cases per unit retained'))
    save('r2/queue.json',dict(status='STOPPED_USER_SCOPE',dat_sha256=PIN,executed_commands=15,remaining_original_commands=51,units={u:dict(executed=5,returncodes=[r['returncode'] for r in queues[u]],unexecuted_original=17,unexecuted_extra=4) for u in UNITS}))
    table=initial['matrix']
    for row in table:
        g=row['group']
        if g=='原始通信日志复核':row['states']=audit['units']
        elif g=='其余原审查 24 条命令':row['states']={u:'STOPPED_USER_SCOPE 7/24' for u in UNITS}
        elif g in ('工作区与界面分配失败后重试','ERR 原因码、单行光标及空说明','列表与面板合并循环各 16 轮'):row['states']={u:'NOT_RUN_SCOPE_STOPPED' for u in UNITS}
        elif g=='W 前失败保留列表和面板，三种入口重试':row['states']={u:'PASS：前轮 12 核心例' for u in UNITS}
    table.insert(5,dict(group='keep-cases 完整 36 例',states={u:'NOT_RUN_SCOPE_STOPPED；前轮仅 12 核心例' for u in UNITS}))
    table.extend([dict(group='哨兵检测行内部分复位',states={'50mm':'FAIL P1-01：独立模型反例','28mm':'OPEN：数据枚举有未覆盖位置','mount':'OPEN：数据枚举有未覆盖位置'}),dict(group='H01 推迟核对后半按退出',states={'50mm':'FAIL P1-02：独立原生反例','28mm':'OPEN：未跑该原生反例','mount':'OPEN：未跑该原生反例'})])
    review=ROOT/'research/review_g122/REVIEW.md'
    save('acceptance.json',dict(initial,matrix=table,remaining_commands=remaining,r2=dict(status='FAIL_KNOWN_P1_STOPPED_USER_SCOPE',report='r2/REPORT.md',new_commands_executed=15,new_commands_not_run=51,acceptance='NOT_ACCEPTED_FOR_CARD',record_safety='r2/record-safety.json',reusable_auditor='research/g122_keep_list/audit_records.py',full_keep_cases='NOT_RUN_SCOPE_STOPPED',new_functional_groups='NOT_RUN_SCOPE_STOPPED',findings_source=dict(path=str(review.relative_to(ROOT)),sha256=file_sha(review),read_only=True),known_findings=['P1-01 partial row reset not detected','P1-02 deferred H01 half-shutter exit skips DAT'])))
    save('record-safety.json',audit)
    patch=[]
    for name in ('audit_records.py','run_native.py','keep_cases.py'):
        patch.extend(difflib.unified_diff((HERE/'before'/name).read_text().splitlines(True),(OUT/name).read_text().splitlines(True),fromfile='before/'+name,tofile='after/'+name))
    (HERE/'test-tools.patch').write_text(''.join(patch))
    lines=['有缺陷：gen 122 有两个已确认 P1，不能上卡。','',
      '已按编排者更新停止剩余回归。三条正在运行的确认命令自然结束后，调度进程退出，没有再启动下一条。只补完通信记录复核器、证据清单与实际状态记录。','',
      'DAT 为 firmware/package_v36_g122/SD_ROOT/GXRCE.DAT，63,380 B，generation 122，SHA256 `'+PIN+'`。固件源码、DAT、卡包均未改变；未写 engine_v45_verify、package_v36_g123、g123_fix，未操作相机、存储卡或网络，未启动子代理。','',
      '## 已确认缺陷','',
      '独立复审确认 P1-01：哨兵以外的行内部分复位会被当作核对成功；P1-02：H01 推迟核对后，原生半按退出可以不调用 DAT。50mm 的模型与原生反例已成立；28mm/MOUNT 的对应原生反例本轮未执行。来源为 [独立复审](../../review_g122/REVIEW.md)，本轮只读该报告，未修复或重复执行其用例。RPC 地址复核通过不关闭这两个行为缺陷，也不证明一条哨兵代表整行。','',
      '## A：通信记录复核器','',
      '正式入口为 `research/g122_keep_list/audit_records.py`，同内容副本在 `research/g122_keep_list/r2/audit_records.py`。仅依赖 Python 标准库，不导入某代构建目录或 common.py。DAT、记录位置和输出路径均显式传参，从 DAT 的 M+32+12j 解析九行映射及 T，按其真实 SHA 筛选记录。适用于本项目相同 DAT 布局的其他 generation，已用 gen 121 的原 DAT 和三份已有日志验证复用，未运行旧代回归。','',
      '完整 RPC 流必须有 cmd/value/page/result/t；故障事件摘要单独登记，不当作通信流。显式 rpc_log 缺少完整记录仍判失败。每次 X/V/W 检查映射范围，半字边缘 W 必须保留前序读回的相邻字节；失败无设备效果时不推进游标，先产生效果再报失败时依据 device_result 处理。带 page_before/page_after/address 的恢复轨迹另行识别。','',
      '在仓库根复核已有三份主矩阵：','',
      '```sh',
      '/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py \\',
      '  --dat firmware/package_v36_g122/SD_ROOT/GXRCE.DAT \\',
      '  --records research/g122_keep_list/native/matrix-50mm.json \\',
      '            research/g122_keep_list/native/matrix-28mm.json \\',
      '            research/g122_keep_list/native/matrix-mount.json \\',
      '  --output research/g122_keep_list/r2/matrix-record-safety.json',
      '```','',
      '三单元均 PASS，18 份故障事件摘要被正确识别。三份矩阵本身没有完整 rpc_log，结果中的 coverage.raw_streams_present 为 false；本次检查记录类型、原生写入来源、文件计数与矩阵已有的运行时范围记录，没有虚构不存在的原始通信流。','',
      '另对现存完整日志、三份 open-counts 与 machine-gates 重跑，三单元均 PASS，共 '+str(len(audit['communication_logs']))+' 条去重流。两次正常重开的哨兵半字完全在行内。证据见 [主矩阵复核](matrix-record-safety.json)、[完整日志复核](record-safety.json)、[14 项复核器检查](auditor-checks.json)、[gen 121 复用结果](reuse-gen121.json)。旧 FAIL 保留在 [before/record-safety.json](before/record-safety.json)。','',
      '| 单元 | 完整流 | X | V | W | 边缘保留检查 | 结果 |','| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for u in UNITS:
        t=audit['unit_totals'][u];lines.append('| '+NAMES[u]+' | '+' | '.join(str(t.get(k,0)) for k in ('logs','X','V','W','preserved_edges'))+' | '+audit['units'][u]+' |')
    lines += ['', '下一代执行者可替换以下三个路径参数复用：','',
      '```sh',
      '/usr/bin/python3 -I -B research/g122_keep_list/audit_records.py \\',
      '  --dat /absolute/path/to/GXRCE.DAT \\',
      '  --records /absolute/path/to/records-or-json \\',
      '  --output /absolute/path/to/record-safety.json',
      '```','',
      '`--records` 接受多个文件或目录，目录递归读取 JSON；单元顺序固定为 50mm、28mm、mount。不同 DAT SHA 的文件列入 excluded_other_dat，不计为本候选通过。可选 `--sentinel-records` 只用于显式提供 gen 122 的 20 次调用样本；下一代取消该路径时省略。它只证明读取地址在行内。','',
      '## B、C：已跑与未跑','',
      '本轮实际执行 15/66 条缺失命令，每单元五条，全部返回 0。加上前轮已确认的 retain、measure，各单元为 7/24，只有五条是本轮运行。完整 argv、cwd、输入摘要、耗时、返回值与日志 SHA 在 commands-50mm.json、commands-28mm.json、commands-mount.json；stdout/stderr 在 logs/，实际产物摘要见 [completed-check.json](completed-check.json)。','',
      '| 已跑功能 | A12 50mm | A12 28mm | MOUNT A12 |','| --- | --- | --- | --- |']
    for i,label in enumerate(('A–H 原路径','H07 全状态','Fn2 失败情形','原生退出','确认与 ADJ')):
        cells=[]
        for u in UNITS:
            r=queues[u][i];cells.append('PASS，rc=0，'+('≤ ' if r.get('duration_is_upper_bound') else '')+str(round(r['seconds'],1))+' s')
        lines.append('| '+label+' | '+' | '.join(cells)+' |')
    lines += ['',
      '三条确认命令自然结束后，退出码从仍由调度器持有的僵尸进程 xstat 读回，均为 0。其耗时是日志创建至观察到退出的上界。停止过程与 PID/出生身份记录见 [scope-stop.json](scope-stop.json)。','',
      '每单元另外 17 条、共 51 条没有执行：latch_paths、native_names、entry_switch fn2；concurrent_menu 的 recovery/fallback/nested 与 other_menu 五个切点；ui_cutpoints 两项；coalescing 两个切点；failure_boundaries 两项。acceptance.json 对这些项目标记 NOT_RUN_SCOPE_STOPPED，record 保持 null。','',
      '工作区与 UI 分配失败后重试、ERR 原因码/单行光标/空说明、列表与面板各 16 轮三个新功能组均未运行。完整 keep-cases 36 例也未启动；只保留前轮每单元 12 例核心组合，不算完整覆盖。','',
      '## D：清单与输入','',
      '旧 EVIDENCE_SHA256SUMS 有 359 项，其中 100 项不符。已保留旧清单，并按 engine_v44_keep 重新生成 '+str(evidence['entries'])+' 项，仅排除清单自身，路径以该目录为基准，hashlib 与 shasum 逐项自检通过。见 [evidence-manifest.json](evidence-manifest.json)、[自检输出](evidence-selfcheck.log)、[旧清单](before/EVIDENCE_SHA256SUMS)。','',
      '固件源码差异为零；engine 目录唯一修改为该证据清单；卡包 30 个文件未变，29 个固定文件仍与 gen 120b 相同。见 [input-stability.json](input-stability.json)。受保护输入检查覆盖 37,836 项。验收工具调整包括复核器、local/ 缓存与夹具路径，以及本轮未使用的强制重跑开关，见 [test-tools.patch](test-tools.patch)。','',
      '仓库根基准的 ../SHA256SUMS 最后重新生成，覆盖 g122_keep_list、engine_v44_keep、package_v36_g122 全部普通文件，仅排除清单自身；hashlib/shasum 自检和 CARD_SHA256SUMS 完整 30 项核对见 ../checksum-selfcheck.json。','',
      '范围缩小后交回时限为 30 分钟。报告写于 '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'。','',
      '## 三单元完整验收表','',
      '除本轮五条命令与 A 外，保留的 PASS 来自前轮同 SHA 的已核实记录；已接受的 resident、拍摄及说明区限制保持原状态。','',
      '| 功能组 | A12 50mm | A12 28mm | MOUNT A12 |','| --- | --- | --- | --- |']
    for row in table:lines.append('| '+row['group']+' | '+' | '.join(row['states'][u] for u in UNITS)+' |')
    (HERE/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('PASS stopped-scope report and acceptance; gen 122 remains rejected',flush=True)
if __name__=='__main__':main()
