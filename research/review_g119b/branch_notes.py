"""Give each omitted B outcome an exact C cut, invariant, or explicit open status."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save

notes={}
def note(function,gen,pc,direction,kind,reason,evidence):
    notes[(function,str(gen),pc,direction)]=dict(kind=kind,reason=reason,evidence=evidence)

for function,pc in (('finish','0x1054'),('ui_finish','0x1164'),('ig_panel_event','0x9088'),('ig_panel_open','0x8dd8')):
    note(function,119,pc,False,'C','新增失败锁定分支。B 的共同域保留未锁定状态；锁定行为由真实菜单错误路径和全部入口检查验证。',
         ['source.patch','native/persistent-50mm.json','native/latch-paths-50mm.json'])
for pc,directions in (('0x4100',(False,)),('0x4108',(False,True))):
    for direction in directions:
        note('write_word',119,pc,direction,'C','新增首次 W 前取消规则。条件读取 g.view_lost 和 g.uncertain；旧有 W、返回校验和饱和计数正文已差分覆盖。',
             ['source.patch','native/concurrent_menu-other_menu-50mm-at6-reopen-fn2.json','native/concurrent_menu-other_menu-50mm-at17-reopen-fn2.json'])
for pc,directions in (('0x5428',(False,)),('0x5430',(False,True))):
    for direction in directions:
        note('preview_cached',119,pc,direction,'C','新增未发生 W 时取消预览且不执行补偿的分支，读取新增 view_lost 状态。其余预览和恢复正文保留 B。',
             ['source.patch','native/concurrent_menu-other_menu-50mm-at6-reopen-fn2.json'])
for pc,directions in (('0x30cc',(False,)),('0x30e0',(False,True)),('0x31a8',(False,True)),
                      ('0x31b8',(False,True)),('0x31ca',(False,True)),('0x31d0',(False,True))):
    for direction in directions:
        note('core_call',119,pc,direction,'C','新增 RPC 返回后的归属和首次 W 前合并检查，属于 source.patch 中 core_call 的新增条件块。请求构造、返回头、token 和内存复制保留 B。',
             ['source.patch','native/concurrent_menu-other_menu-50mm-at6-reopen-fn2.json','native/coalescing-119-50mm-at1.json'])
for gen,pc in ((118,'0x4a4'),(119,'0x3124')):
    note('core_call',gen,pc,True,'UNREACHABLE','本分支要求服务返回 RV_OK 而 reply.status 非零。实际 rv_call 的 finish 将同一个 result 同时写入 reply.status 并返回；core_call 始终传非空、对齐的内部请求与 reply。',
         ['engine118.asm','engine119.asm','core_call-review-targeted.json'])
for gen,pc in ((118,'0x8980'),(119,'0x8eac')):
    note('ig_panel_open',gen,pc,True,'UNREACHABLE','进入 preview_cached 前 panel.open 已为零。预览函数不写私有 panel.open；n.active 和 resident inflight 拒绝嵌套 engine 写入。其它原生菜单不持有这个私有对象，所以返回后 panel.open 仍为零。',
         ['source.patch','ig_panel_open-review-targeted.json'])
for gen,zero_pc,range_pc in ((118,'0x5b0c','0x5b16'),(119,'0x53e0','0x53ea')):
    note('preview_cached',gen,zero_pc,True,'UNREACHABLE','此前已确认 slot 在 1..eng_visible_rows；冻结数据的可见行数为 8，因此转为 uint8_t 后不可能为零。',
         ['data-equality.json','preview_cached-review-targeted.json'])
    note('preview_cached',gen,range_pc,True,'UNREACHABLE','正常配方列表的 list.rows 与冻结数据的 eng_visible_rows 同为 8。锁定后的一行提示由 n.failed 的入口检查隔离，不会进入 preview_cached。',
         ['data-equality.json','preview_cached-review-targeted.json','native/latch-paths-50mm.json'])
for pc,directions in (('0x569c',(False,)),('0x56b4',(False,)),('0x56bc',(False,True))):
    for direction in directions:
        note('list_bind',119,pc,direction,'C','新增一行错误列表选择及 op3 归属检查。原配方文本生成、指针、服务和发布正文已差分；错误行与归属失败由原生路径单独验证。',
             ['source.patch','native/persistent-50mm.json','native/ui-cutpoint-redraw-50mm.json'])
for gen,pc in ((118,'0x4068'),(119,'0x5d28')):
    note('panel_render',gen,pc,True,'UNREACHABLE','rows() 先清零九字节文本行，再生成七字符文本；SaveFail 分支复制的第九字节为 NUL。扫描到 PN_COLUMNS=8 时文本仍必为 NUL，不能进入非零字符拒绝分支。',
         ['panel_render-results.json','panel_render-targeted.json','source.patch'])
for pc,directions in (('0x8448',(False,)),('0x8454',(False,True))):
    for direction in directions:
        note('ig_menu',119,pc,direction,'C','新增失败锁定时发布一行提示的入口片段。正常 H01 正文保留 B；发布成功由真实菜单验证，发布失败分支保留原 UI 收尾契约。',
             ['source.patch','native/persistent-50mm.json'])
for gen,pairs in ((118,(('0x8094',True),('0x809c',False))), (119,(('0x8518',True),('0x8520',False)))):
    for pc,direction in pairs:
        note('ig_menu',gen,pc,direction,'UNREACHABLE','本冻结程序的 install() 固定返回 RV_UNAVAILABLE，初始化的 install_status 也为该值；没有把它改为 RV_STALE 或 RV_UNCERTAIN 的正常写入路径。',
             ['engine118.asm','engine119.asm','source.patch'])
for gen,points in ((118,('0x82e4','0x8338','0x8344','0x8364','0x8378','0x83fc')),
                   (119,('0x8758','0x87ac','0x87b8','0x87d8','0x87ec','0x8870'))):
    reasons=[
        '前面已检查 eng_visible_rows 非零；该函数只读同一份私有冻结数据和 ready 状态，当前入口不修改它们，因此第二次不能变为零。',
        'preload 查找的 ID 为 1..6，冻结八项表的前六项正是 1..6，搜索不可能走到八项均不匹配。',
        '此前每个参数索引查找都检查 g.ready。入口内没有修改 ready 的动作，metadata 循环不能再遇到 ready=0。',
        'metadata 循环的 slot 在 1..8，冻结可见行数为 8，不能出现 slot=17。',
        '冻结配方的全部 48 条 records 均 occupied=1，metadata 不会读到 occupied=0。',
        '同一份已验证冻结 records 生成列表，全部 occupied=1，文本生成不会走空记录分支。',
    ]
    for pc,reason in zip(points,reasons):
        note('ig_menu',gen,pc,False if pc in ('0x8338','0x87ac') else True,'UNREACHABLE',reason,
             ['frozen-facts.json','data-equality.json','ig_menu-results.json'])
note('ig_event',119,'0x8b0c',False,'C','新增失败锁定时只消费或关闭事件的入口分支。H07 的其余接受和设置逻辑保留 B。',
     ['source.patch','native/latch-paths-50mm.json'])
for pc,directions in (('0x8950',(False,)),('0x8980',(False,)),('0x8a18',(True,)),('0x8a20',(True,)),
                      ('0x8a40',(True,)),('0x8a48',(True,)),('0x8a70',(False,)),('0x8a84',(False,True)),('0x8aa0',(True,))):
    for direction in directions:
        note('ig_apply',119,pc,direction,'C','新增失败锁定、归属检查、首次 W 前重新选择及安全收尾片段。保留入口、Fn2、原光标与 list_bind 失败处理由 B 和定向 240 例验证。',
             ['source.patch','ig_apply-review-targeted.json','native/concurrent_menu-other_menu-50mm-at6-reopen-fn2.json'])
for pc,directions in (('0xad18',(False,True)),('0xad2c',(False,True))):
    for direction in directions:
        note('rv_call',119,pc,direction,'C','UI_LIST 的 op3 在原 IRQ 临界区内新增归属检查。这两个条件及失败后恢复 IRQ 的跳转属于有意源码改动；其它 dispatcher 改码仍须独立闭合。',
             ['source.patch','native/ui-cutpoint-redraw-50mm.json'])

coverage=json.loads((OUT/'coverage-union.json').read_text())
file_cfg=json.loads((OUT/'file-gate-cfg.json').read_text()) if (OUT/'file-gate-cfg.json').exists() else None
rows=[];functions={}
for name,pair in coverage['functions'].items():
    local=[]
    for gen,record in pair['pair'].items():
        for item in record['uncovered']:
            key=(name,gen,item['pc'],item['taken'])
            disposition=notes.get(key,dict(kind='OPEN',reason='该具体机器分支尚无 A 翻译证明、B 结果或足够的不变式；不将其默认为不可达。',evidence=pair['evidence']))
            if name=='rv_call' and file_cfg:
                cfg=file_cfg['generations'][gen]
                forced={x['pc']:x['taken'] for x in cfg['forced_edges']}
                if item['pc'] in cfg['unreachable_pcs'] or (item['pc'] in forced and item['taken']!=forced[item['pc']]):
                    disposition=dict(kind='UNREACHABLE',reason='正常会话不含文件写能力。保守控制流图仅固定三个文件能力条件，其余条件两方向和所有 switch 目标均保留；此结果落在被能力门禁排除的路径。',
                                     evidence=['file-gate-cfg.json','final-no-write-cutpoints.json','machine-gates.json'])
            row=dict(function=name,generation=int(gen),**item,**disposition)
            rows.append(row);local.append(row)
    functions[name]=dict(open_outcomes=sum(r['kind']=='OPEN' for r in local),omitted_outcomes=len(local),
                         closed_local=not any(r['kind']=='OPEN' for r in local),evidence=pair['evidence'])
save('branch-dispositions.json',dict(functions=functions,outcomes=rows,open_outcomes=sum(r['kind']=='OPEN' for r in rows),
    scope='C identifies a precise intentional code region; it does not approve its product behavior. Observed outcomes remain separately recorded.'))
print('Branch disposition records',len(rows),'open',sum(r['kind']=='OPEN' for r in rows))
for name,row in functions.items():
    if row['open_outcomes']:print(name,row['open_outcomes'],'specific outcomes open')
