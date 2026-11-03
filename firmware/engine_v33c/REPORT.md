已停止，不可以上卡。现有冻结入口没有可供引擎在首次建页 stores 之后、首帧之前重设光标的回调。R6-01 产品断言仍失败，触发任务规定的停止条件。未构建 generation 109，未生成 full-r7、card_update 或新容器 SHA-256。R6-02 和记忆写入策略均未改。

本目录从 engine_v33b 复制。containers/product/ 和 engine_services/ 逐文件与 full-r6 相同，R4-01、R4-02、可见行、GXLS 格式和数据均保留。

已核实的原生顺序如下。

1. 0x202BA76C 调用 0x20287080。H01 0x2028709C 调用引擎恢复配方，containers/product/adapter.c:206 同步调 UI_LIST，engine_services/services.c:189-190 已把 native cursor 和 snapshot state[9]/[10] 写成配方槽。
2. 栈顶仍为父页 tag 32。冻结 firmware/resident_v32/resident/hooks.c:13,64 的 owned() 为假，H01 不采用 skip；H02 0x202870A8 也不接管。
3. 0x20287104 把 S mode 3 映射为 r8=4。0x20287158/164 分别向 0x2022F725/726 写 r8，覆盖步骤 1。mode 1 则映射为 2。
4. 0x202871A4 才调用 0x201C07E0 创建 tag 33，state 参数仍是固定地址 0x2022F71C。0x201C0878/888/890 写 tag、state 和计数，随后开始绘制。
5. H05 0x201FEBE4 晚于 stores，但冻结 hooks.c:35-37 只替换详情指针和 skip 地址，不进入引擎、不调 UI_LIST/VIEW、不写 cursor。H06 是 Fn2，H07 是确认或退出，H08 是选择事件，均晚于首帧。

UI_LIST/VIEW 是引擎主动调用的同步服务，没有登记建页完成回调。engine_services/services.c:201-219 的 UI_VIEW 只改当前栈顶 state，不能改变后来 push 的固定参数。提前把父页 tag 32 改成 33 会改变原生栈，不满足真实入口要求。

[native_evidence.py](native_evidence.py) 从官方字节重算 11 种枚举，与审查轨迹全等。切片与批准机身的差异仅为既有 hook。证据见 [建页](local/logs/native-build.log)、[push](local/logs/native-push.log)、[H05](local/logs/native-details.log)、[区域摘要](local/native-regions.json) 和 [枚举轨迹](local/native-enum-traces.json)。固定地址扫描找到上述调用点，未证明穷尽所有间接入口。

后续有两个超出本任务权限的选择，均需重新批准 resident 和机身候选，尚未实现或验收。

- 修改 resident 的 H01/H02，让经过验证的首次建页也能接管并跳过七项枚举，保留真实父页。
- 增加建页完成回调，或修改 H05，使它在首次绘制前恢复 cursor，同时核对后续光标移动，避免每次重绘都拉回旧行。

测试共 38 个不同场景，复跑两轮，共 76 次 ASan/UBSan 主机运行。每轮包括 8 个 R6-01 原反例、16 个 R6-02 原反例、4 个写频率观察和 10 个新的首建断言。前 24 例仍证明缺陷，不能把其返回 0 当作产品通过。

host_boundary.c:14 在 H01 前只放 tag 32。两镜头分别测试无记忆，以及记忆 01、03、05、08。两轮的 10 个首建断言均失败；host_boundary.c:33-37 核对 H05 没有再次进入引擎，也没有恢复 cursor。snapshot 内的正确 cursor 没有替代 native state。03 仍高亮 04，无记忆仍从默认 01 跳到 02，见 [03 日志](local/logs/boundary-first-build-0-1-3.log)、[无记忆日志](local/logs/boundary-first-build-2-1-0.log)。[逐例结果](local/boundary-results.json) 明确标记 product_assertions_pass=false，check_boundary.py 返回 1。

R6-02 仍可复现。engine_services/services.c:83,92,137 的 GXLS 错误仍污染 RF_UNCERTAIN。四个写频率场景仍观测到 01→08→01 产生 15 次 TEMP 创建和 15 次 rename。每会话最多写一次的策略尚未实施，forced close 写入安全性未验收。

停止后未启动 2,088 组全套和 1,584 次逐操作注入，也未验收全部原生入口、首帧 OK、所有故障后续动作、forced close 或 105–108 升级矩阵。

| 项目，B | full-r6 | full-r7 |
| --- | ---: | --- |
| 容器 / 65,536 上限余量 | 61,936 / 3,600 | 未构建 |
| engine / BSS | 52,912 / 11,188 | 未构建 |
| 主块 / 会话 request | 80,628 / 1,460 | 未测 |
| loader / UI snapshot request | 608 / 1,968 | 未测 |
| 正常保留量，含头 | 84,712 | 未测 |
| 首装，含头 / 已有 UI snapshot | 212,356 / 214,336 | 未测 |

已实算 full-r6 SHA-256 为 8ae376fe5edd4a2f78dbf3f9db95a70313f59d136f21ca300b4eb657b9e264d6。批准机身仍为 05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c，resident ELF 仍为 f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58。

本轮新增 native_evidence.py、host_boundary.c、check_boundary.py、finalize_stop.py，只供阻断复现。common.py:52 把写入限制到本目录；build.py:54、finalize.py:31 阻断复制来的 generation 108 构建和暂存入口，避免误发。完整读入 1,944 份审查日志，摘要见 [日志索引](local/review-log-read.json)。11,405 个冻结输入未变，decisions.tsv 排除在外。SHA256SUMS 覆盖本目录，.gitignore 为 /local/，理光派生字节全部在 local。

复跑入口如下，第二条返回 1 表示产品断言仍失败。

```sh
/usr/bin/python3 -I -B firmware/engine_v33c/native_evidence.py
/usr/bin/python3 -I -B firmware/engine_v33c/check_boundary.py
/usr/bin/python3 -I -B firmware/engine_v33c/finalize_stop.py
/usr/bin/python3 -I -B firmware/engine_v33c/finalize_stop.py --check
```

主机运行真实产品、services 和 resident C，枚举读取官方字节，cursor stores 和 push 按官方指令投影。未执行完整原生 UI 或候选 M32R 指令，实体相机行为未知。写入仅在本目录，未访问相机卡、刷机、安装依赖、启动子代理、sleep、轮询、commit 或 push。
