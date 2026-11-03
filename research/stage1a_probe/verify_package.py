#!/usr/bin/env python3
"""Independently verify the final on-disk package, not a builder return value."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PKG = ROOT / "artifacts/stage1a-probe/packages/stage1a-probe-ok-ng"
FW = ROOT / "artifacts/firmware/gxr-1.51"
OUT = HERE / "evidence"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest = json.loads((PKG / "manifest.json").read_text())
    tests = json.loads((OUT / "builder-verification.json").read_text())
    assert tests["failed"] == 0 and tests["passed"] == 52
    assert tests["builder_sha256"] == sha((ROOT / "scripts/build_code_patch.py").read_bytes())
    assert manifest["tool_sha256"]["scripts/build_code_patch.py"] == tests["builder_sha256"]
    for name, expected in tests["protected_inputs"].items():
        assert sha((ROOT / name).read_bytes()) == expected
    for name, expected in manifest["tool_sha256"].items():
        assert sha((ROOT / name).read_bytes()) == expected
    for a in manifest["assets"].values():
        path = Path(a["path"])
        if not path.is_absolute():
            path = ROOT / path
        assert sha(path.read_bytes()) == a["sha256"]
    assert sha((ROOT / "firmware/stage1a_probe/spec.json").read_bytes()) == manifest["spec_sha256"] == tests["spec_sha256"]
    roots = {"probe": PKG / "probe/SD_ROOT", "recovery": PKG / "recovery-official-1.51/SD_ROOT"}
    expected_names = sorted(manifest["recovery_sha256"])
    inventory = {}
    for kind, root in roots.items():
        assert sorted(p.name for p in root.iterdir()) == expected_names
        assert all(p.is_file() and not p.is_symlink() for p in root.iterdir())
        hashes = manifest["probe_sha256"] if kind == "probe" else manifest["recovery_sha256"]
        for name in expected_names:
            assert sha((root / name).read_bytes()) == hashes[name]
            if kind == "recovery" or name != "ilaunch3":
                assert (root / name).read_bytes() == (FW / name).read_bytes()
        result = subprocess.run(["shasum", "-a", "256", "-c", str(root.parent / "SHA256SUMS")],
                                cwd=root, capture_output=True, text=True, check=True)
        assert result.stdout.count(": OK") == 29
        (OUT / f"final-{kind}-shasum.txt").write_text(result.stdout)
        inventory[kind] = {"files": 29, "all_sha256_verified": True,
                           "SHA256SUMS_sha256": sha((root.parent / "SHA256SUMS").read_bytes())}
    original = (FW / "ilaunch3").read_bytes()
    final = (roots["probe"] / "ilaunch3").read_bytes()
    assert len(final) == len(original) == 3993340
    assert final[:0x16C] == original[:0x16C] and final[0x170:512] == original[0x170:512]
    scalar_sum = sum(byte * (i % 6 + 2) for i, byte in enumerate(final[512:])) & 0xFFFFFFFF
    assert struct.unpack_from(">I", final, 0x16C)[0] == scalar_sum == 0x6ACCE776
    payload = (ROOT / "firmware/stage1a_probe/build/probe.bin").read_bytes()
    assert final[0x99B0:0x9A00] == payload
    assert set(final[0x796C:0x99B0]) == {255}
    assert len(final[0x796C:0x99B0]) == 8260
    allowed = [(0x99B0, 0x9A00), (0x2CEE7C, 0x2CEE80), (0x2CD664, 0x2CD668), (0x16C, 0x170)]
    diffs = [i for i, (a, b) in enumerate(zip(original, final)) if a != b]
    assert len(diffs) == 89 and all(any(a <= i < b for a, b in allowed) for i in diffs)
    cmp_result = subprocess.run(["cmp", "-l", str(FW / "ilaunch3"), str(roots["probe"] / "ilaunch3")],
                                capture_output=True, text=True)
    assert cmp_result.returncode == 1 and len(cmp_result.stdout.splitlines()) == 89
    (OUT / "final-ilaunch3-cmp.txt").write_text(cmp_result.stdout)
    parts = []
    for va, start, end, target in [(0x200547B0, 0x99B0, 0x99F4, None),
                                   (0x20319C5C, 0x2CEE5C, 0x2CEE84, 0x20319C7C),
                                   (0x20318444, 0x2CD644, 0x2CD66C, 0x20318464)]:
        raw = OUT / f"final-window-{va:08x}.bin"
        raw.write_bytes(final[start:end])
        result = subprocess.run([str(OBJDUMP), "-D", "-b", "binary", "-m", "m32r", "-EB",
                                 f"--adjust-vma=0x{va:x}", str(raw)], capture_output=True, text=True, check=True)
        (raw.with_suffix(".txt")).write_text(result.stdout)
        if target:
            pc = target
            source = start + pc - va
            word = int.from_bytes(final[source:source + 4], "big")
            disp = word & 0xFFFFFF
            if disp & 0x800000:
                disp -= 0x1000000
            assert word >> 24 == 0xFE and pc + disp * 4 == 0x200547B0
            assert "bl 0x200547b0" in result.stdout
            assert "addi sp,#8" in result.stdout
        parts.append({"va": f"0x{va:08X}", "file_start": f"0x{start:X}", "file_end": f"0x{end:X}",
                      "sha256": sha(raw.read_bytes()), "disassembly": raw.with_suffix(".txt").name})
    qualification = manifest["qualification"]
    assert qualification["camera_execution_verified"] is False
    assert qualification["runtime_region_persistence_verified"] is False
    receipt = {"package": str(PKG.relative_to(ROOT)), "inventory": inventory,
               "manifest_sha256": sha((PKG / "manifest.json").read_bytes()),
               "ilaunch3_sha256": sha(final), "ilaunch3_changed_bytes": len(diffs),
               "equal_length_replacement_bytes": manifest["ilaunch3_replacement_bytes"],
               "payload_changed_bytes": manifest["ilaunch3_payload_changed_bytes"],
               "checksum_phase": 0, "checksum": f"0x{scalar_sum:08X}",
               "all_other_28_files_identical": True, "all_recovery_29_files_identical": True,
               "headers_unchanged_except_checksum": True, "checked_ff_bytes": 8260,
               "final_disassembly_windows": parts, "tests_passed": tests["passed"],
               "test_rejections": tests["rejections"], "qualification": qualification}
    (OUT / "package-verification.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    text = f"""# 最终包独立落盘核验

最终目录 `{receipt['package']}` 已通过电脑上的独立核验。探针版与恢复版各 29 个文件；其余 28 个文件及全部恢复文件与官方逐字节相同。真机执行、区域持久性和本机恢复均待测。

核验脚本：[verify_package.py](verify_package.py)。它直接读成品，未调用构建器的 build 或接受其返回数据作字节证据。

| 项目 | 结果 |
|---|---|
| 实际变更文件 | 仅 ilaunch3 |
| 文件长度 | 3,993,340 字节，保持原长度 |
| 等长替换跨度 | 88 字节（80 字节探针＋两处 4 字节调用） |
| 实际变化字节 | 86 个 payload 字节＋3 个校验字节＝89 字节；cmp -l 独立确认 |
| 未改写的检查区 | 文件 [0x796C,0x99B0)，8,260 字节全部 FF |
| 校验 | 相位 0；0x6ACDB212 → 0x6ACCE776；逐字节标量重算相同 |
| ELF/payload/map/spec/approval | 全部与 manifest 哈希相同 |
| 最终挂钩字节 | 0x2CEE7C: FE F4 EA CD；0x2CD664: FE F4 F0 D3；独立反汇编均指向 0x200547B0 |
| 构建器验证 | 52 项通过，含 14 个正向项目、38 个拒绝项目；0 失败 |
| 原有 build_drill.py 与四份指定报告 | 与测试前哈希相同 |

SHA-256 身份如下。

| 文件 | SHA-256 |
|---|---|
| 探针 ilaunch3 | `{receipt['ilaunch3_sha256']}` |
| 探针 SHA256SUMS | `{inventory['probe']['SHA256SUMS_sha256']}` |
| 官方恢复 SHA256SUMS | `{inventory['recovery']['SHA256SUMS_sha256']}` |
| manifest.json | `{receipt['manifest_sha256']}` |

证据：[package-verification.json](evidence/package-verification.json)、[builder-verification.json](evidence/builder-verification.json)、[cmp 差异](evidence/final-ilaunch3-cmp.txt)、[探针 29 文件哈希](evidence/final-probe-shasum.txt)、[恢复 29 文件哈希](evidence/final-recovery-shasum.txt)。

最终成品的两个挂钩窗口包含未改动的参数准备和返回后的栈清理，见 [正常回放](evidence/final-window-20319c5c.txt)、[另一份回放](evidence/final-window-20318444.txt)。探针 [最终代码](evidence/final-window-200547b0.txt) 的 ELF 原始反汇编另存于 `firmware/stage1a_probe/build/probe.disasm.txt`。

没有对 SD 卡或 `/Volumes` 执行写入。相机执行测试是 [FLASH_AND_CHECK.md](FLASH_AND_CHECK.md) 中的待测步骤；宿主重放没有执行完整原厂格式化函数或相机硬件。
"""
    (HERE / "PACKAGE_VERIFICATION.md").write_text(text)
    print(json.dumps({k: receipt[k] for k in ("ilaunch3_changed_bytes", "all_other_28_files_identical", "all_recovery_29_files_identical", "tests_passed", "checksum")}))


if __name__ == "__main__":
    main()
