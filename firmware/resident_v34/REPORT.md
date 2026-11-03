停在 P1，原因是 resident 放不下。当前源码最小 payload 为 8976 B，加 256 B root 共 9232 B，超过原 8340 B 窗口 892 B；要保留 200 B 余量，还须回收 1092 B。P1 未通过，P2–P6 未启动，没有可刷的 v3.4、full-r10 或 SD 包。

2026-10-25，仅主机开发。写入前核实指定 UUID、可写 APFS 和 df，剩余约 1.3 TiB。保护输入 37519 项，排除 decisions.tsv，最终核对见 [protected-final.json](local/protected-final.json)。写入仅限 resident_v34/image_v34；未访问相机或卡文件，未刷写、安装依赖、启动子代理、sleep/轮询或提交 Git。

草稿改动如下，不能据此认定产品已通过。

- [abi.h:26](resident/abi.h#L26)、[resident.h:19](resident/resident.h#L19) 定义独立 entry/session 权限、24 B token、quarantine 和 ready/mode 位；root 仍为 256 B，lease_inverse 移到 240，pins 保持 244。
- [permit.c:29](resident/permit.c#L29) 一次消费 token；[permit.c:43](resident/permit.c#L43) 在 H40 观察有序初始化、单位/链路/模式/S/heap 变化及暖重入，撤销过期许可。只读固定原生状态，不调用 loader 或文件桥。
- [build.py:86](resident/build.py#L86) 生成 28 B H40 桩，分别续行到 0x202B115C 和 0x202B1364；[hooks.c:34](resident/hooks.c#L34) 在原钩子过滤前分派 H40。H09 直接返回，不改 packet。
- [hooks.c:38](resident/hooks.c#L38) 在 token 消费后检查 CTL，早于 loader；[permit.c:115](resident/permit.c#L115) 仅完整、CRC/EOF/close/SD 身份都通过的 OFF 锁定停用。无文件、不可读或无效文件仍启用。
- [loader.c:81](resident/loader.c#L81) 锁存拒绝或未知卡源；service 和 adapter 的隔离仍待 P2，R33-01 尚未关闭。[resident.c:22](resident/resident.c#L22) 复用 session 的分配/lease/header 检查，保留代码采样、unit 和 UI 检查。
- [build.py:67](resident/build.py#L67) 轮换新 ABI/build 身份及三枚 ISO100 pins：f09fe7b4 / fb3fbcb2 / 95f3dca9。ISO100 引擎格式和行事务未实施。

尺寸由实际失败 map 读取，见 [budget.json](local/budget.json)。基线重编仍为 7800 B。首版 9560 B；收缩后最终 Os/Oz 均为 9280 B，Oz/LTO 为 8976 B，关闭内联的 Oz/LTO 为 9220 B。最终配置均触发 [resident.ld:22](resident/resident.ld#L22) 的 200 B assertion 和 root overlap；root/pins 大小、禁全局可变区及重定位断言未报错。没有放宽窗口或输出失败链接的产品 ELF。

已核实的局部检查见 [results.json](local/p1-checks/results.json)。ASan/UBSan 的 117 例、10966 次断言覆盖三单元许可、缺 token 零边界调用、一次消费、边沿/错序、epoch 变化、暖重入、wrap 和 CTL 错误。断言数包含替身地址范围检查。H40 相同汇编对象的隔离 ELF 跑了 524 组，核对全部通用寄存器、LR、PSW、SP、f[2..16]、原生 SP=f+17 和两条分支。IRQ helper 从编译字节穷举 65536 组；两份 4 KiB 空日志模板解码通过。

这些检查没有执行完整 resident 或引擎。H40 的 C observer 在机器码检查中为替身；C 检查手工提供分派坐标，不能充当从 state0 到 constructor/stores/push/render 的连续重放。P5 基础矩阵、旧反例和 ISO100 X/V/W 故障注入均为 0 次。没有相机启动、堆水位、LCD、持久化或照片证据。

用户行为目前只验证了许可/CTL 局部合同。目标是启动不加载扩展；真实 Image Settings 人工入口取得许可；移动光标不应用，OK/Fn2 才应用；GXLS 只恢复待选光标。这些 engine 行为仍待 P2。默认启用，ON 文件可省；有效 OFF 停用至下次冷启动。OFF 文件若 open/read 返回 -1，不会被识别，退路是不进入 Image Settings，或另行获批后回刷 Stage2l/官方。当前模板不适用于 v3.2/v3.3。

黑匣子仅交付格式与空模板，尚无写日志功能。目标文件为 /ATA1/GXRBX0.BIN、GXRBX1.BIN，安装和发布回执分开；安全点 flush 和 H40 的 NATIVE_COMMITTED 收据导出仍待 P2。RPC 仅在明确应用、token 和 ready 通过后准许，不采用默认 RPC_BOUND_PROVEN=false 拦截。原生 0x2009005C 的参数为 send=5000、ack=0x7A120，时间单位和所有等待路径的实际上界仍未知。

后续只有收缩成功才能恢复实现，不能把估计当作已腾出的空间。

- 保持窗口，把 token/ready 逻辑改写得更小，或合并更多重复边界检查。相对当前最小配置，净目标至少 1092 B；尚无满足目标的实测版本。
- 把适合迁移的加载后逻辑移到容器，再扣除新增桥和检查的成本，净收益仍须至少 1092 B。标准编译的 hooks 约 1140 B、loader 约 2291 B，只是候选范围，不代表这些字节都能迁出。未找到、未采用第二代码窗口。

完整摘要在 SHA256SUMS。已从实际文件复核基线和局部产物：

```text
v3.3 resident ELF  51e44b50862afa74c18920c001cb47d1f65210462d82da2925e67c16438cce08
v3.3 ilaunch3     7f01e7535a0c3ebe84bf2d7a060590b24b19f0e1065afc7fe1762973f3f08546
full-r9 / 111     7fc825755406c8dccd49d49277098afedd478ec45260d53893bf0c55d0ab6e7b
H40 隔离证明 ELF  6f55ad2f24ac175cfe58d1b46abf32da7ed42e0b3e9a61bea5c8ef3183334fad
P1 主机测试程序   582a9f9ea325bd27f9971c840f067c9c40067672c76fd35cb7927a59fabdd98a
OFF 模板          c9780dc432d4d3be6553eee8146668a78ef02a5eeae4853db5d988f149ea08de
ON 模板           d2f1b75f37b38508106372a2dd3fa6e3ce764eb58f15bb12ef4f7557443e69d2
空日志模板两份   eef8f137893e16898de4a3fef8d2bdb3bcdac27c7cbe3c7475e154adadcc2b57
```

复跑尺寸失败是预期结果，exit 2。Python 使用系统隔离模式，工具链与指定基线相同，没有安装工具。

```sh
/usr/bin/python3 -I -B firmware/resident_v34/build.py --label review-size --profile lto
/usr/bin/python3 -I -B firmware/resident_v34/verify_p1.py
/usr/bin/python3 -I -B firmware/resident_v34/finalize.py verify
```

首刷清单目前不可执行。后续先取得 ≥200 B 的真实链接和完整 P2–P6/独立审查；核对新镜像、full-r10、28 个官方兄弟文件及恢复包哈希；再由用户另行授权，先验三单元原厂启动、更新入口可取消及有效 OFF，再分阶段验人工进入、应用和收回日志。本轮没有可供该清单使用的文件。
