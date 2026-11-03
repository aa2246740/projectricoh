g155b 修复说明

来源为完整复制的 `firmware/engine_v64_g155/`。本轮只修订 DAT 的 BOOT 资格规则及本目录构建入口；resident 与 v3.10 机身沿用原件。

`candidate/containers/product/boot_adapter.inc.c` 将 BOOT 上下文统一为 MY 已知、state 5、activity 0。初始上下文不符时回复正常跳过，不写颜色；事务开始后的资格复核仍使用同一规则。Image Settings 菜单的 activity 8 不属于开机待机上下文。

格式、条目布局、记录 v3 和代数 155 不变；重建后 DAT 校验字改变，因此记录必须绑定新 DAT。现有工作室 155 codec 已只读核对解析及逐字节往返一致。报告位于 `research/v310_body/REPORT.md`，构建入口和证据位于 `research/v310_body/fix/`。完整新包位于 `firmware/package_v310_g155b{,_test}/local/SD_ROOT/`。

release SHA-256：`1df64437d83629627fd4ba513b2988a014114f22cf5b184f7347f5437073bcfc`。

test SHA-256：`466bf5b7b523321f804700fc93fb6d53efccfe4006421b5ad462e0da222a1f56`。

是否可以交复审，以 `research/v310_body/REPORT.md` 第一行为准；未上实体相机。
