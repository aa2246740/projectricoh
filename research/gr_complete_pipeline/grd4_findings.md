# GR DIGITAL IV 原生模式静态交接

静态确认：`grd4_extract.py` 从原包读取表、UEEF1 脚本、菜单字形/资源与 M32R 分段。所有表号为 **1 起算**，type23 selector 为 **0 起算**。六种菜单名称到 raw mode 的链已闭合：Standard=1、Vivid=9、Hi-Contrast B&W=11、Cross Process=12、Positive Film=13、Bleach Bypass=14。固件资源原文拼作 `Hi-Cntrast B&W`，JSON 保留原文并另列规范名称。

静态确认：canonical still 请求为32..37、48..52、54。以下 tone 行须排除效果25/28及效果27的另选路径；效果24保留行。监视请求16也有单独效果覆盖，不能把本表当作所有请求的最终响应。

| 模式 | still tone A/B 行 | monitor16 行 | main/aux 原始加载行 |
|---|---|---|---|
| Positive Film | 归一化1..9→24..32；中心5→28 | 28 | variant0..3→9..12；T+EEE==1时→25..28 |
| Bleach Bypass | 归一化1..9→15..23；中心5→19 | 19 | variant0..3→5..8；T+EEE==1时→21..24 |
| Standard | 固定 raw3→归一化5→5 | 5 | 普通 packed selector；variant0回退时1或17 |
| Vivid | UEEF1 T+20E4=4→归一化6→6 | 5 | 普通 packed selector；variant0回退时2或18 |
| Hi-Contrast B&W | UEEF1 T+21F0=3→归一化5→5 | 11 | main被gray enum7强制为33；aux在variant0回退时1或17 |
| Cross Process | 对比归一化1..9→1..9 | 5 | 普通 packed selector；中心饱和度、variant0回退时1或17 |

静态确认：普通色表初始化器`0x201221F4`将T+B04..B33的48字节复制到RAM`0x205D3428`。24个BE16为六个0101、六个0202、六个0303、六个0404。读取地址为`RAM+12*variant+2*sat_index`；归一化饱和度1..9映射index0..8。所有36个组合都保留，其中3个读到上述48字节以外，值明确为null。variant0回退仅在`T+BFC=01、r7!=0、Q+5A=Q+5B=0`时成立，不是出厂值声明。T+EEE不在5832次UEEF1写中；`0x2012B998`仅在该字节恰为1时让1..16的主/辅行加16。

静态确认：Positive九档31×u16BE与33×u8曲线全部不等于GXR22行中的任一行。中心是GRD IV第28行。Positive候选主色表9..12/25..28也全部不等于GXR29主色表中的任一行。GRD IV主色表33=GXR28，34=GXR29；辅色表33=GXR26。完整原字节、数值、偏移及SHA-256在`grd4_positive_film_tables.json`与`grd4_mode_mapping.json`。

静态确认：type23有31×u16输入银行和三个33×u16输出银行，已提取每个银行index0..5，共24行。它们全部在GXR原始type23表中有逐字节匹配。Cross Process toning enum1/2/3选择GRD selector2/3/4；三个输出分别对应GXR selector3/4/5。Positive将selector设255，raw packer跳过替换；另有动态生成器将保存的255转换为index5。不能由此声称Positive具有已确定的最终三通道LUT。

静态确认：type28八套14×u16矩阵在`0x2014C818`，与GXR`0x2012D0C0`八套逐行相同。canonical color内层由Q+84选择row1/2，`0x2012B10C`按T+BE0+exposure index的百分数缩放系数3..8。推断：bit11为符号-幅值，单位Q10，row1属于RGB→YCbCr一类的公共颜色空间矩阵。未知：没有找到Positive独立look matrix或sensor CCM。

未知：实际保存的Positive/Bleach滑块、Q+58/59的运行时variant及Q+5A/5B权重、T+EEE生产者、sector/饱和度和混合后的完整type28数值、gain处理后的type23、硬件插值和全链顺序。JSON将最终effective row/LUT设null，不宣称六种模式端到端闭合。

静态确认：最终复跑PASS，核心原表131行、type23另24行、type28矩阵另8行，总163行；4066条反汇编机器码逐条对原件，UEEF1写5832次。没有运行固件、构建或打包，没有相机测试。

复跑命令：

```sh
python3 -I research/gr_complete_pipeline/grd4_extract.py
```
