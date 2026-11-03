### P1-01：首次发布前仍为七行，重入 H08 可写 Image mode，随后八行 04 不再核对该状态

位置为 `firmware/engine_v46_ui/candidate/containers/product/adapter.c:472`、`:474`，`firmware/engine_v46_ui/candidate/containers/product/src/firmware/engine/core/eng_core.c:566`，以及固定 resident `firmware/resident_v36/resident/hooks.c:28`、`:31`、`:70`。八行实际写入在 `firmware/engine_v46_ui/candidate/engine_services/services.c:220`。

从干净模型启动，经官方构造器首次进入 Image 列表。在 DAT `list_bind` 入口、八行尚未发布时，用另一个原生任务执行方向键。此时 activity=8、state=56、inflight=1、PSW.IE=1，但原生仍是七行，`ui_block=0`、`ui_restore[0]=0`。

```sh
/usr/bin/python3 -I -B research/review_g124/cold_reentry.py --tag=-recheck
/usr/bin/python3 -I -B research/review_g124/cold_reentry.py --generation 121 --tag=-baseline-recheck
```

命令在复现 Image 写入时按断言返回 1。无输入控制、八行发布后恢复 IRQ 的控制例另列。

最终 DAT 的向下键反例经过 `native_h08`、`0x20268768` 和 `0x20268774`。resident 将 H08 记为 busy，但 `early()` 因行数不是 8 而没有跳过原生续程。PC `0x20268774` 把 `S+0x36e` 从 1 写成 5，另有 `0x20268798` 的同值写入。重入 RPC 为 0，host UI writes 为 0，Image getter 没有 stub。

外层继续发布八行，光标和圆点均为 4，Image mode 却仍为 5；标准 04 要求的 mode 是 1。九行和 T 仍匹配 04，失败点是原生模式。因此这不是图形闪烁或仅合成 WB 输入的差异。根因是首次会话 `committed=0` 且 `recheck=0`，`validate_live()` 在 `eng_core.c:566` 直接返回成功。确认退出也不核对该模式，模式 5 保留，确认 RPC 为 0。

向上键的最终 mode 仍为 1，但同样经过 Image setter 并写 `S+0x36e`，也不满足不得触及的要求。该例最终配方比较成功不能代替零写入检查。

无重入控制保持 mode=1、八行、光标 4。将同一方向键移到首次八行发布后、恢复 IRQ 的续程，原生 setter 被跳过，mode 保持 1。此前通过的 210 例全部从已经发布的八行视图开始，覆盖不到首次发布前这个七行切点。

gen 121 的首次发布前向下键也留下 mode=5，向上键也有同值写入。这是继承缺陷，不是 gen 124 新增回退；本轮明确要求检查发布过渡及完整配方或纯 04，故仍阻断放行。该反例独立执行的是 50mm，没有声称在相机或另外两单元上实测。

影响是首次界面能在未锁定、未报警的状态下指向 04，但原生 Image mode 与 04 不同，并可确认退出。需先处理首次发布前的原生输入和最终状态核对，再复跑该反例。只在已发布八行的入口增加检查不足以关闭本项。

证据见 [独立核查汇总](evidence/cold-publication-verified.json)、[最终 DAT 向下键](local/cold-reentry-final/124-50mm-before_publish-right.json)、[同值写入](local/cold-reentry-final/124-50mm-before_publish-left.json)、[八行后的控制](local/cold-reentry-final/124-50mm-after_publish_restore-right.json) 和 [gen 121 原始对照](local/cold-reentry/121-50mm-before_publish-right.json)。
