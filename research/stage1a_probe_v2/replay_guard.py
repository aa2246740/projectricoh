#!/usr/bin/env python3
"""Replay two official instruction slices; no v2 payload and no camera emulator."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
FLAG = 0x200D6118
STOP = 0xFFFFF000


def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


class Machine:
    def __init__(self, body, flags, psw_c=0, auto_check=0, variant=0):
        self.body = body
        self.segments = [struct.unpack_from(">5I", body, 0x20 + i * 20) for i in range(16)]
        self.reg = [0xAB000000 + i for i in range(16)]
        self.reg[14], self.reg[15] = STOP, 0x207F0000
        self.c = psw_c
        self.memory = {FLAG: flags, 0x20410574: variant}
        self.auto_check = auto_check
        self.pc = 0
        self.trace = []
        self.calls = []

    def fetch(self):
        if 0x2005276C <= self.pc < 0x20054800:
            raise AssertionError("Candidate region fetched")
        for source, load, size, _, _ in self.segments:
            if load <= self.pc and self.pc + 4 <= load + size:
                offset = 512 + source + self.pc - load
                return int.from_bytes(self.body[offset:offset + 4], "big")
        raise ValueError(f"Unmapped instruction fetch {self.pc:#x}")

    def read_word(self, address):
        if address not in self.memory:
            raise ValueError(f"Unmodelled memory read {address:#x}")
        return self.memory[address]

    def half(self, raw, pc, old):
        raw &= 0x7FFF
        dest, source = (raw >> 8) & 15, raw & 15
        opcode = raw & 0xF0F0
        if raw == 0x7000:
            return None
        if raw & 0xF000 == 0x6000:
            self.reg[dest] = signed(raw & 255, 8) & 0xFFFFFFFF
        elif opcode == 0x1080:
            self.reg[dest] = old[source]
        elif opcode == 0x00C0:
            self.reg[dest] = old[dest] & old[source]
        elif opcode == 0x00E0:
            self.reg[dest] = old[dest] | old[source]
        elif opcode == 0x20C0:
            self.reg[dest] = self.read_word(old[source])
        elif opcode == 0x2040:
            self.memory[old[source]] = old[dest]
        elif raw & 0xFFF0 == 0x1FC0:
            return old[source]
        elif raw & 0xFFF0 == 0x1EC0:
            target = old[source]
            self.reg[14] = (pc & ~3) + 4
            self.calls.append({"pc": hex(pc), "target": hex(target), "r4": self.reg[4], "lr": hex(self.reg[14])})
            if target == 0x2036D4E8:
                return STOP
            if target == 0x20089340:
                self.reg[0] = self.auto_check & 0xFFFFFFFF
                return self.reg[14]
            if target in (0x20068A58, 0x20068A5C):
                return target
            raise ValueError(f"Unmodelled call {target:#x}")
        elif raw & 0xFF00 == 0x7F00:
            return (pc & ~3) + signed(raw & 255, 8) * 4
        else:
            raise ValueError(f"Unsupported 16-bit opcode {raw:04x} at {pc:#x}")
        return None

    def step(self):
        pc = self.pc
        word = self.fetch()
        self.trace.append({"pc": hex(pc), "bytes": f"{word:08x}"})
        next_pc = pc + 4
        if word & 0x80000000:
            dest, source, imm = (word >> 24) & 15, (word >> 16) & 15, word & 0xFFFF
            opcode = word & 0xF0F00000
            if opcode == 0xD0C00000:
                self.reg[dest] = imm << 16
            elif opcode == 0x80E00000:
                self.reg[dest] = self.reg[source] | imm
            elif opcode == 0x80C00000:
                self.reg[dest] = self.reg[source] & imm
            elif opcode == 0xA0C00000:
                self.reg[dest] = self.read_word((self.reg[source] + signed(imm, 16)) & 0xFFFFFFFF)
            elif opcode in (0xB0800000, 0xB0900000, 0xB0A00000, 0xB0B00000, 0xB0C00000, 0xB0D00000):
                value = signed(self.reg[source], 32)
                taken = {0xB0800000: value == 0, 0xB0900000: value != 0,
                         0xB0A00000: value < 0, 0xB0B00000: value >= 0,
                         0xB0C00000: value <= 0, 0xB0D00000: value > 0}[opcode]
                if taken:
                    next_pc = pc + signed(imm, 16) * 4
            else:
                raise ValueError(f"Unsupported 32-bit opcode {word:08x} at {pc:#x}")
        else:
            left, right = word >> 16, word & 0xFFFF
            old = self.reg.copy()
            branch = self.half(left, pc, old)
            # The right high bit marks parallel execution; both halves read old registers.
            if branch is None or right & 0x8000:
                right_branch = self.half(right, pc + 2, old if right & 0x8000 else self.reg.copy())
                if right_branch is not None:
                    branch = right_branch
            if branch is not None:
                next_pc = branch
        self.reg = [v & 0xFFFFFFFF for v in self.reg]
        self.pc = next_pc

    def run(self, entry, end=None):
        self.pc = entry
        for _ in range(100):
            if self.pc == STOP or self.pc == end:
                return
            self.step()
        raise AssertionError("Instruction budget exhausted")


def verify(body):
    records = []
    for c in (0, 1):
        for flags in (0, 1, 2, 0x80000000, 0xFFFFFFFF):
            for argument in (0, 1, 2, 0x100000):
                machine = Machine(body, flags, c)
                machine.reg[4] = argument
                before = machine.reg.copy()
                machine.run(0x20068A68)
                assert machine.memory[FLAG] == flags | argument
                assert machine.reg[4:] == before[4:] and machine.c == c
                records.append({"case": "official_flag_setter", "initial": hex(flags), "argument": hex(argument),
                                "result": hex(machine.memory[FLAG]), "condition_bit": c,
                                "sp_lr_r4_through_r15_unchanged": True})
    decisions = []
    for flags in (0, 1, 2, 3):
        for result in (0, -1):
            for variant in (0, 1):
                for c in (0, 1):
                    machine = Machine(body, flags, c, result, variant)
                    machine.reg[8] = flags
                    sp = machine.reg[15]
                    machine.run(0x2036E4BC, 0x2036E514)
                    updates = [call for call in machine.calls if call["target"] == "0x2036d4e8"]
                    expected = bool(flags & 1) or result < 0
                    assert bool(updates) == expected
                    if expected:
                        assert updates[0]["r4"] == (35 if variant else 33)
                        assert updates[0]["lr"] == "0x2036e50c"
                    assert machine.reg[15] == sp and machine.c == c
                    decisions.append({"case": "official_update_decision_slice", "flags": hex(flags),
                                      "synthetic_0x20089340_return": result, "context_plus_88": variant,
                                      "initial_condition_bit": c, "bit0_guard_would_bypass_scan": bool(flags & 1),
                                      "update_control_call": updates[0] if updates else None,
                                      "executed_trace": machine.trace})
    counterexamples = [x for x in decisions if x["update_control_call"] and not x["bit0_guard_would_bypass_scan"]]
    assert len(counterexamples) == 8
    return {"schema": "gxr-stage1a-v2-official-guard-replay-v1", "passed": len(records) + len(decisions),
            "setter_cases": records, "decision_cases": decisions, "bit0_only_control_predicate_counterexamples": len(counterexamples),
            "limitations": ["Actual official instruction bytes decoded by this small independent interpreter",
                            "0x20089340 return is synthetic; its I/O and callbacks are not emulated",
                            "0x20068A58 and 0x20068A5C execute their official instructions",
                            "The context +88 word is synthetic; registers at slice entry are synthetic",
                            "No update-to-ISO-producer path or reachable hardware state is demonstrated",
                            "No rewritten producer, probe, formatter, interrupt, PSW other than C, DMA or camera is emulated"],
            "v2_firmware_emulated": False, "camera_execution_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.resolve()
    if not (destination.is_relative_to(ROOT / "research/stage1a_probe_v2") or destination.is_relative_to(Path("/private/tmp"))):
        raise ValueError("Output must be under v2 research or /tmp")
    if destination.exists():
        raise ValueError("Refusing to overwrite replay evidence")
    body = (ROOT / "artifacts/firmware/gxr-1.51/ilaunch3").read_bytes()
    assert hashlib.sha256(body).hexdigest() == "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
    result = verify(body)
    result["official_ilaunch3_sha256"] = hashlib.sha256(body).hexdigest()
    result["interpreter_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"passed": result["passed"], "control_predicate_counterexamples": result["bit0_only_control_predicate_counterexamples"],
                      "v2_firmware_emulated": False, "output": str(destination)}))
