"""Write the verdict only after every required execution has finished."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def main():
    commands = [json.loads(s) for s in (OUT / 'commands.jsonl').read_text().splitlines()]
    latest = {row['name']: row for row in commands}
    for name in ('build117', 'host-compile', 'host-stages', 'conformance', 'native-scenarios', 'native-gen117'):
        assert name in latest and latest[name]['returncode'] == 0, ('required execution unfinished', name)
    host = json.loads((OUT / 'runs/host-stages.json').read_text())
    assert len(host) == 26 and all(row['returncode'] == 0 for row in host)
    native = json.loads((OUT / 'native_harness/local/scenarios.json').read_text())
    assert len(native) == 20 and not any(row.get('error') or row['violations'] for row in native)
    actual_native = (OUT / 'command-logs/native-gen117.stdout').read_text()
    assert 'PASS v35 scenarios 7' in actual_native and 'write_open=0 boots 9' in actual_native
    inputs = json.loads((OUT / 'protected-scope-summary.json').read_text())
    assert inputs['current_review_input_content_changes'] == 0
    assert hashlib.sha256((ROOT / 'firmware/package_v35_g117/SD_ROOT/GXRCE.DAT').read_bytes()).hexdigest() == '4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a'
    calls = json.loads((OUT / 'native-file-calls.json').read_text())
    call_table = '\n'.join('| `' + row['pc'] + '` | ' + row['operation'] + ' | ' + (
        'CAP_FILE_WRITE 门禁之后，不可达。' if row['operation'] in ('create', 'rename', 'delete') else
        '要求 write-mode token；其唯一产生路径被门禁封住。' if row['operation'] == 'write' else
        'mark 读回辅助；写能力门禁之后，不可达。' if row['pc'] in ('0x2100ac14', '0x2100d1a0', '0x2100d1ac', '0x2100d1c8', '0x2100d1dc', '0x2100d270', '0x2100d284') else
        'flags=0，只读。' if row['operation'] == 'open' else '只读或只读句柄收尾。') + ' |' for row in calls)
    shrink = json.loads((OUT / 'symbol-shrink-audit.json').read_text())
    families = {'generic': '通用函数', 'generic/UI': '通用 UI', 'alias': '别名合并',
                'blackbox': '黑盒', 'install/store/GXLS': '安装、存储、GXLS',
                'install/workspace': '安装、工作区内联', 'install/GXLS': '安装、GXLS',
                'install/GXLS/GXTS/cursor': '安装、偏好、光标'}
    shrink_table = '\n'.join('| `' + row['symbol_family'] + '` | ' + str(row['old_bytes']) + ' → ' + str(row['new_bytes']) + ' | ' + families.get(row['family'], row['family']) + ' |' for row in shrink)
    text = '''不可以上卡。

本次容器的无文件写入修复通过，精确重建、22 个 Host 阶段及原生 harness 也通过。阻断点是任务第 2 项明确要求的二进制冻结条件没有满足：五个通用或 UI 函数在允许的文件家族之外缩短，受保护的 cursor 路径也发生了指令打包变化。不能把“规范化后的指令流一致”写成“机器码逐字节不变”。没有复现这些生成差异导致的相机故障。

审查对象仅为 gen 117、55,500 B 的 GXRCE.DAT，SHA-256 为 `4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a`。当前绑定 resident v3.5，build id 为 `9cc5359e073a3b65a223ca3af41055fd10e52b5e701db1fe08426023aea731ba`，ABI 为 `d7387c3670059c325186de3af1b3d5c6`。机身 H08 及 resident v3.6 的修复不在本裁决内，没有借机身的另一路 P0 判负容器。

只写本审查目录，没有访问相机、卡卷或刷机，没有启动子代理。所有 Python 命令均用 `/usr/bin/python3 -I -B`。文中的 Host 是实际产品 C 加原生边界替身；原生重放是实际 M32R 指令加文件、镜头 RPC、媒体和调度替身。它们均不是相机实测。

1. 发现、影响与最小修复

P0：本轮未发现可达的容器文件系统写入 P0。上一版 P0-01、P1-01、P1-02 的触发路径已关闭，证据见第 3 节。

P1-01：体积缩减超出“只能缩减文件家族”的验收边界。

已核实，gen 116 → 117 有以下变化，均来自最终 ELF。

| 通用或 UI 函数 | 116 / 117 字节 | 实际变化 |
| --- | --- | --- |
| `es_range.constprop.0` | 128 / 124 | 调用缩码与 packet 合并。 |
| `gate_validate.constprop.0` | 2,816 / 2,792 | LTO 重新分配寄存器、缓存中间值并重排指令；源代码未改。 |
| `gxr2_crc32` | 42 / 38 | 调用与前一条指令打包。 |
| `pn_address` | 68 / 64 | gen 116 的空地址分支被删。 |
| `pn_native_from_seed` | 388 / 380 | 两个调用缩码并重打包。 |

最清楚的反例是 `pn_address`。gen 116 在 `0x210070E0` 检查 `r1==0`，下一条再检查 `r2==0`。gen 117 从 `0x21004E18` 只检查 `r2==0`，原来的空地址检查不存在。它属于通用 UI 地址转换，不属于 install、store、GXLS/GXTS、mark 或 black-box 文件家族。源代码仍有 `if (!s || !n) return 0`，因此源代码差分不能代替本次机器码检查。

另一个受保护路径 `ig_apply` 从 184 B 增至 188 B。其 57 条非 NOP 指令规范化后相同，但 call 的 packet 编排改变。`list_bind` 和 `eng_current` 也有短调用与 NOP 排列差异。排除 ELF 地址立即数、符号调用距离、相同 helper 的 LTO 别名及 packet/NOP 后，所查的 apply、T、ISO/B5 所在 `eng_apply`、RPC、list/publish、cursor、Fn2 指令流一致。72 组实际 LUT/T/完整设置区差分也一致。这些证据支持“未发现行为回归”，不满足题目写明的字节冻结规则。

用户可见失败尚未复现；本项是明确验收门槛失败，不宣称已证明崩溃或写坏卡。最小修复落在构建边界：保留 gen 116 受保护 core、gate 和 UI 通用函数的受审指令及其地址重定位信息，只让已允许的文件路径、`eng_menu_open` 和 `preload_gxts` 改变，并把逐符号比较作为构建失败条件。仅改源码注释、继续跑 Host 或重绑 v3.6 build id 都不能关闭本项。本轮没有构建这个修复，尺寸成本未知。若主任务希望接受这些编译器变化，必须先明确改变第 2 项验收条件，再对这些差异作单独裁决；本审查不自行放宽。

若已在相机使用这份候选而要撤回，恢复用卡 A 的 Stage2l-50mm：挂上 50mm，用“+ 与回放”进入恢复更新。任何机身刷写都必须挂着 50mm。本轮没有执行这一恢复。

证据：[逐符号差分](symbol-diff.tsv)、[全部缩减的归属](symbol-shrink-audit.json)、[真实汇编差分](key-functions-asm.patch)、[受保护指令流比较](instruction-delta.json)、[允许的能力位变化](instruction-delta.patch)、[72 组实值差分](differential-live-results.json)。规范化比较明确不是逐字节证明。

P2-01：成功进入 Fn2 后，RAM 首次/最近 apply 固定记录仍为空。

三单元均独立复现，选择 01 后成功 Fn2 apply 有 172 次 W，但 `apply_count=0`、`first_valid=0`、`latest_valid=0`。`ig_panel_open` 只在 `select_cached` 失败时调用 `ig_bx_apply`。本项继承 gen 116，builder 也已说明保留。文件落盘虽然取消，RAM 诊断仍不能把空固定记录解释为“没应用过”。

用户可见影响是故障定位可能漏掉真正发生的 Fn2 应用，不影响本轮正常颜色用例。恢复无需刷机，诊断时结合同次启动的 RPC/W 事件，不能单凭空固定记录下结论。最小修复是让成功和失败的 Fn2 apply 都用真实 status、T、W 更新该 RAM 记录，仍不调用文件服务。如需整体撤回 mod，沿用上面的卡 A、50mm、“+ 与回放”恢复流程。证据：[三单元独立输出](command-logs/extra-summary.stdout)、[探针](extra_host.c)。

2. 体积、源代码与数据

生产源码变化只在 adapter、blackbox、`eng_menu_open` 及 pack 文件上限；另外有构建入口、输出路由和测试变化。[完整源码差分](source116-117.patch) 和 [构建入口差分](build116-117.patch) 均已保存。旧脚本 build116.py 本身未被改写。

| 项目 | gen 115 | gen 116 | gen 117 |
| --- | ---: | ---: | ---: |
| DAT | 65,252 | 66,488 | 55,500 B |
| engine | 55,700 | 56,936 | 45,948 B |
| BSS | 11,520 | 11,524 | 9,652 B |
| file+BSS | 76,772 | 78,012 | 65,152 B |

gen 117 的文件余量为 10,036 B，engine 余量为 19,588 B，file+BSS 距 114,688 B 还有 49,536 B。文件满足恢复后的 65,536 B 上限，也超过旧审查采用的 512 B 余量。resident 的 RV_MAX_FILE=98,304、RV_MAX_CODE=65,536、RV_MAX_IMAGE=114,688 未改。

engine 减少 10,988 B，可精确拆成函数地址区间并集减少 10,918 B，加其它汇编、只读常量和填充减少 70 B。BSS 另减 1,872 B。非 engine 的 header、重定位表和数据合计仍为 9,552 B，其中 header 256 B、重定位表 8 B、数据 9,288 B。[字节核算](size-accounting.json) 没有把 LTO 同地址别名重复计费。

以下列出所有按 LTO 家族合并后确实缩减的符号。原始 52 个消失名称里有 27 个仍有同家族符号，不能把改名误报成删功能；[LTO 名称对照](symbol-renames.json) 和完整原始表保留了这些情况。`last_p32` 的内容与保留的 `p32` 相同。

| 符号家族 | 116 → 117 字节 | 归属 |
| --- | ---: | --- |
__SHRINK_TABLE__

除 P1-01 的五项通用/UI 缩减外，其余缩减属于写入、安装、偏好、黑盒路径或其内联/别名变化。`ig_menu` 同时包含允许的光标和 metadata 默认值改动；`ig_event` 删除文件保存及存储失败回滚，保留 RAM draft commit。代码区缩减没有靠改配方内容取得。

独立 Python 从三份真实 DAT 解出全部 48 个 entry552、48 条 records、3 maps、48 metadata、3 pins，gen 115、116、117 全部相等，三单元各 8 owner。不是只比较 builder 缓存的 expanded 文件。[独立展开与比较](artifact_checks.py)、[数据哈希与结果](recipe-data-equality.json)。

3. 最终机器码的无写证明

本轮先验证交付 DAT 的代码段等于 engine.elf，再实际应用 DAT 重定位，验证其等于 relocated ELF。下列汇编的每条已解码指令字节还逐条对回重定位后的 DAT。没有只读源代码就签“无写”。

`ig_init` 两条成功路径分别在 `0x2100B3A4` 和 `0x2100BB6C` 装入 `0x000E0000`，不含 CAP_FILE_WRITE=`0x00010000`。loader 初始 RV_READ_CAPS=`0x7FFF` 也不含它。实际最终 M32R dispatcher 重放得到 session capabilities=`0xE7FFF`。

create 的机器码在 `0x2100CF1C..CF28` 读 session+340、与 0x10000 相与，为零跳到 RV_CAPABILITY。rename、delete、mark 的共同门禁在 `0x2100D078..D084`。普通 open 在 `0x2100CF5C` 令 flags=0。文件 token 的 mode 在 `0x2100D02C` 只由 op==3 产生写模式；op=5 在 `0x2100CB84..CB98` 要求 mode 为写。因此以全零 token 表开始，op=3 不可达，之后无法取得合法写 token。没有其它对 capabilities 或 file-mode 的合法赋值路径能打破此不变量。

真实 M32R 调用逐项得到：storage query capabilities=3；create、rename、delete、mark 均 RV_CAPABILITY；用合法只读 token 请求 write 得 RV_RANGE；只读 close 得 RV_OK；再次 ig_init 仍未开启写位。整个过程 native mutations=0、write-open=0、live handles=0。[机器码门禁实验](machine-gates.json)、[原始输出](command-logs/machine-gates.stdout)。

全部 21 个原生文件调用点如下。

| relocated PC | 服务 | 本次可达性 |
| --- | --- | --- |
__CALL_TABLE__

native bridge 表里的文件入口确认为 open `0x200A40B4`、read `0x200A449C`、close `0x200A437C`、create `0x200A544C`、write `0x200A45E8`、rename `0x200A49D8`、delete `0x200A4910`。完整 19 项 bridge 及 RPC8 `0x2009005C` 均已核对。没有直接跳到官方地址的 bl/bra/jmp，也没有额外装入 0x200A/0x200B 文件/FAT 入口的旁路。11 处寄存器间接跳转已枚举：产品固定回调、内部 switch 表、native bridge 公共跳板和 RPC8。没有额外 DCF/format/FAT 调用入口。这里证明的是容器主动文件调用；不宣称整个相机原生系统不再写照片或设置。

resident_v35 的 loader.c 所有 open 均为 flags=0，只调用 open/read/close。shared.c、resident.c 没有 create/write/rename/delete。复制参与编译的 resident 与实际 v3.5 对应 15 个文件逐字节相等。[文件调用上下文](native-file-calls.json)、[全部 bridge](all-native-bridges.json)、[间接转移清单](indirect-transfers.json)、[关键门禁指令](no-write-machine-cutpoints.json)、[resident 源码一致性](resident-source-equivalence.json)。

官方 close 的 P1-01 退路也独立重放。genuine ZIP SHA 为 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`，ilaunch3 SHA 为 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`，没有用 04168d00… fixture。11 段文件/FAT 机器码重新从官方文件提取并以 M32R 大端反汇编，VMA 始终等于文件偏移+0x2004AE00。

29 个官方机器码用例通过，其中 16 个组合覆盖只读 open、0/1/17/4096 B read、read error 和底层 close error。外层句柄计数均回到 0，均不经过 `0x200A43F4..4418` 的脏缓冲回写及漏清理路径。open 把模式初始化为干净，read 在 `0x200A44D0` 设为 2；write 才会进入模式 1。没有 write，就不会触发旧 P1-01。原先两次脏 close 错误耗尽计数的正对照也成功复现，说明探针能看到这个缺陷。

这些重放的 lookup、media、lower close 有显式替身，不是对物理卡错误和 FAT 持久性的测试。[官方重放输出](command-logs/official-replay.stdout)、[结果](native/replay-results.json)、[新提取片段](native/ranges.json)。首次提取遗漏了 objdump 的 -EB；错误已保留，改为显式大端后全部重跑通过，没有把那个失败算产品缺陷。

4. 测试断言有没有被放松

对 `host-expectation-changes.json` 的 35 条替换从原 gen 116 Host 顺序重放，除三条空白分隔行外，与实际 gen 117 Host 完全相同。另查 history 的五处光标断言。没有发现与文件停写、冷启动 04、旧偏好或新增边界计数无关的弱化。[逐条审计](test-expectation-audit.json)、[原始清单](host-expectation-changes.json)、[实际 patch](host117.patch)、[history patch](history117.patch)。

| 改变 | 独立判断 |
| --- | --- |
| 黑盒预期从写 SD 改为 RAM 环、seed 和 flush 无 I/O | 对应停写，T/配方实值检查保留。 |
| 安装、TEMP、DAT→OK、GXLS/GXTS 的写故障改为不可达 | 对应停写；所有 native create/write/rename/delete/write-open 另作全阶段零次数检查。 |
| store-fault 原来的默认回滚改为 current(+2) | 因 OK 改为 RAM 接受而合理，但单看 current 不够，已补实际 LUT/T/完整设置区差分。 |
| create 成功改为 CAPABILITY，已关闭 token 的 write 改为 STALE | 没有合法写 token，原来的写 token 情景已不再成立。读错误与 quarantine 拦截仍测。 |
| conflict 不再置安装 quarantine，隐藏较新 IROM 不再被覆盖 | 安装扫描取消后的预期；loader 自己的拒绝/quarantine 场景仍保留。 |
| 冷启动 remembered/01 改为 04，重启 tweak 改为 defaults | 与本代产品契约一致；保留重开已提交槽、完整设置区及换单元检查。 |
| 新增 native open/close 包装 | 所有 flags 必须为 0，close 只接受只读句柄，连失败 open 尝试也计数。 |

5. 实际执行结果

隔离构建从 source/model 重新编服务 archive、LTO engine、relocation ELF 和完整 DAT，结果与交付物逐字节相同。只修改隔离副本的输出路由、guard、随机种子路径文字和负对照 include 路径，变更在 [routing.patch](routing.patch)。没有在会写回自身树的原脚本目录执行构建或测试。

ASan/UBSan 重新编译并实际执行 22 阶段，共 255 个原阶段 Host 进程，再加 3 个 history 和 3 个 G117 进程。vectors 独立核对当前与历史数据。实际阶段输出为：

```text
__HOST_PHASE_OUTPUT__
PASS historical power projections: three units, 192 unclosed pairs, 24 ROM-reset slots
HOST_RESULT PASS stages=22 extra=history+three_units failed= []
```

所有三单元的 G117 输出均包含 `counterexample=P0-01/P1-01/P1-02 ... fault_path_unreachable=1`、`highlight cold=4 apply01_reopen=1 apply08_reboot=4`、`stale IROM115=2 ... source=CARD generation=117`、`full_session ... zero mutations` 及 `B5 low_byte_at_apply=0xa5 retained=1`。[逐阶段 stdout/stderr 与退出码](runs/host-stages.json)、[总输出](command-logs/host-stages.stdout)、[编译/执行命令](commands.jsonl)。

另执行 72 组 gen 116/117 正常路径差分。每组对实际九行 LUT、T 及 4096 B settings 作逐字节比较，覆盖三单元、八槽、默认/+2/-3 微调，全部相同。gen 116 用原有只读 sanitized 对象，gen 117 用本轮重编对象；这项是 Host 差分，不冒充两代 M32R 程序的全状态等价。[差分探针](differential_host.c)、[结果](differential-live-results.json)。

tools/native_harness 已复制后执行。解释器、conformance.py、scenarios.py 均与原文件相等，只改 ROOT 路由及记录 open flags。[原生复制差分](native-harness-routing.patch)、[源文件哈希](native-harness-equivalence.json)。conformance 通过；20 个既有场景的 violations 均为空，error 均为 false/空。这 20 个使用旧 113/114/115，单独不算 gen 117 通过。

另实际执行 builder 的 run_v35_g117 副本，绑定本轮独立重建的 DAT/ELF、指定 v3.5 body。实际输出如下：

```text
__ACTUAL_NATIVE__
```

[原始 native stdout](command-logs/native-gen117.stdout)、[20 组结构化结果](native_harness/local/scenarios.json)。没有把旧场景通过替代当前 DAT 的执行。

6. 三单元产品状态、拔卡与故障

| 情景 | jlaunch 50mm / qlaunch 28mm / l08firm MOUNT 的实际 Host 结果 |
| --- | --- |
| 冷启动及旧 GXLS=08 | 九行 stock、T=2，零 W，无 commit，高亮 04。 |
| 显式应用 01 后重开 | LUT/T 匹配 01，高亮 01。 |
| 应用 08 再模拟重启 | 纯 04、高亮 04，启动不发 W。 |
| Fn2 接受 +3，重开同槽 | live LUT 确实改变，RAM current=+3；MENU 保留已提交值。 |
| Fn2 后模拟重启 | 高亮 04，再应用原槽使用 default=0，LUT 回到该槽默认实值。 |
| 已应用后拔卡、SD 全零、IO epoch 改变 | 下一次 ADJ 仍显示当前槽；九行/T 未变，可以从 RAM 应用 02；再开 32 次没有 native 文件读取和追加 RPC。 |
| 无卡重新启动、只有旧 IROM | 当前容器不再载入，原生七行；32 次 H01 无重试。 |
| T 拒绝 | 零 W，503 B rows 不变，容器停用并退原生七行；失败后不开出错误的八行高亮。 |
| RPC 中途失败 | 第 16 次 RPC 注入失败，已有 9 次 W，8 个 stock 字节已改变；live 既不是完整 04，也不是完整 01，custom list 被撤回。没有之后的 W 或重试。 |
| 四个分配点逐个失败 | loader workspace、main、menu workspace、UI snapshot 均能停用，原生七行、零 W、无重试。 |

RPC 中途失败不能读成“错误后已自动恢复纯 04”。中途写错后的 partial live 数据留在镜头内；原生七行只表示容器 UI 撤回，不证明颜色回到 stock。应重启后再用；若要撤回机身 mod，使用卡 A Stage2l-50mm、50mm 挂载、“+ 与回放”，机身刷写必须挂 50mm。这是继承的失败收尾边界，本轮未把它伪装成原子回滚，也未证明它会在下一次物理上电后继续混串。

T 首次拒绝时 core 内 cursor 仍是请求的 02、applied=0；之前已提交 01 时则恢复 core cursor=01。这两个值都不再发布到可见八行列表。正常滚动本身也只移动候选光标，live 要到 OK/Fn2 才应用，因此不能把正在浏览的高亮当作实时生效指示。

推断：载入后的 engine、配方、metadata、微调值及 live 账本都在 RAM，正常 ADJ/Fn2/OK 路径无需再读 DAT、GXLS、GXTS 或黑盒文件。CTL 只在 bootstrap 读一次，拔卡后重开不会重读它。若真实卡门事件同时改变 unit/link/heap/settings 身份，现有 epoch/owner 检查会停用，而不是继续使用旧身份。

未知：没有操作真实卡门、没有模拟原生所有卡门任务及并发调度，也没有执行镜头真实断电初始化。Host 的 reboot 明确重建官方 stock，再检查 settings 投影。它支持本轮状态规则，不能单独证明物理相机永远“04 不混串”。[独立故障与拔卡输出](command-logs/extra-summary.stdout)、[探针源码](extra_host.c)。

7. 实际会留下的旧文件与 CTL

真实 gen 115 的两份旧 IROM、旧 GXLS 及有效旧 GXTS，已在新增 G117 用例中组合执行。它们保持原字节，旧偏好 open=0，卡上选中 gen 117。没有把 115 header 改成新身份来伪造“旧包”。旧 115 在只有 IROM 时因 resident/ABI 身份不符而被拒绝。

另外组合实际 gen 105、109、111、113、114、115 DAT，两个 IROM 副本、旧偏好和四种 CTL，覆盖三单元共 72 组。对 IROM open 设置了拦截计数，正常卡 DAT 被接受后 old-IROM-opens 始终为 0；旧偏好 open=0，所有文件字节不变、mutation=0。更早的 105..111 等原阶段也已复跑。

| CTL 情况 | 行为 |
| --- | --- |
| 缺失 | 从卡运行 117，冷启动 04。 |
| CRC 错或有效 enable=1 | 从卡运行 117，冷启动 04；只读后忽略无效/非停用记录。 |
| 完整有效 `GXRC3401`、value=0、16 B | bootstrap 按现有停用规则退出，本次启动原生七行，无写、无重试。它不会因为是旧文件就被无条件忽略。 |
| 读错、close 错、多余字节、无 SD identity | 原 30 个 CTL 场景保留并通过；未取得有效完整停用记录时不触发停用。 |

干净卡只放题定的 30 文件、不含 CTL 时，适用第一行。包里 28 个官方文件逐字节等于 genuine ZIP 和提取目录；DAT 不改名 OK，也不安装 IROM。当前启动载入后移除卡，RAM 仍可用；下一次启动必须重新有卡 DAT。有效停用 CTL 不属于“总是忽略”的范围。[旧状态输出](command-logs/extra-summary.stdout)、[交付身份](artifact-identities.json)。

8. 堆与绑定

本轮用 M32R 交叉编译重新测量 heap34c 的实际类型。SessionWork=1460、RvLoadWork=608、RvUiSnapshot=1968、RvSession=1104、RV_BLOCK_OVERHEAD=7504 B，与 gen 115 的布局相同。主块请求为 `7504 + align4(file+BSS)`。

| 请求模型，含每块 12 B native header | gen 115 | gen 117 |
| --- | ---: | ---: |
| 主块请求本身，不含 header | 84,276 | 72,656 B |
| 安装缓冲 | 两块各 65,536 | 无 |
| 首次安装模型 | 216,004 | 无安装阶段 |
| 已有 UI 再安装模型 | 217,984 | 无安装阶段 |
| 常驻及可选四块 | 88,360 | 76,740 B |

gen 117 的四块目标请求为 `[608, 72656, 1460, 1968]`，常驻比现场用过的 gen 115 模型少 11,620 B。独立 Host 实际只申请四块，没有 65,536 或 73,728 B install buffer。macOS Host 的含指针结构分别表现为 616/1512 B，不能把 Host64 的 sizeof 当成 M32R 堆申请。本轮首次探针误把目标大小当成 Host 大小，已保留失败，随后按 Host sizeof 检查并单独交叉编译目标布局，三单元通过。

源码遗留的 `heap34c.py` 仍写着两块 73,728 B 的旧安装模型，不适合直接报告本代实际峰值。本报告只使用本轮交叉测量和真实申请轨迹修正后的模型。没有测相机堆水位、碎片或栈余量。[目标布局和模型](heap-results.json)、[测量脚本](heap_review.py)、[四点故障注入](command-logs/extra-summary.stdout)。

resident build id 已从实际 v3.5 源码及工具链重算，ABI 也独立重算，均匹配当前 DAT。后来另一路正在改 v3.6；本审查没有用其变化后的文件验收本代，也没有给它签字。

实际运行 build117 的 `--resident-trust`，只在隔离输出内使用明确标为不可安装的假 build id。与当前绑定相比，精确变化为：

| 文件 | 字节位置 | 原因 |
| --- | --- | --- |
| DAT header | 十进制 80..111，十六进制 0x50..0x6F | 32 B resident build id。 |
| DAT header | 十进制 20..23，十六进制 0x14..0x17 | header CRC32 随上述字段重算。 |
| trust.bin | 十进制 40..71 | 旁路 Host trust 的 build id。 |

ABI 不变时，header 212..227 不变；payload CRC 的 24..27 不变；全部 payload、engine、relocation、BSS 尺寸、entry、配方数据均不变。代码从 header 取 build id，用于身份验证及 RAM 诊断收据；它不参与配方运算、默认值、函数选择或其它代码生成。因此重绑不会暗改这些内容，也不会修复 P1-01 的生成差异。实际新 v3.6 的身份和机身接受仍需自己的小 delta 检查。[实际重绑结果](empirical-rebind.json)、[实际输出](command-logs/rebind.stdout)、[绑定核对](binding-and-rebind.json)。

9. 执行范围与证据完整性

已执行：隔离重建、数据独立展开、ELF 符号与指令比较、能力门禁 M32R 实验、29 个官方 wrapper 用例、22 Host 阶段、history、G117 三单元、独立热拔卡/T/中途失败/分配失败/旧状态矩阵、72 实值差分、conformance、20 原生基线、7 组 G117 原生场景及实际重绑实验。

只读检查：上一版完整 REVIEW、生产源码及测试 patch、官方 FAT 深层函数、resident loader/source、gen 115 堆模型和当前 package。没有执行真实 FAT 媒体写入、相机启动、物理掉电、LCD 显示或拍摄，没有接受 v3.6 机身修复。

初始冻结 30,337 个文件。当前审查直接相关的 4,737 个输入内容变化为 0。全量复核另观察到 resident_v36 的 31 项、image_v36 的 226 项变化，均在题目说明的另一路机身工作目录；本审查没有写这些路径，也没有用它们替代本次 v3.5 证据。不能把全仓库写成“全部零变化”。[前快照](protected-before.json)、[后快照](protected-after.json)、[全部变化](protected-changes.json)、[范围归属](protected-scope-summary.json)。

[SHA256SUMS](SHA256SUMS) 使用本目录相对路径，不包含清单自身。构建副本、检查脚本、输出、错误、反例和明确标注的不可安装重绑 fixture 均随清单保存。从本目录可运行：

```sh
shasum -a 256 -c SHA256SUMS
```
'''
    text = text.replace('__CALL_TABLE__', call_table).replace('__SHRINK_TABLE__', shrink_table)
    text = text.replace('__ACTUAL_NATIVE__', actual_native.strip())
    text = text.replace('__HOST_PHASE_OUTPUT__', '\n'.join(row['stdout'].strip() for row in host[:22]))
    (OUT / 'REVIEW.md').write_text(text)
    print('Wrote REVIEW.md; verdict 不可以上卡, one P1 acceptance blocker and one inherited P2')


if __name__ == '__main__':
    main()
