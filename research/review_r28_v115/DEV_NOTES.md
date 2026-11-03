本目录的两处开发错误已修正，没有改候选或降低产品断言。

1. delta_audit.py 的初版误把 Standard selector 写成 4。实际 canonical record 的 selector 为 1，和 114 一样；4 是 core 中另一条可调模式的分支。核对 record 和原生枚举后改为精确断言 1。
2. freeze.py 初版沿用了 114 审查对 artifacts/downloads 的全目录枚举，误纳入并发 worker 的活动文件。先捕捉到 artifacts/downloads/bridge_public_r1 四个新增下载资料/回执，后来又捕捉到三个新增 DPReview GR IV 文件。七条路径均不在原清单内，原先冻结的这些文件并不存在，故不是冻结输入 drift。它们不是官方 Ricoh 输入，不被任何审查脚本读取，也不在用户指定冻结域内。初次修正只排除 bridge 目录仍过宽，因此最终改为精确包含官方 gxr-151.zip 和 gxr_vup，保留其它所有指定冻结域与实际证据。没有重建或替换原始冻结清单，也没有接纳任何候选、官方、设计或备份的新 SHA。PROTECTED_DRIFT.json 保留第二次误报的 hashes；初次记录被原检查器覆盖，只能从工具输出保留其四条路径，另存 first_foreign_drift_paths.json，未伪造当时的 after hashes。建记录时初版误假设四条路径原来存在，KeyError 后用 before=null 如实表示新增。后续误报文件不再覆盖已有记录。

prepare_replays.py 是本次适配的可重跑生成器。它从冻结的 114 独立审查脚本派生输出到本目录，变更限于候选路径、代次、输出位置及 qlaunch 已有八行的预期；113 原生断言仍在历史夹具运行。rebuild.py 的数据段复用最终 DAT，引擎和 services archive 则从冻结源码重新编译、链接并逐字节比较。数据段由独立的 delta_audit.py 另行解包核对。
