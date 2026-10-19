#!/usr/bin/env python3
"""Audit a complete recipe image in memory; print evidence, never an update file."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


code = module("gxr_code_audit", ROOT / "scripts/build_code_patch.py")
build = module("gxr_recipe_build", HERE / "tools/build.py")
drill = code.drill
require = code.require

# Pin the reviewed entry points independently of the generated hook list.
HOOKS = {
    "init_recipe_cache": (0x2028709c, "d0c0202780e01fec", "ricoh_recipe_open"),
    "init_cursor_bypass_enum": (0x202870a8, "12806005", None),
    "adj_name_table": (0x2022f5a8, "2022d610", "rfw_closed_table"),
    "adj_count_16": (0x2022f5ac, "07", None),
    "adj_empty_details": (0x201febe4, "d2c0202382e2fd38", "rfw_no_details"),
    "fn2_no_editor": (0x202be24c, "d0c02026", "recipe_fn2_guard"),
    "adj_confirm_close": (0x202871d8, "2e7ff000", "ricoh_recipe_action"),
    "live_recipe_commit": (0x202bb968, "dbc02022", "recipe_live_commit"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_inputs(output=None):
    output = HERE/'build' if output is None else Path(output).resolve()
    require(output.is_relative_to(HERE), 'Build evidence escapes Stage 2a')
    manifest = json.loads((output / "manifest.json").read_text())
    evidence = json.loads((output / "verification.json").read_text())
    require(manifest['variant'] == evidence['variant'], 'Build/test variant mismatch')
    require(evidence["protected_inputs_unchanged"] and
            {h["mode"] for h in evidence["host"]} == {"host", "sanitizers"} and
            all(h["pass"] and h["cases"] > 0 for h in evidence["host"]) and
            evidence["abi_model_cases"] > 0 and all(r["pass"] for r in evidence["rejections"]),
            "Current host verification has not passed")
    for hashes in (manifest["build_inputs_sha256"], manifest["tool_sha256"], evidence["inputs_sha256"]):
        for name, expected in hashes.items():
            path = (ROOT / name).resolve()
            require(path.is_relative_to(ROOT), "Input escapes project")
            require(sha(path.read_bytes()) == expected, f"Stale source/tool evidence: {name}")
    payload = (output / "payload.bin").read_bytes()
    require(sha(payload) == manifest["payload_sha256"] == evidence["payload_sha256"],
            "Payload does not match tested evidence")
    elf = build.Elf(output / "payload.elf")
    allocated = [s for s in elf.sections if s["size"] and s["flags"] & 2]
    require(elf.kind == 2 and len(allocated) == 1, "Expected one final ELF payload")
    section = allocated[0]
    require((section["name"], section["va"], section["flags"], section["type"])
            == (".payload", 0x2005276c, 6, 1), "Unexpected ELF allocation")
    require(elf.content(section) == payload, "ELF and binary payload differ")
    require(not any(s["size"] and s["type"] in (4, 9) for s in elf.sections), "Remaining relocation")
    require(not any(s["section"] == 0 and s["name"] for s in elf.symbols.values()), "Undefined symbol")
    symbols = {name: s["value"] for name, s in elf.symbols.items()}
    files = drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")
    hooks = json.loads((output / "hooks.json").read_text())
    return files, hooks, payload, symbols


def check_replacement(identifier, va, replacement, symbols):
    target_name = HOOKS[identifier][2]
    target = symbols[target_name] if target_name else None
    if identifier == "init_cursor_bypass_enum":
        require(replacement == bytes.fromhex("18807f1c"), "Cursor bypass differs")
    elif identifier == "adj_count_16":
        require(replacement == b"\x04", "Recipe count differs")
    elif identifier == "adj_name_table":
        require(len(replacement) == 4 and int.from_bytes(replacement, "big") == target,
                "Name table target differs from ELF")
    elif identifier in ("init_recipe_cache", "adj_empty_details"):
        register = 0 if identifier == "init_recipe_cache" else 2
        op1, high, op2, low = struct.unpack(">4H", replacement)
        require(op1 == (0xd0c0 | register << 8) and op2 == (0x80e0 | register << 8 | register),
                "Absolute hook opcodes differ")
        require((high << 16 | low) == target, "Absolute hook target differs from ELF")
    else:
        word = int.from_bytes(replacement, "big")
        require(len(replacement) == 4 and word >> 24 == 0xff, "Expected BRA24 hook")
        displacement = word & 0xffffff
        if displacement & 0x800000:
            displacement -= 0x1000000
        require(va + displacement * 4 == target, "Branch target differs from ELF")


def audit(files, hooks, payload, symbols):
    drill.check_official(files)
    original = files["ilaunch3"]
    require(hooks["image_sha256"] == drill.OFFICIAL["ilaunch3"], "Hook input identity differs")
    segments = code.parse_container(original, ROOT / "research/firmware/ilaunch3-sections.csv")
    entries = hooks["hooks"]
    require(len(entries) == len(HOOKS) and {h["id"] for h in entries} == set(HOOKS),
            "Reviewed hook inventory differs")
    patches = []
    for h in entries:
        va, old, _ = HOOKS[h["id"]]
        replacement = bytes.fromhex(h["new_bytes"])
        length = len(bytes.fromhex(old))
        offset, segment = code.mapped(va, length, segments)
        require((int(h["va"], 16), h["original_bytes"], h["length"], len(replacement))
                == (va, old, length, length), "Reviewed hook bytes or length differ")
        require(int(h["file_offset"], 16) == offset and h["segment"] == segment, "Hook mapping differs")
        check_replacement(h["id"], va, replacement, symbols)
        patches.append({"file": "ilaunch3", "name": h["id"], "offset": hex(offset),
                        "expected": old, "replacement": replacement.hex()})
    p = hooks["payload_patch"]
    require(0 < len(payload) <= 8084 and len(payload) % 4 == 0, "Payload exceeds reserved region")
    require((int(p["va"], 16), int(p["file_offset"], 16), p["segment"], p["length"])
            == (0x2005276c, 0x796c, 0, len(payload)), "Payload mapping differs")
    require(code.mapped(0x2005276c, len(payload), segments) == (0x796c, 0), "Payload map does not match header")
    require(sha(payload) == p["new_sha256"], "Payload hash differs from hooks")
    patches.append({"file": "ilaunch3", "name": "recipe_payload", "offset": "0x796c",
                    "expected": (b"\xff" * len(payload)).hex(), "replacement": payload.hex()})
    segment_map = [(s["index"], s["load"], s["size"], s["start"]) for s in segments]
    build.check_protected_code(original, segment_map, entries, 0x796c, len(payload))
    outputs, records = drill.build(files, {"patches": patches}, segments)
    candidate = outputs["ilaunch3"]
    allowed = drill.allowed_ranges(records[0])
    changes = [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b]
    require(len(candidate) == len(original), "Image length changed")
    require(all(any(lo <= i < hi for lo, hi in allowed) for i in changes), "Undeclared image change")
    require(candidate[:0x16c] == original[:0x16c] and candidate[0x170:512] == original[0x170:512],
            "Container header changed outside checksum")
    require(candidate[0x175b2c:0x175ef4] == original[0x175b2c:0x175ef4], "Shared layer function changed")
    require(candidate[0x9900:0x9a00] == b"\xff" * 256, "Probe reserve changed")
    require(all(outputs[n] == files[n] for n in files if n != "ilaunch3"), "Other component changed")
    # Recompute without the builder's residue-sum implementation.
    checksum = sum(value * (i % 6 + 2) for i, value in enumerate(candidate[512:])) & 0xffffffff
    require(checksum == struct.unpack_from(">I", candidate, 0x16c)[0], "Independent checksum differs")
    return {
        "status": "IN_MEMORY_IMAGE_AUDIT_PASS", "audit_tool_sha256": sha(Path(__file__).read_bytes()),
        "payload_sha256": sha(payload),
        "payload_bytes": len(payload), "official_components_verified": len(files),
        "unchanged_components": sorted(n for n in files if n != "ilaunch3"),
        "candidate_image_sha256": sha(candidate), "candidate_image_bytes": len(candidate),
        "checksum": hex(checksum), "checksum_independently_verified": True,
        "changed_bytes": len(changes), "modified_segments": sorted({r["segment"] for r in records[0]["patches"]}),
        "allowed_changes": [{k: r[k] for k in ("name", "offset", "vma", "segment", "changed_bytes")}
                            | {"length": r["end"] - r["start"]} for r in records[0]["patches"]]
                           + [{"name": "container_checksum", "offset": "0x16c", "length": 4}],
        "shared_layer_function_unchanged": True, "probe_reserve_unchanged": True,
        "upgrade_package_generated": False, "camera_executed": False,
        "release_approved": False, "image_written": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=HERE/'build')
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    report = audit(*read_inputs(args.build))
    if args.candidate is not None:
        require(args.candidate.resolve().is_relative_to(HERE), 'Candidate must stay in Stage 2a')
        artifact = args.candidate.read_bytes()
        require(sha(artifact) == report['candidate_image_sha256'], 'Candidate artifact differs from audited bytes')
        require(len(artifact) == report['candidate_image_bytes'], 'Candidate artifact length differs')
        report.update(image_written=True, artifact_readback_verified=True, artifact_path=str(args.candidate))
    print(json.dumps(report, ensure_ascii=False, indent=2))
