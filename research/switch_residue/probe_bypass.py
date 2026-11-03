#!/usr/bin/env python3
"""Bind the existing instruction model to the actual P0 body image."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    model = load("switch_p0_model", ROOT / "firmware/stage2k_p0/verify.py")
    builder = load("switch_elf_reader", ROOT / "firmware/stage2j/tools/build.py")
    image_path = ROOT / "artifacts/stage2k-p0-packages/CANDIDATE-AWAITING-APPROVAL/image/ilaunch3"
    image = image_path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    assert digest == "8a0ab7a1c490d1213eb22ff9c4b41b7c874fb774b6606330f4884f4ffb9820ba"
    segments = [struct.unpack_from(">5I", image, 32 + i * 20) for i in range(16)]

    def at(address, length):
        offsets = [src + 512 + address - base for src, base, size, _, _ in segments
                   if base <= address and address + length <= base + size]
        assert len(offsets) == 1
        return image[offsets[0]:offsets[0] + length]

    old = builder.Elf(ROOT / "firmware/stage2j/build/payload.elf")
    resident = builder.Elf(ROOT / "firmware/stage2k_p0/local/build/probe.elf")
    for section in resident.sections:
        if section["name"] in (".early", ".late", ".probe"):
            assert at(section["va"], section["size"]) == resident.content(section)
    entry = resident.symbols["p0_select"]["value"]
    branch = struct.unpack(">I", at(0x2005324c, 4))[0]
    assert branch == 0xfe000000 | (((entry - 0x2005324c) // 4) & 0xffffff)
    code = model.decode((ROOT / "firmware/stage2j/build/payload-disasm.txt").read_text())
    code.update(model.decode((ROOT / "firmware/stage2k_p0/local/build/probe-disasm.txt").read_text()))
    code[0x2005324c] = ([f"bl {entry:08x}"], 0, False)
    symbols = {name: value["value"] for name, value in old.symbols.items()}
    outcomes = []
    for present in (False, True):
        vm = model.fixture(code, symbols, slot=8, present=present, sync="ok")
        vm.put(model.CACHE + 3534, 6, 1)  # last committed menu slot
        vm.put(model.CACHE + 3536, 5, 1)  # deep profile associated with slot 06
        vm.run(symbols["rfw_select"])
        calls = sum(event[0] == "apply" for event in vm.events)
        result = {"helper_present": present, "application_callback_count": calls,
                  "highlighted_slot": vm.get(0x2022f726, 1),
                  "last_committed_slot": vm.get(model.CACHE + 3534, 1),
                  "deep_profile": vm.get(model.CACHE + 3536, 1),
                  "select_return": vm.r[0]}
        if present:
            assert calls == 0 and result["last_committed_slot"] == 6
            assert result["deep_profile"] == 5 and result["highlighted_slot"] == 8
        else:
            assert calls == 1
        outcomes.append(result)
    report = {"evidence": "EMITTED_INSTRUCTION_CONTROL_FLOW_WITH_EXPLICIT_MODELS",
              "image_sha256": digest, "cases": outcomes,
              "limitations": "Uses the original P0 helper and existing external-service/cache assumptions. Does not execute camera hardware or model the service internals. It proves the normal application callback is bypassed when a helper is present."}
    destination = HERE / "local/probe-bypass.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
