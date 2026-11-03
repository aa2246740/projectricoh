`knobs_v2_r2_tables.h` 和 `final.json` 是同一份最终整数表，由 `src/export_tables.py` 生成。`steps.csv` 是便于查阅的展开剂量表。

`units` 的顺序为 jlaunch、qlaunch、l08firm。每个单元有 01..08 八个配方。`recipes` 保存单元编号、配方编号、该配方在 `items` 的起点与项目数；`items` 的顺序就是菜单顺序。

每项包含实际最小档、最大档、默认档、上下端 `!` 标志和完整的 `points`。普通档为整数 UI 档位，剂量是 Q12。Amount 的档位和剂量都是整数百分比，默认 100%，端点是 0%、150%。`amount_step=20` 时，完整序列最后两档为 140%、150%，该短末段也已经单独复验。

C 表的 `points` 是固定容量数组，遍历时只读 `point_count` 个元素；末尾隐式填充不属于档位。JSON 只保存实际元素。

`control` 编号依次为 Amt、Cont、High、Shad、Fade、Sat、Warm、Tint、Split、Filt。控制描述中的 `dose_index=-1` 表示 Amount；其他值是 `KvRequest.dose` 的索引。Warmth、Tint 固定采用矩阵行和，Split 固定采用 T1。最终表没有 Tone，也没有 T1 Warmth、Tint 的对照剂量。

`cap_lower=1` 或 `cap_upper=1` 表示该方向提前到顶，界面仅在对应端点显示 `!`。普通旋钮仍以 ±9 为标称范围，实际可选范围以该项为准。Fade 始终只有 0..+9 十档。03 只有 Cont、High、Shad、Fade、Filt；04 不含 Amount。

`src/menu.c` 和 `src/menu.py` 使用这些表构造请求。非法档位返回错误，不把超限档映射到相同输出。C 入口需要调用者传入与单元和配方相符、已验证的不可变 552 B 原厂条目和配方条目；不解析不可信容器。表内没有原始理光行字节，相关字节只保存在 `local/`。
