"""由最终产物和逐组回执生成中文报告，不把未完成组计为通过。"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    import sys
    sys.path.insert(0,str(HERE));from batch import jobs
    required=['fixed-builtin-c']+['accepted-'+name for name,_,_ in jobs()[1:]]
    required += ['extra-retire-live-50mm','extra-retire-live-mount','extra-builtin6-50mm','extra-builtin6-28mm','extra-t1-mount','extra-repeat','extra-release-ui']
    rows=[json.loads((HERE/'evidence'/('job-'+name+'.json')).read_text()) for name in required if (HERE/'evidence'/('job-'+name+'.json')).exists()]
    missing=sorted(set(required)-{r['name'] for r in rows});bad=[r['name'] for r in rows if r['status']!='PASS']
    audit=json.loads((HERE/'evidence/audit.json').read_text())
    clean=json.loads((HERE/'evidence/cleanup.json').read_text())
    assert audit['status']=='PASS' and clean['status']=='PASS'
    final={s:json.loads((ROOT/('firmware/package_v310_g155'+s+'/MANIFEST')).read_text()) for s in ('','_test')}
    for r in rows:
        assert r['dat_sha256']=={s:final[s]['dat_sha256'] for s in final},r['name']
    verdict='可以交复审' if not missing and not bad else '有缺陷'
    summary=dict(status='PASS' if verdict=='可以交复审' else 'INCOMPLETE',required=len(required),completed=len(rows),
        passed=sum(r['status']=='PASS' for r in rows),missing=missing,failed=bad,seconds=sum(r['seconds'] for r in rows),
        jobs=rows,dat_sha256={s:final[s]['dat_sha256'] for s in final})
    (HERE/'evidence/test-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    text=[verdict,'',
        'g155 在 v3.10 主机模型中自动恢复上次手动选择的完整配方，包括十个 Looks 和用户条目。发布 DAT 的 G155_BOOT=0，BOOT_RUN 返回 RV_PASS / RV_UNSUPPORTED，颜色零写；测试 DAT 的 G155_BOOT=1，包含与 g154 测试包相同的三个用户条目。没有生成机身安装映像，没有访问相机或存储卡，也没有 Git 写操作。',
        '',
        '这是 DAT 实现与主机验收交付。C07–C11、C14/C15、持键、连拍、自定时、原生等待上界及实际相机验收仍为 OPEN，发布版自动套用继续关闭。',
        '',
        '## 产物与尺寸','',
        '| 包 | 代码 B | DAT B | BSS B | 主请求 B | 距主请求上限 B |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for suffix,label in (('','release，BOOT off'),('_test','test，BOOT on')):
        m=final[suffix];text.append(f"| {label} | {m['code_bytes']:,} | {m['dat_bytes']:,} | {m['bss_bytes']:,} | {m['main_request']:,} | {m['main_headroom']:,} |")
    text += ['',
        '主请求按本轮 resident 的实际 7,628 B 父块开销计算：`7,628 + align4(DAT+BSS)`，上限 107,612 B。代码上限统一为 69,632 B，文件上限仍为 98,304 B，image+BSS 上限仍为 114,688 B。链接、PIC 平移、重定位和无未定义符号检查通过。',
        '',
        'resident 严格链接代码为 7,968 B；8,340 B 窗口扣除 root/pins 256 B 和原 24 B 保留后余 92 B。运行时代码相对 thin 只改 RV_MAX_CODE；build.py 指向本轮构建入口，README 说明模型用法。未改 hooks.c、loader.c、shared.c、resident.ld、ABI 结构或固定字布局。',
        '',
        'v3 放得下，没有退回 v1。GXFX 行容量从 `8/28/32/32` 改为 `0/16/12/12`，移除 3,932 B 空槽，实际使用仍为 `0/10/9/10`。十个 Looks、32 个用户格式槽位及本轮三个用户条目均保留；当前 K=10 时，可见用户上限仍为 30。与 g154 测试 DAT 的全部 63 份 552 B 输出逐字节相同，release 另核对 54 份。原始输出在 evidence/outputs，R3 的 7,904 B 和测试用户扩展的 1,984 B 也逐字节相同。',
        '',
        '相对 g154，测试版代码增加 3,816 B，DAT 减少 116 B，BSS 增加 16 B，主请求减少 100 B。只提交 g155 独立目录；完整文件差异见 [source.diff](evidence/source.diff)，路径与前后摘要见 [audit.json](evidence/audit.json)。BOOT 分别放在新增 boot_adapter.inc.c、eng_boot.inc.c；kv_data.c、kv_math.c 和 g154 导航算法保留，可按对应文件重放 g154 后续修复。',
        '',
        '两个包各只有 GXRCE.DAT 和 MANIFEST。模型从既有 8233a1c4 文件取得原厂代码，再把本轮 resident ELF 和替换字装入模型 RAM；没有创建 v3.10 ilaunch3 文件。',
        '',
        '| 产物 | SHA-256 |','| --- | --- |']
    for suffix,label in (('','release DAT'),('_test','test DAT')):text.append(f"| {label} | `{final[suffix]['dat_sha256']}` |")
    text += [f"| resident.bin | `{sha(HERE/'evidence/resident/neutral/resident.bin')}` |",'',
        f"resident build=`{final['']['resident_build_id']}`，ABI=`{final['']['resident_abi_id']}`。新 DAT 在 v3.9 8233a1c4 模型上、g154 在本轮 v3.10 resident 上均在 DAT 执行前拒收。",'',
        '## 40 B 记录与开关','',
        '| 字节 | GXR2 v3 |','| --- | --- |',
        '| 0..3 | GXR2。 |','| 4 | 3。 |','| 5 | 内置 1..8；Look 为 0x40+i；用户为 0x80+i，i 从 0 起。 |',
        '| 6..7 | 单元类型 0..2、完整标志 1。 |','| 8..27 | 十个大端 int16 控制值。 |',
        '| 28..35 | 本 DAT 头偏移 20 和 24 的两个 CRC32。 |','| 36..39 | 前 36 B 的大端 CRC32。 |','',
        '记录仍位于 S+0xFD4..0xFFB，通过原 op 4/5 读写，不写 S+0xFFC。手动完整应用并预览后才写；全零或格式、类型、完整标志和 CRC 合法的自有 v1/v3 尾部才允许替换。未知非零、未知版本和坏 CRC 尾部只读。BOOT 只接受当前 DAT、当前单元类型的合法 v3，不迁移 v1；更新后需手动选择一次。自动成功与补偿均不改意愿记录，不新增文件、强制保存或单元持久提交。',
        '',
        'adapter 向 engine 传完整的 1..32 用户索引；用户 1/2/3 实测分别写 0x80/0x81/0x82。恢复时按本 DAT 的实际可见条目和合法控制点重建引用与完整 552 B，不存地址、单元快照或唯一编号。',
        '',
        '唯一编译开关为 G155_BOOT，默认 0。构建器参数 --boot 0/1 直接设置该宏。release 不执行 BOOT 服务或设置 DIRTY/GUARD；test 在 H51 上执行。手动 v3 记忆在两种构建中均保留。',
        '',
        '## 事务与服务改动','',
        'PREPARE 先检查 MY=0、pending=0，再校验对象、记录、身份、控制点和精确纯 04 双读。0x205D9A7F 只记录到 ig_boot_raw_mode，不参与门控；0xFF 诊断值在 MY/pending 为零且起点合格时可以应用，这是后续裁定要求。MY1–3、非零及未知 MY/pending 均 detail=2、W/S/T 零写，不建立 DIRTY/GUARD；MY 首次 H01 也不建立自有基线。',
        '',
        'APPLY 保留完整 S 计划，即使差量为空，首 W 前仍执行 op 6 原厂锁检查。忙则零写退出。DAT 在首笔 W/S/T 前置固定 DIRTY；整行全写并逐字节读回，在 S 写和完整预览后核对全部拥有行、T 和 S。每个服务调用前后重验 lease、请求 epoch、MODE epoch、S 对象地址/长度/版本以及当前单元名字和版本；既有 fresh 检查继续生效。',
        '',
        'CANCEL 最多调用一轮完整纯 04 补偿，不进入菜单四次/两次恢复循环。只有完整读回目标或纯 04、释放令牌成功后才清 DIRTY。补偿失败、对象变化或会话退役时保留 DIRTY，resident 加 GUARD，H52 在 C01 取消快门；退役不清固定字。首次 H01 使用 BOOT 提交的引用、控制值和完整用户索引，只核对与建界面，不重新归一或应用。',
        '',
        '| 服务文件 | 本轮变化 |','| --- | --- |',
        '| engine_services/services.c | 新增真实 BOOT entry=51 的 nonce/entry_serial/inflight/ATTEMPTED/state=5 归属；允许原 S 与预览白名单在该归属内执行；BOOT 的 W/S 写须 DIRTY，BOOT 禁止 op 5 改意愿；自有记录校验接受 v1/v3。 |',
        '| engine_services/library.ld | 服务库链接上限 69,632 B。 |',
        '| candidate/service_build.py | 服务库尺寸报告与剩余代码预算改为 69,632 B。 |','',
        '没有新增服务号、扩大 S 字段或行/T 白名单，没有伪造菜单归属、隐藏列表或 BOOT state 56。服务变化纳入新 resident build 身份。BOOT 主调用栈帧的编译器记录为 268 B，deep 为 76 B；这些单帧数值不证明 task 6/IRQ 的完整栈峰值。','',
        '统一上限的读者和元数据如下。RV_MAX_LEASE=65,536 B 是另一项租约限制，保持原值；数学中的 65,536 常数也保持原值。','']
    text += ['- '+p+'。' for p in audit['cap_readers']]
    text += ['',
        'product/build.py 的初次链接把探测 BSS 起点放到 98,304 B，避免代码超过旧 64 KiB 时先和临时 BSS 重叠；正式链接仍使用真实 DAT 长度。',
        '',
        '## 主机测试','',
        f"正式要求 {len(required)} 个作业，已完成 {len(rows)} 个，PASS {sum(r['status']=='PASS' for r in rows)} 个，合计 {sum(r['seconds'] for r in rows):.1f} 秒。每组均有结束回执和最终 DAT 哈希。机器码测试使用 tools/native_harness_c 的 PythonBackend，GXR_HARNESS_BACKEND=c；552 B 对照使用主机编译 C。所有非 PASS 的初始结果均另以 Python 确认并保留，不计正式 PASS。",'',
        '| 作业 | 后端 | 秒 | 结果 |','| --- | --- | ---: | --- |']
    for r in rows:
        backend='主机 C' if 'equality' in r['name'] else 'C 指令' if r['backend']=='c' else 'Python'
        text.append(f"| [{r['name']}](evidence/job-{r['name']}.json) | {backend} | {r['seconds']:.1f} | {r['status']} |")
    if missing:text += ['',f"未完成：{', '.join(missing)}。"]
    if bad:text += ['',f"未通过：{', '.join(bad)}。"]
    text += ['',
        '矩阵覆盖三单元的内置/Look/用户菜单对照、S 尾部往返、首次 H01；S/T/实际行非纯 04、MY1–3、pending、未知非零值、坏记录 CRC、跨型号、跨 DAT、v1、非法控制点和未知尾部；首 W 锁忙；S 处迟到 BUSY；T=0 的目标补偿；行写中断的成功及失败补偿；lease/epoch/对象/单元变化；真实 rv_retire 在 DAT 调用期间执行及 H52；release 不支持；手动记录替换边界；两次后续 32→5 不再调用服务；g154 三单元平铺导航、50mm/MOUNT 跨退出和锁忙子集；新旧身份拒收。',
        '',
        '初始失败分为两类：旧观察脚本读取被 LTO 内联的 rv_load，以及冷 root 清零期间的中间字节值被误算为 DIRTY；两者 C/Python 结果相同，修正观察入口。另有实际 H01 重复预览，C/Python 均确认，已增加 BOOT 提交标志修复，并用最终 DAT 重跑。初始文件与日志保留在 evidence/job-initial-*、job-second-*、job-third-*，不覆盖为 PASS。','',
        '## 复审及现场未决项','',
        '静态上仍未排除“MY 启动但 MY 字节为 0”的路径。M02 只证明三条 MY 生产者写 1/2/3，不提供启动类别全集；本轮按裁定只认 MY/pending 与完整纯 04，不声称已经排除该路径。复审必须核对，机主可用现有 BOOT_CURRENT 探测包做一次 MY 档冷启动，拍 BOO 页确认 MY/pending 实际值。本轮未得到这份现场记录。',
        '',
        'C07–C11 的最早消费者、C14/C15、持全按开机、连拍首帧与后续帧、自定时冻结点，仍须最终机身复审和现场试验。H52 证据只覆盖 C01 原始键请求，不能扩大为全部首拍路径已保护。完整模拟器从 MAIN 自行冷启动到待机、实际 RTOS 交错、IRQ/任务栈、LCD、物理键、JPEG/DNG、真实断电和 NAND 都未运行。g154 继承的完整 keep=1 续接及直接 part1 重显/关闭观察仍为 OPEN，本轮没有据此放行发布。',
        '',
        '原厂设置锁只尝试一次且不等待。RPC 的原生等待参数 0x7A120 的单位、单次应答/取消和文件调用返回上界仍未独立证明；主机模型在这些边界直接返回，表中秒数不能替代相机最坏等待。BOOT 只限制目标一轮和补偿一轮，没有以平均时间关闭等待上界。官方 1.51 的最终恢复完成及更新后持久字节对照也须绑定后续机身映像另验。',
        '',
        '## 易错点清单','',
        '按 research/pitfalls/CHECKLIST_NEUTRAL.md 的 15 类逐项核对。','',
        '| # | 类别 | 本轮结果和边界 |','| --- | --- | --- |']
    pitfalls=[
        ('中断与残留进程','前台、有界、nice 10；无子代理；逐组回执，Scratch 清理见 cleanup.json。'),
        ('Studio 管线一致性','不适用。'),
        ('归属、重入与指针寿命','BOOT 独立归属；服务前后重验；lease/epoch/对象/单元变化后停止写入。'),
        ('夹具与原厂代码','明确由 host 提供启动/S/模式输入；运行真实 setter、跳板、resident 和 DAT；没有把模型称为完整冷启动。'),
        ('原厂时机与隐藏分支','C01 已测；C07–C11、C14/C15、MY=0 残余路径保留 OPEN。'),
        ('布局、过期套件与结束回执','目标布局重测；以最终包和每组回执计数；旧 v1 断电预期不计入本轮。'),
        ('真实基线、未知值与相邻字节','纯 04 双读；全行写及逐字读回；未知尾部只读；沿用实时邻字节处理。'),
        ('原厂续接与八行窗口','BOOT 不发布列表；H01 发布八行且从已提交目标建立界面；g154 继承 OPEN 单列。'),
        ('文件语义与 FAT','无新增机内文件写入；包只有 DAT/MANIFEST；真实 FAT 未测。'),
        ('失败收尾与恢复','一次补偿；失败后 DIRTY/GUARD 不清、H52 拒绝；对象变化不写新对象。'),
        ('物理按键和显示','未运行，留给现场验收。'),
        ('返回值、锁和等待','首 W 前锁门不依赖 S 差量；忙、错误和释放结果均检查；原生等待上界 OPEN。'),
        ('断电后的状态','S 尾部往返与新实例恢复已测；v1 不迁移；真实保存和异常断电未测。'),
        ('三个单元','50mm/MOUNT 完整 BOOT 选择及失败组，28mm 选择子集；全部当前 552 B 输出对照。'),
        ('现场变量与官方文件','没有相机操作；绑定 final DAT、resident ELF/bin、ABI 和 build；官方恢复另验。')]
    text += [f'| {i} | {a} | {b} |' for i,(a,b) in enumerate(pitfalls,1)]
    text += ['',
        '## 重跑和收尾','',
        '先按任务要求核对 Workspace UUID/APFS/可写和磁盘余量，创建指定 TMPDIR。然后运行：','',
        '```sh',
        'TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1/ nice -n 10 /usr/bin/python3 -I -B research/g155/build_resident.py --variant neutral',
        'TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1/ nice -n 10 /usr/bin/python3 -I -B research/g155/build.py --boot 1',
        'TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1/ nice -n 10 /usr/bin/python3 -I -B research/g155/build.py --boot 0',
        'TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1/ nice -n 10 /usr/bin/python3 -I -B research/g155/batch.py --tag recheck',
        '```','',
        '额外 T=0、重复首次 5 和真实退役用例的完整命令在各 job-extra-* 回执 argv 中。run.py 拒绝覆盖同名结果，重跑请换名称。没有任何步骤构建机身安装映像。',
        '',
        f"冻结输入 {audit['inputs']} 项无变化。TMPDIR 已删除，清理 {clean['files']} 个文件，{clean['bytes']} B；本轮子进程均结束。SHA256SUMS 绑定本轮源文件、两个最终 DAT、MANIFEST、报告及证据，校验方式为在项目根目录运行 `/usr/bin/shasum -a 256 -c research/g155/SHA256SUMS`。",'']
    (HERE/'REPORT.md').write_text('\n'.join(text))
    print(json.dumps(dict(verdict=verdict,required=len(required),passed=summary['passed'],missing=missing,failed=bad),ensure_ascii=False))

if __name__=='__main__':main()
