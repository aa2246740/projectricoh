不能上卡

g152 测试卡离线复审，2026-11-01。发现 1 项阻断 P1：未建基线时的快照会跨退出保留，实际单元状态改变后仍能被用作补偿来源。g150 §0 的直接复现已经修好，但修法尚未覆盖快照失效后的下一次事务。

结论仅针对用户已有 v3.8 机身、只更换 DAT 的测试卡门槛。没有上机、读写存储卡、刷机、联网、Git 写操作或子代理。真实相机的关机恢复、照片保存和 RTOS 时序不属于本轮已验证结果。

## 1. 阻断 P1-01：首次拒绝后，旧快照被再次当作实际此前状态

主位置为 `firmware/engine_v60_g152/candidate/containers/product/src/firmware/engine/core/eng_core.c:396`。关联位置为同文件 `:345`、`:354`、`:378`、`:639`、`:758`、`:761`、`:769`、`:816`。

首次应用通过两遍读取后，`:378` 把 `live_verified` 设为 1。若 op 6 遇忙，这次选择在首次 W 前被拒；没有提交配方，`baseline`、`committed` 仍为 0，但 `live_verified` 保留为 1。退出时的重查可以清掉 `recheck`。此后菜单关闭期间实际单元行改变，重开在 `:761` 因 `!committed && !recheck` 返回；下一次应用又在 `:396` 跳过捕获。写 S 才遇忙时，`:357` 全量写回旧 `g.live`，`:359` 清 uncertainty，最后普通拒绝。

独立用例只把单元九行/T、S 和锁作为明确的模型输入；方向键、OK、退出和重开均走原生入口，没有预置 UI 或引擎变量。

1. 初始为合法 02 九行、T=2、S 模式 4，未建基线。
2. 持锁并按 DOWN。g152 捕获 02 后普通拒绝，W=0；OK 退出到原厂 7 行。
3. 菜单关闭期间，把实际单元改为另一套合法九行，保持 resident epochs 与 S 不变，然后释放锁并重开。这里的行变化是模型输入；没有声称真机发生频率或具体物理触发已测。`eng_core.c:756` 至 `:757` 自身也说明，原生拍摄能在不改变 resident epoch 时恢复单元行。
4. 再选 05，op 6 返回 0，op 2 入口才取锁并返回 -2。
5. g152 写回第一次的 02，既非本次实际此前状态，也非 05；S 零写、W=506、没有 ERR，退出重开仍保持这个第三状态。

MOUNT、50mm 的实际此前状态为 08 时均复现。证据为 `runtime/evidence/after-refusal-observation-{mount,50mm}.json`；正常合同断言的失败保留在 `runs/after-refusal-*.log` 与对应运行 JSON，未改记通过。

MOUNT 另以原厂 04 作为退出后的实际状态复现，仍回写旧 02。第一次退出后的实测字段为 `baseline=0`、`committed=0`、`live_verified=1`、`uncertain=0`、`snapshot_fault=0`。按键前、按键后和重开的完整九行/T 各保存为 505 B，完整 S 各保存为 4,096 B；见 `runtime/evidence/after-refusal-4-mount-observation.json` 与同名前缀的 `.bin` 文件。

三条复现直接执行测试 DAT。发布 DAT 的代码、映射、内置行池、R3 和效果区与测试 DAT 相同，本问题不依赖三个用户条目；发布包为静态同因判断，未另执行这三条原生用例。

最小修正方向是给未提交快照明确的有效期。尚未建立可信配方基线时，每次新事务都须重新读取并验证实际九行/T，或在退出/重开等会失效的边界撤销快照资格。仅保留“曾经验证过”的布尔值不足以证明它仍是本次事务的此前状态。

关闭条件是复跑本目录的两次事务用例，分别以原厂 04 和合法非原厂行作为变化后的状态；写 S 才遇忙后必须保留本次真实此前九行/T 和完整 S，或明确进入 ERR 并保留 uncertainty。还须保留首轮非原厂起点和快照不稳定时零写入的通过结果。

复现入口如下。当前合同断言失败时返回码为 1，不能计作固件通过。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
nice -n 10 sandbox-exec -f research/review_g152/offline.sb \
  /usr/bin/python3 -I -B research/review_g152/run.py \
  independent_cases after-refusal --unit mount
```

把子命令改为 `independent_cases after-refusal-stock --unit mount` 可复跑原厂 04 版本。`verify_witness.py` 用另一份字节读取器从最终 DAT 解出 02/04/05/08，再比较保存的单元字节，已确认按键前是 04，按键后和重开都是 02，全部 4,096 B S 不变；见 `witness_check.json`。

## 2. 产物和证据层

| 对象 | 独立核对 |
| --- | --- |
| 发布 DAT | `9180745af84593c24e62da5abe595d8ba6a6a8b078d7d1a6cd89fdbfc39b945a`，90,156 B。 |
| 测试 DAT | `88ca8b46c5f4f1590adfa613828ba1bfe808b23779111651d0a2ebb69c489e2b`，90,156 B。 |
| 冻结清单 | 开始时 `research/looks_g152/SHA256SUMS` 的 559 项全部匹配；清单自身为 `52739502ac39a1a13ac2f6b5e02b7d73468f79f55883fdff68d3aaac0d8c7395`。 |
| 旧候选封存 | 按其清单独立核对 354 项；144 条锁忙回执均为 PASS，并绑定旧测试 DAT `eb04787d…`。它们没有算作最终候选的新执行结果。 |
| 机身 | 两包各 29 个非 DAT 文件与 g150 逐字节一致。 |
| 链接身份 | 两份最终 DAT 的代码段均与最终 ELF 的 `.engine` 逐字节相同。 |
| 尺寸 | 代码 63,896 B，BSS 9,252 B，主请求 106,912 B；距本次 107,612 B 限制余 700 B。 |

`static_checks.json`、`input_hashes_before.json` 保存明细。M32R 对象独立编译得到 session 1,104 B、固定开销 7,504 B、引用 56 B，并核对本轮主机读取的关键结构偏移。

- 静态与最终字节检查证明包身份、结构、表和代码的对应关系。
- C 模块比较证明算法及格式层；它没有替代 M32R 执行。
- 菜单、RPC、事务和写入检查均使用 `tools/native_harness/python_backend.py` 执行最终 M32R；锁、单元传输、文件读取和图形叶子仍是主机模型。
- 本轮没有照片、LCD、真实单元固件、物理断电或存储卡验收。

本轮原生复跑以 MOUNT 为主，50mm 用于原 §0 和十效果。28mm 没有另跑原生整组；其包内行、R3 格式、整数等价与 C/Python 对照在三单元检查内。

## 3. 七项重点检查

下文 `adapter.c`、`fx_pool.c`、`kv2/` 相对 `firmware/engine_v60_g152/candidate/containers/product/`；`semantic.c` 位于其 `src/firmware/card_container_v2/`。

### 3.1 kv2 等价回执

独立复跑 `equivalence`、`control_parity`，全部通过。回执分别在 `runtime/evidence/kv_equivalence.json` 和 `runtime/evidence/control_parity.json`，均绑定上述最终 DAT。

覆盖 3×8×10×65,536=15,728,640 个 int16 单控制输入；另有 11 个 API 边界、201 个点尾拒绝、3,430 个文本值、7,056 个两两端点组合。隐藏控制只接受默认值，拒绝不改预置输出。完整点序列与元数据一致，未改变的请求函数按控制分别写入互不重叠的字段，支持任意合法向量的请求组合性结论。

最终结果比较覆盖 15,050 个完整 552 B，包含九行、T、14 行与 CRC；“请求相同但参考基底字节变化”的对照能检出不等价。C/Python 独立整数对照 8,521 次通过。以上没有把 52 B 请求相同直接当作最终写入字节相同。

50mm 十个效果另经最终 M32R 原生菜单逐项应用，逐字比较九行/T、完整 S 和运行中 552 B，全部通过。保存效果状态的 S 后建立新启动实例，菜单为原厂 04、效果号 0、单元 W=0，记录为 40 个零。见 `runtime/evidence/apply-50mm.json`；此处仅为模型冷启动恢复。

受控的合法零 Y 基底另经最终 M32R 检查计算拒绝。实际运算返回 −2，S/单元 W 为零，live/staging 与九行/T 均不变，见 `runtime/evidence/knobs-refusal-50mm.json`。该组验证拒绝边界，不是把生产效果的全部十维组合宣称为不会返回 −2。

### 3.2 R3 与效果区拒收

形式解析独立复跑通过：正常包三单元接受，31 个格式变体拒收，93 个允许名字字符接受，61,250 个窗口组合通过。详见 `runtime/evidence/format_checks.json`。

R3 有效区是 `[3664,7902)`，物理块长 7,904 B；尾部两个字节为零，引用区间并集覆盖有效区。`kv2/kv_data.c:155` 至 `:179` 另查逻辑尾、对齐长度和覆盖，R2 标记拒收。效果区先按实际长度核对公式，再读 CRC、索引及行结构，见 `fx_pool.c:4`、`:45`。

`adapter.c:526` 的 R3 校验早于 `:538` 的能力返回。效果校验经 `eng_init` / `eng_data_accept` / `gxr2_semantic_validate` 执行，见 `semantic.c:192`，也早于能力返回和首次配方写入。

原生九组拒收独立复跑全部通过，均回到原厂 7 行、S 零写、单元 W 零写；加载期间没有设置接受标志，`ig_init` 返回的写能力为 0，session 只保留 `0x7fff` 读取能力。另补头 CRC 有效、区内容 CRC 单独失败的原生组，也得到相同结果。见 `runtime/evidence/own-reject-*-mount.json`、`own-reject-mount-rows.json` 与 `area-crc-isolation.json`。原九组中的区 CRC 夹具隔离不足，见 P2-01。

### 3.3 未建基线修法

原 g150 late 用例在 MOUNT、50mm 都独立复跑通过；原“应出现第三状态”的断言在原位置失败，新的正常合同核对保留了实际 02 九行/T，op 6=0、op 2=-2、W=506、S 零写，退出重开仍一致。见 `runtime/evidence/unverified-{unit}-original-late.json`。

另构造两种竞态：第一次完整读取结束后，MOUNT 改 T，50mm 改为另一套合法九行。两者都在 W 前进入 ERR，`live_verified=0`、`snapshot_fault=1`、`uncertain=1`；三种退出重开后均保留错误、S 和单元零写入。见 `runtime/evidence/own-snapshot-race-*.json`。

这些通过只证明捕获当次的处理。第 1 节证明跨退出保存的快照仍会过期，因此不能认定 §0 已全部关闭。

另独立复跑 MOUNT 的实际此前 T=0、late-BUSY 用例，九行/T 和完整 S 在按键、退出和重开后都保留，见 `runtime/evidence/t0-late-mount.json`。它直接覆盖最终候选将观测行校验与目标 T/C/D 关系分开的改动；没有仅凭正常 T=2 矩阵推断该分支安全。

MOUNT 行格式无效的快照专组也独立通过：ERR、`snapshot_fault=1`、`uncertain=1`，S/W 为零；OK、半按、MENU 退出重开均保留错误和完整 S。见 `runtime/evidence/unverified-mount-effect-other-base-capture-invalid-ok.json`。

### 3.4 四种切换、身份与锁忙范围

独立核对最终候选 48 条回执，均绑定最终测试 DAT；每条的此前九行、T、完整 S 摘要与引用摘要在按键、退出和重开后相同。旧 144 项与最终 48 项也分别核对了完整组合集合，没有仅以条数代替覆盖。完整 144 项留给发布复审，本轮不以此延期作为缺陷。

旧候选到最终候选只有 `capture_previous` 中 `fx_row_valid` 的 flags 参数从 `g.live[1]` 改为 0，另加解释注释；其余来源/头文件摘要不变，见 `candidate-change.diff` 和 `static_checks.json`。该函数仅在 `!live_verified` 时运行，正常已验证来源的四种切换矩阵不会执行这处改动。旧 144 项加最终 48 项可以支持这个范围内的锁忙结论；不能扩展成未建基线状态的完整保证。P1-01 正好属于两套矩阵均未覆盖的快照寿命条件，不是未重跑 144 项本身的问题。

MOUNT 四种切换的独立原生身份复跑全部通过，耗时 887.691 秒；比较完整 56 B 当前/确认引用、两套控制值和确认标志。迟到 BUSY 后身份与此前相同；释放锁后下一次有效选择，九行/T、完整 552 B、S 和效果 CRC 都与目标一致。见 `runtime/evidence/identities-mount.json`。

### 3.5 8 行与文本

M32R 对象独立编译确认 `UvState.text` 与 `KvUiFrame.text` 都是 112 B，即各 8×14 B，每行 14 B；引用仍为 56 B。`fx_name` 限长复制 12 B 后补 NUL，见 `fx_pool.c:96`；adapter 先清零 14 B，再按最多 13 个可见字节交给文本服务，见 `adapter.c:330` 至 `:339`。

窗口形式检查覆盖 1 至 49 个逻辑行的所有光标和旧 top。

49 行的 MOUNT 原生检查已通过，运行器计时 408.669 秒，见 `runs` 对应回执和 `runtime/evidence/ui-rows49-mount.json`；覆盖首尾环回、跨 8 行窗口移动、最后一行标题、返回与重开，所有发布帧保持 8 行。

MOUNT 空列表原生检查通过，UP/DOWN 均停在 Back 行，九行/T 与完整 S 不变。12 字符名字专组直接读取两套 8×14 B 缓冲，并逐次检查文本服务的源长度和末尾字节；最长 13 个可见字节，随后就是 NUL，标题也为 13 个可见字符。见 `runtime/evidence/ui-empty-mount.json`、`own-text12-mount-rows.json`。

MOUNT 原生传输失败的错误页检查通过，显示 ERR，所有发布帧仍为 8 行，见 `runtime/evidence/ui-error-mount.json`。没有把这条持续通信失败用例解释为单元 RAM 已完整恢复。

### 3.6 黑白效果

最终两包的 Tri-X 第三效果 C080 为 96 B 全零，与三单元内置 03 的对应行一致；不是依据效果名字判定。十个效果均独立核对 A14/B14=A5/B5 和逐行 CRC。

MOUNT 原生实际写入已独立通过：九行/T 与完整 552 B 对得上最终 DAT，读出的实际 C080 是 96 B 零。直接解码其 24 对系数，对相邻扇区权重、正负色度和亮度用有理数运算检查 98,688 个样本，均严格 R=G=B；零色度的结论不依赖所选亮度或拟合预测函数。见 `runtime/evidence/own-bw-mount-rows.json`。这是编码与写入路径证明，不是实拍或单元 ISP 测量。

### 3.7 MOUNT

最终 MOUNT 八个内置条目与 g150 完整 552 B 相同，原厂 04 保留自己的行与 pin。槽 1、2、3、5、7、8 的九行与 50mm 相同；槽 6 沿用已披露的 MOUNT safe 差异：不带 50mm 的 T1，C/D 保留 MOUNT 原厂值。效果区由三个单元共享同一套 50mm 拟合的编码行，没有把 50mm 的原厂 04 复制成 MOUNT 原厂 04。这不构成 MOUNT 独立画质标定。

## 4. P2 与继承边界

P2-01，验收夹具没有单独检验区 CRC。位置为 `research/looks_g152/format_checks.py:86`、`:95` 至 `:96`。`fx-area-crc` 只改区 CRC 字段后重算 DAT 外层校验，没有重算效果头 CRC；因为区 CRC 字段也在头 CRC 覆盖范围内，该组的头、区两个 CRC 同时失败，头校验足以使它拒收。复现入口为 `independent_cases isolated-area --unit mount`，`area-crc-isolation.json` 保留两个 CRC 的独立比较。新夹具改一个合法名字字节、保持头 CRC 有效，并确认仅修复 CRC 后整块完全有效；最终 M32R 对这个单一区 CRC 错误仍零写拒收。因此这不是产品阻断，但下一轮应替换正式夹具，使区 CRC 检查缺失时测试能够失败。

1. 九个彩色效果的扇区模型限制已在实现报告披露；电脑相似度是相对 04 的误差改善，不是实拍还原率。本轮未重跑拟合或扩展图像质量结论。
2. 真实 LCD 截字、RPC/RTOS 时序、ISO100 单元分支、`rpc_ready=0` 首开及失归属时 S 待写边界仍按原报告留给发布复审。这里没有用主机通过替代这些验收。
3. 持续通信错误可能留下部分单元 RAM，但须显示 ERR 并保留 uncertainty；失归属的四个清理字段属于已披露继承边界，没有作为本次新增阻断理由。

## 5. 执行、耗时与复跑

本轮原生与算法测试均以 `nice -n 10` 经 `offline.sb` 执行，网络与写入路径由系统策略限制；最多两个测试进程，按批前台等待，两项都退出后才换批。输出路径重绑定在 `run.py` 内，保留原检查源码及被执行文本摘要，不修改被审源码或 g150 目录。没有给原生作业加短墙钟终止器，解释步数上限沿用原夹具；编译调用的 2,400 秒期限超过其历史用时的三倍。

验证区间为 2026-11-01 19:16:54 至 20:24:05，Asia/Taipei；墙钟 67 分 11.120 秒。28 个运行器作业累计 100 分 19.272 秒，因两个作业并行而长于墙钟。22 项 PASS；3 项 FAIL 是 P1-01 的三条合同失败，另 3 项是下述复审夹具初版错误。独立字节读取器另确认 P1。完整逐项命令、结果和耗时见 `RUNS.md` 与 `execution_summary.json`；报告整理和封存时间不计入这个验证区间。

末次核对 559 项清单全部匹配，另核对实现者冻结的 414 项旧输入与 4 项设计/复审输入；g150 原复现脚本与实现目录中的逐字副本仍相同。见 `input_hashes_after.json`。进程清点为 0 个存活测试，最大并发按全部作业起止记录核对为 2，nice 全部为 10。外置卷再次确认为可写 APFS、UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，见 `mount-final.txt`。仅删除本轮自建 Scratch 和解码缓存，删除清单见 `cleanup.json`。输出由本目录 `SHA256SUMS` 封存，路径相对仓库根。

共同入口如下，将模块与参数替换为各条目所列值即可；会重新产生指定 Scratch 和本复审目录中的运行证据。

```sh
cd /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh
nice -n 10 sandbox-exec -f research/review_g152/offline.sb \
  /usr/bin/python3 -I -B research/review_g152/run.py equivalence
```

初次静态检查对 MOUNT 06 使用了过宽的“全部九行等于 50mm”断言，按已披露的 safe/T1 差异修正复审脚本后通过；原失败保留为 `runs/static-initial.log`。这属于复审夹具修正，没有改产品或原回执。

原生拒收观测器初版在 `rv_reset` 尚未清完内存时检查 `RF_PUBLISHED`，因未初始化的标志字节而停止。修正为从真实 `rv_load` 入口开始判定发布标志；原失败保留为 `runs/reject-initial-observer.log`，没有计为产品缺陷或通过项。

独立区 CRC 夹具初版把不可变 bytes 交给原有原地 CRC 修正函数，尚未运行原生构造器就因类型不符停止；改用局部 bytearray 后复跑通过。原失败保留为 `runs/isolated-area-initial.log`。以上三类夹具错误都保留原失败，没有改写成首轮通过。

封存脚本初版在 sandbox 内调用 ps 被 macOS 拒绝，见 `seal-initial-error.txt`。进程清点改为本轮一直使用的独立只读 ps，过滤后只保存本任务记录；摘要核对、清理及 SHA 封存仍在同一 `offline.sb` 下执行。这不是固件运行失败。
