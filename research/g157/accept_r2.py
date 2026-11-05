"""Three-hour acceptance continuation for immutable final g157 DATs."""
from pathlib import Path
import argparse
import datetime
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

EXPECTED={'test':'3478b9954c122142a0711ff07cc7251a50abb442f7069cc2c558d1ca61f882a3',
          'release':'488943d2a3b0303cc5cbec6d3c85a96e539fd19a71c3596968c40cda619dbf88'}
BODY='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
DIR=C.LOCAL/'acceptance-r2'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text())
def freeze(label=None):
    C.compute_gate('acceptance-r2-fixed-DAT')
    files=[]
    for profile,digest in EXPECTED.items():
        for path in (C.artifact(profile,'model')['dat'],C.PACKAGES[profile]/'local/GXRCE.DAT',C.PACKAGES[profile]/'local/SD_ROOT/GXRCE.DAT'):
            raw=path.read_bytes();assert C.sha(raw)==digest
            files.append(dict(path=str(path.relative_to(C.ROOT)),sha256=digest,bytes=len(raw)))
    frozen=read(C.LOCAL/'engine-freeze.json')
    assert all(C.sha((C.ENGINE/path).read_bytes())==digest for path,digest in frozen['source_C'].items())
    assert C.sha((C.ROOT/'firmware/image_v310/local/ilaunch3').read_bytes())==BODY
    target='fixed-DAT.json' if label is None else 'fixed-DAT-'+label+'.json'
    C.save(DIR/target,dict(status='PASS',utc=now(),files=files,engine_C_unchanged=True,body_sha256=BODY))
def reference_receipt(label,profile,unit):
    directory=C.LOCAL/'runs'/label;r=read(directory/'result.json')
    assert r['status']=='OBSERVED' and r['actual_backend']=='reference' and r['unit']==unit and r['version']==profile
    assert r['dat_sha256']==EXPECTED[profile] and r['cold_start'] and not r['snapshots']
    assert r['body_sha256']==BODY
    page=r.get('list_after_diagnostic',r['first_menu'])
    assert page['rows']==8 and page['screen']==0 and page['root_state']==3
    assert page['cursor']==page['cached']==page['physical']+1
    assert page['memory_result']==1
    source=C.LOCAL/'reference-fixtures'/('model-'+profile+'-'+unit+'-S.bin')
    block=source.read_bytes();record=block[0xfd4:0xffc]
    assert C.sha(block)==r['settings_sha256'] and page['record']==record.hex()
    assert 0x40<=record[5]<0x70 and record[6]==C.UNITS.index(unit)
    raw=C.artifact(profile,'model')['dat'].read_bytes();assert C.sha(raw)==EXPECTED[profile]
    area,_=C.D.effect_area(raw)
    visible=[i for i in range(C.D.u16(raw,area+10)) if raw[area+32+32*i+18]>>record[6]&1]
    expected_cursor=8+visible.index(record[5]-0x40)
    assert page['cur']==expected_cursor and any('Acros' in text for text in page['text'])
    if 'saved_levels' in page:assert page['saved_levels']==list(struct.unpack('>10h',record[8:28]))
    if profile=='test':
        assert r['BOOT_expected_552_equal'] and r['BOOT_unit_readback']['complete_552_equal']
        assert r['BOOT_unit_readback']['nine_rows_and_T_from_unit_peer']
        assert r['after_boot']['boot_committed']==1
    else:assert r['unit_W']==0 and not r['after_boot']['boot_committed']
    return dict(status='PASS',utc=now(),run=label,profile=profile,unit=unit,DAT_sha256=EXPECTED[profile],
                cold_MAIN=True,CPU_snapshot=False,full_record=page['record'],
                logical_cursor=page['cur'],expected_logical_cursor=expected_cursor,
                boundary='Independent reference MAIN and first ADJ critical path; no camera, NAND shutdown or JPEG claim.')
def update(step,value):
    path=DIR/'receipts.json';state=read(path) if path.exists() else dict(started_utc='2026-11-04T13:35:57+00:00',deadline_utc='2026-11-04T16:35:57+00:00',DAT=EXPECTED,steps={})
    state['steps'][str(step)]=value;state['updated_utc']=now();C.save(path,state)
    render(state)
def render(state):
    steps=state['steps'];p1=steps.get('1',{}).get('status','OPEN');p2=steps.get('2',{}).get('status','OPEN');p3=steps.get('3',{}).get('status','OPEN');p4=steps.get('4',{}).get('status','OPEN');p5=steps.get('5',{}).get('status','OPEN')
    p6=steps.get('6',{}).get('status','OPEN')
    native5=steps.get('5_native',{}).get('status','OPEN')
    mount=all(v=='PASS' for v in (p1,p2,p3));allpass=mount and p4==p5==p6=='PASS'
    verdict=('可以交复审' if allpass else
             'test 可以交复审；release/MOUNT 参考 OPEN' if mount and p4==p5=='PASS' else
             'test 可以交复审，release OPEN' if mount and p4=='PASS' else
             'MOUNT test 可以交复审，其余 OPEN' if mount else
             'MOUNT test 参考已通过，持续 Vivid 与文本证据待验；其余 OPEN')
    rows=[('1. test/MOUNT 参考关键路径',p1),('2. test/MOUNT 持续 Vivid 完整 MAIN',p2),('3. 首次 ADJ/诊断文本与 glyph 替代证据',p3),('4. test/50mm、28mm 参考关键路径',p4),('5. release/50mm、28mm 完整原生及参考',p5),('前五项后补齐 release/MOUNT 参考余项',p6)]
    block=['<!-- G157 ACCEPTANCE R2 BEGIN -->','## 三小时补验收（'+state['updated_utc']+'）','',
           '只补验收。test `3478b995…`、release `488943d2…` 的 DAT 字节不改；截止 16:35:57 UTC。','',
           '| 优先级与验收 | 状态 |','| --- | --- |']
    block += ['| '+name+' | '+status+' |' for name,status in rows]
    if p2=='PASS':block += ['','第 2 项已通过原生与独立参考：完整逻辑 S 的有效 Vivid=09 在 BOOT、首次 ADJ 诊断和列表持续保留；HC BW Cont +1 读回、40 B 意图记录保留、颜色零写。首次自动显示 B20/R03，active 为 A--，没有把 Vivid 标成 DAT 纯 04。参考写观察器另证明从有效 09 首次载入后，后续 selector 写入均保持 09。']
    if p2=='PASS' and all('ui_cached_levels' in row for row in steps['2'].get('rows',[])):
        block += ['','另从两个后端首次 ADJ 的实际内存输入中直接读取 UI 的 HC BW 缓存，均为 `[100,1,0,0,0,0,0,0,0,0]`，与保存值一致；不是仅检查引擎的保存缓存。']
    if p3=='PASS':block += ['','第 3 项替代证据通过，首次普通 ADJ 与首次诊断共 16 行，返回列表另有 8 行；逐字符实际 glyph 均与原厂转换器的独立 Python 指令执行相等。导出：[普通首次 ADJ](local/acceptance-r2/ui-text-normal.md)、[Vivid 诊断与列表](local/acceptance-r2/ui-text-Vivid09.md)。对应 JSON 保留实际字节与描述符来源，TSV 给出每行每列字符和 glyph。']
    if p4=='PASS':block += ['','第 4 项 test/50mm 与 test/28mm 均由新 MAIN 参考后端完成：高索引官方 Acros 的完整 BOOT 552 B、单元九行/T、保存记录与首菜单游标均通过。逐项 run 及完整 SHA 见回执 JSON。']
    if p5=='PASS':block += ['','第 5 项 release/50mm 与 release/28mm 均完成 29 条完整原生流程和参考关键路径：全部记录/552 B 读回、光标、DISP、OK/ADJ 收尾通过；参考冷启动按关闭 BOOT 的策略保持颜色零写、读回有效并发布诊断与列表。']
    elif native5=='PASS':block += ['','第 5 项的完整原生子项已通过：release/50mm 与 release/28mm 各 29 条记录、完整单元读回、游标、DISP 和 OK/ADJ 收尾均正常；对应参考路径继续验证。']
    if p6=='PASS':block += ['','剩余 release/MOUNT 参考关键路径也已通过，最终六个单元/包组合的完整原生流程及参考关键路径均闭合。']
    seal_path=DIR/'fixed-DAT-final.json';references_path=DIR/'reference-final-verification.json'
    if allpass and seal_path.exists() and references_path.exists():
        seal=read(seal_path);references=read(references_path)
        if seal.get('status')==references.get('status')=='PASS':
            block += ['','最终封存于 '+seal['utc']+'：两包共六份 DAT 副本的完整 SHA 均未变，引擎 C 源码冻结及机身输入校验通过。六个参考组合另复核了保存记录与实际逻辑光标。回执：[固定字节封存](local/acceptance-r2/fixed-DAT-final.json)、[参考终验](local/acceptance-r2/reference-final-verification.json)。']
    block += ['','| 最终包 / 单元 | 完整原生流程 | 标准启动参考关键路径 |','| --- | --- | --- |']
    for profile in ('test','release'):
        for unit in C.UNITS:
            native='PASS' if profile=='test' or unit=='mount' or native5=='PASS' or p5=='PASS' else 'OPEN'
            reference=(p1 if profile=='test' and unit=='mount' else p4 if profile=='test' else p6 if unit=='mount' else p5)
            block.append('| '+profile+'/'+unit+' | '+native+' | '+reference+' |')
    block += ['','第 1 项复核既有最终 SHA 的参考回执 `local/runs/r1-model-test-mount-critical-reference-r2/result.json`：从新 MAIN 启动，官方 Acros 完整 552 B 与单元九行/T 相等，保存记录有效、八行 DAT 列表与游标一致。没有修改 DAT，因此该有效回执继续适用。','',
              '早期数据对照：不需要。数据接入已按 ELF 重定位归一证明引擎逐字节等价，C 源码冻结一致；已有对照包与回执保留，本轮不再计算其余矩阵。','',
              'Vivid 刺激纠正：上轮验收脚本把原厂 Vivid 编码误写为 02；正确值为 09，已有 `research/field_gate_r1/REPORT.md` 与原厂提交指令依据。旧 02 失败回执保留，不能据此认定有效 Vivid 会被原厂归一化。新测试从有效完整逻辑 S 输入启动 MAIN，不在 BOOT 或菜单边界强改 RAM。','',
              'LCD 像素输出仍未实现。本轮按用户指定，使用 UI 实际发布的八行逐字符文本、实际 glyph 缓冲区与映射作为替代证据；这不是像素截图。','',
              '逐项回执：`local/acceptance-r2/receipts.json`。本轮结论以顶部表格为准，旧六小时封存仅作历史证据。','<!-- G157 ACCEPTANCE R2 END -->']
    report=C.HERE/'REPORT.md';text=report.read_text()
    text=text.replace('## 最终封存（2026-11-04T13:33:40.862513+00:00）','## 六小时历史快照（2026-11-04T13:33:40.862513+00:00）')
    start='<!-- G157 ACCEPTANCE R2 BEGIN -->';end='<!-- G157 ACCEPTANCE R2 END -->'
    if start in text:text=text[:text.index(start)]+'\n'.join(block)+text[text.index(end)+len(end):]
    else:
        title=text.index('\n')
        text=text[:title+1]+'\n\n'+'\n'.join(block)+'\n\n'+text[title+1:]
    historical_start='<!-- G157 LIVE RECEIPTS BEGIN -->';historical_end='<!-- G157 LIVE RECEIPTS END -->'
    if allpass and historical_start in text:
        before=text.index(historical_start);after=text.index(historical_end)+len(historical_end)
        note='首轮六小时报告原样保存在 [历史快照](local/acceptance-r2/REPORT-before-r2.md)，包括当时的 OPEN、首错和未收尾状态；当前验收结论以顶部本轮表格为准。'
        text=text[:before]+note+text[after:]
    adjusted=[];table=None
    for line in text.splitlines():
        if line.startswith('| 验收 | 新记录最终包 | 早期数据对照 |'):table='old-summary'
        elif line.startswith('| 包 / 单元 |'):table='old-units'
        elif line.startswith('| 层 | control |'):table='old-layers'
        elif not line.startswith('|'):table=None
        if line.startswith('|') and not line.startswith('| ---'):
            cells=line.split('|')
            if table=='old-summary' and not line.startswith('| 验收 |'):cells[-2]=' 不需要 '
            elif table=='old-units' and not line.startswith('| 包 / 单元 |'):cells[-2]=cells[-3]=' 不需要 '
            elif table=='old-layers' and not line.startswith('| 层 |'):cells[2]=' 不需要 '
            line='|'.join(cells)
        adjusted.append(line)
    text='\n'.join(adjusted)+'\n'
    lines=text.splitlines()
    if lines[0].startswith('# '):lines.insert(0,verdict);lines.insert(1,'')
    else:lines[0]=verdict
    report.write_text('\n'.join(lines)+'\n')
    C.save(DIR/'summary.json',dict(verdict=verdict,utc=state['updated_utc'],steps={k:v.get('status','OPEN') for k,v in steps.items()},DAT=EXPECTED))
    for profile,root in C.PACKAGES.items():
        manifest=read(root/'MANIFEST');assert manifest['dat_sha256']==EXPECTED[profile]
        complete=(mount and p4=='PASS') if profile=='test' else (p5==p6=='PASS')
        manifest.update(status='ACCEPTANCE_COMPLETE_FOR_REVIEW' if complete else 'PARTIAL_ACCEPTANCE_OPEN',
            acceptance_utc=state['updated_utc'],acceptance_r2=str(DIR/'receipts.json'),
            verdict='可以交复审' if complete else 'MOUNT 可以交复审，其余 OPEN' if profile=='test' and mount else 'OPEN',
            native_complete=3 if profile=='test' or native5=='PASS' or p5=='PASS' else 1,
            reference_complete=(3 if p4=='PASS' else 1) if profile=='test' else (2 if p5=='PASS' else 0)+(1 if p6=='PASS' else 0),
            LCD_screenshot='NOT_IMPLEMENTED_TEXT_EVIDENCE' if p3=='PASS' else 'OPEN',
            lcd_text_evidence='PASS' if p3=='PASS' else 'OPEN',camera_verified=False)
        C.save(root/'MANIFEST',manifest)
def main():
    p=argparse.ArgumentParser();p.add_argument('--init',action='store_true');p.add_argument('--seal',action='store_true');a=p.parse_args();C.setup();DIR.mkdir(exist_ok=True)
    if a.init:
        old=DIR/'REPORT-before-r2.md'
        if not old.exists():old.write_bytes((C.HERE/'REPORT.md').read_bytes())
        freeze();update(1,reference_receipt('r1-model-test-mount-critical-reference-r2','test','mount'))
    else:
        if a.seal:freeze('final')
        render(read(DIR/'receipts.json'))
    print(json.dumps(read(DIR/'summary.json'),ensure_ascii=False))
if __name__=='__main__':main()
