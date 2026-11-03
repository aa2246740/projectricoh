# full-r4 第四轮报告

任务 1–4 全部通过，卡包已暂存为 STAGED_HOST_ONLY。14 组场景使用真实 full-r3/full-r4 容器、原产品与 resident C 对象，并启用 -Werror、ASan/UBSan。没有相机或实际 M32R 执行验收。

已核实：三单元 × 两种 IROM 布局 × 两种去除 DAT 后的卡状态，共 12 组 (iv-a)/(iv-b) 通过。另有 50mm、Mount 两组保存微调、删除旧 OK、更新和冷加载场景通过。逐例结果见 [host-results.json](local/round4/attempt-01/host-results.json)，运行日志见 [verify-attempt-01.log](local/round4/logs/verify-attempt-01.log)。

任务 1：IROM 为 A=105/B=106 或只有 A=106 时，有效卡 DAT=105 均优先加载。用户看到 105 的 16 行名称和配方数据，未停用，也不显示 SaveFail。引擎安装结果为 RV_CONFLICT；加载与浏览期间 create/write/delete/rename 全为 0，IROM、卡及其它文件逐字节未变。

该 105 会话允许保存微调。每槽先建 /IROM/T{50|28|M0}{slot-1:02}.TMP，再 rename 到 A.BIN；每次 create=1、write=3、rename=1、delete=0，共写入 240 B，未动卡文件或 IROM 容器。GXTS 的文件 generation=1，绑定为对应 105 条目。50mm 01/02/05、28mm 01 和 Mount 01 均实际保存了 3,2,-2,1,0,0，校验了 CRC、绑定和六个参数。

任务 2、3：移除 DAT，只留 OK=106 或完全不留 GXRCE 卡文件后，冷启动均从 IROM 加载 106，显示 16 行。A=105/B=106 从 B 加载，单 A=106 从 A 加载。加载与浏览没有文件操作。GXTS 原文件仍逐字节保留；50mm 01/02、Mount 01 的旧绑定不匹配，生效值回到默认，50mm 05 与 28mm 01 保留微调。没有停用或 SaveFail。

任务 4：先在 full-r3 下保存，再删旧 OK、更新 106 并冷加载，结果如下。

| 槽位 | 105 下保存值 | 106 冷加载生效值 | 结果 |
| --- | --- | --- | --- |
| 50mm 01 | 3,2,-2,1,0,0 | 0,0,0,0,0,0 | 回到默认 |
| 50mm 02 | 3,2,-2,1,0,0 | 0,0,0,0,0,0 | 回到默认 |
| 50mm 05 | 3,2,-2,1,0,0 | 3,2,-2,1,0,0 | 保留 |
| Mount 01 | 3,2,-2,1,0,0 | 0,0,0,0,0,0 | 回到默认 |

四槽的旧 GXTS 文件都没删除或改写。回到默认是条目绑定改变后拒用旧值，不是文件丢失。更新后立即读取及冷加载均核对了实际生效值，没有停用或 SaveFail。文件摘要见 [task4-results.json](local/round4/task4-results.json)。

任务 5：暂存文件为 [card_update/GXRCE.DAT](local/card_update/GXRCE.DAT)，与 [full-r4/GXRCE.DAT](local/full-r4/GXRCE.DAT) 逐字节相同，generation 106，59,516 B。[manifest.json](local/card_update/manifest.json) 标记 STAGED_HOST_ONLY。SHA-256：

```text
f874b5cd3da3dd1af749bf759a5e94e574886f55200cb61e6f2ea39cc0db971e
```

卡流程：关机、取卡、删除 GXRCE.OK、删除任何 GXRCE.DAT，只把新容器复制为卡根目录的 GXRCE.DAT，其它文件全部保留。这里只暂存本机文件，没有操作真实卡。

开发修复共两项。第一项把 host_round2.c 的三参数 tweak_path 及六处调用重命名为 slot_tweak_path，消除第三轮记录的同名冲突。路径格式和全部产品断言未变，未改 extra_checks.inc.c。第四轮首次编译和首次行为运行均通过。新增 verify_round4.py 隔离本轮输出；没有改前三轮验证脚本。

第二项修正 finalize_round4.py 的本地输出范围。首次收尾把 common.LOCAL 留在 local/round4/finalization，写 task4-results.json 时被 common.write 拒绝，尚未暂存卡包。修复后，preflight 仍单独落盘，后续输出范围恢复为本任务的 local/。原始 traceback 和修复记录见 [development-fixes.json](local/round4/development-fixes.json) 与 [finalization-first-failure.log](local/round4/finalization/finalization-first-failure.log)。这是本轮 helper 错误，没有修改或重复执行产品场景。

480 个冻结输入在开始、验收后和暂存后均未变。decisions.tsv 只记摘要，不属于冻结输入。此前 341 个文件全部保留，修改文件原件在 [round4/prior/](local/round4/prior/)，其余保持原位；第一轮 298 个文件另行复核通过。证据见 [scope-after.json](local/round4/scope-after.json)。容器、引擎、resident 和 body 未改，第一轮的三条目差异及重定位证明仍保留。批准 body 和 resident ELF 摘要再次核对通过。

未知仍包括真实相机 UI、实际 M32R 执行、原生 rename 和掉电持久化。本轮没有子代理、sleep、轮询循环、包安装、commit 或 push。写入仅在 firmware/full_r4/；未访问相机卡或刷机。[SHA256SUMS](SHA256SUMS) 覆盖全部交付文件和历轮原始证据。

以下入口复核既有验收结果、冻结输入、原产品对象和暂存文件，再重建清单。

```sh
/usr/bin/python3 -I -B firmware/full_r4/finalize_round4.py
```

以下保留第三轮报告作为历史记录。

# full-r4 第三轮报告

第三轮在主机夹具编译时失败，按规则停止，没有修复后重试。卡包仍为 BLOCKED_NOT_STAGED，没有 GXRCE.DAT 暂存文件。

已核实：按本轮批准，仅把 decisions.tsv 排除出冻结输入，摘要保留作参考；其余 480 个输入在开始与收尾时均与第一轮一致。现有 313 项校验全部通过，第一轮 298 个文件与本轮开始时的 314 个文件均保留。第二轮报告、旧清单和原脚本副本在 [round3/prior/](local/round3/prior/)，第一轮与第二轮的失败记录仍在原位。

编译使用原有 clang、-Werror 和 ASan/UBSan 选项，只尝试一次，返回码为 1。根因是 [host_round2.c:25](host_round2.c#L25) 定义三参数 tweak_path，而 host_checks.c:434 包含的 extra_checks.inc.c:1 已定义同名单参数函数。clang 报 7 个错误，首条为：

```text
error: conflicting types for 'tweak_path'
```

完整错误见 [编译日志](local/round3/logs/round3-host-compile.log)，调用与真实 traceback 见 [运行日志](local/round3/logs/verify-round3.log)。本轮审查漏掉了间接包含文件里的同名函数；未改引擎、resident、body 或原夹具，也未放宽断言。下一轮只需先处理新夹具的函数名冲突，再在新目录编译验证。

未运行：(iv-a)、(iv-b) 的三单元场景，以及 (d) 四槽微调保存、更新和冷加载。不能据本轮报告 16 行显示、SaveFail、停用、GXTS 保留或重置结果。

full-r4 候选未变，generation 106，59,516 B，SHA-256：

```text
f874b5cd3da3dd1af749bf759a5e94e574886f55200cb61e6f2ea39cc0db971e
```

只改三条目、引擎仅 type-64 BSS 重定位低半部不同等第一轮证据仍保留，见 [第一轮报告](local/round2/round1/REPORT.md)。本轮再次核对批准映像 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c 与 resident ELF f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58 的摘要。

验收通过后的卡流程仍为：关机、取卡、删除 GXRCE.OK、删除任何 GXRCE.DAT，只把新容器复制为 GXRCE.DAT，其它文件全部保留。本轮没有执行这些步骤。当前卡包 manifest 保留原样，本轮阻断状态另记在 [blocked-card-manifest.json](local/round3/blocked-card-manifest.json)。

未知：本轮所有行为与 GXTS 结果、相机 UI、实际 M32R 执行、rename 和掉电持久化。写入只在 firmware/full_r4/；未访问相机卡或刷机，未启动子代理、sleep、轮询、安装包、commit 或 push。清单覆盖原证据、新日志及本报告。
