"""Write the Chinese review handoff only after acceptance succeeds."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope


def main():
    here = scope.HERE
    v = json.loads((here / 'verification.json').read_text())
    assert v['status'] == 'PASS_HOST_READY_FOR_REVIEW'
    elapsed = (datetime.now(timezone.utc) - datetime(2026, 10, 29, 1, 6, 11, tzinfo=timezone.utc)).total_seconds()
    allowed = json.loads((here / 'local/time-limit.json').read_text())['allowed_minutes']
    assert elapsed <= allowed * 60
    text = f'''可以交复审

# diag-v21-raw-r1

H 页 BAD 的第 2 至 7 行现显示原始 32 位值；未读取的动态头字段显示 `--------`。第 1 行和第 8 行的格式保持原样。成功 H 页、A/B/C/D/F/E、切页和原有校验条件均沿用 diag v2。字段定义及 2026-10-29 真机旧读数的判读见 [READINGS.md](READINGS.md)。

最终包为 `firmware/package_v36_diag21/local/SD_ROOT`，共 30 个文件，generation 132。DAT 为 {v['dat_bytes']:,} B，SHA256：

```text
{v['dat_sha256']}
```

## 静态已证

新增读取只在 BAD 时发生。R 读取两个固定初始化字段 `0x200C0DC0/0x200C0DC4`，并在链根四字节对齐、完整 12 B 头位于 `[0x20000000,0x20800000)` 时读取首字。P/F 使用相同的完整头检查，再读取偏移 0、4、8 的三个原始字。完整头的最高有效起点是 `207FFFF4`。N/M/S 直接使用原读取器保存的字段。

新增代码不读取 MMIO，不写原生堆头、槽或其他原生内存。诊断原有 UI 和 loader 行为仍按原合同工作。P/F 的诊断字在识别失败后读取，不保证与触发失败的那次读取来自同一个瞬间。

相对 diag v2 的源码差异见 [source-v2.diff](source-v2.diff)，只有五个文件：STATUS、构建脚本、构建路径检查、diag.c 版本字符串及 diag_heap.h。50 字段表和旧页排版表的编译字节保持一致。没有更改容量、哨兵、块头、归属或槽分类条件。

每份快照从 12,432 B 增至 12,460 B，原字段和块数组的偏移保持原样，末尾新增六个诊断字及有效位。两份合计增加 56 B。BSS 为 {v['bss_bytes']:,} B，代码为 {v['code_bytes']:,} B。主请求为 `1104 + align4(22020 + 26372) + 6144 + 256 = 55896 B`，原生跨度为 55,908 B。

## 主机已证

| 检查 | 结果 |
| --- | --- |
| 原有合成堆 | 43 个情形全部完成，保存实际新版行值；138,760 次行格式检查通过。 |
| 新增原始行值 | 24 个情形，逐行比对固定期望，覆盖 R/P/F/N/M/S、链根不等于 base、容量超限、哨兵非零、完整状态字和 RAM 边界。 |
| 最终 DAT 的 BAD 行 | 9 个指令模型情形，直接调用最终 DAT 的 dh_bad / dh_bad_block 并核对 H 页显示，覆盖六条路径；读取限于 RAM，CPU 数据写入限于诊断 BSS 和调用栈，原生服务调用为零。完整采样器及失败分类另由 43+24 个 C 情形覆盖。 |
| 三单元切页 | 50mm、28mm、MOUNT，各两次打开及 ABCDFHA，共 42 次页观察；每次打开一次 capture，DISP 不采样。 |
| 旧功能及复审 | 旧 411 场景和 review_diag 套件完成，共 874 条唯一记录；20 个矩阵分组与 14 个补充分组均返回 0。 |
| review_diag2 | 169 个 C 读取器情形、15 个最终 DAT capture 情形、三单元 pages/baseline 对照及静态检查完成。 |
| 独立复编 | DAT、engine.bin、engine.elf、reloc.bin、服务库逐字节相同。 |
| 包 | 最终 SD_ROOT 读回 30 文件；29 个固定文件与 gen 120b 逐字节相同，30 文件均位于忽略范围。 |
| 冻结输入 | 初始 {v['frozen_inputs']:,} 个文件的内容哈希未变。 |

完整验收结果见 [verification.json](verification.json)，新增字面值检查见 [raw-tests.json](raw-tests.json) 和 [raw-model.json](raw-model.json)。独立复编的各项 SHA 记录在 verification.json。包的 30 项哈希位于 `firmware/package_v36_diag21/CARD_SHA256SUMS`。

## 原路径套件的适配

旧脚本从原路径载入调用，没有查看、复制或打印 `research/diag_dat_v1`、`research/review_diag` 的脚本源码；异常只保留类型、文件、函数和行号。路径重绑在任何套件入口执行前完成，输出统一写入本轮三个目录。每个驱动的 Python 子任务在同一解释器中串行执行。两个独立模型驱动同时运行时，审计钩子禁止创建子进程；需要 fork 的套件使用单驱动。

沿用 diag-v2-heap-r2 的六页适配：旧五页断言位置先检查真实 H，再多按一次 DISP 继续原 A 页断言。身份、generation、BSS、快照尺寸和主块尺寸期望改为最终产物的值。旧 BAD 的六行显示断言按新版合同检查八位十六进制或 `--------`，具体原值由新增 24 个 C 情形及 9 个最终 DAT 情形独立核对。没有把原始行值改成旧占位符。

原路径、参数、返回码、实际页及适配记录位于 `local/calls/`、`local/suite-r2/`、`local/legacy/review/evidence/` 和 `local/review2/`。重跑命令见 [COMMANDS.txt](COMMANDS.txt)。封存后的 [SHA256SUMS](SHA256SUMS) 以仓库根为基准，自身除外。

## 继承事项与证据边界

P1-03 的持续变化示例仍可复现。任务方已变更要求后豁免，本轮没有增加同步方案。两份记录相等不代表整个遍历期间没有变化。P2-03 仍为 OPEN，管理末端之外的特定槽值仍可能显示 Q/OK。P1-01、P1-02 的既有例外保持原状；旧套件的 56 个 setter 记录仍包括 44 次值变化和 12 次同值写入。

任务方提供的旧真机 H 页面是第 2 至 7 行占位、第 8 行 BADR0000。它只证明边界或哨兵检查失败，不能确定失败子条件。新版的真实原值尚未知；READINGS 中的数值例子明确是构造示例。

没有相机、存储卡或网络操作，没有子代理。静态、主机 C 和指令模型结果不代表相机 LCD、RTOS 调度或物理重启验收。系统写入限制先于构建建立，构建和套件只能写本轮三个新目录；理光二进制及反汇编位于被忽略的 local。报告生成距本轮开始 {elapsed / 60:.1f} 分钟，本轮获准时限为 {allowed} 分钟。
'''
    (here / 'REPORT.md').write_text(text)
    print('REPORT RETURN 0')


if __name__ == '__main__':
    main()
