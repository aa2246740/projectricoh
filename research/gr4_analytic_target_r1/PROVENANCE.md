# 参数和语义来源

本目录只做电脑研究。固件数值、字节、生成曲线、矩阵和照片派生数组都在被忽略的 `local/`。本文件只记录取值规则，不复制原始表。

| 环节 | 本次使用的值或规则 | 来源类别 | 证据与限制 |
|---|---|---|---|
| 模式选择 | Standard、Positive Film、Negative Film 对应已提取记录。 | GR IV 固件静态提取。 | `../gr_firmware/data/gr4-1.11-tables.json` 的 modes 和同名参数记录。只覆盖该提取版本；HDF 老版本照片单列。 |
| look matrix | 从同名表读取，按已记录 Q13 解释。 | GR IV 固件静态提取；像素位置借用公开 GR III 解读。 | 同名 `look-matrix`，静态哈希和格式逐块重算。没有把 GR III look 系数用作 GR IV 系数。 |
| 相机矩阵 | GR IV sensor CCM 作初始化先验，随后仅用训练页 Standard 拟合共同矩阵与 WB。 | 静态先验加推断。 | 拟合值保存在 `local/calibration/`。这不是测得的传感器光谱矩阵，也不是从风格图回归的残差 LUT。 |
| 饱和度 | 读取 GR IV 默认档饱和度表。 | GR IV 固件静态提取。 | `saturation-+0`。该档为单位矩阵，因此 GR III／IV 饱和度阶段位置的差异不改变本次默认档输出。其他档不在验证范围内。 |
| WB、黑白电平、方向、裁切 | 从每张 DNG 读取。WB 后再拟合共同 R/B 小修正。 | 真实 DNG 元数据加推断。 | 用原 DNG 解码，不用旧预测 RAW 替身。不对留出图片拟合 WB。 |
| DNG 曝光约定 | 输入中的 BaselineExposure 相对模板的差直接用于共同输入缩放。 | 真实 DNG 元数据；作为 JPEG 增益依据仍属推断。 | 不用风格 JPEG 反求曝光。保留漏算此项的早期失败结果。BaselineExposure 不等于固件实际运行 gain。 |
| mode sliders | 采用 GR III 已闭合默认值；逐张核对本批 GR IV JPEG 的默认滑杆与其相符。 | GR III 类比，加本批真实 JPEG 元数据佐证。 | 没有把本批字段相符提升成 GR IV 所有 reset/profile 默认值已静态闭合。私有元数据存于 audit 文件。 |
| gamma | 使用 GR IV 的基础族、key、过渡权重和单位，按既有整数算法重新合成。 | GR IV 固件静态提取。 | `../gr_complete_pipeline/gr3_gr4_effective_curves.json` 的 GR IV source_blocks；公式来自 `arm_gamma_model.py`。与既有保存状态逐节点比较。 |
| gamma gain 与输入曝光 | 只以训练页 Standard 的稳健 RGB 残差选取共用 gain 和曝光。 | 推断。 | 有限粗网格后细化，所有候选及求解状态留档。原图实际 ShootingInfo gain 未取得。 |
| 通道曲线覆盖 | 三种模式的 descriptor flag 关闭，保留共同 gamma，不启用候选 RGB 曲线指针。 | GR IV 固件静态提取。 | 不能因存在三个指针便把它们当作三条 Film 专属曲线。 |
| 默认 toning 与曲线后矩阵 | 默认 toning 查得为零；曲线后 RGB 矩阵采用单位矩阵。 | 前者为静态数据，后者为 GR III 类比和推断。 | 本次没有恢复 GR IV 完整 CSP／YCbCr 像素级舍入。若存在额外运行变换，本模型不包含它。 |
| MultiAxial 数值 | 使用 GR IV 各模式的矩阵、controls 与 RGB→YCbCr 系数。 | GR IV 固件静态提取。 | Positive 记录地址与已有提取一致；不使用公开项目改造后的 film 矩阵。 |
| MultiAxial 启用 | active controls 对应开启，stock inactive 配置对应关闭。 | 公开 GR III 实机探针类比，加 GR IV 静态结构对应。 | 来自 FINDINGS 29–30a。硬件任意 controls 组合未全部解读。 |
| MultiAxial 顺序 | 主模型在 look 之后、gamma 之前执行。 | 公开 GR III 方法类比。 | `work/films_v16/refit16.py::model` 和 `work/v16_plan/hue15.py::render` 明确如此。另测任务摘要所述的 gamma 后顺序。 |
| 扇区 | 用公开的 Cb/Cr 角边界判定扇区。主模型为硬边界，第一个 level；线性混合和其他 level 单列敏感度。 | 公开方法类比；level 与边界混合仍是推断。 | FINDINGS 30b–31 证明了探针几何和排列，未提供完整芯片亮度／色度阈值及插值公式。不能称为逐像素完整 ISP 仿真。 |
| 镜头／径向增益 | 仅用训练页 Standard 拟合共用径向增益，固定用于留出页及自然照片。 | 推断。 | 没有使用既有返回文件中的逐页／逐风格 `rgb_center`、径向模型或中性 LUT。自然照片的镜头及场景适用性单独检验。 |
| scene-linear 输入 | DNG ColorMatrix、白点适配与 BaselineExposure 定义 sRGB/D65 场景坐标，再映射到共同处理坐标。 | DNG 色度学近似和推断。 | 这一步只定义坐标，不计量传感器光谱差；未取得绝对反射率曝光标定。 |
| 测量与色差 | 真实 JPEG 的 sRGB 编码均值转 D65 Lab，再算 CIEDE2000。 | 对真实 GR IV 照片的验证。 | 色块取样与自然场景平坦区域分别统计。合并点数不是独立照片数。 |

公开资料为本地只读副本 `artifacts/downloads/gr3-film-mods/repo`，固定 commit `04d5d5dd6e85d80089c6200bd0f0de5fff2d658f`。代码许可证为 MIT；本次只读 README、FINDINGS 和相关源码，没有 import 或运行该目录任何脚本。参考入口为 [gr3-film-mods](https://github.com/idontknownihil/gr3-film-mods)。没有使用该项目其他许可证下的 film 拟合数据。

未模拟的环节包括 ShootingInfo 的实际 gain 生成、ToneControl 的完整全局／局部行为、镜头状态选择、去马赛克及锐化／降噪、色域裁切和最终 YCbCr／JPEG 的精确整数行为。平坦区域比对降低了后几项的影响，不证明它们不存在。
