#!/usr/bin/env python3
"""Generate the one-page owner handout. It contains no patch values or images."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()

MANUAL = 'https://www.ricoh-imaging.co.jp/english/support/man-pdf/gr-3.pdf#page=101'


def text():
    return f'''GR 密集参考卡 / GR dense reference · r1

不需要拍屏幕，也不用重拍。这是照片 DNG，请只用相机“RAW显像”。
准备：电池充足；先备份存储卡；确认菜单有标准、正片、负片三种风格。
[ ] HDF 关闭；不用自定义配方；每次回到原 DNG，不显像上一张 JPEG。
[ ] JPEG 6000×4000、3:2、sRGB；增减感 0.0；白平衡保留原片。
[ ] 周边光量校正、降噪、阴影校正保留原片设置，三种风格完全一致。

先试一张，只做这 5 步
1. 仅把 R0900001.DNG 放进卡上现有 DCIM 下的 RICOH 照片目录，勿覆盖任何原片。
2. 相机回放打开它，应看到大色块、底部灰阶和四角定位方框。
3. 回放菜单 → RAW显像 → 图像控制“标准”，恢复该风格默认滑杆后执行，保存新 JPEG。
4. 打开新 JPEG，确认是完整色块图，四角都在，灰阶由暗到亮。只看到预览不算通过。
5. 以“文件”发回此 JPEG、R0900001.DNG、机型和固件版本；等研究者回复 PASS 再继续。
PASS：相机能打开并生成完整网格 JPEG；回读 ImageTone=256、默认滑杆和显像记录，灰阶正常。
FAIL：不识别、无 RAW显像选项、报错、旧照片、损坏网格或读回设置不符，立即停，不试整套。

收到 PASS 后，4 张 × 3 风格 = 12 张 JPEG
R0900002.DNG、R0900003.DNG、R0900004.DNG、R0900005.DNG，每张原 DNG 各保存一次：
标准 Standard → 正片 Positive Film → 负片 Negative Film。保存后返回同一张 DNG 再选下一风格。
每次恢复“该风格的原厂默认”，不是把所有滑杆都设成 0。
核对：键/对比/高光/暗部，标准 0/0/0/0；正片 -1/+3/-1/-2；负片 +1/+1/0/-1。
其余适用滑杆全 0。不要改白平衡、增减感、裁切或校正设置。
按 0002/0003/0004/0005 分组标明三种风格；连同原 4 张 DNG 原文件发回。
请用原文件附件或 ZIP，不发截图，不经聊天图片压缩，不经 Lightroom 导出。

English: Back up the card. Test ONLY R0900001.DNG first. In playback, use RAW Development,
Standard at factory defaults, original WB, 0.0 exposure, full-size sRGB. Return the NEW grid JPEG
and DNG as files; wait for PASS. Then develop each R0900002–R0900005 three times from the SAME
original DNG: Standard, Positive Film, Negative Film, each at its own factory defaults.
HDF off. Keep all other processing identical. Return 12 original JPEGs plus the 4 unchanged DNGs.
Stop if the camera rejects the test. No screen photograph is needed.

RAW显像菜单依据：Ricoh GR III 官方手册，印刷页 100–101。
{MANUAL}
'''


def generate():
    handout = text()
    dense.allowed(dense.HERE / 'OWNER_ZH_EN.txt').write_text(handout)
    out = dense.allowed(dense.delivery() / 'OWNER_ZH_EN.txt')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(handout)
    print('owner handout generated')


if __name__ == '__main__':
    generate()
