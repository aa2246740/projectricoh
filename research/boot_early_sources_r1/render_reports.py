"""把冻结的静态目录、槽位算术及未定项写成中文报告。"""
from pathlib import Path
import collections
import hashlib
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_tools as s
import catalog
import budget

HERE = s.HERE


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(name, value):
    s.save(name, value)


def collect_evidence(rows):
    metas=[]
    for p in sorted((HERE/'evidence').glob('*.json')):
        m=json.loads(p.read_text())
        m['label']=p.stem
        metas.append(m)
    images={}
    def im(name):
        if name not in images:images[name]=s.Image(name)
        return images[name]
    def excerpt(pc, name):
        a=int(pc,16)
        options=[x for x in metas if x['source']==name and int(x['start'],16)<=a<int(x['end'],16)]
        if not options:return None
        m=min(options,key=lambda x:x['size'])
        lo=max(int(m['start'],16), (a&~3)-4)
        hi=min(int(m['end'],16), (a&~3)+12)
        code=[x for x in m['instructions'] if lo<=int(x['address'],16)<hi]
        raw=im(name).raw(lo,hi-lo)
        for x in code:assert im(name).raw(int(x['address'],16),len(bytes.fromhex(x['bytes'])))==bytes.fromhex(x['bytes'])
        eq=im(s.BODY).raw(lo,hi-lo)==raw if name==s.OFFICIAL else None
        return dict(point=pc,source=name,source_sha256=im(name).sha256,
                    address=hex(lo),file_offset=hex(im(name).offset(lo,hi-lo)),bytes=raw.hex(),
                    sha256=digest(raw),instructions=code,window='evidence/'+m['label']+'.json',
                    window_sha256=m['sha256'],window_binary='evidence/'+m['label']+'.bin',
                    disassembly_file='evidence/'+m['label']+'.asm.txt',body_equal=eq)
    calls=json.loads((HERE/'references/calls.json').read_text())
    for row in rows:
        points=list(row['points'])
        for field in ['last_copy','completion','save_commit']:
            v=row[field]
            if v and v['address'] not in points:points.append(v['address'])
        row['evidence']=[]
        for pc in points:
            for name in [row['image']]+row.get('extra_images',[]):
                ev=excerpt(pc,name)
                assert ev,(row['id'],pc,name)
                ev['kind']='数据' if pc in row.get('data_points',[]) else '机器码'
                row['evidence'].append(ev)
                if ev['body_equal'] is False:
                    variant=excerpt(pc,s.BODY)
                    assert variant,(row['id'],'body variant',pc)
                    row['evidence'].append(variant)
        targets={int(x,16) for x in points}
        found=[]
        for c in calls:
            if row['image'] not in (s.OFFICIAL,s.BODY):
                continue
            if int(c['target'],16) not in targets:continue
            pc=int(c['pc'],16);raw=bytes.fromhex(c['bytes'])
            assert im(s.OFFICIAL).raw(pc,len(raw))==raw
            found.append(dict(address=c['pc'],target=c['target'],bytes=c['bytes'],
                              disassembly=c['instruction'],args=c.get('args',{}),
                              source_sha256=im(s.OFFICIAL).sha256,
                              excerpt_sha256=digest(raw),
                              body_equal=im(s.BODY).raw(pc,len(raw))==raw,
                              target_resolution_status='候选',
                              note='机器码字节已核对；目标来自直线常量传播，调用链须结合逐点正文判读。'))
        row['indexed_callers']=found
        row['context_status']='未定' if not row['context'] or any(w in row['context'] for w in ['未定','尚未','预期','实际']) else row['status']
        row['entry_irq_status']='未定'
        row['entry_irq_note']='未取得逐次入口的原始 PSW；正文中的局部临界区指令不等于所有调用入口的 IRQ 恒定。'
    return rows


def scalar_boundary(v):
    return '未定：未找到可报告的整体边界。' if not v else v['status']+'：`'+v['address']+'`；'+v['scope']+'。'


def source_map(rows):
    counts=dict(collections.Counter(r['status'] for r in rows))
    identity=json.loads((HERE/'input_identity.json').read_text())
    coverage=[
        ('启动类别全集','未定','B01–B09','MAIN 原始分支/模式表已有字节证据；当前包未提供独立机身 MONITOR 文件；物理类别和复位恢复全集未闭合。'),
        ('MY1–MY3 / 同值 MY','静态已证','M01–M06','已定位选择、分派、最后 S 写和局部返回；整体消费/持久提交另为未定。'),
        ('Restore Defaults / 同值确认','候选','D01–D02','保留候选 UI 路径；不给完成点。'),
        ('Setting1 / Setting2','未定','E01–E04','选择及编辑写者已有证据；每条完整编辑的最后写、完成、保存仍缺。'),
        ('Body / Camera Unit 来源','静态已证','S04–S08、S13–S14','已定位机身复制/接收返回、发送协议等待及 50mm 反向来源；不等于整体来源完成。'),
        ('Start Settings Readout','候选','S10','两处 S+8 写者已找；菜单确认和来源动作的完整绑定未定。'),
        ('单元重连 / 整体初始化','未定','U01–U05','多个局部 ready 不能合并为一个猜测的整体完成点。'),
        ('维护恢复 / 其他生产者','未定','F01–F04','MYSET 文件导入的最后写/返回已证；其后处理、维护、间接和别名仍未形成穷尽闭包。'),
        ('首次 5','静态已证','T01–T02','执行时的第一笔 old≠new 且 new=5 才是 P02；保留所有后续返回。'),
        ('五种触发的全部首个消费者','未定','C01–C11、C14–C15','已证早于 H10 的读者及更早服务的局部写集合、晚于 builder 的 H09 和独立预览；全路径最早集合未闭合。'),
        ('H01 / loader / READY','静态已证','C12','READY 发布在成功 loader 返回之前，拒绝路径可能没有 LOADING。'),
        ('P03 到每张 K 的唯一关联','未定','C13','H09 也用于启动；不能用时间最近的 H09 猜第一张照片。'),
        ('厂商物理唯一 ID','候选','U06–U09','4 B T+0x2C→信息+0x200；原厂 LID 格式及固定默认值已证，唯一性未证。'),
        ('每类来源的持久 save commit','未定','W01–W03','锁内保存与逻辑块返回已证；物理持久边界未证。'),
    ]
    result=dict(schema='gxr-boot-early-static-sources-r1',language='zh-CN',
                status='未定',complete_static_catalog=False,
                conclusion='静态全集未闭合，不能据此直接定版 BOOT_EARLY；没有把候选地址作为整体完成点。',
                counts=counts,count_unit='SOURCE_MAP 唯一条目 ID；不按地址、机器码指令数或重复段落计数。',
                identity=identity,coverage=[dict(name=n,status=z,items=i,result=r) for n,z,i,r in coverage],
                items=rows,
                index_limits='完整线性反汇编已逐字节核对；索引只做直线常量传播。未解析间接调用、别名、跨分支常量和表分派不能由零结果排除。',
                execution='本轮没有执行固件、构建、设备、SD 卡、网络或 Git 写操作。')
    dump('source_map.json',result)
    out=['# BOOT_EARLY 原厂来源与消费者目录',
         '\n[未定] 静态全集尚未闭合，不能直接据此定版 BOOT_EARLY。已确认多个局部完成点和 H09/H10 的相对边界；整体来源完成、全部首个消费者、持久提交和物理唯一 ID 仍有缺口。',
         '\n[静态已证] 条目计数：'+ ' / '.join(f'{k} {counts.get(k,0)}' for k in ['静态已证','候选','未定'])+'。每个 ID 计一次，字节和地址不另算条目。',
         '\n[静态已证] 条目判定概括该条的主张；整体完成、持久提交及入口 IRQ 逐字段另判。一个局部返回已证，不会使同条的整体完成自动通过。',
         '\n[静态已证] 本报告与 [source_map.json](source_map.json) 同源；后者包含每个观察点的原始字节、逐行反汇编、文件偏移、完整 SHA-256 和已解析调用索引。所有区间为半开区间，CPU 为 M32R 大端。',
         '\n## 输入与层次',
         '\n[静态已证] 官方 ZIP SHA-256：`'+identity['archive_sha256']+'`。29 个成员均与本地官方副本逐字节一致，详见 [input_identity.json](input_identity.json)。',
         '\n[静态已证] v3.9 ilaunch3：`'+s.EXPECTED[s.BODY]+'`。原厂 ilaunch3：`'+s.EXPECTED[s.OFFICIAL]+'`。窗口内未改字节可直接对应；外部 hook 改写点另外封存 v3.9 字节，不能把原厂 prologue 当成 v3.9 的实际入口。',
         '\n[静态已证] 对照 v3.8 的逐字节差异见 [compare-package_v38_g152.json](compare-package_v38_g152.json)；固定 resident 窗口之外还有头校验和既有 hook 分支字节差异，清单见 [body_changes_outside_resident.json](references/body_changes_outside_resident.json)。本报告的原厂语义点逐点核对，不以笼统“窗口外相同”替代字节检查。',
         '\n[静态已证] 本轮只读本地输入并写本研究目录；没有执行目标固件、编译固件、接触卡/设备、联网或写 Git。原厂文件哈希通过只证明输入身份。',
         '\n[静态已证] 题定事实直接使用：启动 0→2→32→63→32→5；首张拍摄 5→12→15→16→21→32→5；1 tick=1 ms。本轮没有重测这些数值。',
         '\n[静态已证] [package_types.json](references/package_types.json) 保留全部官方头部、类型分派字节与字符串；当前包唯一 type 1 MONITOR 是 l06firm5，不能代替机身复位层。',
         '\n## 覆盖矩阵',
         '\n| 范围 | 判定 | 条目 | 已到达的边界 |\n| --- | --- | --- | --- |']
    out += [f'| {n} | {z} | {i} | {r} |' for n,z,i,r in coverage]
    out += ['\n## 局部完成、整体完成与保存',
            '\n[静态已证] 机器码可证明一次回调、复制函数或逻辑块服务已经返回。只有正文明确限定的这个范围可使用该地址。整体来源完成与持久 save commit 没有相应证明时保留空值，不从候选入口、pending 清零或最终参数相同推断。',
            '\n| 来源 | 最后参数写/复制 | 局部完成 | 整体完成 / 持久提交 |\n| --- | --- | --- | --- |',
            '| 机身 S 读取/回退 | 静态已证：S03 模板复制后仍写字段；块读不是最后写。 | 静态已证：S02 包装返回 `0x20067302`，模板函数 `0x20067230`。 | 未定：其他迟到来源和持久提交未闭合。 |',
            '| S 头/校验清零、版本迁移 | 静态已证：S11 的 `0x20066DD4`；S12 的补齐复制 `0x20067040` 后还有版本写。 | 静态已证：`0x20066E20` / `0x20067070` 局部返回。 | 未定：后续 S 包装修正及原厂持久保存另计。 |',
            '| Body type 14 | 静态已证：条件分支 `0x20067896`。 | 静态已证：本次回调 `0x200679DE`。 | 未定：不是全部初始化/参数下发/保存的完成。 |',
            '| Camera Unit type 14 | 静态已证：当前机身分支 `0x20067938`。 | 静态已证：本次回调 `0x200679DE`。 | 未定：同上。 |',
            '| MY1/2/3、同值 MY | 静态已证：正常槽最后 S 写 `0x202645D0`；无效槽分开处理。 | 静态已证：复制函数 `0x202645E2`，后续还有模式处理。 | 未定：MY 后续消费与持久提交。 |',
            '| 退出 MY/影子恢复 | 静态已证：`0x20262EE4`。 | 静态已证：`0x20262EEE`。 | 未定：完整上层动作及随后保存。 |',
            '| Restore Defaults、同值确认 | 候选：D01；不报告最后写地址。 | 未定。 | 未定。 |',
            '| Setting1/Setting2 | 静态已证：原生列表两分支最后组写 `0x202BDF64` / `0x202BE070`；其他 modal 路径未闭合。 | 静态已证：原生列表 handler `0x202BE114`。 | 未定：完整编辑/预览/保存闭包。 |',
            '| Start Settings Readout | 静态已证：S+8 的两个直接写者；菜单分派仍为候选。 | 未定。 | 未定。 |',
            '| MYSETxx.IFO 导入 | 静态已证：`0x2011FE90`。 | 静态已证：导入函数 `0x2011FEAC`。 | 未定：外层 F04 仍可再次恢复参数，未证明保存。 |',
            '| 维护/文件恢复、重连 | 候选及未定：F01–F03、U04。 | 未定：局部维护命令返回另列。 | 未定。 |',
            '\n## 首个消费者与两个既有 hook',
            '\n| 触发 | 首个读/下发的判定 | H10 相对关系 | H09 相对关系 |\n| --- | --- | --- | --- |',
            '| 半按 | 候选：C02 的键解析读者及 C07 公共准备路径；最早集合未穷尽。 | 静态已证：C02 在前，原厂 half handler 在后。 | 静态已证：相关参数块先构造再进 H09；不能假定每次 half 都有一个照片 H09。 |',
            '| 直接全按 | 候选：C02+C08；物理是否同时产生先行 half 未定。 | 静态已证：键解析读在前，full handler 在后。 | 未定：本照片与某个 H09 的对应关系；builder→H09 的局部先后已证。 |',
            '| 按住全按开机 | 未定：持键生产者、事件补发/拒绝和首个读未闭合。 | 未定：可能进入 standby event 1 的后处理，不能把它当 full 消息。 | 未定：启动 H09 不能充当该照片的首次读边界。 |',
            '| 连拍首帧 | 未定：C10；另有 `0x20170A4C` 参数发送，不能仅查 H09。 | 静态已证：若走公共键解析，其读早于该次 H10；逐帧关联未定。 | 未定：不是统一逐帧边界；已证发送前有参数构造。 |',
            '| 自定时 | 未定：计时开始/到期与参数冻结的全路径未闭合。 | 未定：真正首个读的对应 H10；公共键解析的局部顺序见 C02。 | 未定：不能以 H09 或计时结束代替首个读。 |',
            '\n[静态已证] 初始化/预览单列：state 2 的 `0x202E3B10/20` 可先到 H09；state 32 的 `0x2029EB02` 经 builder 到 `0x201709CC`，完全不经过 H09。两者不计为用户按快门的首次消费者或第一张照片。',
            '\n[候选] C14 的原厂服务 82/83 还早于 C02 的设置读。其远端成像影响未闭合，不能把 C02 的 getter 单独定版为最早 P03，也不能把一般通信直接当作成像消费。',
            '\n## 逐点目录']
    for row in rows:
        out += [f"\n### {row['id']} · {row['title']}",f"\n[{row['status']}] {row['result']}",
                '\n| 项 | 内容 |\n| --- | --- |',
                f"| 覆盖点 | {row['status']}：{row['phase']}。 |",
                f"| 读取/含义 | {row['status'] if row['reads'] else '未定'}：{row['reads'] or '该项未另定义参数读取。'} |",
                f"| 写入/含义 | {row['status'] if row['writes'] else '未定'}：{row['writes'] or '未确认可归属于该动作的完整写集合。'} |",
                f"| 调用来源 | {row['status'] if row['callers_note'] else '未定'}：{row['callers_note'] or '已解析调用见 JSON；间接/更早调用闭包未定。'} |",
                f"| task / IRQ | {row['context_status']}：{row['context'] or '本项的完整任务/IRQ 现场未定。'} |",
                f"| 入口 IRQ 原值 | 未定：{row['entry_irq_note']} |",
                f"| 时基 | 静态已证：{row['time_base']} |",
                '| 最后复制/写 | '+scalar_boundary(row['last_copy'])+' |',
                '| 局部完成 | '+scalar_boundary(row['completion'])+' |',
                '| 持久 save commit | '+scalar_boundary(row['save_commit'])+' |',
                f"| 解释范围 | {row['status']}：{row['boundary']} |"]
        # 每个已列地址都有独立原始片段；重复点保持明确引用。
        for ev in row['evidence']:
            variant='；此片段与 v3.9 相同' if ev['body_equal'] is True else '；此片段与 v3.9 不同，另列 v3.9 片段' if ev['body_equal'] is False else ''
            data_note='此点为数据；下面工具反汇编不用于解释执行语义。' if ev.get('kind')=='数据' else ''
            out += [f"\n[静态已证] 点 `{ev['point']}`，文件 `{ev['source']}`，偏移 `{ev['file_offset']}`，片段 SHA-256 `{ev['sha256']}`{variant}。{data_note}完整窗口：[原始字节]({ev['window_binary']}) / [反汇编]({ev['disassembly_file']}) / [封存元数据]({ev['window']})。",
                    '\n```text']
            out += [f"{x['address']}  {bytes.fromhex(x['bytes']).hex(' '):<12}  {x['disassembly']}" for x in ev['instructions']]
            out += ['```']
    out += ['\n## 索引的覆盖限制',
            '\n[静态已证] [scan_summary.json](references/scan_summary.json) 记录逐字节检查的线性反汇编规模。分支之后清空传播状态，未知间接调用单独留下；[producer_inventory.json](references/producer_inventory.json) 分别列 S 来源、模式/WB、MY/pending、保存和 builder/H09 的解析集合。',
            '\n[候选] 直线索引可用于寻找调用者与字段写者，不能据其零命中证明没有其他生产者。表项调用、跨分支寄存器、索引地址、内存别名及程序版本迁移仍需逐项闭合。',
            '\n[静态已证] 启动分类原始通道、位设置点和模式表另见 [boot_flag_map.json](references/boot_flag_map.json)。来源包长度与尾部交集的算术见 [source_copy_ranges.json](references/source_copy_ranges.json)；它只计算已封存分支的字节范围，不执行固件。',
            '\n[未定] 因上述缺口，`complete_static_catalog=false`。这份目录可供继续静态定位和安排最小观察，尚不满足“来源事件为零即可证明没发生”的前提。']
    (HERE/'SOURCE_MAP.md').write_text('\n'.join(out)+'\n')
    return result


def slot_report(data):
    dump('slot_budget.json',data)
    out=['# BOOT_EARLY 物理槽位账',
         '\n[未定] 不能宣称 32 槽足够。允许首次 H01 前发生四次有效来源动作时，仅动作前后的完整尾部原值已需 40 槽、1024 B；其他原始事实仍须保留。完整场景最大值尚未定。',
         '\n[静态已证] DIAG_BOOT §3 的固定账是 `64 + 32×24 = 832 B`；每个物理槽的两个原始参数只容纳 8 B。连续序号按物理分片计；tick、类型号和上下文索引不能再当额外原值空间。',
         '\n## 固定槽位布局下的必需子集',
         '\n[静态已证] 每次有效来源动作须保留前后各 40 B 尾部；一份完整尾部需要 `ceil(40/8)=5` 个物理分片。仅这部分给出 `N≥10m`、内存 `≥64+24N` 的下限。四次动作的八份尾部为 320 B 原值，已占 40 槽；tick、类型和上下文索引不能代存这些字节。',
         '\n[静态已证] MY1→MY2→MY3→MY1 可在首次 ADJ/H01 前逐次完成；同值动作也保留各次原值。不能让尚未装载的 DAT BSS 代存历史尾部，也不能用首次/末次或相同字节的摘要删除中间快照。',
         '\n| 有效来源动作数 | 尾部快照数 | 尾部原值字节 | 仅尾部至少槽数 | 至少字节（含头） |\n| --- | --- | --- | --- | --- |']
    out += [f"| 静态已证：{r['actions']} | {r['snapshots']} | {r['raw_tail_bytes']} | {r['tail_slots_lower_bound']} | {r['bytes_lower_bound']} |" for r in data['tail_only_lower_bounds']]
    out += ['\n[候选] 如果开始、最后复制/写、局部返回各用独立记录，另给 P00/封存各一条，则参考子集为 `13m+2`。三次动作得到 41 槽/1048 B；四次为 54 槽/1360 B。这是指定编码的算术，不是允许阶段事实与快照分片共用记录时的通用下限。',
            '\n| 动作数 | 尾部分片 | 独立三阶段记录 | P00/封存参考 | 参考子集槽数 | 参考字节 |\n| --- | --- | --- | --- | --- | --- |']
    out += [f"| 候选：{r['actions']} | {r['tail_fragments']} | {r['stage_fragments']} | {r['boot_and_seal_minimum']} | {r['reference_subset_slots']} | {r['reference_subset_bytes']} |" for r in data['witness']]
    out += ['\n[未定] 如果产品将支持范围限制为某一明确动作序列，必须独立说明封存时机并重新数该序列；本研究没有通过缩减来源、合并同值动作或丢弃状态返回来使账落入 32 槽。未设动作次数上界时，m 可随用户继续切换而增长，没有一个静态有限容量能保证任意晚才打开 H01 的场景完整。',
            '\n## 单次事件分片参考',
            '\n[候选] 下表给不缩减字段的计数参考，便于后续实现者重算。它不是已经定版的格式，也不是最优压缩证明。84 B 上下文的 21 个字为：boot、来源序号、unit/link/S 代次、阶段、task、PSW、S 指针、S 长度、S+0、S+4、S+0xA/+0xC 的两个 BE16、S+0xE/来源/MY 的原宽字节、pending/有效性原宽字节、锁 ID、锁 count、链接原值、信息就绪原值、握手原值、信息对象指针。新上下文另需 11 槽。',
            '\n| 类型 | 原始字节 | 每次分片数 | 原值范围 |\n| --- | --- | --- | --- |']
    out += [f"| {r['status']}：{r['name']} | {r['bytes']} | {r['physical_fragments']} | {r['fields']} |" for r in data['type_catalog']]
    out += ['\n[静态已证] 完整 UID 不能截短。若必须保留某次历史身份的 `L` B ID，长度字 4 B 和全部字节另外至少 `ceil((4+L)/8)` 槽。当前仅有 4 B 字段候选，不能据它把未知 UID 长度锁死为 4。',
            '\n[静态已证] P04 当前九行 503 B、T 与校验使用合同另列的 512 B DAT 快照区；S/40 B 尾部/完整 ID 使用另列 128 B 区。不把这些当前快照重复计入固定槽；也不允许它们覆盖早期的历史快照。',
             '\n[未定] 768 B BSS 的完整布局及不同冻结集并存开销仍未链接核实。',
            '\n## 每个场景的原生次数上界',
            '\n[未定] 下表逐类保留未闭合的数量。空总数表示尚未获得上界，不是零槽，也不是 32 槽通过。初始化读取与照片读取分别计；所有迟到来源、状态返回、失败/取消及原生状态返回都要保留。',
            '\n| 场景 | 生产者次数 | 状态变化/返回 | 原生 status/返回事件 | 最大槽数 / 所需字节 |\n| --- | --- | --- | --- | --- |']
    out += [f"| 未定：{r['scenario']} | {r['producers']} | {r['state_returns']} | {r['status_returns']} | 未定 / 未定 |" for r in data['scenarios']]
    out += ['\n## 一次通行的可复算参考',
            '\n[候选] 下列参考继续采用阶段事实各占独立记录的格式。基数逐项为：上下文 11、P00 2、初次 S 9、一次有效 type 14 来源 13、三个单元局部状态 3、启动五次状态变化 10、H01/loader/LOADING/READY/返回五个事件 5、封存 2，共 '+str(data['base_reference_slots'])+' 槽。初次 S 的前值不可读时保留缺项 1 槽，之后 40 B 尾部 5 槽和三阶段 3 槽；这不表示缺项场景已经完整。清零、默认、迁移、发送协议和其他原生修正实际发生时另外保留事件。',
            '\n[候选] 首张参考增量为 P03 2、六次题定拍摄状态变化 12、H09/H40/H41/关联各 2，共 '+str(data['photo_reference_slots'])+' 槽。这只是算术通行参考，H09 的真实次数以及计时、重试、额外事件都没有被宣称为这个数量。',
            '\n| 条件参考场景 | 物理槽 | 总字节（含 64 B 头） | 条件 |\n| --- | --- | --- | --- |']
    out += [f"| 候选：{r['scenario']} | {r['slots']} | {r['bytes']} | {r['assumptions']} |" for r in data['projections']]
    out += ['\n[候选] 这些参考没有为每次上下文变化另增 11 槽，也未假装枚举完全部原厂路径。它们是指定参考序列的精确算术，不是实机计数、完整场景下限或最大值。全量最大值未定时，不能据这些数值选择一个最终内存大小。',
            '\n[未定] 固定区扩大到任何上述参考值都必须重新证明 RAM 归属与 G0；本研究没有改窗口、构建或批准观察机身。']
    (HERE/'SLOT_BUDGET.md').write_text('\n'.join(out)+'\n')


def open_report():
    items=[
        dict(id='O01',status='未定',name='普通首次快门与直接全按',minutes=3,
             step='拨盘放 P。开机后先不推 ADJ，半按后拍第一张；再推 ADJ，拍下 BOOT 冻结页。关机再开机，先不推 ADJ，快门一次按到底拍第一张，再拍 BOOT 页。',
             settles='比较 raw half/full、键解析、参数读取、H10、第一张 K 与 H01 的顺序；直接全按是否产生先行 half。',
             needs='能保留 C14 服务 82/83、C02/C07/C08 及 P03 原始事件的已验收只读观察机身；原 v3.9 的普通照片不能证明这些内部顺序。'),
        dict(id='O02',status='未定',name='按住全按开机',minutes=1,
             step='拨盘仍在 P。关机后按住快门到底，再开机；画面稳定后松开。记录是否已经拍到照片，再推 ADJ 拍 BOOT 页；如果没拍到，只补按一次快门并记下这一点。',
             settles='区分持键请求、等待松开、拒绝及补按；核对 0x205D9BAC 路径是否对应此触发。',
             needs='同 O01 的早期原始事件；不把补按得到的照片算成持键触发照片。'),
        dict(id='O03',status='未定',name='连拍首帧和自定时',minutes=2,
             step='用已经设好的原厂连拍模式，短按拍两张，停下后拍 BOOT 页。再用已经设好的 2 秒自定时拍一张，拍 BOOT 页。若这两项尚未设置，先跳过，本次不为补证据改设置。',
             settles='区分首帧、第二帧、计时开始和到期；查看首个参数读及请求到每张 K 的对应。',
             needs='每个场景单独冻结；需要记录计时事件、相关命令及逐帧身份。'),
        dict(id='O04',status='未定',name='MY 与同值 MY',minutes=3,
             step='只使用已经保存的 MY1、MY2、MY3：分别关机，把拨盘放到相应 MY 档，开机后先拍一张，再拍 BOOT 页。若某个现有 MY 的设置本来就与 P 下 Standard 相同，把它记为同值用例；没有就跳过同值项。',
             settles='MY 恢复与最后参数下发的实际顺序、是否重复进入来源、返回 5 的次数和槽位是否溢出。',
             needs='记录来源开始/最后写/返回及全尾部；不新建或覆盖 MY 槽。'),
        dict(id='O05',status='未定',name='来源菜单与默认值菜单的绑定',minutes=1,
             step='按 MENU/OK，拍当前 Image Settings 页及 Recall My Settings 的现有列表，退出。到 Setup 的 Start Settings Readout，拍当前 Body/Camera Unit 标记，按 DISP. 退出。到拍摄菜单 Restore Defaults，只打开确认画面拍一张，选取消退出。',
             settles='把菜单显示项与候选分派原值绑定，并记录当前来源；取消画面不能证明执行后的完成/保存。',
             needs='只读菜单事件记录；Restore Defaults 执行、同值复位和来源切换的完成/持久性仍另列未定。'),
        dict(id='O06',status='未定',name='4 B 编号候选的对应与重连',minutes=2,
             step='拍当前单元底部编号；拨盘放 P，拍一张普通照片和身份页。正常关机，取下再装回同一单元，开机再拍普通照片和身份页。有另一颗现成单元时，正常关机换上它，再各拍一张。',
             settles='比较完整 4 B 候选、标签、照片元数据及同一单元重连前后；核对对象更新。',
             needs='身份页仅纯读已验证信息对象中的候选字段；不同型号的差异不能证明同型号两颗的唯一性，厂商全局唯一语义仍需来源依据。'),
        dict(id='O07',status='未定',name='播放与加号组合启动',minutes=1,
             step='拨盘放 P，正常关机后只按播放键开机，拍一张画面。再正常关机，按住加号并按播放键，拍下出现的版本或启动画面；如果出现升级确认，选取消退出。',
             settles='把两个实际按法与原始分类器通道/标志和模式表分支对应；不执行升级。',
             needs='早期原始标志及类别分支；这些画面不能证明维护或复位恢复的所有路径。'),
    ]
    gaps=[
        dict(id='G01',status='未定',source_ids=['B04','B05','B06'],observations=['O07'],
             open='普通/播放/组合启动的物理绑定，以及维护/复位恢复类别全集。',
             scope='O07 只给实际按法与画面的对应；有早期原值后才能绑定通道/标志。当前官方包未提供独立机身 MONITOR 文件；普通照片不能补出未取得的复位层代码。'),
        dict(id='G02',status='未定',source_ids=['B07'],observations=['O01'],
             open='P00 时钟可用性与更早恢复动作的顺序。',
             scope='O01 的早期原始时间、返回值和有效性可检查这一次路径；现有 v3.9 开 ADJ 后的时间不能补开机时间，也不能证明所有复位路径。'),
        dict(id='G03',status='未定',source_ids=['S09','S10','U04'],observations=['O04','O05','O06'],
             open='来源交换、Start Settings Readout、单元重连的整体完成与迟到次数。',
             scope='O05 只关闭菜单/当前选项绑定；O04/O06 可给已有模式和重连的实际序列。来源切换执行后的全路径、反向消息与保存仍需静态闭包；本会话不改来源选项。'),
        dict(id='G04',status='未定',source_ids=['D01','D02'],observations=['O05'],
             open='Restore Defaults 的菜单绑定、执行/同值确认的最后写和完成。',
             scope='只打开确认页并取消，是最小只读菜单观察；它不关闭执行后的最后写和保存。没有不执行复位即可证明执行路径的普通相机步骤。'),
        dict(id='G05',status='未定',source_ids=['E04'],observations=['O05'],
             open='Setting1/Setting2 的全部 modal 确认/取消、预览及保存边界。',
             scope='当前 Image Settings 页能核对现有选项和菜单绑定；原生列表局部返回已另证。只看页面不能证明所有编辑分支，完整编辑链继续留作静态工作。'),
        dict(id='G06',status='未定',source_ids=['F03','F04'],observations=['O05'],
             open='MYSET 文件后处理、维护恢复与间接/别名生产者全集。',
             scope='现有 Recall My Settings 列表只帮助绑定 UI。文件导入和维护命令的最后写/保存不能靠未执行时的照片证明；不安排维护或导入操作。'),
        dict(id='G07',status='未定',source_ids=['C07','C08','C09','C10','C11','C13','C14'],observations=['O01','O02','O03'],
             open='五种触发的全部最早消费者，以及 P03 到首张 K 的唯一关系。',
             scope='三组快门步骤覆盖五种触发；须有相应早期原始记录。普通照片可证是否拍到，不能独自证明内部参数读取顺序；原厂服务的后续控制字消费者仍须静态闭合。'),
        dict(id='G08',status='未定',source_ids=['U07'],observations=['O06'],
             open='4 B 编号候选的厂商语义、同型号唯一性与对象更新。',
             scope='同一单元重连及已有另一颗单元，可检查稳定性/差异；厂商唯一性定义不能由一次有限观察证明，名字/版本和三种不同型号都不能代替。'),
        dict(id='G09',status='未定',source_ids=['W03'],observations=['O04','O06'],
             open='每类来源到原厂持久 save commit 的绑定。',
             scope='自然关机再开机只给这次可见持久结果；不能确定 NAND/FTL 提交点、全故障一致性或其他来源。没有纯读屏即可确定物理提交点的步骤。'),
        dict(id='G10',status='未定',source_ids=[],observations=['O01','O02','O03','O04','O05','O06','O07'],
             open='完整物理事件和上下文次数的最大值。',
             scope='这些步骤可数实际事件并识别缺项；一次实测次数不是全部路径上界。四动作的尾部下限已足以否定未限动作范围的 32 槽，不增加一次相机操作来重复证明算术。'),
        dict(id='G11',status='未定',source_ids=['*'],observations=['O01','O04','O06'],
             open='未闭合调用者的 task/IRQ 入口现场及跨 CPU 时间关系。',
             scope='只读记录逐次保存 task/PSW 和缺项；同一 CPU 的单位不自动给出跨 CPU 同步关系。UI task 6 及短临界区的局部静态事实仍按 SOURCE_MAP 单列。'),
    ]
    dump('open_items.json',dict(status='未定',items=items,gaps=gaps,
                                minutes=sum(x['minutes'] for x in items),
                                duration_kind='计划时长，未实测；需后续独立验收的只读观察能力。'))
    out=['# 尚未闭合的项目与最小只读观察',
         '\n[未定] 以下七项按一次约 13 分钟编排，时长尚未实测；复用第一张照片、已有模式和单元，不安排复位、升级、维护写入或设置重建。本任务没有操作相机。',
         '\n[静态已证] 现有 v3.9 在首次 ADJ/H01 后才装载引擎，不能靠这些屏幕照片追补 P00–P03。内部顺序项目只有在后续独立验收的 BOOT_EARLY 只读观察机身记录到相应原值时才可关闭；本轮未生成该机身，也不要求现在安装。',
         '\n[未定] 当前目录保留不能靠普通屏幕/照片单独解决的静态缺口：MONITOR 启动类别全集；Restore Defaults 和 Setting1/2 完整分派/最后写；单元整体初始化及维护/迁移别名；五种触发的全部最早消费者；原生时间在 P00 的有效性；各来源的持久 commit；完整事件最大次数；厂商 UID 的唯一性语义。',
         '\n[静态已证] 只读现场结果可以选定实际分支与事件次数，不能证明未走分支不存在、最大次数永远不会更大或逻辑块返回即已持久保存。上述静态缺口不转化为额外现场任务；未关闭前保持未定。']
    for x in items:
        out += [f"\n## {x['id']} · {x['name']}（约 {x['minutes']} 分钟）",
                f"\n[{x['status']}] 相机步骤：{x['step']}",
                f"\n[{x['status']}] 这组观察用于：{x['settles']}",
                f"\n[{x['status']}] 关闭条件与范围：{x['needs']}"]
    out += ['\n## 未定项与观察的对应范围',
            '\n[未定] 表中每项都保留能关闭的范围；没有普通只读相机步骤能关闭的部分直说，不把普通屏幕或一次成功照片当作内部边界证明。',
            '\n| 项 | 对应目录 | 尚缺内容 | 最小观察 | 能关闭的范围与限制 |\n| --- | --- | --- | --- | --- |']
    for g in gaps:
        out.append('| 未定：'+g['id']+' | '+('全部条目的入口现场' if g['source_ids']==['*'] else '、'.join(g['source_ids']) or '槽位账')+
                   ' | '+g['open']+' | '+ '、'.join(g['observations'])+' | '+g['scope']+' |')
    out += ['\n[未定] 需要执行 Restore Defaults、切换来源、升级/维护恢复或证明掉电保存的项目，不纳入这次只读短会话。取消画面只关闭 UI 绑定，普通关机后重开只检查该次可见结果；两者都不能替代完整的执行/持久边界。',
            '\n[静态已证] 所有新观察按场景独立冻结，录完每份结果的全部页，并明确是同一次还是下一次开机；开 ADJ 之后的当前快照不填回早期缺项。若某项现有模式或观察能力不具备，保留未定，不反复开 ADJ 求一个看似正常的值。']
    (HERE/'OPEN_ITEMS.md').write_text('\n'.join(out)+'\n')


def main():
    catalog.ROWS.clear()
    catalog.build_sources()
    dump('catalog_notes.json',catalog.ROWS)
    rows=collect_evidence(catalog.ROWS)
    result=source_map(rows)
    data=budget.build()
    slot_report(data)
    open_report()
    print(json.dumps(dict(source_counts=result['counts'],source_items=len(rows),
                          scenarios=len(data['scenarios']),reference_base=data['base_reference_slots'],
                          three_source_subset=data['witness'][2]),ensure_ascii=False))


if __name__=='__main__':main()
