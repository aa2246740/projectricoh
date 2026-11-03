不能采用

原有 18 项反例全部通过，但 P1-01、P1-02、P1-04、P1-05 在其他形态下仍有独立反例。P1-03 的大整数算术问题在本轮所测范围内关闭。正常整机流程的值状态比较通过，尚不足以允许所有调用方默认切换。

| 核查项 | 判定 | 独立证据 |
| --- | --- | --- |
| 上一轮全部反例 | 18/18 通过 | [原反例回执](local/runs/original-replay.json)，包含原包装、六组模型变化及文件、源码失效。 |
| P1-01 完整调度 | 原形态通过；同类问题未关闭 | 新的 StepHook 调度方法在参考批量、参考逐步均得到 r9=31，候选为 0。见 [候选](local/runs/final-dispatch-valid-native.json)、[参考](local/runs/final-dispatch-valid-reference.json)、[逐步](local/runs/final-dispatch-valid-scalar.json)。 |
| P1-02 可变容器关系 | 原形态通过；同类问题未关闭 | 共享 tuple 中的列表被拆开；快照恢复也丢失共享关系。见 [执行反例](local/runs/final-tuple-native.json)、[参考](local/runs/final-tuple-reference.json)、[快照反例](local/runs/final-snapshot-graph-native.json)。 |
| P1-03 大整数算术 | 所测整数域通过 | 原 2**90 时钟及扩展正负边界通过；新 2**80 时钟和绝对截止步正确回退，数据 5a 正常到达。见 [候选](local/runs/final-deadline-native.json)、[参考](local/runs/final-deadline-reference.json)。活动字段类型另见 P2-03。 |
| P1-04 快照身份 | 原形态通过；同类问题未关闭 | SD 模型 BASE 变化后键不变、旧快照被接受，随后候选读 5a、参考读 84。见 [候选](local/runs/final-sdbase-native.json)、[参考](local/runs/final-sdbase-reference.json)。 |
| P1-05 模型绑定 | 原形态通过；同类问题未关闭 | 模型常量类型及观察方法的原位定义变化仍获原生资格。常量反例候选返回 ff、参考出现 DeviceBoundary；观察计数为 0/6。见 [常量候选](local/runs/final-modeltype-native.json)、[参考](local/runs/final-modeltype-reference.json)、[观察候选](local/runs/observer-binding-native.json)、[参考](local/runs/observer-binding-reference.json)。 |
| 实现方扩展用例 | 32+14+4 全部通过 | [独立比较](local/runs/implementation-cases-independent.json)，包括 ready-hold 的内层函数、设备闭包、容器关系和未修改正例。 |
| 四项修正组合 | 16/16 通过 | 136 次状态比较相同，正例均执行原生指令，零 Python 总线及 HLE 回调。见 [组合比较](local/runs/correction-comparison.json)。 |
| 四项修正快照键 | 16 个键、64 次拒绝通过 | 单项配置变化全部拒绝，恢复目标状态不变。见 [键矩阵](local/runs/snapshot-key-matrix.json)。运行期常量仍有 P1-04。 |
| 冷启动到 state 5 检查点 | 通过，原生比例 100% | 35,537,208 步，两点全状态相同。见 [比较](local/runs/cold-standby-comparison.json)。 |
| 首次八行图像设置菜单 | 通过，原生比例 100% | v3.9、g154 Looks18、28mm、四项修正；449,600,040 步，44 个检查点及各段最终状态相同。见 [比较](local/runs/menu-comparison.json)。 |
| 官方恢复确认页 | 通过，原生比例 100% | v3.10 机身、官方 1.51 的 29 个文件、单元关闭、修正关闭；65,975,242 步，三点全状态和 UI 初始化记录相同。见 [候选](local/runs/recovery-r2-native.json)、[参考](local/runs/recovery-r2-reference.json)。 |
| 新整机工作负载 | 通过 | v3.10、g155b release DAT、50mm、声明的 4096 B 设置输入；冷启动至 BOOT_RUN 返回，共六点相同。候选参考模式及原 standby 目录均独立运行。见 [原目录比较](local/runs/g155b-original-comparison.json)。 |
| 现有 input_run 调用方 | 值状态通过；原生比例 0% | 50M 步，完整 CPU、设备、观察及 Flow 状态相同。面板引用和观察记录共享 args 触发回退。见 [实际路径](local/runs/caller-paths.json)。 |
| 当前输入基准 | 1841 项无变化 | 历史 .gitignore 前 1183 B 仍匹配，当前多 199 B。见 [当前输入核对](local/runs/current-inputs-check.json)。 |
| M2b/M2c 全套、重启一次回调、成功完整恢复 | 本轮未完整复跑 | 实现方 22/22、当前 21/21、历史 20/21 和重启一次 Python 停止回调保留为其记录，不计作本轮独立通过。 |

完整状态比较使用 Python 规范哈希，覆盖全部公开寄存器、145 B 架构状态及 LOCK、全部内存区域与属性、各设备状态和历史、全部观察者、面板、控制变量、NAND 页、完整 SD 字节、CPU/MMIO trace、coverage、IO 计数和错误。现有 input_run 另比较 Flow 状态。值哈希不能证明容器共享关系，因此本轮还直接检查对象关系和修改后的可见行为。

P1-01：StepHook 的实际调度方法未获资格验证。

位置为 `native_machine.py:60–113`。候选核对链、字段、工厂内函数及设备绑定，却没有核对 StepHook 类的 `__call__`、`batch_plan`、`batch_skip` 或实例上的同名方法。新反例同时扩展逐步和批量方法，每一步让 r9 加 1，两条参考路径都得到 31；候选仍执行 31 条原生指令，r9 保持 0。

最小修正是冻结并核对这些实际方法、类定义和实例覆盖。关闭条件是构造前后、类和实例上的调度扩展都能正确回退，原有调度链与 16 个修正组合继续获得原生资格。[反例脚本](local/new_cases.py) 的用例名为 `scheduler-class-dispatch`。

P1-02：共享的不可变容器隐藏了可变对象关系，快照也只保存值。

位置为 `state_contract.py:17–57`、`native_machine.py:388` 及 `snapshots.py:173–177`。资格检查只对可变容器的多条入边拒绝。当两个字段共享一个含列表的 tuple，tuple 的两条入边没有触发拒绝，内部列表只被遍历一次。执行 7 步后共享关系丢失；再修改一处并执行 19 步，候选另一处仍为 `[17]`，参考为 `[17,90]`。候选 26 步全部原生执行。

快照恢复在两个后端都复现相同问题。恢复前后值状态哈希相同，共享关系却从真变成假，随后修改也不再传播。最小修正是识别含可变对象的共享 tuple、frozenset 和循环关系，不能保留时回退；状态传输至少拒绝无法保留的内部关系。恢复目标已有的引用也不能被静默替换。关闭条件同时覆盖执行和快照恢复的对象关系及修改行为。脚本为 [new_cases.py](local/new_cases.py) 的 `tuple-state-alias` 和 [snapshot_graph.py](local/snapshot_graph.py)。

P1-04：快照身份未覆盖基础模型方法实际读取的模块常量。

位置为 `models.py:82–101`、`bindings.py:12–36` 和 `snapshots.py:130–151`。函数指纹未覆盖一般全局值，额外常量列表也没有 SD 的 BASE。新反例先保存快照，再将运行期 BASE 加 4。源码、库、修正列表及快照键均未变化，恢复被接受。之后同一条半字读取指令，候选读出 5a，参考读出 84。

最小修正是为每个原生模型显式声明其行为相关常量和辅助函数，把实际值、类型及定义同时用于资格检查和快照身份。关闭条件是 BASE、SECTOR 及其他已声明常量变化时，键变化，并在改变恢复目标前拒绝旧快照。脚本为 [new_cases.py](local/new_cases.py) 的 `snapshot-sd-base`。

P1-05：模型常量类型和观察方法的实际定义未完整绑定。

位置为 `models.py:44–79`。`PAGE_BYTES == 2112` 接受一个数值为 2112 的整数子类，即使该类型改变了比较行为。实际读取函数的代码、默认值和闭包均未改，模型仍标为原生可用。候选执行一条指令并返回 ff；参考保留页几何边界并停止。

另一新反例保留 Observer.entered 的函数对象，原位改变其代码，在原逻辑后增加观察计数。`native_machine.py` 对观察方法只比较函数对象身份，因此仍执行一条原生指令，候选计数为 0，参考为 6。这个形态使用普通整数状态。见 [脚本](local/observer_binding.py) 和表中配对回执。

最小修正是对全部已移植方法核对实际代码、默认值、闭包及行为相关全局值，并对常量要求已审定的具体类型及内容，把这些定义纳入快照身份。关闭条件覆盖观察方法的原位代码变化，以及值相等但行为不同的整数、字节和集合类型，并保留真正四项修正的原生正例。常量脚本为 [new_cases.py](local/new_cases.py) 的 `model-global-type`。同类快照键反例见 [回执](local/runs/final-snaptype-native.json)。

P2-03：活动算术字段仍接受字符串。

`state_contract.py:73` 通用地接受字符串，没有按字段区分活动计数器和被动描述。将 BootSerial.clock 设为字符串 `17`，参考报 TypeError，候选执行 17 步并把时钟改为整数 17。该输入不属于合法整数状态，列为诊断与类型检查问题。最小修正是在执行入口按字段校验，保留快照对被动字符串的无损传输。见 [候选](local/runs/final-textclock-native.json)、[参考](local/runs/final-textclock-reference.json)。

P2-04：正常调用方的引用与观察记录会使提速缩水。

三类指定流程均能维持原生路径，但现有 input_run 在运行前保留 panel.records，并在观察记录中产生共享 args，50M 步全部使用设备参考执行。这些引用约束真实存在。仅调整面板记录的收集时机不能消除后续观察记录的共享关系。最小改进是保留公开容器关系的原位同步，或明确限定并验证记录的使用方式；在此之前保留回退，并按具体调用方记录性能。修正后应重新比较值状态和容器关系，再测占比与速度。见 [调用方驱动](local/caller_probe.py) 与 [交替测速驱动](local/benchmark_caller.py)。

测速结果

每组五对独立新进程，顺序交替，全部配对检查点一致，均实际执行 50M 步。两组内都保留全部样本。

| 流程与口径 | 参考中位秒 | 候选中位秒 | 倍数 | 参考范围秒 | 候选范围秒 | 整机原生比例 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MAIN，原 batch 目录；cpu.run 及同步 | 82.197 | 1.937 | 42.44 | 77.700–90.716 | 1.743–1.977 | 100% |
| 现有 input_run；调用方完整流程 | 142.855 | 66.592 | 2.15 | 114.057–166.081 | 51.220–96.566 | 0% |

MAIN 计时包含资格检查、运行和状态同步，构造及独立状态取证位于计时之外。input_run 计时保留其构造、观察、每 1M 步调用及原有检查点保存，扣除本复审额外添加的最终状态取证时间。两个倍率分别适用于所列流程。input_run 回退后仍使用候选 CPU 库，因此原生步骤为零也可以有部分提速。

主机为 10 逻辑核，CPython 3.9.6，nice 10，其他任务保持运行。MAIN 采样点的一分钟负载为 8.16–16.92。独立 600M 段的两秒采样显示工作落在原生指令、设备调度和值操作中；该采样未计入正式测速。[MAIN 原始五对](local/runs/benchmark-r2.json)、[调用方原始五对](local/runs/benchmark-caller-r2.json)、[采样](local/runs/profile-native.sample.txt)。

新工作负载的 BOOT_RUN 调用发生在 198,917,071 步，199,006,590 步返回，r0=0，回复状态为 -4。这是 release DAT 的返回观察与后端等价性证据，不表示自动配方事务或刷写通过。候选原生指令为 199,006,588 条，两条指令通过本复审的 Python 观察边界执行；相应 HLE 回调计数为进入两次、返回一次。零 Python 总线回调不等于零 Python 执行。

恢复首探 `recovery-confirm-native.json` 的 COMPLETE 仅表示预算执行结束，没有到达确认页，不计正式通过。后续独立的 recovery_workload.py 明确断言目标停点，并保留两边有效回执。所有初始探查与中间结果均保留。

冻结身份与收尾

候选 CPU 库 SHA256 为 `0e4e94f0bbc1637141879d40ec037a83827b2b76ece4c7fa737c54e40f7ece03`，传输扩展为 `315dce38ff9d3ce3985482e6257d5704f89d6acc022d9357bd2aba359d56775b`。交付候选 60 个文件独立核对通过。

新增工作负载机身 SHA256 为 `a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8`，release DAT 为 `1df64437d83629627fd4ba513b2988a014114f22cf5b184f7347f5437073bcfc`。原 standby 库为 `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95`。

收尾重新读取 70,449 个冻结文件，变化为零。research/emulator_fast_r1 清单 5596 项 PASS；research/emulator_fast_r1/fix_r1 清单 5596 项 PASS。见 [初始清单](local/runs/frozen-inputs.json)、[补充清单](local/runs/additional-frozen-inputs.json)、[收尾核对](local/runs/frozen-inputs-final.json) 和 [实现方清单核验](local/runs/supplied-manifests.json)。指定临时目录已删除，删除 96 个临时文件，本复审无残留计算进程。见 [清理回执](local/runs/cleanup.json)。

恢复检查见 [resume-audit.json](local/runs/resume-audit.json)。误停后未发现本复审残留进程、不可解析 JSON 或停在 RUNNING/ERROR 的记录；候选 60 个文件仍匹配交付清单。采样、修正与快照矩阵及正式测速均在恢复后新启动。未把中断结果续跑成正式结论。

本轮没有改 tools/、实现目录或并行任务目录，没有 Git 写操作、联网、存储卡或相机操作。计算任务 nice 10，同时最多两个进程；长菜单按同后端快照拆成 100M 步以内的段，单段超时 1700 秒。其余完整冷启动预计不足 30 分钟。采用步骤、必须回到参考的用法、非 PASS 复核、快照限制和任务切换要求见 [ADOPTION.md](ADOPTION.md)。

成功完整恢复、存储卡、实卡 FAT32、真实 SD、刷写与断电、相机 RTOS/LCD、物理按键和拍摄均未运行。

不能采用；P1 4 个；MAIN 50M 复测 42.44 倍，input_run 复测 2.15 倍；指定临时目录已清理。
