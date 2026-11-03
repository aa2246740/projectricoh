#!/usr/bin/env python3
"""本地 M32R 静态证据工具，所有输出限定在本目录。"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(rel, data):
    p = (OUT / rel).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")
    return p


def save(rel, obj):
    return write(rel, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


class Image:
    def __init__(self, name="jlaunch3"):
        self.name = name
        self.data = (OUT / "official" / name).read_bytes()
        records = json.loads((OUT / "evidence/official_inputs.json").read_text())
        rec = next(x for x in records if x["name"] == name)
        assert sha(self.data) == rec["sha256"]
        self.sections = rec["sections"]
        if name.endswith("0"):
            vma, size = struct.unpack_from(">II", self.data, 0x160)
            assert size + 0x200 == len(self.data)
            self.sections = [{"index": 0, "file_offset": 0x200, "vma": vma,
                              "size": size, "bss": 0, "bss_size": 0}]

    def offset(self, a, n=1):
        found = [s for s in self.sections if s["vma"] <= a and a + n <= s["vma"] + s["size"]]
        assert len(found) == 1, (self.name, hex(a), n)
        return found[0]["file_offset"] + a - found[0]["vma"]

    def read(self, a, n):
        off = self.offset(a, n)
        return self.data[off:off + n]

    def u32(self, a):
        return struct.unpack(">I", self.read(a, 4))[0]

    def disasm(self, a, b, stem):
        assert a % 4 == 0 and b > a
        raw = self.read(a, b - a)
        p = write(stem + ".bin", raw)
        cmd = [str(OBJDUMP), "-D", "-z", "-b", "binary", "-m", "m32r", "-EB",
               f"--adjust-vma=0x{a:x}", str(p)]
        run = subprocess.run(cmd, check=True, capture_output=True, text=True)
        write(stem + ".asm", run.stdout)
        save(stem + ".json", {"image": self.name, "image_sha256": sha(self.data),
                              "start": hex(a), "end": hex(b), "file_offset": hex(self.offset(a)),
                              "sha256": sha(raw), "command": cmd, "stderr": run.stderr})

    def lines(self):
        for s in self.sections:
            path = OUT / f"disasm/{self.name}-sec{s['index']:02d}.asm"
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                m = re.match(r"\s*([0-9a-f]{7,8}):\s+((?:[0-9a-f]{2} ){1,4})\s*(.*)", line)
                if not m:
                    continue
                pc = int(m[1], 16)
                code = bytes.fromhex(m[2])
                assert self.read(pc, len(code)) == code, line
                yield pc, m[3], line


def full(name):
    im = Image(name)
    for s in im.sections:
        if s["size"]:
            im.disasm(s["vma"], s["vma"] + s["size"], f"disasm/{name}-sec{s['index']:02d}")
    print(f"{name}: {len(im.sections)} mapped sections")


def raw(a, b, label, name="jlaunch3"):
    im = Image(name)
    data = im.read(a, b - a)
    write("evidence/" + label + ".bin", data)
    rows = [f"{a + i:08X} file={im.offset(a + i):08X} {data[i:i+16].hex(' ')}"
            for i in range(0, len(data), 16)]
    write("evidence/" + label + ".txt", "\n".join(rows) + "\n")
    save("evidence/" + label + ".json", {"image": name, "vma": hex(a), "end": hex(b),
                                        "file_offset": hex(im.offset(a)), "sha256": sha(data)})


def refs(name, targets, label):
    im = Image(name)
    result = {hex(t): {"direct": [], "constant_calls": [], "constants": [], "pointers": []}
              for t in targets}
    regs = {}
    previous = None
    total = 0
    for pc, asm, line in im.lines():
        total += 1
        if previous is None or pc - previous > 4:
            regs.clear()
        previous = pc
        item = {"pc": hex(pc), "file_offset": hex(im.offset(pc)), "text": line}
        for m in re.finditer(r"\b(?:bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bgtz|blez|bltz)\b[^|]*?\b(0x[0-9a-f]+)", asm):
            target = int(m[1], 16)
            if target in targets:
                result[hex(target)]["direct"].append(item)
        old = dict(regs)
        parallel = "||" in asm
        pending = {}
        clear_after = False
        for insn in re.split(r"\s*(?:->|\|\|)\s*", asm):
            words = insn.split(None, 1)
            if not words:
                continue
            op = words[0]
            args = words[1].split(",") if len(words) > 1 else []
            args = [x.strip() for x in args]
            dest = args[0] if args else ""
            src = old if parallel else regs
            value = None
            try:
                if op in ("seth", "ld24", "ldi") and len(args) == 2:
                    value = int(args[1].lstrip("#"), 0)
                    if op == "seth":
                        value <<= 16
                elif op in ("or3", "add3", "and3") and len(args) == 3 and args[1] in src:
                    value0 = src[args[1]]
                    imm = int(args[2].lstrip("#"), 0)
                    value = value0 | imm if op == "or3" else value0 + imm if op == "add3" else value0 & imm
                elif op == "mv" and len(args) == 2:
                    value = src.get(args[1])
                elif op == "addi" and len(args) == 2 and dest in src:
                    value = src[dest] + int(args[1].lstrip("#"), 0)
                elif op in ("jl", "jmp"):
                    target = src.get(dest)
                    if target in targets:
                        hit = dict(item, registers={k: hex(v) for k, v in src.items()})
                        result[hex(target)]["constant_calls"].append(hit)
                    if op == "jl":
                        for reg in [f"r{i}" for i in range(8)] + ["lr"]:
                            regs.pop(reg, None)
                    else:
                        clear_after = True
                    continue
            except ValueError:
                pass
            if value is not None:
                value &= 0xFFFFFFFF
                if parallel:
                    pending[dest] = value
                else:
                    regs[dest] = value
                if value in targets:
                    result[hex(value)]["constants"].append(dict(item, register=dest))
            elif dest and re.fullmatch(r"r\d+|fp|sp|lr", dest) and op not in (
                    "st", "sth", "stb", "cmp", "cmpu", "cmpi", "cmpui", "beqz", "bnez", "push"):
                regs.pop(dest, None)
        regs.update(pending)
        if clear_after or re.search(r"\b(?:bra|bl)\b", asm):
            regs.clear()
    for s in im.sections:
        data = im.read(s["vma"], s["size"])
        for target in targets:
            pat = struct.pack(">I", target)
            start = 0
            while True:
                pos = data.find(pat, start)
                if pos < 0:
                    break
                result[hex(target)]["pointers"].append({"vma": hex(s["vma"] + pos),
                    "file_offset": hex(s["file_offset"] + pos), "alignment": (s["vma"] + pos) % 4})
                start = pos + 1
    save("evidence/" + label + ".json", {"image": name, "checked_listing_lines": total,
         "scope": "全部已初始化段；直接目标、局部常量传播、原始大端指针。数据区候选需读上下文；间接调用与跨基本块别名未闭合。",
         "targets": result})
    for target, row in result.items():
        print(target, {k: len(v) for k, v in row.items()})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("full", "window", "raw", "refs"))
    p.add_argument("values", nargs="+")
    args = p.parse_args()
    if args.action == "full":
        for name in args.values:
            full(name)
    elif args.action == "window":
        name, a, b, label = args.values
        Image(name).disasm(int(a, 0), int(b, 0), "evidence/" + label)
    elif args.action == "raw":
        name, a, b, label = args.values
        raw(int(a, 0), int(b, 0), label, name)
    else:
        name, label, *targets = args.values
        refs(name, [int(t, 0) for t in targets], label)


if __name__ == "__main__":
    main()
