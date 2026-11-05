"""Seal the generation160 collision without constructing a replacement DAT."""
from pathlib import Path
import json
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C


def main():
    C.setup()
    scan=json.loads((C.LOCAL/'generation-scans/initial/result.json').read_text())
    assert scan['status']=='FAIL_GENERATION_IN_USE'
    rows=[]
    for entry in scan['generation_packages']:
        path=C.ROOT/entry['path'];raw=path.read_bytes()
        assert raw[:8]==b'GXRCE001' and C.D.u32(raw,28)==160
        complete=C.D.u32(raw,16)==len(raw)
        crc_valid=complete and C.D.seal(raw)==raw
        rows.append(dict(path=entry['path'],sha256=C.sha(raw),actual_bytes=len(raw),
                         declared_bytes=C.D.u32(raw,16),generation=160,complete_GXRCE_image=complete,
                         header_and_payload_CRC_valid=crc_valid,
                         classification='complete_DAT' if crc_valid else 'header_fragment'))
    published=next(r for r in rows if r['path']=='firmware/package_v39_diagv4p/GXRCE.DAT')
    assert published['sha256']=='b3e5db12b42edf39f2fc4fe603ee83cdb9ba526b5c270efa736a97b5debbeeb4'
    assert published['header_and_payload_CRC_valid'] and published['actual_bytes']==22372
    prior=json.loads((C.LOCAL/'freeze.json').read_text())
    drift=[name for name,digest in prior['files'].items()
           if not (C.ROOT/name).is_file() or C.sha((C.ROOT/name).read_bytes())!=digest]
    assert not drift,drift
    assert not C.ENGINE.exists() and not any(p.exists() for p in C.PACKAGES.values())
    g159_files=sum(name.startswith('research/g159/') for name in prior['files'])
    C.save(C.LOCAL/'closeout.json',dict(status='DEFECT_GENERATION160_ALREADY_USED',existing_images=rows,
        complete_valid_images=sum(r['header_and_payload_CRC_valid'] for r in rows),
        header_fragments=sum(not r['complete_GXRCE_image'] for r in rows),
        protected_files_rechecked=len(prior['files']),g159_sealed_files_unchanged=g159_files,
        changed_inputs=drift,g160_product_source_created=False,g160_DAT_created=False,
        original_generation_scan_sha256=C.sha((C.LOCAL/'generation-scans/initial/result.json').read_bytes()),
        test=dict(status='NOT_BUILT',sha256=None,dat_bytes=None,main_request=None),
        release=dict(status='NOT_BUILT',sha256=None,dat_bytes=None,main_request=None)))
    driver=C.LOCAL/'generation-scans/initial/driver.py'
    if driver.exists():assert driver.read_bytes()==(C.HERE/'generation_scan.py').read_bytes(), 'Preserve original scanner snapshot'
    else:driver.write_bytes((C.HERE/'generation_scan.py').read_bytes())
    audit=dict(status='SOURCE_READ_ONLY_PARTIAL_NOT_RUNTIME_ACCEPTANCE',
        runtime_findings=[
            dict(path='firmware/engine_v70_g158/candidate/containers/product/fx_pool.c',function='fx_area_valid',finding='Checks descriptor flags against the base selected by effect byte0 for each unit in its mask.'),
            dict(path='firmware/engine_v70_g158/candidate/containers/product/adapter.c',function='uv_look_row / uv_sync / uv_rows',finding='Defaults, selection and knob rendering use the effect base byte0 or current recipe slot.'),
            dict(path='firmware/engine_v70_g158/candidate/containers/product/src/firmware/engine/core/eng_core.c',function='project_compute',finding='Calls kv_data_request with ref.slot; also requires the effect base to match that slot.'),
            dict(path='firmware/engine_v70_g158/candidate/containers/product/memory.c',function='memory_decode',finding='Restores an effect via its descriptor, assigns ref.slot=entry[0], then validates the levels for that slot.'),
            dict(path='firmware/engine_v70_g158/candidate/containers/product/src/firmware/engine/core/eng_boot.inc.c',function='eng_boot_run',finding='Uses decoded saved reference and levels through compute; no uniform05 knob selection observed.'),
            dict(path='firmware/engine_v70_g158/candidate/containers/product/pack.py',function='pack_model',finding='Packs descriptors per entry; effect_area in looks_data.py packs effect.base and its flags. Generation registration remains158.'),
            dict(path='research/recipe_redo_r1/local/source/studio_snapshot/src/gxr_studio/camdata/datcodec.py',function='_parse_looks',finding='Checks flags against entry_of(unit,base). Archived full-DAT profiles register only through155, so this is not current g160 Studio support.')],
        stale_product_policy=[
            dict(path='research/film_looks_r2/local/studio_installation_contract.json',field='dependency.Look_flags_must_also_equal_unit_slot05_for_this_product_layout',value=True,authority='Dropped by owner build-r2 brief; original sealed contract left intact.'),
            dict(path='research/g158/records.py',function='read_manifest',finding='Contains all Look flags == base05 flags assertion, which cannot be reused unchanged for a mixed-base build.'),
            dict(path='research/film_looks_r2/acros_handoff.py',finding='Old handoff validates03/05/TriX as one flags1 group. Revised acceptance would need a separate g160 contract, not an edited historical handoff.')],
        behavior_driver_rerun=False,readback_and_BOOT_proven_for_g160=False,
        no_dependency_rule_claimed_accepted=True,
        stop_reason='Mandatory generation uniqueness gate failed before product construction.')
    C.save(C.LOCAL/'path-audit.json',audit)
    report=f'''有缺陷

# build-r2 停止：160 已被诊断包使用

本轮没有生成g160 test或release DAT，没有派生 `firmware/engine_v71_g160/`，没有更新任何引擎代数常量。全仓检查直接触发机主“绝不复用”的硬约束，未擅自改用161或其他代数。g158源码与两包、g159封存证据共{len(prior['files'])}个文件核对无变化，其中g159为{g159_files}个文件。

## 两包SHA与字节账

| 本轮目标 | 状态 | SHA-256 | DAT/代码/BSS/主请求/每单元行池 |
| --- | --- | --- | --- |
| g160 test | 未构建 | 无 | 没有成品，未产生新字节账。 |
| g160 release | 未构建 | 无 | 没有成品，未产生新字节账。 |

下表是已占用160的历史诊断文件，不是本轮配方交付。

| 既有文件 | generation | 长度B | SHA-256 | 当前核对 |
| --- | ---: | ---: | --- | --- |
| `firmware/package_v39_diagv4p/GXRCE.DAT` | 160 | 22,372 | `b3e5db12b42edf39f2fc4fe603ee83cdb9ba526b5c270efa736a97b5debbeeb4` | 实际文件长度、头CRC和载荷CRC均有效。 |
| `research/diag_v4p/round1/GXRCE.DAT` | 160 | 21,364 | `cb413b97379e83feada9782ea8ee24b9ec7d86b1519a9c252900e4fa1b9d2a70` | 实际文件长度、头CRC和载荷CRC均有效。 |

首个SHA还有引擎构建副本及历史卡归档副本，均逐字节身份相同。另找到两个1,024B头片段，其声明长度为22,372B；它们单列为片段，不计作完整DAT。总计4个完整且CRC有效的DAT副本、2个头片段，不能据此说有6个完整包。

扫描使用实际 `GXRCE001` 魔数，检查{scan['binary_paths_examined']}个二进制路径，找到{len(scan['DAT_headers'])}个该格式头。两个已交付g158包、lutprobe包和EXIF探针中的159赋值分别作二进制/文本阳性对照。文本扫描指定仓库路径，不设8MB截断。扫描清单中的旧审计JSON提及只是引用，不重复计作独立包。原始结果见 `local/generation-scans/initial/result.json`，实际文件哈希与CRC复核见 `local/closeout.json`。

独立历史旁证为 `research/review_diag_v4p/REVIEW.md`，其首段明确绑定同一完整SHA与generation160。不存在仅凭文件名误判的情况。

## 三单元列表

MOUNT、28mm、50mm均未形成新的最终列表。以下仅保留build-r2的候选布局，未装入任何DAT。

| 单元 | 满配01–08候选 | 锁定Look候选 | 新胶片Look优先级 |
| --- | --- | --- | --- |
| MOUNT | GRPos、GRNeg、HC BW、Std、Eterna BB、Leica Classic、Kodachrome25、Gold 200。 | 官方Acros、ARRI 709、M9 STD、instax mini、HNCS HiCon、HNCS LowSat；Tri-X按依赖决定可见性。 | Ektachrome 100、Provia 100F、Portra 800、Kodachrome64、Portra160、Vision3 500T。 |
| 28mm | 同上，01–04逐字节固定。 | 同上。 | 同上，数量尚未做实际预算。 |
| 50mm | 同上，01–04及HC BW/Tri-X组逐字节固定。 | 同上。 | 同上，数量尚未做实际预算。 |

## 准入与路径检查

| 项目 | 本轮状态 |
| --- | --- |
| generation160唯一性 | FAIL，已有实际完整诊断DAT。 |
| 菜单、实际C解析器、BOOT及记忆的基底选择 | 已读关键源码，均看到按实际引用槽位取配置；尚未运行新的混合flags候选，不记作运行验收PASS。 |
| 旧Studio合同与研究打包器 | 已定位旧05统一策略字段和断言，不能原封复用为build-r2验收。 |
| Acros/03/Tri-X逐字节、Filt+1、Y矩阵对照 | 未执行新候选验证，不能把g159的失败反例改记为本轮通过。 |
| 其他5个锁定Look的逐code与全部原有旋钮等价 | 未执行。 |
| Eterna BB/Leica Classic三单元正式准入 | 未执行。保留集、场景、其他ISO、敏感性、整数和128分支全部OPEN。 |
| 记录颜色回执、实际容量、LCD字形 | 未执行。 |
| 原生29、参考整机P1、S重放、PASM、旧记忆拒收 | 未执行，没有本轮成品。 |

实际代码路径的读码记录位于 `local/path-audit.json`。`fx_area_valid`按Look自己的base与flags核对；菜单的默认值和旋钮、`project_compute`、`memory_decode`以及BOOT的compute也读取该base。用户项按自己的base恢复，没有从这些函数观察到统一05的运行时选择。

旧 `studio_installation_contract.json` 仍明确写有 `Look_flags_must_also_equal_unit_slot05_for_this_product_layout=true`，并注明它是额外产品策略。`research/g158/records.py:read_manifest` 也有全体Look对齐05的断言。机主已在build-r2撤销该策略；本轮保留历史文件，不把它当作新的引擎要求，也没有生成修改后的候选合同或调用旧断言打包。实际Studio快照的完整DAT代数表只登记到155，不能据其中的通用Look解析函数就声称Studio已支持新代数。

保留Tri-X的有效GXFX描述符会被 `fx_visible` 枚举；mask=0又会被解析器拒绝。因此隐藏依赖需要另证仅保留被实际配方引用的行，不挂可见描述符；本轮未构造或验证该方案，不宣称Tri-X已隐藏。

## OPEN与现场边界

下一轮首先需要指定并全仓确认未使用的代数。之后仍按build-r2的实际基底规则工作：Acros和03/Tri-X保持flags1，其余锁定Look必须保留已有操作的相同输出，新胶片Look再按flags7安装。任何未证明等价的项都不能出包。

两包的BOOT诊断预期还须按实际原逻辑区分。g158 test换代干净拒收为B21/R3；release关闭BOOT，原复审记录为B02/R3。若引擎逻辑保持不变，不能把release的B02改写成已经观察到B21。后续新包需重跑并报告真实诊断值。

未接触相机、SD卡或网络，未安装依赖、commit、push或开子agent。既有诊断DAT只读核对，未移动或清理。没有向 `firmware/engine_v71_g160/` 或两包目录写入任何文件。现场停止说明见 [OWNER_STEPS.md](OWNER_STEPS.md)。

所有Python用 `-I -B` 和实际nice15。扫描单作业通过 `loadgate.workers()`；未并发派发新计算队列、未做墙钟计时实验。固件、派生字节及原始扫描只保留在忽略的 `local/`，公开报告不写固件地址。

## 复核

下面命令只核对现有占用文件、受保护输入及停止条件，不生成DAT。

```sh
nice -n 15 python3 -I -B research/g160/closeout.py
```

若要重新扫描，使用新的tag保留现有清单；该脚本检查的是160，不会代选其他代数。

```sh
nice -n 15 python3 -I -B research/g160/generation_scan.py --generation 160 --tag independent-review
```
'''
    assert not re.search(r'0x[0-9a-fA-F]{8}',report)
    (C.HERE/'REPORT.md').write_text(report)
    files=[p for p in C.HERE.iterdir() if p.is_file() and p.name!='SHA256SUMS']
    (C.HERE/'SHA256SUMS').write_text(''.join(C.sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(files)))
    files=[p for p in C.LOCAL.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
    (C.LOCAL/'SHA256SUMS').write_text(''.join(C.sha(p.read_bytes())+'  '+str(p.relative_to(C.LOCAL))+'\n' for p in sorted(files)))
    print(json.dumps(dict(status='DEFECT_GENERATION160_ALREADY_USED',complete_valid_DATs=4,header_fragments=2,
                          protected_files_unchanged=len(prior['files']),g159_files_unchanged=g159_files,new_DAT_created=0)))


if __name__=='__main__':main()
