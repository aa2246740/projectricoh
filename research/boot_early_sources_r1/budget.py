"""对固定原始记录进行算术计数，不运行相机模型。"""
import math


def fragments(size):
    return (size + 7) // 8


def memory(slots):
    return 64 + 24 * slots


def build():
    # 本表是计数参考，实际次数的上界仍取决于来源和消费者闭包。
    kinds = [
        dict(id='context', status='候选', name='完整上下文建立', bytes=84,
             fields='boot、来源序号、unit/link/S 代次、阶段、task、PSW、S 指针/长度、S+0/+4、S+0xA/+0xC/+0xE 三个 BE16、来源/MY 原字节、pending 原字节/有效性、锁 ID/count、链接值、信息就绪值、握手值、信息对象指针'),
        dict(id='boot',status='候选',name='P00 原始分支',bytes=16,
             fields='原始启动输入引用、分支值、初始化阶段、原厂去向；目录固定 PC 不另猜测'),
        dict(id='source_start',status='候选',name='来源开始',bytes=8,fields='原始 source/MY 值与调用身份'),
        dict(id='source_last',status='候选',name='最后参数写/复制',bytes=8,fields='实际目标/长度或字段值；每条分支分别定义'),
        dict(id='source_return',status='候选',name='来源本地返回',bytes=8,fields='原厂去向和原始结果；有状态语义才称 status'),
        dict(id='tail',status='静态已证',name='完整 40 B 尾部原值',bytes=40,fields='S+0xFD4..+0xFFB 的全部原始字节'),
        dict(id='unavailable',status='候选',name='尚未初始化/不可读标记',bytes=8,fields='缺项及原始原因；不伪造一份全零/FF 快照'),
        dict(id='unit',status='候选',name='单元局部状态变化',bytes=8,fields='原始 ready/握手/信息状态及原厂结果'),
        dict(id='state',status='候选',name='实际状态变化',bytes=16,fields='旧状态、新状态、原厂去向、事件身份；任务/锁等保留于完整上下文'),
        dict(id='request',status='候选',name='P03 请求进入',bytes=16,fields='原生请求身份、触发原值、调用来源、原厂去向'),
        dict(id='load',status='候选',name='H01/loader/LOADING/READY/返回',bytes=8,fields='事件原值和结果，每个实际发生的阶段单独记录'),
        dict(id='image',status='候选',name='H09/H40/H41/请求到 K 关联',bytes=16,fields='source、原生请求/K/lifetime/结果按阶段分别记录'),
        dict(id='save',status='候选',name='原厂保存阶段/结果',bytes=8,fields='开始、逻辑块返回、外层返回等实际点分别记录'),
        dict(id='seal',status='候选',name='封存',bytes=16,fields='实际终止原因、连续物理范围、阶段关联'),
    ]
    for row in kinds:
        row['physical_fragments'] = fragments(row['bytes'])
    by = {r['id']: r['physical_fragments'] for r in kinds}
    # 参考格式让三个阶段各用独立记录；此项不是最优编码下限。
    source = by['source_start'] + by['source_last'] + by['source_return'] + 2 * by['tail']
    # 初次 S 还未成为有效对象，前值缺项仍计一条，完成后保留全尾部。
    initial = 3 + by['unavailable'] + by['tail']
    # 显式、可复算的单次通行参考；不把它当真实最大次数。
    base = (by['context'] + by['boot'] + initial + source + 3 * by['unit'] +
            5 * by['state'] + 5 * by['load'] + by['seal'])
    photo = by['request'] + 6 * by['state'] + 4 * by['image']
    projection = []
    for name,extra,note in [
        ('普通 Body，首次 H01 后封存',0,'S 读取 1 次、type 14 有效接收 1 次、3 个单元局部状态、5 次启动状态变化、5 个装载阶段；只建立一组上下文。'),
        ('先半按再全按，首张先于 H01',photo,'另有 1 次请求、6 次题定拍摄状态变化、H09/H40/H41 与关联各 1 次。H09 的实际次数另行核对。'),
        ('直接全按，首张先于 H01',photo,'仅对原厂未额外产生 half 消息的条件参考；有额外事件必须加记。'),
        ('按住全按开机',photo,'借用普通单次通行参考；实际生产者/消息次数未定。'),
        ('连拍首帧后停下',photo,'只数首帧；额外帧、计时或重试须按真实事件加记。'),
        ('自定时首张',photo,'尚未计入未知数量的计时事件；这不是最大值。'),
        ('MY1，一次有效恢复',source,'另加 1 次有效 MY 动作；同值也计 13 槽。'),
        ('MY2，一次有效恢复',source,'同 MY1，槽索引为 1。'),
        ('MY3，一次有效恢复',source,'同 MY1，槽索引为 2。'),
        ('同值 MY，一次有效恢复',source,'保留完整 3 个阶段和前后尾部。'),
        ('一次来源动作并观察原厂保存',source+3*by['save'],'其他来源动作加 13，保存开始/逻辑块返回/外层返回加 3；这不证明物理 commit。'),
    ]:
        slots=base+extra
        projection.append(dict(scenario=name,status='候选',slots=slots,bytes=memory(slots),fits_32=slots<=32,
                               extra_fragments=extra,assumptions=note,
                               maximum='未定；额外上下文、迟到来源、重试、其他消费者和状态返回只会继续增加本参考计数。'))
    scenarios = [
        ('普通 Body / Camera Unit 启动','S_load=1；type14 完成 n14；清零/默认/迁移条件次数另计','启动实际变化=5（题定）；额外返回未定','S 本地返回 1；type14 返回 n14；保存返回未定'),
        ('先半按再全按','普通启动源 + half/full 消息次数未定','完整第一张题定变化=6；额外返回未定','参数/单元命令返回次数未定'),
        ('直接全按','普通启动源 + 是否先行 half 未定','第一张变化=6；额外返回未定','命令及取消返回未定'),
        ('按住全按开机','原始持键生产者和补发/取消次数未定','启动/拍摄额外状态未定','等待、拒绝和返回次数未定'),
        ('连拍首帧','至少 1 个首帧请求；来源与后续帧并发未定','首帧之后返回/下一帧状态未定','单元与逐帧返回未定'),
        ('自定时','开始、计时到期和取消生产者次数未定','计时及拍摄状态返回未定','计时/命令返回未定'),
        ('MY1','有效 MY 动作 m1≥1；无效槽回退另分支','动作前后返回 5 的次数未定','每次恢复有本地返回；持久保存未定'),
        ('MY2','有效 MY 动作 m2≥1；无效槽回退另分支','同 MY1','同 MY1'),
        ('MY3','有效 MY 动作 m3≥1；无效槽回退另分支','同 MY1','同 MY1'),
        ('同值 MY','同有效 MY；不能按数值合并动作','同 MY','同 MY'),
        ('Restore Defaults / 同值确认','完整生产者与分派尚未闭合','未定','本地完成和持久返回未定'),
        ('Setting1 选择及编辑','至少选择/字段编辑，完整生产者次数未定','预览/菜单返回次数未定','预览及保存返回未定'),
        ('Setting2 选择及编辑','至少选择/字段编辑，完整生产者次数未定','同 Setting1','同 Setting1'),
        ('Start Settings Readout 选 Body','S+8 UI 写者已知；确认、复制与保存次数未定','未定','未定'),
        ('Start Settings Readout 选 Camera Unit','同上；type14 来源包数未定','未定','未定'),
        ('单元重连','link 断/连 + type13/type14 的次数未定','额外初始化及返回未定','握手、来源和保存返回未定'),
        ('维护恢复','命令高字节 0x80/0x81/0x82 与其他入口；全集未定','未定','有局部返回，物理持久提交未定'),
        ('MYSETxx.IFO 文件恢复','本地导入 1 次；成功后还可能进入兼容性修正或字段默认值，次数未定','菜单/预览返回次数未定','导入返回 1；后处理与保存返回未定'),
        ('播放组合键启动','类别绑定与来源动作次数未定','不能套用普通启动的 5 次变化','未定'),
        ('升级启动/返回','分流候选已知；来源/版本恢复全集未定','未定','未定'),
        ('维护启动','类别与生产者全集未定','未定','未定'),
        ('复位恢复启动','MONITOR/MAIN 来源全集未定','未定','未定'),
        ('保留 RAM 启动','清 BSS 跳过分支已知；原厂对象旧值和重跑次数未定','未定','未定'),
    ]
    scenario_rows=[dict(scenario=n,status='未定',producers=p,state_returns=r,status_returns=t,
                        max_fragments='原生可变事件次数未定；单次分片参考见类型表。',
                        total_slots=None,needed_bytes=None,fits_32=None) for n,p,r,t in scenarios]
    witness = []
    for n in [1,2,3,4]:
        slots = source*n+2
        witness.append(dict(actions=n,status='候选',tail_fragments=10*n,
                            stage_fragments=3*n,boot_and_seal_minimum=2,
                            reference_subset_slots=slots,reference_subset_bytes=memory(slots),
                            scope='参考编码让每次 80 B 尾部、3 个阶段及 P00/封存各有独立记录；不是所有可行编码的最低槽数。'))
    tail_bounds=[dict(actions=n,status='静态已证',snapshots=2*n,raw_tail_bytes=80*n,
                      tail_slots_lower_bound=10*n,bytes_lower_bound=memory(10*n),
                      scope='仅计每次动作前后完整 40 B 原始尾部；未加入任何阶段、状态、身份、返回或封存事件。')
                 for n in [1,2,3,4]]
    return dict(status='未定',slot_bytes=24,raw_bytes_per_slot=8,header_bytes=64,
                target_slots=32,target_bytes=832,type_catalog=kinds,source_action_fragments=source,
                initial_s_reference_fragments=initial,base_reference_slots=base,
                photo_reference_slots=photo,scenarios=scenario_rows,projections=projection,witness=witness,
                tail_only_lower_bounds=tail_bounds,
                conclusion='32 槽不能覆盖允许四次来源动作的范围；仅八份完整尾部原值已需 40 槽/1024 B。完整场景的最大次数与所需总大小仍未定。',
                formula='固定槽位每条只有 8 B 原值；m 次来源动作前后尾部给出 N≥10m、字节≥64+24N 的下限。阶段各独立记录的参考格式为 13m+2，不把该格式当最优编码证明。',
                context_note='84 B 是不缩减字段的计数参考；不是最优编码证明。每次新上下文另加 11 槽，实际最大上下文数未定。',
                snapshot_note='P04 的 503 B 九行/T 及 S/完整 ID 当前快照属于 DIAG_BOOT 另列的 768 B DAT BSS。没有把它们重复塞进固定槽；P06 在 H01 前的历史尾部仍须保留原始分片。')
