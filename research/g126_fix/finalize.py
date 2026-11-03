"""Verify final acceptance, write the Chinese report, and seal root-relative hashes."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *

UNITS=('50mm','28mm','mount')
GROUPS={
    '首次发布':('cold-reentry-126-{unit}.json',4),
    '未提交会话的 H07':('cold-exit-{unit}.json',2),
    'gen 122 反例':('suite-126-{unit}.json',9),
    '安全边界':('safety-{unit}.json',8),
    '锁定':('locked-{unit}.json',8),
    '锁定重入':('lock-nested-126-{unit}-record_failure_return-after_update_restore-before_redraw-row_draw.json',40),
    'IRQ 开启时切换':('lock-cutpoints-{unit}-irq-enabled.json',16),
    '锁定退出':('lock-exits-126-{unit}.json',24),
    '逐屏六键':('transitions-{unit}.json',42),
    '退出行数与 IRQ':('row-transitions-{unit}-irq.json',21),
    '档位端点':('values-{unit}.json',7),
    '七视图方向键重入':('view-reentry-{unit}.json',70),
    '七视图六键重入':('reentry-all-keys-{unit}.json',210),
    '设置核对及服务失败':('settings-cases-{unit}.json',36),
    '用户条目':('users-{unit}.json',None),
    '另外七个底子':('other-users-{unit}.json',None),
    'M32R 档位与窗口':('project-boundary-{unit}.json',None),
    '逐屏文字':('labels-{unit}.json',None),
}

def load_json(name):
    return json.loads((OUT/name).read_text())

def acceptance():
    obligations=[]
    for name,(pattern,count) in GROUPS.items():
        for unit in UNITS:
            path=OUT/'evidence'/pattern.format(unit=unit)
            value=json.loads(path.read_text()) if path.exists() else {}
            cases=value.get('cases',value.get('results',[]))
            removed=sum(row.get('status')=='REMOVED_UPDATE_PATH' for row in cases)
            ok=value.get('status')=='PASS' or name=='首次发布' and bool(cases)
            expected=load_json('evidence/user-tool.json')['fixture_sha256'] if name in ('用户条目','另外七个底子') else PIN
            identity=value.get('dat_sha256',PIN if name=='首次发布' else None)==expected
            ok=ok and identity and (count is None or len(cases)==count) and all(row.get('wait_status',0)==0 for row in cases)
            obligations.append(dict(group=name,unit=unit,status='PASS' if ok else 'INCOMPLETE_OR_FAIL',
                cases=len(cases),triggered_cases=len(cases)-removed,removed_paths=removed,
                expected_cases=count,dat_sha256=value.get('dat_sha256'),expected_dat_sha256=expected,
                file=str(path.relative_to(ROOT))))
    for unit in UNITS:
        path=OUT/'local'/('official-half-'+unit+'-with-hooks.json')
        value=json.loads(path.read_text()) if path.exists() else {}
        ok=value.get('status','').startswith('PASS') and value.get('dat_sha256')==PIN
        obligations.append(dict(group='原生半按',unit=unit,status='PASS' if ok else 'INCOMPLETE_OR_FAIL',file=str(path.relative_to(ROOT))))
    return obligations

def root_hashes():
    paths=[]
    for folder in (TREE,ROOT/'firmware/package_v36_g126',OUT):
        paths.extend(p for p in folder.rglob('*') if p.is_file() and not p.is_symlink() and
                     p!=OUT/'SHA256SUMS' and p.name!='.DS_Store')
    text=''.join(file_sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(set(paths)))
    (OUT/'SHA256SUMS').write_text(text)
    for line in text.splitlines():
        digest,name=line.split('  ',1)
        assert file_sha(ROOT/name)==digest,name
    return len(set(paths))

def main():
    assert file_sha(DAT)==PIN and int.from_bytes(DAT.read_bytes()[28:32],'big')==126
    protected=load_json('inputs-before.json')
    changed=[];log_appends=[]
    for name,digest in protected.items():
        path=ROOT/name
        if path.is_file() and file_sha(path)==digest:
            continue
        if name=='research/review_g124/commands.jsonl' and path.is_file():
            raw=path.read_bytes();prefix=hashlib.sha256();offset=0;boundary=None
            for line in raw.splitlines(keepends=True):
                prefix.update(line);offset+=len(line)
                if prefix.hexdigest()==digest:
                    boundary=offset;break
            if boundary is not None:
                appended=[json.loads(line) for line in raw[boundary:].splitlines()]
                if all(isinstance(row,dict) and isinstance(row.get('argv'),list) for row in appended):
                    log_appends.append(dict(path=name,initial_sha256=digest,current_sha256=sha(raw),
                        initial_prefix_bytes=boundary,initial_prefix_preserved=True,appended_records=len(appended),
                        observation='Append-only records of the existing gen 124 review batch. This task does not rewrite the log.'))
                    continue
        changed.append(name)
    save('evidence/protected-inputs.json',dict(status='PASS_IMMUTABLE_INPUTS' if not changed else 'FAIL',
        checked=len(protected),unexpected_changes=changed,observed_baseline_log_appends=log_appends))
    provenance={}
    for path in sorted(OUT.glob('*.py')):
        source=ROOT/'research/review_g124'/path.name
        if source.exists():
            provenance[path.name]=dict(source=str(source.relative_to(ROOT)),source_sha256=file_sha(source),
                current_sha256=file_sha(path))
    save('evidence/replay-provenance.json',dict(scope='Current routed replay sources; final-DAT identities are recorded per case.',modules=provenance))
    fixed=ROOT/'firmware/package_v36_g120b/SD_ROOT'
    sd=DAT.parent
    assert len(list(sd.iterdir()))==30
    equal={p.name:p.read_bytes()==(fixed/p.name).read_bytes() for p in sd.iterdir() if p.name!='GXRCE.DAT'}
    assert len(equal)==29 and all(equal.values())
    assert (TREE/'candidate/local/full-r13/effective-rows.bin').read_bytes()==(ROOT/'firmware/engine_v46_ui/candidate/local/full-r13/effective-rows.bin').read_bytes()
    assert all(p.resolve().is_relative_to(ROOT/'firmware/package_v36_g126/local') for p in sd.iterdir())
    obligations=acceptance()
    special={name:load_json('evidence/'+name+'.json')['status'] for name in
             ('package','rebuild-124','rebuild-126','mac-cli-rejections','user-tool','compiled-tables','codegen-safety','native-edges','rpc-default-complete','rpc-users-complete')
             if (OUT/'evidence'/(name+'.json')).exists()}
    complete=len(special)==10 and all(s.startswith('PASS') for s in special.values()) and not changed and all(r['status']=='PASS' for r in obligations)
    cold=[]
    for unit in UNITS:
        records=sorted((OUT/'local/cold-reentry').glob('126-'+unit+'-*.json'))
        assert len(records)==4
        for path in records:
            value=json.loads(path.read_text())
            assert value['status']=='PASS' and value['dat_sha256']==PIN
            assert value['published_plan']['matches'] and value['exit_plan']['matches']
            assert value['preview_plans'] and value['preview_plans'][-1]['matches']
            assert not value['native_UI']['host_ui_writes'] and not value['native_UI']['getter_callback_present']
            stores=value.get('nested',{}).get('Image_mode_stores',[])
            native=[row for row in stores if 0x20000000<=int(row['pc'],16)<0x20400000]
            cold.append(dict(unit=unit,cut=value['cut'],action=value['action'],native_mode_stores=len(native),
                all_recorded_mode_stores=stores,
                published_mode=value['published_plan']['actual']['0x36e'],exit_mode=value['exit_plan']['actual']['0x36e'],
                preview_matches=True,file=str(path.relative_to(ROOT)),source_sha256=file_sha(path)))
    save('evidence/acceptance.json',dict(status='PASS' if complete else 'INCOMPLETE_OR_FAIL',dat_sha256=PIN,
        completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),obligations=obligations,special=special,
        cold_publication=cold,protected_input_changes=changed,observed_baseline_log_appends=log_appends,physical_acceptance=False))
    layout=load_json('evidence/codegen-safety.json')
    table=['| 套件 | 50mm | 28mm | MOUNT |','| --- | --- | --- | --- |']
    for group in GROUPS:
        cells=[]
        for unit in UNITS:
            row=next(r for r in obligations if r['group']==group and r['unit']==unit)
            if row['status']!='PASS':
                cell=row['status']
            elif row['cases']:
                cell=str(row['triggered_cases'])+' 例通过'+('，'+str(row['removed_paths'])+' 个旧路径已删除' if row['removed_paths'] else '')
            elif group=='用户条目':
                cell='25 条 FCC 通过'
            elif group=='另外七个底子':
                cell='7 条通过'
            elif group=='M32R 档位与窗口':
                value=json.loads((ROOT/row['file']).read_text())
                cell=str(value['level_cases'])+' 个档位 / '+str(value['window_cases'])+' 个窗口通过'
            else:
                cell='通过'
            cells.append(cell)
        table.append('| '+group+' | '+' | '.join(cells)+' |')
    rpc=load_json('evidence/rpc-default-complete.json') if (OUT/'evidence/rpc-default-complete.json').exists() else {}
    rpc_users=load_json('evidence/rpc-users-complete.json') if (OUT/'evidence/rpc-users-complete.json').exists() else {}
    verdict='可以交复审' if complete else '有缺陷'
    report=f'''{verdict}

gen 126 只增加列表发布后的原生设置核对及引擎仍拥有界面时的 H07 核对，并同步本代 generation 校验。最终 DAT 为 {DAT.stat().st_size:,} B，SHA256 `{PIN}`。交付目录为 `firmware/engine_v47_fix`、`firmware/package_v36_g126`、`research/g126_fix`。

## 修复

`list_bind_impl()` 在八行服务返回后调用 `eng_check_settings()`，不依赖 committed 或 recheck。H07 在确认前调用同一函数。永久锁定时仍走原有锁定路径，不恢复设置，不增加通信。

新函数复用 `settings_match()` 读取 settings 租约并逐字段比较原 `make_plan()` 的计划。没有成功应用记录时 current 初始化为纯 04；已有成功应用时采用当前已验证的配方及 RAM 档位，包含既有浏览预览，以保留原有浏览和确认规则。核对已确认配方时使用该配方计划。失败后的补偿目标仍由未修改的 `recover_confirmed()` 选取已确认配方或纯 04。

不一致时复用 `apply_impl()` 的 settings 服务及 preview 服务。`make_plan`、settings 服务、九行和 T 通信路径、RPC 类型、S 地址、锁定条件均保持原样。源差异见 [source-change-vs-g124.patch](source-change-vs-g124.patch)。本代的三个 C 校验只把 generation 124 改为 126；GXUI124 格式标识保持不变。当前三个单元的 24 条原配方记录均为原生 mode=1，实际计划包含 Image mode 与两条 WB；其他模式的专属字段分支由逐字未改的 make_plan 保留，本轮只核对源码和编译码，不列为本包真实数据的运行覆盖。

## 首次发布和退出

三个单元各四个 cold_reentry 切点全部绑定最终 DAT。七行窗口的原生方向键仍可写 `S+0x36e`；向下键短暂变成 5，向上键有同值写入。八行发布后及确认退出后均为 mode=1，WB 两字段符合纯 04，九行和 T 相符。预览服务入口观察到相同计划。这些记录证明最终状态恢复，不能描述成原生没有写入。

原始记录在 `local/cold-reentry/`，逐条哈希和切点结果在 [acceptance.json](evidence/acceptance.json)。参考代结果在 `local/cold-reentry-reference/`，分别保留 gen 124 与 gen 121 的首次发布状态。

设置补充案例分别改变 mode、WB 两字段以及组合，在纯 04 和确认配方 05 上走发布、OK、ADJ。正常服务案例要求最终完整计划、九行、T 和预览一致。服务失败情形单列，不计作成功恢复。

## 恢复失败边界

处理沿用原 settings 失败分支：已发生 W 且仍不确定时进入原确认配方补偿；没有 W 时清除本地 uncertainty 并返回原错误，不能据此触发永久 W 锁定。现有 finish/keep_view/release_view 处理失败。模拟 settings 失败后，错误设置可保留到撤回的原生七行视图；服务恢复后下一次打开再核对恢复。preview 服务失败时设置可已正确，但没有成功刷新证据，不能算预览一致。永久通信失败的部分 W 和 ERR 锁定仍是继承边界。

补充记录在 `local/settings-cases/`。它们分别记录正常恢复、模拟服务失败当次状态和下一次打开状态。最初补充测试把服务失败也要求立即成功，已更正为观察现有失败返回；固件未因此增加重试或改变锁定规则。

## 回归

{chr(10).join(table)}

已删除的 op 2 更新切点保持 `REMOVED_UPDATE_PATH`，不计作触发成功。原生半按的独立记录另列在 acceptance.json。用户条目的 25 条 FCC 与另外七个底子分别执行，元数据保持只读。`commands.jsonl` 保留实际退出码；超时或失败不算通过。

## 通信和编译码

通信由未修改的 `research/g122_keep_list/audit_records.py` 复核，不传哨兵参数。默认 DAT 去重完整流 {len(rpc.get('communication_logs',[]))} 条，用户变体 {len(rpc_users.get('communication_logs',[]))} 条。默认结果见 [rpc-default-complete.json](evidence/rpc-default-complete.json)，变体见 [rpc-users-complete.json](evidence/rpc-users-complete.json)。通信切点摘要和完整流分开识别，半字边缘 W 保留最近读回的邻字节。

七个改动 C 函数逐一闭合地址与长度、文件操作、原生界面写入、循环与内存四类检查。DAT 内引擎与 ELF 段逐字相同，PIC 平移检查通过；45 个 switch word 由汇编标签和最终链接值核对，未分类可执行异常为零。最大静态函数栈帧 {layout['maximum_static_frame']} B，引擎 {layout['engine_bytes']:,} B，BSS {layout['bss_bytes']:,} B。未测 RTOS 栈高水位。

结果见 [codegen-safety.json](evidence/codegen-safety.json)、[compiled-tables.json](evidence/compiled-tables.json)、[binary-inventory.json](evidence/binary-inventory.json)。编译差异中的 ig_init 为三个 generation 比较，ig_panel_open 和 rv_call 的同长度变化为随代码增加而平移的 switch 表基址；表目标仍由链接值核对。

## 保留限制及复现路径

P2-01 保留。最后一次归属核对到原生绘制之间仍有调度窗口，原生绘制会写全局 `0x205d4f64`。最终 DAT 在 50mm 的列表和面板各两个切点均重现旧行绘制及该全局写入，四例的迟到 S 写入为零。见 [p2-01-final.json](evidence/p2-01-final.json)。本修复不把这段描述成原子操作或只有像素写入。

P2-02 的正确原脚本路径是 `firmware/engine_v46_ui/candidate/reproduce124.py`。原目录及原说明保持只读；本目录 [REPRODUCE.md](REPRODUCE.md) 给出正确路径和输出只写新目录的包装命令。gen 124 与 gen 126 均已隔离重建，各自产出的 DAT、引擎、重定位和 48 槽位有效行分别与各自冻结候选逐字一致。48 槽位有效行在两代之间也逐字一致。

## 交付边界

`firmware/package_v36_g126/SD_ROOT` 指向包内的 `local/SD_ROOT`。实际 30 个文件均在该 local 目录，29 个固定文件与 gen 120b 逐字一致。根目录基准的 SHA256SUMS 包含三个交付目录的实际文件，不把符号链接重复计作文件。

冻结项 {len(protected):,} 个，非预期变化 {len(changed)} 个。另观察到原复审 `research/review_g124/commands.jsonl` 有 {sum(row['appended_records'] for row in log_appends)} 条追加，冻结前缀逐字保留；其余冻结项均未变。追加命令属于原 gen 124 复审批次，该日志保持原样。本轮源码、编译输入和包输入未发生漂移，详情见 [protected-inputs.json](evidence/protected-inputs.json)。

本任务最终新增只保留三个任务目录。过程有一次补丁路径误写，在许可目录外短暂生成一个无关文本文件和空目录，发现后立即删除。本轮初次构建未带本代 UI 扩展，已同步代际校验并重建；该中间结果没有计入最终验收。

本报告的通过范围是源码、主机编译、最终打包和 M32R 原生重放。没有访问相机、存储卡或网络，没有启动子代理。预览图形叶函数、设备及 RTOS 边界由模型承接，未验实体 LCD、曝光完成、实体断电或上卡行为。
'''
    (OUT/'REPORT.md').write_text(report)
    (ROOT/'firmware/package_v36_g126/DELIVERY.md').write_text(
        'gen 126 DAT-only candidate\n\nDAT SHA256 `'+PIN+'`。30 files in local/SD_ROOT; SD_ROOT is a local alias.\n'
        '29 fixed files match gen 120b. Host/native-model review only. See research/g126_fix/REPORT.md.\n')
    (TREE/'STATUS.txt').write_text(verdict+'\nGeneration 126 first-publication settings check.\n'
        'Authoritative DAT: firmware/package_v36_g126/SD_ROOT/GXRCE.DAT\nSHA256 '+PIN+'\n'
        'See research/g126_fix/REPORT.md. Older copied scripts and manifests are inherited references.\n')
    save('local/run-state.json',dict(task='g126-first-publish-fix-r1',status='COMPLETE' if complete else 'INCOMPLETE',
         dat_sha256=PIN,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sessions={}))
    count=root_hashes()
    print(verdict,'manifest files',count,'acceptance',complete,'unexpected input changes',len(changed),'baseline log appends',len(log_appends))
    assert complete, [row for row in obligations if row['status']!='PASS']

if __name__=='__main__':
    main()
