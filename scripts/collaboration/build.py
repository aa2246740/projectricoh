#!/usr/bin/env python3
"""Build the collaboration page and checklist from one dated status snapshot."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/collaboration"
PLAN = json.loads((OUTPUT / "plan.json").read_text())


def bullets(values):
    return "\n".join(f"- {value}" for value in values)


def numbered(values):
    return "\n".join(f"{index}. {value}" for index, value in enumerate(values, 1))


def build():
    template = (ROOT / "scripts/collaboration/page.html").read_text()
    if template.count("__PLAN_JSON__") != 1:
        raise ValueError("The page needs exactly one plan data placeholder")
    # Escape script delimiters without changing the decoded text.
    data = json.dumps(PLAN, ensure_ascii=False).replace("<", "\\u003c")
    page = template.replace("__PLAN_JSON__", data)
    (OUTPUT / "gxr-collaboration.html").write_text(page)

    stages = []
    for index, stage in enumerate(PLAN["stages"], 1):
        stages.append(f"""### {index}. {stage['title']}，{stage['status']}

我负责：

{bullets(stage['me'])}

你配合：

{numbered(stage['you'])}

本阶段交付：{' '.join(stage['deliver'])}

进入下一阶段的条件：{stage['next']}
""")

    source_links = "\n".join(f"- [{s['label']}]({s['url']})" for s in PLAN["sources"])
    text = f"""# A12 50mm 协作与操作清单

我准备代码、文件和操作表；你操作相机菜单、装卡和拍摄；我读取文件、分析结果，再给下一轮步骤。

核对日期：{PLAN['date']}。范围：{PLAN['scope']}。目标：{PLAN['goal']}。

{PLAN['current_note']} 相机未连接，启动、配方菜单、颜色和恢复都尚未验证。本清单是当前执行计划，取代历史双模块、Box 和 MY 拨盘实验。My Settings 用于定位原厂保存代码；最终 16 个配方通过独立列表选择。

## 你现在需要做什么

相机还没带来时，你可以先准备研究卡和读卡器；电脑开发工具已经备好。当前不用安装软件、升级、拆机或购买烧录器。离线字段、菜单和接口研究可由我继续推进。

你已确认相机使用最新固件，当前按官方 1.51 继续研究，不再等待版本照片。[官方版本页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/)

相机带来后，取样前先拍 **Reg. My Settings 保存菜单**，拍到实际可选位置，尤其是是否有 Card，先不确认保存。中文菜单文字以你相机实际显示为准。原 Setting 1/2 和拍摄参数在修改前完整留存。候选核对时再留档版本页，不把它作为当前离线研究的前置条件。

需要留档版本时，使用原厂只读步骤：相机关闭，A12 50mm 已装好，按住减号 `[–]` 与回放键超过一秒，拍清 BODY 和 CAMERA UNIT 的 MAIN，并保留 BKUP、MONI 等其他项。这是减号。升级入口使用另一组按键，当前不用进入。[原厂操作手册，第 1 页](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf)

保存菜单只读查看步骤：相机开机，按 `MENU/OK`，进入 `Key Custom Options`，选中 `Reg. My Settings` 后按 `Fn2`。只拍保存位置列表，不按 `MENU/OK` 确认保存，按 `DISP.` 不保存退出。若实际界面或按键不同，停在当前画面拍照交给我。[GXR 手册，印刷页 130](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf#page=142)

取样时，我按实际菜单给步骤。如果没有 Card 菜单，交菜单照片后改查代码。相机不是必须用 USB 连接；读卡器即可交接文件。目前没有验证过可让代理远程操作 GXR 菜单或快门的 USB 接口。

## 带来的东西

{bullets(PLAN['gear'])}

研究卡在任何格式化或覆盖之前都要完成备份，并确认备份能打开。第一次只用 50mm；28mm 模块暂不用。原来用于日常拍摄的卡、Box 记录、MY 拨盘关联留存。

## 已完成

{bullets(PLAN['done'])}

电脑验证证据：

- [配方核心源码与说明](../firmware/recipe_core/README.md)
- [根代理宿主验证记录](../artifacts/development/recipe-core-root-verification.json)
- [根代理 M32R 目标编译记录](../artifacts/development/m32r-c-root-check/verification.json)
- [GPT-6.1 独立复核](../research/review/RECIPE_CORE_REVIEW.md)
- [原厂 My Settings 记录研究](../research/a12_50_firmware/REPORT.md)

这些证据证明电脑原型和编译工具的行为。核心记录中的 13 字节目前是合成数据，尚未确定原厂颜色编码；目标对象没有在相机运行。

## 还没完成

{bullets(PLAN['pending'])}

白平衡是否加入首版仍待确认。16 条记录核心没有白平衡字段；真实胶片风格预置尚未调校，最终参数范围与名称输入方式还要结合机内菜单。

## 全流程与分工

{chr(10).join(stages)}

## 第一轮取样怎样交接

菜单核对后才开始取样。先拍照或录像保留 Setting 1、Setting 2 的全部参数、当前 Image Settings 选择项，以及画质、模式、ISO、白平衡、曝光、对焦和按钮配置。记录 Start Settings Readout 的当前值，取样时保持它不变。原厂卡记录是否完整包含自定义颜色参数尚未证明，不能只靠 Card 文件恢复既有设置。

取样固定用这套机身＋50mm、同一个研究卡 Card 槽，以及同一个拍摄模式。若菜单允许命名，名称保持不变。只改一个颜色字段。先记录实际显示值，不预填字段的数值范围。

| 样本 | 相机上做什么 | 文件交给我时保留什么 |
| --- | --- | --- |
| A0 | 用 Setting 1 的基线参数保存到研究卡选定槽，并拍 JPEG＋DNG | 本次保存后的原厂文件、目录结构与基线照片对 |
| A1 | 所有值保持 A0，不改任何项，再保存到同一槽 | 独立复制；用于识别时间、计数器等自然变化 |
| B | 只把 Setting 1 的全局鲜艳度改一个允许档位，保存到同一槽，并拍 JPEG＋DNG | 修改前后显示值、原厂文件与 B 照片对 |
| A2 | 将鲜艳度恢复 A0 原值，保存到同一槽 | 独立复制；用于检查改回后的数据是否对应 |

每次保存后，等待写卡完成并正常关机，再取卡用读卡器复制。不要让 A1 的电脑副本覆盖 A0，后面同样如此。实际文件名由相机产生，保留原样；没有找到设置文件时，交目录清单和菜单照片，让我确定文件位置。

先保护原设置，再在相机里选择 RAW 画质，并在 RAW/JPEG 设置中选同时保存 JPEG 的模式，在 A0 之前固定好其他拍摄设置。1.50 起新增 `RAW only`，取样需要 JPEG＋DNG，因此不要选该项。[官方修订记录](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/gxr/)

GXR 原厂 RAW 使用 DNG；同时保存的 JPEG 副本受 Image Settings 影响。[GXR 手册，印刷页 63](https://www.ricoh-imaging.co.jp/english/r_dc/support/manual/pdf/gxr/GXR_E.pdf#page=75)

基线和 B 必须在各自参数状态下拍摄，B 的照片在改回 A2 之前完成。每次快门都保留 JPEG＋DNG。用同一个静物和固定照明，其他拍摄参数保持一致，文件按基线与 B 分开。不要经过手机、社交软件或图像编辑器压缩、转换。相机操作完成后按原设置照片恢复；不需要改变 Box 或 MY 拨盘关联。

目录建议：

```text
captures/a12-50/session-01/
  00-device/             版本页、保存菜单、Start Settings Readout
  01-original-settings/  原 Setting 1/2 与拍摄设置照片或视频
  A0-baseline/           第一次保存的原文件，保留原路径
  A1-repeat/             不改参数再次保存的原文件
  B-vividness/           只改鲜艳度后的原文件
  A2-restored/           改回原值后的原文件
  photos/baseline/       同次快门 JPEG＋DNG，保留原文件名
  photos/B/              同次快门 JPEG＋DNG，保留原文件名
  sample-log.csv         实际版本、槽号、前后值和文件对应关系
```

你可以把这一目录复制到项目，或在本对话附上原文件与照片。我分析已经交接到项目的副本。当前没有直接控制相机的能力；能否读挂载中的卡，也取决于电脑权限。`captures/` 已被 Git 忽略，样本不需要提交到公开仓库。

完整交接清单：

{bullets(PLAN['handoff'])}

[记录表模板](../artifacts/collaboration/sample-log-template.csv)只含列名和 A0/A1/B/A2 编号。先复制到采样目录并命名 `sample-log.csv`，再填实际值。我核对文件结构、校验和三组差分，然后给字段候选或下一轮操作表。若设置文件没有保存这些颜色值，由我改查菜单函数与机身/模块通信，采样成功不等于字段定位成功。

## 后续可能要补的样本

首轮分析后才决定。Setting 1 和 Setting 2 可能需要分别逐项采集以下 13 个字段，总计 13＋13 项：

{numbered(PLAN['fields'])}

白平衡如纳入配方，会另给独立步骤，不混进颜色字段取样。喜欢的风格样片 3–5 张可帮助调校，当前不影响开始研究；提供自己有权分享的文件即可。最后真机验收才需要全部 16 个配方的照片对和操作记录。

## 更新与失败时怎样合作

未来的更新按具体候选执行：我给出输入版本、实际写入的机身/模块组件、文件校验值、已证实的恢复条件和该次步骤；你复制到 SD 卡并在相机上按键确认，我分析结果。[原厂 SD 更新说明](https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_en.pdf)

当前没有可执行的刷写步骤。更新失败后能否刷回官方固件，取决于相机是否还能进入升级、读卡和完成写入。同版本重刷、回滚和坏主程序救援都未在你的设备上验证。最坏情况下机身与 50mm 模块都可能不能正常启动；实际风险由修改的写入范围决定。不能承诺一次更新完成，也没有可报告的失效概率。详见 [RAW 与风险证据](A12_50_RAW_AND_RISK.md)。

不通过主动断电、拔卡或写坏固件来验证救援。出现异常时，你记录画面、操作到哪一步和发生的现象，我先定位原因，再给下一步。

## 原厂来源与重建

{source_links}

当前状态数据在 [plan.json](../artifacts/collaboration/plan.json)。协作图和本清单由同一份数据生成，重建命令：

```sh
python3 scripts/collaboration/build.py
```
"""
    (ROOT / "docs/A12_50_COLLABORATION.md").write_text(text)
    with (OUTPUT / "sample-log-template.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "sample_id", "module", "body_main", "module_main", "card_slot",
            "changed_field", "before_value", "after_value", "settings_path",
            "jpeg_file", "dng_file", "notes",
        ])
        for sample in ("A0", "A1", "B", "A2"):
            writer.writerow([sample] + [""] * 11)
    print("Built collaboration page, operation checklist, and sample log template.")


if __name__ == "__main__":
    build()
