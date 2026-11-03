# GR 参考函数的交接约定

这份约定接收其他 worker 的干净 GR 数据，不负责提取固件。当前没有合格的 golden reference，`acceptance.json` 维持 `NOT_RUN`。

## 输入与输出

统一输入是减黑电平、除以 white−black 后的线性 camera RGB，尚未应用 AsShotNeutral 白平衡。必须声明这是 DNG 存储域、原厂未修正 RAW 域、白平衡后 RGB，还是其他 ISP 中间域。若固件函数只接收中间域，交付者还需提供前级变换；不能用一个文件名替代这条链。

输出是 sRGB 编码的 JPEG 颜色值 [0,1]。JPEG 编码、锐化和降噪可以另列，但用于大色块均值的渲染必须闭合。区分 RGB 顺序、曲线输入范围、黑电平、白电平、饱和截断、WB、矩阵、曲线、扇区色表、色域压缩和每一步量化。

每个函数版本附带以下元数据：

```json
{
  "gr_generation": "GR III | GR IIIx | GR IV",
  "firmware_version": "exact version",
  "renderer_sha256": "...",
  "source_artifact_sha256": "...",
  "look_settings": {"mode": "Positive Film", "all_sliders": "explicit values"},
  "input_domain": "black/white-normalized unbalanced DNG camera RGB",
  "output_domain": "sRGB encoded SDR RGB",
  "sensor_bridge_convention": "specified DNG profile and white/exposure convention",
  "common_white_frozen": true,
  "common_white_xyz_y1": [0.95047, 1.0, 1.08883],
  "exposure_scale_frozen": true,
  "golden_reference_validated": false,
  "same_gr_pair_error": {"de00_median": null, "de00_p90": null}
}
```

Positive 与 Negative 可以有不同内部表，不能假定共享曲线或默认 sliders 全为 0。必须明确复制原厂默认状态还是某张参考 JPEG 的实际状态。GR III 1.60 Positive 与 1.71 Negative 的这套参考是两个版本；不能写成一个同版本实验。

## 两台传感器之间的桥

RAW 桥的两端必须采用同一个光源白点 `W_common` 和同一温度 `T_common`，不能分别用两张照片的 AsShotNeutral 做不同的 chromatic adaptation。计划先以屏幕预设 D65 为模型假设；8 对试拍的中性 RAW 可以在拟合前修正一次，然后冻结。它不是屏幕实测光谱或经过仪器认证的白点。

```text
M_camera(T) = AnalogBalance * CameraCalibration(T) * ColorMatrix(T)
A_camera_common = Bradford(W_common -> D50) * inverse(M_camera(T_common))
B = inverse(A_gr_common) * A_gxr_common
  = M_gr(T_common) * inverse(M_gxr(T_common))
x_gr = exposure_scale * B * x_gxr
target_srgb = F_gr(x_gr, frozen_WB_and_look_state)
```

共同的 Bradford 因子在 `B` 中抵消；GR 风格的固定 WB 随后由 `F_gr` 施加。这与每份 DNG 为显示而计算的 camera→XYZ D50 矩阵用途不同。ForwardMatrix 是另一种渲染比色模型，若选它作为桥，必须明示并同样使用共同白点，不能偷偷与原生 ColorMatrix 路径混用。示例和来源在 [common_white_sensor_bridges.json](common_white_sensor_bridges.json)。GR IV 示例来自 Lightroom 改写容器的 DNG，只是辅助模型，尚未核实为原始 Ricoh 矩阵。

`exposure_scale` 只在训练灰阶上拟合一次并冻结，吸收两传感器归一化的相对比例。DNG 的 BaselineExposure 与 DCP 的 BaselineExposureOffset 必须说明是否已在 `F_gr` 内使用，不能重复加。不能对每张验收图重新拟合 WB、曝光或颜色。各照片实际 AsShotNeutral 仅用于诊断参数传播；候选配方的 WB 不能移动 `B` 或参照。

这是比色近似，不是两种传感器光谱响应的可逆变换。在相同屏幕的 RGB 三基色子空间，若两台相机都能拍同样色块，可直接拟合两机的 3×3 sensor bridge；主人没有 GR，因此本轮不能测到它。屏幕只让 GXR 的自身 ISP 映射可辨识，不能自动补出真实 GR 的屏幕响应。

## 必须保留的失败状态

- 输入超出 RAW 白电平、低于噪声、或落在参考经验模型支持域外时，返回 unsupported，不能夹到最近训练点后称为匹配。
- 只收到曲线／色表、没有上下游域定义时，返回 incomplete，不生成验收金标。
- 由 Adobe DCP 或社区 LUT 产生的目标必须分别叫 profile proxy 或 community proxy。它们能参与探索，不能在缺少真 GR 对照时改成 firmware golden。
- 参考渲染器要先在真实 GR 同曝光 DNG/JPEG 上达到 ΔE00 中位数≤0.5、P90≤1.0，才进入声明的 Phase 1 验收。只有一张色卡通过也只证明该场景，跨明暗、跨光源和其他设置保留未知。

目前 `analyze_pairs.py` 的二次多项式仅为可复查的失败基准，不满足这个交接约定。`derive_dcp_targets.py` 是独立的规范解释器；源数据和曲线解释的误差分开报告，没有冒充 Adobe Camera Raw。
