"""Generate the complete per-symbol review from checked evidence."""
from pathlib import Path
import collections,json,re,sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]


def get(n):return json.loads((OUT/n).read_text())
def write(n,v):(OUT/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def link(n,label=None):return '['+(label or n)+']('+n+')'


def main():
    rows=get('function-closure.json');changed=[x for x in rows if x['category']!='identity']
    assert len(changed)==95 and all(x['closed'] for x in changed)
    branches=get('branch-closure.json');assert all(x['closed'] for x in branches.values())
    integrity=get('input-integrity.json');assert integrity['unchanged'] and integrity['files']==2014
    support=get('support-results.json');support_by={x['function']:x for x in support}
    local={x['name']:x for x in get('translation-local.json')}
    spans=get('object-spans.json');graph=get('dependency-graph.json')
    assert not graph['unresolved']
    assert len(support)==70 and set(support_by)=={x['function'] for x in changed if x['category']=='A'}
    proofs=OUT/'proof-A';proofs.mkdir(exist_ok=True)
    for row in changed:
        if row['category']!='A':continue
        n=row['function']
        write('proof-A/'+n+'.json',dict(function=n,category='A',closed=True,
              local=local[n],relocation_targets=[x for x in spans if x['function']==n],
              dependencies=row['dependencies'],dependencies_closed=True,
              supporting_execution=support_by[n]))
    source_patch=ROOT/'firmware/engine_v38_ro/local/static/all-source-changes.patch'
    parts=re.split(r'(?=^--- gen116/)',source_patch.read_text(),flags=re.M)
    intentional=''.join(x for x in parts if any(x.startswith('--- gen116/'+name+'\n') for name in [
        'containers/product/adapter.c','containers/product/blackbox.c',
        'containers/product/src/firmware/engine/core/eng_core.c']))
    (OUT/'C-source-hunks.patch').write_text(intentional)
    file_family=[x['function'] for x in changed if x['category']=='C-file']
    write('source-closure.json',dict(functions=file_family,
          authority='本轮任务已明确排除 io_*、open_read、remember_load、remove_owned、verify 文件家族，并复用容器审查的有意源码改动裁决。',
          source_patch='C-source-hunks.patch',container_review='../review_g117_container/REVIEW.md',
          references=[64,71,72,96,98,106,110],closed=True))
    diagnostics=[]
    for f in sorted(OUT.glob('support-*-limitation.json')):
        n=f.name[len('support-'):-len('-limitation.json')]
        current=support_by.get(n)
        diagnostics.append(dict(file=f.name,function=n,
             classification='earlier inconsistent callee model, superseded by 1000 passing pairs' if current and current['pass_'] else 'current supporting harness limitation',
             current_pass=current['pass_'] if current else None))
    write('model-diagnostics.json',dict(support=diagnostics,
          semantic_probe=dict(initial='invariants.stderr: GXR2_PIN=10 because r1 gate_seed does not initialize stock_sha256 tags',
              correction='invariants.py fills exactly the four pin-tag bytes written by the real adapter trust_init',
              final='frozen-helper-execution.json: both final machine bodies pass all three units'),
          alias_probe=dict(initial='support.py initially kept primitives by spelling while stubbing equal-code aliases on the other side',
              correction='all aliases sharing the exact primitive machine bytes now get the same real execution boundary',
              final='binding, descriptor aliases and metadata aliases each pass 1000 pairs in support-results.json')))
    arows=[x for x in changed if x['category']=='A'];aset={x['function'] for x in arows}
    packets=[x for x in get('packet-modes.json') if x['function'] in aset]
    aspan=[x for x in spans if x['function'] in aset]
    passed=sum(x['pass_'] for x in support);limited=[x for x in support if not x['pass_']]
    text=[]
    text.extend(['可以接受。','',
      '本轮关闭 P1-CG01。95 个改码符号对应 88 个真实函数区间，全部按题定 A、B、C 关闭，未找到可达行为差异。分类为 70 个 A、10 个纯 B、5 个 C+B、10 个题定已审文件家族 C。同地址别名逐名列出。',
      '',
      '审查只覆盖 gen 116 与 gen 117 的冻结容器机器码。实际 v3.6 绑定包沿用题目已核实的相同 engine 事实。本轮未操作相机、卡或刷机，未启动子代理，所有新增文件均在本目录。Python 均使用 `/usr/bin/python3 -I -B`。',
      '',
      '1. 输入与证据边界','',
      '| 对象 | SHA-256 或身份 |','| --- | --- |',
      '| gen 116 DAT | `1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864` |',
      '| gen 117 DAT | `4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a` |',
      '| 实际绑定 DAT | `35ce20ac843764b9cdd452785683ebf99004c47b77ae90720c2e3dc716c31211` |',
      '| gen 117 engine | 45,948 B；`548715f68ec9731423d6e1e36290fbcc3372de844cc0861ff5cbb859ccbf64e5` |',
      '',
      '题目已核实的输入身份、r1 九项 B、容器有意改动裁决直接复用。本轮另冻结并复核 '+str(integrity['files'])+' 个输入文件，前后哈希全部相同，见 '+link('input-integrity.json')+'、'+link('input-before.json')+'、'+link('input-after.json')+'。文中 PC 使用 r1 冻结 ELF 地址。',
      '',
      '2. A 的翻译验证','',
      '两代各用 r1 原链接命令重放，增加 `-save-temps=obj -Wa,-L -Wl,--discard-none`，全部输出和临时文件留在本目录。新增的局部标签没有改变 engine 的任何字节，见 '+link('labels116/command.json')+'、'+link('labels117/command.json')+'。读取完整符号表时保留不同输入对象的同名 `.LC` 标签，避免 Python 字典按名称覆盖标签。',
      '',
      '这使匿名常量的边界来自真实汇编标签。每个匿名常量和只读对象都比较到下一个符号或 section 末尾，包含填充字节。BSS 对应对象的尺寸相同，初始字节全零。'+str(len(aspan))+' 个 A 类地址目标逐项通过。唯一的 `rv_api+16` 数据重定位是 `R_M32R_32_RELA` 函数指针，递归验证其目标都是已关闭的 `rv_call`；其余 156 个数据字节逐字节相同，没有把不同普通数据当作地址抹掉。证据为 '+link('object-spans.json')+' 和各函数 `proof-A` 文件。',
      '',
      '非 NOP 指令按执行顺序逐条比较操作码、寄存器和非地址立即数。只转换 ELF 明列的 GOTOFF、GOTPC 字段以及逐目标核对的分支位移。每个 GOTOFF_LO 都有独立目标证据，GOTPC 高低字段都重新计算到 image+0x100。每个真实代码字节都被解码核对，没有未解码空洞。',
      '',
      'A 类两代共核对 '+str(len(packets))+' 个双 16 位字的模式位，原始字节与 ELF 一致。所有并行 packet 都只含一条有效指令和 NOP，没有两条有效指令并行的情况；填充全部是 NOP。顺序 packet 保留有效指令的原顺序。直接分支及 call 返回位置逐一映射到相同的下一条有效指令。',
      '',
      '`rv_call` 的两个 switch 表分别有 14 和 13 项，108 B 表内容相同，27 个目标都落到对应有效指令。A 类栈调整和 push/pop 序列相同，保存寄存器集合相同。30 个同码符号也独立核对了内部控制流，另核对 23 个同码 native、IRQ 汇编入口。证据为 '+link('packet-modes.json')+'、'+link('switch-tables.json')+'、'+link('identity-leaves.json')+'。',
      '',
      '调用依赖按从叶节点到调用者的顺序关闭，间接调用按真实赋值连接到 `rv_call`、`core_call`、`grain_snapshot`、`address`、`pn_native_from_seed`。148 个符号节点都关闭，无未解析目标，本次没有非平凡递归分量。函数地址字段也纳入依赖，见 '+link('dependency-graph.json')+'、'+link('function-closure.json')+'。',
      '',
      '`path` 的 `names.0` 完整区间为 91/90 B，`ig_init` 的单位名称表完整区间为 25/24 B。差异在尾部填充，严格的 A 条件未通过，因此这两个函数改由 B 关闭，没有缩小比较范围来签 A。',
      '',
      '3. 新增 B 与五个混合函数','',
      '六项各执行 10,000 组随机输入加 64 组明确边界输入，共 60,384 对。比较返回值、恢复后的 r8–r15，以及按对象映射的全部公共字节写入历史。临时栈按内部帧处理，恢复寄存器和 sp 必须相同。五个混合函数的 C 部分只按下表投影，剩余编译改码执行冻结 M32R 正文，callee 的共同边界在 '+link('differential.py')+' 明列。',
      '',
      '| 函数 | 116 分支结果覆盖 | 117 分支结果覆盖 | 执行结果 |',
      '| --- | ---: | ---: | --- |'])
    for n in ('finish','ui_finish','ig_event','ig_init','ig_menu','path'):
        rr=get(n+'-results.json');co=rr['coverage']
        fmt=lambda g:str(co[g]['covered'])+'/'+str(co[g]['possible'])+'，'+format(100*co[g]['covered']/co[g]['possible'],'.2f')+'%'
        text.append('| `'+n+'` | '+fmt('116')+' | '+fmt('117')+' | '+link(n+'-results.json','10,000 + 64 组一致')+' |')
    text.extend(['',
      '上表是原始正文覆盖率。所有未覆盖结果在 '+link('branch-closure.json')+' 逐 PC 标明 C 片段或不可达理由，没有未解释项。旧版 `ig_event` 去掉两个 C 片段后，20 个剩余条件分支的 40 个结果全覆盖。`ig_menu` 剩下的四类未覆盖结果是 install 已固定返回 2、两次可见行数保持一致，以及冻结 record 全部 occupied=1。',
      '',
      '`ig_init` 的不可达结果来自私有加载租约、gate 的布局不变量、首次初始化状态、snapshot 成功条件，以及本次两份冻结容器的配方数据。这里的域是这两份不可变私有 image 和实际可变 resident/native 状态，未把任意改写过配方的其它 DAT 当作同一冻结程序。snapshot 异常版本、cmp_version 和未知名称的拒绝路径也已执行。',
      '',
      '固定数据证据包括七段连续和尺寸、三份 stock entry CRC、三个 map+stock pin、48 个 style 和 occupied 字节及 384 组 metadata，见 '+link('frozen-invariants.json')+'。两代最终机器码的 semantic 和 stock expansion 在三单元共六组实执行通过，CRC 使用精确 zlib 规格，其余语义和展开正文是真实 M32R，见 '+link('frozen-helper-execution.json')+'。',
      '',
      '| 混合函数 | C：批准的源码改动和机器切点 | 剩余编译改码的关闭方式 |',
      '| --- | --- | --- |',
      '| `finish` | `blackbox.c @@ -146,6 +146,7 @@` 令 `ig_bx_flush` 立即返回 0。原调用和控制分支随之删除。容器审查第 64、96、98 行说明黑盒缩减归属。 | B 运行原正文，共同 flush callee 设为无副作用返回 0，比较全部剩余 RAM 效果。栈帧 36→36 B。 |',
      '| `ui_finish` | 同一 `ig_bx_flush` hunk。只去掉文件 flush，收尾状态清零仍执行。 | B，错误收尾、workspace 失败和普通返回均覆盖，栈帧 24→24 B。 |',
      '| `ig_event` | `adapter.c @@ -344,25 +335,8 @@` 删除 GXTS 保存和失败回滚，留下 RAM draft commit。旧 ELF `0x69b8→0x6ba8` 只代入 `last_store=RV_OK` 后进入原 RAM commit。`@@ -301,6 +291,7 @@` 的 `remember_save` 直接返回，用第二个精确切点跳过旧文件片段。容器审查第 71、98 行已接受。 | B 从入口执行，剩余 draft→values、draft→committed、dirty/open/input、普通列表及收尾路径全部比较。原始 38/38 个新版分支结果全覆盖。栈帧 400→104 B，减少的是已删文件临时区，r8–r15 完整恢复。 |',
      '| `ig_init` | `adapter.c @@ -417,7 +391,7 @@` 与 `@@ -433,7 +407,7 @@` 的两条能力常量 `0xF0000→0xE0000`，对应去掉 CAP_FILE_WRITE。容器审查第 106、110 行已接受。 | B 只投影 reply.capabilities 中明确删除的 `0x10000` 位，其余返回和写入全部比较。机器流另核实只有这两个非地址立即数不同；只读表尾部填充按 B 处理。栈帧 164→164 B。 |',
      '| `ig_menu` | install 的 `@@ -154,6 +154,7 @@`、preload 的 `@@ -222,25 +223,13 @@`，以及 `eng_core.c @@ -328,13 +328,8 @@` 的冷启动 04 和旧 remembered cursor 删除。旧 install、cursor、remembered 覆盖点在 results 的 cutpoints 中逐项列出。metadata 首次默认值路径属于整段已审 preload 改动。容器审查第 72、98 行已接受。 | B 覆盖这些改动以外的 RAM 路径，包括隔离标记、安装尝试记账、workspace 新建与已有 lease、fresh/busy、行内容、已提交 cursor 和 list_bind 失败。栈帧 172→76 B，公共对象写入及 r8–r15 一致。 |',
      '',
      '上表源码 hunk 的原文保存在 '+link('C-source-hunks.patch')+'，完整原件仍在 '+link('../../firmware/engine_v38_ro/local/static/all-source-changes.patch')+'。容器裁决原件为 '+link('../review_g117_container/REVIEW.md')+'。切点没有改写机器码，只在模拟器边界投影已批准的 C 语义。',
      '',
      '4. 每个改码符号的关闭表','',
      '| 函数 | 类别 | 证据文件 | 结论 |','| --- | --- | --- | --- |'])
    prior={'es_range.constprop.0':'es_range_constprop_0-results.json','gate_validate.constprop.0':'gate-results.json',
           'gxr2_crc32':'crc-results.json','pn_address':'pn-results.json','pn_native_from_seed':'native-results.json',
           'ig_apply':'ig_apply-results.json','list_bind':'list_bind-results.json','eng_current':'eng_current-results.json','workspace_close':'workspace_close-results.json'}
    for r in changed:
        n=r['function'];c=r['category']
        if c=='A':
            evidence=link('proof-A/'+n+'.json',n+'.json')
            conclusion='已关闭；支持性 1,000 组一致。' if support_by[n]['pass_'] else '已关闭；支持性 fixture 限制见第 5 节。'
        elif c=='B-r1':
            c='B';evidence=link('../review_g117_codegen/'+prior[n],prior[n]);conclusion='已关闭；题定复用 r1，至少 10,000 组。'
        elif c=='C+B':
            evidence=link(n+'-results.json')+'；'+link('branch-closure.json','分支裁决')
            conclusion='已关闭；C 切分见第 3 节，B 为 10,000 + 64 组。'
        elif c=='B-r2':
            c='B';evidence=link(n+'-results.json');conclusion='已关闭；10,000 + 64 组，40/40 分支结果。'
        else:
            c='C';evidence=link('source-closure.json');conclusion='已关闭；题定已审文件家族。'
        text.append('| `'+n+'` | '+c+' | '+evidence+' | '+conclusion+' |')
    text.extend(['','5. 分级发现与支持性执行','',
      'P0：未发现可达行为差异。','',
      'P1-CG01：已关闭。没有具体函数遗留 A、B、C 无法关闭的证明缺口。','',
      'P2-S01：支持性 harness 仍有 '+str(len(limited))+' 项 fixture 限制。'+str(passed)+' 个 A 类函数各完成 1,000 组差分，全部一致。另 '+str(len(limited))+' 项在下面的共同边界发生相同 fault，未把这些域外模型失败计为产品反例或通过。题目明确此矩阵不构成证明前提，不阻断。完整 70 项状态见 '+link('support-results.json')+'。',
      '',
      '| A 类函数 | 未跑满的具体原因 |','| --- | --- |'])
    for r in limited:
        f=r['limitations'][0];details=list(dict.fromkeys(x['detail'] for x in f['stops']))
        text.append('| `'+r['function']+'` | 现有通用 fixture 未满足此入口的 resident 地址或 ABI 前提；两代都报 `'+ ' / '.join(details)+'`。已完成 '+str(r['completed'])+' 组。 |')
    text.extend(['',
      '支持性首轮的 helper stub 曾按名称区分，导致一边执行 primitive、另一边执行同机器码别名的替身。现已按机器码等价类统一，binding、descriptor、metadata 的最终各 1,000 组都一致。semantic 补验首次沿用 gate 专用 trust fixture，缺少 stock_sha256 的四字节 pin 标签，返回 GXR2_PIN；补入真实 trust_init 写入的字段后六组全部通过。初版输出及当前状态分类保留在 '+link('model-diagnostics.json')+'，没有把初版结果算作已验证产品行为。',
      '',
      '6. 复核入口与清单','',
      '以下命令只写本目录。重放使用受保护的 r1 输入和相同工具链，不需要相机、卡、网络或固件写入。',
      '',
      '```sh',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/relink_labels.py 116',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/relink_labels.py 117',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/translation.py',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/invariants.py',
      '# 对 finish、ui_finish、ig_event、ig_init、ig_menu、path 分别运行：',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/differential.py ig_event 10000',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/branches.py',
      '/usr/bin/python3 -I -B research/review_g117_codegen_r2/closure.py',
      '```','',
      '`SHA256SUMS` 覆盖本目录全部文件，按惯例不包含清单自身。最终校验命令为：','',
      '```sh','cd research/review_g117_codegen_r2','shasum -a 256 -c SHA256SUMS','```',''])
    (OUT/'REVIEW.md').write_text('\n'.join(text))
    print('report',len(changed),'rows; A support',passed,'/ 70; all mandatory obligations closed')


if __name__=='__main__':main()
