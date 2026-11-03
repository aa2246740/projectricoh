27 条历史记录逐条判断。这里只认定本轮主机指令模型中的行为；原记录 OBSERVED 不自动等于产品通过。外层文件名保留旧记录编号，实际 DAT 逐条核对为 gen 135。

| 单元 | 历史条目 | 行数 / mode | RPC / W | 判断 | 依据 |
| --- | --- | --- | --- | --- | --- |
| 50mm | deferred_adj_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | deferred_confirm_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | deferred_confirm_recovered | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | deferred_direction | 7 / 10 | 1 / 0 | PASS | 列表已撤下；方向键由原生菜单处理，不把原生 mode 10 当作软件 06。 |
| 50mm | deferred_disp | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | deferred_half_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | deferred_half_recovered | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | deferred_raw_half_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 50mm | partial_reset | 8 / 1 | 805 / 253 | PASS | 重开先恢复已确认 05 的九行和 T，再发布八行；不能沿用旧数据字节期望。 |
| 28mm | deferred_adj_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | deferred_confirm_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | deferred_confirm_recovered | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | deferred_direction | 7 / 10 | 1 / 0 | PASS | 列表已撤下；方向键由原生菜单处理，不把原生 mode 10 当作软件 06。 |
| 28mm | deferred_disp | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | deferred_half_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | deferred_half_recovered | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | deferred_raw_half_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| 28mm | partial_reset | 8 / 1 | 803 / 253 | PASS | 重开先恢复已确认 05 的九行和 T，再发布八行；不能沿用旧数据字节期望。 |
| mount | deferred_adj_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | deferred_confirm_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | deferred_confirm_recovered | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | deferred_direction | 7 / 10 | 1 / 0 | PASS | 列表已撤下；方向键由原生菜单处理，不把原生 mode 10 当作软件 06。 |
| mount | deferred_disp | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | deferred_half_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | deferred_half_recovered | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | deferred_raw_half_busy | 7 / 1 | 1 / 0 | PASS | 待处理期间撤下软件列表；确认、DISP、ADJ 或半按均不得重新写入配方。 |
| mount | partial_reset | 8 / 1 | 803 / 253 | PASS | 重开先恢复已确认 05 的九行和 T，再发布八行；不能沿用旧数据字节期望。 |

半按记录只证明模型入口处理；未验证拍摄、RTOS 调度或照片。H07 父层问题及首次发布前窗口仍分别保留，不由这些记录关闭。
