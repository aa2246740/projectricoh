full-r6 已生成并暂存，generation 108，引擎 v3.3，状态 STAGED_HOST_ONLY。body、resident 和 ABI 未改，无需重刷机身；本轮未访问相机卡。

```text
SHA-256 8ae376fe5edd4a2f78dbf3f9db95a70313f59d136f21ca300b4eb657b9e264d6
```

已核实的修改如下，所有源码均在本目录，未依赖取消的 engine_fix_r3 或 engine_v33。

- [gxts_io.c:31](containers/product/src/firmware/card_container_v2/gxts_io.c#L31)、[panel_gxts.c:59](containers/product/src/firmware/engine/panel/panel_gxts.c#L59)：原先旧绑定被视作缺失，现在完整读到 EOF 且 close 成功就保留“存在”证据。已读但验证无效的正式目标先删除再 rename；当前绑定唯一有效副本始终保留。持续三次 open(-1) 仍属未知。
- [adapter.c:315](containers/product/adapter.c#L315)：原先 uncertain 提前返回，留下未保存的 408 B 预览行；现在任何保存错误都先恢复 committed 配方行和 tweak，再关闭或停用。故障矩阵同时核对 410 B 行加控制值和完整 S 区。
- [eng_core.c:305](containers/product/src/firmware/engine/core/eng_core.c#L305)、[adapter.c:198](containers/product/adapter.c#L198)：原先固定 16 行，现在从已校验 metadata 的 descriptor 引用推导连续配方尾端。slot≠04 且引用 stock 04 的尾部为占位，04 保留为列表内原厂配方；当前容器前缀已逐槽核验，不另加计数元数据。H08、Fn2、光标和 GXTS 均用同一可见范围，GXTS 文件仍按原 slot-1 命名。
- [eng_core.c:334](containers/product/src/firmware/engine/core/eng_core.c#L334)、[adapter.c:260](containers/product/adapter.c#L260)、[adapter.c:271](containers/product/adapter.c#L271)、[panel_store.c:386](containers/product/src/firmware/engine/panel/panel_store.c#L386)：原先每次开机无应用记录，现在首次 menu_open 经 eng_select_saved 恢复本单元最后配方及 GXTS 微调，再发布列表。IROM 的 L50/LM0 A/B 记录用 192 B GXLS、generation、CRC 和完整 160 B 条目绑定；只有 recipe commit 成功且 slot 改变才写，走 TMP→write→close→完整读回→删除非保留目标→rename→正式读回。记忆读取错误不污染 GXTS store，也不停用。记忆写失败保留本次已提交配方，下次开机使用最后可验证记录；旧卡 CONFLICT 会话浏览不写记忆。
- R4-02 已修复，范围是两个 IROM 副本均可读且验证无效。[panel_store.c:177](containers/product/src/firmware/engine/panel/panel_store.c#L177)、[panel_store.c:304](containers/product/src/firmware/engine/panel/panel_store.c#L304) 允许在 TMP 完整验证后删除该无效目标。三单元、两种 rename 语义的双残缺安装和冷加载均通过；不可读副本不获此删除权限。

用户看到 50mm 01–08、Mount 01–08；50mm 09/10 已改为与 11–16 相同的 Stock 别名并隐藏。28mm 没有实际配方，完全保留原生 7 项菜单，不发布自定义列表。每次开机必须打开一次 ADJ Image Settings，首次打开才恢复该镜头最后选择、保存的微调及光标。记忆缺失、不可读、损坏、绑定过期或指向隐藏 09/10 时，光标在 01，不自动应用，也不停用。03 HC B&W 的实际行、S 区及微调冷恢复已核对。

数据由 full-r5 的只读管线先逐字节复现，再仅把 50mm 09/10 改为 stock 的 record/entry/ref 模式。其余 46 槽的 entry、record、160 B GXTS binding、240 B 默认记录均全等。独立冻结完整 C validator 对最终 48 槽输出与当前 validator 全等。80 B trust 与批准 resident ELF 全等，7,772 B resident payload 与批准机身映像全等，pins 为 DF2BCAF5/6700E6FF/1B3C7000。注意批准映像 SHA 为 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c；容器的 body trust 仍是批准 resident 固有的 da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7，未为改成映像 hash 而更改 ABI。resident ELF 为 f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58。

测试共 2,088 组主机运行：r2 适配 252、R4/R5 流程 102、新行为 124、故障矩阵 1,590、补充 20。含 1,584 次逐操作注入和 6 个基线 trace，覆盖空/单/双副本的 create、每次分块 write/read、close、delete、rename、open，原始错误 -1/-2，两种 rename。每例均验证即时 committed 外观，重启后再保存成功；最后配方写失败时当前成功提交的配方保留。连续八次同绑定保存覆盖三单元、两种 rename，generation 和实际值逐次核对。

其中 5 组专门复现既有持续 open(-1) F02 限制，不计为消除风险的证据。r2 中 33 个原 28mm 自定义 UI 场景改验原生菜单；三单元 GXTS 旧绑定及八连存另以同一真实存储 C 路径核验。另有 12 次完整 C 验证、四版共 192 槽展开、16 个重封 CRC 的语义篡改拒绝。所有行为程序启用 -Werror、ASan/UBSan，缺文件真实返回 -1。覆盖 105/106/107 有/无保存状态升级、空 IROM 首装、旧 DAT 优先且零写、移除 DAT 后 IROM 108 冷加载、首末行、越界、Fn2 末行、03 和 05 恢复、三镜头隔离、手选与自动应用失败。

| 大小/申请量，B | full-r5 | full-r6 |
| --- | ---: | ---: |
| 容器 | 59,704 | 61,936 |
| 引擎 | 50,276 | 52,912 |
| BSS | 11,172 | 11,188 |
| 数据，不含头和重定位 | 9,164 | 8,760 |
| 主块 request | 78,380 | 80,628 |
| 会话工作区 request | 912 | 1,460 |
| loader request | 608 | 608 |
| UI snapshot request | 1,968 | 1,968 |
| 正常保留量，含原生头 | 81,916 | 84,712 |
| 首次安装申请量，含原生头 | 210,108 | 212,356 |
| 安装且已有 UI snapshot | 212,088 | 214,336 |

每块原生头为 12 B。file≤65,536、engine≤65,536、file+BSS≤114,688 均满足，PIC 平移校验通过，容器重定位 1 项，未解析符号 0，没有新增或修改 asm。申请量不是相机堆余量。

[逐例结果](local/all-tests.json)、[测试汇总](local/test-summary.json)、[目标尺寸](local/artifact-inspection.json)、[开发修复记录](local/development-fixes.json) 均已保留。3,395 个冻结输入未变，decisions.tsv 不作为输入。全部写入只在 engine_v33b/；理光派生字节只在被 /local/ 忽略的目录。

卡流程为关机，删除 GXRCE.OK，删除任何旧 GXRCE.DAT，只复制 [新 GXRCE.DAT](local/card_update/GXRCE.DAT)，保留其余全部文件。[manifest](local/card_update/manifest.json) 明确标记 STAGED_HOST_ONLY。本轮只做本机暂存。

未知仍是实体相机 UI、M32R 实际执行、原生 rename、掉电持久化和堆碎片。持续三次 open(-1) 的缺失/不可读歧义仍保留。旧容器的主机 bootstrap 通过其声明 offset 接到本轮真实 C，未执行旧或新 M32R 指令。没有子代理、sleep、状态轮询循环、包安装、commit、push 或刷机。

复核清单：

```sh
/usr/bin/python3 -I -B firmware/engine_v33b/finalize.py --check
```

重建入口为 build.py；验证按 verify.py 的 compile、static、legacy、historical、behavior、faults、additional 顺序，随后 inspect.py、finalize.py。全部使用 /usr/bin/python3 -I -B。SHA256SUMS 覆盖源码、交付物和原始日志。
