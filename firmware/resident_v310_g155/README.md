# g155 的 v3.10 resident 模型

复制自 resident_v310_thin。运行时代码仅把 RV_MAX_CODE 改为 69,632 B；保留 H50/H51/H52 与原链接窗口。BOOT 策略在 DAT。构建身份绑定 g155 服务文件，ABI 身份绑定新的上限。

只生成 ELF、bin、替换表与身份资料。构建入口为 research/g155/build_resident.py --variant neutral，使用本轮指定 TMPDIR 和 nice 10。产物在 research/g155/evidence/resident/neutral。

主机模型把 ELF 与替换字装入 RAM，没有创建 ilaunch3 文件。薄 ABI 见 research/v310_resident/ABI.md，g155 的上限和验证见 research/g155/REPORT.md。
