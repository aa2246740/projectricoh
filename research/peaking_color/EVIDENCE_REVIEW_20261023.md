现有证据不足以断言 GXR 硬件“绝对不能”给峰值描边换色。C-red 与 C-mode1 已否定所测的三字节注入方案；软件检测边缘后叠加彩色轮廓尚未被排除，但也没有证据证明它能在 GXR 上实时运行。目前没有可交付的彩色峰值方案。

2026-10-23。对象为 GXR 机身 1.51、GR LENS A12 50mm 单元 1.51。以下相对路径均以 `/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh` 为根，链接指向本轮读取的实际文件和起始行。

本轮只读复核既有证据，唯一新增文件为本报告。写入前两次核对 `/Volumes/Workspace` 为已挂载、可写 APFS，Volume UUID 为 `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`。未访问 SD 卡或相机，未发送 RPC，未构建、安装或运行探针，未修改固件、原报告、校验清单或 `decisions.tsv`。用户已使用 MODE1，不建议再切 MODE1 或重做染色实验。

真机结果已经覆盖两个模式，旧报告的 MODE1 缺口已经关闭。

| 已执行方案 | 本轮独立复算的寄存器结果 | 既有真机记录 | 能支持的结论 |
| --- | --- | --- | --- |
| C-red，修改 MODE2 选择器及两个 D 槽 | 在对应 MODE2 基线中仅改变 `0xF0353324`，结果为 `0x0060A040`。 | MODE2 整幅偏紫，描边仍白。见 [decisions.tsv:317](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/decisions.tsv:317)。 | 这组写入不能把 MODE2 白边改成预期红色。 |
| C-mode1，实际修改 MODE1 自己的选择器 | 在对应 MODE1 基线中仅改变 `0xF0353324`，结果为 `0x0000A040`。 | MODE1 整幅偏紫、描边仍白；MODE2 为默认灰底白边。见 [decisions.tsv:326](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/decisions.tsv:326)。 | 同一色度值注入 MODE1 也失败，不能再把“尚未给 MODE1 注入”列为下一步。 |

实际写入表分别见 [module_color.S:107](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/peaking_probe/module_color.S:107) 和 [module_color1.S:115](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/peaking_probe/module_color1.S:115)。旧独立报告 [REPORT.md:7](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/REPORT.md:7) 把 MODE1 注入列为首选时，C-mode1 尚未执行；该建议现已过时。

上述真机结果来自用户反馈及决策记录，本轮没有复验或重新读取照片。它们强烈支持“所测配置下，该三字节量影响全局底色，不能独立指定描边颜色”。两个取值并未穷尽全部编码和控制位，也未证明 ISP 的内部公式。画面偏紫、白边保留，仍可由亮度过冲后的裁剪或独立合成等机制解释；不能把“白边一定由独立图层合成”当成已观察事实。预期红色却得到紫色，也说明原先 type 32 通道顺序、符号和尺度假说尚未闭合。

`research/peaking_probe/操作说明.md:22` 的“C 未生成”是早期状态。较新的 [verify.json:65](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_probe/local/verify.json:65) 和 [verify.json:109](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_probe/local/verify.json:109) 已列出 RED、M1；文件开头的 `HOST_STATIC_AND_REPLAY_ONLY`、`camera_executed=false` 描述校验脚本自身的证据级别，不能代替或否定后来的真机记录。

“硬件绝对不能换色”的几个支撑理由不成立。

1. “只有 20 个寄存器不同”是模式比较结果，不是所有硬件能力的清单。本轮复算 MODE1、MODE1 请求加一配置、MODE2，各 251 个寄存器均与保存结果相同，MODE1/2 确实相差 20 个。但完整重构先把其他 F 字段填零，用于隔离模式差异，见 [analyze.py:354](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/analyze.py:354) 和 [原方法说明:21](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/REPORT.md:21)。模式不变的字段仍可能含路由或使能位；没有芯片手册就不能称其全为亮度量。例如 `jlaunch3` VMA `0x20116868..0x20116874`、文件偏移 `0x0CBA68..0x0CBA74` 复制 F 的首个 halfword，作为 `0xF0353000` 的配置源，见 [full-packer.disasm.txt:8](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/evidence/full-packer.disasm.txt:8)。零基线不是相机 RAM 读数。

2. 斜坡两条 halfword 通道相等，不能证明“只有一条亮度通道”。完整 packer 在 VMA `0x201179A0`、文件偏移 `0x0CCBA0` 读取 `F+0x25`；选择号为零时取 `T+0x2400`，否则取 `0x2012EF68` 的索引行。数据打成九个 word，送往 `0xF03532F0..0xF0353310`。见 [取源及打包:2](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/evidence/ramp-and-four-row-block.disasm.txt:2) 和 [硬件写入:8](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/evidence/ramp-and-block-hardware-writes.disasm.txt:8)，后者 store 位于 `0x202579D8`、文件偏移 `0x20CBD8`。其他出厂行含不相等的坐标对，例如 `(32,64)`，更像传递曲线的输入、输出节点，见 [既有分析:33](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/REPORT.md:33)。本轮仅在 Python 字典中改变该 T 源，确实只改变对应寄存器。因此“不可写”不成立，但其硬件含义仍未知，不能反过来声称它就是色度表。

3. 所谓“固定 YCbCr→RGB 矩阵”实际是来源可选的数据块，尚无矩阵语义证据。`0xF0353340..0xF03533FC` 共 48 个 word，完整 writer 在 `0x20257A20..0x20257A44`、文件偏移 `0x20CC20..0x20CC44` 循环复制。`F+0x29=0` 时，前 24 个 word 来自 `T+0x0B4C/+0x0B64/+0x0B7C/+0x0B94`；后半块由 `F+0x2A` 选择。见 [T 取源:176](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/evidence/ramp-and-four-row-block.disasm.txt:176)、[后半块:1338](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/evidence/full-packer.disasm.txt:1338)、[48-word 写入:30](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/evidence/ramp-and-block-hardware-writes.disasm.txt:30)。本轮复算 `F+0x29=0` 条件下，仅改变 T 源 `+0x0B5C`，即可只把 `0xF0353350` 从 `0x80808080` 改成 `0x40808080`。这证明可写数据流，不证明能染边；`0x80` 也不能脱离寄存器定义就叫作“中性色度填充”。

4. `0xFF` 和 `0x00FF00FF` 不能单独证明“不可更改的白色”。两模式存在这些相同值，但相关路径没有给出 RGB 分量或白色编码定义；原研究已明确将限幅、强度列为推断，见 [focus_assist/REPORT.md:133](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/focus_assist/REPORT.md:133)。现有配置代码没有暴露完整的边缘检测、色度和裁剪公式。

5. “只能重刷，现有协议无法碰到 MMIO”也过强。X 的通用页分支在 `0x2024314C..0x20243154`、文件偏移 `0x1F834C..0x1F8354` 保存解析出的页基址；地址上可到 `0xF0350000`，见 [x-page-addressing.disasm.txt:72](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/evidence/x-page-addressing.disasm.txt:72)。W 的相关 helper `0x20242D98..0x20242DC4` 做的是 32-bit 读改写，见 [w-access-widths.disasm.txt:6](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/local/independent_edge_colour_review_20261023/evidence/w-access-widths.disasm.txt:6)。当前探针 helper 自己只选 T、D 两页，见 [pk_core.S:103](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/peaking_probe/pk_core.S:103)。协议地址可达不等于安全可用，更不等于找到了颜色位；完整 apply 还会覆盖直接 MMIO 值。本报告不提供新的寄存器试写方案。

所以 [decisions.tsv:320](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/decisions.tsv:320) 的 `structurally pure-luma` 和“同类 T/D 写入均不可能染边”超出了证据。更准确的判断是：已试常量路径失败，已追 CPU 路径没有发现独立描边颜色入口，剩余 ISP 字段尚未解释。

其他相机能有彩色描边，是因为它们提供了对轮廓单独着色的功能。[FUJIFILM 官方说明](https://digitalcamera-support-en.fujifilm.com/digitalcameraengpcdetail?aid=000008350) 的 “MF Assist: Focus Peaking” 将其描述为强调高对比轮廓，并可选白、红、蓝；[Sony DSC-HX90 官方指南](https://helpguide.sony.net/dsc/1510/v1/en/contents/TP0000576727.html) 的 “Peaking Color” 明确列出红、黄、白轮廓。两份文档说明产品行为，不披露 CPU、DSP 或 ISP 的内部实现，也不证明 GXR 有相同的颜色开关。

软件实现可以先根据图像亮度的局部高频或梯度生成边缘 mask，再只在 mask 覆盖的位置叠上指定颜色。这是可研究的替代设计，不依赖原厂白边是否由纯亮度锐化产生。它也不是把现有画面中的所有白像素替换成红色，后者会误染真实高光和 UI。梯度只指示局部对比度，噪声、纹理和曝光都会影响结果，不能把任意边缘检测器直接当作精确合焦判断。

GXR 的软件路线尚未被排除，具体缺口仍在显示输入和输出接口。

- 现有原厂链是 `0x2F05 → 0x2010C67C → 0x2011659C → 0x20115E80 → 0x20255740`，恢复的是单元配置与寄存器写入，没有发现逐帧扫描像素的 CPU 循环。见 [focus_assist/REPORT.md:102](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/focus_assist/REPORT.md:102)。这只能说明当前追到的实现方式，不能禁止另写软件算法。机身 P 模块和镜头单元是不同 CPU，不能从机身直接调用单元 VMA 来替代通信。
- 机身 `ilaunch3` VMA `0x20218D44..0x20218D84`、文件偏移 `0x1CDF44..0x1CDF84` 确实出现 320×240、640×480 的分支，见 [body-display-dimensions.disasm.txt:11](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/focus_assist/body-display-dimensions.disasm.txt:11)。它不证明 live-view 缓冲地址、像素格式、stride、双缓冲所有权、缓存/DMA 同步或可用 overlay 层，也没有证明原厂边缘 mask 能导出给 CPU。
- 旧预算采用 50–200 MHz、每像素 50–100 cycles 等假设，见 [peaking_color/REPORT.md:309](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/peaking_color/REPORT.md:309)。160×120、10–15 Hz 是建议起步档，不是 GXR 测出的性能上限。现有材料既不能保证全分辨率实时，也不能证明只能运行该低分辨率档。
- 预览与拍摄共用 parser `0x20197F68`，见 [focus_assist/REPORT.md:85](/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/focus_assist/REPORT.md:85)。新软件需要专属显示输出或已证实的显示层，不能默认共享图像缓冲只供屏幕使用。

在用户不再试染色的边界内，后续研究可以按下面的顺序收敛。这是研究路径，不是本轮新增实现。

| 路径 | 可以只读推进的工作 | 在什么证据出现前不能承诺成功 |
| --- | --- | --- |
| 先恢复机身显示接口。 | 从 `ilaunch3:0x20218D28` 及其调用者继续追 live-view 输入、绘图/合成输出，记录地址来源、格式、stride、生命周期和帧完成事件；查是否存在可读取的硬件边缘结果。 | 未恢复输入和专属显示输出前，不能称“加个 OSD 就能完成”。 |
| 再评估新边缘检测加彩色叠加。 | 若有可读 mask 则研究复用；没有则设计亮度边缘算法。用已有离线图像检验 mask、噪声和轮廓稳定性，区分算法效果与设备性能。 | 离线效果不能证明 GXR 的 CPU 余量、延迟、帧同步、照片隔离或户外可读性；这些最终仍需设备验收，用户当前不接受这一步。 |
| 保留 ISP 静态线索。 | 复用上述 T 源、完整/快速 writer，比较原厂其他参数组的生产者与消费者，寻找局部边缘与颜色控制的明确联系或公开寄存器定义。 | 可写、表尾像颜色、两模式值相同，都不足以推出字段语义；没有明确证据就保持未知，不再靠试染色推进。 |

本轮校验只证明输入和静态运算可信，不证明 ISP 像素行为。

- 29 个官方输入通过现有 `research/focus_assist/official-inputs.before.sha256` 校验。
- 将 `research/peaking_color/local/evidence/`、`local/independent_edge_colour_review_20261023/evidence/` 和 `research/focus_assist/` 中共 82 份反汇编摘录的 8,585 行指令逐行对照官方映像，文件偏移、VMA 映射和机器码全部匹配。重叠窗口计入行数，不声称覆盖 8,585 条不同指令或整个固件。
- 用 `python3 -I -B` 导入已有 `analyze.py` 的 `Image`、`Listing`、`Arithmetic`、`fields`、`script`，未调用会生成文件的 `main()`、`save()` 或 `excerpt()`。三个保存配置的 251 个寄存器逐项一致；两个既有模块及 T 源变化仅在 Python 字典里复算，没有向硬件写值。
- 三个研究目录及 `decisions.tsv` 共 130 个既有文件的内容哈希、大小和修改时间均与本轮读取前一致，唯一新增项为本报告。旧 `SHA256SUMS` 保持原样，本报告未加入其清单，也未声称重跑通过原交付包的完整校验器。
- 正式输入身份为 `jlaunch3` SHA-256 `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`、`jlaunch8` SHA-256 `92554edf413e0090550f192973d0555ee13770cee0764802be209f491f2c424f`、`ilaunch3` SHA-256 `da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7`。地址不可直接外推到其他单元或版本。
