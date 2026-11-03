"""Record machine-bound RPC, reply and navigation-loop obligations."""
from pathlib import Path
import collections
import json
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import ROOT,SOURCE,OUT,save,record_inputs
from machine import Image,COND


def named(row):
    m=re.search(r'<([^>]+)>',row['asm'])
    return m[1].split('+')[0] if m else ''


def dominators(im,function,forced):
    start=im.elf.functions[function]['address']
    allowed={row['pc'] for row in im.function_rows(function)}
    reached=set();todo=[start];pred=collections.defaultdict(set)
    while todo:
        pc=todo.pop()
        if pc not in allowed or pc in reached:
            continue
        reached.add(pc)
        row=im.rows[pc]
        nexts=im.successors(pc)
        if pc in forced:
            nexts=[im.target(row) if forced[pc] else pc+row['size']]
        for nxt in nexts:
            if nxt in allowed:
                pred[nxt].add(pc);todo.append(nxt)
    dom={pc:({pc} if pc==start else set(reached)) for pc in reached}
    changed=True
    while changed:
        changed=False
        for pc in sorted(reached):
            if pc==start:
                continue
            shared=set.intersection(*(dom[p] for p in pred[pc]))
            value=shared|{pc}
            if value!=dom[pc]:
                dom[pc]=value;changed=True
    return reached,dom


def main():
    im=Image(120)
    maps=json.loads((OUT/'maps.json').read_text())['units']
    expected={0x8470:'st r0,@(44,r10)',0x84e8:'stb r8,@(2524,r10)',
        0x84ec:'stb r8,@(2523,r10)',0x4f14:'ld r0,@(44,r6)',
        0x4f0c:'ldi r4,#12',0x4f20:'addi r4,#32',
        0x5114:'addi r4,#-9',0x5118:'bnez r4,4f08 <.L1052>',
        0x5068:'addi r6,#2',0x5070:'addi r5,#2',0x5074:'cmp r5,r11',
        0x5076:'bc 5034 <.L1038>',0x51a4:'addi r10,#2',
        0x4e80:'ld r0,@(44,fp)',0x4e84:'addi r0,#24',
        0x4344:'ld r4,@(44,r4)',0x4390:'ld r4,@(44,r8)',
        0x30e8:'ldi r4,#80',0x30ea:'cmpu r4,r5',
        0x30ec:'bc 3308 <.L714>',0x30f8:'st r4,@(40,r0)',
        0x311c:'st r5,@(52,r6)',0x317c:'jl r6',
        0x4230:'bl 3ebc <svc.constprop.0>',0x3f32:'jl r4',
        0xa738:'bl bbac <rv_rpc8_native>'}
    for pc,asm in expected.items():
        assert im.rows[pc]['asm']==asm,(hex(pc),im.rows[pc]['asm'],asm)
    emitters=[row for fn in im.elf.functions for row in im.function_rows(fn)
              if row['asm'].startswith(('bl ','bra ')) and named(row)=='rv_rpc8_native']
    assert [row['pc'] for row in emitters]==[0xa738]
    rpc_calls=[(fn,row) for fn in im.elf.functions for row in im.function_rows(fn)
               if row['asm'].startswith('bl ') and named(row)=='rpc.lto_priv.0'
               and im.target(row)==im.elf.functions['rpc.lto_priv.0']['address']]
    assert {(fn,row['pc']) for fn,row in rpc_calls}=={
        ('expect',0x4284),('t_read',0x43f4),('apply_impl.constprop.0',0x4de0),
        ('apply_impl.constprop.0',0x4ea8),('apply_impl.constprop.0',0x4fb0)}
    sites=[
        ('t_read',0x43b2,'X','BE16(M+28)','T 页；M=g.data.map。'),
        ('t_read',0x43f4,'V','BE16(M+30)','T 控制半字；前一个成功的 X 已选择 T 页。'),
        ('t_store',0x4332,'W','T cursor','调用者先执行成功的 t_read；写值只为 0 或 2。'),
        ('t_store',0x435c,'V','BE16(M+30)','T 写入后的读回。'),
        ('apply_impl.constprop.0',0x4e98,'X','BE32(M+24)>>16','B5 尾部相邻字节的所在页。'),
        ('apply_impl.constprop.0',0x4ea8,'V','BE32(M+24)&65535','M+24 经地图验证等于 B5.address+32。'),
        ('apply_impl.constprop.0',0x4f70,'X','BE32(M+32+12*j)>>16','j 从 0 到 8。'),
        ('apply_impl.constprop.0',0x4fb0,'V','BE32(M+32+12*j)&65534','从当前行起点向下对齐为半字。'),
        ('apply_impl.constprop.0',0x505c,'W','(row.address&~1)+2*k','k 受已验证的 row.length 限制；每次只写一个半字。'),
        ('apply_impl.constprop.0',0x5088,'X','row.address>>16','恢复读回前重新选择行页。'),
        ('apply_impl.constprop.0',0x50e8,'V','((row.address&~1)+2*k)&65535','恢复读回循环同样由 row.length 限制。'),
        ('apply_impl.constprop.0',0x5190,'X','((row.address&~1)+2*k)>>16','恢复读回跨页时更新页；50mm 的 B5 跨过页边界。'),
        ('write_word',0x42f8,'W','inherited cursor','该函数只转发数据值，不计算新地址；调用者仅为行写入和 t_store。')]
    for fn,pc,cmd,expr,reason in sites:
        assert im.owner(pc)==fn
        assert im.rows[pc]['asm'].startswith('bl ')
    rows=[]
    for unit in maps:
        for row in unit['rows']:
            assert row['words']<49
            rows.append(dict(unit=unit['unit'],row=row['label'],length=row['length'],
                address=hex(row['address']),words=row['words'],physical_bytes=2*row['words'],
                physical_begin=hex(row['word_begin']),physical_end=hex(row['word_end']),
                crosses_page=(row['word_begin']>>16)!=((row['word_end']-1)>>16),
                preserved_bytes=row['leading_preserved_bytes']+row['trailing_preserved_bytes']))
    save('rpc-provenance.json',dict(status='PROVED_WORD_INTERVAL_STRICT_ROW_INTERVAL_OPEN',
        pc_kind='ELF offsets before relocation; add the loaded image base for runtime PCs.',
        machine_assertions=[dict(pc=hex(pc),asm=asm) for pc,asm in expected.items()],
        call_sites=[dict(function=fn,pc=hex(pc),command=cmd,value_source=expr,reason=reason)
                    for fn,pc,cmd,expr,reason in sites],
        emitter=dict(pc='0xa738',service=4,operations={2:'V/21',3:'W/22',4:'X/23'},
            route=['svc.constprop.0@0x3f32','core_call@0x317c','rv_call@0xa738','rv_rpc8_native']),
        guards=[
            dict(pc='0x81e8',condition='gxr2_semantic_validate returns success before map assignment'),
            dict(pc='0x8448',condition='map plus stock-entry pin equals the connected module pin'),
            dict(pc='0x8470',condition='g.data.map=image+BE32(selected_directory+12)'),
            dict(pc='0x84e8/0x84ec',condition='bound and ready become one only after map assignment'),
            dict(pc='0x44ec/0x44f4',condition='apply rejects not-ready or unbound state before communication')],
        loops=dict(map_rows=9,stride=12,maximum_row_bytes=96,maximum_words_per_row=48,
            maximum_words_all_rows=sum(r['words'] for r in maps[0]['rows']),
            row_end='j increments by one and exits at nine at 0x5114/0x5118',
            word_end='i starts at -(address&1), increments by two and exits at i>=length',
            recovery_end='The readback loop uses the same start, length and increment.'),
        rows=rows,
        strict_gap='B5, B20 and B14 are 33-byte rows accessed as 17 halfwords. A row interval alone does not include the preserved adjacent byte. The maps and boundary flags are identical to gen117. The retained and directed records establish preserved values and word bounds; they do not establish a strict 33-byte physical access interval.',
        alias_scope='The address proof follows the initialized Engine fields and named caller contracts. It is not a complete proof of every store in every remaining dispatcher direction.'))
    replies=[]
    for generation in (119,120):
        q=Image(generation)
        atoms=q.function_rows('rv_call')
        guards=[row for row in atoms if row['asm'].split(' ')[0] in COND][:3]
        assert [row['asm'].split(' ')[0] for row in guards]==['beqz','beqz','bnez']
        reached,dom=dominators(q,'rv_call',{row['pc']:False for row in guards})
        returns=[row for row in atoms if row['asm']=='jmp lr' and row['pc'] in reached]
        assert len(returns)==1
        writes=[row for row in atoms if re.fullmatch(r'st r10,@\(4,\w+\)',row['asm'])]
        assert len(writes)==1 and writes[0]['pc'] in dom[returns[0]['pc']]
        heads=[row for row in atoms if re.fullmatch(r'ld24 \w+,10020(?: <.*>)?',row['asm'])]
        assert heads
        head=heads[0]
        head_store=next(row for row in atoms if row['pc']>head['pc'] and row['asm'].startswith('st '))
        assert head_store['pc'] in dom[returns[0]['pc']]
        replies.append(dict(generation=generation,entry_guards=[dict(pc=hex(row['pc']),taken=False,asm=row['asm']) for row in guards],
            header_store=dict(pc=hex(head_store['pc']),asm=head_store['asm']),
            status_store=dict(pc=hex(writes[0]['pc']),asm=writes[0]['asm']),
            return_pc=hex(returns[0]['pc']),reachable_atoms=len(reached)))
    save('reply-invariant.json',dict(status='PASS_UNDER_FROZEN_CALLER_CONTRACTS',generations=replies,
        invariant='The fixed dispatcher writes header 0x00010020 and reply.status on every return reached with valid aligned request/reply blocks. Its return value is that status.',
        caller_guards='ingress accepts only rv_services_init from the current session; that initializer returns the fixed rv_api. core_call uses its aligned static request and the named caller reply object; reply and scratch blocks are disjoint.',
        callee_contract='Native helpers may modify only their declared result buffers. The header/status proof uses that ordinary ABI memory contract.',
        closed_outcomes=[dict(generation=g,pc=pc,taken=True) for g,pc in [
            (119,'0x3124'),(119,'0x3130'),(120,'0x3194'),(120,'0x321c'),(120,'0x3228')]]))
    loops=[dict(function='ig_apply',header='0x8b54',back_edge='0x8bd6',
        condition='view is owned, no pending error, and native row remains in 1..8 but differs from the last slot',
        cycle=[5,7],bounded_domain=8,fixed_iteration_bound=None),
        dict(function='a4_move',header='0x6104',back_edge='0x6276',
        condition='panel/preview/current/parameter steps succeed, view is owned, and native row remains in 1..11 but differs from the last numeric row',
        cycle=[6,8],bounded_domain=11,fixed_iteration_bound=None)]
    for loop in loops:
        edge=int(loop['back_edge'],16);target=int(loop['header'],16)
        assert im.rows[edge]['asm'].startswith('bra ') and im.target(im.rows[edge])==target
    save('loop-proof.json',dict(status='NO_FIXED_ITERATION_BOUND',loops=loops,
        conclusion='The cursor domain is finite, but a repeated pair of valid rows can revisit the same loop header without a counter, deadline or decreasing budget. The loop body restores its temporary call frames before the back edge, so this finding is about iteration bounds, not growing stack usage.',
        runtime_evidence='loop-cases.json',
        source_evidence='firmware/engine_v42_ux/candidate/containers/product/adapter.c:417 and :500',
        physical_scope='No camera or RTOS session was executed. The retained native coalescing case demonstrates two same-page arrows during communication; continuous scheduling remains a model contract.'))
    save('contracts.json',dict(H07_RAM=dict(method='C',
        contract='H07 confirms verified live RAM state and closes the product panel/list without new unit RPC or file access.',
        machine_evidence='research/ux_preview_dot_r5/h07-recipe-callgraph.json',
        native_evidence=['research/ux_preview_dot_r5/native/h07-all-'+u+'.json' for u in ('50mm','28mm','mount')],
        excluded='The fixed native close continuation and functional acceptance are handled by the other review scope.'),
        FN2_VIEW=dict(method='C',contract='Fn2 numeric cursor values are not interpreted as recipe-list slots; only watch_view==1 performs that comparison.',evidence='core-C-cases.json')))
    record_inputs('boundary-inputs.json')
    print('PASS machine-bound boundary records; strict row access and loop obligations remain open')


if __name__=='__main__':
    main()
