# v3.10 薄机身研究原型

从 resident_v310_proto 的默认中性版本复制。默认源码保留两个机内 DAT 来源；单机内副本与仅卡只用于独立测量和主机夹具，不替换默认源码。

真实窗口链接和结果见 research/v310_resident/REPORT_R2.md，薄 ABI 见 research/v310_resident/ABI.md。此目录没有相机安装包，不含测试 DAT。

在项目根目录设置指定 TMPDIR 后构建三种变体：

```sh
TMPDIR=/Volumes/Workspace/Scratch/tmp/projectricoh/v310-resident-r1/ \
  nice -n 10 /usr/bin/python3 -I -B firmware/resident_v310_thin/resident/build.py
```

脚本核对指定 APFS 卷和冻结输入，使用真实 M32R 工具链及未改动的 resident.ld。临时编译放在 scratch，研究产物写入 research/v310_resident/evidence_r2。

BOOT_RUN=0x101。启用完全由 DAT 决定；未经复审和现场验证的发布 DAT 必须返回“不支持”且零颜色写入。H50/H51 只负责一次性派发，H52 只根据固定 dirty/guard 拒绝 C01 原始快门请求。完整颜色事务、MY 零写和未闭合的消费者顺序由 DAT 后续实现与复审处理。
