"""Generate the field report from retained measurements, without image processing."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_20261103 as f
import json

HERE, ROOT, OUT = f.HERE, f.ROOT, f.OUT
REPORT = HERE / 'FIELD_20261103.md'
NAME = dict(zip(f.PATCH_NAMES+('toolbar_aux',), ('暗灰','中灰','亮灰','天空蓝','肤色','绿叶','浏览器浅灰辅助区')))


def read(name):
    return json.loads((OUT/name).read_text())


def triple(a, signed=True, digits=2):
    spec = ('+' if signed else '')+'.'+str(digits)+'f'
    return ' / '.join(format(float(v),spec) for v in a)


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(map(str,r))+' |' for r in rows])


def main():
    assert os.getpriority(os.PRIO_PROCESS,0) >= 10
    a,e,s,m = read('assignments.json'),read('empirical.json'),read('stability.json'),read('responses.json')
    meta,model = read('metadata.json'),read('model.json')
    frames = a['frames']; primary=e['primary']; labels=[r['label'] for r in frames]
    assert a['counts']==dict(A=6,R=3,G=4,B=3)
    assert e['direct_chroma_check']['same_labels']
    assert all(v['same_labels'] for v in e['classification_variants'])
    assert all(v['R_labels_equal'] for v in e['auxiliary_roi_variants'])
    cleanup=read('cleanup.json')
    assert cleanup['scratch_removed'] and not f.TMP.exists()
    raw_span=s['raw_percent_range']
    shift=next(v for v in e['geometry'] if v['frame']=='R8051882')['max_displacement_px']
    sig=e['direct_chroma_check']['features']; splits=e['direct_chroma_check']['splits']
    rows=[]
    for i,r in enumerate(frames):
        cls=r['label']+'+2' if r['label']!='A' else 'A 型*'
        scores=[sig[i][k]-splits[ch]['lower_mean'] for k,ch in enumerate('RGB')]
        rows.append([r['frame'],meta[i]['dng']['time'].split()[-1],cls,
                     '高，响应类型' if r['label']!='A' else '高，基线类型*',
                     *[f'{v:+.2f}' for v in scores]])
    frame_table=table(['照片','相机时间','判定','置信度','辅助区 R−G','亮灰 G−B','亮灰 B−R'],rows)
    response_rows=[]
    for ch in 'RGB':
        group=primary['effects'][ch]
        for p,name in enumerate(m['patch_names'][:6]):
            response_rows.append([ch+'+2',NAME[name],group['n'],triple(group['mean'][p]),
                                  triple(group['sd'][p],False),triple(m['channels'][ch]['predicted']['mean'][p])])
    response_table=table(['扰动','色块','张数','实测 ΔR / ΔG / ΔB','重复 SD，R / G / B','模型预测 ΔR / ΔG / ΔB'],response_rows)
    main_rows=[]
    for k,ch in enumerate('RGB'):
        p=6 if ch=='R' else 2
        g=primary['effects'][ch]
        pred=m['channels'][ch]['predicted']['mean'][p][k]
        observed=g['mean'][p][k]
        main_rows.append([ch+'+2',NAME[m['patch_names'][p]],g['n'],f'{observed:+.3f}',
                          f'{g["sd"][p][k]:.3f}',f'{pred:+.3f}',f'{100*(observed/pred-1):+.1f}%',
                          f'{m["channels"][ch]["mean"][p][k]:+.3f}'])
    comparison_table=table(['扰动','目标区域','张数','主通道实测','重复 SD','原模型预测','实测相对预测','模型式 RAW 校正复核'],main_rows)
    stability_rows=[]
    for p,name in enumerate(m['patch_names']):
        stability_rows.append([NAME[name],triple(raw_span[p],False),
            triple(primary['leave_one_A_out_summary']['sd'][p],False)])
    stability_table=table(['区域','16 张 RAW 黑位扣除信号全距 / 中位数，R / G / B（%）',
                           'A 留一检验的 JPG 残差 SD，R / G / B（码）'],stability_rows)
    drift_rows=[]
    direct_span=f.np.ptp(s['jpeg_direct'],axis=0)
    corrected_span=f.np.ptp(s['jpeg_raw_corrected'],axis=0)
    for p,name in enumerate(m['patch_names']):
        drift_rows.append([NAME[name],triple(direct_span[p],False),triple(corrected_span[p],False)])
    drift_table=table(['区域','六张 A 型之间原始 JPG 全距，R / G / B（码）',
                       '相对首张按 RAW 比例校正后的全距，R / G / B（码）'],drift_rows)
    natural=[]
    handoff=[]
    for row in meta[16:]:
        d=row['dng']; exp=d['exposure_s']
        natural.append([row['frame'],d['time'].split()[-1],f'{d["selector"]} / {d["selector_name"]}',
                        ' / '.join(map(str,d['sliders_display'][:3])), '日光，1',d['iso'],f'1/{round(1/exp)} s'])
        handoff.append(dict(frame=row['frame'],metadata=d,
            source_sha256={ext:f.sha(f.CAP/(row['frame']+'.'+ext)) for ext in ('DNG','JPG')},
            role='natural_scene_identity_only',native_04_identity_verified=False,
            probe_analysis_used=False,small_physical_chart_reported_by_owner=row['frame']=='R8051895'))
    natural_table=table(['照片','相机时间','选择器','滑杆：对比 / 锐度 / 鲜艳度','白平衡，ShotInfo','ISO','快门'],natural)
    aux_rows=[]
    for ch in 'RGB':
        g=primary['effects'][ch]
        aux_rows.append([ch+'+2',g['n'],triple(g['mean'][6]),triple(g['sd'][6],False),
                         triple(m['channels'][ch]['predicted']['mean'][6])])
    auxiliary_table=table(['扰动','张数','辅助区实测 ΔR / ΔG / ΔB','重复 SD，R / G / B','原模型预测'],aux_rows)
    direct=[]
    for ch in 'RGB':
        sp=splits[ch]
        direct.append([ch,f'{sp["gap"]:.3f}',f'{sp["threshold"]-sp["lower_mean"]:.3f}'])
    split_table=table(['响应特征','两群最近距离，JPG 码','归零后的分类阈值，JPG 码'],direct)
    text=f'''部分可用

MOUNT 的独立三曲线确实在这次静帧 JPG 上生效，R、G、B 命名对应各自的主要响应。它可以作为 recipe-redo-r1 开放 MOUNT L1 拟合的硬件依据。现有连续模型的定量幅度尚未通过：R 的实测主响应低于预测，G 高于预测，B 接近预测；最终 JPG 也有跨通道变化，不能写成“R+2 只改变 JPG 的 R”。

16 张全部保留。判定为 A 型 6 张、R+2 三张、G+2 四张、B+2 三张。R 依靠画面内浏览器浅灰空白区得到证据，设计的六色块在本曝光下没有激励 R 的修改区间。因此本轮提供了三通道存在性和局部响应证据，没有闭合全曲线标定。

## 输入、范围与方法

只读 `captures/mount-probe-20261103/` 的 23 组 DNG＋JPG，独立核对同目录清单的 46 个文件哈希，分析结束再次逐一核对。R8051878–R8051893 做像素分析；R8051894–R8051900 只读身份元数据，未用于曝光回归、条目判定或响应拟合。

DAT 本地包的 SHA-256 为 `a30675fa8450a7dcb258ca494f5f0615d054743b738190b4ef3b6c0a227b6de5`，和机主提供的版本一致。照片 EXIF 不记录这个 DAT 哈希，实际加载版本仍以机主记录为来源。分析从这份 DAT 独立展开 MOUNT 四条记录，并核对本包既有 expected 数据。各 B 仅将对应曲线零基节点 16 加 2，其余 payload 不变。参数字节、地址和曲线数组只在 local 内保存。

所有 JPG 都按相机 sRGB 文件的原始 8 位码值测量，没有按屏幕 P3 预设再转换，也没有自动曝光、直方图对齐或按条目白平衡。屏幕、预设和亮度设置取自机主描述，不作为绝对色度标定。

逐张用三个彩色色块定位整个网格，避开边缘，主测中心 50%；另用中心 35% 和 65% 复核。1882 相对首张的最大色块中心位移为 {shift:.1f} 像素，采用它自己的位置，没有套用首张坐标。浏览器浅灰辅助区单列，另以 64、36、16 个中心子块检验。见 [逐张 ROI 图](local/field_20261103/roi-contact.jpg)。

RAW 直接解包 12 位 CFA，按实际裁切起点 `(8,7)` 处理 CFA 相位，扣黑位后分别统计 R/G/B，保留两个绿平面的采样；不去马赛克、不应用 DNG BaselineExposure、不做自动处理。全部 RAW 像素字节都经过重打包一致性检查，16 个传感器 payload 哈希各不相同。DNG 默认裁切与 JPG 均为 4288×2848，方向为 1，按同尺寸坐标取样并远离边缘，没有声称像素级去马赛克对齐。

条目判定首先比较 RAW 归一化后的 JPG 通道响应，再独立对原始 JPG 的三个色差特征作两群划分。两个方法均不输入拍摄顺序或各条目的预期张数，16 张判定完全一致。不同主 ROI 和辅助区子集也保持同一判定。“高”表示这些方法一致、两群无重叠，不表示经过外部样本标定的概率。

响应主表使用六张 A 型照片拟合每个区域的 JPG 对 RAW 绿信号的局部线性关系，只有截距和一个亮度斜率，不拟合探针响应。将各 B 的 JPG 减去其 RAW 亮度对应的 A 预测，得到校正差分。另用 RAW 三通道平均亮度和既有 ISP 模型的 RAW 比例法复核。重复 SD 按三张或四张完整拍摄计算，64 个空间子块没有冒充 64 次独立拍摄。

## 逐张判定与口述顺序

下表后三列只用于分类，是各 JPG 色差减去低响应群均值后的码值，不是通道增量。

{frame_table}

*A 型指在三种诊断区域都没有 +2 响应。按本题四分类归入 A；这些照片不能单靠像素或 Standard 选择器唯一证明菜单条目是 `M26 A`，原生 `04 Std` 仍是不可分的基线候选。尤其最后 1893 可能已选回 04，不能把它额外称为已验证的 M26 A 或原生 04。

恢复出的响应顺序为 `A型、R×3、A型、G、A型、G×3、A型、B×3、A型、A型`。G 段的额外 G 是 1883，额外 A 型是 1884；1893 又是一张基线型。相对原 13 张计划，响应数量多两张 A 型和一张 G，机主描述的“一张 A＋一张 G”只解释了其中两张。全部 16 张都参与相应统计，未丢掉 1883、1884 或 1893。

{split_table}

![按 JPG 响应恢复拍摄顺序](local/field_20261103/classification.png)

## RAW 稳定性、重复性与恢复

16 张均为 M 档、ISO 200、1/30 秒、日光白平衡。DNG AsShotNeutral 全部为 `[0.51282, 1, 0.666666]`，DNG/JPG 的时间、选择器、13 个滑杆记录、ISO、快门和白平衡一致。MOUNT 的光圈记录为 0，不能读作真实 f/0；真实光圈未由 EXIF 核实。

曝光设置稳定，屏幕与机位读数没有完全冻结。各区域的 RAW 全距如下，最高约 5%；不能把未经校正的 JPG 差直接解释成探针。色块之间的变化不完全一致，不能只给整张照片乘一个共同亮度系数。每个区域分别校正，并保留原始数值。

{stability_table}

{drift_table}

主 ROI 及辅助区的 RAW 过曝比例均为 0，JPG 的 0/255 端点裁切未进入取样。A 留一检验显示弱通道仍有约零点几码的基线不确定性。上表的 A 残差包括定位、光谱比例变化、局部线性近似及 JPG 量化，不能只用 B 组很小的重复 SD 宣称高精度。

每段扰动之后均出现基线型，末尾 1892、1893 也都回到基线型。按 RAW 校正后的 A 与 A 差分及逐张数值保存在 [stability.json](local/field_20261103/stability.json)。这证明测试区域恢复到基线响应范围，不证明全部设置字节复原、断电持久化或原生 04 身份。

## 六色块的实测响应

单位均为相机 JPG 的 0–255 码值。实测为 RAW 亮度校正后的组均值，SD 是完整拍摄间的样本标准差。模型列使用现有 50mm 响应核、MOUNT 自身参数及实际 A 像素条件，没有按本次 B 数据重拟合幅度。原始差分、各帧样本和另一种 RAW 校正均保留在 local。

{response_table}

R+2 在这六块中的预测均为零，所以这些小幅残差不能用来验证 R 或否定 R。其它阴性区域也存在 RAW 回归残差，例如天空蓝的弱变化与 A 留一残差同量级，未作为新的通道耦合结论。

## 辅助灰块、模型幅度与单调性

浏览器空白浅灰位于六块之外，亮度刚好覆盖 R 扰动区间，R+2 的三张在该区都有同向变化。它是事后声明的辅助证据，不能算作原设计六块的 R 验收。

{auxiliary_table}

{comparison_table}

![实测响应与原模型比较](local/field_20261103/response-comparison.png)

R 的主增量在辅助区不同子集上约 +1.67 至 +1.69 码，确实存在；不过两种 RAW 校正给出的幅度有差距。G 的四张均有正向 G 响应，其中较早的 1883 因实际亮度不同，幅度小于后续三张；它仍作为额外重复保留。B 的三张最一致。三通道主增量均高于各自 A 的残差水平，通道没有互换。

现有模型的三条输出曲线在参数上均保持单调。照片只测试同一节点的 +2，没有负向扰动、逐节点扫描或完整灰阶梯，因而只能确认这三处局部扰动的主响应为正，不能从本次照片证明全码域硬件单调性。六主色块的 R 未受激励，G/B 主要依靠亮灰，不能称为三条完整曲线的实拍标定。

C100、色度表及 JPG 量化会让单一前级曲线扰动传到最终多个 RGB 分量。通道命名正确，不等于最终 JPG 只有目标通道改变。G 在亮灰同时降低 R 和 B，B 同时降低 R，都是实测需要保留的结果。现有模型的方向大体相符，但幅度和部分交叉分量未闭合，不能将差异全部归因于 JPG 量化，亦不能据此拟合一个全局的 R/G/B 增益修正。

## 自然场景仅核对身份

{natural_table}

七组 DNG/JPG 上述字段逐对相同，机型均为 `GXR MOUNT A12`。五色饱和度记录均为 5；五色色相记录为橙 5、绿 5、蓝 4、红 4、品红 4。白平衡微调未从已核实字段恢复，不能补成零。1895 有小色卡来自机主说明，本轮未定位或测量该色卡。

`Standard` 选择器和 5/6/5 滑杆不能证明深层配方是原生 04；16 张探针也记录同一选择器。将这七组交给 recipe-redo-r1 时标为“机主认为已选回 04 的 Standard 候选，深层身份未由照片证明”，不可提升为绝对 04 标定真值。完整身份表及来源哈希见 [natural_identity.json](local/field_20261103/natural_identity.json)。

## 给 recipe-redo-r1 的结论

允许 MOUNT 在 ISO 200 的 L1 拟合中使用独立三曲线，R←C、G←B5、B←D 的现有命名获得了本轮局部静帧响应支持。保留现有模型作为拟合起点，并把它当作仍需 MOUNT 照片校准的近似。不要沿用“已按模型精确生效”的表述，也不要拿本轮幅度比例统一缩放整条曲线。

本轮覆盖一个节点、+2、一个 ISO、两种有效灰块亮度，没有验证全范围、负扰动、较大曲线改动、其它 ISO 或 50mm/28mm。A 与原生 04 的像素等价性未单独闭合，C120 没有进入本轮照片。七张自然场景只交付身份候选，未作 L1 准确度或配方好坏评分。机器可读结论见 [recipe_redo_handoff.json](local/field_20261103/recipe_redo_handoff.json)。

## 复跑、校验与清理

脚本为 [field_20261103.py](field_20261103.py) 和 [报告生成脚本](field_20261103_report.py)。复跑前核对 Workspace 挂载、APFS、可写及 UUID `14BE04EB-AF49-497E-B36A-B078B2F7C5E8`，并在项目根依次执行，各命令结束后再执行下一条。

```sh
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py inventory
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py extract
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py predictions
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py measure
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py robustness
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py figures
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py cleanup
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103_report.py
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py seal
nice -n 10 studio/.venv/bin/python -I -B research/probe_pack_r1/field_20261103.py verify
```

[FIELD_20261103.SHA256SUMS](FIELD_20261103.SHA256SUMS) 以项目根为基准，覆盖本报告、两个脚本及 [local/SHA256SUMS](local/field_20261103/SHA256SUMS)。local 清单覆盖全部保留证据。原有探针包、报告和 SHA256SUMS 没有改写。

封存初次检查误要求裁切起点为偶数，已按实际 CFA 相位修正。主 ROI 原来就处理了相位；另修正一项未用于结论的绿平面行统计，重跑提取后 16 张主 ROI 和辅助区的 RAW/JPG 均值逐项完全相同。记录见 [validation_failures.json](local/field_20261103/validation_failures.json) 和 [rerun_comparison.json](local/field_20261103/rerun_comparison.json)。

本任务只有一个 nice 10 计算进程，各数值库线程数设为 1，未开子代理、未轮询 sleep、未访问存储卡、未调用或改动 Studio 服务及用户数据、未做 Git 写操作。指定 Scratch 已删除，见 [cleanup.json](local/field_20261103/cleanup.json)。门槛为部分可用，原因是完整曲线及原模型定量幅度尚未通过；局部通道响应结论可用于 MOUNT L1 重拟合。
'''
    REPORT.write_text(text)
    f.dump('natural_identity.json',dict(frames=handoff,source='paired DNG/JPG metadata only',
                                       native_04_identity_verified=False))
    f.dump('recipe_redo_handoff.json',dict(verdict='部分可用',mount_l1_enable_for_fitting=True,
        channel_mapping_confirmed_locally=dict(R='C',G='B5',B='D'),quantitative_model_accepted=False,
        iso=200,node_index_zero_based=16,node_delta=2,full_curve_monotonicity_verified=False,
        designed_R_patch_excited=False,R_evidence='auxiliary browser grey',
        native04_equivalence_verified=False,c120_tested=False,
        natural_scenes='identity-only Standard candidates, not verified native 04 ground truth',
        probe_frame_counts=a['counts'],original_files_changed=False))
    print(REPORT)


if __name__=='__main__':
    main()
