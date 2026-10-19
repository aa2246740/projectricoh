# 配方核心综合设计

## Problem

用户已授权开发 A12 50mm 的16个独立配方。现有 My Settings 会改动画质、曝光与对焦，且原厂颜色字段、ABI、菜单和代码空间尚未映射。本轮实现一个宿主可测试的配方核心，先证明独立记录和只交付颜色参数的接口；它尚不接入固件。

## Usage (caller's view)

```c
Recipe selected;
if (recipe_read(core, (RecipeSlot){6}, &selected) == RECIPE_OK) {
    /* 将来由已确认的窄适配器接收 selected.colors，当前不调用相机。 */
}
recipe_save(core, (RecipeSlot){6}, &edited);
recipe_delete(core, (RecipeSlot){6});
```

菜单名称也从 `recipe_read` 的结果读取，不增加只转发读取的 summary 接口。调用方只在 `RECIPE_OK` 后使用颜色值；错误或空槽保留原输出。

## Shape

采用独立64字节记录和按槽读取。公共类型见 [recipe_core.h](../../firmware/recipe_core/recipe_core.h)，仅有读取、保存和明确删除三个入口。平台端口是私有 read/write/remove 三个回调，以槽号访问，不暴露任意路径或完整相机配置。宿主 fake store 和后续原厂文件适配器分别持有自己的端口上下文。

v1 私有布局是：magic `GXRRCP01` 8字节、version 1字节、slot 1字节、flags 1字节、name length 1字节、name 32字节、opaque colors 13字节、reserved 3字节、CRC32 4字节大端。CRC采用 CRC-32/ISO-HDLC，覆盖前60字节。unused name bytes、flags 和 reserved 必须为零。空槽以存储端口的“文件不存在”表示，零记录属于损坏。

名称只作为1至32字节存储，不宣称真机可以显示该编码。13个颜色值只是宿主合成表示，不证明原厂字段是单字节，不包含白平衡或通用配置扩展。总记录载荷为1024字节，文件系统开销未知。核心每次只处理一个槽，无heap、无整库缓存。最终保存路径复用一个64字节记录缓冲，并使用临时 Recipe；解码调用还有自己的局部变量。真实目标栈必须包含嵌套调用和平台回调，不能把源代码局部缓冲大小当作目标栈上限。目标代码和栈以实际编译报告为准。

## Synthesis decision

以 [candidate A](candidate_a/RATIONALE.md) 为基线，因为已经发现的原厂文件 I/O 可按长度读写，且本轮无需证明整库 RAM。一个槽损坏时，核心仍可独立读取其他槽；介质故障不在隔离保证内。

从 [candidate B](candidate_b/RATIONALE.md) 保留显式删除、确定性格式和重读验证要求。拒绝其整库CRC、双1024字节缓冲和暂定UTF-8绑定，避免一条记录损坏导致全部配方无法加载，也不提前绑定未知菜单字符集。

按 design-red-flags 审查：A的summary是冗余转发且缺少删除，已替换为明确删除；B的整库工作区和输出副本增加RAM压力，整体校验扩大单槽损坏影响。最终版本不同时支持两种存储方式，也没有通用配置写接口。

## Tradeoffs accepted

- 接受显示16行时多次小读取，减少常驻RAM及损坏影响范围。
- 接受保存失败或断电可能破坏正在写的槽；不会把读回校验写成原子保存或掉电恢复。
- 接受首版宿主核心不含白平衡、颜色语义和真机显示编码，先验证可以独立保存、读取和拒绝损坏。

## Alternatives considered

单库方案隐藏一次加载和批量提交，但每次改动要处理完整快照。当前不存在已证实的整库RAM或原子文件替换能力，因此不采用。扩展 My Settings 的完整记录会绑定六槽结构和画质等状态，不能实现颜色专用接口。

## Open questions and risks

真机文件 I/O 是否能区分不存在、短读和长文件？菜单名称编码是什么？颜色输入如何翻译为原厂参数？独立恢复入口在哪里？这些问题继续由静态逆向与原厂采样解决，本轮不要求用户批准默认设计。

## Next implementation step

实现 freestanding C codec 和三个业务入口，用独立16槽宿主适配器覆盖读取、覆盖、删除、重启式重读、损坏拒绝和只输出颜色值。
