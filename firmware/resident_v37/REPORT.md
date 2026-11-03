resident v3.6 已在主机原生指令验证中关闭 P0-01。交 gen 117 重绑的机身与完整证据见 [image_v36/REPORT.md](../image_v36/REPORT.md)。

build id 为 `b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7`。ABI 为 `d7387c3670059c325186de3af1b3d5c6`，三个 ABI 头文件未变。

[resident.elf](local/resident/build/resident.elf) 为 10672 B，SHA-256 为 `5d66184ce33f280aa370ebfc1753fe74e8ad398f01558406909733cec779acff`。payload 7884 B，代码末尾 0x20054638，root 前保留 200 B。resident.ld:22 未变。

hooks.c 删除 P3 写入和 pack 参数。H07 关闭逻辑保留。H06/H08 在八行早退时写 f[7]=0，并跳到各自 skip。rv_check 故障先判定本次续体，再恢复七行。根校验只做一次，非法根的原有行为保留。

P3 回收 48 B。H08/H06 保护与等价控制流合计增加 52 B，净增 4 B。Host 检查为 PASS_HOST checks=157249，ASan/UBSan 均通过。原生 i–v、vii 与评审基线相同。viii-b、首次发布故障、嵌套 H08 和 H06 均跳过原生续体。主 MENU 完整路径仍受原有系统链表模型阻塞。

本次只写 resident_v36 与 image_v36。没有构建容器，没有访问相机或卡。刷入时必须挂 50mm。恢复固定使用卡 A 的 Stage2l-50mm、50mm 镜头，按住「+ 和回放」开机。
