#!/usr/bin/env python3
"""Decode official/rewrite M32R producer bytes, using the Round 1 interpreter."""
import argparse
import sys
sys.dont_write_bytecode = True
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


base = module("stage1a_round1", ROOT / "research/stage1a_probe_v2/replay_guard.py")
builder = module("stage1a_code_builder", ROOT / "scripts/build_code_patch.py")
LO, HI = 0x2005276C, 0x20054800
ISO, LOW, BUFFER = 0x205DF074, 0x205E42F9, 0x20234BD0
MEMSET, FORMAT, DISPLAY = 0x20062750, 0x200BBC7C, 0x203189B4
ENTRIES = (0x20319C00, 0x203183E8)
ISOS = (-1, 0, 1, 200, 3200, 9999, 10000, 32767, -32768)
OFFSETS = (0, 1, 0x1000, 0x1051, 0x2000, 0x2084, 0x2090, 0x2093)
SENTINELS = tuple(LO + offset for offset in OFFSETS)
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
        self.probe_windows = ()
        self.probe_entry = None

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
        self.scan_count, self.sentinel_reads = 0, []
        self.changed = dict(changed or ())
        self.instructions = self.instructions_with_nops = self.probe_instructions = 0
        self.probe_snapshot = None
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
        assert not (address < HI and LO < address + width), "Candidate region write"
        value &= (1 << (width * 8)) - 1
        self.writes.append((address, width, value, kind))
        self.poke(address, value, width)

    def read(self, address, width, signed=False):
        if address == ISO and width == 2:
            value = self.iso_pair[min(len(self.iso_reads), 1)] & 0xFFFF
            self.iso_reads.append(value)
        elif LO <= address < HI:
            assert width == 1 and self.scan_count < 8, "Unbounded or wide candidate read"
            assert address == SENTINELS[self.scan_count], "Unexpected/repeated/out-of-order sentinel"
            self.sentinel_reads.append(address)
            self.scan_count += 1
            value = self.changed.get(address, 255)
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

    def count_instruction(self, pc, nop=False):
        self.instructions_with_nops += 1
        if not nop:
            self.instructions += 1
            if any(lo <= pc < hi for lo, hi in self.image.probe_windows):
                self.probe_instructions += 1

    def half(self, raw, pc, old):
        raw &= 0x7FFF
        self.count_instruction(pc, nop=raw == 0x7000)
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
            self.reg[dest] = self.read(old[source], 4)
            self.reg[source] = (old[source] + 4) & MASK
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
        if pc == self.image.probe_entry:
            self.probe_snapshot = (self.reg[4:].copy(), self.c)
        self.visited.add(pc)
        word = self.image.fetch(pc)
        next_pc = pc + 4
        if word & 0x80000000:
            self.count_instruction(pc)
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
            elif opcode == 0xA0400000:
                self.store((self.reg[source] + base.signed(imm, 16)) & MASK, self.reg[dest], 4)
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
            assert self.probe_snapshot == (self.reg[4:].copy(), self.c), "Probe changed r4..r15/C"
            next_pc = self.call(FORMAT, self.reg[14])
        self.pc = next_pc
        self.steps += 1
        self.minimum_sp = min(self.minimum_sp, self.reg[15])

    def run(self, entry=None, end=None):
        if entry is not None:
            self.pc = entry
        while self.pc != base.STOP and self.pc != end:
            assert self.steps < 256, "Instruction budget exhausted"
            self.step()


def compare_case(official, rewritten, case, probe_store):
    entry, argument, first, second, low, changed, c, garbage_index, seed = case
    args = (entry, argument, (first, second), low, changed, c, GARBAGE[garbage_index], seed)
    stock, patch = ProducerMachine(official, *args), ProducerMachine(rewritten, *args)
    stock.run()
    patch.run()
    expected_scan = first > 0 and second < 10000
    changes = dict(changed or ())
    index = next((i for i, address in enumerate(SENTINELS) if changes.get(address, 255) != 255), 8)
    expected_reads = (8 if index == 8 else index + 1) if expected_scan else 0
    prefix = "OK" if index == 8 else "NG"
    assert stock.scan_count == 0
    assert patch.sentinel_reads == list(SENTINELS[:expected_reads]), "Sentinel coverage differs"
    assert stock.iso_reads == patch.iso_reads, "Volatile ISO reads differ"
    assert len(stock.iso_reads) == (2 if first > 0 else 1)
    assert patch.reg[0] == stock.reg[0], "Return r0 differs"
    assert patch.reg[8:] == stock.reg[8:] == stock.initial[8:], "Callee-saved state differs"
    assert patch.c == stock.c, "Final condition bit differs in the coupled callee model"
    assert stock.minimum_sp == patch.minimum_sp == (SP - 24 if expected_scan else SP - 16)
    assert all(patch.memory[a] == stock.memory[a] == stock.start_memory[a]
               for a in range(SP, SP + 128)), "Caller stack above sp changed"
    assert len(stock.calls) == len(patch.calls)
    substitutions = 0
    normalized_calls = []
    for a, b in zip(stock.calls, patch.calls):
        normalized = dict(b, stack_args=b["stack_args"].copy())
        if a["callee"] == FORMAT and len(a["stack_args"]) == 2:
            assert patch.cstring(b["stack_args"][0]) == prefix + " %d"
            assert b["stack_args"][1] == index, "First bad index differs"
            assert stock.cstring(a["stack_args"][0]) == "ISO %d"
            normalized["stack_args"] = a["stack_args"].copy()
            substitutions += 1
        assert a == normalized, f"Callee trace differs: {a!r} != {normalized!r}"
        normalized_calls.append(normalized)
    assert substitutions == int(expected_scan)
    effects = []
    for machine, patched in ((stock, False), (patch, True)):
        writes = [w for w in machine.writes if w[3] != "formatter"]
        if expected_scan:
            positions = [i for i, w in enumerate(writes) if w[0] in (SP - 24, SP - 20)][:2]
            assert len(positions) == 2
            initial_args = [writes[i] for i in positions]
            if patched:
                assert initial_args == [(SP - 24, 4, machine.calls[1]["stack_args"][0], "producer"),
                                        (SP - 20, 4, index, "producer")]
                assert initial_args[0][2] in probe_store
            else:
                assert initial_args == [(SP - 20, 4, second & MASK, "producer"),
                                        (SP - 24, 4, machine.calls[1]["stack_args"][0], "producer")]
            writes = [w for i, w in enumerate(writes) if i not in positions]
        effects.append(writes)
    assert effects[0] == effects[1], "Unexpected non-vararg memory write"
    assert len(stock.formats) == len(patch.formats)
    for a, b in zip(stock.formats, patch.formats):
        if a["format"] == "ISO %d":
            assert b == {"format": prefix + " %d", "output": f"{prefix} {index}", "address": BUFFER}
        else:
            assert a == b and a["format"] == "ISO-LO"
    for machine in (stock, patch):
        expected_writes = [(BUFFER + i, 1, byte, "formatter")
                           for fmt in machine.formats
                           for i, byte in enumerate(fmt["output"].encode("ascii") + b"\0")]
        assert [w for w in machine.writes if w[3] == "formatter"] == expected_writes
    allowed_memory = set(range(SP - 24, SP - 16)) if expected_scan else set()
    if expected_scan:
        longest = max(len(x["output"]) + 1 for x in stock.formats + patch.formats)
        allowed_memory.update(range(BUFFER, BUFFER + longest))
    for address in stock.memory.keys() | patch.memory.keys():
        if address not in allowed_memory:
            assert stock.memory.get(address) == patch.memory.get(address), f"Memory differs at {address:#x}"
    assert not any(LO <= address < HI for address in patch.memory), "Probe wrote candidate region"
    result = {"input": [hex(entry), hex(argument), first, second, low,
                        [[hex(a), v] for a, v in changed or ()], c, garbage_index, seed],
              "sentinel_reads": [hex(a) for a in patch.sentinel_reads],
              "scan_bytes": patch.scan_count, "calls": len(stock.calls), "r0": hex(patch.reg[0]),
              "steps": [stock.steps, patch.steps],
              "non_nop_instructions": [stock.instructions, patch.instructions],
              "instructions_with_nops": [stock.instructions_with_nops, patch.instructions_with_nops],
              "probe_instructions": patch.probe_instructions,
              "first_result": patch.formats[0]["output"] if expected_scan else None}
    fingerprint = json.dumps([normalized_calls, effects[0], stock.reg[0], stock.reg[8:]], sort_keys=True).encode()
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


def verify(official_body, rewritten_body, symbols, quick=False):
    official, rewritten = Image(official_body), Image(rewritten_body)
    rewritten.probe_windows = ((symbols["probe_entry"]["value"], symbols["alt_code_end"]["value"]),
                               (symbols["probe_loop"]["value"], symbols["normal_code_end"]["value"]))
    rewritten.probe_entry = symbols["probe_entry"]["value"]
    probe_formats = {symbols[name]["value"] for name in ("probe_ok_string", "probe_ng_string")}
    states = ((),) + tuple(((address, 0),) for address in SENTINELS) + (
        ((LO + 2, 0),), ((SENTINELS[1], 0), (SENTINELS[7], 128)))
    cases, samples, census, visited = [], [], Counter(), set()

    def add(case, category):
        result, stock, patch = compare_case(official, rewritten, case, probe_formats)
        cases.append(result)
        census[category] += 1
        census["scans"] += bool(result["scan_bytes"])
        visited.update(patch.visited)
        if len(samples) < 8 and case[2] == 200:
            samples.append({**result, "official_trace": stock.calls, "rewrite_trace": patch.calls,
                            "official_writes": stock.writes, "rewrite_writes": patch.writes,
                            "formats": patch.formats})

    for entry, argument, iso, low, changed, c, garbage in product(
            ENTRIES, (0, 1, MASK), ISOS, (0, 1), states, (0, 1), range(3)):
        if quick and (iso != 200 or garbage != 0):
            continue
        add((entry, argument, iso, iso, low, changed, c, garbage, garbage * 3 + c), "primary")
    if not quick:
        for entry, argument, first, second, low, c in product(
                ENTRIES, (0, 1, MASK), ISOS, ISOS, (0, 1), (0, 1)):
            if first != second:
                add((entry, argument, first, second, low, (), c, 1, 4 + c), "changing_iso")
        # Independent literal expectations for every byte, including signed-load boundaries.
        for entry, ordinal, value, c in product(ENTRIES, range(8), range(256), (0, 1)):
            add((entry, 1, 200, 200, 0, ((SENTINELS[ordinal], value),), c, 1, 7 + c), "byte_value")
    maximum_probe = max(case["probe_instructions"] for case in cases)
    timing = {"unit": "decoded instructions, external callees excluded; not CPU cycles or milliseconds",
              "maximum_probe_non_nop_instructions": maximum_probe,
              "maximum_producer_non_nop_delta": max(b - a for a, b in (c["non_nop_instructions"] for c in cases)),
              "minimum_producer_non_nop_delta": min(b - a for a, b in (c["non_nop_instructions"] for c in cases)),
              "maximum_producer_including_nops_delta": max(b - a for a, b in (c["instructions_with_nops"] for c in cases)),
              "maximum_producer_word_step_delta": max(b - a for a, b in (c["steps"] for c in cases)),
              "maximum_candidate_byte_reads": max(case["scan_bytes"] for case in cases),
              "maximum_pointer_table_word_reads": 8,
              "real_formatter_UI_interrupts_bus_waits": "not measured or modeled"}
    repeat = ProducerMachine(rewritten, ENTRIES[0], 1, (200, 200), 0, (), 0, GARBAGE[1], 3)
    repeated_calls = []
    for iso, changes, expected in ((200, (), "OK 8"), (3200, ((SENTINELS[0], 0),), "NG 0"),
                                   (200, (), "OK 8"), (3200, ((SENTINELS[7], 0),), "NG 7")):
        repeat.iso_pair, repeat.iso_reads, repeat.changed = (iso, iso), [], dict(changes)
        repeat.reg[4], repeat.reg[14], repeat.pc = 1, base.STOP, ENTRIES[0]
        repeat.scan_count, repeat.sentinel_reads, repeat.steps = 0, [], 0
        before = len(repeat.formats)
        repeat.run()
        assert repeat.formats[before]["output"] == expected and repeat.reg[15] == SP
        repeated_calls.append({"iso": iso, "result": expected, "reads": repeat.scan_count})
    return {"schema": "gxr-stage1a-v3-producer-equivalence-v1", "passed": len(cases),
            "primary_cases": census["primary"], "changing_iso_cases": census["changing_iso"],
            "byte_value_cases": census["byte_value"], "divergences": 0,
            "scanning_cases": census["scans"], "maximum_sentinel_reads": 8,
            "sentinel_offsets": list(OFFSETS), "candidate_region_bytes": HI - LO,
            "candidate_instruction_fetches": 0, "candidate_writes": 0,
            "producer_frame_max_bytes": 24, "new_probe_stack_bytes": 0,
            "memset_instruction_model_checks": verify_memset_model(official),
            "visited_rewrite_words": [hex(pc) for pc in sorted(visited)],
            "instruction_count": timing, "same_machine_repeated_calls": repeated_calls,
            "allowed_differences": ["First formatter sp+0 format and sp+4 vararg words, including write order",
                "ISO -> OK/NG text with sentinel ordinal instead of ISO, NUL position and stale tail"],
            "compared": ["Ordered callee/r4..r7/C/sp trace; only first formatter arguments normalized",
                "Every non-vararg producer/memset memory write in order",
                "Every modeled formatter byte, literal result and NUL",
                "Final r0/r8..r15/C, frame depth, caller stack and other memory",
                "Both volatile ISO reads; exact fixed-sentinel prefix, at most eight candidate bytes",
                "Probe preserves r4..r15/C before tail formatter"],
            "callee_abstraction": {"memset": "Exact applicable official instruction path, separately replayed",
                "formatter_r0": "Successful formatter character count; wrapper leaves r0 unchanged",
                "display_r0": "Unconditional ldi r0,#0 on its only return path",
                "scratch_and_c": "ABI-opaque returns coupled across official/rewrite, varied by seed; full libc/UI not emulated",
                "formatter_output": "ASCII %d and ISO-LO modeled; callee-internal stack writes abstracted",
                "external_state": "Ordered ISO pairs and LOW per invocation; no asynchronous timing/ISR/DMA/cache model"},
            "cases": cases, "samples": samples,
            "official_ilaunch3_sha256": builder.sha(official_body),
            "rewritten_ilaunch3_sha256": builder.sha(rewritten_body),
            "interpreter_sha256": builder.sha(Path(__file__).read_bytes()),
            "base_interpreter_sha256": builder.sha((ROOT / "research/stage1a_probe_v2/replay_guard.py").read_bytes()),
            "camera_execution_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not (output.is_relative_to(HERE)) or output.exists():
        raise ValueError("Use a new v3 research evidence file")
    official = builder.drill.load_official(ROOT / "artifacts/firmware/gxr-1.51")["ilaunch3"]
    elf = builder.parse_elf(args.elf.read_bytes(), inplace=True)
    result = verify(official, args.firmware.read_bytes(), elf["symbols"], quick=args.quick)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("passed", "primary_cases", "changing_iso_cases", "divergences", "scanning_cases", "byte_value_cases", "instruction_count")}))


if __name__ == "__main__":
    main()
