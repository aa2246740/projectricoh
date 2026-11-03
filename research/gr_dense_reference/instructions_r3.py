#!/usr/bin/env python3
"""Generate the canonical bilingual r3s spare-card handout."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import owners

DEFAULT_CONTROL_ZH = 'R0000101 是你自己拍的一张原片，只改了文件名，作为对照。'
DEFAULT_CONTROL_EN = 'R0000101 is one of your own original photos, renamed only, as the control.'


def text(owner):
    entry = owners.get(owner)
    legacy = entry.get('legacy', {})
    labels = entry.get('instructions', {})
    model = entry['model'].removeprefix('RICOH ')
    hdf = model == 'GR IV HDF'
    return TEMPLATE.format(
        model=model,
        hdf_zh='HDF 开关不影响本次显像。' if hdf else '',
        hdf_en=' The HDF switch does not matter here.' if hdf else '',
        control_zh=labels.get('control_label_zh', legacy.get('control_label_zh', DEFAULT_CONTROL_ZH)),
        control_en=labels.get('control_label_en', legacy.get('control_label_en', DEFAULT_CONTROL_EN)),
        control_card_separator_en=legacy.get('control_card_separator_en', '\n'),
        old_zh=(legacy['old_files_zh'] + '\n') if legacy.get('old_files_zh') else '',
        old_en=(' ' + legacy['old_files_en']) if legacy.get('old_files_en') else '')


TEMPLATE = '''{model} 密集参考卡 r3s（空卡版）/ dense reference cards, spare-card edition
仅供模板原机主、原机身使用，含原片的序列号、时间等私密资料，请勿转发。
不用拍照。全程只用一张单独的空 microSD 卡：不碰你自己的照片、内置存储和你自己的卡，事后什么都不用删。
电池充满即可。{hdf_zh}

准备（约 3 分钟）
1. 找一张空的 microSD 卡（旧卡也行，先把里面的东西挪走）。在电脑上把本包里的 DCIM 文件夹整个拷到这张卡的最外层。
   拷好后，卡里 DCIM/100RICOH/ 下有 6 张：R0000101.DNG ～ R0000106.DNG。
2. 关机，把这张卡插进相机。如果相机里原本插着你自己的卡，先取出来放好。
3. 开机进回放。如果看到的是你自己的照片，就长按"短片/存储切换"键（说明书 p.41、p.51），
   或用回放菜单 C1 → 选择回放存储 → 存储卡，切到这张卡。应能看到这 6 张。
   万一相机提示这张卡不能用：只格式化这张卡（菜单 E1 → 格式化 → 选"存储卡"，千万别选"内置存储"），再重新拷一次 DCIM。

TEST 先做（约 1 分钟）
{control_zh}
R0000102 是 38 色块测试卡。
分别回放这两张：回放菜单 C3 → RAW显像 → 图像控制"标准" → 执行 → 保存位置选"存储卡"，各存出一张新 JPEG。
看到回放预览不算成功，必须存出新 JPEG。
两张都成功：不用等回复，直接做 MAIN。
有一张失败：停下，拍下报错画面发回，并说明是哪一张。后面都不用做，这张卡也不用管。

MAIN（约 15 分钟）
R0000103 ～ R0000106 分别是密集卡 1/2/3/4。
回放时画面略模糊是正常的：为了符合相机文件格式，回放用的小预览图做了柔化，不影响显像结果；放大查看是清晰的。
每张各显像三次：标准 Standard、正片 Positive Film、负片 Negative Film，共 12 次，保存位置都选"存储卡"。
每次回到同一张 DNG，把该风格恢复"原厂默认"，不是把所有滑杆都归零。不用自定义配方。
键/对比/高光/暗部：标准 0/0/0/0；正片 -1/+3/-1/-2；负片 +1/+1/0/-1。其余适用滑杆为 0。
JPEG 6192×4128、3:2、sRGB；白平衡保留原片；增减感 0.0 EV。
周边光量校正、降噪、阴影校正保留原片设置，三种风格保持一致，不裁切。

发回
这张卡原本没有 JPG，所以卡上的 JPG 全是这次显像出来的（应为 14 张：TEST 2 + MAIN 12），不用挑，全部发回。
作为原文件附件或 ZIP 发送，不发截图，不经聊天图片压缩或 Lightroom 导出。
文件名不用改：研究者按卡片内容和机内风格记录匹配。
万一有一张存到了内置存储：在存储卡上重做那一张即可；内置存储里那张色卡图删不删随你。

收尾
取出这张卡；如果之前换下了你自己的卡，插回去就恢复原样。这张卡留着、清空、格式化都随你。
相机给照片的编号可能会往后跳十几个号，就像多拍了十几张又删掉一样，没有其他影响。
{old_zh}
English
Private: only for the owner and camera body that supplied this template. Files retain personal
metadata including serial numbers and dates. Do not forward.
No shooting needed. Use one separate, empty microSD card for everything: your own photos, internal
memory and your own card are never touched, and nothing needs deleting afterwards.
Charge the battery.{hdf_en}
Setup (~3 min): on a computer, copy this package's DCIM folder to the root of an empty microSD card
(an old card is fine once emptied). The card then holds DCIM/100RICOH/R0000101.DNG to R0000106.DNG.
Power off and insert this card. If your own card is in the camera, take it out first.
Enter playback. If you see your own photos, press and hold the Movie/Save destination memory
switching button (manual pp.41, 51), or use C1 → Select Playback Memory → Memory Card.
You should see the six images. If the camera says the card cannot be used, format THIS card only:
E1 → Format → Memory Card (never Internal Memory), then copy the DCIM folder again.
TEST first (~1 min): {control_en}{control_card_separator_en}R0000102 is the 38-patch card.
For each: Playback menu C3 → RAW Development → Image Control Standard → Execute → save to
Memory Card. Save a NEW JPEG for each. Playback alone does not count.
Both succeed: go straight to MAIN without waiting for a reply. Either fails: STOP, send a photo of
the error and say which file failed. Nothing else to do; leave the card as it is.
MAIN (~15 min): R0000103 to R0000106 are dense cards 1 to 4. Slightly blurred playback is normal:
the small playback preview was softened to fit the camera file format. This does not affect RAW
Development results; zoomed viewing is sharp. Develop each three times from the same original DNG,
once per style: Standard, Positive Film, Negative Film (12 in total), always saving to the Memory
Card. Reset EACH style to its own factory defaults, not all sliders to zero. No custom recipes.
Key/contrast/highlights/shadows: Standard 0/0/0/0; Positive -1/+3/-1/-2; Negative +1/+1/0/-1.
Other applicable sliders 0. Use 6192×4128, 3:2, sRGB, original WB and 0.0 EV.
Keep peripheral illumination correction, noise reduction and shadow correction at the original
settings, identical across styles. No crop.
Return: the card had no JPEGs before, so every JPEG on it came from this session (14 expected:
2 TEST + 12 MAIN). Send them all as files or a ZIP. No screenshots, chat image compression or
Lightroom exports. Do not rename them; matching uses card content and the camera's style metadata.
If one was saved to internal memory by mistake, redo it to the Memory Card; keeping or deleting
the stray chart image is up to you.
Afterwards: remove the card, and put your own card back if you took it out. Everything is as
before. Keep, erase or format this card as you like. The camera's file numbers may jump ahead by
about 14, as if you had taken and deleted 14 shots; nothing else changes.{old_en}

菜单依据 / menu reference: GR IV manual pp.41, 51 (memory switching), p.46 (format),
p.90 (save destination), pp.111–112 (RAW Development), pp.148–152 (file numbering).
说明修订 / revised 2026-10-22 r3s：改用单独空卡、低编号、存到存储卡，事后无需删除。
spare card, low file numbers, save to Memory Card, nothing to delete afterwards.
'''
