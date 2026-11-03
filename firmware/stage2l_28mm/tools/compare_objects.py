#!/usr/bin/env python3
"""Compare unrelocated per-function object code of two builds (Stage 2j vs Stage 2l).

Relocated fields hold no address in an M32R RELA object, so equal bytes and
equal relocation records (type, symbol, addend modulo the symbol's own move)
mean the function compiles to the same instructions. Prints JSON.

  python3 -I firmware/stage2l_switch/tools/compare_objects.py OLD_BUILD NEW_BUILD
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parents[1]
OBJECTS = ("abi.o", "platform.o", "ui.o", "deep_isp.o", "recipe_format.o", "recipe_apply.o")


def load_builder():
    spec = importlib.util.spec_from_file_location("stage2j_builder", HERE / "tools/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def functions(elf):
    """name -> (section name, bytes, relocations as (offset, type, symbol, addend))."""
    out = {}
    relocations = {}
    for section in elf.sections:
        if section["type"] != 4:
            continue
        target = elf.sections[section["info"]]["name"]
        table = elf.symbol_tables[section["link"]]
        for offset in range(0, section["size"], 12):
            address, info, addend = struct.unpack_from(">IIi", elf.bytes, section["offset"] + offset)
            symbol = table[info >> 8]
            name = symbol["name"] or elf.sections[symbol["section"]]["name"]
            relocations.setdefault(target, []).append((address, info & 0xff, name, addend))
    for table in elf.symbol_tables.values():
        for symbol in table:
            if symbol["info"] & 0xf != 2 or not symbol["size"]:
                continue
            section = elf.sections[symbol["section"]]
            start, end = symbol["value"], symbol["value"] + symbol["size"]
            blob = elf.bytes[section["offset"] + start:section["offset"] + end]
            relocs = [(a - start, t, n, addend if not n.startswith(".") else None)
                      for a, t, n, addend in relocations.get(section["name"], []) if start <= a < end]
            out[symbol["name"]] = (section["name"], blob, relocs)
    return out


def compare(old_dir, new_dir):
    builder = load_builder()
    report = {}
    for name in OBJECTS:
        old = functions(builder.Elf(Path(old_dir) / name))
        new = functions(builder.Elf(Path(new_dir) / name))
        rows = {}
        for function in sorted(set(old) | set(new)):
            if function not in old:
                rows[function] = {"status": "added", "bytes": len(new[function][1]), "section": new[function][0]}
            elif function not in new:
                rows[function] = {"status": "removed_or_inlined", "bytes": len(old[function][1])}
            else:
                a, b = old[function], new[function]
                same_code = a[1] == b[1]
                same_relocs = a[2] == b[2]
                rows[function] = {"status": "identical" if same_code and same_relocs else
                                  "same_code_other_relocations" if same_code else "changed",
                                  "bytes_old": len(a[1]), "bytes_new": len(b[1]),
                                  "section_old": a[0], "section_new": b[0]}
        report[name] = rows
    return report


if __name__ == "__main__":
    print(json.dumps(compare(sys.argv[1], sys.argv[2]), indent=1))
