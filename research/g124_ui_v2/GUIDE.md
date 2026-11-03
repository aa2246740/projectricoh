gen 124 当前提供 Cont、High、Shad、Satu 四项微调，范围为 −5 到 +5。黑白 03 不显示 Satu。0 表示底子原样；Amount 等七项只预留数据接口，本轮没有相应的菜单行。

本指南说明主机候选的操作。实体按键时序、LCD 字形和拍后显示仍需相机复核。

1. 打开 Image 配方列表。上下移动到 01–08 会实时预览该配方。`>` 表示已核对的应用中配方，`*` 表示这次通电中调过数值。原生小圆点仍与光标同行，配方状态看文字标记。
2. 在配方行按 DISP，打开配方卡。卡上两项一行；在参数行按 DISP，进入逐项列表，再按 DISP 进入数值页。
3. 数值页上键加一档，下键减一档。+5 在上，−5 在下。进入时光标落在当前值。`Cont   0` 的零没有正负号；`Cont! +5` 和 `Cont! -5` 的 `!` 表示已到边界。
4. 数值页按 DISP 返回逐项列表。逐项列表的第一行、配方卡的第一行均用 `<` 表示返回，在这一行按 DISP 返回上一层。
5. 在配方卡的 Default 行按两次 DISP，把当前配方的所有档位归零。第一次显示 `Sure?`；中间按上下键会取消确认，即使已经在端点也会取消。
6. OK、ADJ 和半按关闭叠层，保留当前已核对的效果。没有取消效果的退出键。要撤销微调，用 Default 或逐项调回 0。

L1 的逻辑顺序是八个配方、` DISP:Tw`、` MyRec`。提示行按 DISP 打开当前应用中配方的卡，不改变效果。MyRec 按 DISP 进入分组。

所有自有视图的原生行数固定为八行。超过八项时窗口重绑文字；到逻辑首尾后停止，不循环。不足八项时补空白行，空白行不能选中；方向键在最后一个有效项目处停住。原生首尾循环产生的移动由 DAT 消化。

`MyRec` 的条目随 DAT 一起装入，数据源只读。分组显示各底子的数量，进入组后最新序号在上。空组显示 `None`，在这一行按 DISP 保持原页。仅进入组不改变效果，移动到条目或在条目上按 DISP 才预览。条目可打开配方卡和临时微调，但相机上没有 Save、Copy、Delete。临时微调只留在本次通电的 RAM 中；重新开机后，条目恢复 DAT 中的原值。开机不自动应用上次条目，初始为纯 04。

每份 DAT 最多有 32 个用户条目。名字由工具生成，例如 `FCC*001`；`*` 表示相对底子有非零档位，`-` 表示底子原样。序号在每个底子组内从 001 递增。重建清单会重新编号。

| 代码 | 底子 |
| --- | --- |
| GRP | 01 GRPos |
| GRN | 02 GRNeg |
| HCB | 03 HC BW |
| STD | 04 Std |
| FCC | 05 F-CC |
| FCN | 06 F-CN |
| LCH | 07 L-Chr |
| LVI | 08 L-Viv |

紧凑格式的字母按 UI v2 设计保留。当前卡上只出现 C、H、S、V。

| 字母 | 项目 | 本轮 |
| --- | --- | --- |
| C | Cont，对比 | 可调 |
| H | High，高光，原 HiLt | 可调 |
| S | Shad，阴影 | 可调 |
| F | Fade，褪色 | 接口保留 |
| V | Satu，饱和 | 彩色可调 |
| W | Warm，暖冷 | 接口保留 |
| T | Tint，偏绿 | 彩色接口保留 |
| P | Splt，分离 | 接口保留 |
| A | Amt，强度 | 接口保留；r2 每配方 20% 或 25% 刻度尚未接入 |
| G | Filt，滤镜 | 黑白接口保留 |
| T | Tone，色调 | 黑白接口保留 |

在 Mac 上生成用户条目

工具只用 Python 标准库。命令从仓库根执行，输入为 gen 124 DAT，输出必须是 `local/` 下尚不存在的新文件。生成不会改动输入 DAT。

```sh
/usr/bin/python3 -I -B firmware/engine_v46_ui/user_entries.py check firmware/package_v36_g124/SD_ROOT/GXRCE.DAT
/usr/bin/python3 -I -B firmware/engine_v46_ui/user_entries.py list firmware/package_v36_g124/SD_ROOT/GXRCE.DAT
/usr/bin/python3 -I -B firmware/engine_v46_ui/user_entries.py build firmware/package_v36_g124/SD_ROOT/GXRCE.DAT --manifest research/g124_ui_v2/user_entries_example.json --output research/g124_ui_v2/local/my-export/GXRCE.DAT
```

清单可用 JSON，也可每行写底子编号和项目值。以下两种写法等价。

```json
{"entries":[{"base":5,"levels":{"Cont":1,"High":-1,"Shad":2,"Satu":-2}}]}
```

```text
5 Cont=1 High=-1 Shad=2 Satu=-2
```

省略的项目为 0。黑白 Satu 非零、当前四项的 ±6 到 ±9、以及七个预留项目的非零值都会被拒绝。本轮 `Amt` 只接受 0，表示 100%，不能据此输入其它百分比。r2 的每配方刻度还未导入。

生成工具验证现有 CRC 和数据绑定，更新用户段、其配方绑定、载荷 CRC 和头部 CRC，保持文件长度、引擎和 BSS 位置不变。新 DAT 的 SHA256 会改变，复审应以实际生成的文件为对象。

错误码

锁定时第一行显示八字符短码，例如 `ERR 0ABC`，其余七行为空白。方向键和 DISP 不再发起通信。OK、ADJ、半按可关闭叠层；重新打开仍显示 ERR，关机再开才清除锁定。ERR 表示本次补偿未能确认完整状态，不表示图像效果已恢复。

短码无损编码原来的 E、S、P、QQ，不需要在屏上显示长句。解码命令如下。

```sh
/usr/bin/python3 -I -B research/g124_ui_v2/decode_error.py 'ERR 0ABC'
```

| 字段 | 映射 |
| --- | --- |
| E | 1 为 H01，6 为 DISP，7 为退出，8 为方向键。编码时依次映射为 0、1、2、3。 |
| S | 0 IDLE，1 T，2 ROWS，3 SETTINGS，4 PREVIEW，5 COMMITTED，6 BROWSING。 |
| P | 0 OK，1 REJECTED，2 UNCERTAIN，3 STALE，4 IO，5 FAULT。实际锁定仍由原规则决定。 |
| QQ | 本次通电 RPC 序号的低八位，解码后以两位十六进制显示。 |

码值是 `(((E索引 × 7 + S) × 6 + P) × 256 + QQ)`，转为四位大写 36 进制，左补 0，再加 `ERR `。

H01 不能核对且没有锁定时，仍回退到原生列表，不显示 Busy、Retry 或未核对的应用标记。下次成功打开并完整核对后，才恢复配方列表。
