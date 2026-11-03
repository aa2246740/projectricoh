#!/usr/bin/python3
"""Build the report from verified result tables and the protocol reference."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent


def write():
    repeated = json.loads((HERE/'evidence/repeatability.json').read_text())
    off = json.loads((HERE/'evidence/model-off-comparison.json').read_text())
    assert repeated['status'] == off['status'] == 'PASS'
    tables = (HERE/'RESULT_TABLES.md').read_text()
    protocol = (HERE/'PROTOCOL.md').read_text().split('\n',2)[2]
    text = r'''到达待机

官方 1.51 和指定 v3.9 都从 MAIN 冷启动到状态 5。50mm、28mm、MOUNT 各跑两次，共 12 次；同一机身、同一单元的状态序列、步数、CPU 寄存器、全部映射内存、设备状态、HSP 数据和批处理统计相同。

这是声明镜头输入下的机身指令执行结果。镜头单元的完整初始化、光学动作和照片流程仍未知。

## 输入和实现

| 输入 | SHA-256 |
| --- | --- |
| 官方 1.51 `ilaunch3` | `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7` |
| `firmware/package_v39_g153/SD_ROOT/ilaunch3` | `8233a1c464b29ba88cfdfce1d083b9bf652586edeb216cacf6f16cf36788b25d` |
| `artifacts/downloads/gxr-151.zip` | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |
| 50mm `jlaunch3` | `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673` |
| 28mm `qlaunch3` | `e487d00b5539aa1e3ca9373829456e00676b37310dc717f0a5bcb5235bac6690` |
| MOUNT `l08firm3` | `0a4dff6d3be9b9a9b56dfcbd98a2df59efcb31f7d4eaca6b0c3fbdb1641fde44` |
| GNU M32R C 库 | `018a6d9731d54b6b27e6729d4a8903a4cab5b8763a0ce92467ad91e02d2d8c95` |

zip 的 29 个成员均先与本地固件比对摘要，结果见 [archive-members.json](evidence/archive-members.json)。每次开启新模型还会重新核对 zip 和所选 MAIN。REA 用于 zip 目录核对，记录见 [rea-archive.json](evidence/rea-archive.json)。M32R 指令窗口由仓库 GNU 工具直接从已核对文件生成，原始字节范围、文件偏移和摘要位于 [static](evidence/static)。

新工具位于 `tools/gxr_emulator_standby`，从 batch 复制。C 核、计时器、RTOS、面板、NAND 和 SD 实现保持原代码。新增 `unit_link.py` 在完整 HSP 请求到达后提供声明回复，`unit_peer.py` 选择型号，`peripherals.py` 把新模型接到现有 HSP 寄存器路径。`outputs.py` 另将 batch 目录列为冻结输出。

模型没有改机身程序、RTOS 队列、任务状态或 UI 状态。收据中的状态变化均为机身 `0x202B0AD8` 写入。镜像在第一条 MAIN 指令前按原节表装入；没有使用启动检查点。

冷启动沿用已有串口输入配置：byte 0 为 `(mask=2, level=0)`，byte 8 初始为 `(15,15)`，原厂输入 11 采样后变为 `(15,7)`，模式拨盘原始键码为 2。三条既有单元启动通知在状态 2 时交付。物理信号名称未确认。

## 冷启动结果

六个组合的序列均为 `0→2→32→5`。以下首次待机步数指机身写入状态 5 的时刻；停止步数指随后首个 UI 分派点 `0x202B1210`。状态 0 的 tick 尚未初始化，其余 tick 读取 `0x200D183C`。模型 tick 未校准为实机毫秒。

''' + tables + r'''
完整统计保留在每份 `*-final-a.json` 和 `*-final-b.json`。上表汇总首次状态 5 分派点的计数；所有运行均为 fast、batch 开启、nice 10、超时 7,200 秒。`rte-in-c` 均为 0，沿用已批准 C 核的行为。本轮未作硬件速度或毫秒耗时判断。

[repeatability.json](evidence/repeatability.json) 逐项比较了 12 份收据。比较器同时核对每次运行的 Python 源、C 库和镜像摘要，绑定到 [final-tool-sources.json](evidence/final-tool-sources.json)。

## 关闭模型的结果

最终源版本分别用原 batch 和新副本重跑两项门槛。比较结果见 [model-off-comparison.json](evidence/model-off-comparison.json)。

| 路线 | 两版结果 | 比较范围 |
| --- | --- | --- |
| 既有恢复检查 | 第 65,975,242 步到 `0x2036C9E4` 更新确认页，替换入口及 resident 执行为 0。 | CPU、全部 RAM、设备状态、原厂里程碑、NAND 命令、虚拟介质内容和批处理统计相同。 |
| `v310_window` 既有冷启动收据 | 50,000,000 步，`state=2`、PC=`0x2006F1FC`。 | 完整状态摘要相同，状态、原始观察、DMA 长度、启动通知和批处理统计也与旧收据逐项一致。 |

恢复路线直接调用 `research/body_v39/tests/recovery_path.py` 的函数。适配器只更换工具导入、输出位置和 scratch 介质路径，并移除该介质的 Git 忽略检查。64 MiB FAT16 虚拟介质内容摘要仍为 `2a986483f0b74a0b003d8b4945a2bc6743cf0b33d41edf28c65ebc4329204866`。设备状态比较仅将两次运行的主机介质路径统一为同一标记，保留介质内容摘要、读写错误和全部其他字段。

旧冷启动的临时镜像已被上轮清理。本轮用原 ELF 和原替换清单在指定 scratch 重建，得到原收据相同的 `71697385bf69283ed6349f8829884e8768ff33be2869f940188b668d782e31fa`，再执行原 `cold_check.py`。两版都重现了原来的未待机结果，适配器保留原断言记录。

## 单元消息和机身条件

''' + protocol + r'''
## 功能检查与 ADJ

[model-checks.json](evidence/model-checks.json) 的 10 项检查通过，覆盖完整请求分片、回复字节、不完整请求不回复、未知业务消息停止、未知配置停止、同步返回及序号、单向请求无回复、默认设备未启用模型，以及公开 CPU 快照恢复后的序号连续性。它们验证声明的设备边界；不代表单元完整程序已运行。

官方 50mm 在首次待机后继续两百万步，再通过 GPIO 按下和释放 ADJ。Task 6 消费事件 43，机身在第 43,201,587 步写入状态 56，第 43,201,673 步以 event 1 调用 `0x202BA5C8`。第 51,836,659 步，已有 NAND 模型报告页尺寸限制，PC 为 `0x201FE12C`。完整记录见 [official-adj-r8.json](evidence/official-adj-r8.json)。构造函数未证明返回，完整菜单显示和关闭仍未验收。

初轮未声明的 slot 47、slot 38 和 slot 28 停点均已保留。每次补充前先核对静态代码；未将未知返回统一设为成功。ADJ 后段的 NAND 范围未扩展。

## 使用与复核

运行命令、参数和 Python 接口见 [工具 README](../../tools/gxr_emulator_standby/README.md)。新运行器显式开启批处理，示例保留 `GXR_EMULATOR_BATCH=1` 的既有设置。`GXR_UNIT_MODEL` 默认为 `off`，可选择 `50mm`、`28mm`、`mount`。`--unit-model` 优先于环境变量。输出目录必须用 `--output-dir` 显式给出，每次使用新的 `--name`。

本轮 `TMPDIR` 为 `/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-standby-r1/`。所有运行以 `nice -n 10` 在前台执行，最多三个运行进程，无后台启动或定时等待。新运行器超时为 7,200 秒；既有冷启动脚本保留 1,800 秒。两者均高于对应历史运行耗时的三倍。指令执行使用同一 GNU M32R C 库，没有 host-harness 运行。

在项目根目录复核保留收据和摘要：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-standby-r1/ \
nice -n 10 /usr/bin/python3 -I -B research/emulator_standby/collect.py pairs
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-standby-r1/ \
nice -n 10 /usr/bin/python3 -I -B research/emulator_standby/collect.py compatibility
shasum -a 256 -c research/emulator_standby/SHA256SUMS
```

实际重新冷启动使用 README 的命令，并换一个未使用的收据名。关闭回归可运行 `compatibility.py --case window` 或 `--case recovery`，分别选择 `--emulator batch` 和 `--emulator standby`，并给出新的 `--name`。

## 未闭合项

- 实机的 `32→63→32` 分支尚未重现。当前零输入使 `0x2037F3B1=0`，只能证明本文记录的待机路线。
- 单元侧如何产生就绪值、能力、校准和光学动态值仍未知。`0x1F03→0x1003` 照片链未建模。
- ADJ 已进入状态 56 并调用原厂构造函数，后续 NAND 页尺寸限制、构造返回、完整显示和关闭仍待验证。
- 开启模型后的受限 pickle 读取路径未扩展或验收。功能检查中的 CPU 快照恢复不等于现有检查点 CLI 的续跑验收。
- 附加的 M2d 旧冷启动收据重放比历史步数提前 3,000 步。两套当前工具均在 30,721,580 步到相同接收点，完整状态相同；旧收据的源和 C 库摘要不同，这个历史差异尚未归因。原始记录保存在 `cold-batch-cold-r1.json` 与 `cold-standby-cold-r1.json`。

原两套模拟器及冻结输入的最终摘要核对、临时文件和进程清理记录见 [PROGRESS.md](PROGRESS.md) 与 [cleanup.json](evidence/cleanup.json)。本轮未访问实体介质，未执行设备动作，未写 Git，也未改其他工作区。
'''
    (HERE/'REPORT.md').write_text(text)
    print('REPORT.md written')


if __name__ == '__main__':
    write()
