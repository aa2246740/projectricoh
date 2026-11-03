# 配方样本统计

由 `analyze_recipes.py` 从 `recipes.csv` 生成。数值是样本频率，不是全球使用率。

## ALL

| 底片预设 | 条数 | 占比 |
|---|---:|---:|
| Positive Film | 20 | 33.9% |
| Negative Film | 7 | 11.9% |
| Retro | 5 | 8.5% |
| Cross Process | 5 | 8.5% |
| Standard | 5 | 8.5% |
| Monotone | 4 | 6.8% |
| Bleach Bypass | 3 | 5.1% |
| Hi-Contrast B&W | 3 | 5.1% |
| Vivid | 2 | 3.4% |
| Hard Monotone | 2 | 3.4% |
| B&W (TE) | 2 | 3.4% |
| High Key | 1 | 1.7% |
| Soft Monotone | 0 | 0.0% |
| HDR Tone | 0 | 0.0% |

| 参数 | 写明条数 / 样本数 | 非零或非 Off 条数 | 观察范围 | 常用值（次数） |
|---|---:|---:|---|---|
| saturation | 33/59 | 33 | -4 至 4 | 4 (12), 2 (9), 3 (5), 1 (3), -1 (2) |
| vividness | 17/59 | 17 | 1 至 9 | 9 (7), 3 (3), 1 (2), 7 (2), 5 (1) |
| hue | 38/59 | 35 | 分类值见频次 JSON | -2 (6), -4 (4), 4 (4), -1 (4), 1 (3) |
| high_low_key | 39/59 | 36 | -4 至 4 | 1 (15), 2 (8), -1 (4), -2 (3), 3 (3) |
| contrast | 58/59 | 57 | -4 至 9 | 4 (13), 2 (9), 3 (8), -2 (7), 9 (5) |
| contrast_highlight | 39/59 | 38 | -4 至 4 | -4 (18), -3 (7), 2 (5), 3 (3), -2 (3) |
| contrast_shadow | 39/59 | 37 | -4 至 4 | 4 (15), -4 (10), -3 (5), 3 (2), 2 (2) |
| sharpness | 58/59 | 48 | -4 至 7 | 1 (13), -1 (11), 0 (10), 2 (8), 4 (5) |
| shading | 39/59 | 9 | -1 至 2 | 0 (30), -1 (6), 1 (2), 2 (1) |
| clarity | 39/59 | 37 | -4 至 4 | 2 (11), -2 (9), -1 (6), 1 (4), 4 (3) |
| toning | 11/59 | 3 | 分类值见频次 JSON | Off (7), 3 (1), 1 (1), 4 (1), N/A (1) |
| toning_effect | 2/59 | 2 | 分类值见频次 JSON | Sepia (1), Blue (1) |
| color_tone | 2/59 | 2 | 分类值见频次 JSON | Y (1), Blue (1) |
| filter_effect | 4/59 | 3 | 分类值见频次 JSON | 2 (2), 3 (1), Off (1) |
| hdr_tone | 0/59 | 0 | 无样本值 |  |
| grain_effect | 6/59 | 6 | 1 至 3 | 2 (3), 3 (2), 1 (1) |
| vignetting | 19/59 | 6 | 分类值见频次 JSON | Off (13), Weak (5), Medium (1) |
| highlight_correction | 39/59 | 39 | 分类值见频次 JSON | On (37), Auto (2) |
| shadow_correction | 39/59 | 38 | 分类值见频次 JSON | Low (14), Medium (13), High (8), Auto (3), Off (1) |
| peripheral_illumination_correction | 39/59 | 39 | 分类值见频次 JSON | On (39) |
| dynamic_range_compensation | 20/59 | 17 | 分类值见频次 JSON | Strong (6), Medium (6), Weak (5), Off (3) |
| high_iso_noise_reduction | 39/59 | 0 | 分类值见频次 JSON | Off (39) |
| noise_reduction | 20/59 | 0 | 分类值见频次 JSON | Off (20) |
| white_balance | 59/59 | 59 | 分类值见频次 JSON | Auto (7), Cloudy (7), Daylight (7), Shade (6), Outdoors (5) |
| wb_compensation | 59/59 | 59 | 分类值见频次 JSON | B:4 G:2 (3), A:8 G:2 (2), A:6 G:2 (2), B:2 G:5 (2), B:8 M:8 (2) |
| iso | 59/59 | 59 | 分类值见频次 JSON | up to ISO 6400 (43), up to ISO 3200 (15), Up to 6400 (1) |
| exposure_compensation | 59/59 | 59 | 分类值见频次 JSON | 0 to +2/3 (typically) (15), -1/3 to +1/3 (typically) (13), 0 to +1/3 (typically) (8), +1/3 to +1 (typically) (7), +1/3 to +2/3 (typically) (5) |
| wb_ab_signed | 59/59 | 54 | -14 至 14 | 0 (5), -2 (5), -6 (4), 14 (4), -8 (4) |
| wb_gm_signed | 59/59 | 54 | -14 至 14 | 2 (10), 5 (6), 3 (5), 0 (5), 10 (4) |
| wb_kelvin | 14/59 | 14 | 2500 至 10000 | 10000 (2), 2500 (2), 6300 (1), 5250 (1), 5500 (1) |

## GR/GR II

| 底片预设 | 条数 | 占比 |
|---|---:|---:|
| Positive Film | 6 | 30.0% |
| Cross Process | 3 | 15.0% |
| Bleach Bypass | 2 | 10.0% |
| Retro | 2 | 10.0% |
| Monotone | 2 | 10.0% |
| B&W (TE) | 2 | 10.0% |
| Standard | 1 | 5.0% |
| High Key | 1 | 5.0% |
| Hi-Contrast B&W | 1 | 5.0% |

| 参数 | 写明条数 / 样本数 | 非零或非 Off 条数 | 观察范围 | 常用值（次数） |
|---|---:|---:|---|---|
| saturation | 0/20 | 0 | 无样本值 |  |
| vividness | 17/20 | 17 | 1 至 9 | 9 (7), 3 (3), 1 (2), 7 (2), 5 (1) |
| hue | 5/20 | 5 | 分类值见频次 JSON | Yellow (3), Warm (1), Cool (1) |
| high_low_key | 0/20 | 0 | 无样本值 |  |
| contrast | 19/20 | 19 | -2 至 9 | 9 (5), 7 (4), 2 (2), 3 (2), 6 (2) |
| contrast_highlight | 0/20 | 0 | 无样本值 |  |
| contrast_shadow | 0/20 | 0 | 无样本值 |  |
| sharpness | 19/20 | 19 | 1 至 7 | 2 (7), 4 (4), 3 (2), 1 (2), 6 (2) |
| shading | 0/20 | 0 | 无样本值 |  |
| clarity | 0/20 | 0 | 无样本值 |  |
| toning | 0/20 | 0 | 无样本值 |  |
| toning_effect | 2/20 | 2 | 分类值见频次 JSON | Sepia (1), Blue (1) |
| color_tone | 0/20 | 0 | 无样本值 |  |
| filter_effect | 0/20 | 0 | 无样本值 |  |
| hdr_tone | 0/20 | 0 | 无样本值 |  |
| grain_effect | 0/20 | 0 | 无样本值 |  |
| vignetting | 19/20 | 6 | 分类值见频次 JSON | Off (13), Weak (5), Medium (1) |
| highlight_correction | 0/20 | 0 | 无样本值 |  |
| shadow_correction | 0/20 | 0 | 无样本值 |  |
| peripheral_illumination_correction | 0/20 | 0 | 无样本值 |  |
| dynamic_range_compensation | 20/20 | 17 | 分类值见频次 JSON | Strong (6), Medium (6), Weak (5), Off (3) |
| high_iso_noise_reduction | 0/20 | 0 | 无样本值 |  |
| noise_reduction | 20/20 | 0 | 分类值见频次 JSON | Off (20) |
| white_balance | 20/20 | 20 | 分类值见频次 JSON | Outdoors (5), Cloudy (4), Incandescent 2 (3), CT 4700K (1), Auto (1) |
| wb_compensation | 20/20 | 20 | 分类值见频次 JSON | B:4 G:2 (3), B:2 G:5 (2), B:8 M:8 (2), A:3 G:5 (1), A:3 M:2 (1) |
| iso | 20/20 | 20 | 分类值见频次 JSON | up to ISO 3200 (15), up to ISO 6400 (5) |
| exposure_compensation | 20/20 | 20 | 分类值见频次 JSON | 0 to +2/3 (typically) (7), 0 to +1/3 (typically) (4), -1/3 to +1/3 (typically) (3), +1/3 to +2/3 (typically) (2), +1/3 to +1 (typically) (2) |
| wb_ab_signed | 20/20 | 19 | -8 至 8 | 3 (3), -4 (3), -2 (3), -8 (3), -1 (2) |
| wb_gm_signed | 20/20 | 18 | -8 至 8 | 2 (4), 5 (3), 3 (3), -8 (3), 0 (2) |
| wb_kelvin | 5/20 | 5 | 2500 至 10000 | 4700 (1), 6600 (1), 7800 (1), 10000 (1), 2500 (1) |

## GR III/IIIx

| 底片预设 | 条数 | 占比 |
|---|---:|---:|
| Positive Film | 14 | 35.9% |
| Negative Film | 7 | 17.9% |
| Standard | 4 | 10.3% |
| Retro | 3 | 7.7% |
| Vivid | 2 | 5.1% |
| Cross Process | 2 | 5.1% |
| Hard Monotone | 2 | 5.1% |
| Hi-Contrast B&W | 2 | 5.1% |
| Monotone | 2 | 5.1% |
| Bleach Bypass | 1 | 2.6% |
| Soft Monotone | 0 | 0.0% |
| HDR Tone | 0 | 0.0% |

| 参数 | 写明条数 / 样本数 | 非零或非 Off 条数 | 观察范围 | 常用值（次数） |
|---|---:|---:|---|---|
| saturation | 33/39 | 33 | -4 至 4 | 4 (12), 2 (9), 3 (5), 1 (3), -1 (2) |
| vividness | 0/39 | 0 | 无样本值 |  |
| hue | 33/39 | 30 | -4 至 4 | -2 (6), -4 (4), 4 (4), -1 (4), 1 (3) |
| high_low_key | 39/39 | 36 | -4 至 4 | 1 (15), 2 (8), -1 (4), -2 (3), 3 (3) |
| contrast | 39/39 | 38 | -4 至 4 | 4 (11), 2 (7), -2 (6), 3 (6), 1 (3) |
| contrast_highlight | 39/39 | 38 | -4 至 4 | -4 (18), -3 (7), 2 (5), 3 (3), -2 (3) |
| contrast_shadow | 39/39 | 37 | -4 至 4 | 4 (15), -4 (10), -3 (5), 3 (2), 2 (2) |
| sharpness | 39/39 | 29 | -4 至 4 | 1 (11), -1 (11), 0 (10), -2 (4), -4 (1) |
| shading | 39/39 | 9 | -1 至 2 | 0 (30), -1 (6), 1 (2), 2 (1) |
| clarity | 39/39 | 37 | -4 至 4 | 2 (11), -2 (9), -1 (6), 1 (4), 4 (3) |
| toning | 11/39 | 3 | 分类值见频次 JSON | Off (7), 3 (1), 1 (1), 4 (1), N/A (1) |
| toning_effect | 0/39 | 0 | 无样本值 |  |
| color_tone | 2/39 | 2 | 分类值见频次 JSON | Y (1), Blue (1) |
| filter_effect | 4/39 | 3 | 分类值见频次 JSON | 2 (2), 3 (1), Off (1) |
| hdr_tone | 0/39 | 0 | 无样本值 |  |
| grain_effect | 6/39 | 6 | 1 至 3 | 2 (3), 3 (2), 1 (1) |
| vignetting | 0/39 | 0 | 无样本值 |  |
| highlight_correction | 39/39 | 39 | 分类值见频次 JSON | On (37), Auto (2) |
| shadow_correction | 39/39 | 38 | 分类值见频次 JSON | Low (14), Medium (13), High (8), Auto (3), Off (1) |
| peripheral_illumination_correction | 39/39 | 39 | 分类值见频次 JSON | On (39) |
| dynamic_range_compensation | 0/39 | 0 | 无样本值 |  |
| high_iso_noise_reduction | 39/39 | 0 | 分类值见频次 JSON | Off (39) |
| noise_reduction | 0/39 | 0 | 无样本值 |  |
| white_balance | 39/39 | 39 | 分类值见频次 JSON | Daylight (7), Auto (6), Shade (5), Fluorescent N – Daylight White (4), Cloudy (3) |
| wb_compensation | 39/39 | 39 | 分类值见频次 JSON | A:8 G:2 (2), B:7 G:2 (1), A:1 G:6 (1), A:12 G:10 (1), B:6 G:5 (1) |
| iso | 39/39 | 39 | 分类值见频次 JSON | up to ISO 6400 (38), Up to 6400 (1) |
| exposure_compensation | 39/39 | 39 | 分类值见频次 JSON | -1/3 to +1/3 (typically) (10), 0 to +2/3 (typically) (8), +1/3 to +1 (typically) (5), -2/3 to 0 (typically) (5), 0 to +1/3 (typically) (4) |
| wb_ab_signed | 39/39 | 35 | -14 至 14 | -6 (4), 14 (4), 0 (4), 10 (3), 1 (2) |
| wb_gm_signed | 39/39 | 36 | -14 至 14 | 2 (6), 10 (4), 5 (3), 4 (3), 1 (3) |
| wb_kelvin | 9/39 | 9 | 2500 至 10000 | 6300 (1), 5250 (1), 5500 (1), 5200 (1), 6900 (1) |

