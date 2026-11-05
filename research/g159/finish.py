"""Seal the concrete no-package result after a failed mandatory equivalence gate."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    C.setup()
    preflight = json.loads((C.LOCAL / "preflight.json").read_text())
    generation = json.loads((C.LOCAL / "generation-scan.json").read_text())
    proof_path = C.LOCAL / "checks/trix-group-r1/equivalence.json"
    proof = json.loads(proof_path.read_text())
    assert preflight["status"] == "PASS_INPUT_BINDING"
    assert generation["status"] == "BLOCKED_PRIOR_HOST_PROBE_FIXTURE" and generation['actual_DAT_magic'] == 'GXRCE001'
    assert generation['DAT_scan_status'] == 'PASS'
    assert proof["status"] == "FAIL_BEHAVIOR_EQUIVALENCE" and len(proof["rows"]) == 6
    drift = []
    for name, digest in preflight["baseline_files"].items():
        path = C.ROOT / name
        if not path.is_file() or C.sha(path.read_bytes()) != digest:
            drift.append(name)
    current = set()
    for folder in (C.BASE, C.ROOT / "firmware/package_v310_g158", C.ROOT / "firmware/package_v310_g158_test"):
        current.update(str(p.relative_to(C.ROOT)) for p in folder.rglob("*") if p.is_file())
    added = sorted(current - set(preflight["baseline_files"]))
    assert not drift and not added, (drift, added)
    forbidden = [str(p.relative_to(C.ROOT)) for folder in (C.ENGINE, *C.PACKAGES.values())
                 if folder.exists() for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in (".dat", ".bin", ".elf")]
    assert not forbidden
    assert not C.ENGINE.exists() and not any(p.exists() for p in C.PACKAGES.values()), "Blocked before product creation"
    failed = []
    for row in proof["rows"]:
        assert row["actual_C_parser"] == dict(flags7_on_fixed03=213, flags7_on_existing06=0)
        for candidate in row["all_permitted_bases"]:
            assert not candidate["equivalent"]
            if candidate["flags_compatible"]:
                assert candidate["rebased_filter_plus1_result"] == -1
        failed.append((row["profile"], row["unit"]))
    C.save(C.LOCAL / "closeout.json", dict(status="DEFECT_NO_PACKAGES", failed_cases=failed,
        baseline_files_rechecked=len(preflight["baseline_files"]), baseline_changed=drift, baseline_added=added,
        g159_product_source_created=False, g159_DAT_created=False, generation159_approved_for_use=False,
        prior_host_probe_generation159_use=generation['host_probe_generation159_uses'],
        test=dict(status="NOT_BUILT", sha256=None, dat_bytes=None, main_request=None),
        release=dict(status="NOT_BUILT", sha256=None, dat_bytes=None, main_request=None),
        proof_sha256=C.sha(proof_path.read_bytes()), no_camera_card_network_commit_push_dependencies_or_subagents=True))
    report = f"""有缺陷

# g159 构建停止于 Acros 行为等价门

按机主补充的“如果有任何一项无法证明等价，不要出包”，本轮未生成 test 或 release DAT，也未派生 `firmware/engine_v71_g159/` 产品源码。g158 源码与两包重新逐文件核对，{len(preflight['baseline_files'])} 个文件无变化、无新增。没有触碰相机、SD 卡、网络，没有安装依赖、commit、push 或启动子 agent。

## 两包 SHA 和字节账

| g159 包 | 状态 | SHA-256 | DAT / 主请求 / 每单元行池 |
| --- | --- | --- | --- |
| test | 未构建 | 无 | 未生成，不能给出成品字节账。 |
| release | 未构建 | 无 | 未生成，不能给出成品字节账。 |

已重新读取的 g158 基线身份如下。它们是原包，不能作为 g159 交付。

| 基线包 | SHA-256 | DAT B | 代码 B | BSS B | 主请求 B | 主请求余量 B |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| g158 test | `6a40262c3fc5b94e7152012c655f5c7d2dc98bf6186cf3e80d2429b76f45fcee` | 94,952 | 69,624 | 4,360 | 106,940 | 672 |
| g158 release | `756d5840da9d0393f29411a4f8f61c7e2bb88fb546c814b316982ca8c7cb24f6` | 92,484 | 67,392 | 4,360 | 104,472 | 3,140 |

上限仍为主请求 107,612 B、代码 69,632 B。没有修改 resident、代码窗口或分配窗口。

展开长度只能记作候选内容量，不能代替实际打包增量。

| 单元 | 固定01–04，4×552 B | 候选05–08，4×552 B | 锁定6 Look，6×552 B | 优先胶片6候选，6×552 B | 实际池/描述符/对齐分配 |
| --- | ---: | ---: | ---: | ---: | --- |
| MOUNT | 2,208 | 2,208 | 3,312 | 3,312 | 未分配。 |
| 28mm | 2,208 | 2,208 | 3,312 | 3,312 | 未分配。 |
| 50mm | 2,208 | 2,208 | 3,312 | 3,312 | 未分配。 |

## 每单元列表

三个单元均没有可交付的 g159 最终列表。下表仅记录机主要求，不表示全部候选已准入或装入；Look 的实际数量也未确定。

| 单元 | 满配01–08候选 | 锁定Look | 后续Look候选优先级 |
| --- | --- | --- | --- |
| MOUNT | GRPos、GRNeg、HC BW、Std、Eterna BB、Leica Classic、Kodachrome 25、Gold 200。 | 官方Acros、ARRI 709、M9 STD、instax mini、HNCS HiCon、HNCS LowSat。 | Ektachrome 100、Provia 100F、Portra 800、Kodachrome 64、Portra 160、Vision3 500T。 |
| 28mm | GRPos、GRNeg、HC BW、Std、Eterna BB、Leica Classic、Kodachrome 25、Gold 200。 | 官方Acros、ARRI 709、M9 STD、instax mini、HNCS HiCon、HNCS LowSat。 | Ektachrome 100、Provia 100F、Portra 800、Kodachrome 64、Portra 160、Vision3 500T。 |
| 50mm | GRPos、GRNeg、HC BW、Std、Eterna BB、Leica Classic、Kodachrome 25、Gold 200。 | 官方Acros、ARRI 709、M9 STD、instax mini、HNCS HiCon、HNCS LowSat。 | Ektachrome 100、Provia 100F、Portra 800、Kodachrome 64、Portra 160、Vision3 500T。 |

没有移除 g158 的任何可见 Look，也没有把未验收的新布局写入 Studio 库。

## 实际 C 反例

对 test/release × MOUNT/28mm/50mm 共6组，读取完整 SHA 对应的 g158 DAT，编译原有 C 解析器、`kv_data.c` 和 `kv_math.c`。没有改动这些产品源文件。

| 项目 | 原 g158 Acros，基底03 | flags7 重绑到05–08 |
| --- | --- | --- |
| 合法微调项 | Cont、High、Shad、Fade、Filt，共5项。 | Amt、Cont、High、Shad、Fade、Satu、Warm、Tint、Splt，共9项。 |
| Filt +1 | `kv_data_request` 返回0，实际 `kv_apply_work` 成功，Y矩阵发生变化。 | 四个基底均返回−1，不产生合法微调请求。 |
| Amt 0 | 返回−1。 | 四个基底均返回0，多出原来没有的剂量功能。 |

这不是输出量化的微小色差。旧操作成功，新操作被拒绝，不能把 RGB code 差或 ΔE00 记成0；在这条操作上它们没有可比较的新输出。

另做真实解析器正反例。将 Acros 转码为 flags7，三个通道引用同一条原共享曲线：保持03引用时，C解析器在全部6组返回213；重绑到现存 flags7 的06时，全部6组返回0。后者证明转码和解析可成立，但同样会丢失 Filt 路由。默认曲线、两半C100和C080的有效载荷保持逐字节相同，不能据此宣布旋钮、整机应用或BOOT等价。

所有许可基底已枚举。01/02/03固定为 g158 的 flags1，不能承接 flags7 Acros；04禁止作为Look基底；05–08的微调合同均缺 Filt。槽位的微调项种类和数量由现有C验证器固定，复制03的5项配置到05–08也不符合现有格式。因此在“01–04逐字节固定、Acros转flags7、引擎逻辑不变”的组合下，无法保留 Acros 的原有完整行为。

`eng_core.c` 的 `project_compute` 和 `eng_boot.inc.c` 都按实际引用槽位调用 `kv_data_request`；菜单也按该槽位取得默认值及微调项。仅保留旧的曲线池或 Tri-X 行数据不能让05–08获得03的 Filt 操作。

## 03、05、Tri-X 依赖

三单元原始03、Tri-X及官方Acros均为 flags1，Tri-X和Acros都引用03。本轮保留了完整原03/Tri-X/Acros组合；反例发生时 Tri-X 仍可见，未删除其数据。50mm的 HC BW/Tri-X兼容组合没有被拆开。

Acros 的旧交接还固定05身份及与03/Tri-X的兼容组。新05会成为独立RGB的 flags7，旧的准入合同不能直接沿用。保留隐藏Tri-X数据只能保住数据依赖，不能解决这里已运行复现的微调路由差异。

证据：`local/checks/trix-group-r1/equivalence.json`、其 `driver.py`、原C源码哈希、主机库，以及 `witness/` 中的原记录和Filt+1实际结果。首轮反例另保留在 `local/equivalence.json`，没有覆盖。

## 准入状态

| 项目 | 本轮状态 |
| --- | --- |
| Acros转码与重绑后的完整行为 | FAIL，6/6组复现。 |
| 其余5个锁定Look的完整等价 | 未执行，不能凭研究库已有29个代表性旋钮样本宣称完整等价。 |
| Eterna BB、Leica Classic三单元正式满配准入 | 未执行，保留集、场景、其他ISO、敏感性、整数取整和128分支全部继续OPEN。 |
| Kodachrome 25、Gold 200与新增胶片Look | 未安装、未重绑；本轮没有g159最终记录的预测颜色与相似度回执。 |
| 原生29条、参考整机P1、S重放、PASM、g158旧记忆拒收 | 未执行，没有g159 DAT。g158历史回执不计作本轮通过。 |
| LCD文字与字形 | 未修改产品UI；新名称尚未经过g159 LCD字形核验。 |

未降低任何准入门槛，也未用替换其他胶片来掩盖 Acros 的行为失败。换掉 Eterna BB 或 Leica Classic 不能解决这个与微调槽位绑定有关的缺陷，因此本轮没有可同时满足全部硬约束的配方替补。

## generation与OPEN

修正后的全仓扫描检查 {generation['binary_paths_examined']} 个二进制路径，找到 {len(generation['DAT_headers'])} 个实际 `GXRCE001` DAT头，并用两包g158与lutprobe作阳性覆盖检查。没有发现159的DAT或generation清单；历史提及保存在 `local/generation-scan.json`。

源码扫描发现已封存的 `research/exif_recipe_tag_r1/local/format_probe.py` 在主机EXIF序列化夹具中使用 `t.generation=159`，极简线格式也写入159。对应PASS回执有128个极简向量和128个完整向量，源码与回执SHA均符合原封存清单。这不是机内DAT，也不是已上卡的探针镜像；但按机主“任何包或探针”都不能复用的严格口径，不能把159标为全新未用。当前状态为 `BLOCKED_PRIOR_HOST_PROBE_FIXTURE`，本轮未创建159 DAT，未擅自改用其他代数。

初版扫描误把记忆记录的 `GXR2` 魔数用于DAT，初版源码保存在 `local/preflight-initial.py`，不作为代数准入。`generation_scan.py` 按实际 `GXRCE001` 重扫，并用带显式仓库路径的rg流式检查文本，不设初版的8MB文本大小截断。文本阳性对照要求命中已有g159候选报告；空stdin扫描尝试也单独保留。Acros C解析器与微调反例不依赖这段扫描代码。最终g158全文件快照在行为反例后建立，并重新核对反例编译时的11个C源码哈希与两包完整SHA，未把它写成任务开始时已有的冻结。

OPEN首先是 Acros 的行为合同。建议后续由机主决定是否允许官方Acros继续使用 flags1/03，并豁免它与05的flags一致规则；实际C解析器核对的是所引用基底。这会改变本轮硬约束，本轮没有采用。若维持全部flags7，则需允许修改引擎，把Look的颜色基底与微调配置解耦，并重新验收，超出本轮“引擎逻辑不变”的范围。159的既有主机探针使用也须先解决，不能直接按“未用”批准。

在该合同解决前，不构建两包，不开展现场换装。Eterna BB/Leica Classic的新满配准入、全部锁定Look等价、实际字节分配和整机验收都保留OPEN。现场草案见 [OWNER_STEPS.md](OWNER_STEPS.md)。

## 重跑

以下命令只复现g158上的拒收反例，不产生g159 DAT。使用新tag，保留前次回执。准入返回75时推迟；实际输出为 `FAIL_BEHAVIOR_EQUIVALENCE`，命令正常退出表示反例断言全部成立。

```sh
nice -n 15 python3 -I -B research/g159/equivalence.py --tag independent-review-01
nice -n 15 python3 -I -B research/g159/finish.py
```

Python均使用 `-I -B` 和实际nice15。单作业使用 `loadgate.workers()`；与全仓扫描并行启动主机反例前先调用 `loadgate.cap(len(running))`。未运行墙钟性能测量，无须 `quiet_for_timing()`。所有原厂派生记录、反例字节和原始回执只保存在忽略的 `local/`。
"""
    (C.HERE / "REPORT.md").write_text(report)
    for path in (C.HERE / "REPORT.md", C.HERE / "OWNER_STEPS.md"):
        assert path.exists()
    files = [p for p in C.HERE.iterdir() if p.is_file() and p.name != "SHA256SUMS"]
    lines = [C.sha(p.read_bytes()) + "  " + p.name for p in sorted(files)]
    (C.HERE / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    local_files = [p for p in C.LOCAL.rglob("*") if p.is_file() and p.name != "SHA256SUMS"]
    lines = [C.sha(p.read_bytes()) + "  " + str(p.relative_to(C.LOCAL)) for p in sorted(local_files)]
    (C.LOCAL / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    print(json.dumps(dict(status="DEFECT_NO_PACKAGES", baseline_files_unchanged=len(preflight["baseline_files"]),
                          public_files=len(files), private_files=len(local_files), DAT_created=0)))


if __name__ == "__main__":
    main()
