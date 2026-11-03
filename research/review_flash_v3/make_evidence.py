#!/usr/bin/env python3
"""Assemble address-linked byte evidence entirely inside ignored local/."""
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('review', HERE / 'review.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.preflight()
    resident = (r.LOCAL / 'disasm/resident.txt').read_text()
    product = (r.LOCAL / 'disasm/product.txt').read_text()
    probe = (r.LOCAL / 'disasm/probe-life.txt').read_text()
    def function(text, name):
        m = re.search(r'^([0-9a-f]+) <'+re.escape(name)+r'>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)',text,re.M|re.S)
        assert m, name
        return m[0]
    out = ['# v3 最终字节证据', '', '本附件和反汇编均为离线证据，不是实机执行记录。', '', '## identity', '',
           '```json', (r.LOCAL / 'identity.json').read_text().strip(), '```', '', '## irq', '']
    for name in ['rv_irq_save', 'rv_irq_restore', 'rv_reset']:
        out += ['```text', function(resident, name), '```', '']
    out += ['全部静态 save/restore 调用点：', '```json', (r.LOCAL / 'irq-call-sites.json').read_text().strip(), '```', '',
            '## f04-close', '', '最终 H07 observer 分支、返回桩、原生关闭路径和引擎 event：', '']
    for start, end in [(0x2005295c,0x200529a0),(0x20052ae8,0x20052b08)]:
        lines = [line for line in resident.splitlines() if (m:=re.match(r'^([0-9a-f]+):',line)) and start<=int(m[1],16)<end]
        out += ['```text', '\n'.join(lines), '```', '']
    out += ['```text', function(product, 'ig_event'), function(probe, 'pv_event'), '```', '',
            '原生调用点见 [H07 与行号上下文](h07-and-row-context.txt)。', '', '## f05-retire', '']
    for name in ['rv_check','rv_retire','rv_allocation','rv_session','rv_free_checked']:
        out += ['```text',function(resident,name),'```','']
    out += ['原厂分配/释放指令见 [heap-native.txt](heap-native.txt)。', '', '## f06-ui-lifetime', '',
            '```text',function(resident,'rv_ui_abort'),function(resident,'ui_at'),'```', '',
            '快照服务的最终字节见 [services.txt](disasm/services.txt) 的 ui_prepare、ui_seed 与 rv_service。', '',
            '## f07-row', '', '```text',function(product,'ig_apply'),'```', '',
            '原生 1 基光标的初始化、限制及显示见 [hook-focus.txt](hook-focus.txt) 与 [h07-and-row-context.txt](h07-and-row-context.txt)。', '',
            '## behaviour', '', '```text',(r.LOCAL/'host/behaviour.log').read_text().strip(),'```','',
            '## hooks','', '| H | 原 VA | 官方覆盖字 | 实际候选覆盖字 | 候选桩 | Stage2l 同位置字节 | Stage2l 类别及目标 |',
            '|---|---|---|---|---|---|---|']
    hooks=json.loads((r.LOCAL/'hooks.json').read_text())
    for h in hooks:
        if h['changed']:
            out.append('|H%02d|0x%08X|`%s`|`%s`|0x%08X|`%s`|%s 0x%08X|' %
                       (h['number'],h['va'],h['original'],h['candidate'],h['target'],h['stage2l'],h['stage2l_kind'],h['stage2l_target']))
    out += ['', '```text', '\n'.join(function(resident,'rv_hook_%02d'%h['number']) for h in hooks if h['changed']),
            function(resident,'rv_hook_shared'), '```', '', '全部原生上下文见 [hook-focus.txt](hook-focus.txt)。', '',
            '## tables', '', '以下十八处表与两个 8 B 覆盖区的内部字地址相距不足 32 KiB。自动上界均为候选，负扫描不排除任意 RAM 计算目标。', '']
    tables=json.loads((r.LOCAL/'relative-tables.json').read_text())
    inner=[h['va']+4 for h in hooks if h['changed'] and h['length']==8]
    relevant=[t for t in tables if any(abs(t['base']-a)<32768 for a in inner)]
    for t in relevant:
        out += ['### table-0x%08x'%t['jump'], '', '```text']
        out += ['%08x: %s %s'%(i['pc'],i['raw'],i['asm']) for i in t['context']]
        out += ['```', '', '候选数量：%s；扫描目标没有命中覆盖区内部。'%t['count_candidate'], '']
    out += ['## stack', '', '```json', (r.LOCAL/'stack-independent.json').read_text().split('"resident_frames"')[0].rstrip().rstrip(',')+'\n}', '```', '']
    for name in ['ig_apply','bind_gxts','gxts_load.part.0']:
        body=function(product,name).splitlines()
        out += ['```text','\n'.join(body[:26]),'...']
        out += [line for line in body[26:] if re.search(r'\bbl .*<(bind_gxts|gxts_load.part.0)>|(?:addi sp,#|add3 sp,sp,#)',line)]
        out += ['```','']
    (r.LOCAL/'EVIDENCE.md').write_text('\n'.join(out)+'\n')
    print('EVIDENCE_READY hooks=%d nearby_relative_tables=%d'%(sum(h['changed'] for h in hooks),len(relevant)))


if __name__=='__main__':
    main()
