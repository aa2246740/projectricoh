#!/usr/bin/env python3
"""Independently audit a frozen image-v3 package. Never import the builder."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys

TASK = Path(__file__).resolve().parent
PROJECT = TASK.parents[1]
PRIVATE = TASK / "local"
POLICY_DIGEST = "1cc1664145b0a3d1bafac553bb418d6cf1b7068a77f2cbba42b40813c9a919fb"
WARNING = "未审查候选，不得上卡"
REFERENCE = PROJECT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8"


class Rejected(ValueError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def check(condition, code, detail):
    if not condition:
        raise Rejected(code, detail)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def unique_object(items):
    obj = {}
    for key, value in items:
        check(key not in obj, "E_JSON", "duplicate key " + key)
        obj[key] = value
    return obj


def decode_json(blob):
    return json.loads(blob, object_pairs_hook=unique_object)


def inside(path, root, code):
    check(path.resolve().is_relative_to(root.resolve()), code, "path escapes " + str(root))
    return path.resolve()


def load_elf(blob, policy):
    """Parse ELF from scratch; return actual allocated bytes and normalized PHs."""
    check(len(blob) >= 52 and blob[:7] == bytes((127, 69, 76, 70, 1, 2, 1)), "E_ELF_HEADER", "ELF32 MSB version 1 required")
    fields = struct.unpack_from(">HHIIIIIHHHHHH", blob, 16)
    et, em, ev, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, names_index = fields
    check((et, em, ev, flags, ehsize, phsize, phnum, shsize, shnum, phoff) == (2, 88, 1, 0, 52, 32, 3, 40, 7, 52), "E_ELF_HEADER", "unexpected ELF header/table shape")
    check(0 <= names_index < shnum and shoff >= 52 and shoff + shnum * 40 <= len(blob), "E_ELF_TABLE", "section table bounds")
    sections = []
    for idx in range(shnum):
        values = struct.unpack_from(">IIIIIIIIII", blob, shoff + idx * 40)
        s = dict(zip(("name_index", "kind", "attrs", "address", "offset", "length", "link", "info", "align", "entry_size"), values))
        s["index"] = idx
        check(s["kind"] == 8 or s["offset"] + s["length"] <= len(blob), "E_ELF_TABLE", "section data bounds")
        check(s["kind"] not in (4, 9) and not s["attrs"] & 0x400, "E_ELF_RELOC", "relocation/TLS sections are forbidden")
        check(s["align"] == 0 or s["align"] & (s["align"] - 1) == 0, "E_ELF_TABLE", "section alignment")
        sections.append(s)
    names_section = sections[names_index]
    check(names_section["kind"] == 3, "E_ELF_TABLE", "missing section-name strings")

    def content(s):
        return blob[s["offset"]:s["offset"] + s["length"]]

    def cstring(table, index):
        check(0 <= index < len(table), "E_ELF_STRING", "invalid string offset")
        end = table.find(bytes((0,)), index)
        check(end >= index, "E_ELF_STRING", "unterminated string")
        return table[index:end].decode("ascii")

    section_names = content(names_section)
    by_name = {}
    for s in sections:
        name = cstring(section_names, s["name_index"])
        check(name not in by_name, "E_ELF_TABLE", "duplicate section name")
        s["name"] = name
        by_name[name] = s
    check(set(by_name) == {"", ".payload", ".root", ".root_pins", ".symtab", ".strtab", ".shstrtab"}, "E_ELF_TABLE", "section inventory differs")
    text, root, pins = (by_name[x] for x in (".payload", ".root", ".root_pins"))
    start, limit, root_va = policy["window_start"], policy["window_end"], policy["root_start"]
    check((text["kind"], text["attrs"], text["address"]) == (1, 6, start), "E_ELF_HEADER", "payload allocation differs")
    check(0 < text["length"] <= root_va - start and text["length"] % 4 == 0, "E_PAYLOAD_RANGE", "payload crosses root/window boundary")
    check((root["kind"], root["attrs"], root["address"], root["length"]) == (8, 3, root_va, 244), "E_ELF_ROOT", "244B NOBITS root differs")
    check((pins["kind"], pins["attrs"], pins["address"], pins["length"]) == (1, 2, limit - 12, 12), "E_ELF_ROOT", "12B initialized pins differ")
    check([s["name"] for s in sections if s["attrs"] & 2] == [".payload", ".root", ".root_pins"], "E_ELF_ROOT", "unexpected allocated section")
    symtab, strings = by_name[".symtab"], by_name[".strtab"]
    check(symtab["kind"] == 2 and strings["kind"] == 3 and symtab["entry_size"] == 16
          and symtab["length"] % 16 == 0 and symtab["link"] == strings["index"], "E_ELF_SYMBOL", "invalid symbol table")
    symbols = {}
    for index, offset in enumerate(range(symtab["offset"], symtab["offset"] + symtab["length"], 16)):
        name_off, value, size, info, other, section = struct.unpack_from(">IIIBBH", blob, offset)
        if index == 0:
            check((name_off, value, size, info, other, section) == (0, 0, 0, 0, 0, 0), "E_ELF_SYMBOL", "invalid null symbol")
        check(not name_off or section not in (0, 0xfff2), "E_ELF_SYMBOL", "undefined or COMMON symbol")
        check(section < shnum or section == 0xfff1, "E_ELF_SYMBOL", "symbol section index")
        if name_off and info // 16 in (1, 2):
            name = cstring(content(strings), name_off)
            check(name not in symbols, "E_ELF_SYMBOL", "duplicate global symbol")
            symbols[name] = dict(value=value, section=section, type=info & 15)
    check("rv_hook_shared" in symbols and symbols["rv_hook_shared"]["value"] == entry
          and start <= entry < start + text["length"], "E_ELF_SYMBOL", "entry does not name resident hook dispatcher")
    norm = bytearray(blob)
    excluded, loads = [], []
    for idx, s in enumerate((text, root, pins)):
        program = struct.unpack_from(">IIIIIIII", blob, phoff + idx * phsize)
        typ, offset, va, pa, file_size, mem_size, attrs, align = program
        check(typ == 1 and va == pa and attrs == (5, 6, 4)[idx] and align in (1, 4)
              and (va - offset) % align == 0, "E_ELF_LOAD", "PT_LOAD type/address/flags/alignment")
        if s is text:
            prefix = s["offset"] - offset
            check(prefix >= 0 and va + prefix == start and file_size == mem_size == prefix + s["length"], "E_ELF_LOAD", "text PT_LOAD coverage differs")
            if prefix:
                check(offset == 0 and prefix == 148 and s["offset"] == phoff + phsize * phnum == 148,
                      "E_ELF_PREFIX", "excluded prefix must contain exactly ELF header and 3 PHs")
                excluded.append(dict(file_offset=0, va=va, bytes=prefix))
            replacement = (1, s["offset"], start, start, s["length"], s["length"], attrs, align)
            struct.pack_into(">IIIIIIII", norm, phoff + idx * phsize, *replacement)
        elif s is root:
            check(va == root_va and file_size == 0 and mem_size == 244, "E_ELF_LOAD", "root must be file-empty NOBITS")
        else:
            check((offset, va, file_size, mem_size) == (s["offset"], s["address"], 12, 12), "E_ELF_LOAD", "pins segment differs")
        loads.append(dict(va=s["address"], file_bytes=0 if s is root else s["length"], memory_bytes=s["length"], flags=attrs))
    expected_window = bytearray([255] * (limit - start))
    for s in (text, pins):
        lo = s["address"] - start
        expected_window[lo:lo + s["length"]] = content(s)
    return dict(window=bytes(expected_window), code=content(text), symbols=symbols, text=text,
                normalized=bytes(norm), excluded=excluded, loads=loads, margin=root_va - start - text["length"])


def container_checksum(blob):
    """Audit using individual weighted bytes, without builder residue sums."""
    weights = itertools.cycle((2, 3, 4, 5, 6, 7))
    return sum(value * weight for value, weight in zip(memoryview(blob)[512:], weights)) & 0xffffffff


def matching_phases(blob):
    target = int.from_bytes(blob[0x16c:0x170], "big")
    totals = [sum(memoryview(blob)[512 + residue::6]) for residue in range(6)]
    return [phase for phase in range(6) if sum(totals[r] * (2 + (phase + r) % 6) for r in range(6)) & 0xffffffff == target]


def parse_container(blob):
    check(len(blob) >= 512 and int.from_bytes(blob[0x164:0x168], "big") == len(blob) - 512
          and int.from_bytes(blob[0x168:0x16c], "big") == len(blob), "E_CONTAINER_LENGTH", "header/file lengths differ")
    result = []
    for index in range(16):
        src, address, size, bss, bss_size = struct.unpack_from(">IIIII", blob, 32 + 20 * index)
        row = dict(index=index, source=src, offset=512 + src, va=address, size=size, bss=bss, bss_size=bss_size)
        check(size > 0 and src + 512 + size <= len(blob) and address + size <= 2**32
              and bss + bss_size <= 2**32, "E_CONTAINER_SEGMENT", "segment extent invalid")
        for old in result:
            check(not (row["offset"] < old["offset"] + old["size"] and old["offset"] < row["offset"] + size), "E_CONTAINER_SEGMENT", "file segment overlap")
            check(not (address < old["va"] + old["size"] and old["va"] < address + size), "E_CONTAINER_SEGMENT", "VA segment overlap")
        result.append(row)
    for a in result:
        for b in result:
            if b["bss_size"]:
                check(not (a["va"] < b["bss"] + b["bss_size"] and b["bss"] < a["va"] + a["size"]), "E_CONTAINER_SEGMENT", "initialized segment overlaps BSS")
            if a["index"] < b["index"] and a["bss_size"] and b["bss_size"]:
                check(not (a["bss"] < b["bss"] + b["bss_size"] and b["bss"] < a["bss"] + a["bss_size"]), "E_CONTAINER_SEGMENT", "BSS overlap")
    return result


def address_offset(rows, address, size):
    matches = [r for r in rows if r["va"] <= address and address + size <= r["va"] + r["size"]]
    check(size > 0 and len(matches) == 1, "E_ADDRESS", "hook/window does not have one initialized segment")
    match = matches.pop()
    return match["offset"] + address - match["va"], match["index"]


def inspect_hooks(original, reference, candidate, rows, hook_source, patch_source, policy, elf):
    records = decode_json(hook_source)
    declared = decode_json(patch_source)
    check(type(records) is list and len(records) == 37 and [h.get("number") for h in records] == list(range(1, 38)), "E_HOOK_INVENTORY", "37 numbered source rows required")
    check(type(declared) is list and len(declared) == 37
          and [m.get("hook") for m in declared] == ["H%02d" % n for n in range(1, 38)],
          "E_PATCH_INVENTORY", "37 ordered patch-manifest rows required")
    evidence, allowed = [], []
    for spec, h, declaration in zip(policy["hooks"], records, declared):
        label = "H%02d" % spec["number"]
        check((h["id"], int(h["va"], 0), h["length"]) == (spec["id"], spec["va"], spec["length"]), "E_HOOK_INVENTORY", label + " id/address/length differs from policy")
        check((int(declaration["address"], 0), declaration["length"]) == (spec["va"], spec["length"]),
              "E_PATCH_INVENTORY", label + " patch address/length differs from policy")
        off, segment = address_offset(rows, spec["va"], spec["length"])
        check(int(h["file_offset"], 0) == off and h["segment"] == segment, "E_HOOK_MAPPING", label + " mapping differs")
        check(type(h.get("enabled")) is bool and h["enabled"] == spec["enabled"], "E_HOOK_INVENTORY", label + " enabled flag differs")
        check(h["kind"] == ("data" if spec["kind"] == "stock_data" else "execution"),
              "E_HOOK_INVENTORY", label + " hook kind differs")
        check(type(declaration.get("enabled")) is bool and declaration["enabled"] == spec["enabled"],
              "E_PATCH_INVENTORY", label + " patch enabled flag differs")
        old, actual = original[off:off + spec["length"]], candidate[off:off + spec["length"]]
        check(bytes.fromhex(h["original_bytes"]) == old and len(old) == spec["length"], "E_HOOK_ORIGINAL", label + " source original bytes differ from official")
        check(bytes.fromhex(declaration["original"]) == old, "E_PATCH_ORIGINAL", label + " patch original differs from official")
        stage2l_word = h.get("existing_stage2l_bytes")
        check(declaration["stage2l_reference"] == stage2l_word
              and (stage2l_word is None or bytes.fromhex(stage2l_word) == reference[off:off + spec["length"]]),
              "E_PATCH_REFERENCE", label + " Stage2l bytes differ")
        check(declaration["constrained_link"] is True and declaration["installable"] is False,
              "E_PATCH_STATUS", label + " patch is not constrained/unreviewed")
        target = None
        if not spec["enabled"]:
            check(actual == old, "E_DISABLED_HOOK", label + " disabled point changed")
        elif spec["kind"] == "stock_data":
            check(actual == old, "E_STOCK_DATA", label + " factory data must remain original")
        else:
            check(spec["va"] % 4 == 0 and len(actual) in (4, 8) and actual[0] == 255, "E_HOOK_OPCODE", label + " expected BRA24")
            displacement = int.from_bytes(actual[1:4], "big", signed=False)
            if displacement >= 0x800000:
                displacement -= 0x1000000
            target = spec["va"] + 4 * displacement
            symbol = elf["symbols"].get(spec["target_symbol"])
            check(symbol is not None and symbol["section"] == elf["text"]["index"]
                  and elf["text"]["address"] <= symbol["value"] <= elf["text"]["address"] + elf["text"]["length"] - 4
                  and symbol["value"] % 4 == 0, "E_ELF_SYMBOL", label + " corresponding symbol is not resident code")
            check(target == symbol["value"], "E_HOOK_TARGET", f"{label} decoded=0x{target:08x}, {spec['target_symbol']}=0x{symbol['value']:08x}")
            check(actual[4:] == bytes((112, 0, 240, 0)) * ((len(actual) - 4) // 4), "E_HOOK_PADDING", label + " displaced tail differs")
            allowed.append((off, off + spec["length"], label))
        for key in ("replacement", "new_bytes"):
            check(key not in h or bytes.fromhex(h[key]) == actual, "E_HOOK_SOURCE", label + " declared replacement differs")
        check(bytes.fromhex(declaration["replacement"]) == actual, "E_PATCH_REPLACEMENT", label + " patch replacement differs from independently checked candidate")
        evidence.append(dict(number=spec["number"], id=spec["id"], va=spec["va"], file_offset=off,
                             segment=segment, length=spec["length"], original=old.hex(), replacement=actual.hex(),
                             enabled=spec["enabled"], kind=spec["kind"], target_symbol=spec["target_symbol"], target=target))
    return evidence, allowed


def unchanged_outside(original, candidate, allowed):
    cursor, changed = 0, []
    for start, end, label in sorted(allowed):
        check(cursor <= start < end <= len(original), "E_ALLOWLIST", "overlapping/out-of-bounds allowed ranges")
        a, b = original[cursor:start], candidate[cursor:start]
        if a != b:
            index = next(i for i, (x, y) in enumerate(zip(a, b)) if x != y)
            raise Rejected("E_OUTSIDE_DIFF", f"undeclared byte change at file offset 0x{cursor + index:x}")
        changed.append(dict(name=label, start=start, end=end, changed_bytes=sum(x != y for x, y in zip(original[start:end], candidate[start:end]))))
        cursor = end
    check(original[cursor:] == candidate[cursor:], "E_OUTSIDE_DIFF", "undeclared trailing byte change")
    return changed


def audit(args):
    package = inside(args.package, PRIVATE, "E_PATH")
    check(package != PRIVATE and package.is_dir(), "E_PATH", "package directory required")
    for path in package.rglob("*"):
        check(not path.is_symlink() and (path.is_file() or path.is_dir()), "E_PATH", "package contains symlink or special file")
    policy_blob = (TASK / "policy.json").read_bytes()
    check(digest(policy_blob) == POLICY_DIGEST, "E_POLICY", "policy digest differs from pinned registry")
    policy = decode_json(policy_blob)
    official_path = inside(args.official, PROJECT, "E_PATH")
    check(official_path.name == "ilaunch3", "E_OFFICIAL", "--official must name ilaunch3")
    official = {n: (official_path.parent / n).read_bytes() for n in policy["official"]}
    check(all(digest(d) == policy["official"][n] for n, d in official.items()), "E_OFFICIAL", "official 29-file digest mismatch")
    source_elf = inside(args.elf, PROJECT, "E_PATH").read_bytes()
    source_hooks = inside(args.hooks, PROJECT, "E_PATH").read_bytes()
    source_patch_manifest = inside(args.patch_manifest, PROJECT, "E_PATH").read_bytes()
    elf = load_elf(source_elf, policy)
    root = package / "candidate/SD_ROOT"
    recovery = package / "recovery-official-1.51/SD_ROOT"
    for path in (root, recovery):
        check(path.is_dir() and {p.name for p in path.iterdir()} == set(official)
              and all(p.is_file() for p in path.iterdir()), "E_FILE_SET", str(path) + " must contain exactly the 29 official component names")
    original = official["ilaunch3"]
    candidate = (root / "ilaunch3").read_bytes()
    check(len(candidate) == len(original), "E_IMAGE_SIZE", "body file size changed")
    check(candidate[:0x16c] == original[:0x16c] and candidate[0x170:512] == original[0x170:512], "E_HEADER", "header changed outside 0x16c..0x170")
    official_rows, rows = parse_container(original), parse_container(candidate)
    check(rows == official_rows, "E_HEADER", "16 segment descriptors changed")
    reference_root = inside(args.stage2l, PROJECT, "E_PATH")
    reference = (reference_root / "candidate/SD_ROOT/ilaunch3").read_bytes()
    check(digest(reference) == policy["stage2l_sha256"] and len(reference) == len(original), "E_REFERENCE", "Stage2l image identity differs")
    check(reference[:0x16c] == candidate[:0x16c] and reference[0x170:512] == candidate[0x170:512]
          and container_checksum(reference) == int.from_bytes(reference[0x16c:0x170], "big"), "E_REFERENCE", "Stage2l header/checksum structural rule differs")
    patches, allowed = inspect_hooks(original, reference, candidate, rows, source_hooks, source_patch_manifest, policy, elf)
    counts = dict(enabled_points=sum(h["enabled"] for h in patches), code_hooks=len(allowed),
                  stock_data_points=sum(h["enabled"] and h["kind"] == "stock_data" for h in patches),
                  disabled_points=sum(not h["enabled"] for h in patches),
                  execution_overwrite_bytes=sum(end - start for start, end, _ in allowed))
    window_start, segment = address_offset(rows, policy["window_start"], len(elf["window"]))
    window_end = window_start + len(elf["window"])
    check(segment == 0 and original[window_start:window_end] == bytes([255]) * len(elf["window"]), "E_WINDOW", "official window is not entirely FF")
    check(candidate[window_start:window_end] == elf["window"], "E_PAYLOAD_BYTES", "window differs from ELF allocated bytes, root NOBITS FF, or FF gap")
    changes = unchanged_outside(original, candidate, allowed + [(window_start, window_end, "payload_window"), (0x16c, 0x170, "container_checksum")])
    stored = int.from_bytes(candidate[0x16c:0x170], "big")
    check(container_checksum(candidate) == stored and matching_phases(candidate) == [0], "E_CHECKSUM", "body weighted checksum invalid or ambiguous")
    component_checks = []
    for name in sorted(official):
        actual = (root / name).read_bytes()
        if name != "ilaunch3":
            check(actual == official[name], "E_OTHER_COMPONENT", name + " changed")
        restored = (recovery / name).read_bytes()
        check(restored == official[name], "E_RECOVERY", name + " recovery bytes differ from official")
        check((reference_root / "recovery-official-1.51/SD_ROOT" / name).read_bytes() == official[name], "E_REFERENCE", name + " Stage2l recovery differs")
        check(len(actual) >= 512 and int.from_bytes(actual[0x164:0x168], "big") == len(actual) - 512
              and int.from_bytes(actual[0x168:0x16c], "big") == len(actual), "E_CONTAINER_LENGTH", name + " length fields invalid")
        expected_phase, actual_phase = matching_phases(official[name]), matching_phases(actual)
        check(len(expected_phase) == 1 and actual_phase == expected_phase, "E_CHECKSUM", name + " component checksum phase/field invalid")
        component_checks.append(dict(file=name, phase=actual_phase[0], stored=int.from_bytes(actual[0x16c:0x170], "big"), sha256=digest(actual), recovery_identical=True))
    ev = package / "evidence"
    check((ev / "resident.source.elf").read_bytes() == source_elf and (ev / "hooks.source.json").read_bytes() == source_hooks
          and (ev / "patch-manifest.source.json").read_bytes() == source_patch_manifest,
          "E_INPUT_SNAPSHOT", "frozen ELF/hooks/patch manifest differ from requested inputs")
    canonical = (ev / "resident.load.elf").read_bytes()
    check(canonical == elf["normalized"], "E_ELF_NORMALIZATION", "normalized ELF differs outside the exact code PT_LOAD descriptor")
    normalized = load_elf(canonical, policy)
    check(not normalized["excluded"] and normalized["window"] == elf["window"], "E_ELF_NORMALIZATION", "normalized ELF still has excluded file-load bytes")
    for idx in range(3):
        typ, off, va, pa, count, mem, attrs, align = struct.unpack_from(">8I", canonical, 52 + idx * 32)
        if count:
            image_off, _ = address_offset(rows, va, count)
            check(candidate[image_off:image_off + count] == canonical[off:off + count], "E_ELF_LOAD_BYTES", "normalized PT_LOAD bytes differ from candidate")
    check((ev / "payload.bin").read_bytes() == elf["code"] and decode_json((ev / "patches.json").read_bytes()) == patches, "E_EVIDENCE", "payload/patch evidence differs from independent parsing")
    manifest = decode_json((package / "manifest.json").read_bytes())
    expected = dict(schema="gxr-image-v3/1", status="UNREVIEWED_DO_NOT_COPY_TO_CARD", notice=WARNING,
                    image_sha256=digest(candidate), image_bytes=len(candidate), official_sha256=digest(original),
                    stage2l_sha256=digest(reference), policy_sha256=POLICY_DIGEST,
                    inputs_sha256={"elf": digest(source_elf), "hooks": digest(source_hooks), "patch_manifest": digest(source_patch_manifest)},
                    normalized_elf_sha256=digest(canonical), payload_sha256=digest(elf["code"]),
                    window_sha256=digest(elf["window"]), code_bytes=len(elf["code"]), root_bytes=256,
                    root_nobits_bytes=244, root_pins_bytes=12, occupied_bytes=len(elf["code"]) + 256,
                    margin_bytes=elf["margin"], elf_metadata_prefixes=elf["excluded"], elf_loads=elf["loads"],
                    **counts,
                    candidate_files=29, official_recovery_files=29,
                    candidate_sha256={n: digest((root / n).read_bytes()) for n in official}, recovery_sha256=policy["official"],
                    checksum=dict(field=0x16c, phase=0, method="sum(payload[i] * (i % 6 + 2)) mod 2^32",
                                  segment_checksum_fields=False, other_header_bytes="identical to official and Stage2l"),
                    camera_executed=False, sd_accessed=False,
                    tool_sha256={n: digest((TASK / n).read_bytes()) for n in ("build.py", "audit.py", "policy.json")})
    check(manifest == expected, "E_MANIFEST", "manifest does not match independently observed package")
    check(WARNING in (package / "README.txt").read_text(encoding="utf-8") and WARNING in (package / "candidate/README.txt").read_text(encoding="utf-8"), "E_NOTICE", "unreviewed/card prohibition missing")
    actual_paths = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file() and p != package / "SHA256SUMS"}
    expected_paths = {"README.txt", "manifest.json", "candidate/README.txt"}
    expected_paths.update(directory + "/SD_ROOT/" + n for directory in ("candidate", "recovery-official-1.51") for n in official)
    expected_paths.update("evidence/" + n for n in ("resident.source.elf", "resident.load.elf", "hooks.source.json", "patch-manifest.source.json", "payload.bin", "patches.json"))
    check(actual_paths == expected_paths, "E_FILE_SET", "unexpected/missing package evidence file")
    listed = {}
    for line in (package / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        checksum, separator, name = line.partition("  ")
        check(separator and name in actual_paths and name not in listed and len(checksum) == 64, "E_SUMS", "invalid/duplicate/unexpected SHA256SUMS entry")
        listed[name] = checksum
    check(set(listed) == actual_paths and all(digest((package / n).read_bytes()) == h for n, h in listed.items()), "E_SUMS", "SHA256SUMS mismatch or incomplete inventory")
    contributions = []
    for r in rows:
        part = memoryview(candidate)[r["offset"]:r["offset"] + r["size"]]
        cycle = itertools.cycle(tuple(2 + (r["source"] + i) % 6 for i in range(6)))
        amount = sum(x * weight for x, weight in zip(part, cycle)) & 0xffffffff
        contributions.append(dict(**r, weighted_contribution=amount))
    segment_total = sum(r["weighted_contribution"] for r in contributions) & 0xffffffff
    coverage = sum(r["size"] for r in rows)
    gaps_total, cursor = 0, 512
    for r in sorted(rows, key=lambda x: x["offset"]):
        part = candidate[cursor:r["offset"]]
        cycle = itertools.cycle(tuple(2 + (cursor - 512 + i) % 6 for i in range(6)))
        gaps_total += sum(x * w for x, w in zip(part, cycle))
        cursor = r["offset"] + r["size"]
    gaps_total += sum(x * w for x, w in zip(candidate[cursor:], itertools.cycle(tuple(2 + (cursor - 512 + i) % 6 for i in range(6)))))
    check((segment_total + gaps_total) & 0xffffffff == stored, "E_SEGMENT_SUM", "segment and gap contributions do not reconstruct container checksum")
    return dict(status="AUDIT_PASS_UNREVIEWED", notice=WARNING, image_sha256=digest(candidate),
                official_sha256=digest(original), stage2l_sha256=digest(reference),
                source_elf_sha256=digest(source_elf), hooks_sha256=digest(source_hooks),
                patch_manifest_sha256=digest(source_patch_manifest),
                normalized_elf_sha256=digest(canonical), code_bytes=len(elf["code"]), root_bytes=256,
                margin_bytes=elf["margin"], elf_metadata_prefixes=elf["excluded"],
                normalized_file_load_bytes=len(elf["code"]) + 12, root_nobits_preserved_ff_bytes=244,
                **counts,
                unexpected_changed_bytes=0, changes=changes, hooks=patches,
                checksum=dict(stored=stored, phase=0, segment_checksum_fields=False,
                              segments=contributions, segment_bytes=coverage,
                              gaps_bytes=len(candidate) - 512 - coverage, gaps_weighted=gaps_total & 0xffffffff),
                components=component_checks, recovery_identical_files=29, package_sums_files=len(listed),
                audit_tool_sha256=digest(Path(__file__).read_bytes()), camera_executed=False, sd_accessed=False)


def report_path(path):
    destination = inside(path, PRIVATE, "E_PATH")
    check(not PRIVATE.is_symlink() and PRIVATE.resolve() == PRIVATE, "E_PATH", "private directory is a symlink")
    info = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
    check(info.get("MountPoint") == "/Volumes/Workspace" and info.get("FilesystemType") == "apfs"
          and info.get("VolumeUUID") == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
          and info.get("WritableVolume") and info.get("WritableMedia") and os.access(PRIVATE, os.W_OK), "E_VOLUME", "workspace preflight failed")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--official", required=True, type=Path)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--hooks", required=True, type=Path)
    parser.add_argument("--patch-manifest", required=True, type=Path)
    parser.add_argument("--stage2l", default=REFERENCE, type=Path)
    parser.add_argument("--report", type=Path, help="JSON output under image_v3/local, outside package")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    try:
        destination = report_path(args.report) if args.report else None
        check(destination is None or not destination.is_relative_to(args.package.resolve()), "E_PATH", "audit report must be outside sealed package")
        result = audit(args)
    except (Rejected, ValueError, OSError, KeyError, TypeError, struct.error) as error:
        code = error.code if isinstance(error, Rejected) else "E_INPUT"
        result = dict(status="AUDIT_REJECT", code=code, error=str(error))
        print(f"AUDIT_REJECT {code}: {error}", file=sys.stderr)
        if args.report:
            try:
                dest = report_path(args.report)
                if not dest.is_relative_to(args.package.resolve()):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except (ValueError, OSError, subprocess.SubprocessError):
                pass
        return 1
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("AUDIT_PASS_UNREVIEWED " + WARNING)
    print("IMAGE_SHA256=" + result["image_sha256"])
    print("OFFICIAL_SHA256=" + result["official_sha256"])
    print("STAGE2L_SHA256=" + result["stage2l_sha256"])
    print("INPUT_ELF_SHA256=" + result["source_elf_sha256"] + " HOOKS_SHA256=" + result["hooks_sha256"])
    print("PATCH_MANIFEST_SHA256=" + result["patch_manifest_sha256"])
    print(f"PAYLOAD_PASS code={result['code_bytes']} root=256 margin={result['margin_bytes']} normalized_PT_LOAD_bytes={result['normalized_file_load_bytes']}")
    print("ELF_METADATA_PREFIX_EXCLUDED=" + str(sum(x["bytes"] for x in result["elf_metadata_prefixes"])) + " root_NOBITS_FF=244")
    print(f"HOOKS_PASS enabled={result['enabled_points']} BRA24={result['code_hooks']} stock_data_unchanged={result['stock_data_points']} disabled_unchanged={result['disabled_points']} execution_overwrite_bytes={result['execution_overwrite_bytes']}")
    print(f"OUTSIDE_DIFF_PASS unexpected=0 allowed=window+{result['code_hooks']}_code_points+checksum_0x16c_0x170")
    print(f"CONTAINER_PASS checksum=0x{result['checksum']['stored']:08x} phase=0 segments=16 components=29 header_other_changes=0")
    print("RECOVERY_PASS identical_official_files=29")
    print(f"PACKAGE_SUMS_PASS files={result['package_sums_files']} camera_executed=false sd_accessed=false")
    if args.verbose:
        for h in result["hooks"]:
            status = "DISABLED_ORIGINAL" if not h["enabled"] else "STOCK_DATA_ORIGINAL" if h["kind"] == "stock_data" else f"BRA24->{h['target_symbol']}@0x{h['target']:08x}"
            print(f"HOOK H{h['number']:02} va=0x{h['va']:08x} offset=0x{h['file_offset']:x} {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
