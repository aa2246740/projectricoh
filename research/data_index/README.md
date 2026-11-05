# 本地照片与颜色源索引

统计口径：照片按文件 SHA-256 去重，DNG 和 JPG 分别计数；配对数是通过同目录同名及关键 EXIF、MakerNote 一致性检查的关系数。来源按路径计数，同一文件的多处副本可出现在不同来源。颜色源按文件计数。数据和 CSV 在被忽略的本地目录，仅供本机使用；不登记 GPS 字段。

| 项目 | 数量 |
| --- | ---: |
| 去重后的图像文件 | 3,661 |
| 图像路径 | 5,429 |
| DNG/JPG 配对 | 1,433 |
| 颜色源文件 | 206 |
| 旧卡根目录归档文件 | 29 |

| 单元 | 图像文件数 |
| --- | ---: |
| 28mm | 576 |
| 50mm | 1,418 |
| MOUNT | 1,109 |
| unknown | 558 |

| 图像设定 | 图像文件数 |
| --- | ---: |
| Standard | 2,471 |
| Black & White | 325 |
| Setting1 | 34 |
| Setting2 | 116 |
| Vivid | 25 |
| Natural | 2 |
| unknown | 688 |

| 来源 | 路径数 | 去重文件数 |
| --- | ---: | ---: |
| 仓库采集 | 2,318 | 2,301 |
| 清卡前归档 | 1,148 | 1,148 |
| 个人备份 | 1,126 | 1,126 |
| Studio | 802 | 802 |
| Spotlight 额外位置 | 35 | 34 |

| 内容类型 | 图像文件数 |
| --- | ---: |
| 屏幕色卡 | 148 |
| 实物色卡 | 18 |
| 探针 | 124 |
| 自然场景 | 14 |
| unknown | 3,357 |

| 字段 | 未知或缺失文件数 |
| --- | ---: |
| 单元 | 558 |
| 图像设定 | 688 |
| 白平衡模式 | 685 |
| 白平衡补偿 | 3,661 |
| DAT | 2,997 |
| 配方 | 2,981 |
| 内容类型 | 3,357 |
| 页码 | 3,511 |
| EXIF 时间缺失 | 544 |

另有 665 个文件的 EXIF 年份为 2000 或 2009，标记为不可信。页码只适用于部分内容，unknown 不代表每张照片都应有页码。

数据库表：

- `photos`：按 SHA-256 去重的图像、EXIF、单元、图像设定、参数和保守认定。
- `paths`：每个文件位置、来源和文件修改时间。
- `pairs`：通过检查的 DNG/JPG 关联及判断依据。
- `uses`：照片与研究之间有依据的关联。
- `evidence`：单项认定的值及其依据；证据冲突时主表保留 unknown。
- `labels`：按照片 SHA-256 合并后的内容、环境、主题及模型信息。
- `label_sources`：每张照片每个模型的原始标签和来源文件。
- `conflicts`：互相矛盾的认定，保留两边的值和证据文件。
- `color_sources`：颜色源的位置、来源、格式、大小和 SHA-256，不解析内容。
- `archived_files`：旧卡根目录文件、格式、大小和 SHA-256。
- `errors`：无法读取元数据等问题。

可在本目录执行以下命令；每行输出一个 JSON 文件记录及其所有路径、配对和研究证据。

```sh
/opt/homebrew/bin/python3 -I query.py --unit 28mm --setting Standard --pairs
/opt/homebrew/bin/python3 -I query.py --used-by library_28mm_r1
/opt/homebrew/bin/python3 -I query.py --content screen --page V1
/opt/homebrew/bin/python3 -I query.py --unit MOUNT --iso 200 --limit 10
```

图像设定及参数复用已有的有界 TIFF 和 Ricoh MakerNote 解码；WB 补偿尚无经过验证的解码，全部保留 unknown。单元优先使用焦距，并单独记录 MakerNote 单元及冲突。配对失败不证明文件一定没有对应照片。固件版本不证明 DAT 身份。

当前反查仍不完整：一般清单只按 SHA 或完整绝对路径关联，未覆盖所有相对路径、超大清单和各研究的非清单认定；内容类型仅导入已确认的午间清单及四份探针输入清单。不能把未查到研究或 unknown 视为不存在。首次扫描排除了 Spotlight 返回的仓库外挂载卷，避免读取相机或 SD 卡；本次 Spotlight 结果没有此类路径。续跑复用已记录哈希并检查大小和修改时间，不能代替重新计算哈希；重新构建后需重新核对来源和统计。

## 导入和标签

运行 `python3 -I import_findings.py` 可重放本次新增的确定性认定。证据按照片 SHA-256、字段、值和来源保存；有争议的字段保持 unknown。`probe_response` 是响应身份，不是菜单名称或 DAT 身份。`dat_presence=absent_by_predat_backup_provenance` 表示来源认定为 DAT 安装前备份，不推断具体 DAT。`owner_recipe_assignment` 保留拍摄者报告的原文。探针标签和响应的分歧单独保存在 `conflicts`。

将 Gemini 输出放到 `local/labels_gemini.jsonl`，每行一个对象，例如：

```json
{"sha256":"<64位小写SHA-256>","content":"natural","environment":"outdoor_sun","subjects":["skin","sky"],"monochrome":false,"confidence":0.9,"model":"gemini-model-name","notes":""}
```

```sh
nice -n 15 /opt/homebrew/bin/python3 -I merge_labels.py
nice -n 15 /opt/homebrew/bin/python3 -I query.py --subject skin --environment outdoor_sun --pairs
```

也可给 `merge_labels.py` 一个 JSONL 路径作为位置参数。同一照片的不同 `model` 分开保存在 `label_sources`；相同照片和模型的重导入更新该来源。脚本先验证全文件，遇到无效行或未入库的 SHA-256 则不写标签。确定性内容优先；模型与确定性证据或不同模型之间的内容、环境、单色判断冲突会保留两边的值，互相冲突的模型环境或单色结果不选胜者。主题集合取各模型并集，原始来源仍可单独查看。查询结果中的 `labels` 是合并值；`photos.content` 保留既有确定性认定。

内容类别为 `screen_chart`、`printed_chart`、`probe_page`、`natural`、`lcd_or_screen_photo`、`other`、`unknown`；环境类别为 `outdoor_sun`、`outdoor_shade`、`overcast`、`indoor_artificial`、`mixed`、`night`、`unknown`。允许的主题为 `skin`、`sky`、`foliage`、`blue_object`、`red_object`、`saturated_colour`、`clipped_highlights`、`deep_shadow`、`neutral_grey`、`architecture`、`text_or_signage`。
