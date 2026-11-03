"""Classify every retained outcome and retain individual closure evidence."""
from pathlib import Path
import collections
import csv
import json
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import SOURCE,OUT,save,record_inputs
from machine import Image,COND

LABELS={1:'RPC 地址和长度',2:'文件服务',3:'原生界面写入',4:'循环和内存范围',5:'计算和状态记账'}
FILE_NAMES={'rv_native_open','rv_native_read','rv_native_close','rv_native_write',
            'rv_native_create','rv_native_rename','rv_native_delete','sd_current.constprop.0',
            'es_storage_mark'}
UI_NAMES={'rv_native_ascii','rv_native_draw','rv_native_layer','es_ui_abort.constprop.0',
          'es_memcpy','es_ui_capture.constprop.0','ui_seed.constprop.0'}
MEM_NAMES={'rv_native_alloc','rv_native_free','ui_prepare.constprop.0'}


def call_name(row):
    m=re.search(r'<([^>]+)>',row['asm'])
    return m[1].split('+')[0] if m else ''


def walk(im,function,start):
    allowed={row['pc'] for row in im.function_rows(function)}
    seen=set()
    todo=[start]
    while todo:
        pc=todo.pop()
        if pc in seen or pc not in allowed:
            continue
        seen.add(pc)
        todo.extend(im.successors(pc))
    return seen


def rv_effects(im,pcs):
    effects={}
    for pc in sorted(pcs):
        row=im.rows[pc]
        if not row['asm'].startswith(('bl ','bra ')):
            continue
        name=call_name(row)
        category=(2 if name in FILE_NAMES else 1 if name=='rv_rpc8_native' else
                  4 if name in MEM_NAMES else 3 if name in UI_NAMES else None)
        if category is not None:
            effects.setdefault(category,dict(pc=hex(pc),asm=row['asm']))
    return effects


def main():
    images={g:Image(g) for g in (118,119,120)}
    current=json.loads((SOURCE/'codegen-open-outcomes.json').read_text())['outcomes']
    previous=json.loads((SOURCE/'previous_delta/rv-coverage-current.json').read_text())['outcomes']
    assert len(current)==578 and len(previous)==246
    checks={}
    for name in ('apply','file','core','owner'):
        d=json.loads((OUT/(name+'-check.json')).read_text())
        assert d['status']=='PASS' and not d.get('failures')
        checks[name]={int(g):set(map(tuple,e)) for g,e in d['edges'].items()}
    b_witness={}
    for name in ('apply','file','core','owner'):
        rows=json.loads((OUT/(name+'-cases.json')).read_text())
        for row in rows:
            assert row['ok']
            for gen,edges in row['edges'].items():
                for pc,taken in edges:
                    b_witness.setdefault((name,int(gen),pc,taken),row['index'])
    inventory=json.loads((OUT/'local_a/codegen-inventory.json').read_text())
    assert next(row for row in inventory if row['name']=='rv_call')['local_A']
    old_rv=images[119].function_rows('rv_call')
    new_rv=images[120].function_rows('rv_call')
    old_non_nop=[row for row in old_rv if row['asm']!='nop']
    new_non_nop=[row for row in new_rv if row['asm']!='nop']
    assert len(old_non_nop)==len(new_non_nop)
    rv_map={a['pc']:b['pc'] for a,b in zip(old_non_nop,new_non_nop)}
    rows=[]
    for delta,originals in (('119_120',current),('118_119',previous)):
        for index,item in enumerate(originals):
            gen=item['generation'];function=item.get('function','rv_call')
            pc=int(item['pc'],16);taken=item['taken'];im=images[gen]
            row=im.rows[pc]
            assert row['asm'].split(' ')[0] in COND
            assert im.owner(pc)==function
            start=im.target(row) if taken else pc+row['size']
            reachable=walk(im,function,start)
            category=5;reason='本方向只保留计算、拒绝返回或本产品的私有状态更新。'
            witness={};method='P2';status='P2';severity='P2';evidence=[item.get('evidence','previous_delta/rv-coverage-current.json')]
            if function=='rv_call':
                effects=rv_effects(im,reachable)
                category=next((k for k in (2,4,1,3) if k in effects),5)
                if category!=5:
                    witness=effects[category]
                    reason=f"从 {hex(start)} 的保守控制流可达 {witness['pc']} 的 {call_name(im.rows[int(witness['pc'],16)])}，归入{LABELS[category]}。"
                    if (pc,taken) in checks['file'][gen]:
                        method='B';status='CLOSED';severity=''
                        evidence=['file-check.json','file-cases.json#'+str(b_witness['file',gen,pc,taken])]
                    else:
                        method='OPEN';status='OPEN';severity='P1'
                        evidence+=['instructions/'+str(gen)+'-rv_call.txt']
                else:
                    reason=f"从 {hex(start)} 到返回没有可达的文件、RPC、原生界面或分配调用；保留的 dispatcher B 对覆盖该函数。"
                if (gen,pc,taken) in {(118,0x9150,False),(119,0x96ac,False)}:
                    category=2;method='UNREACHABLE';status='CLOSED';severity=''
                    reason='本方向要求 op=5 且文件 token 的 mode 非零；冻结能力没有文件写位，唯一的 token 建立路径只能得到 mode=0。'
                    evidence=['file-mode-proof.json']
                if (gen,pc,taken) in {(118,0xac44,False),(119,0xb20c,False)}:
                    category=4;method='UNREACHABLE';status='CLOSED';severity=''
                    reason='ASCII 检查循环到此分支时 i<source_bytes≤255，未采用方向要求 i=source_bytes；初始化、递增及回边守卫排除此条件。'
                    evidence=['ascii-loop-proof.json']
                if (gen,pc,taken) in {(118,0x93c4,True),(119,0x993c,True)}:
                    category=2;method='UNREACHABLE';status='CLOSED';severity=''
                    reason='本方向要求已保存 SD 身份全零；在 obj=1 的同一请求中，前面的成功 sd_current 已把非零身份复制到该字段，期间没有写回零值。'
                    evidence=['file-sd-proof.json']
                domain={(118,0xa610,True),(119,0xabbc,True),
                        (118,0x9984,True),(119,0x9ef4,True),
                        (118,0x9a6a,True),(119,0x9fe6,True)}
                if (gen,pc,taken) in domain:
                    method='UNREACHABLE_FINAL_DOMAIN';status='CLOSED';severity=''
                    reason='最终引擎的全部服务调用点已经列出；它不发出 UI-list op=4、service=13 或范围外服务号，本方向要求其中一种输入。'
                    evidence=['caller-domain.json']
                if (gen,pc,taken) in {(118,0x9f60,True),(119,0xa4f4,True)}:
                    category=4;method='B';status='CLOSED';severity=''
                    reason='该方向继续检查后续自有 lease；五组实际 dispatcher 对比覆盖第 1 至第 5 个匹配块，核对返回、寄存器和逐字节写入历史。'
                    evidence=['owner-check.json','owner-cases.json#'+str(b_witness['owner',gen,pc,taken])]
            elif function=='ig_init':
                category=1;method='A+C';status='CLOSED';severity=''
                reason='该方向属于地图准入或初始化控制流；594 条旧指令及其全部边均有对应，新增八条指令只建立 g.current。'
                evidence=['init-translation.json','local-a-check.json']
            elif function=='core_call':
                category=1
                reason='该方向位于 RPC 请求转发或回复检查；地址值写入请求 +40，RPC 数据长度为零，非零缓冲区上限为 80。'
                if (pc,taken) in checks['core'][gen]:
                    method='B+C';status='CLOSED';severity=''
                    evidence=['core-check.json','core-cases.json#'+str(b_witness['core',gen,pc,taken])]
                else:
                    method='UNREACHABLE';status='CLOSED';severity=''
                    reason='此方向要求 dispatcher 返回值与 reply.status 不同，或成功回复头不是 version=1、bytes=32；固定 API、独立回复块及最终 dispatcher 的统一返回排除此条件。'
                    evidence=['reply-invariant.json','instructions/'+('119-' if gen==119 else '')+'core_call.txt']
            elif function in ('ig_apply','a4_move'):
                header=(0x89bc if gen==119 else 0x8b54) if function=='ig_apply' else (0x6104 if gen==120 else None)
                child_loop=function=='ig_apply' and gen==120 and any(call_name(im.rows[p])=='a4_move' for p in reachable)
                if header in reachable or child_loop:
                    category=4;method='OPEN_NO_FIXED_BOUND';status='OPEN';severity='P1'
                    reason=f"本方向可继续到导航循环 {hex(header) if header in reachable else 'a4_move'}；输入持续变化时没有固定轮数上限。"
                    witness=dict(loop_header=hex(header) if header in reachable else 'a4_move')
                    evidence=['loop-cases.json','loop-proof.json','instructions/'+('119-' if gen==119 else '')+function+'.txt']
                else:
                    reason=f"从 {hex(start)} 直接收尾或返回，不再经过导航循环；其写入限于列表、面板及私有状态。"
            elif function in ('apply_impl','apply_impl.constprop.0'):
                calculation=(pc<(0x4a20 if gen==119 else 0x4bd8) or
                    (0x4b30<=pc<0x4b78 if gen==119 else 0x4cac<=pc<0x4d84))
                rpc_names={'rpc.lto_priv.0','expect','write_word','t_read','t_store'}
                calls=[p for p in sorted(reachable) if call_name(im.rows[p]) in rpc_names and im.rows[p]['asm'].startswith('bl ')]
                if calculation:
                    reason='该方向只选择颜色系数、WB 数值、固定设置项或拒绝状态；它不写地图指针、行地址、行长度或通信游标，固定数据范围与本函数 B 对见证据。'
                    evidence=['calculation-contract.json','../ux_preview_dot_r5/pairs/apply-body-results.json','apply-check.json']
                elif calls:
                    category=1;witness=dict(pc=hex(calls[0]),asm=im.rows[calls[0]]['asm'])
                    reason=f"从 {hex(start)} 可达 {witness['pc']} 的单元通信；地址取自准入后的 GXMP，行循环最多九行。"
                    if (pc,taken) in checks['apply'][gen]:
                        method='B';status='CLOSED';severity=''
                        evidence=['apply-check.json','apply-cases.json#'+str(b_witness['apply',gen,pc,taken]),'rpc-provenance.json']
                    else:
                        method='OPEN';status='OPEN';severity='P1'
                        evidence+=['rpc-provenance.json']
                else:
                    reason=f"从 {hex(start)} 不再到达 X/V/W；该方向处理参数计算、设置释放、状态发布或错误返回，函数已有 B 对。"
                if (gen,pc,taken) in {(119,0x4bec,True),(120,0x4da4,True)}:
                    category=5;method='P2';status='P2';severity='P2';witness={}
                    reason='该比较只处理 have/want 控制标志；到达时 changed 行掩码为零，比较不改地图指针、地址或长度，后续控制访问只取已验证 T 字段，函数已有 B 对。'
                    evidence=['rpc-provenance.json','apply-check.json','../ux_preview_dot_r5/pairs/apply-body-results.json']
            elif function=='ig_event' and gen==119:
                category=1;method='C';status='CLOSED';severity=''
                reason='旧 H07 的通信确认路径由本次有意改动替换为纯 RAM live 确认；最终 H07 调用图和 88 条保留记录验证零通信。'
                evidence=['contracts.json#H07_RAM','../ux_preview_dot_r5/h07-recipe-callgraph.json','../ux_preview_dot_r5/native/h07-all-50mm.json']
            elif function=='ig_panel_open':
                reason='该方向选择已核对的当前槽、参数或本产品面板；通信地址和行长度由 apply 的地图字段决定，面板只传槽号和微调值，已有面板 B 对。'
                evidence+=['calculation-contract.json','rpc-provenance.json']
            elif function=='ig_panel_event' and gen==120:
                if any(call_name(im.rows[p])=='a4_move' for p in reachable):
                    category=4;method='OPEN_NO_FIXED_BOUND';status='OPEN';severity='P1'
                    reason='该方向可调用 a4_move，后者的导航收尾循环没有固定轮数上限。'
                    evidence=['loop-cases.json','loop-proof.json']
            if category==5:
                if delta=='119_120':
                    evidence+=['../ux_preview_dot_r5/'+item['evidence']]
                else:
                    evidence+=['../ux_preview_dot_r5/previous_delta/service-completion.json',
                               '../ux_preview_dot_r5/previous_delta/service-fields.json']
            evidence=list(dict.fromkeys(e if e.startswith(('../','instructions/')) or (OUT/e.split('#')[0]).exists()
                else '../ux_preview_dot_r5/'+e for e in evidence))
            rows.append(dict(id=delta+'-'+str(index+1).zfill(3),delta=delta,generation=gen,
                function=function,pc=hex(pc),taken=taken,successor=hex(start),asm=row['asm'],
                final_pc=hex(rv_map[pc]) if function=='rv_call' and gen==119 else hex(pc) if gen==120 else '',
                category=category,category_name=LABELS[category],method=method,status=status,severity=severity,
                reason=reason,evidence=evidence,witness=witness,reachable_atoms=len(reachable)))
    assert len(rows)==824
    assert len({(r['delta'],r['generation'],r['function'],r['pc'],r['taken']) for r in rows})==824
    save('classification.json',dict(count=len(rows),outcomes=rows,
        policy='Each direction has one conservative primary class. Unknown branch conditions retain both successors after the selected edge. A call witness establishes a possible boundary, not its feasibility under every caller invariant. P2 is used only when the selected path has no such boundary, or contains only the product-owned fields exempted by the task.',
        switch_targets={g:{hex(pc):[hex(t) for t in ts] for pc,ts in im.switch_jumps.items()} for g,im in images.items()}))
    with (OUT/'classification.tsv').open('w') as stream:
        fields=['id','delta','generation','function','pc','taken','successor','final_pc','category',
                'category_name','method','status','severity','reason','evidence']
        writer=csv.DictWriter(stream,fieldnames=fields,delimiter='\t',extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row,evidence=';'.join(row['evidence'])))
    summary=[]
    for category in range(1,6):
        group=[r for r in rows if r['category']==category]
        summary.append(dict(category=category,name=LABELS[category],count=len(group),
            closed=sum(r['status']=='CLOSED' for r in group),
            P1=sum(r['severity']=='P1' for r in group),P2=sum(r['severity']=='P2' for r in group)))
    save('classification-summary.json',dict(total=len(rows),categories=summary,
        methods=dict(collections.Counter(r['method'] for r in rows)),
        functions=[dict(function=fn,count=len(group),P1=sum(r['severity']=='P1' for r in group),
            closed=sum(r['status']=='CLOSED' for r in group),P2=sum(r['severity']=='P2' for r in group))
            for fn in sorted({r['function'] for r in rows})
            for group in [[r for r in rows if r['function']==fn]]]))
    record_inputs('classification-inputs.json')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    main()
