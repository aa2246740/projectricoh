#!/usr/bin/env python3
"""Decode official/rewrite M32R producer bytes, using the Round 1 interpreter."""
import argparse
from collections import Counter
import hashlib
import importlib.util
from itertools import product
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


base = module("stage1a_round1", HERE / "replay_guard.py")
builder = module("stage1a_code_builder", ROOT / "scripts/build_code_patch.py")
LO, HI = 0x2005276C, 0x20054800
ISO, LOW, BUFFER = 0x205DF074, 0x205E42F9, 0x20234BD0
MEMSET, FORMAT, DISPLAY = 0x20062750, 0x200BBC7C, 0x203189B4
ENTRIES = (0x20319C00, 0x203183E8)
ISOS = (-1, 0, 1, 200, 3200, 9999, 10000, 32767, -32768)
SP = 0x207F0000
MASK = 0xFFFFFFFF
GARBAGE = ((0, MASK, 0x12345678, 0x87654321),
           (0xDEADBEEF, 0x13579BDF, 0x2468ACE0, 0xAAAAAAAA),
           (MASK, 0x80000000, 0x7FFFFFFF, 0x55555555))


class Image:
    def __init__(self, body):
        self.body = body
        self.segments = [struct.unpack_from(">5I", body, 0x20 + 20 * i) for i in range(16)]
        self.words = {}

    def offset(self, address, width):
        for source, load, size, _, _ in self.segments:
            if load <= address and address + width <= load + size:
                return 512 + source + address - load
        raise ValueError(f"Unmapped image address {address:#x}")

    def fetch(self, pc):
        if LO <= pc < HI:
            raise AssertionError("Candidate region fetched")
        if pc not in self.words:
            offset = self.offset(pc, 4)
            self.words[pc] = int.from_bytes(self.body[offset:offset + 4], "big")
        return self.words[pc]


class ProducerMachine(base.Machine):
    """Extend the old word/halfword decoder; unsupported instructions fail closed.

    The producer's writes execute as instructions. Callee stack internals are
    abstracted, as required by the stub-based comparison, never guessed as ABI.
    """
    def __init__(self, image, entry, r4, iso_pair, low, changed, c, garbage, seed=0,
                 stub=True):
        self.image, self.body, self.segments = image, image.body, image.segments
        self.reg = [(0xA6000000 + 0x10101 * i + seed) & MASK for i in range(16)]
        self.reg[:4] = garbage
        self.reg[4], self.reg[14], self.reg[15] = r4, base.STOP, SP
        self.initial = self.reg.copy()
        self.c, self.seed, self.stub = c, seed, stub
        self.pc, self.steps, self.minimum_sp = entry, 0, SP
        self.memory, self.writes, self.calls, self.formats = {}, [], [], []
        self.visited, self.reads, self.iso_reads = set(), [], []
        self.iso_pair = iso_pair
        self.scan_count, self.scan_next = 0, LO
        self.changed = changed
        self.poke(LOW, low, 1)
        self.poke(0x205E445E, 0x37, 1)
        self.poke(0x205E4460, 0xA9, 1)
        for address in range(SP - 256, SP + 128):
            self.memory[address] = (address * 37 + 0xA5 + seed) & 255
        for address in range(BUFFER, BUFFER + 32):
            self.memory[address] = (address * 13 + seed + 0x5A) & 255
        self.start_memory = self.memory.copy()

    def poke(self, address, value, width):
        for i, byte in enumerate((value & ((1 << (width * 8)) - 1)).to_bytes(width, "big")):
            self.memory[address + i] = byte

    def store(self, address, value, width, kind="producer"):
        value &= (1 << (width * 8)) - 1
        self.writes.append((address, width, value, kind))
        self.poke(address, value, width)

    def read(self, address, width, signed=False):
        if address == ISO and width == 2:
            value = self.iso_pair[min(len(self.iso_reads), 1)] & 0xFFFF
            self.iso_reads.append(value)
        elif LO <= address < HI:
            assert width == 1 and address == self.scan_next, "Scan skipped/repeated a byte"
            self.scan_next += 1
            self.scan_count += 1
            value = 0 if address == self.changed else 255
        else:
            values = []
            for i in range(width):
                at = address + i
                if at in self.memory:
                    values.append(self.memory[at])
                else:
                    values.append(self.body[self.image.offset(at, 1)])
            value = int.from_bytes(bytes(values), "big")
        return base.signed(value, width * 8) & MASK if signed else value

    def read_word(self, address):
        return self.read(address, 4)

    def cstring(self, address):
        data = bytearray()
        for i in range(32):
            value = self.read(address + i, 1)
            if not value:
                return data.decode("ascii")
            data.append(value)
        raise AssertionError("Unterminated format")

    def call(self, target, link):
        self.reg[14] = link
        if not self.stub:
            return target
        assert target in (MEMSET, FORMAT, DISPLAY), f"Unexpected external call {target:#x}"
        sp = self.reg[15]
        args = [self.read(sp, 4), self.read(sp + 4, 4)] if target == FORMAT else []
        text = self.cstring(args[0]) if target == FORMAT else None
        if text == "ISO-LO":
            args = args[:1]
        record = {"callee": target, "r4_r7": self.reg[4:8].copy(),
                  "stack_args": args, "condition_bit": self.c, "sp": sp}
        self.calls.append(record)
        if target == MEMSET:
            # This exact high, aligned SDRAM address takes the word+byte path.
            assert self.reg[4] == SP - 8 and self.reg[5:7] == [0, 5]
            self.store(self.reg[4], 0, 4, "memset")
            self.store(self.reg[4] + 4, 0, 1, "memset")
            self.reg[0:3] = [self.reg[4], 0, self.reg[4] + 5]
            self.reg[6], self.c = 0, 1
        elif target == FORMAT:
            assert self.reg[4] == BUFFER
            assert text in ("ISO %d", "OK %d", "NG %d", "ISO-LO"), text
            rendered = text if "%d" not in text else text % base.signed(args[1], 32)
            payload = rendered.encode("ascii") + b"\0"
            self.formats.append({"format": text, "output": rendered, "address": BUFFER})
            for i, byte in enumerate(payload):
                self.store(BUFFER + i, byte, 1, "formatter")
            # Successful sprintf: engine count is returned unchanged, then NUL.
            self.reg[0] = len(payload) - 1
            self.reg[1] = 0
            # ABI-opaque scratch is coupled between the two executions. Vary it
            # across cases; the producer must not derive control/arguments from it.
            for r in range(2, 8):
                self.reg[r] = (0xD1000000 + r * 0x101 + self.seed) & MASK
            self.c = self.seed & 1
        else:
            # The real single return writes ldi r0,#0 at 0x203189E4.
            self.reg[0] = 0
            for r in range(1, 8):
                self.reg[r] = (0xD2000000 + r * 0x101 + self.seed) & MASK
            self.c = (self.seed >> 1) & 1
        return link

    def half(self, raw, pc, old):
        raw &= 0x7FFF
        dest, source = (raw >> 8) & 15, raw & 15
        opcode = raw & 0xF0F0
        if raw == 0x7000:
            return None
        if raw & 0xF000 == 0x4000:
            self.reg[dest] = (old[dest] + base.signed(raw & 255, 8)) & MASK
        elif raw & 0xFFF0 == 0x1EC0:
            return self.call(old[source], (pc & ~3) + 4)
        elif opcode == 0x2070:
            assert source == 15
            self.reg[15] = (old[15] - 4) & MASK
            self.store(self.reg[15], old[dest], 4)
        elif opcode == 0x20E0:
            assert source == 15
            self.reg[dest] = self.read(old[15], 4)
            self.reg[15] = (old[15] + 4) & MASK
        elif opcode in (0x2080, 0x2090, 0x20A0, 0x20B0, 0x20C0):
            width = {0x2080: 1, 0x2090: 1, 0x20A0: 2, 0x20B0: 2, 0x20C0: 4}[opcode]
            self.reg[dest] = self.read(old[source], width, opcode in (0x2080, 0x20A0))
        elif opcode in (0x2000, 0x2020, 0x2040):
            width = {0x2000: 1, 0x2020: 2, 0x2040: 4}[opcode]
            self.store(old[source], old[dest], width)
        elif raw & 0xFF00 in (0x7C00, 0x7D00, 0x7E00, 0x7F00):
            target = (pc & ~3) + base.signed(raw & 255, 8) * 4
            kind = raw & 0xFF00
            if kind == 0x7E00:
                return self.call(target, (pc & ~3) + 4)
            if kind == 0x7F00 or bool(self.c) == (kind == 0x7C00):
                return target
        elif opcode in (0x0040, 0x0050):
            left, right = old[dest], old[source]
            if opcode == 0x0040:
                left, right = base.signed(left, 32), base.signed(right, 32)
            self.c = int(left < right)
        elif opcode == 0x00A0:
            self.reg[dest] = (old[dest] + old[source]) & MASK
        elif opcode == 0x1060:
            self.reg[dest] = (old[dest] * old[source]) & MASK
        else:
            return super().half(raw, pc, old)
        return None

    def step(self):
        pc = self.pc
        assert pc % 4 == 0
        self.visited.add(pc)
        word = self.image.fetch(pc)
        next_pc = pc + 4
        if word & 0x80000000:
            dest, source, imm = (word >> 24) & 15, (word >> 16) & 15, word & 0xFFFF
            opcode = word & 0xF0F00000
            if word >> 24 in (0xFE, 0xFF):
                target = pc + base.signed(word & 0xFFFFFF, 24) * 4
                next_pc = self.call(target, pc + 4) if word >> 24 == 0xFE and target in (MEMSET, FORMAT, DISPLAY) else target
                if word >> 24 == 0xFE:
                    self.reg[14] = pc + 4
            elif opcode == 0xD0C00000:
                self.reg[dest] = imm << 16
            elif opcode == 0x80E00000:
                self.reg[dest] = self.reg[source] | imm
            elif opcode == 0x90F00000:
                self.reg[dest] = base.signed(imm, 16) & MASK
            elif word & 0xF0000000 == 0xE0000000:
                self.reg[dest] = word & 0xFFFFFF
            elif opcode == 0x80A00000:
                self.reg[dest] = (self.reg[source] + base.signed(imm, 16)) & MASK
            elif opcode == 0x80C00000:
                self.reg[dest] = self.reg[source] & imm
            elif opcode in (0x80400000, 0x80500000):
                value = self.reg[source]
                if opcode == 0x80400000:
                    value = base.signed(value, 32)
                    imm = base.signed(imm, 16)
                self.c = int(value < imm)
            elif opcode in (0xA0800000, 0xA0900000, 0xA0A00000, 0xA0C00000):
                width = {0xA0800000: 1, 0xA0900000: 1, 0xA0A00000: 2, 0xA0C00000: 4}[opcode]
                self.reg[dest] = self.read((self.reg[source] + base.signed(imm, 16)) & MASK,
                                           width, opcode in (0xA0800000, 0xA0A00000))
            elif opcode in (0xB0000000, 0xB0100000):
                same = self.reg[dest] == self.reg[source]
                if same == (opcode == 0xB0000000):
                    next_pc = pc + base.signed(imm, 16) * 4
            elif opcode in (0xB0800000, 0xB0900000, 0xB0A00000, 0xB0B00000, 0xB0C00000, 0xB0D00000):
                value = base.signed(self.reg[source], 32)
                taken = {0xB0800000: value == 0, 0xB0900000: value != 0,
                         0xB0A00000: value < 0, 0xB0B00000: value >= 0,
                         0xB0C00000: value <= 0, 0xB0D00000: value > 0}[opcode]
                if taken:
                    next_pc = pc + base.signed(imm, 16) * 4
            else:
                raise ValueError(f"Unsupported 32-bit opcode {word:08x} at {pc:#x}")
        else:
            left, right = word >> 16, word & 0xFFFF
            old = self.reg.copy()
            branch = self.half(left, pc, old)
            if branch is None or right & 0x8000:
                other = self.half(right, pc + 2, old if right & 0x8000 else self.reg.copy())
                if other is not None:
                    branch = other
            if branch is not None:
                next_pc = branch
        # A direct tail branch into formatter must not change lr.
        if next_pc == FORMAT and self.stub:
            next_pc = self.call(FORMAT, self.reg[14])
        self.pc = next_pc
        self.steps += 1
        self.minimum_sp = min(self.minimum_sp, self.reg[15])

    def run(self, entry=None, end=None):
        if entry is not None:
            self.pc = entry
        while self.pc != base.STOP and self.pc != end:
            assert self.steps < 100000, "Instruction budget exhausted"
            self.step()


def compare_case(official, rewritten, case, probe_store):
    entry, argument, first, second, low, changed, c, garbage_index, seed = case
    args = (entry, argument, (first, second), low, changed, c, GARBAGE[garbage_index], seed)
    stock, patch = ProducerMachine(official, *args), ProducerMachine(rewritten, *args)
    stock.run()
    patch.run()
    expected_scan = first > 0 and second < 10000
    assert stock.scan_count == 0
    assert patch.scan_count == (HI - LO if expected_scan else 0), "Scan coverage"
    assert stock.iso_reads == patch.iso_reads, "Volatile ISO reads differ"
    assert len(stock.iso_reads) == (2 if first > 0 else 1)
    assert patch.reg[0] == stock.reg[0], "Return r0 differs"
    assert patch.reg[8:] == stock.reg[8:] == stock.initial[8:], "Callee-saved state differs"
    assert patch.c == stock.c, "Final condition bit differs in the callee model"
    assert stock.minimum_sp == patch.minimum_sp == (SP - 24 if expected_scan else SP - 16)
    assert all(patch.memory[a] == stock.memory[a] == stock.start_memory[a]
               for a in range(SP, SP + 128)), "Caller stack above sp changed"
    assert len(stock.calls) == len(patch.calls)
    allowed_formats = 0
    normalized_calls = []
    for a, b in zip(stock.calls, patch.calls):
        normalized = dict(b, stack_args=b["stack_args"].copy())
        if a["callee"] == FORMAT and len(a["stack_args"]) == 2:
            assert patch.cstring(b["stack_args"][0]) == ("OK %d" if changed is None else "NG %d")
            assert stock.cstring(a["stack_args"][0]) == "ISO %d"
            normalized["stack_args"][0] = a["stack_args"][0]
            allowed_formats += 1
        assert a == normalized, f"Callee trace differs: {a!r} != {normalized!r}"
        normalized_calls.append(normalized)
    assert allowed_formats == int(expected_scan)
    stock_effects = [w for w in stock.writes if w[3] != "formatter"]
    patch_effects = [w for w in patch.writes if w[3] != "formatter"]
    substitutions = [i for i, w in enumerate(patch_effects)
                     if w[0] == SP - 24 and w[1] == 4 and w[2] in probe_store]
    assert len(substitutions) == int(expected_scan)
    if substitutions:
        at = substitutions[0]
        assert patch_effects[at - 1] == stock_effects[at - 1]
        assert patch_effects[at - 1][0:2] == (SP - 24, 4)
        del patch_effects[at]
    assert stock_effects == patch_effects, "Unexpected non-format memory write"
    assert len(stock.formats) == len(patch.formats)
    for a, b in zip(stock.formats, patch.formats):
        if a["format"] == "ISO %d":
            prefix = "OK" if changed is None else "NG"
            assert b == {"format": prefix + " %d", "output": f"{prefix} {second}", "address": BUFFER}
        else:
            assert a == b and a["format"] == "ISO-LO"
    # Check every final byte too, including stale bytes after the shorter NUL.
    allowed_memory = set(range(SP - 24, SP - 20)) if expected_scan else set()
    if expected_scan:
        longest = max(len(x["output"]) + 1 for x in stock.formats + patch.formats)
        allowed_memory.update(range(BUFFER, BUFFER + longest))
    for address in stock.memory.keys() | patch.memory.keys():
        if address not in allowed_memory:
            assert stock.memory.get(address) == patch.memory.get(address), f"Memory differs at {address:#x}"
    assert not any(LO <= address < HI for address in patch.memory), "Probe wrote candidate region"
    result = {"input": [hex(entry), hex(argument), first, second, low,
                        None if changed is None else hex(changed), c, garbage_index, seed],
              "scan_bytes": patch.scan_count, "calls": len(stock.calls),
              "r0": hex(patch.reg[0]), "steps": [stock.steps, patch.steps]}
    fingerprint = json.dumps([normalized_calls, stock_effects, stock.reg[0], stock.reg[8:]], sort_keys=True).encode()
    result["comparison_sha256"] = hashlib.sha256(fingerprint).hexdigest()
    return result, stock, patch


def verify_memset_model(official):
    cases = []
    for garbage_index, c in product(range(3), (0, 1)):
        machine = ProducerMachine(official, MEMSET, SP - 8, (200, 200), 0, None, c,
                                  GARBAGE[garbage_index], stub=False)
        machine.reg[5:7] = [0, 5]
        machine.run()
        assert machine.reg[0:3] == [SP - 8, 0, SP - 3]
        assert machine.reg[6] == 0 and machine.c == 1
        assert machine.writes == [(SP - 8, 4, 0, "producer"), (SP - 4, 1, 0, "producer")]
        cases.append({"garbage": garbage_index, "initial_c": c, "r0": hex(machine.reg[0]),
                      "return_c": machine.c, "writes": machine.writes})
    return cases


def verify(official_body, rewritten_body, symbols, *, quick=False):
    official, rewritten = Image(official_body), Image(rewritten_body)
    probe_formats = {symbols[s]["value"] for s in ("probe_ok_string", "probe_ng_string")}
    cases, samples, census, visited = [], [], Counter(), set()
    primary = product(ENTRIES, (0, 1, 0xFFFFFFFF), ISOS, (0, 1),
                      (None, LO, HI - 1, LO + (HI - LO) // 2), (0, 1), range(3))
    for entry, argument, iso, low, changed, c, garbage in primary:
        if quick and (iso != 200 or changed is not None or garbage):
            continue
        case = (entry, argument, iso, iso, low, changed, c, garbage, garbage * 3 + c)
        result, stock, patch = compare_case(official, rewritten, case, probe_formats)
        cases.append(result)
        census["primary"] += 1
        census["scans"] += bool(result["scan_bytes"])
        visited.update(patch.visited)
        if len(samples) < 8:
            samples.append({**result, "official_trace": stock.calls, "rewrite_trace": patch.calls,
                            "official_writes": stock.writes, "rewrite_writes": patch.writes,
                            "formats": patch.formats})
    if not quick:
        # The second load is genuinely distinct: cover changing ISO globals too.
        for entry, argument, first, second, low, c in product(ENTRIES, (0, 1, 0xFFFFFFFF), ISOS, ISOS, (0, 1), (0, 1)):
            if first == second:
                continue
            result, _, patch = compare_case(official, rewritten,
                (entry, argument, first, second, low, None, c, 1, 4 + c), probe_formats)
            cases.append(result)
            census["changing_iso"] += 1
            census["scans"] += bool(result["scan_bytes"])
            visited.update(patch.visited)
    return {"schema": "gxr-stage1a-v2-producer-equivalence-v2", "passed": len(cases),
            "primary_cases": census["primary"], "changing_iso_cases": census["changing_iso"],
            "divergences": 0, "scanning_cases": census["scans"], "bytes_per_scan": HI - LO,
            "candidate_instruction_fetches": 0, "candidate_writes": 0,
            "producer_frame_max_bytes": 24, "new_probe_stack_bytes": 0,
            "memset_instruction_model_checks": verify_memset_model(official),
            "visited_rewrite_words": [hex(pc) for pc in sorted(visited)],
            "allowed_differences": ["One sp+0 format-word substitution before the first formatter",
                                    "Its ISO -> OK/NG rendered bytes including shorter NUL and stale tail"],
            "compared": ["Ordered external callee/r4..r7/stack arguments/C/sp trace",
                         "Every producer and modeled memset memory write in order",
                         "Every modeled formatter output byte against literal expected text",
                         "Final r0/r8..r15/C, frame depth, caller stack and other memory",
                         "Both ordered volatile ISO reads; all 8340 byte addresses per scan"],
            "callee_abstraction": {"memset": "Exact applicable official instruction path, separately replayed",
                "formatter_r0": "Successful formatter engine character count; wrapper leaves r0 unchanged",
                "display_r0": "Unconditional ldi r0,#0 on its only return path",
                "scratch_and_c": "ABI-opaque return values coupled across official/rewrite, varied by seed; no claim of full libc/UI instruction emulation",
                "formatter_output": "ASCII %d and ISO-LO modeled; callee-internal stack writes abstracted on both sides"},
            "cases": cases, "samples": samples,
            "official_ilaunch3_sha256": builder.sha(official_body),
            "rewritten_ilaunch3_sha256": builder.sha(rewritten_body),
            "interpreter_sha256": builder.sha(Path(__file__).read_bytes()),
            "base_interpreter_sha256": builder.sha((HERE / "replay_guard.py").read_bytes()),
            "camera_execution_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not (output.is_relative_to(Path("/private/tmp")) or output.is_relative_to(HERE)) or output.exists():
        raise ValueError("Use a new v2 research or /tmp evidence file")
    official = builder.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")["ilaunch3"]
    elf = builder.parse_elf(args.elf.read_bytes(), inplace=True)
    result = verify(official, args.firmware.read_bytes(), elf["symbols"], quick=args.quick)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("passed", "primary_cases", "changing_iso_cases", "divergences", "scanning_cases")}))


if __name__ == "__main__":
    main()
