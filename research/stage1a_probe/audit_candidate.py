#!/usr/bin/env python3
"""Reproduce the bounded stage 1a static audit without executing firmware."""
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "evidence"
OLD = ROOT / "research/stage1_codespace/evidence"
START, END = 0x2005276C, 0x20054800
EXPECTED = {
    "ilaunch3": "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7",
    "ilaunch0": "b896f40d9f330c4235d99bd6e32963876f9701293530a927672fd6fab7281e65",
}
ROW = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ?)+)\s+(.+)$")
REG = r"(?:r\d+|sp|lr|fp)"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    images = {n: (ROOT / "artifacts/firmware/gxr-1.51" / n).read_bytes() for n in EXPECTED}
    assert all(sha(images[n]) == EXPECTED[n] for n in EXPECTED)
    body = images["ilaunch3"]
    sections = [struct.unpack_from(">5I", body, 0x20 + 20 * i) for i in range(16)]

    def at(va, image="ilaunch3"):
        if image == "ilaunch0":
            off = va - 0x27E00000 + 512
            return off if 512 <= off < len(images[image]) else None
        for src, load, length, _, _ in sections:
            if load <= va < load + length:
                return src + 512 + va - load
        return None

    def from_file(off, image):
        if image == "ilaunch0":
            return off + 0x27E00000 - 512, "monitor.disasm.txt"
        for i, (src, load, length, _, _) in enumerate(sections):
            if src + 512 <= off < src + 512 + length:
                return load + off - src - 512, f"body-seg{i:02d}.disasm.txt"
        return None, None

    all_rows, lookup, texts = {}, {}, {}
    for name in [f"body-seg{i:02d}.disasm.txt" for i in range(16)] + ["monitor.disasm.txt"]:
        text = (OLD / name).read_text().splitlines()
        texts[name] = text
        image = "ilaunch0" if name.startswith("monitor") else "ilaunch3"
        rows = []
        for ln, line in enumerate(text, 1):
            m = ROW.match(line)
            if not m:
                continue
            va, raw, asm = int(m[1], 16), bytes.fromhex(m[2]), m[3]
            off = at(va, image)
            assert off is not None and images[image][off:off + len(raw)] == raw
            row = {"image": image, "va": va, "file_offset": off,
                   "disassembly": str((OLD / name).relative_to(ROOT)), "line": ln,
                   "bytes": raw.hex(" "), "asm": asm}
            rows.append(row)
            lookup[image, va] = row
        all_rows[name] = rows

    def excerpt(name, low, high):
        rows = [r for r in all_rows[name] if low <= r["va"] < high]
        out = f"window-{low:08x}-{high:08x}.txt"
        (OUT / out).write_text("\n".join(
            f"{r['line']}: {r['va']:08x} file={r['file_offset']:08x} {r['bytes']} {r['asm']}"
            for r in rows) + "\n")
        return {"file": out, "source": rows[0]["disassembly"],
                "first_line": rows[0]["line"], "last_line": rows[-1]["line"]}

    # The original icon initializer computes offsets from width, height and packing.
    cursor = 0x20245CCE
    icons = []
    for i in range(183):
        va = 0x2023C224 + 16 * i
        off, width, height, kind = struct.unpack_from(">4I", body, at(va))
        div = 8 if kind in (1, 2) else 4 if kind in (3, 4) else 0
        size = ((width + div - 1) // div) * height if div else 0
        icons.append({"index": i, "descriptor_va": va, "descriptor_file": at(va),
                      "initial_offset": off, "width": width, "height": height,
                      "packing_type": kind, "computed_start": cursor,
                      "computed_end": cursor + size})
        cursor += size
    assert struct.unpack_from(">4I", body, at(0x2023CD94))[-1] == 255

    prior = next(x for x in json.loads((OLD / "uniform-xrefs.json").read_text())
                 if x["load"] == START)
    branches = []
    for ref in prior["instruction_refs"]:
        if START <= ref["site"] < END:
            continue
        row = lookup["ilaunch3", ref["site"]]
        icon = next(x for x in icons if x["computed_start"] <= ref["site"] < x["computed_end"])
        assert row["bytes"] == "ff f8 2f ef" and 47 <= icon["index"] <= 54
        branches.append({**row, "decoded_target": ref["target"], "icon": icon,
                         "classification": "bitmap bytes interpreted as a branch",
                         "evidence_level": "static bytes and initializer arithmetic",
                         "excerpt": excerpt("body-seg08.disasm.txt", ref["site"] - 16, ref["site"] + 20)})
    assert len(branches) == 8
    write("branch-matches.json", branches)

    patterns = []
    for image, data in images.items():
        for off in range(512, len(data) - 3):
            if data[off] != 0x20:
                continue
            word = struct.unpack_from(">I", data, off)[0]
            if not START <= word < END:
                continue
            va, name = from_file(off, image)
            assert va is not None
            anchor = va & ~3
            row = lookup[image, anchor]
            following = lookup.get((image, anchor + 4))
            patterns.append({"image": image, "file_offset": off, "va": va,
                             "value": word, "alignment": off % 4,
                             "instruction": row, "following": following,
                             "classification": "instruction bytes, not an address literal",
                             "excerpt": excerpt(name, anchor - 8, anchor + 16)})
    assert len(patterns) == 28
    write("be32-matches.json", patterns)

    # This is a bounded straight-line constant pass, not a control-flow proof.
    # Unknown loads remain unknown; current RAM never inherits file initializers.
    hits, accesses, calls, stack, words = [], [], [], [], 0
    for name, rows in all_rows.items():
        values = {}
        for row in rows:
            words += 1
            parallel_old = values.copy() if " || " in row["asm"] else None
            for part in re.split(r" -> | \|\| ", row["asm"]):
                op = part.split(" ", 1)[0]
                reg_match = re.match(rf"\w+ ({REG})", part)
                dest = reg_match[1] if reg_match else None
                operands = re.findall(r"\b" + REG + r"\b", part)
                old = parallel_old if parallel_old is not None else values.copy()
                def val(reg):
                    v = old.get(reg)
                    return v if v is not None and words - v[1] <= 64 else None
                def put(reg, v):
                    if v is None:
                        values.pop(reg, None)
                    else:
                        values[reg] = (v & 0xFFFFFFFF, words)
                        if START <= (v & 0xFFFFFFFF) < END:
                            hits.append({**row, "operation": part, "value": v & 0xFFFFFFFF})
                imm = re.search(r"#(-?0x[0-9a-f]+|-?\d+)", part)
                k = int(imm[1], 0) if imm else None
                if op == "seth" and dest and k is not None:
                    put(dest, k << 16)
                elif op == "ldi" and dest and k is not None:
                    put(dest, k)
                elif op == "ld24" and dest:
                    put(dest, int(part.split(",")[1], 16))
                elif op in ("mv", "neg") and len(operands) == 2:
                    v = val(operands[1])
                    put(dest, (v[0] if op == "mv" else -v[0]) if v else None)
                elif op in ("or3", "add3", "and3", "sll3", "srl3", "sra3") and len(operands) == 2 and k is not None:
                    v = val(operands[1])
                    if op in ("sll3", "srl3", "sra3") and not 0 <= k < 32:
                        put(dest, None)
                    elif v:
                        f = {"or3": lambda: v[0] | k, "add3": lambda: v[0] + k,
                             "and3": lambda: v[0] & k, "sll3": lambda: v[0] << k,
                             "srl3": lambda: v[0] >> k,
                             "sra3": lambda: (v[0] - (1 << 32) if v[0] & 0x80000000 else v[0]) >> k}
                        put(dest, f[op]())
                    else:
                        put(dest, None)
                elif op == "addi" and dest and k is not None:
                    v = val(dest)
                    put(dest, v[0] + k if v else None)
                elif op in ("add", "sub", "or", "and") and len(operands) == 2:
                    a, b = val(operands[0]), val(operands[1])
                    put(dest, {"add": lambda: a[0] + b[0], "sub": lambda: a[0] - b[0],
                               "or": lambda: a[0] | b[0], "and": lambda: a[0] & b[0]}[op]() if a and b else None)
                elif op.startswith(("ld", "st")) and "@" in part:
                    mem = re.search(rf"@\((-?\d+),({REG})\)|@([+]?{REG})([+]?)", part)
                    if mem:
                        base = mem[2] or mem[3].lstrip("+")
                        disp = int(mem[1]) if mem[1] else 0
                        width = 1 if op in ("ldb", "ldub", "stb") else 2 if op in ("ldh", "lduh", "sth") else 4
                        if mem[3] and mem[3].startswith("+"):
                            disp += width
                        v = val(base)
                        if v:
                            address = (v[0] + disp) & 0xFFFFFFFF
                            access = {**row, "operation": part, "address": address,
                                      "width": width, "kind": "write" if op.startswith("st") else "read"}
                            accesses.append(access)
                        if op.startswith("ld"):
                            put(dest, None)
                        if mem[3] and (mem[3].startswith("+") or mem[4]):
                            put(base, v[0] + width if v else None)
                elif op == "mvtc" and part.endswith((",spi", ",spu")):
                    v = val(dest)
                    stack.append({**row, "operation": part, "constant": v[0] if v else None})
                elif op in ("jl", "bl", "jmp"):
                    target = val(dest) if dest else None
                    if op == "bl":
                        m = re.search(r"0x([0-9a-f]+)", part)
                        target = (int(m[1], 16), words) if m else None
                    calls.append({**row, "operation": part,
                                  "target": target[0] if target else None,
                                  "args": {r: val(r)[0] if val(r) else None for r in ("r4", "r5", "r6", "r7")}})
                    if op in ("jl", "bl"):
                        for r in [f"r{i}" for i in range(8)]:
                            values.pop(r, None)
                    else:
                        values.clear()
                elif op in ("cmp", "cmpu", "cmpi", "cmpui", "cmpeq", "nop", "st", "stb", "sth", "push"):
                    pass
                elif op.startswith("b") or op in ("rte", "trap"):
                    values.clear()
                elif dest:
                    values.pop(dest, None)
    direct = [a for a in accesses if a["address"] < END and a["address"] + a["width"] > START]
    assert any(c["target"] == 0x20088358 for c in calls), "Loader positive control failed"
    assert any(a["address"] == 0x200D1838 for a in accesses), "Known clear-region control failed"
    assert any(c["target"] == 0x20062750 and c["args"]["r4"] == 0x20051ED8
               and c["args"]["r6"] == 2048 for c in calls), "Nearby memset control failed"
    write("constant-accesses.json", {"coverage": "all linear words, constants at most 64 words old; reset at branches; unknown loads not propagated",
                                     "word_count": words, "resolved_accesses": len(accesses),
                                     "candidate_constructed_values": hits, "candidate_accesses": direct,
                                     "nearby_accesses": [a for a in accesses if 0x20051EC8 <= a["address"] < 0x20055000],
                                     "stack_setters": stack,
                                     "known_loader_calls": [c for c in calls if c["target"] in (0x2004B89C, 0x20088358, 0x27E36980)],
                                     "nearby_memset_calls": [c for c in calls if c["target"] in (0x2004BD7C, 0x20062750)
                                        and c["args"]["r4"] is not None and 0x20051EC8 <= c["args"]["r4"] < 0x20055000]})
    windows = []
    for name, lo, hi in [
        ("body-seg00.disasm.txt", 0x2004B000, 0x2004B158),
        ("body-seg00.disasm.txt", 0x2004B89C, 0x2004BAF8),
        ("body-seg00.disasm.txt", 0x20050C0C, 0x20050C78),
        ("body-seg01.disasm.txt", 0x20055000, 0x200550A4),
        ("body-seg01.disasm.txt", 0x20068818, 0x200688F8),
        ("body-seg01.disasm.txt", 0x20088358, 0x200885A4),
        ("body-seg01.disasm.txt", 0x20089158, 0x200891C4),
        ("body-seg08.disasm.txt", 0x201D4FE4, 0x201D5098),
        ("body-seg08.disasm.txt", 0x201D5794, 0x201D5834),
        ("body-seg08.disasm.txt", 0x201D5834, 0x201D586C),
        ("body-seg14.disasm.txt", 0x204020E0, 0x20402154),
        ("body-seg15.disasm.txt", 0x050022BC, 0x050022E0),
        ("body-seg15.disasm.txt", 0x0500C918, 0x0500C930),
        ("monitor.disasm.txt", 0x27E00000, 0x27E000AC),
        ("monitor.disasm.txt", 0x27E36980, 0x27E36BD0),
    ]:
        windows.append(excerpt(name, lo, hi))
    write("windows.json", windows)
    candidate_bytes = body[0x796C:0x9A00]
    assert len(candidate_bytes) == 8340 and set(candidate_bytes) == {255}
    audit = {"schema": "gxr-stage1a-static-audit-v1", "candidate_va": [START, END],
             "candidate_file": [0x796C, 0x9A00], "original_sha256": sha(candidate_bytes),
             "inputs": EXPECTED, "audit_script_sha256": sha(Path(__file__).read_bytes()),
             "scan_word_count": words, "scan_resolved_accesses": len(accesses),
             "branch_matches": len(branches), "be32_matches": len(patterns),
             "constructed_candidate_values": len(hits), "resolved_candidate_accesses": len(direct),
             "sections": [{"index": i, "source": s, "load": v, "size": n, "bss": b, "bss_size": z,
                           "load_overlaps_candidate": v < END and v + n > START,
                           "bss_overlaps_candidate": b < END and b + z > START}
                          for i, (s, v, n, b, z) in enumerate(sections)],
             "decision": ("experimental candidate retained, no established owner in covered paths" if not hits and not direct
                          else "candidate excluded pending classification of resolved accesses"),
             "runtime_verified": False,
             "limitations": ["No reset ROM or module firmware analysis", "No whole-program indirect/DMA proof",
                             "Task stack values loaded from RAM are unknown", "Segment 0 reload is possible by loader contract; all runtime callers are not proven",
                             "File bytes and static negative searches do not prove RAM persistence or execute permission"]}
    write("static-audit.json", audit)
    print(json.dumps({k: audit[k] for k in ("branch_matches", "be32_matches", "constructed_candidate_values", "resolved_candidate_accesses", "decision")}))


if __name__ == "__main__":
    run()
