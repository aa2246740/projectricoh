full-r7 已暂存，generation 109，STAGED_HOST_ONLY。R6-02 已修；R6-01 按已接受的原生高亮限制保留。

```text
SHA-256 ff1a4d32a23456464e340ac6cf67f95a582a58e61f2860f21e070c1b1509b237
批准机身 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c
resident ELF f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58
build 2eea6eb324790b035d37d33395d60880a1909b4e693414a939dee45f96bfbae7
ABI 9583fdd751bebc36f3af305595559643
pins DF2BCAF5 / 6700E6FF / 1B3C7000
```

已核实的主机行为如下。

- 每次开机必须打开一次 Image Settings。首次 menu_open 才恢复本镜头最后已验证配方和 GXTS 微调。菜单未打开时不会执行记忆自动应用。无有效记忆时内部 cursor 回退 01，不自动应用；首帧原生高亮仍按下表决定。
- 50mm、Mount 显示 01–08，01/02 仍是 GR IV Posi/Nega；28mm 保留原生七项。OK 和 Fn2 都先应用当前高亮行，Fn2 再打开该行的微调面板。MENU 或强制退出微调面板仍撤回未保存的微调，保留 committed 外观。
- 从父页 tag 32 进入时，H01/H02 不接管；原生 getter 0x20271FEC 处理 S，再由 0x202870AC 的枚举及 0x20287158/164 的 stores 定高亮。每次重新进入都如此。因此记忆 03 可已生效，而首帧高亮 04；OK/Fn2 会转用 04。这是 R6-01 已接受限制，不宣称光标等于 live recipe。

| 进入时的 S 值 | 50mm 配方行 | Mount 配方行 | 28mm 原生行 |
| --- | --- | --- | --- |
| 1 | 02 | 02 | 2 |
| 3 | 04 | 04 | 4 |
| 4 | 06 | 06 | 6 |
| 5 | 07 | 07 | 7 |
| 6 | 05 | 05 | 5 |
| 9 | 01 | 01 | 1 |
| 10 | 03 | 03 | 3 |
| 其余字节值 | 02 | 02 | 2 |

S 以首次记忆自动应用之后为准。其余值先被 getter 写成 1，不能直接套枚举的 fallback 行 1。[官方字节与轨迹](local/native-get-mode-traces.json)覆盖全部 256 个输入；与批准机身的差异仅为既有 hooks。主机投影 getter、枚举、stores 和 tag-33 push，没有执行完整原生 UI。

GXLS 仅在列表实际关闭时尝试保存一次，包括正常 OK、MENU 和 H07 强制关闭。只有 committed slot 与最后验证记忆不同才写。仍留在列表内的确认延后到关闭。滚动期间零写；已有 01 记忆的 01→08→01 关闭后仍零写；槽位改变后 OK、MENU、强制关闭各一次 TEMP+rename；不改槽位重开零写。微调仍按原 GXTS 规则保存。

GXLS write、close、delete、rename 错误仅留在独立 preference PsStore/last_store，不设置或清除模块/S 的 RF_UNCERTAIN。失败不撤回已提交配方，不阻止后续预览、应用、GXTS 或新会话。后续保存先重读 A/B，处理 rename 已成功而最终读回失败的 generation。重启只用最新可验证正式记录，TMP 不参与；无有效记录则内部 01、无自动应用。

强制关闭在写入前后及 write/close/rename 内重入均已检查。inflight 拒绝嵌套 hook，外层关闭继续收尾，无等待或重复保存。覆盖普通 H07 关闭、两个 OK 入口以及写入后再次强制关闭；原生 I/O 延迟未实测。

产品源码只改 [adapter.c](containers/product/adapter.c) 和 [services.c](engine_services/services.c)。R4-01/R4-02、committed-look restore、可见行、192 B GXLS 格式和首次 menu_open 自动应用保留。48 槽 entry、record、160 B binding 和默认 GXTS 与 full-r6 全等。80 B trust、7,772 B resident payload、批准 body/resident/ABI 和 pins 均核对一致，未新增或修改 asm。

共 2,380 次 ASan/UBSan 主机运行。原套件 2,088 次全部复跑：r2 适配 252、历史流程 102、行为 124、故障 1,590、补充 20。故障含 840 次 GXTS、744 次 GXLS 注入和六个基线，覆盖 -1/-2、两种 rename、全部操作序号。每次 GXLS 故障后验证 Fn2、同行重选、换行、GXTS 保存、关闭、重开及重启；另恢复原故障映像，严格核对冷启动实际采用的完整记录。

新增 292 次包括 R6 审查 44、父 tag-32 入口 136、写入/强制关闭 52、升级 60。R6-02 的 16 个原反例已改为正向回归。R6-01 只验原生高亮及 OK/Fn2 与高亮一致。105/106/107/108 的无状态、GXTS 状态、GXLS 状态升级，空 IROM 首装，旧 DAT 覆盖 109 时全程零写，移除 DAT 后冷加载 109 均通过。15 次完整 C 验证、240 槽展开、冻结 validator 的 48 槽核对和 16 个重封 CRC 语义拒绝均通过。

继承限制仍保留：五例持续 open(-1) F02 继续复现；四例同次开机换镜头仍由冻结 resident 停用。测试按各自断言分类，见 [汇总](local/test-summary.json)、[逐例日志](local/all-tests.json)、[源码范围](local/source-scope.json) 和 [开发修复记录](local/development-fixes.json)。

| 大小或申请量，B | full-r6 | full-r7 |
| --- | ---: | ---: |
| 容器 | 61,936 | 62,228 |
| 引擎 | 52,912 | 53,204 |
| BSS | 11,188 | 11,192 |
| 数据，不含头和重定位 | 8,760 | 8,760 |
| 主块 request | 80,628 | 80,924 |
| 会话工作区 request | 1,460 | 1,460 |
| loader request | 608 | 608 |
| UI snapshot request | 1,968 | 1,968 |
| 正常保留量，含头 | 84,712 | 85,008 |
| 首装，含头 | 212,356 | 212,652 |
| 首装且已有 UI snapshot | 214,336 | 214,632 |

容器余量 3,308 B。file≤65,536、engine≤65,536、file+BSS≤114,688，PIC 平移核对、零未解析符号和一项容器重定位均通过。每块原生头 12 B；申请量不代表真机连续堆余量。

卡流程：关机，删除 GXRCE.OK，删除任何旧 GXRCE.DAT，只复制 [新 GXRCE.DAT](local/card_update/GXRCE.DAT)，保留其余全部文件。[manifest](local/card_update/manifest.json) 标记 STAGED_HOST_ONLY。本轮只在本机暂存，未访问相机卡或刷机。

12,276 个冻结输入未变，decisions.tsv 排除。完整读入 1,944 份原审查日志，见 [索引](local/review-log-read.json)。全部写入限本目录，理光派生字节在忽略的 local/。没有子代理、sleep、轮询循环、包安装、commit 或 push。

未知仍是真机 UI/M32R 执行、原生文件语义、掉电持久化、堆碎片和照片颜色。历史容器主机入口接到本轮 C，没有执行历史引擎机器码。

复核交付与冻结输入：

```sh
/usr/bin/python3 -I -B firmware/engine_v33d/finalize.py --check
```

重跑顺序：build.py；native_evidence.py；verify.py 的 compile、static、legacy、historical、behavior、faults、additional；verify_revision.py 的 compile、reviewer、boundary、policy、upgrade；inspect.py；finalize.py。每条均用 /usr/bin/python3 -I -B。首次冻结 inputs-before.json 不得覆盖。
