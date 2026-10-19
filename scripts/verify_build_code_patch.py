#!/usr/bin/env python3
"""Exercise real ELF rejection gates, final probe instructions, and package readback."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "research/stage1a_probe/evidence"
loader = importlib.util.spec_from_file_location("code_builder", ROOT / "scripts/build_code_patch.py")
builder = importlib.util.module_from_spec(loader)
loader.loader.exec_module(builder)
RESULTS = []


def test(name, action, rejection=None):
    try:
        action()
    except (ValueError, AssertionError, OSError, KeyError) as error:
        if rejection is None or rejection not in str(error):
            raise AssertionError(f"{name}: unexpected failure: {error}") from error
        RESULTS.append({"name": name, "kind": "reject", "passed": True, "reason": str(error)})
    else:
        if rejection:
            raise AssertionError(f"{name}: unsafe input was accepted")
        RESULTS.append({"name": name, "kind": "positive", "passed": True})


def emulate_probe(body, hook, dirty_va=None):
    """Only the emitted M32R instructions; unknown instructions/addresses fail closed.

    Execution ends at the unchanged stock formatter entry. This is host evidence,
    not a full M32R emulator or camera/stock-formatter execution.
    """
    image = bytearray(body)
    if dirty_va is not None:
        image[dirty_va - 0x2004B000 + 512] = 0
    regs = [0x13570000 + i * 17 for i in range(16)]
    regs[0] = 200
    regs[15] = 0x05017000
    stack = {}
    writes, reads = [], []
    segments = [struct.unpack_from(">5I", body, 0x20 + i * 20) for i in range(16)]
    def read(address, size):
        for src, va, length, _, _ in segments:
            if va <= address and address + size <= va + length:
                offset = src + 512 + address - va
                return int.from_bytes(image[offset:offset + size], "big")
        if address in stack and size == 4:
            return stack[address]
        raise AssertionError(f"Probe accesses unknown address 0x{address:X}")
    def signed(value, bits):
        return value - 2 ** bits if value >= 2 ** (bits - 1) else value
    pc = builder.number(hook["context_va"])
    initial = regs.copy()
    carry = False
    entries = 0
    for _ in range(100000):
        if pc == 0x200BBC7C:
            break
        if pc == 0x200547B0:
            entries += 1
        word = read(pc & ~3, 4)
        if pc % 4 == 0 and word >> 24 >= 0x80:
            first, second = (word >> 24) & 255, (word >> 16) & 255
            if first & 0xF0 == 0xD0 and second == 0xC0:
                regs[first & 15] = (word & 0xFFFF) << 16
                pc += 4
            elif first & 0xF0 == 0x80 and second & 0xF0 == 0xE0:
                regs[first & 15] = regs[second & 15] | (word & 0xFFFF)
                pc += 4
            elif first & 0xF0 == 0xB0 and second & 0xF0 == 0x10:
                pc = pc + signed(word & 0xFFFF, 16) * 4 if regs[first & 15] != regs[second & 15] else pc + 4
            elif first == 0xFE:
                regs[14] = pc + 4
                pc += signed(word & 0xFFFFFF, 24) * 4
            else:
                raise AssertionError(f"Unsupported 32-bit instruction {word:08X} at {pc:08X}")
            continue
        half = read(pc, 2)
        # The reviewed parallel companion is NOP; no data-dependent parallel ops.
        if half in (0x7000, 0xF000):
            pc += 2
        elif half & 0xF000 == 0x6000:
            regs[(half >> 8) & 15] = signed(half & 255, 8) & 0xFFFFFFFF
            pc += 2
        elif half & 0xF000 == 0x4000:
            r = (half >> 8) & 15
            regs[r] = (regs[r] + signed(half & 255, 8)) & 0xFFFFFFFF
            pc += 2
        elif half & 0xF0F0 == 0x2080:
            dest, base = (half >> 8) & 15, half & 15
            address = regs[base]
            reads.append(address)
            regs[dest] = signed(read(address, 1), 8) & 0xFFFFFFFF
            pc += 2
        elif half & 0xFFF0 == 0x0050:
            carry = regs[(half >> 8) & 15] < regs[half & 15]
            pc += 2
        elif half >> 8 in (0x7C, 0x7F):
            if half >> 8 == 0x7F or carry:
                pc = (pc & ~3) + signed(half & 255, 8) * 4
            else:
                pc += 2
        elif half & 0xF0FF == 0x207F:
            r = (half >> 8) & 15
            regs[15] -= 4
            stack[regs[15]] = regs[r]
            writes.append(regs[15])
            pc += 2
        elif half & 0xF0F0 == 0x2040:
            source, base = (half >> 8) & 15, half & 15
            assert base == 15, "Probe may only store a format pointer on the caller stack"
            stack[regs[base]] = regs[source]
            writes.append(regs[base])
            pc += 2
        elif half & 0xFFF0 == 0x1FC0:
            pc = regs[half & 15]
        else:
            raise AssertionError(f"Unsupported 16-bit instruction {half:04X} at {pc:08X}")
    else:
        raise AssertionError("Probe did not reach stock formatter")
    assert pc == 0x200BBC7C and entries == 1
    assert regs[15] == initial[15] - 8
    assert regs[14] == builder.number(hook["return_va"])
    assert regs[4] == 0x20234BD0 and regs[5:14] == initial[5:14]
    assert stack[regs[15] + 4] == 200
    assert writes == [initial[15] - 4, initial[15] - 8, initial[15] - 8]
    label = bytearray()
    address = stack[regs[15]]
    for i in range(6):
        label.append(read(address + i, 1))
    expected = b"OK %d\0" if dirty_va is None else b"NG %d\0"
    assert bytes(label) == expected
    last_read = dirty_va if dirty_va is not None else 0x200547AF
    assert reads == list(range(0x2005276C, last_read + 1))
    return {"hook": hook["va"], "dirty_va": f"0x{dirty_va:08X}" if dirty_va else None,
            "format": label[:-1].decode(), "bytes_checked": len(reads),
            "tail_target": "0x200BBC7C", "registers_and_varargs_preserved": True}


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    spec_bytes = (ROOT / "firmware/stage1a_probe/spec.json").read_bytes()
    spec = json.loads(spec_bytes)
    files = builder.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")
    csv_path = ROOT / "research/firmware/ilaunch3-sections.csv"
    protected = [ROOT / p for p in ("scripts/build_drill.py", "research/stage1_brief/COMMON.md",
                 "research/stage1_codespace/REPORT.md", "research/phase0_drill/ROOT_VERIFICATION.md",
                 "research/phase0_drill/FLASH_AND_RECOVERY.md")]
    before = {str(p.relative_to(ROOT)): builder.sha(p.read_bytes()) for p in protected}
    outputs, report, manifest = builder.build(files, spec, csv_path)
    original, changed = files["ilaunch3"], outputs["ilaunch3"]
    test("official-29-file-positive", lambda: builder.drill.check_official(files))
    def identity():
        assert len(original) == len(changed)
        assert {n for n in files if files[n] != outputs[n]} == {"ilaunch3"}
        assert all(files[n] == outputs[n] for n in files if n != "ilaunch3")
        assert original[:0x16C] == changed[:0x16C] and original[0x170:512] == changed[0x170:512]
        calculated = sum(value * (i % 6 + 2) for i, value in enumerate(changed[512:])) & 0xFFFFFFFF
        assert calculated == struct.unpack_from(">I", changed, 0x16C)[0]
        diffs = [i for i, (a, b) in enumerate(zip(original, changed)) if a != b]
        allowed = [(0x99B0, 0x9A00), (0x2CEE7C, 0x2CEE80), (0x2CD664, 0x2CD668), (0x16C, 0x170)]
        assert all(any(a <= i < b for a, b in allowed) for i in diffs)
        assert len(diffs) == 89
    test("independent-container-byte-and-checksum-positive", identity)
    for delta in (-0x2000000, 0x1FFFFFC):
        def boundary(delta=delta):
            pc, target = 0x2028A000, 0x2028A000 + delta
            raw = builder.encode_bl24(pc, target)
            assert builder.decode_branch(raw, pc, "BL24") == target
            assert f"bl 0x{target:x}" in builder.disassemble(raw, pc)
        test(f"BL24-valid-boundary-{delta}", boundary)
    for delta in (-0x2000004, 0x2000000):
        test(f"BL24-out-of-range-{delta}", lambda d=delta: builder.encode_bl24(0x2028A000, 0x2028A000 + d), "out of range")
    test("BL8-out-of-range", lambda: builder.branch_delta(0x200547B0, 0x200549B0, 8, True), "out of range")
    test("conditional16-out-of-range", lambda: builder.branch_delta(0x200547B0, 0x200747B0, 16), "out of range")
    test("unaligned-BL24-target", lambda: builder.encode_bl24(0x20319C7C, 0x200547B2), "aligned")
    test("unaligned-BL24-PC", lambda: builder.encode_bl24(0x20319C7E, 0x200547B0), "PC must be aligned")
    probes = []
    for hook in manifest["hooks"]:
        for dirty in (None, 0x2005276C, 0x2005378E, 0x200547AF):
            result = {}
            def execution():
                result.update(emulate_probe(changed, hook, dirty))
            test(f"final-bytes-{hook['va']}-{'OK' if dirty is None else hex(dirty)}", execution)
            probes.append(result)
    with tempfile.TemporaryDirectory(prefix="gxr-code-gates-") as temp:
        temp = Path(temp)
        serial = 0
        def mutate_asset(base, key, transform):
            nonlocal serial
            serial += 1
            _, raw = builder.asset(base[key])
            data = bytearray(raw)
            transform(data)
            path = temp / f"asset-{serial}"
            path.write_bytes(data)
            result = copy.deepcopy(base)
            result[key] = {"path": str(path), "sha256": builder.sha(data)}
            return result
        def mutate_approval(transform):
            _, raw = builder.asset(spec["approval"])
            value = json.loads(raw)
            transform(value)
            encoded = json.dumps(value).encode()
            return mutate_asset(spec, "approval", lambda b: b.__setitem__(slice(None), encoded))
        elf_bytes = builder.asset(spec["elf"])[1]
        elf = builder.parse_elf(elf_bytes)
        shoff = struct.unpack_from(">I", elf_bytes, 32)[0]
        phoff = struct.unpack_from(">I", elf_bytes, 28)[0]
        text_index = next(s["index"] for s in elf["sections"] if s["name"] == ".text")
        ro_index = next(s["index"] for s in elf["sections"] if s["name"] == ".rodata")
        syms = next(s for s in elf["sections"] if s["name"] == ".symtab")
        entry_symbol_off = next(off for off in range(syms["offset"] + 16, syms["offset"] + syms["size"], 16)
                                if struct.unpack_from(">I", elf_bytes, off + 4)[0] == 0x200547B0
                                and elf_bytes[off + 12] & 15 == 2)
        cases = [
            ("ELF64-rejected", lambda b: b.__setitem__(4, 2), "ELF32/MSB"),
            ("little-endian-rejected", lambda b: b.__setitem__(5, 1), "ELF32/MSB"),
            ("wrong-machine-rejected", lambda b: struct.pack_into(">H", b, 18, 40), "M32R"),
            ("relocatable-object-rejected", lambda b: struct.pack_into(">H", b, 16, 1), "executable"),
            ("writable-section-rejected", lambda b: struct.pack_into(">I", b, shoff + text_index * 40 + 8, 7), "Writable"),
            ("undefined-symbol-rejected", lambda b: struct.pack_into(">H", b, entry_symbol_off + 14, 0), "Undefined"),
            ("common-symbol-rejected", lambda b: struct.pack_into(">H", b, entry_symbol_off + 14, 0xFFF2), "COMMON"),
            ("remaining-relocation-rejected", lambda b: struct.pack_into(">I", b, shoff + ro_index * 40 + 4, 9), "relocation"),
            ("writable-program-segment-rejected", lambda b: struct.pack_into(">I", b, phoff + 24, 7), "writable ELF program"),
            ("NOBITS-section-rejected", lambda b: struct.pack_into(">I", b, shoff + ro_index * 40 + 4, 8), "NOBITS"),
            ("orphan-section-rejected", lambda b: b.__setitem__(slice(None), bytes(b).replace(b".rodata\0", b".xodata\0")), "orphan"),
        ]
        for name, mutate, reason in cases:
            bad = mutate_asset(spec, "elf", mutate)
            test(name, lambda b=bad: builder.build(files, b, csv_path), reason)
        bad = mutate_asset(spec, "payload", lambda b: b.__setitem__(0, b[0] ^ 1))
        test("ELF-payload-disagree", lambda: builder.build(files, bad, csv_path), "Payload differs")
        bad = mutate_asset(spec, "map", lambda b: b.__setitem__(slice(None), bytes(b).replace(b".text           0x200547b0", b".text           0x200547b4", 1)))
        test("map-ELF-disagree", lambda: builder.build(files, bad, csv_path), "Map section")
        bad = mutate_approval(lambda a: a["code_ranges"][0].update(original_sha256="0" * 64))
        test("original-byte-hash-disagree", lambda: builder.build(files, bad, csv_path), "original bytes hash")
        def shrink(a):
            r = a["code_ranges"][0]
            r.update(va_start="0x200547B4", file_start="0x99B4", original_sha256=builder.sha(original[0x99B4:0x9A00]))
        bad = mutate_approval(shrink)
        test("unapproved-code-range", lambda: builder.build(files, bad, csv_path), "unapproved range")
        bad = mutate_approval(lambda a: a["hooks"][0].update(expected="1f c0 f0 00"))
        test("hook-original-byte-disagree", lambda: builder.build(files, bad, csv_path), "original bytes mismatch")
        bad = mutate_approval(lambda a: a["hooks"][0].update(context_expected="21" + a["hooks"][0]["context_expected"][2:]))
        test("argument-preparation-disagree", lambda: builder.build(files, bad, csv_path), "argument preparation")
        bad = mutate_approval(lambda a: a["hooks"][0].update(return_va="0x20319C84"))
        test("return-position-disagree", lambda: builder.build(files, bad, csv_path), "return position")
        bad = mutate_approval(lambda a: a["code_ranges"][0].update(file_start="0x796D"))
        test("approved-VA-file-disagree", lambda: builder.build(files, bad, csv_path), "range mapping differs")
        bad = copy.deepcopy(spec)
        bad["hooks"][0]["va"] = "0x20319C80"
        test("unapproved-hook-range", lambda: builder.build(files, bad, csv_path), "unapproved range")
        bad = copy.deepcopy(spec)
        bad["hooks"][1]["va"] = bad["hooks"][0]["va"]
        test("overlapping-hooks", lambda: builder.build(files, bad, csv_path), "Duplicate hook")
        bad = copy.deepcopy(spec)
        bad["branch_assertions"][0]["target_symbol"] = "probe_format"
        test("payload-branch-target-disagree", lambda: builder.build(files, bad, csv_path), "branch target mismatch")
        bad = copy.deepcopy(spec)
        bad["branch_assertions"].pop()
        test("missing-branch-assertion", lambda: builder.build(files, bad, csv_path), "assertion list disagree")
        bad = copy.deepcopy(spec)
        bad["mode"] = "production"
        test("unverified-production-mode", lambda: builder.build(files, bad, csv_path), "experiment only")
        bad = copy.deepcopy(spec)
        bad["elf"]["sha256"] = "0" * 64
        test("stale-ELF-asset-hash", lambda: builder.build(files, bad, csv_path), "Asset hash")
        bad = dict(files)
        bad["ilaunch4"] = bad["ilaunch4"][:-1] + bytes([bad["ilaunch4"][-1] ^ 1])
        test("nonofficial-28th-file", lambda: builder.build(bad, spec, csv_path), "Not the official")
        bad = dict(files)
        del bad["ilaunch0"]
        test("missing-official-file", lambda: builder.build(bad, spec, csv_path), "29 official")
        csv_bad = temp / "wrong.csv"
        csv_bad.write_text(csv_path.read_text().replace("0,0,512,", "0,0,516,", 1))
        test("CSV-header-disagree", lambda: builder.build(files, spec, csv_bad), "CSV and official header")
    test("SD-Volumes-write-refused", lambda: builder.write_package(Path('/Volumes/stage1a-forbidden'), files, outputs, report, copy.deepcopy(manifest)), "SD/Volumes writes forbidden")
    builder.PACKAGES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verification-", dir=builder.PACKAGES) as temp:
        package = Path(temp) / "new-package"
        def package_positive():
            builder.write_package(package, files, outputs, report, copy.deepcopy(manifest))
            for tree in ("probe", "recovery-official-1.51"):
                root = package / tree / "SD_ROOT"
                assert len(list(root.iterdir())) == 29
                result = subprocess.run(["shasum", "-a", "256", "-c", str(package / tree / "SHA256SUMS")],
                                        cwd=root, capture_output=True, text=True, check=True)
                assert result.stdout.count(": OK") == 29
        test("full-29-plus-29-package-readback-and-shasum", package_positive)
        test("existing-package-overwrite-refused", lambda: builder.write_package(package, files, outputs, report, copy.deepcopy(manifest)), "overwrite")
        probe_root = package / "probe/SD_ROOT"
        recovery_root = package / "recovery-official-1.51/SD_ROOT"
        victim = probe_root / "ilaunch4"
        raw = victim.read_bytes()
        victim.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        test("written-other-file-tamper-detected", lambda: builder.drill.check_written(probe_root, recovery_root, files, report), "changed but has no patch")
        victim.write_bytes(raw)
        victim = recovery_root / "ilaunch3"
        victim.write_bytes(changed)
        test("recovery-must-be-official", lambda: builder.drill.check_written(probe_root, recovery_root, files, report), "Not the official")
    after = {str(p.relative_to(ROOT)): builder.sha(p.read_bytes()) for p in protected}
    test("protected-existing-inputs-unchanged", lambda: builder.require(before == after, "Protected inputs changed"))
    result = {"schema": "gxr-code-patch-verification-v1", "passed": len(RESULTS),
              "positive": sum(r["kind"] == "positive" for r in RESULTS),
              "rejections": sum(r["kind"] == "reject" for r in RESULTS), "failed": 0,
              "tests": RESULTS, "probe_instruction_replays": probes,
              "protected_inputs": before, "builder_sha256": builder.sha((ROOT / "scripts/build_code_patch.py").read_bytes()),
              "spec_sha256": builder.sha(spec_bytes), "elf_sha256": spec["elf"]["sha256"],
              "payload_sha256": spec["payload"]["sha256"], "ilaunch3_sha256": manifest["probe_sha256"]["ilaunch3"],
              "runtime_boundary": "Host replay of only emitted instructions; camera and stock formatter execution not tested"}
    (HERE / "builder-verification.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: result[k] for k in ("passed", "positive", "rejections", "failed", "ilaunch3_sha256")}))


if __name__ == "__main__":
    main()
