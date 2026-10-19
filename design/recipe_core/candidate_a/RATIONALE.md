# Candidate A：独立定长槽记录

## Problem

目标是给 A12 50mm 提供 16 条命名配方，切换时只交付 13 个颜色值，保留 Picture Quality、曝光、对焦和原厂 JPEG+DNG 流程。相机字段、菜单 ABI、代码空间和恢复入口未知；现有 My Settings 会恢复 288 字节完整拍摄状态，不能成为颜色切换接口。当前交付只能是宿主可编译、可验证的 C 核心。

## Usage (caller's view)

菜单每次只读需要显示的槽，不持有整库：

```c
RecipeSummary row;
RecipeStatus s = recipe_get_summary(core, visible_slot, &row);
menu_draw_recipe_row(visible_slot, s, s == RECIPE_OK ? &row.name : 0);
```

选择配方时，损坏记录不会触及相机状态：

```c
Recipe selected;
if (recipe_load(core, selected_slot, &selected) == RECIPE_OK) {
    a12_apply_13_image_values(&selected.colors); /* 未来的窄适配器 */
}
```

编辑名称或颜色后，只保存该槽：

```c
Recipe edited = editor_result();
RecipeStatus s = recipe_save(core, selected_slot, &edited);
menu_show_save_result(s);
```

## Shape

每槽一个私有 64 字节记录，16 槽的记录载荷共 1,024 字节，不含文件系统元数据。记录使用新的 8 字节 magic `GXRRCP01`，文件扩展名和路径由平台存储端口决定，绝不使用 `.IFO` 或 `MY SETTING CARD`。私有布局为：magic 8、版本 1、槽号 1、flags 1、名称长度 1、名称 32、颜色值 13、保留 3、CRC32 4。flags 和保留字节在 v1 必须为零；记录内槽号必须等于请求槽，交叉复制或错误路径会被拒绝。

公共接口只有 `recipe_get_summary`、`recipe_load`、`recipe_save`。它隐藏路径、记录字节序、magic、CRC、短读写和写后校验；调用者只能得到名称与 13 个字节，无法传入完整相机配置指针。名称编码暂不声明，颜色值也只表示合成字节。白平衡不在 v1 类型中，版本字段仅为以后定义新 codec 留入口，没有通用扩展字段。

模块图：

```text
menu/editor -> recipe_core.h -> recipe_core.c
                                  |-- recipe_record.c       (私有64字节codec)
                                  `-- recipe_storage_port.h (私有单槽read/write)
host tests  -> fake_slot_store.c   (16个互不重叠的64字节单元)
```

平台端口只提供“按槽完整读/写一个记录”，不提供 rename、fsync 或任意路径访问。`RecipeCore` 是平台或宿主测试夹具持有的静态不透明对象，不增加业务入口。核心无堆分配、无整库缓存；32 位目标上常驻上下文预算不超过 16 字节，每次操作只需一个 64 字节记录缓冲，栈预算上限 128 字节（不含调用者输出）。相同输入编码成相同字节；保存后重读并完整解码。核心每次只向一个槽发出 I/O，适配器契约要求槽地址互不重叠；介质级故障不在隔离保证内。断电可能损坏当前槽，损坏槽永不应用。

## Synthesis decision

候选 A 提议以“单槽文件、按需读”为基线。它与整库单文件方案保持结构差异；最终是否采用由综合阶段决定，本候选未吸收其他 runner 方案。

## Tradeoffs accepted

- 接受菜单绘制时发生多次小读取，换取零整库 RAM 和单槽故障隔离。
- 接受断电可能损坏正在写的一个槽，换取不假定 rename、fsync 或原子替换。
- 接受 v1 没有白平衡，换取公共 API 无任意配置写入口。

## Alternatives considered

- 单个整库文件：一次读可降低菜单 I/O，但一次损坏或覆写影响 16 槽，并需要约 1 KiB 整库缓冲；接口还要暴露批量提交策略，因此落选。
- 扩展原厂 My Settings `.IFO`：可借现有 I/O，却会耦合六槽上限和完整拍摄状态，无法保证只改颜色，因此落选。

## Open questions and risks

- 相机文件 API 能否可靠创建 16 个独立记录，且短写、卡满和拔卡分别返回什么？
- 菜单名称最终使用哪种编码，32 字节是否足够显示目标语言？
- 13 个颜色值的地址、取值范围和 A12 50mm 调用 ABI 确认后，是否仍能保持单一窄适配器？
- 目标编译器下 CRC32、codec 和三个入口的实际代码/栈尺寸是否落入尚未确认的固件空间？

## Next implementation step

先用宿主 clang 实现私有 64 字节 codec 与 16 单元 fake store，验证槽隔离、确定性编码、截断/位翻转/错槽记录均不产生可应用的 `Recipe`。
