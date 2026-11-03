不可以上卡

两个 P1 阻断。审查对象是 `firmware/engine_v33b/local/card_update/GXRCE.DAT`，generation 108，61,936 B；文件实算 SHA-256 为：

```text
8ae376fe5edd4a2f78dbf3f9db95a70313f59d136f21ca300b4eb657b9e264d6
```

P1 · R6-01：首次建页时，原生七项映射会覆盖恢复的配方光标。

场景：保存 03 HC B&W 和 Cont=2，重启，从父视图 tag 32 打开 Image Settings。引擎正确恢复 03，但 H01/H02 都没有接管返回路径；原生代码随后把 S 模式 3 映射成第 4 行。此时实际配方是 03，光标却在 04，按 Fn2 会应用 04 并改掉记忆。没有记忆时也有反例：原生 S 模式 1 把预设的光标 01 改成 02。两镜头、两种 rename 语义共八例复现，不注入 I/O 故障。

依据：`firmware/resident_v32/resident/hooks.c:8-15,59-65` 要求原生栈顶已经是 tag 33，才覆盖 H01/H02。实际建页顺序相反：官方机身文件偏移 `0x23C2A8` 是 H02，`0x23C304` 把模式 3 映射成 r8=4，`0x23C358/0x23C364` 写光标；直到 `0x23C3A4` 才调用 tag-33 建页。对应 VA 是 `0x202870A8/0x20287104/0x20287158/0x20287164/0x202871A4`。`firmware/engine_v33b/containers/product/src/firmware/engine/core/eng_core.c:334-338` 的自动应用发生在这些原生步骤之前。

见 [03 反例](local/logs/case-parent-remember03-0-1.log)、[空记忆反例](local/logs/case-parent-empty-2-1.log)、[官方建页指令](local/logs/native-menu-disassembly.log) 和 [枚举字节执行轨迹](local/native-enum-traces.json)。主机运行真实 resident/产品 C，枚举执行官方字节；后续两次光标 store 按官方指令投影，未执行完整原生 UI。相关原生续行字节已对回批准机身映像。

既有测试 `firmware/engine_v33b/containers/product/host_checks.c:240-243` 在 H01 前就放好了 tag 33，因此漏过此路径。必须让初次建页也保留配方光标，再用未预建 tag 33 的入口复测；仅调整行数不能解决。

P1 · R6-02：记忆文件保存失败会污染配方应用，下一次正常操作停用引擎。

场景：选择 05 时，仅令 `/IROM/L50.TMP` 或 `/IROM/LM0.TMP` 的第一次 write 返回 -1。05 已成功应用，引擎仍 READY，但全局 `RF_UNCERTAIN` 未清。接着按 Fn2，或再次选择同一行，不再发生模块行写入，预览服务因该标记拒绝调用，引擎进入 `RV_DISABLED_UNTIL_REBOOT`，菜单退回七项。TEMP close 或 rename 失败也能触发。两镜头、两种 rename 语义共十六例复现。

依据：`firmware/engine_v33b/engine_services/services.c:83,92,137` 把存储错误写进全局标记；`firmware/engine_v33b/containers/product/adapter.c:284-292` 保留已提交配方并继续。下一次同槽应用在同目录 `src/firmware/engine/core/eng_core.c:191` 跳过 deep 事务，因而没有清标记；`services.c:332-333` 拒绝预览，最终由 `firmware/resident_v32/resident/resident.c:70` 停用。此时 `eng_uncertain()==0`，模块没有新增 W，错误来自记忆文件事务。

见 [write 后按 Fn2](local/logs/case-poison-write-panel-0-1.log)、[Mount 同行重选](local/logs/case-poison-write-same-2-1.log) 和 [rename 后按 Fn2](local/logs/case-poison-rename-panel-0-1.log)。应区分记忆文件与模块/S 的不确定态，并验证失败后同次开机的下一步操作。现有故障测试在检查当前配方后就重启，漏过这个传播路径。

其余核对结果如下。

- R4-01 的旧绑定保存与 R4-02 的双残缺安装，在指定输入范围内已修复。可读旧绑定、A/B 有效副本保留、连续八次保存、空 IROM、单份及双份 1,024 B 残缺、遗留 TMP 均通过。没有复现新增的有效引擎副本删除。840 次 GXTS 故障注入核对即时 410 B 行/控制值和完整 S 区恢复，随后重启再保存通过。
- 描述符确实导出 50mm/Mount 各八行，28mm 不发布自定义列表；H08 越界被拒绝，Fn2 第八槽和原 slot-1 文件名一致。H01/H02 的初次建页例外见 R6-01。换单元而不重启会由 `resident.c:34-43` 停用本次会话，不会自动 rebind；此为继承限制，原生七项可撤回。
- GXLS 是 192 B，含 generation、CRC 和完整 160 B 绑定。缺失、损坏、旧绑定及隐藏 09/10 在记录读取检查中均不自动应用或停用；03 的行、S 和 GXTS 冷恢复本身正确。744 次记忆保存故障注入通过已有的即时/重启断言，但不能覆盖 R6-02。每次换行都会提交一次记忆；01→08→01 的 15 次选择产生 15 次 TEMP 创建及 rename，无须按 OK，见 [写频率](local/logs/case-write-frequency-0-1.log)。这不是介质磨损测量。
- 独立 Python 展开与重新编译的完整 C 对 144 槽的 entry、record、GXTS binding 和 240 B 默认记录一致。相对指定 full-r5，只有 50mm 09/10 改为 stock 别名，其余 46 槽全等；两镜头 01/02 为 Posi/Nega。见 [字节核对](local/artifact-results.json)。
- 80 B trust 与批准 resident ELF 全等，build/ABI 从冻结源码和工具摘要重算相同，pins 为 `DF2BCAF5/6700E6FF/1B3C7000`。批准机身 SHA-256 为 `05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c`；其偏移 31,084 B 的 7,772 B resident payload 与 ELF 全等。body trust 仍为固有的 `da1980e9…`。引擎段与最终 ELF 全等，PIC 平移独立核对通过，未解析符号为零，asm 未改。
- 尺寸未超限，但余量比 full-r3 少。主块 78,380→80,628 B，常驻申请量含头 81,916→84,712 B，首装峰值含头 210,108→212,356 B；若已有 UI snapshot，峰值为 214,336 B。安装文件距 65,536 B 上限仅余 3,600 B。见 [M32R 类型尺寸](local/target-layout.json)；这些数值不代表真机连续堆余量。
- 105/106/107 有无 GXTS、首装及残缺安装、移除 DAT 后 IROM 108 冷加载、旧 DAT 优先且浏览零写，指定场景均通过，见 [232 项复跑](local/acceptance-results.json)。已接受的持续 open(-1) F02 仍能复现，不列为新增阻断。删旧 OK 仍是必要前提。

检查程序由本轮冻结的产品、services 和 resident C 重新编译，启用 ASan/UBSan；原生文件、堆、RPC 和 UI 边界为替身。独立 44 项检查中，24 项证明上述反例，四项确认同次开机换单元限制；其余十六项满足断言。另有 1,584 次逐操作故障注入及六个基线。不能把这些程序返回 0 当作候选安全。

未核实的范围：

- 未执行真实机身首次产品容器、完整原生建页/按键流程或候选 M32R 指令。历史容器的主机入口接到当前 C，也没有执行旧引擎机器码。
- 未核实原生 rename、掉电持久化、真机堆碎片和完整调用栈水位。
- 未验证照片颜色。

全部写入仅在本目录；7,193 个冻结输入未变，decisions.tsv 不参与冻结。未重建或重封装候选，未访问相机卡、刷机、安装依赖、使用子代理、commit 或 push。派生字节均在忽略的 `/local/`，交付清单见 [SHA256SUMS](SHA256SUMS)。

复核入口只读保护输入，只向本目录写证据；不要重跑 freeze 覆盖起始记录。

```sh
/usr/bin/python3 -I -B research/review_full_r6/review.py check-delivery
```

完整复跑顺序为 inspect、native、compile、vectors、layout、acceptance、cases、faults-tweak、faults-last、finalize。
