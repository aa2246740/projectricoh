#!/usr/bin/env python3
"""Acceptance and mutation rejections for the in-place rewrite and final package."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("function_rewrite", ROOT / "scripts/build_function_rewrite.py")
b = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b)


def verify(output, package=None, equivalence=None):
    output = output.resolve()
    if output.exists() or not (output.is_relative_to(ROOT / "research/stage1a_probe_v2") or output.is_relative_to(Path("/private/tmp"))):
        raise ValueError("Use a new v2 research or /tmp verification file")
    files = b.legacy.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")
    spec = json.loads((ROOT / "firmware/stage1a_probe_v2/spec.json").read_text())
    csv = ROOT / "research/firmware/ilaunch3-sections.csv"
    results = []

    def check(name, action, rejected=False):
        try:
            action()
        except (ValueError, AssertionError, KeyError, OSError) as error:
            if not rejected:
                raise AssertionError(f"{name}: {error}") from error
            results.append({"name": name, "kind": "rejection", "passed": True,
                            "exception": type(error).__name__, "reason": str(error)})
        else:
            if rejected:
                raise AssertionError(f"{name}: unsafe input accepted")
            results.append({"name": name, "kind": "positive", "passed": True})

    def expect(value, message):
        if not value:
            raise AssertionError(message)

    outputs, report, manifest = b.build(files, spec, csv)
    check("official_29_sha256", lambda: b.legacy.drill.check_official(files))
    check("equal_length_ilaunch3_only", lambda: expect(
        len(outputs["ilaunch3"]) == len(files["ilaunch3"]) and
        [n for n in files if files[n] != outputs[n]] == ["ilaunch3"], "Output scope differs"))
    check("all_8340_candidate_bytes_official_ff", lambda: expect(
        outputs["ilaunch3"][0x796C:0x9A00] == b"\xff" * 8340, "Candidate differs"))
    check("exact_424_replacement_and_386_changed_bytes", lambda: expect(
        manifest["ilaunch3_replacement_bytes"] == 424 and manifest["ilaunch3_total_changed_bytes"] == 386, "Diff count"))
    check("84_freed_56_probe_12_strings_16_padding", lambda: expect(
        [manifest["code"][k] for k in ("freed_bytes", "probe_bytes", "string_bytes", "remaining_padding_bytes")]
        == [84, 56, 12, 16], "Compaction sizes"))
    check("25_independently_encoded_branches", lambda: expect(len(manifest["code"]["branches"]) == 25, "Branch count"))
    check("checksum_phase0_and_unchanged_header", lambda: expect(
        b.legacy.drill.checksum_phase(outputs["ilaunch3"]) == 0 and
        outputs["ilaunch3"][:0x16C] == files["ilaunch3"][:0x16C] and
        outputs["ilaunch3"][0x170:0x200] == files["ilaunch3"][0x170:0x200], "Header/checksum differs"))
    independent_checksum = sum(byte * (i % 6 + 2) for i, byte in enumerate(outputs["ilaunch3"][0x200:])) & 0xFFFFFFFF
    check("independent_bytewise_header_checksum", lambda: expect(
        independent_checksum == struct.unpack_from(">I", outputs["ilaunch3"], 0x16C)[0], "Independent checksum differs"))

    with tempfile.TemporaryDirectory(prefix="gxr-v2-rejections-", dir="/tmp") as temp:
        scratch = Path(temp)
        counter = 0

        def asset(data, suffix):
            nonlocal counter
            counter += 1
            path = scratch / f"{counter}-{suffix}"
            path.write_bytes(data)
            return {"path": str(path), "sha256": b.sha(data)}

        def reject_spec(name, mutate):
            changed = copy.deepcopy(spec)
            mutate(changed)
            check(name, lambda: b.build(files, changed, csv), True)

        def reject_policy(name, mutate):
            changed = copy.deepcopy(spec)
            policy = json.loads(b.legacy.asset(changed["approval"])[1])
            mutate(changed, policy)
            changed["approval"] = asset(json.dumps(policy).encode(), "approval.json")
            check(name, lambda: b.build(files, changed, csv), True)

        changed = dict(files)
        del changed["ilaunch8"]
        check("only_28_official_files", lambda: b.build(changed, spec, csv), True)
        for name in ("jlaunch3", "ilaunch3"):
            modified = dict(files)
            modified[name] = bytes([files[name][0] ^ 1]) + files[name][1:]
            check("modified_official_" + name, lambda modified=modified: b.build(modified, spec, csv), True)
        reject_spec("nonexperimental_mode", lambda x: x.update(mode="production"))
        reject_spec("wrong_patch_kind", lambda x: x.update(patch_kind="unrestricted"))
        reject_spec("reintroduced_update_guard", lambda x: x.update(update_mode_guard=True))
        reject_spec("missing_slot", lambda x: x["ranges"].pop())
        reject_spec("missing_branch_assertion", lambda x: x["branch_assertions"].pop())
        reject_spec("duplicate_branch_assertion", lambda x: x["branch_assertions"].append(x["branch_assertions"][0]))
        reject_spec("wrong_branch_target", lambda x: x["branch_assertions"][0].update(target="0x2005276C"))
        reject_spec("wrong_asset_hash", lambda x: x["elf"].update(sha256="0" * 64))
        reject_spec("wrong_source_hash", lambda x: x["sources"]["rewrite.S"].update(sha256="0" * 64))
        reject_spec("wrong_expected_final_hash", lambda x: x.update(expected_ilaunch3_sha256="0" * 64))
        reject_spec("wrong_expected_changed_count", lambda x: x.update(expected_changed_bytes=385))
        for name, field, value in (("moved_va", "va_start", "0x203183EC"),
                                   ("changed_length", "va_end", "0x203184B8"),
                                   ("moved_file_offset", "file_start", "0x2CD5EC"),
                                   ("wrong_original_bytes", "original_bytes", "00" * 212),
                                   ("wrong_original_hash", "original_sha256", "0" * 64)):
            def mutate(x, p, field=field, value=value):
                x["ranges"][0][field] = value
                p["ranges"][0][field] = value
            reject_policy(name, mutate)
        reject_policy("approval_wrong_official_identity", lambda x, p: p.update(official_ilaunch3_sha256="0" * 64))
        reject_spec("map_section_mismatch", lambda x: x.update(map=asset(b"wrong map\n", "map")))
        reject_spec("payload_different_from_elf", lambda x: x.update(payload=asset(b"wrong payload", "bin")))
        for kind, pc, target in (("BL24", 0x20319C00, 0x22319C00),
                                 ("BRA8", 0x20319C00, 0x20319E00),
                                 ("BEQZ16", 0x20319C00, 0x20339C00)):
            check("out_of_range_" + kind,
                  lambda kind=kind, pc=pc, target=target: b.encode_branch(
                      {"kind": kind, "va": hex(pc), "target": hex(target), "opcode": "b080"}), True)
        check("unaligned_BL24", lambda: b.encode_branch({"kind": "BL24", "va": "0x20319C00", "target": "0x20062752"}), True)
        raw = b.legacy.asset(spec["elf"])[1]
        elf = b.legacy.parse_elf(raw, inplace=True)

        def reject_elf(name, mutation):
            data = bytearray(raw)
            mutation(data)
            check(name, lambda: b.legacy.parse_elf(data, inplace=True), True)

        shoff = struct.unpack_from(">I", raw, 32)[0]
        text = elf["allocated"][0]
        symbols = next(s for s in elf["sections"] if s["name"] == ".symtab")
        reject_elf("ELF_wrong_endianness", lambda x: x.__setitem__(5, 1))
        reject_elf("ELF_wrong_machine", lambda x: struct.pack_into(">H", x, 18, 3))
        reject_elf("ELF_writable_text", lambda x: struct.pack_into(">I", x, shoff + text["index"] * 40 + 8, 7))
        reject_elf("ELF_NOBITS", lambda x: struct.pack_into(">I", x, shoff + text["index"] * 40 + 4, 8))
        reject_elf("ELF_remaining_relocation", lambda x: struct.pack_into(">I", x, shoff + symbols["index"] * 40 + 4, 4))
        reject_elf("ELF_undefined_symbol", lambda x: struct.pack_into(">H", x, symbols["offset"] + 16 + 14, 0))
        reject_elf("ELF_wrong_text_VA", lambda x: struct.pack_into(">I", x, shoff + text["index"] * 40 + 12, 0x2005276C))
        reject_elf("ELF_extra_slot_byte", lambda x: struct.pack_into(">I", x, shoff + text["index"] * 40 + 20, 216))
        damaged = copy.deepcopy(elf)
        payload = bytearray(damaged["payload"])
        payload[0x203183F8 - damaged["start"] + 3] ^= 1
        damaged["payload"] = bytes(payload)
        check("final_branch_byte_corrupted", lambda: b.audit_branches(damaged, spec["branch_assertions"], manifest["code"]["disassembly"]), True)
        replay_spec = importlib.util.spec_from_file_location("producer_replay", ROOT / "research/stage1a_probe_v2/replay_equivalence.py")
        replay = importlib.util.module_from_spec(replay_spec)
        replay_spec.loader.exec_module(replay)
        official_image = replay.Image(files["ilaunch3"])
        formats = {elf["symbols"][n]["value"] for n in ("probe_ok_string", "probe_ng_string")}
        for name, va, replacement, iso, argument, low, changed_byte in (
            ("emulation_short_scan", 0x20319CA0, bytes.fromhex("91 f0 20 93"), 200, 1, 0, None),
            ("emulation_skipped_first_byte", 0x20319C9C, bytes.fromhex("80 e0 27 6d"), 200, 1, 0, None),
            ("emulation_condition_bit_clobber", 0x20319CAC, bytes.fromhex("43 01 02 43"), 200, 1, 0, None),
            ("emulation_removed_second_load", 0x20319C2C, bytes.fromhex("70 00 70 00"), 200, 1, 0, None),
            ("emulation_wrong_display_node", 0x20319C8C, bytes.fromhex("a4 94 44 60"), 200, 1, 0, None),
            ("emulation_early_return_r0_changed", 0x20318490, bytes.fromhex("40 08 1f ce"), -1, 0, 0, None),
            ("emulation_low_iso_routed_through_probe", 0x20319C80,
                b.encode_branch({"kind": "BL24", "va": "0x20319C80", "target": "0x20319C98"}), 200, 1, 1, None),
            ("emulation_candidate_instruction_fetch", 0x20319C54,
                b.encode_branch({"kind": "BL24", "va": "0x20319C54", "target": "0x2005276C"}), 200, 1, 0, None),
            ("emulation_NG_changed_to_OK", 0x20319CC4, bytes.fromhex("70 00 70 00"), 200, 1, 0, replay.HI - 1)):
            image = bytearray(outputs["ilaunch3"])
            offset = official_image.offset(va, len(replacement))
            image[offset:offset + len(replacement)] = replacement
            check(name, lambda image=image, iso=iso, argument=argument, low=low, changed_byte=changed_byte:
                  replay.compare_case(official_image, replay.Image(bytes(image)),
                    (0x20319C00, argument, iso, iso, low, changed_byte, 1, 0, 1), formats), True)
        unqualified = copy.deepcopy(manifest)
        check("packaging_without_equivalence", lambda: b.write_package(
            b.legacy.PACKAGES / spec["name"], files, outputs, report, unqualified), True)
        qualified = copy.deepcopy(manifest)
        qualified["qualification"]["exhaustive_equivalence_verified"] = True
        check("Volumes_output", lambda: b.write_package(
            Path("/Volumes/forbidden") / spec["name"], files, outputs, report, qualified), True)
        check("outside_package_root", lambda: b.write_package(scratch / spec["name"], files, outputs, report, qualified), True)
        old = b.legacy.PACKAGES / "stage1a-probe-ok-ng"
        old_hash = b.sha((old / "manifest.json").read_bytes())
        check("never_overwrite_existing_package", lambda: b.legacy.write_package(old, files, outputs, report, qualified), True)
        check("old_package_manifest_unchanged", lambda: expect(b.sha((old / "manifest.json").read_bytes()) == old_hash, "Old package changed"))
        if equivalence:
            evidence = {"path": str(equivalence.resolve()), "sha256": b.sha(equivalence.read_bytes())}
            check("qualified_full_equivalence", lambda: b.qualify(manifest, evidence))
            for name, mutation in (("equivalence_wrong_artifact", lambda x: x.update(rewritten_ilaunch3_sha256="0" * 64)),
                                   ("equivalence_partial_matrix", lambda x: x.update(passed=24)),
                                   ("equivalence_has_divergence", lambda x: x.update(divergences=1)),
                                   ("equivalence_stale_interpreter", lambda x: x.update(interpreter_sha256="0" * 64))):
                data = json.loads(equivalence.read_text())
                mutation(data)
                reference = asset(json.dumps(data).encode(), "equivalence.json")
                check(name, lambda reference=reference: b.qualify(copy.deepcopy(manifest), reference), True)
        if package:
            package = package.resolve()
            probe, recovery = package / "probe/SD_ROOT", package / "recovery-official-1.51/SD_ROOT"
            check("written_package_readback", lambda: b.legacy.drill.check_written(probe, recovery, files, report))
            for label, tree, expected in (("probe", probe, manifest["probe_sha256"]),
                                           ("recovery", recovery, manifest["recovery_sha256"])):
                check(label + "_SHA256SUMS", lambda tree=tree, expected=expected: expect(
                    (tree.parent / "SHA256SUMS").read_text() == "".join(f"{expected[n]}  {n}\n" for n in sorted(expected)), "Hash list differs"))
            actual = json.loads((package / "manifest.json").read_text())
            check("manifest_actual_artifact_identity", lambda: expect(
                actual["probe_sha256"] == manifest["probe_sha256"] and actual["recovery_sha256"] == manifest["recovery_sha256"] and
                actual["written_and_reverified"] and actual["qualification"]["exhaustive_equivalence_verified"], "Manifest differs"))
            check("final_package_overwrite_refused", lambda: b.write_package(package, files, outputs, report, manifest), True)
            fixture = {n: (recovery / n).read_bytes() for n in files}
            fixture["ilaunch3"] = fixture["ilaunch3"][:-1] + bytes([fixture["ilaunch3"][-1] ^ 1])
            check("recovery_tampering_rejected", lambda: b.legacy.drill.check_official(fixture), True)
    check("official_hashes_unchanged_after_tests", lambda: b.legacy.drill.check_official(
        b.legacy.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")))
    result = {"schema": "gxr-stage1a-v2-builder-verification-v2", "positive_checks": sum(r["kind"] == "positive" for r in results),
              "rejection_checks": sum(r["kind"] == "rejection" for r in results), "failed": 0, "checks": results,
              "package": str(package) if package else None, "ilaunch3_sha256": manifest["probe_sha256"]["ilaunch3"],
              "changed_bytes": manifest["ilaunch3_total_changed_bytes"], "script_sha256": b.sha(Path(__file__).read_bytes())}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("positive_checks", "rejection_checks", "failed", "ilaunch3_sha256", "changed_bytes")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--equivalence", type=Path)
    args = parser.parse_args()
    verify(args.output, args.package, args.equivalence)
