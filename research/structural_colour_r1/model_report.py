"""Format conditional model replay scores without treating them as hardware forecasts."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r
import csv

rows=list(csv.DictReader((r.HERE/'predictions.csv').open()))
assert len(rows)==280
assert len({(v['index'],v['group'],v['axis_hypothesis'],v['body_level'])for v in rows})==280
indices=list(range(27))+list(range(43,51))

def fmt(value):
    return '—' if value=='' else f'{float(value):.2f}'

lines=[
    '# 冻结双程假设的电脑复算',
    '',
    '这里复算的是 look-ceiling 已保存的数学假设，不是机身 F034 的硬件收益预测。六项候选都没有在本轮闭合新的硬件像素方程。',
    '模型代码已复制到本任务 model_copy/，仅 runtime.py 的输出位置和 diskutil 绝对路径改变。没有重新拟合、挑起点或按照片留出选择解释。',
    '',
    '27 个 Looks 加 MOUNT 内置 01–08 共 35 档案。每档复算两种 C120 轴、两种第二阶段和两组照片输入，共 280 条评分。重新渲染后，中位 ΔE00 与冻结结果的最大差为 0。完整数值、样本数、绝对 ΔE00 和 50mm 输入对照在 [predictions.csv](predictions.csv)。',
    '',
    '相似度沿用 100 × [1 − median ΔE00(预测,目标) / median ΔE00(原厂04,目标)]。目标04的分母接近零，不报百分比。照片输入来自既有 DNG，输出仍为电脑渲染。',
    '',
    '第一阶段为 L4。第二阶段 L1 或 L4、8-bit RGB 中间值、单位扇区响应、借用的响应核和坐标缩放都是原数学模型的约定。真实 format1 是否经过这些颜色阶段、RGB/YCC 域、YUV422 共色度、内部舍入、全尺寸 DMA、所有权和主 JPEG 接管均未因此得到验证。MOUNT 响应核沿用 50mm 迁移。',
    '',
    '下表仅列 MOUNT 照片输入，单位为百分数和百分点。Y 与 C 两种解释分别保留，未取留出成绩更好的分支。负增益照录。它们是有限优化的保存解，不是表达能力的数学上界。',
]
for axis in ('Y','C'):
    lines+=['',f'## 两个阶段都假设 C120 按 {axis} 轴工作','',
        '| 目标 | 单次 L4 | 第二程 L1 | 差值 | 第二程 L4 | 差值 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for index in indices:
        pair={int(v['body_level']):v for v in rows if int(v['index'])==index and v['group']=='mount-a12' and v['axis_hypothesis']==axis}
        a,b=pair[1],pair[4]
        lines.append('| '+' | '.join([a['name'],fmt(a['single_percent']),fmt(a['two_pass_percent']),fmt(a['gain_pp']),fmt(b['two_pass_percent']),fmt(b['gain_pp'])])+' |')
(r.HERE/'MODEL_REPLAY.md').write_text('\n'.join(lines)+'\n')
r.finish('model_report')
print('Wrote conditional replay tables for 35 targets; no hardware forecast.')
