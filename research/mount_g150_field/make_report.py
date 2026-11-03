"""Build the Chinese report from persisted measurements."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
import csv
import json
import numpy as np


def read(n): return json.loads((a.HERE/n).read_text())
def f(v,n=2,sign=False): return '—' if v is None else format(v,('+' if sign else '')+'.'+str(n)+'f')
def table(head,rows):
    return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+''.join('| '+' | '.join(str(x) for x in row)+' |\n' for row in rows)


def main():
    m,fs,sc,gr,bb,iv=(read(n) for n in ('chart_metrics.json','frame_scores.json','scene_metrics.json','griv_posneg.json','griv_grn.json','inventory.json'))
    pairs=list(csv.DictReader((a.HERE/'patch_metrics.csv').open()))
    baseline={r['patch_id']:r for r in pairs if r['recipe']=='04'}
    summary={}
    byhue=[]
    for s in m:
        rows=[r for r in pairs if r['recipe']==s and r['paired_valid']=='True']
        h=np.array([float(r['g150_camera_dhue_residual']) for r in rows if r['g150_camera_dhue_residual']])
        hr=np.array([float(r['g150_relative_dhue_residual']) for r in rows if r.get('g150_relative_dhue_residual')])
        summary[s]=dict(n=len(rows),hue_n=len(h),hue_residual_signed_median=float(np.median(h)) if len(h) else None,
            hue_residual_abs_median=float(np.median(abs(h))) if len(h) else None,
            hue_residual_abs_p90=float(np.percentile(abs(h),90)) if len(h) else None,
            relative_hue_residual_abs_median=float(np.median(abs(hr))) if len(hr) else None)
        for name,lo,hi in [('red_orange',345,75),('green',75,170),('cyan',170,220),('blue',220,300),('purple',300,345)]:
            selected=[]
            for r in rows:
                b=baseline[r['patch_id']]
                if not b['camera_hue'] or not r['camera_dhue_vs04'] or not r['fifty_dhue_vs04']:continue
                h0=float(b['camera_hue'])
                if (lo<=h0<hi if lo<hi else h0>=lo or h0<hi):selected.append(r)
            byhue.append(dict(recipe=s,group=name,n=len(selected),
                camera_dL_vs04=float(np.median([float(r['camera_dL_vs04']) for r in selected])) if selected else None,
                camera_dhue_vs04=float(np.median([float(r['camera_dhue_vs04']) for r in selected])) if selected else None,
                fifty_dhue_vs04=float(np.median([float(r['fifty_dhue_vs04']) for r in selected])) if selected else None))
    a.dump('colour_summary.json',summary)
    a.dump('colour_by_hue.json',byhue)
    t=[]
    t.append('本批 ISO 200 照片已证实：g150 修好了 MOUNT 旧表造成的额外偏暗；颜色仍有模型残差，GRN*001 与 GR IV 留银冲洗目标仍差明显。\n')
    t.append('# MOUNT g150 实拍研究，2026-11-01\n')
    t.append('01 正片和 05–08 仍会按设计压暗，03 是强反差黑白；修复的不是这些风格本身，而是旧 MOUNT 表多压的那一段亮度。02 负片已经恢复提亮。今天 01/02 对 GR IV 正负片目标的评分分别为 68.2% / 54.1%，同批输入的 50mm 设计预测为 65.2% / 53.0%，已接近其设计水平；这不是两台相机今天同场景实拍的结论。\n')
    t.append('## 1. 输入、证据范围与方法\n')
    t.append('- 原始输入为 `captures/mount-g150-20261101/R8051691–R8051706` 的 16 对 DNG/JPG。32 个文件逐一通过原目录 `SHA256SUMS`，运行后再次核对。照片原件没有改动。\n- DAT 为 `firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT`，SHA-256：`'+iv['dat_sha256']+'`。EXIF 不记录 DAT 哈希；照片与该包的关联来自用户说明，RAW→JPEG 的吻合另作行为核对。\n- 全程本机离线，不访问相机存储卷，不做 Git 写操作，不开子代理。分析命令均以 `nice -n 10` 前台顺序运行；最终编译脚本用 exec 启动编译器，避免保留额外包装进程。\n- 静态已证：g150 的 MOUNT 默认有效行、mask、control 与 g139m 全部一致。01/02/03/05/07/08 与 50mm 配方一致；06 保留 MOUNT 不使用 T1 的既有安排，04 使用 MOUNT 原厂行。详见 [inventory.json](inventory.json)、[g139m_comparison.json](g139m_comparison.json)。\n- 主机已证：用 g150 自己的 C 计算路径重算用户条目；8 个默认条目与 DAT 解码结果逐字节相同。`GRN*001` 用基底 02、Cont 2、High 5、Shad 5、Satu −5，Amount 100%。同时纳入 `FCC-001` 和 `FCC*002` 比较。源码、计算库和派生行哈希见 [build_receipt.json](build_receipt.json)、[user_rows.json](user_rows.json)。\n')
    t.append('每张 DNG 都单独扣黑电平、按白电平归一、应用自己的 AsShotNeutral，再用既有 MOUNT ISO 200 的固定标定映射到表的输入；没有按今天的配方 JPEG 重拟曝光、白平衡或颜色。MOUNT 模型仍借用已测 50mm 响应核。所有照片的原生选择器都是 1，13 个滑杆字节也相同，所以不能用 EXIF 直接认出配方。\n')
    t.append('逐帧识别用 40×28 网格、12×12 像素区域，对八个默认配方和测试用户条目分别预测。色卡另用 chart-v2 的 Hamming 与文字页码双证据识页，逐张定位 116 个色块，不用照片顺序指定身份。16 张的 RAW/JPEG 配准均通过，统一使用校正量 (−1, 0) 像素，校正前平移拟合残差 RMS 为 0.12–0.23 像素。\n')
    t.append('本文“相机实测”来自原始机内 JPEG；“电脑预测”来自配方表、50mm 模型或 GR IV 目标模型。L* 使用 JPEG 按 sRGB、D65 转 Lab 的定义，范围 0–100；色差为 ΔE00。色相差为 Lab 圆周最短差，单位度，只有两端 C*≥8 才报告，灰和黑白不报色相。所有逐色块 L*、色相、相对 04 的变化、模型值、残差与质量标记均在 [patch_metrics.csv](patch_metrics.csv)，共 1,044 行。\n')
    t.append('## 2. 每张实际用了哪个配方\n')
    rr=[]
    for st in sorted(fs):
        r=fs[st];scores={**r['scores'],**{k:v for k,v in r['user_scores'].items() if k!='FCC-001'}}
        rank=sorted(scores,key=lambda k:scores[k]['de00_median']);best,second=rank[:2]
        z=scores[best];q=scores[second]
        rr.append([st[-4:],best,z['n'],f(z['de00_median'])+' / '+f(z['de00_p90']),f(z['dL_median'],2,True),second+' '+f(q['de00_median'])])
    t.append(table(['照片','最吻合配方','网格有效点','相机−预测 ΔE00 中位 / p90','亮度残差 L*','次近候选及中位 ΔE00'],rr))
    t.append('这张表全部是相机 JPEG 与同张 RAW 的预测比较。色卡范围也独立得到同一排序：1693–1701 依次为 04、01、02、03、05、06、07、08、GRN*001。逐色块核对中，1699 的 07 / 08 残差为 1.29 / 3.04，1700 的 08 / 07 为 1.41 / 2.97，1701 的 GRN*001 / 02 为 1.94 / 4.40。用户随后补充的拍摄说明与此吻合。\n')
    t.append('1691–1692 同样符合 GRN*001，不能只把它们归到普通 02。05 与未改参数的 `FCC-001` 生成相同配方行，像素不能区分这两个菜单入口；根据用户“八个内置配方各拍一次”的说明，1697 记为 05。`FCC*002` 的色卡残差为 1.95，高于 05 的 1.45。完整排名见 [frame_scores.json](frame_scores.json)、[chart_recipe_ranking.json](chart_recipe_ranking.json)。\n')
    t.append('## 3. 相对 04 的亮度：额外偏暗已经消失\n')
    t.append('九张色卡均为 ISO 200、1/60、手动白平衡，AsShotNeutral 完全相同，为 `[0.420168, 1, 0.740740]`。可信 RAW 色块的绿通道中位漂移为 0 至 −0.0059 EV，最大一张的中灰位置偏移约 0.0125 EV。这不足以解释旧表的 5–9 L* 额外偏暗。\n')
    t.append('先区分“色卡中灰这个位置”和“实际输出 L*=50”：本次 04 的中灰位置实际只有 L*=25.19，白块为 69.96，整页本身偏暗。表中比较都固定在今天实际的输入，不能把以前在 L*=50 或街景上算出的数字直接移过来。\n')
    rr=[]
    for s in ['04','01','02','03','05','06','07','08','GRN*001']:
        g=m[s]['anchors']['ANCHOR_midgray']
        rr.append([s,f(g['camera_L']),f(g['camera_dL_vs04'],2,True),f(g['g150_dL_vs04'],2,True),
            f(g.get('g137_dL_vs04'),2,True),f(g.get('fifty_dL_vs04'),2,True)])
    t.append(table(['配方','中灰位置 L*，相机实测','相对 04，相机实测','g139m/g150 电脑预测 ΔL*','旧 g137 电脑预测 ΔL*','50mm 电脑预测 ΔL*'],rr))
    t.append('01/03/05–08 的实测仍低于 04，这是新表的设计。02 从旧表预测的 −1.67 恢复为实测 +3.01。03 在这个偏暗输入上把中灰压到 L*=4.32，同时把白块提到 91.29，是强反差曲线，不是整体少进光。\n')
    t.append('不只中灰吻合：各配方同页有效色块的“相机−新表预测”亮度中位残差均在 +0.03 至 +0.31 L*；不存在旧表那种整体多压 5–9 L* 的现象。05/06 与 07/08 的色调本来就不同，不能把“都与 04 一样亮”当作修复标准。\n')
    design=read('design_grey.json')['50']['recipes']
    t.append('为与旧报告的 L*=50 口径对照，以下全部为电脑预测，未把今天 L*=25 的中灰读数当作 L*=50 实测。输入选到 04 输出 L*=50.04。\n')
    t.append(table(['配方','旧 MOUNT ΔL*','g150 MOUNT ΔL*','50mm ΔL*'],[[s,f(design[s]['oldmount'],2,True),f(design[s]['mount'],2,True),f(design[s]['e50'],2,True)] for s in ['01','02','03','05','06','07','08']]))
    t.append('06 的小差异来自 MOUNT 不使用 T1 的安排。g139m 当时街景预测的 01“−10.2 变 −3.4”、02“约 −0.9 变 +4.9”与这里并不冲突：场景和亮度分布不同；g139m 与 g150 的有效行相同，今天实际 RAW 上的新表预测已直接与机内 JPEG 对过。[旧报告](../g139m/REPORT.md)\n')
    t.append('## 4. 颜色、色相与按表出片的残差\n')
    t.append('下表只取各配方与 04 都无质量标记的配对色块。它与第 2 节的全图小网格采样口径不同，因此残差数值也不同。独立固定标定保留了 04 自身约 1.24 ΔE00 的误差，没有先用今天 04 把误差拟合掉。\n')
    rr=[]
    for s in m:
        z=m[s]['metrics']['paired']['camera_minus_g150'];h=summary[s]
        rr.append([s,z['n'],f(z['de00_median'])+' / '+f(z['de00_p90']),f(z['dL_median'],2,True),
                   f(h['hue_residual_abs_median'],1)+' / '+f(h['hue_residual_abs_p90'],1) if h['hue_n'] else '—'])
    t.append(table(['配方','配对有效块','相机−模型 ΔE00 中位 / p90','相机−模型 ΔL* 中位','色相残差绝对值中位 / p90，度'],rr))
    t.append('结论是“照片支持相机按新表出片”，不是“颜色与模型逐点相同”。彩色配方中位色差约 1.2–1.8，亮度残差很小，但部分颜色仍有明显色相残差。06 的青蓝块 `H29_L78_C60` 残差为 9.37 ΔE00、约 −32°，`H23_L78_C60` 为 10.54 ΔE00、约 −29°，已保留在 CSV 中，不能用总体中位数盖掉。\n')
    t.append('这类残差也可能受借用的 50mm 响应核、既有 MOUNT RAW 标定、低信号与屏幕光谱影响，当前照片不足以把各项拆开。作为附加诊断，用实测 04 反解潜在输入，再按每张 RAW 比例修正，彩色配方的残差中位仍约 1.1–1.8；因此不能承诺单靠重新校正 04 就消除这些颜色误差。04 在这种附加诊断中近零是构造结果，不算独立验证。\n')
    t.append('相对 04 的色相变化按 04 实拍色相分组，下面每格为“相机实测 / 同输入 50mm 设计预测”，单位度。只显示至少 3 个同时可用、C*≥8 的色块；完整分组数量、青色、紫色与 ΔL* 见 [colour_by_hue.json](colour_by_hue.json)。\n')
    rr=[]
    for s in ['01','02','03','05','06','07','08']:
        row=[s]
        for name in ['red_orange','green','blue','purple']:
            z=next(v for v in byhue if v['recipe']==s and v['group']==name)
            row.append(f(z['camera_dhue_vs04'],1,True)+' / '+f(z['fifty_dhue_vs04'],1,True) if z['n']>=3 else '样本不足' if s!='03' else '—')
        rr.append(row)
    t.append(table(['配方','红橙 Δh°','绿色 Δh°','蓝色 Δh°','紫色 Δh°'],rr))
    t.append('## 5. GR 正片、负片与 GR IV 目标\n')
    t.append('沿用 [gr_posneg_gap](../gr_posneg_gap/REPORT.md) 的目标与公式：将已有 GR IV 17³ 模型套到实拍 04，目标表示“此 GXR 04 加上 GR IV 标准到风格的变化”。评分为 `1 − median(配方→目标 ΔE00) / median(04→目标 ΔE00)`。这是相对 04 改善误差的比例，不是肉眼相似度的概率。目标是电脑预测，没有今天 GR IV 同场景照片。\n')
    rr=[]
    for s in ['01','02']:
        d=gr[s]
        for name,label in [('camera','g150 相机实测'),('mount_g150','g150 MOUNT 电脑预测'),('fifty_design','50mm 设计电脑预测'),('mount_g137','旧 MOUNT 电脑预测')]:
            z=d['scores'][name]
            rr.append([s,label,z['n'],f(z['de00_median'])+' / '+f(z['de00_p90']),f(100*z['similarity'],1)+'%',f(z['dL_median'],2,True)])
    t.append(table(['配方','结果来源','色块','到 GR IV 的 ΔE00 中位 / p90','评分','到 GR IV 的 ΔL* 中位'],rr))
    t.append('因此本批 01/02 已接近同输入 50mm 设计的总体水平。按 RAW 修正两帧与 04 的微小输入差异后，实测评分为 66.4% / 52.4%，判断不变。这里的百分比不与旧街景的百分比直接相减，也不与历史六页训练集评分直接比较。\n')
    t.append('暖色仍有小偏差，但没有复现旧街景约 −15° 的整组红橙偏转：本页红橙对 GR IV 目标，01 为 +2.27°、色差 1.83；02 为 +3.38°、色差 1.94。02 的绿色仍不够接近目标，12 块绿色的中位色差 5.66、彩度高 3.82，说明“提亮修好”不等于“负片颜色已精确复刻”。[详细分区](griv_posneg.json)\n')
    t.append('## 6. GRN*001 与 GR IV 留银冲洗目标\n')
    t.append('1701 是 GRN*001；1691–1692 的室内试拍也与该条目吻合。它比普通 02 更亮，1701 的中灰位置相对 04 实测 +6.61 L*，白块 L*=87.33。按当前表预测，其配对色块残差中位 1.77 ΔE00、亮度残差 +0.21 L*，没有额外压暗。\n')
    t.append('目标与 [gr4_bleach_fit_r1](../gr4_bleach_fit_r1/REPORT.md) 完全沿用同一套纯计算定义：04 反解、固定传感器桥接、三维线性插值、凸包内且最近特征距离≤1，只在支持内打分；保留原来针对强去饱和目标的色度比规则。没有重新选档位。116 块中有 81 块在目标支持内，1693/1701 双方质量合格共 69 块，两者交集 62 块参与主评分。35 块目标不支持，未填入替代目标；另有 19 块已支持但因 JPEG 质量标记未进主评分。\n')
    rr=[]
    for k,label in [('camera','GRN*001 相机实测'),('mount_g150','GRN*001 MOUNT 电脑预测'),('fifty_design','相同档位 50mm 电脑预测'),('base02','普通 02 MOUNT 电脑预测')]:
        z=bb['scores'][k]
        rr.append([label,z['n'],f(z['de00_median'])+' / '+f(z['de00_p90']),f(z['similarity']*100,1)+'%',f(z['dL_median'],2,True),f(z['dC_median'],2,True)])
    t.append(table(['来源','色块','到 GR IV 的 ΔE00 中位 / p90','评分','ΔL* 中位','ΔC* 中位'],rr))
    t.append('相机结果接近同输入的 50mm 用户条目 A 版，但 A 版本身离 GR IV 留银冲洗还有一段：实测总体仍低 11.40 L*，彩度高 1.51。中性色块低约 8.99 L*，绿色低 13.30，蓝色低 14.12；颜色变化也不是单一提亮可以全部补齐。原六页报告 A 版的 48.6% / 48.7% 是另一批 209 个支持色块的留出预测，本页 42.0% 是固定参数后的单页相机实测，两者不能直接判成 MOUNT 损失了几个百分点。\n')
    t.append('按 RAW 微小差异修正目标后，本页评分为 42.9%、亮度残差 −11.19 L*，结论不变。若把有 JPEG 质量标记但目标仍支持的色块也纳入，81 块评分降为 36.3%，已保存在 [griv_grn.json](griv_grn.json)。1701 证明的是用户条目的实际出片与 A 版预测相近，不是原报告 B 完整表版的实机验证。\n')
    t.append('![GRN*001 与 GR IV 目标](../../captures/mount-g150-20261101/compare-grn.jpg)\n')
    t.append('## 7. 真实场景、高光与观感\n')
    t.append('1702–1706 都是 01 正片。EXIF 快门依次为 1/60、1/3200、1/2500、1/4000、1/60；其中 1704 实际是 1/2500，不是 1/3200。自动白平衡每张不同，已按各自 RAW 元数据使用，不能据这几张估计绝对色温准确度。\n')
    rr=[]
    for st in ['R8051691','R8051692','R8051702','R8051703','R8051704','R8051705','R8051706']:
        j=sc[st]['jpeg']['full'];r=sc[st]['raw']['full']
        rr.append([st[-4:],f(j['all_channels_ge253']*100,5)+'%',f(j['any_channel_ge253']*100,5)+'%',f(r['saturated_fraction']*100,5)+'%'])
    t.append(table(['照片','JPEG 三通道均≥253','JPEG 任一通道≥253','RAW 原生采样≥98% 白电平'],rr))
    t.append('百分比均为整幅原图统计；RAW 按原生 CFA 采样计数，分母与 RGB 像素的语义不同。三通道 JPEG 接近白更接近大面积高光失去细节的指标；单通道裁切还包括饱和色，不能全部叫“白色过曝”。\n')
    t.append('- 1703–1705 没有大面积高光过曝。1705 整幅没有 JPEG 高端裁切，RAW 最高采样只有 50.5% 白电平；专门取天空、云层区域，RAW/JPEG 裁切也都是 0。1704 选定天空区域同样为 0。1703/1704 只有极少数亮点，约百万分之几的整幅 JPEG 接近白，不影响云层结论。\n- 这组室外照片没有拍到 03，不能据此验收 03 的室外高光。色卡上的 03 确认了其强反差行为：低部很暗，亮部迅速上升。\n- 1703/1704 的树木与建筑阴面确实较暗，符合 01 的设计；同 RAW 的 04 预测更亮。相机与 01 预测的亮度中位残差分别为 −0.10、−0.02 L*，没有旧表的额外压暗。\n- 1704 底部黑影、1705 左侧暗区在 RAW 渲染的 04 中也存在，具体物体未知，不能归为配方异常。\n- 1706 白毛巾有少量真实高光损失。白毛巾指定区域约 0.53% RAW 采样达到饱和门槛；黄色毛巾区域约 10.01% JPEG 像素有单通道裁切，三通道同时接近白只有约 0.012%。强光下拍白色织物可略减曝光，尤其要看纹理，不能只看整幅是否发白。\n- 没有看到覆盖全图的新增紫色偏色。1705 亮中性小区域的相机−01 模型中位色差约 1.22、亮度残差 −0.01 L*。实景没有已知光谱的中性物体或同场 GR IV，白平衡与绝对颜色是否正确仍未知。\n')
    t.append('![真实场景与同 RAW 预测](../../captures/mount-g150-20261101/compare-scenes.jpg)\n')
    t.append('## 8. 屏幕色卡能证明什么\n')
    t.append('本次没有触发 chart-v2 的摩尔纹、条带或亮带标记，轻微失焦使色块内部较平滑；这只能说明当前取样未发现这些结构，不能证明所有空间频率都不存在摩尔纹。每张 116 块中，质量合格数依次为 70、61、80、83、64、75、113、83、92；其余标记全部是 JPEG 低端或高端通道裁切，没有 RAW 饱和标记。色卡本身有许多深色、高彩度色块，低端裁切尤其多。所有读数仍保留在逐帧 JSON，未把被排除颜色当作不存在。\n')
    t.append('屏幕发光光谱和真实物体反射光谱不同，尤其会影响青、蓝、紫；Display P3 的名义码值也不等于相机应拍出的 sRGB 码值。没有本次显示器实测白点、亮度、色彩管理与光谱记录，手动白平衡只固定了相机增益，不能把屏幕白点认证为 D65。相对同一页 04 的比较可以消去一部分共同影响，不能消去所有传感器与光谱差异。\n')
    t.append('本次只拍第 1 页，且 04 的绝对输出较暗，其他五页、亮部更多的颜色、真实人像与其他 ISO 未覆盖。因此“ISO 200 上额外偏暗已修好”有直接照片证据，“所有颜色已精确达到设计、所有 ISO 都已实测”没有。GR IV 目标也沿用既有模型和支持范围，本轮没有补录 GR IV 真机照片。\n')
    t.append('## 9. 对比图、数据和复算\n')
    t.append('要求的六配方对比图如下。上排是今天同页色卡，按各张几何校正透视，保持原始亮度和颜色；下排为 10-31 g137 的同配方街拍。街拍的场景、曝光、白平衡不同，只能作观感参照，不能从上下排直接相减判断修复幅度。\n')
    t.append('![04、01、02、03、05、06 对比](../../captures/mount-g150-20261101/compare.jpg)\n')
    t.append('主要文件：\n\n- [chart_metrics.json](chart_metrics.json)：逐配方、灰阶锚点、曝光与模型误差。\n- [patch_metrics.csv](patch_metrics.csv)：全部 1,044 个色块，包含被标记的读数；[charts/](charts/) 内是逐帧数据和采样框图。\n- [griv_posneg.json](griv_posneg.json)、[griv_grn.json](griv_grn.json)：GR IV 目标比较、支持范围与敏感性。\n- [scene_metrics.json](scene_metrics.json)：原图高光统计、区域坐标对应见 [scenes.py](scenes.py)。\n- [provenance/](provenance/)：各步骤读取的输入哈希及运行后未变检查。\n- [SHA256SUMS](SHA256SUMS)：本目录全部交付文件及三个对比 JPG 的哈希；[INPUT_SHA256SUMS](INPUT_SHA256SUMS)：所有受核验输入，含 32 个原始照片。临时编译文件在交付前删除。\n')
    t.append('从仓库根按顺序运行，使用本机已有依赖，不下载任何内容。每一步都以前台顺序执行，Python 自身禁止调用网络与子进程，并检查写入范围。C 编译使用本机 SDK，仅为重算用户条目，不生成相机固件。\n\n```sh\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/analyze.py inventory\nnice -n 10 /bin/zsh -f research/mount_g150_field/build_users.sh\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/users.py\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/analyze.py frames\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/analyze.py rescore\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/analyze.py charts\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/measure.py\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/scenes.py\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/figures.py\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/make_report.py\nnice -n 10 /opt/homebrew/bin/python3 -I -B research/mount_g150_field/verify.py\n```\n')
    t.append('## 给用户的大白话\n')
    t.append('MOUNT 以前额外偏暗的问题，这批照片已经确认修好了。01 正片仍会压暗，02 负片已经会提亮，03 是黑白强反差，05–08 也各自保留原本的深浅风格，这些不是旧问题又回来了。正片、负片现在已接近 50mm 配方的设计水平，但少数颜色，尤其 06 的青蓝色，还不能说完全准确。“留银冲洗”GRN*001 也确实按表生效了，只是这套简化配方离 GR IV 原效果仍差不少，主要还不够亮。室外几张用的都是 01，云没有明显过曝；白毛巾有少量高光损失，强光下可略减曝光。今天连标准色卡本身都拍得较暗，所以不要只看这张黑底色卡就判断所有配方还偏暗。\n')
    (a.HERE/'REPORT.md').write_text('\n'.join(t))
    a.finish('report')
    print('REPORT.md written; patch rows',len(pairs),flush=True)


if __name__=='__main__':main()
