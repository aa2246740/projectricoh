#!/usr/bin/env python3
"""Build the local read-only gate probe and audit it. Never touches a card."""
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
GCC = ROOT / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
BIN = ROOT / "research/tooling_m32r_asm/prefix/bin"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
OFFICIAL = ROOT / "artifacts/firmware/gxr-1.51"
IMAGE = OFFICIAL / "ilaunch3"
IMAGE_SHA = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
OFFICIAL_SUM = 0x6ACDB212
FILE_BASE = 0x2004AE00
GLYPH_LO = 0x2005276C
GLYPH_HI = 0x20052D6C
REENTRY = 0x200546FF
TAIL_LO = 0x20054700
TAIL_HI = 0x20054800
CODE = 0x20052EAC
NATIVES = {
    0x201D73E0: "gxr_ascii",
    0x201DC180: "gxr_language",
    0x201FD360: "gxr_list_paint",
}
FORBIDDEN_CALLS = {
    0x202D6F38: "gxr_preview",
    0x201C092C: "gxr_layer_action",
    0x2009005C: "rpc8",
}
FORBIDDEN_STORES = {
    0x200C0DAC: "settings-pointer",
    0x205D9BF8: "activity-word",
    0x2022F71C: "type-byte",
    0x205A280F: "part-byte",
    0x205A27D4: "count-byte",
}
HOOKS = (
    ("sample_and_draw", 0x202871C4, 0x23C3C4, "d0c0203380e01d14", "d0c0200580e02eac"),
    ("confirm_return", 0x202871D8, 0x23C3D8, "2e7ff000", "1fcef000"),
    ("type5_names", 0x2022F5A8, 0x1E47A8, "2022d610", "20052dac"),
    ("type5_rows", 0x2022F5AC, 0x1E47AC, "07", "10"),
    ("type5_details", 0x201FEBE4, 0x1B3DE4, "d2c0202382e2fd38", "d2c0200582e22dec"),
)
KEEP = (
    ("image_mode_getter", 0x2028709C, 0x23C29C, "d0c0202780e01fec"),
    ("cursor_switch", 0x202870A8, 0x23C2A8, "12806005"),
    ("dispatcher", 0x202BA6FC, 0x26F8FC, "d2c0205e"),
    ("live_commit", 0x202BB968, 0x270B68, "dbc02022"),
    ("fn2", 0x202BE24C, 0x27344C, "d0c02026"),
)
JUMP_TABLE_VA = 0x20377434
JUMP_TABLE_FILE = 0x32C634
JUMP_TABLE = bytes.fromhex(
    "00fc0118007002bc01540000001c0038005402bc00e0008c"
    "00a800c401bc01d802bc0250026c02bc028802a4")
PACKAGE = ROOT / "artifacts/gate-probe-packages/gate-probe-r1"
OUT = HERE / "build"
STEP_LIMIT = 2_000_000

REGS = {f"r{i}": i for i in range(16)}
REGS.update(fp=13, lr=14, sp=15)
UNK = ("u",)
C_UNK = None


def fail(message):
    raise SystemExit(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checksum(image):
    return sum(byte * ((index % 6) + 2) for index, byte in enumerate(image[0x200:])) & 0xFFFFFFFF


def run(argv, out_path):
    result = subprocess.run([str(arg) for arg in argv], cwd=ROOT, text=True, capture_output=True)
    out_path.write_text(result.stdout + result.stderr)
    if result.returncode:
        fail(f"{argv[0]} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def file_offset(va, image):
    direct = va - FILE_BASE
    hits = []
    for index in range(16):
        source, load, size, _bss, _bss_size = struct.unpack_from(">5I", image, 0x20 + index * 20)
        if load <= va < load + size:
            hits.append(source + 512 + (va - load))
    if hits != [direct]:
        fail(f"file offset for {va:#x} is {hits}, formula gave {direct:#x}")
    return direct


def u32(value):
    return value & 0xFFFFFFFF


def parse_imm(text):
    return int(text.replace("#", ""), 0)


class Insn:
    def __init__(self, pc, text, fall):
        self.pc = pc
        self.text = text
        self.fall = fall


def parse_disassembly(path):
    insns = {}
    line_re = re.compile(r"^([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$")
    pending = []
    for raw in path.read_text().splitlines():
        match = line_re.match(raw)
        if not match:
            continue
        pc = int(match.group(1), 16)
        raw_bytes = bytes.fromhex(match.group(2))
        text = match.group(3).strip()
        if " -> " in text:
            parts = [part.strip() for part in text.split(" -> ")]
            slots = [(pc, parts[0], 2), (pc + 2, parts[1], 2)]
        elif text.endswith(" || nop"):
            slots = [(pc, text[:-len(" || nop")].strip(), 4)]
        elif " || " in text:
            fail(f"unhandled parallel pair at {pc:#x}: {text}")
        else:
            slots = [(pc, text, len(raw_bytes))]
        for slot_pc, slot_text, size in slots:
            pending.append((slot_pc, slot_text, size))
    for index, (pc, text, size) in enumerate(pending):
        fall = pending[index + 1][0] if index + 1 < len(pending) else None
        # A 2-byte left slot falls into the right slot. A 4-byte insn falls
        # into the next architectural instruction, which is the next entry.
        if size == 4:
            fall = pc + 4
        insns[pc] = Insn(pc, text, fall)
    return insns


def reg_index(name):
    if name not in REGS:
        fail(f"unknown register {name}")
    return REGS[name]


def is_const(value):
    return value[0] == "c"


def const_of(value):
    return value[1]


def is_stack(value):
    return value[0] == "s"


def tokenize(text):
    protected = []

    def hide(match):
        protected.append(match.group(0))
        return f"__ADDR{len(protected) - 1}__"

    hidden = re.sub(r"@\([^)]*\)", hide, text)
    hidden = hidden.replace(",", " ")
    hidden = hidden.replace("@", " @")
    tokens = []
    for token in hidden.split():
        if token.startswith("__ADDR"):
            tokens.append(protected[int(token[6:-2])])
        else:
            tokens.append(token)
    return tokens


class Machine:
    def __init__(self, insns):
        self.insns = insns
        self.stores = {}
        self.calls = {}
        self.steps = 0
        self.glyph_bytes = 0
        self.reentry_values = set()

    def record_store(self, pc, text, kind, address, width, stored):
        slot = self.stores.setdefault(pc, {
            "text": text, "kind": kind, "width": width, "count": 0,
            "min": None, "max": None, "values": set(),
        })
        if slot["kind"] != kind or slot["width"] != width:
            fail(f"store at {pc:#x} changed classification")
        slot["count"] += 1
        if address is not None:
            slot["min"] = address if slot["min"] is None else min(slot["min"], address)
            slot["max"] = address if slot["max"] is None else max(slot["max"], address)
        if stored is not None and len(slot["values"]) < 8:
            slot["values"].add(stored)
        if kind == "glyph":
            self.glyph_bytes += width
        if kind == "reentry" and stored is not None:
            self.reentry_values.add(stored)

    def record_call(self, pc, target, kind):
        self.calls.setdefault((pc, target), {"kind": kind, "count": 0})
        self.calls[(pc, target)]["count"] += 1

    def check_store(self, pc, text, address, width, stored):
        if address is None:
            fail(f"store address is not provable at {pc:#x}: {text}")
        last = address + width - 1
        for forbidden, name in FORBIDDEN_STORES.items():
            if address <= forbidden <= last:
                fail(f"store hits {name} {forbidden:#x} at {pc:#x}: {text}")
        if GLYPH_LO <= address and last < GLYPH_HI:
            self.record_store(pc, text, "glyph", address, width, stored)
            return
        if width == 1 and address == REENTRY:
            self.record_store(pc, text, "reentry", address, width, stored)
            return
        fail(f"store outside glyph/reentry/stack at {pc:#x}: {text} address {address:#x} width {width}")

    def run(self):
        start = (
            CODE,
            (UNK,) * 15 + (("s", 0),),
            C_UNK,
            (),
            (),
        )
        seen = set()
        work = [start]
        while work:
            state = work.pop()
            if state in seen:
                continue
            seen.add(state)
            self.steps += 1
            if self.steps > STEP_LIMIT:
                fail(f"store audit exceeded {STEP_LIMIT} steps at {state[0]:#x}")
            for successor in self.successors(state):
                if successor is not None:
                    work.append(successor)
        return len(seen)

    def successors(self, state):
        pc, regs, carry, mem_items, calls = state
        insn = self.insns.get(pc)
        if insn is None:
            fail(f"execution left the instruction map at {pc:#x}")
        regs = list(regs)
        mem = dict(mem_items)
        action = self.execute(insn, regs, mem, carry)
        mem_items = tuple(sorted(mem.items()))
        regs_t = tuple(regs)
        kind = action[0]
        if kind == "fall":
            carry = action[1]
            if insn.fall is None:
                fail(f"fallthrough missing at {pc:#x}")
            return [(insn.fall, regs_t, carry, mem_items, calls)]
        if kind == "goto":
            return [(action[1], regs_t, action[2], mem_items, calls)]
        if kind == "fork":
            left, right = action[1], action[2]
            return [
                (left, regs_t, action[3], mem_items, calls),
                (right, regs_t, action[3], mem_items, calls),
            ]
        if kind == "call":
            target, ret, carry = action[1], action[2], action[3]
            self.record_call(pc, target, "payload")
            if target in FORBIDDEN_CALLS or target in NATIVES:
                fail(f"payload call landed on a native at {pc:#x}")
            return [(target, regs_t, carry, mem_items, calls + (ret,))]
        if kind == "native":
            target, ret, carry = action[1], action[2], action[3]
            if target in FORBIDDEN_CALLS:
                fail(f"forbidden call to {FORBIDDEN_CALLS[target]} at {pc:#x}")
            if target not in NATIVES:
                fail(f"jl target {target:#x} is neither payload nor an allowed native at {pc:#x}")
            self.record_call(pc, target, NATIVES[target])
            return [(ret, regs_t, carry, mem_items, calls)]
        if kind == "ret":
            if not calls:
                return []
            return [(calls[-1], regs_t, action[1], mem_items, calls[:-1])]
        fail(f"bad action {action}")

    def execute(self, insn, regs, mem, carry):
        text = insn.text
        pc = insn.pc
        word = tokenize(text)

        def need(value, what):
            if not is_const(value):
                fail(f"expected a constant {what} at {pc:#x}: {text}")
            return const_of(value)

        def set_reg(name, value):
            regs[reg_index(name)] = value

        def get(name):
            return regs[reg_index(name)]

        def write_mem(address, width, value):
            if is_stack(address):
                base = address[1]
                self.record_store(pc, text, "stack", None, width, None)
                for offset in range(width):
                    mem.pop(base + offset, None)
                if is_const(value):
                    raw = const_of(value) & ((1 << (8 * width)) - 1)
                    for offset in range(width):
                        shift = 8 * (width - 1 - offset)
                        mem[base + offset] = (raw >> shift) & 0xFF
                return
            if is_const(address):
                self.check_store(pc, text, const_of(address), width,
                                 const_of(value) if is_const(value) else None)
                return
            fail(f"unclassified store at {pc:#x}: {text}")

        def read_mem(address, width, signed=False):
            if not is_stack(address):
                return UNK
            base = address[1]
            bytes_ = []
            for offset in range(width):
                if base + offset not in mem:
                    return UNK
                bytes_.append(mem[base + offset])
            raw = 0
            for byte in bytes_:
                raw = (raw << 8) | byte
            if signed and width == 1 and raw >= 0x80:
                raw -= 0x100
            return ("c", u32(raw))

        word = text.replace(",", " ").split()
        op = word[0]
        if op == "nop":
            return ("fall", carry)
        if op == "push":
            set_reg("sp", ("s", get("sp")[1] - 4))
            write_mem(get("sp"), 4, get(word[1]))
            return ("fall", carry)
        if op == "pop":
            loaded = read_mem(get("sp"), 4)
            set_reg("sp", ("s", get("sp")[1] + 4))
            set_reg(word[1], loaded)
            return ("fall", carry)
        if op == "seth":
            set_reg(word[1], ("c", u32(parse_imm(word[2]) << 16)))
            return ("fall", carry)
        if op == "or3":
            base = need(get(word[2]), "or3 base")
            set_reg(word[1], ("c", u32(base | (parse_imm(word[3]) & 0xFFFF))))
            return ("fall", carry)
        if op == "ldi":
            set_reg(word[1], ("c", u32(parse_imm(word[2]))))
            return ("fall", carry)
        if op == "mv":
            set_reg(word[1], get(word[2]))
            return ("fall", carry)
        if op == "add":
            left, right = get(word[1]), get(word[2])
            if is_const(left) and is_const(right):
                set_reg(word[1], ("c", u32(const_of(left) + const_of(right))))
            elif is_stack(left) and is_const(right):
                set_reg(word[1], ("s", left[1] + const_of(right)))
            elif is_const(left) and is_stack(right):
                set_reg(word[1], ("s", right[1] + const_of(left)))
            else:
                set_reg(word[1], UNK)
            return ("fall", C_UNK)
        if op == "add3":
            src, imm = get(word[2]), parse_imm(word[3])
            if is_const(src):
                set_reg(word[1], ("c", u32(const_of(src) + imm)))
            elif is_stack(src):
                set_reg(word[1], ("s", src[1] + imm))
            else:
                set_reg(word[1], UNK)
            return ("fall", C_UNK)
        if op == "addi":
            src, imm = get(word[1]), parse_imm(word[2])
            if is_const(src):
                set_reg(word[1], ("c", u32(const_of(src) + imm)))
            elif is_stack(src):
                set_reg(word[1], ("s", src[1] + imm))
            else:
                set_reg(word[1], UNK)
            return ("fall", C_UNK)
        if op == "ld24":
            match = re.fullmatch(r"ld24\s+(\w+),([0-9a-fA-F]+).*", text)
            if not match:
                fail(f"bad ld24 at {pc:#x}: {text}")
            set_reg(match.group(1), ("c", int(match.group(2), 16)))
            return ("fall", carry)
        if op in ("and", "xor", "or"):
            left, right = get(word[1]), get(word[2])
            if is_const(left) and is_const(right):
                fn = {"and": int.__and__, "xor": int.__xor__, "or": int.__or__}[op]
                set_reg(word[1], ("c", u32(fn(const_of(left), const_of(right)))))
            else:
                set_reg(word[1], UNK)
            return ("fall", C_UNK)
        if op == "and3":
            src, imm = get(word[2]), parse_imm(word[3])
            if is_const(src):
                set_reg(word[1], ("c", u32(const_of(src) & imm)))
            else:
                set_reg(word[1], UNK)
            return ("fall", carry)
        if op == "slli":
            src = get(word[1])
            if is_const(src):
                set_reg(word[1], ("c", u32(const_of(src) << parse_imm(word[2]))))
            else:
                set_reg(word[1], UNK)
            return ("fall", carry)
        if op == "srl":
            src, amount = get(word[1]), get(word[2])
            if is_const(src) and is_const(amount):
                set_reg(word[1], ("c", u32(const_of(src) >> (const_of(amount) & 31))))
            else:
                set_reg(word[1], UNK)
            return ("fall", carry)
        if op == "srl3":
            src = get(word[2])
            if is_const(src):
                set_reg(word[1], ("c", u32(const_of(src) >> parse_imm(word[3]))))
            else:
                set_reg(word[1], UNK)
            return ("fall", carry)
        if op == "cmpu":
            left, right = get(word[1]), get(word[2])
            if is_const(left) and is_const(right):
                carry = int(u32(const_of(left)) < u32(const_of(right)))
            else:
                carry = C_UNK
            return ("fall", carry)
        if op == "cmpui":
            src = get(word[1])
            if is_const(src):
                carry = int(u32(const_of(src)) < parse_imm(word[2]))
            else:
                carry = C_UNK
            return ("fall", carry)
        if op == "mvfc" and word[2:] == ["cbr"]:
            set_reg(word[1], UNK if carry is None else ("c", carry))
            return ("fall", carry)
        if op in ("ld", "ldub", "ldb"):
            width = 4 if op == "ld" else 1
            address = self.address_of(text, regs)
            set_reg(word[1], read_mem(address, width, signed=(op == "ldb")))
            return ("fall", carry)
        if op in ("st", "sth", "stb"):
            width = {"st": 4, "sth": 2, "stb": 1}[op]
            address = self.address_of(text, regs)
            write_mem(address, width, get(word[1]))
            return ("fall", carry)
        if op == "bra":
            return ("goto", int(word[1], 16), carry)
        if op == "bl":
            target = int(word[1], 16)
            if insn.fall is None:
                fail(f"bl without return at {pc:#x}")
            set_reg("lr", ("c", insn.fall))
            return ("call", target, insn.fall, carry)
        if op == "jl":
            target_v = get(word[1])
            target = need(target_v, "jl target")
            if insn.fall is None:
                fail(f"jl without return at {pc:#x}")
            set_reg("lr", ("c", insn.fall))
            if target in NATIVES or target in FORBIDDEN_CALLS:
                for index in range(8):
                    regs[index] = UNK
                return ("native", target, insn.fall, carry)
            if not (CODE <= target < TAIL_LO):
                fail(f"jl leaves the payload at {pc:#x}: {target:#x}")
            return ("call", target, insn.fall, carry)
        if op == "jmp" and word[1] == "lr":
            return ("ret", carry)
        if op in ("beqz", "bnez"):
            src = get(word[1])
            target = int(word[2], 16)
            if not is_const(src):
                return ("fork", target, insn.fall, carry)
            taken = const_of(src) == 0 if op == "beqz" else const_of(src) != 0
            return ("goto", target if taken else insn.fall, carry)
        if op in ("beq", "bne"):
            left, right = get(word[1]), get(word[2])
            target = int(word[3], 16)
            if is_const(left) and is_const(right):
                same = const_of(left) == const_of(right)
            elif is_stack(left) and is_stack(right):
                same = left[1] == right[1]
            elif (is_stack(left) and is_const(right)) or (is_const(left) and is_stack(right)):
                same = False
            else:
                return ("fork", target, insn.fall, carry)
            taken = same if op == "beq" else not same
            return ("goto", target if taken else insn.fall, carry)
        if op in ("bc", "bnc"):
            target = int(word[1], 16)
            if carry is None:
                return ("fork", target, insn.fall, carry)
            taken = bool(carry) if op == "bc" else not bool(carry)
            return ("goto", target if taken else insn.fall, carry)
        fail(f"unhandled instruction at {pc:#x}: {text}")

    def address_of(self, text, regs):
        indirect = re.search(r"@([a-z0-9]+)$", text)
        if indirect:
            return regs[reg_index(indirect.group(1))]
        displaced = re.search(r"@\((-?0x[0-9a-fA-F]+|-?\d+),([a-z0-9]+)\)$", text)
        if not displaced:
            fail(f"no address in {text}")
        base = regs[reg_index(displaced.group(2))]
        disp = int(displaced.group(1), 0)
        if is_const(base):
            return ("c", u32(const_of(base) + disp))
        if is_stack(base):
            return ("s", base[1] + disp)
        return UNK


def audit_control(insns):
    machine = Machine(insns)
    states = machine.run()
    required = set(NATIVES)
    seen_natives = {target for (_pc, target), info in machine.calls.items() if info["kind"] in NATIVES.values()}
    if seen_natives != required:
        fail(f"native calls were {sorted(hex(item) for item in seen_natives)}")
    if not any(item["kind"] == "glyph" for item in machine.stores.values()):
        fail("no glyph store was proven")
    if machine.reentry_values != {0, 1}:
        fail(f"reentry stores were {machine.reentry_values}")
    summary = []
    for pc in sorted(machine.stores):
        item = machine.stores[pc]
        summary.append({
            "pc": hex(pc), "text": item["text"], "kind": item["kind"],
            "width": item["width"], "count": item["count"],
            "min": None if item["min"] is None else hex(item["min"]),
            "max": None if item["max"] is None else hex(item["max"]),
            "values": sorted(item["values"]),
        })
    calls = [{"pc": hex(pc), "target": hex(target), "kind": info["kind"], "count": info["count"]}
             for (pc, target), info in sorted(machine.calls.items())]
    return {"states": states, "steps": machine.steps, "glyph_byte_writes": machine.glyph_bytes,
            "stores": summary, "calls": calls}


def expected_tables():
    labels = b"".join(struct.pack(">I", GLYPH_LO + 96 * index) for index in range(16))
    table = b"".join(struct.pack(">I", 0x20052D6C + 4 * index) for index in range(16))
    return labels, table


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    host = OUT / "test_host"
    host_cc = run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-DPROBE_HOST",
                   HERE / "tests/test_host.c", "-o", host], OUT / "host-compile.txt")
    host_run = subprocess.run([str(host)], text=True, capture_output=True)
    (OUT / "host-results.txt").write_text(host_run.stdout + host_run.stderr)
    if host_run.returncode or host_run.stdout.strip() != "host-ok":
        fail(f"host test failed: {host_run.stdout} {host_run.stderr}")

    image = bytearray(IMAGE.read_bytes())
    if sha(image) != IMAGE_SHA:
        fail("official ilaunch3 hash mismatch")
    stored = struct.unpack_from(">I", image, 0x16C)[0]
    calculated = checksum(image)
    if stored != OFFICIAL_SUM or calculated != OFFICIAL_SUM:
        fail(f"official checksum stored {stored:#x} calculated {calculated:#x}")
    if image[0x796C:0x9A00] != b"\xff" * (0x9A00 - 0x796C):
        fail("official payload hole or tail is not FF")
    for name, va, offset, old, _new in HOOKS:
        if file_offset(va, image) != offset or image[offset:offset + len(bytes.fromhex(old))] != bytes.fromhex(old):
            fail(f"hook original mismatch: {name}")
    for name, va, offset, old in KEEP:
        if file_offset(va, image) != offset or image[offset:offset + len(bytes.fromhex(old))] != bytes.fromhex(old):
            fail(f"kept site mismatch: {name}")
    if file_offset(JUMP_TABLE_VA, image) != JUMP_TABLE_FILE or image[JUMP_TABLE_FILE:JUMP_TABLE_FILE + 44] != JUMP_TABLE:
        fail("jump table mismatch")

    flags = ["-std=c11", "-Os", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
             "-fno-common", "-fno-pic", "-m32r", "-mmodel=large", "-msdata=none", "-G0",
             "-Wall", "-Wextra", "-Werror", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
             "-fstack-usage", "-fomit-frame-pointer", "-fno-tree-loop-distribute-patterns",
             "-fno-jump-tables"]
    sources = [HERE / "layout.S", HERE / "abi.S", HERE / "entry.S", HERE / "probe_render.c"]
    objects = []
    for source in sources:
        obj = OUT / (source.stem + ".o")
        objects.append(obj)
        if source.suffix == ".S":
            run([BIN / "m32r-elf-as", "-o", obj, source], OUT / f"assemble-{source.stem}.txt")
        else:
            run([GCC, *flags, "-c", source, "-o", obj], OUT / f"compile-{source.stem}.txt")
    elf_path = OUT / "payload.elf"
    run([BIN / "m32r-elf-ld", "--no-undefined", "--orphan-handling=error",
         "-T", HERE / "payload.ld", f"-Map={OUT / 'payload.map'}", "-o", elf_path, *objects],
        OUT / "link.txt")
    disasm_path = OUT / "payload-disasm.txt"
    run([OBJDUMP, "-d", "-z", elf_path], disasm_path)
    sym_text = run([OBJDUMP, "-t", elf_path], OUT / "payload-syms.txt")
    symbols = {}
    for line in sym_text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and re.fullmatch(r"[0-9a-f]{8}", parts[0]):
            symbols[parts[-1]] = int(parts[0], 16)
    expected = {
        "probe_glyphs": GLYPH_LO, "probe_labels": 0x20052D6C, "probe_table": 0x20052DAC,
        "probe_no_details": 0x20052DEC, "gate_probe_render": CODE,
        "__code_end": symbols.get("__code_end"),
    }
    for name, address in expected.items():
        if symbols.get(name) != address:
            fail(f"symbol {name} is {symbols.get(name)} expected {address}")
    code_end = symbols["__code_end"]
    if not (CODE < code_end <= REENTRY):
        fail(f"code end {code_end:#x} is outside the allowed window")

    elf = elf_path.read_bytes()
    if elf[:6] != b"\x7fELF\x01\x02":
        fail("payload is not ELF32 big-endian")
    header = struct.unpack_from(">HHIIIIIHHHHHH", elf, 16)
    if header[1] != 88:
        fail("payload machine is not M32R")
    shoff, shentsize, shnum, shstr = header[5], header[10], header[11], header[12]
    sections = []
    for index in range(shnum):
        name_off, sec_type, _flags, addr, offset, size = struct.unpack_from(">IIIIII", elf, shoff + index * shentsize)
        sections.append((name_off, sec_type, addr, offset, size))
    name_data = elf[sections[shstr][3]:sections[shstr][3] + sections[shstr][4]]
    named = {}
    for name_off, _sec_type, addr, offset, size in sections:
        name = name_data[name_off:name_data.index(0, name_off)].decode()
        if size and name:
            named[name] = (addr, elf[offset:offset + size])
    labels, table = expected_tables()
    if named[".probe_glyphs"] != (GLYPH_LO, b"\x00" * 0x600):
        fail("probe_glyphs image is not 1536 zero bytes")
    if named[".probe_labels"] != (0x20052D6C, labels):
        fail("probe_labels pointers differ from the design")
    if named[".probe_table"] != (0x20052DAC, table):
        fail("probe_table pointers differ from the design")
    if named[".probe_no_details"] != (0x20052DEC, b"\x00" * 0xC0):
        fail("probe_no_details is not 192 zero bytes")
    code_bytes = named[".text"][1]
    if named[".text"][0] != CODE or CODE + len(code_bytes) != code_end:
        fail("linked code does not occupy 0x20052EAC through __code_end")
    if b"\x20\x0c\x0d\xac" in code_bytes or b"\x20\x2d\x6f\x38" in code_bytes or b"\x20\x1c\x09\x2c" in code_bytes or b"\x20\x09\x00\x5c" in code_bytes:
        fail("forbidden absolute address is embedded in the code")

    audit = audit_control(parse_disassembly(disasm_path))
    (OUT / "store-audit.json").write_text(json.dumps(audit, indent=2) + "\n")

    patched = bytearray(image)
    for addr, blob in (
        named[".probe_glyphs"], named[".probe_labels"], named[".probe_table"],
        named[".probe_no_details"], named[".text"],
    ):
        start = file_offset(addr, image)
        patched[start:start + len(blob)] = blob
    patched[file_offset(REENTRY, image)] = 0
    for _name, _va, offset, _old, new in HOOKS:
        raw = bytes.fromhex(new)
        patched[offset:offset + len(raw)] = raw
    new_sum = checksum(patched)
    struct.pack_into(">I", patched, 0x16C, new_sum)
    if checksum(patched) != new_sum:
        fail("checksum did not stick")
    if patched[:0x16C] != image[:0x16C] or patched[0x170:0x200] != image[0x170:0x200]:
        fail("header changed outside the checksum word")
    if patched[0x9900:0x9A00] != b"\xff" * 0x100:
        fail("probe tail was modified")
    for name, _va, offset, old in KEEP:
        if patched[offset:offset + len(bytes.fromhex(old))] != bytes.fromhex(old):
            fail(f"kept site changed: {name}")
    if patched[JUMP_TABLE_FILE:JUMP_TABLE_FILE + 44] != JUMP_TABLE:
        fail("jump table changed")

    allowed = {(0x16C, 0x170), (0x796C, 0x9900)}
    for _name, _va, offset, _old, new in HOOKS:
        allowed.add((offset, offset + len(bytes.fromhex(new))))
    ranges = []
    cursor = 0
    while cursor < len(image):
        if patched[cursor] == image[cursor]:
            cursor += 1
            continue
        end = cursor + 1
        while end < len(image) and patched[end] != image[end]:
            end += 1
        ranges.append((cursor, end))
        cursor = end
    def allowed_byte(index):
        return any(lo <= index < hi for lo, hi in allowed)

    for start, end in ranges:
        if not all(allowed_byte(index) for index in range(start, end)):
            fail(f"difference {start:#x}..{end:#x} is outside the allowed set")
    for _name, _va, offset, _old, new in HOOKS:
        if patched[offset:offset + len(bytes.fromhex(new))] != bytes.fromhex(new):
            fail("hook new bytes were not written")

    official_files = sorted(path for path in OFFICIAL.iterdir() if path.is_file())
    if len(official_files) != 29:
        fail(f"official tree has {len(official_files)} files")
    if PACKAGE.exists():
        fail(f"refusing to overwrite {PACKAGE}")
    (PACKAGE / "candidate/SD_ROOT").mkdir(parents=True)
    (PACKAGE / "recovery-official-1.51/SD_ROOT").mkdir(parents=True)
    staged = OUT / "ilaunch3"
    staged.write_bytes(patched)
    for path in official_files:
        for tree in ("candidate/SD_ROOT", "recovery-official-1.51/SD_ROOT"):
            subprocess.run(["cp", "-X", str(path), str(PACKAGE / tree / path.name)], check=True)
    subprocess.run(["cp", "-X", str(staged), str(PACKAGE / "candidate/SD_ROOT/ilaunch3")], check=True)
    for apple in PACKAGE.rglob("._*"):
        apple.unlink()
    sums = []
    for tree, source in (("recovery-official-1.51/SD_ROOT", "official"),
                         ("candidate/SD_ROOT", "candidate")):
        for path in official_files:
            written = PACKAGE / tree / path.name
            data = written.read_bytes()
            expected_bytes = patched if source == "candidate" and path.name == "ilaunch3" else path.read_bytes()
            if data != expected_bytes:
                fail(f"readback mismatch: {written}")
            sums.append((f"{tree}/{path.name}", sha(data)))
    sums.sort()
    sum_text = "".join(f"{digest}  {name}\n" for name, digest in sums)
    (PACKAGE / "SHA256SUMS").write_text(sum_text)
    if (PACKAGE / "SHA256SUMS").read_text() != sum_text:
        fail("SHA256SUMS readback mismatch")
    checked = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=PACKAGE,
                             text=True, capture_output=True)
    (OUT / "shasum.txt").write_text(checked.stdout + checked.stderr)
    if checked.returncode or checked.stdout.count(": OK") != 58:
        fail("shasum -c did not accept all 58 files")
    readme = """# GXR 门控只读探针 r1

这份包只在电脑上构建和核对过，没有写入 SD 卡，也没有上过相机。

打开 ADJ，进入 Image Settings。原来 7 行模式名的位置会显示 9 行十六进制，后面再加 7 行 `........`。九行依次是：

- `A`：活动字的低 8 位
- `T`：类型字节
- `P`：part 字节
- `C`：part2 栈深
- `G0`：栈顶 tag；条件不够不能解引用时是 `G0=--`
- `S`：栈顶 state；不能解引用时是 `S=--------`
- `V`：这一拍五个门控条件是否都成立，`01` 或 `00`
- `W`：活动字的全部 32 位
- `E`：entries 指针本身，不解引用

看的时候不要按 OK，不要按 Fn2，不要拨 ADJ 拨盘。看完关机。`V` 只代表开页这一拍，不代表之后按键时的值。

探针运行时只写自己的 16×96 字形缓冲，和 `0x200546FF` 这一个重入字节。它不写设置块，不改活动字、类型、part、count，也不调用预览、layer action 或 RPC-8。确认函数被改成直接返回，所以那五个原来的调用点不会再跑图像模式 setter。电源键会不会走别的写设置路径，还未知。

刷回官方 1.51：只把 `recovery-official-1.51/SD_ROOT/` 里面的 29 个文件复制到卡根，用相机自己的固件更新。不要把 `candidate` 和 `recovery` 混在同一张卡上。本目录没有代替你做这件事。
"""
    (PACKAGE / "README.md").write_text(readme)
    manifest = {
        "status": "LOCAL_BUILD_VERIFIED_NOT_FLASHED",
        "camera_executed": False,
        "sd_accessed": False,
        "official_ilaunch3_sha256": IMAGE_SHA,
        "probe_ilaunch3_sha256": sha(patched),
        "official_checksum": hex(OFFICIAL_SUM),
        "probe_checksum": hex(new_sum),
        "payload_linked_bytes": code_end - GLYPH_LO,
        "code_bytes": code_end - CODE,
        "code_end": hex(code_end),
        "reentry_initial": 0,
        "difference_ranges": [{"start": hex(start), "end": hex(end), "length": end - start}
                              for start, end in ranges],
        "hooks": [{"name": name, "va": hex(va), "file_offset": hex(offset),
                   "original": old, "new": new} for name, va, offset, old, new in HOOKS],
        "store_audit_states": audit["states"],
        "store_audit_steps": audit["steps"],
        "glyph_byte_writes_observed": audit["glyph_byte_writes"],
        "host_test": "host-ok",
    }
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for apple in PACKAGE.rglob("._*"):
        apple.unlink()
    result = {
        "probe_ilaunch3_sha256": sha(patched),
        "probe_checksum": hex(new_sum),
        "payload_linked_bytes": code_end - GLYPH_LO,
        "code_bytes": code_end - CODE,
        "code_end": hex(code_end),
        "difference_ranges": manifest["difference_ranges"],
        "store_sites": [{key: item[key] for key in ("pc", "text", "kind", "width", "min", "max")}
                        for item in audit["stores"]],
        "calls": audit["calls"],
        "host": "host-ok",
        "shasum_ok": 58,
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "probe_ilaunch3_sha256": result["probe_ilaunch3_sha256"],
        "probe_checksum": result["probe_checksum"],
        "code_bytes": result["code_bytes"],
        "ranges": result["difference_ranges"],
        "shasum_ok": 58,
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        fail(f"command failed: {error}")
