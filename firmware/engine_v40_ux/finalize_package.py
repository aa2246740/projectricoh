"""Read actual integrated results, produce the Chinese report and verify all manifests."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/"local/integration"
PACKAGE=ROOT/"firmware/package_v36_g117"
sha=lambda b:hashlib.sha256(b).hexdigest()
load=lambda p:json.loads(p.read_text())


def main():
    native={u:load(OUT/("native-"+u+".json")) for u in ("50mm","28mm","mount")}
    for unit,r in native.items():
        assert r["status"]=="PASS",(unit,r.get("error"))
        assert all(k in r for k in "abcdefgh"),(unit,sorted(r))
        assert all(not any(c.values()) for c in r["all_session_counters"])
        for letter in "defgh":
            assert not any(r[letter]["counters"].values()),(unit,letter)
    hosts=load(HERE/"local/host-stages.json")
    assert len(hosts)==26 and all(x["returncode"]==0 for x in hosts)
    assert load(OUT/"host-output-differences.json")==[]
    executions=[json.loads(x) for x in (OUT/"executions.jsonl").read_text().splitlines()]
    assert any(x["label"]=="conformance" and x["returncode"]==0 for x in executions)
    frozen=load(OUT/"protected-before.json")
    changed=[p for p,h in frozen.items() if not (ROOT/p).is_file() or sha((ROOT/p).read_bytes())!=h]
    save=dict(status="PASS" if not changed else "FAIL",files=len(frozen),changed=changed)
    (OUT/"protected-after.json").write_text(json.dumps(save,indent=2)+"\n")
    assert not changed,changed
    current=load(OUT/"rebind-diff.json");inventory=load(OUT/"package-inventory.json")
    sd=PACKAGE/"SD_ROOT";files=sorted(sd.iterdir())
    assert len(files)==30 and all(p.is_file() and not p.is_symlink() for p in files)
    expected={r["name"]:r for r in inventory["card"]}
    assert set(expected)=={p.name for p in files}
    for p in files:assert sha(p.read_bytes())==expected[p.name]["sha256"]
    with zipfile.ZipFile(ROOT/"artifacts/downloads/gxr-151.zip") as z:
        official={Path(i.filename).name:z.read(i) for i in z.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")}
    assert len(official)==29
    assert all((sd/name).read_bytes()==data for name,data in official.items() if name!="ilaunch3")
    card="".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in files)
    assert (PACKAGE/"CARD_SHA256SUMS").read_text()==card
    card_sha=sha(card.encode());assert card_sha==inventory["card_sha256sums_sha256"]
    assert (sd/"ilaunch3").read_bytes()==(ROOT/"firmware/image_v36/local/package/SD_ROOT/ilaunch3").read_bytes()
    assert (sd/"GXRCE.DAT").read_bytes()==(HERE/"candidate/local/full-r13/GXRCE.DAT").read_bytes()
    evidence=PACKAGE/"evidence";evidence.mkdir(exist_ok=True)
    for name in ("rebind-diff.json","official-zip-verification.json","package-inventory.json","inputs.json",
                 "protected-before.json","protected-after.json","resident-body-binding.json","host-source-binding.json","current-host-runs.json","host-output-differences.json",
                 "conformance.stdout","conformance.stderr","rebind.stdout","rebind.stderr",
                 "assemble.stdout","assemble.stderr","host-compile.stdout","host-compile.stderr",
                 "host-stages.stdout","host-stages.stderr","executions.jsonl",
                 "adapter-correction.json","adapter-check.json","adapter-check.stdout","adapter-check.stderr",
                 "engine-source-copy-check.json",
                 "native-binding-adaptation.patch"):
        shutil.copyfile(OUT/name,evidence/name)
    for p in sorted(OUT.glob("native-*")):
        if p.is_file():shutil.copyfile(p,evidence/p.name)
    shutil.copyfile(HERE/"local/host-stages.json",evidence/"host-stages.json")
    shutil.copytree(HERE/"local/host-stages",evidence/"host-stages",dirs_exist_ok=True)
    shutil.copyfile(HERE/"candidate/local/commands.jsonl",evidence/"build-host-commands.jsonl")
    adaptation=[]
    for rel in ("candidate/common.py","candidate/verify_v34c.py"):
        old=(ROOT/"firmware/engine_v38_ro"/rel).read_text();new=(HERE/rel).read_text()
        adaptation.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
            fromfile="engine_v38_ro/"+rel,tofile="engine_v40_ux/"+rel))
    (evidence/"builder-host-adaptation.patch").write_text("".join(adaptation))
    sources={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in (
        HERE/"assemble_v36.py",HERE/"integration_native.py",HERE/"native_binding.py",
        HERE/"conformance_readonly.py",HERE/"run_recorded.py",HERE/"candidate/build117.py",
        ROOT/"tools/native_harness/conformance.py",ROOT/"tools/native_harness/python_backend.py")}
    (evidence/"execution-sources.json").write_text(json.dumps(sources,indent=2)+"\n")
    diffs="\n".join(f"| `0x{r['start']:02X}–0x{r['end_exclusive']-1:02X}` | {r['bytes']} | `{r['old_hex']}` | `{r['new_hex']}` |" for r in current["ranges"])
    successful_labels={x["label"] for x in executions if x["returncode"]==0}
    excerpts=[]
    for unit in native:
        texts=[]
        for p in sorted(OUT.glob("native-"+unit+"*.stdout")):
            if p.stem not in successful_labels:
                continue
            texts.extend(line for line in p.read_text().splitlines() if line.startswith("PASS "+unit+" "))
        excerpts.extend(texts)
    # Keep the report compact; the three complete native streams are in evidence.
    selected=[]
    for letter in "abcdefgh":
        prefix="PASS 50mm "+letter+" "
        selected.append(next(line for line in excerpts if line.startswith(prefix)))
    selected.append(next(line for line in excerpts if line.startswith("PASS 28mm a ")))
    excerpt="\n".join(selected)
    table="\n".join([
        "| a | PASS | PASS，ready 两字为 1 后第二次 ADJ 才发布 | PASS | 真实 rv_load 接受；source=CARD、generation=117、8 行。 |",
        "| b | PASS | PASS | PASS | 冷光标 04；S=1，九行 503 B 与 T 均为纯 04，无 RPC 写。 |",
        "| c | PASS | PASS | PASS | 应用 01，S=1、深层 01；重开高亮 01；关闭再开、02、OK 得到深层 02。 |",
        "| d | PASS | PASS | PASS | viii-b 坏 detached snapshot magic 后滚动；S=1、H08 0 次、深层仍为 01。 |",
        "| e | PASS | PASS | PASS | 含 Fn2、滚动和 OK 保存尝试；五类文件修改尝试均为 0。 |",
        "| f | PASS | PASS | PASS | 原 v3.5-bound gen117 被真实 loader 拒绝，header 返回 RESIDENT_ID；7 行，32 次 H01 无重试、无写。 |",
        "| g | PASS | PASS | PASS | 卡上 gen117 胜出；真实 gen115 两份 IROM header 拒绝，旧 GXLS/GXTS 不读，8 槽均用默认。 |",
        "| h | PASS | PASS | PASS | 应用后移卡仍可用 RAM 切换 02；32 次 H01 无重试。下次启动为纯 04、7 行，旧 IROM 均拒绝。 |",
    ])
    report=f"""v3.6 + gen 117 的三单元 M32R 组合验证 a–h 全部 PASS，22 个 Host 阶段、history、G117 三单元和原始 conformance 全部 PASS。SD_ROOT 恰好 30 个文件。本轮没有访问相机或存储卡，没有刷写；这些结果是主机上的真实指令执行，不是真机验收。

| 交付物 | 字节数 / generation | SHA-256 |
|---|---:|---|
| GXRCE.DAT。 | 55,500 / 117 | `{current['sha256']}` |
| ilaunch3，v3.6。 | 3,993,340 | `50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008` |
| resident.elf，只读输入。 | 10,672 | `5d66184ce33f280aa370ebfc1753fe74e8ad398f01558406909733cec779acff` |
| CARD_SHA256SUMS。 | 30 行 | `{card_sha}` |
| genuine gxr-151.zip，只读输入。 | 11,277,528 | `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898` |

resident build id 为 `{current['resident_build_id']}`；ABI 为 `{current['abi']}`。包内机身的 resident payload 7,884 B 及 pins 12 B 均与指定 ELF 逐字节相等。engine 为 45,948 B，BSS 为 9,652 B，1 条 relocation。28 个官方文件直接取自 genuine ZIP，并逐项与 ZIP 和提取目录比对。未使用 04168d00… mutant fixture。

相对原 gen117 `4f5eeaffdfc4df77d9482887b827fe8ec73e7857b13ea76348e3e49c874d0b5a`，全部 36 个不同字节只有以下两段，端点均含在范围内。

| 文件偏移 | 字节数 | 原字节 | 新字节 |
|---|---:|---|---|
{diffs}

独立按反射多项式 0xEDB88320 逐位重算 header CRC，先清零 0x14 的四字节字段，结果为 `0x{current['header_crc32']}`。payload CRC 仍为 `0x{current['payload_crc32']}`。0x100 起全部字节相等，payload、engine、relocation、recipe、大小均未变。详见 [字节差分](evidence/rebind-diff.json)。

| 项目 | jlaunch，50mm | qlaunch，28mm | l08firm，MOUNT | 本轮结果 |
|---|---|---|---|---|
{table}

原始输出节选如下，完整三单元结果、逐行 SHA、原生文件调用及命令退出码在 [evidence](evidence/)。

```text
{excerpt}
```

g 使用实际 gen115 `a9743bb9f0ace0ebba1d807af124210a2a098ad64f31c27083412923c841c4b8`，两份 IROM DAT 和按其绑定编码的旧 GXLS/GXTS。卡先被接受时，loader 不扫描 IROM；本轮额外调用真实 rv_header，确认两份均返回 GXRCE_RESIDENT_ID。h 的下一次启动撤掉卡后，真实 loader 才实际探测并拒绝这两份 IROM。没有把未扫描说成已扫描。旧偏好没有 open 尝试；8 槽 Fn2 均显示默认 0。既存文件逐字节不变。移卡通过文件边界撤掉 DAT 并让 sd_id 失败模拟；下一次启动使用新的解释器、BSS 和原厂单元行。

本轮实际执行包中机身、v3.6 resident、重绑 DAT 的 engine 和原生 ADJ 路径。模式 getter `0x20271FEC` 的固定返回 1 替身始终移除；未调用 preset_mode，除初始设置输入外未直接写 S，也未直接写光标。28mm 的 ready 字由原生 setter `0x200935B4` 写入。d 只在标出的 detached UI snapshot magic 注入故障。首次 loader 校验执行真实 CRC 循环；发布后沿用 harness 已自校验的 CRC 加速。介质、RPC 单元响应、绘图和部分系统调用仍是模型。

Host 使用 `firmware/resident_v36/resident/` 的 resident.c、loader.c、shared.c、hooks.c、runtime.c、validate_envelope.inc.c 和 v3.6 trust.c 重新编译，开启 ASan/UBSan 与 `-fno-sanitize-recover=all`。22 阶段为 vectors、basic、first、blackbox、neighbour、t、iso、ctl、rpc-faults、conflict、accepted-f02、same-conflict、log-fault、service-quarantine、publish-failure、store-fault、daily、rejected、r33、quarantine、irom、legacy，全部 PASS。另有 history 和三个 G117 场景，共 26 项执行记录。stdout/stderr 与 gen117 原报告的对应记录差异为 0，详见 [Host 结果](evidence/host-stages.json)。

```text
HOST_RESULT PASS stages=22 extra=history+three_units failed= []
PASS python backend conformance unrecognised instruction 0x103000
```

实际执行入口如下，均使用 `/usr/bin/python3 -I -B`。run_recorded.py 保留 stdout、stderr、命令和退出码；conformance_readonly.py 用 runpy 执行原 `tools/native_harness/conformance.py` 的 main，只把 decoder cache 重定向到获准目录。

```sh
/usr/bin/python3 -I -B firmware/engine_v40_ux/candidate/build117.py --resident-trust firmware/resident_v36/local/resident/trust.json
/usr/bin/python3 -I -B firmware/engine_v40_ux/assemble_v36.py
/usr/bin/python3 -I -B firmware/engine_v40_ux/candidate/verify_v34c.py compile
/usr/bin/python3 -I -B firmware/engine_v40_ux/run_host117.py
/usr/bin/python3 -I -B firmware/engine_v40_ux/integration_native.py 50mm
/usr/bin/python3 -I -B firmware/engine_v40_ux/integration_native.py 28mm
/usr/bin/python3 -I -B firmware/engine_v40_ux/integration_native.py mount
/usr/bin/python3 -I -B firmware/engine_v40_ux/conformance_readonly.py
```

构建脚本复制自 engine_v38_ro，原生绑定复制自 v3.6 场景入口；只在副本适配路径和测试。副本中的 C、头文件、汇编和链接脚本与原树逐字节相等。首轮文件边界适配因追加旧回调而报错，已改为替换，并用真实 native open/close 核对一次调用只生成一个 FD；失败日志保留在 evidence，最终矩阵引用修正后的成功执行。原 gen117 与机身的独立审查不属于本报告。原树、v3.5/v3.6 输入、官方固件及 tools/native_harness 共 {len(frozen):,} 个冻结文件内容变化为 0。未复用旧执行结果。

用户可见行为为：卡必须留在相机里；每次开机为纯 04，列表高亮 04。应用后重开高亮当前已提交配方。Fn2 的 OK 只保留本次开机 RAM 微调，关机后不保存。卡上不落黑盒，不把 DAT 改名为 OK，不安装到内部存储。SD_ROOT 没有 DEEPTBL*、DEEPISP*、GXRCE.CTL、GXRCE.OK 或 GXRBX*。

刷入机身时必须挂 50mm。恢复使用卡 A 的 Stage2l-50mm，挂 50mm，按住「+ 与回放」开机。本轮未执行刷入或恢复。

CARD_SHA256SUMS 的 30 个名称均相对 SD_ROOT，可用于卡写入和读回。SHA256SUMS 覆盖本目录全部文件，路径相对本目录，清单自身除外。
"""
    (PACKAGE/"REPORT.md").write_text(report)
    package_files=sorted(p for p in PACKAGE.rglob("*") if p.is_file() and p.name!="SHA256SUMS")
    sums="".join(f"{sha(p.read_bytes())}  {p.relative_to(PACKAGE).as_posix()}\n" for p in package_files)
    (PACKAGE/"SHA256SUMS").write_text(sums)
    for line in (PACKAGE/"SHA256SUMS").read_text().splitlines():
        digest,name=line.split("  ",1);assert sha((PACKAGE/name).read_bytes())==digest,name
    for line in (PACKAGE/"CARD_SHA256SUMS").read_text().splitlines():
        digest,name=line.split("  ",1);assert sha((sd/name).read_bytes())==digest,name
    print("PASS final package SD_ROOT=30 official_zip_equal=28 protected="+str(len(frozen))+" changed=0")
    print("DAT_SHA256",current["sha256"])
    print("CARD_SHA256SUMS_SHA256",card_sha)
    print("SHA256SUMS lines",len(package_files),"SHA256",sha(sums.encode()))


if __name__=="__main__":main()
