# GXR A12 50mm 品牌色彩目标

2026-10-16。用户明确要求优先做理光正片、负片、高对比黑白，并加入徕卡、富士及其他品牌的代表风格。本目录确定参照和开发顺序，尚不是可安装的配方库。逐项来源和状态在 [targets.json](targets.json)。

## 现有 16 槽的来源

当前上机库来自项目自行编写的 [validation_recipes_16.json](../../firmware/recipe_fw/tools/validation_recipes_16.json)，与已上卡包内的 JSON 内容相同。它没有移植 GR、Leica 或 Fujifilm 算法，也未经过实拍调色。

第 01 槽把 13 个颜色参数设为显示中间值 5，白平衡偏移为 0；这不是经过测量的中性色彩校准。第 02 至 07 槽分别把对比度、锐度、鲜艳度改为 2 或 8；第 08 至 12 槽分别提高五组颜色的鲜艳度到 8；第 13 至 16 槽分别给两条白平衡轴设置正负 2。它们用于判断选槽、加载和应用是否生效。

此前收集的 [59 条 GR 配方资料](../gr_reference/REPORT.md)是另一份研究，当前测试库没有把这些配方适配进 GXR。59 条资料的结构覆盖统计也不代表视觉相似度。

[真机照片](../stage1b_integration/FIRST_CAMERA_RUN.md)已确认新增列表显示并能到第 16 槽；目前没有这套库的受控 JPEG/DNG 比较结果，不能宣称它们在 A12 50mm 上已经好看或匹配某个品牌。

## 当前代码能保存和应用什么

- 对比度、锐度、全局鲜艳度，共 3 项。
- 橙、绿、蓝、红、洋红五组颜色各自的色相与鲜艳度，共 10 项。
- 两轴白平衡补偿，共 2 项。

13 个颜色参数使用界面 1 至 9 档，5 为中间值；白平衡两轴范围为 -8 至 +8。代码和字段映射见 [make_recipes.py](../../firmware/recipe_fw/tools/make_recipes.py)、[recipe_apply.c](../../firmware/recipe_v1/recipe_apply.c)、[字段报告](../field_mapping/REPORT.md)，原厂颜色控制见 [GXR 官方 FAQ](https://www.ricoh-imaging.co.jp/english/r_dc/support/faq/bp/gxr/05/gxr05012.html)。白平衡两轴和 G/M、B/A 的具体对应顺序仍待受控实拍确认。

所有配方最终都写入彩色 Setting1，选择字节固定为 `0x04`。因此 `03 High Contrast` 是彩色高对比测试，不是 Hi-Contrast B&W。GXR 本身有 Black & White，后续固件还增加了 High Contrast B&W 场景；这些能力尚未接入当前独立配方记录，场景路径与 RAW 的组合也未在本候选验收。

当前记录不保存日光/自动等基础白平衡模式，没有自定义色调曲线、独立高光/阴影、颗粒或任意 3D LUT 接口，也没有相机端配方编辑保存界面。GXR 原厂有某项功能，不等于这版配方已经能调用它。

## 拟定的 16 个参照

以下编号是正式库的候选安排，与相机当前测试编号无关。全部状态为“已找到官方模式，未在 GXR 标定”；不填写猜测的参数。

- 01–05：GR II Positive Film、GR III Positive Film、GR III Negative Film、GR II Hi-Contrast B&W、GR III Hi-Contrast B&W。正片和黑白分别保留两代参照，不预设其响应相同。GR II 官方效果表没有 Negative Film；GR III 在 1.70 加入该模式。[GR II 官方规格](https://www.ricoh-imaging.co.jp/english/products/gr-2/spec/)、[GR III 官方模式](https://www.ricoh-imaging.co.jp/english/products/gr-3/feature/03.html)、[GR III 更新记录](https://www.ricoh-imaging.co.jp/english/support/digital/gr3_s.html)。
- 06–08：Leica Standard、Leica Vivid、Leica Chrome。用户所说的“徕卡颜色”先按 Standard 选参照，另两项保留正式名称。Chrome 是官方 Essential Look，区别于 Leica Classic；兼容相机通过 FOTOS 获取它，不能据此推断 GXR 可直接使用其文件。[Leica 官方 Looks](https://leica-camera.com/en-US/photography/leica-looks)。
- 09–11：Fujifilm CLASSIC Neg.、NOSTALGIC Neg.、CLASSIC CHROME。Classic Neg. 取向是家庭相册/消费级负片；Nostalgic Neg. 偏琥珀暖调；Classic Chrome 是纪实印刷取向。PRO Neg. Std/Hi 是另一组人像模式，本轮先不混入“负片”统称。[Classic Neg.](https://www.fujifilm-x.com/global/products/film-simulation/classic-neg/)、[Nostalgic Neg.](https://www.fujifilm-x.com/global/products/film-simulation/nostalgic-neg/)、[Classic Chrome](https://www.fujifilm-x.com/global/products/film-simulation/classic-chrome/)。
- 12–13：PENTAX Reversal Film、SATOBI。前者深黑与浓色，后者偏褪色旧照片；官方还明确说明 Reversal Film 的表现不只是提高饱和度。[PENTAX 官方 Custom Image](https://www.ricoh-imaging.co.jp/english/products/custom_image/)。
- 14：Olympus PEN-F Color Profile 2，选其高饱和、深色胶片方向，不用泛称“奥巴蓝”代替具体参照。[PEN-F 官方补充手册，第 165 页](https://learning.omsystem.com/PEN-F/zz_pdf/pen-f_eng.pdf#page=165)。
- 15–16：LUMIX L.ClassicNeo、L.Monochrome D，分别选烟蓝怀旧彩色与深黑硬调黑白。[官方彩色模式](https://www.panasonic.com/au/consumer/lumix-cameras-lenses/lumix-color/photo-style-color.html)、[官方黑白模式](https://www.panasonic.com/global/consumer/lumix/lumix-color/photo-style-monochrome.html)。

## 怎样才算对齐

参照要固定到具体机型、固件和模式设置。同名参数在不同处理器上不代表相同响应，不能直接照抄 GR 或富士的滑块数值。当前 15 个可调量可以用于尝试近似风格，但真实接近程度尚未测量；官方模式还涉及基础颜色响应和不同明暗区域的处理。

官方样片用于确认审美方向。要测量匹配程度，需要同场景受控对拍，或具有明确输入输出定义的参考处理流程。至少比较灰阶、肤色、绿叶、蓝天和亮部，并用未参与调参的场景及另一种光线复核，避免只让一张样片看起来相似。没有配对参照时，标为风格近似，不报告“还原百分比”。

富士确有面向 GFX ETERNA 55 的官方 Film Simulation 3D LUT，但其输入是 F-Log2 C/F-Gamut C 视频流程，不能直接套到 GXR DNG 或 JPEG；它可作为后续参考研究的线索，不代表 GXR 已有可用的 LUT 接口。[富士官方说明](https://shopusa.fujifilm-x.com/discover/what-are-fujifilm-gfx-eterna-55-s-3d-film-simulation-luts-/)。

## 开发顺序

先核验现有库的实际出片和有效 DNG，再把真实黑白模式、明确的基础白平衡处理接入配方设计。标定首先围绕用户必选的理光正片、负片、高对比黑白；当前接口表达不出的曲线或颜色差异，依据测量结果再扩展底层处理。其余品牌逐项通过实拍后再加入正式库，16 是容量，不是需要靠未校准参数凑满的数量。

交付仍是相机直接输出配方 JPEG，同时保存同次曝光的有效 DNG。电脑端参照渲染只能帮助标定，不能代替机内出片验收。此次没有生成新的 DAT、固件或写入 SD 卡。
