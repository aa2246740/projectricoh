"""Write current-build reports and the body-only rebind identity after acceptance."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];R=HERE/'local/review'
def j(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 a=j(R/'acceptance.json');assert a['status']=='HOST_NATIVE_P0_FIXED_REBIND_PENDING'
 res=ROOT/'firmware/resident_v36';elf=res/'local/resident/build/resident.elf';body=HERE/'local/package/SD_ROOT/ilaunch3'
 trust=j(res/'local/resident/trust.json');structure=j(R/'structural.json');protected=j(R/'protected-after.json')
 size=j(res/'local/resident/size.json');assert size['payload_bytes']==7884 and size['margin']==200
 identity=dict(schema='ricoh-gxr-body-rebind/1',status=a['status'],body_firmware='1.51',resident_version='3.6',
  resident_build_id=trust['resident_build_id'],resident_abi_id=trust['resident_abi_id'],
  official_ilaunch3_sha256='da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
  ilaunch3_sha256=sha(body),ilaunch3_bytes=body.stat().st_size,resident_elf=str(elf.relative_to(ROOT)),resident_elf_sha256=sha(elf),resident_elf_bytes=elf.stat().st_size,
  resident_code_end='0x20054638',code_limit='0x20054638',payload_bytes=7884,root_bytes=256,reserve_bytes=200,
  abi_changed=False,P3_diag_early_writes=False,container_built=False,camera_executed=False,card_accessed=False,
  container_next_step='Bind gen 117 to resident_build_id and unchanged resident_abi_id; final 30-file card package belongs to the container task.')
 package=HERE/'local/package';(package/'resident-identity.json').write_text(json.dumps(identity,indent=2,ensure_ascii=False)+'\n')
 (package/'README.txt').write_text('resident v3.6 机身交付。SD_ROOT 只含新 ilaunch3。\n容器任务须先按 resident-identity.json 重绑 gen 117，再形成最终上卡包。\n统一机身刷入时必须挂 50mm。\n恢复：关机，挂 50mm，使用卡 A 的 Stage2l-50mm，按住「+ 和回放」开机。\n本次只执行主机与原生指令模型验证，没有访问相机或卡。\n',encoding='utf-8')
 labels={
 'i':('01 → OK → MENU。','01。','通过。'),
 'ii':('01 → OK → 滚动 → 尝试 02 → OK → MENU。','仍为 01。','列表已关闭，02 未选中，与评审结果相同。'),
 'iii':('01 → OK → 只滚动 → MENU。','01。','通过，关闭后滚动不进入 H08。'),
 'iv':('01 → OK → Fn2 → OK → MENU。','01。','通过，关闭后 Fn2 不打开配方编辑器。'),
 'v':('01 → OK → 关闭 → 重开 → 02 → OK → MENU。','02。','通过，同次启动真正切换到 02。'),
 'vi':('01 → 主 MENU → Image Settings → 原生模式。','阻塞前仍为 01。','BLOCKED，原有 state-9 系统链表模型缺失。'),
 'vii':('真实 ig_event 内 inflight=1 时嵌套 H07，再 MENU。','01。','通过，嵌套调用和外层应用均成功。'),
 'viii-a':('01 → 重开 → 坏快照先由 H07 检出。','01。','通过，保留 H07 关闭保护。'),
 'viii-b':('01 → 重开 → 坏快照先由滚动 H08 检出 → MENU。','01。','P0 已修复，故障调用跳过 H08 原生续体。'),
 'first_fault':('首次发布，尚未 OK，坏快照由 H08 检出。','尚未应用配方。','通过，原模式 1 保持不变。')}
 table={x['sequence']:x for x in a['scenario_table']};lines=[]
 for name in ('i','ii','iii','iv','v','vi','vii','viii-a','viii-b','first_fault'):
  x=table[name];label,deep,result=labels[name];native=x['native']
  lines.append(f'| {name}：{label} | {x["mode"]} | {deep} | {native["H07_native"]} / {native["H08_native"]} | {x["root"]} / {x["flags"]} | 0，停写。 | {result} |')
 report=f'''v3.6 的 P0-01 已在真实 M32R 指令 harness 中修复。i–v、vii 与评审基线相同。此交付可供 gen 117 重绑。主 MENU 完整路径仍有原有模型阻塞，未列为通过。

本次只写 `firmware/resident_v36/` 和 `firmware/image_v36/`。原始 v3.5、engine_v37、评审目录、native_harness 和官方输入共 {protected['files']} 个冻结文件均未变。没有访问相机或卡，没有刷机，没有构建容器。

| 本次产物 | 字节数 | SHA-256 |
|---|---:|---|
| [新 ilaunch3](local/package/SD_ROOT/ilaunch3)。 | {body.stat().st_size} | `{sha(body)}` |
| [resident.elf](../resident_v36/local/resident/build/resident.elf)。 | {elf.stat().st_size} | `{sha(elf)}` |
| 原生测试用 gen 116 DAT，只读。 | 66488 | `1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864` |

本次 build id 为 `{trust['resident_build_id']}`。ABI 为 `{trust['resident_abi_id']}`。重绑输入见 [resident-identity.json](local/package/resident-identity.json)。最终交付的 `SD_ROOT` 只含机身；gen 117 DAT 和最终 30 文件上卡包由容器任务组装。

`__resident_code_end=0x20054638`，payload 为 7884 B，root 为 244 B NOLOAD 加 12 B pins。root 前间隔正好 200 B。`resident.ld:22` 与 v3.5 逐字节一致，仍断言 `__resident_code_end <= 0x20054700 - 200`。没有降低门槛。

源码修改见 [hooks.diff](local/review/hooks.diff)。`resident.h`、`abi.h`、`engine_services.h`、链接脚本均未变，证据见 [abi-and-linker.json](local/review/abi-and-linker.json)。构建脚本只改本目录路径和新 build-id 域，沿用原 ABI 域。

`early()` 不再写 `diag_early`，删除 pack、gate 和 note 参数。root+232 的字段保留，以保持 ABI。按本任务约定，gen 117 关闭黑盒；此处删除诊断写入以回收空间。H07 的 `RF_PUBLISHED` 关闭逻辑保留。根校验移到所有 early 调用之前，避免重复校验；非法根且 state=6 的原有返回行为也保留，Host 用例已覆盖。

H06/H08 仅在 `RF_PUBLISHED` 且本次调用仍有八行时，写 `f[7]=0`、`f[1]=rv_skip_06/rv_skip_08`。入口已排除 H03/H04/H05/H09，因此 helper 中 H07 之外、编号不小于 6 的调用只有 H06/H08。

`rv_check()` 失败时先调用 `early()`，再 `rv_retire()`。这样在原生表被恢复成七行前，保留本次调用的八行语义。检查失败、inflight/RF_BUSY、!owned 这些出口共用同一保护。disabled 和 session 早退也复用 helper；七行时 H06/H08 不改续体。

| 实测尺寸步骤 | payload | 相对上一步 |
|---|---:|---:|
| 原 v3.5 控制流。 | 7880 B | 基线。 |
| 删除 P3 写入和参数。 | 7832 B | -48 B。 |
| H08 八行保护，含退役前判定。 | 7884 B | +52 B。 |
| 加 H06，共享续体写入。 | 7908 B | +24 B。 |
| 根校验只做一次。 | 7888 B | -20 B。 |
| 使用入口已限定的 hook 范围。 | 7884 B | -4 B。 |

因此删除 P3 回收 48 B，H08/H06 保护与等价控制流合计增加 52 B，净增 4 B。所有尺寸探针都使用原 200 B 链接断言；超限方案只保留失败日志。可重跑 [measure_size.py](../resident_v36/measure_size.py)，细项见 `resident_v36/local/h06-size/` 和 [byte-accounting](../resident_v36/local/byte-accounting/size.json)。

| 早退出口 | 本次可达性证据 | 处理 |
|---|---|---|
| rv_check 的 H08 退役。 | viii-b 与首次发布故障均从八行进入。 | 当次跳过；恢复七行后的调用放行。 |
| inflight/RF_BUSY。 | 在真实 ig_apply 内嵌套滚动，v3.5 进入 H08 原生续体并把 S 改成 9。v3.6 保持 1，续体 0 次。RF_BUSY 另有 Host 用例。 | 八行时保护 H08。 |
| !owned。 | 正常 OK 的 rv_ui_abort 同时恢复七行并清零 ui_restore[0]，关闭后按键不进 H08。另以明确标注的根字段故障保留八行并清零该字段，v3.5 可进原生 H08，v3.6 两次滚动均跳过。 | 八行保护，七行放行。该故障注入不冒充正常 abort。 |
| H06。 | 真实 inflight 中 H06 原生续体可达，v3.5 在 0x20268798 写回当前模式 1。v3.6 嵌套 H06 与故障退役均跳过，嵌套期间没有 S 写入。 | 同样使用八行条件，写 f[7]=0 和 rv_skip_06。 |

可达性原始证据见 [v3.5 对照](local/review/reachability-adversarial-v35.json)、[H08 重入与合法七行移动](local/review/extra-adversarial.json)、[H06 重入](local/review/reachability-adversarial.json)、[!owned](local/review/ownership-adversarial.json)、[H06 退役](local/review/h06-fault-adversarial.json)。嵌套测试控制中断点和测试栈，未证明相机调度会在该时刻重入。

下面沿用评审表。H07/H08 续体分别是 `0x202871DC`、`0x202BB96C`。模式 getter `0x20271FEC` 的固定返回替身已移除。未调用 preset_mode。diag_early 为 0 是删除 P3 后的结果。

| 序列 | 最终 S+0x36E | 深层结果 | H07 / H08 原生续体 | 根状态 / flags | diag_early | 判断 |
|---|---:|---|---|---|---|---|
{chr(10).join(lines)}

01 的深层摘要是 `19a2f5a0a52a203de1f198be11054da0c31706eec7e352822b4d2320aae62455`。02 是 `e50a09a1ea5199b1f33479fc4be41ccb61de03466a6636ed84e40ab7b7d46269`。viii-b 故障前后均为前者。01、02、04 各九行共 503 B 以及 T 的 2 B 控制值，实际读回字节均等于 DAT 中有效行。见 [逐行核对](local/review/deep-rows-comparison.json)。

退役后的七行列表可滚到 Natural=10，再到黑白=3，H08 原生续体共执行两次。原有 01 深层行仍在，未声称恢复了原厂深层行。保护只挡八行过渡调用。

28mm 首次 H01 在 ready=0、link=1 时保留七行，state=0、flags=2。用原生镜头就绪 setter 写 1 后，当前列表仍七行；关闭再开才发布八行。50mm 首次即可发布八行。`p2_gates.py` 的五种 ready/link 与 MOUNT 组合均保持七行，无 attempted 锁、文件 IO 或 RPC。见 [P2](local/review/p2-adversarial.json)。

官方 ZIP 的 SHA-256 已核实为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`。正向 ilaunch3 输入固定为 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。没有用 mutant fixture 作官方源。与官方及 v3.5 的差分均只落在 resident 窗口、原有七个 hook 站点和 0x16C 校验字段。七条 BRA 均指向实际 ELF 符号。其余 hook、两个 ADJ 数据字段、30 个 boot/OSD 窗口逐字节等于官方。机身审计候选的 28 个官方兄弟文件逐字节等于 genuine ZIP。

从文件 0x200 起重算 `sum(byte[i] * (i%6+2)) mod 2^32`，v3.6 为 `0x6A7FEFC5`，与 0x16C 字段相同。官方为 `0x6ACDB212`，v3.5 为 `0x6A7FF8D4`。差分、原始字节和窗口摘要见 [structural.json](local/review/structural.json)、[windows.json](local/review/windows.json)。

| 本次实际执行 | 结果 |
|---|---|
| `resident_v36/resident/build.py`，原 GCC/LD 与原编译参数。 | 受限链接通过。 |
| `resident_v36/run_host.py`，v3_checks.c，ASan/UBSan。 | `PASS_HOST checks=157249`。 |
| `image_v36/verify.py`。 | 68 文件重建一致，14/14 拒绝用例，7 条 BRA，3003 个受保护输入不变。 |
| 原 conformance.py，只读导入。 | PASS。输出与缓存只写本目录。 |
| 原 scenarios.py，只读导入。 | 20 项，0 violations，0 errors。此组是原有旧版本回归，不代替本次矩阵。 |
| 复制的 adversarial.py、h08_retire.py、h08_first_fault.py、scroll_both.py、p2_gates.py。 | 上表与门禁通过，移除模式 getter 替身。 |
| extra_scenarios.py、H06/!owned 补充用例、deep_bytes.py。 | 重入、合法七行选择及逐行字节核对通过。 |
| menu_native.py。 | 在原有 `0x2005F4C0` 缺少系统链表处报 `unmapped memory 0x8/4`。完整主 MENU 选择未验收。 |

命令和各次退出码见 `local/review/executions-*.json`。可重跑下面的本次入口，输出均留在两个获准目录。

```sh
/usr/bin/python3 -I -B firmware/image_v36/run_v36_checks.py matrix
/usr/bin/python3 -I -B firmware/image_v36/run_v36_checks.py faults
/usr/bin/python3 -I -B firmware/image_v36/run_v36_checks.py guards
/usr/bin/python3 -I -B firmware/image_v36/run_v36_checks.py supplement
/usr/bin/python3 -I -B firmware/resident_v36/run_host.py
```

评审脚本先复制到 `image_v36/local/review/` 再运行，修改记录见 [review-harness.diff](local/review/review-harness.diff)。gen 116 DAT 文件未变。为让新 resident 身份通过真实 loader，测试文件边界只在内存改 header 的 build id 与 header CRC；从 0x100 起的 payload、真实 engine 及行池完全不变，没有输出新 DAT。见 [fixture-binding.json](local/review/fixture-binding.json)。这不代替 gen 117 最终重绑后的验收。

本次执行了机身、resident 和 engine 的真实 M32R 指令。文件介质、RPC 单元、绘图及部分系统调用仍是模型。源码和反汇编仅用于解释控制流，未把只读分析当作真机运行证据。相机启动、实拍、实体存储和恢复未验收。

刷入统一机身时必须挂 50mm。恢复固定为：关机，挂 50mm，使用卡 A 的 Stage2l-50mm，按住「+ 和回放」开机。本次没有执行刷入或恢复。
'''
 (HERE/'REPORT.md').write_text(report,encoding='utf-8')
 (res/'REPORT.md').write_text(f'''resident v3.6 已在主机原生指令验证中关闭 P0-01。交 gen 117 重绑的机身与完整证据见 [image_v36/REPORT.md](../image_v36/REPORT.md)。

build id 为 `{trust['resident_build_id']}`。ABI 为 `{trust['resident_abi_id']}`，三个 ABI 头文件未变。

[resident.elf](local/resident/build/resident.elf) 为 {elf.stat().st_size} B，SHA-256 为 `{sha(elf)}`。payload 7884 B，代码末尾 0x20054638，root 前保留 200 B。resident.ld:22 未变。

hooks.c 删除 P3 写入和 pack 参数。H07 关闭逻辑保留。H06/H08 在八行早退时写 f[7]=0，并跳到各自 skip。rv_check 故障先判定本次续体，再恢复七行。根校验只做一次，非法根的原有行为保留。

P3 回收 48 B。H08/H06 保护与等价控制流合计增加 52 B，净增 4 B。Host 检查为 PASS_HOST checks=157249，ASan/UBSan 均通过。原生 i–v、vii 与评审基线相同。viii-b、首次发布故障、嵌套 H08 和 H06 均跳过原生续体。主 MENU 完整路径仍受原有系统链表模型阻塞。

本次只写 resident_v36 与 image_v36。没有构建容器，没有访问相机或卡。刷入时必须挂 50mm。恢复固定使用卡 A 的 Stage2l-50mm、50mm 镜头，按住「+ 和回放」开机。
''',encoding='utf-8')
 print('REPORTS_WRITTEN',identity['resident_build_id'],identity['ilaunch3_sha256'])
if __name__=='__main__':main()
