# A12 50mm 协作交付独立复核

复核人：**GPT-6.1 review**  
日期：2026-10-12

结论：发现 **1 个中等严重度问题**，没有高严重度问题。取样顺序、原设置保护、RAW 边界和恢复风险表述均通过；当前第一步缺少进入保存菜单并安全退出的按键步骤。

## Finding

### 中等：第一步没有说明怎样只读打开 `Reg. My Settings` 保存位置

- **位置**：`docs/A12_50_COLLABORATION.md:13-20`；生成源 `scripts/collaboration/build.py:61-68`；`artifacts/collaboration/plan.json:55-62`
- **证据**：清单要求用户拍摄 `Reg. My Settings` 的实际保存位置，却只给了版本页按键。保存菜单的进入方法和退出方法都没有写。本地原厂机身手册 `research/recipes/sources/GXR_E.pdf` 印刷页 129–130 明确说明：在 Key Custom Options 页选中 `Reg. My Settings`，按 `Fn2` 进入；后续按 `C/D` 会保存，按 `DISP.` 才是不保存退出。`research/recipes/sources/gxr_vup_en.pdf` 又说明 1.50 后保存位置可出现 `My Settings Box 1–6` 与 `Card 1–6`。
- **影响**：用户当前唯一需要执行的菜单动作不完整。自行试按时可能确认某个 MY、Box 或 Card 位置，与“第一步只看版本和菜单”和“不覆盖现有设置”的保护目标冲突。
- **具体修法**：在两张照片步骤后补一条原厂只读路径，例如：“相机开机，按 `MENU/OK`，进入 Key Custom Options 页，选中 `Reg. My Settings` 后按 `Fn2`；只拍保存位置列表，不选择或确认任何槽，按 `DISP.` 退出。”同步写入 `build.py`，再重建 Markdown 和 HTML。若实际 1.50/1.51 菜单文字或按键不同，停在当前画面拍照，不继续确认。

## 其余抽查

- **范围与状态通过**：交付明确是 GXR＋A12 50mm 首版，目标为 16 条独立命名列表配方；电脑端核心已完成，相机菜单、字段、链接和真机行为未完成，当前无可刷包。
- **取样通过**：A0/A1/B/A2 使用同一 Card 槽；A1 不改参数，B 只改 Setting 1 全局鲜艳度一档，A2 恢复原值。A0 与 B 都在各自状态下拍同次 JPEG＋DNG，B 在 A2 前拍完；每次写卡结束并正常关机后再复制。Card 名称只在菜单支持时保持不变。
- **原设置保护通过**：修改前记录 Setting 1/2 全部 13 项、当前 Image Settings 选择项、画质、模式、ISO、白平衡、曝光、对焦、按钮和 Start Settings Readout；完成后按记录恢复。流程只用 Card，不改 Box 或 MY 拨盘关联。
- **Card 边界通过**：文档明确原厂 Card 记录是否完整包含自定义颜色尚未证明，不能把 Card 文件当作原设置的完整备份；样本若未保存颜色值，会转入菜单代码与参数调用研究。
- **RAW 边界通过**：原厂手册印刷页 63说明 RAW 保存为 DNG并同时生成 JPEG，Image Settings 只作用于 JPEG 副本。交付把新 16 配方与 DNG 的兼容性留到真机验收，没有声称 DNG 带配方颜色。
- **恢复风险通过**：同版本重刷、回滚与坏主程序救援均标为未在用户设备验证；最坏风险可能涉及机身和 A12 50mm 模块，也没有承诺一次刷写成功。
- **历史计划通过**：`docs/CAPTURE_PLAN.md:3` 已明确其为历史实验，并指向当前 A12 50mm 清单，明确不执行旧双模块、Box、MY 或跨模块步骤。

本轮未操作相机、SD 卡或浏览器，也未复核未改动的配方 C 核心。

## 修正后最终复核

**Resolved，No flags。** `scripts/collaboration/build.py:61-70` 和重建后的 `docs/A12_50_COLLABORATION.md:13-22` 现已写明：相机开机后按 `MENU/OK` 进入 Key Custom Options，选中 `Reg. My Settings` 后按 `Fn2`；只拍保存位置列表，不按 `MENU/OK` 确认，以 `DISP.` 不保存退出；界面或按键不同时停下拍照。该路径与本地原厂机身手册印刷页 129–130（PDF 物理页 141–142）一致。

`artifacts/collaboration/plan.json:55-62` 的当前阶段也包含 Fn2 进入与 DISP. 退出，生成 HTML 嵌入的数据与源计划一致。第一阶段仍只要求版本页和保存菜单两张照片。`artifacts/collaboration/preview-checks.json` 记录 728 像素浅色与 320 像素深色下六个阶段均为 PASS；本次仅核对修正内容，没有重新操作界面。

最终结论：上一轮唯一 finding 已解决，没有新增问题。复核人：**GPT-6.1 review**。
