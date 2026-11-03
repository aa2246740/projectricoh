# 把 v3.9 的 DAT 改动移植到 g150

**状态（2026-11-01 更新）：已按本文移植到 g150，结果是 gen 151（`firmware/engine_v59_g151`），机身随之重建为 `71697385…`，见 `research/body_v39/REPORT.md` §10。** g150 复审又出了一个 P1（`research/review_g150/REVIEW.md` §0：未建基线时写 S 遇忙，会把原厂 04 模板当成此前状态写回），g151 同样带着；修复由 g152 做，之后照本文同样的方法把差异移植进 g151。只改 `eng_core.c` 等引擎文件、不动服务库时，机身身份不变；动了服务库就要再重建机身。

下面是移植前写的原文，保留作方法说明。

**原状态：配套 DAT 需要改为基于 g150 重建。** gen 149（`firmware/engine_v58_g149`）以 g139 为基础，因此带着 `research/review_g139/REVIEW.md` 的 P1：参数锁 BUSY 时会接受并确认半套配方。g149 **不要上卡**。修复在 g150（`firmware/engine_v58_g150`，另一个工人负责，本任务没有改它）。g150 同时合入了 MOUNT 改用 50mm 表的改动。

v3.9 机身（`firmware/resident_v39`、`firmware/image_v39`、`firmware/package_v39_body_only`）：**resident 指令预期不变，但身份和机身包必须重建**。原因是 resident 的 build id 覆盖服务库源码，而合并 g150 一定会改服务库，见下文第 2 步。

## 差异文件（相对 `firmware/engine_v56_g139`）

| 文件 | 内容 | 移植 |
|---|---|---|
| `dat-adapter.diff` | `adapter.c`：`BodyState` 和 `ig_body_config`；`grain_snapshot` 不再调 `es_grain_commit`，改存 DAT 自己的 `body.grain`；`core_call` 在服务返回后清颗粒值；`ig_init` 拆出 `init_core`；`ig_menu` 的 Fn 轮换预选；`ig_panel_event` 改为 H09/H10 入口（`body_request`、`body_grain`、`ok_entry_row`、`body_key`）；`ig_panel_abort` 改为 H40/H41 只读入口；`ig_bootstrap` 单次握手（`RV_INIT_DONE`）；主机用的 `ig_host_body*` | 原样应用 |
| `dat-services.diff` | `services.c` 去掉 `r->grain=0` 两处，`engine_services.h` 去掉 `es_grain_commit` | **在 g150 的服务库上语义合并**（见下文第 2 步），保留 op 6 |
| `dat-generation-g149-only.diff` | 代次 139 → 149 的四处 | **不要应用**，g150 用它自己的代次（或下一个新代次） |

另外两步：
1. 把引擎树的 `resident/` 换成 `firmware/resident_v39/resident` 的文件（不含 `build.py`）。
2. **服务库做语义合并，不要整目录替换**。
   - g150 的 `candidate/engine_services/services.c` 是基础，**保留 g150 的全部修复**：settings op 6（只查锁、零写入），以及它在 dispatcher、`used` 表和 `settings()` 里的分支。
   - 在这个基础上只加入 `dat-services.diff` 的两处改动：去掉 op 2 写区里的 `r->grain=0;`，去掉 RPC op 3 里的 `r->grain=0;`。另外在 `engine_services.h` 里去掉 `es_grain_commit`。
   - 合并结果放回 `firmware/resident_v39/engine_services/`，并且与 DAT 树里的副本逐字节相同（`research/body_v39/build_dat.py` 的 `guard()` 会检查）。
   - 因为服务库源码变了，**机身的 build id 会随之改变**：要重建 resident、镜像和两个机身包，重新核对。

   另一种做法是下一轮把服务库移出 resident 的身份输入，这要另做设计，本轮不建议。

## 应用差异的命令

差异文件头是 `engine_v56_g139/...`（旧）和 `engine_v58_g149/...`（新）。在**目标引擎树的根目录**（例如 g150 的副本 `firmware/engine_v58_g150_v39/`，不要直接改 g150 原目录）下用 `-p1` 去掉第一级目录：

```sh
cd <目标引擎树根目录>           # 里面有 candidate/ 和 resident/
patch -p1 --dry-run < <仓库>/research/body_v39/port/dat-adapter.diff
patch -p1 --dry-run < <仓库>/research/body_v39/port/dat-services.diff
```

- 复审在 g150 快照上核对过（`research/review_body_v39/evidence/port.json`、`port.log`）：`dat-adapter.diff` 在严格上下文下能应用；`dat-services.diff` 在零上下文容错时有一处失败，允许 2 行上下文容错（`--fuzz=2`）后能应用。本任务之前在 Scratch 里的 dry-run（`-p0`，工作目录是放着副本的上一级目录）结论相同。
- **补丁命令成功不等于移植正确**。合并后要逐项核对：
  - g150 的 `last_cur` 那一行还在；
  - op 6 仍然零写入并返回；
  - `core_call` 的颗粒清零条件仍是 `op==2`；
  - 代次四处一致。

## 移植时必须重新核对的语义

- **颗粒清零的条件**：`core_call` 里是 `id==RV_SETTINGS&&op==2&&(result==RV_OK||result==RV_VERIFY)`，以及 `id==RV_RPC8&&op==3&&r->detail==1`。
  - g150 新增的 **op 6 只检查锁、什么都不写，不能清颗粒值**，所以条件里保持 `op==2`，不要扩成 `op==2||op==6`。
  - 如果 g150 改变了 op 2 进入写区的条件或返回值，要按“到达写区”重新推导这个条件。
- **主块预算**：gen 149 是 106,032 B，上限 106,124 B，只余 92 B。g150 加了代码和 MOUNT 表的改动，合并后要重新核算；超出时先删 `BodyState` 里的诊断字段（`last_code`、`last_status`、`last_outer`、`h40/h41`），它们只用于诊断。
- **构建**：`research/body_v39/build_dat.py` 用环境变量 `V39_DAT_TREE` 选择树，目前只接受 `firmware/engine_v58_g149` 及其 `variants/`。重建 g150 版时，要么在 g150 自己的任务里照这个脚本改路径和代次（主块开销 7,628 从 resident 的 `target-layout.json` 读取），要么新开一个树。
- **身份的字节门槛**：重建以后，用复审给的 `research/review_body_v39/checks/identity_compare.py` 比较新旧 ELF 和新旧 `ilaunch3`。只允许：
  - `rv_trust` 后 48 B 的身份区变化；只改 `services.c` 而头文件没改时，只有 build 的 32 B 应该变，ABI 的 16 B 不变；
  - 重算后的校验字变化。

  节布局、root/pins、全部跳板地址、替换字和尺寸都必须不变，28 个同伴文件仍逐字节等于官方 ZIP。不能手改 trust 去配旧机身。这个字节门槛不能代替新 DAT 的语义验收。

  ```sh
  /usr/bin/python3 -I -B research/review_body_v39/checks/identity_compare.py \
    --old-elf <c0 版 resident.elf> --new-elf firmware/resident_v39/local/resident/build/resident.elf \
    --old-body <c0f8065d… 的 ilaunch3 副本> --new-body firmware/image_v39/local/ilaunch3 \
    --output <输出 json>
  ```

  重建会覆盖 `firmware/resident_v39/local` 和 `firmware/image_v39/local`，**先把 c0 版的 ELF 和 `ilaunch3` 复制到一个被忽略的目录里**，再重建，再比较。
- **恢复路径的证据**：用 `research/body_v39/tests/recovery_path.py --image <新 ilaunch3> --elf <新 resident.elf> --label <名字> --serial 8=0x5 --confirm-keys 18 24 --budget 500000000` 重跑，再用 `tests/recovery_compare.py` 与官方 1.51 的同条件运行比较；夹具镜像用 `--make-trap <新 ilaunch3> <ignored 路径>` 重新生成。
- **测试**：重跑 `research/body_v39/tests/` 下的 `dat_body.py`（A–D、H，三个单元）、`dat_rotate.py`（用新的测试变体）、`load_routes.py`、`g139_check_v39.py` 和 `regress/`（把包和引擎路径换成新的）。
