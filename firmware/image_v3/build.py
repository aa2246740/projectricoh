#!/usr/bin/env python3
"""Build a deterministic, unreviewed GXR body package inside image_v3/local."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
POLICY_SHA = "1cc1664145b0a3d1bafac553bb418d6cf1b7068a77f2cbba42b40813c9a919fb"
NOTICE = "未审查候选，不得上卡"
STAGE = ROOT / "artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def json_read(data):
    return json.loads(data, object_pairs_hook=pairs)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preflight(output):
    info = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
    need(info.get("MountPoint") == "/Volumes/Workspace" and info.get("FilesystemType") == "apfs"
         and info.get("VolumeUUID") == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
         and info.get("WritableVolume") and info.get("WritableMedia"), "workspace volume identity/writability mismatch")
    need(HERE == ROOT / "firmware/image_v3" and os.access(HERE, os.W_OK), "wrong task checkout")
    need(not LOCAL.is_symlink() and LOCAL.resolve() == LOCAL, "local must not be a symlink")
    need(output.is_relative_to(LOCAL) and output != LOCAL and not output.exists(), "output must be a new directory under image_v3/local")
    ignored = subprocess.check_output(["git", "check-ignore", "-v", str(output / "check")], cwd=ROOT, text=True)
    need("firmware/image_v3/.gitignore:1:/local/" in ignored, "local is not ignored by the task .gitignore")


def read_input(path):
    need(path.is_relative_to(ROOT), "input must be inside this checkout")
    return path.read_bytes()


def weighted(payload, phase=0):
    return sum(sum(payload[r::6]) * ((r + phase) % 6 + 2) for r in range(6)) & 0xffffffff


def phases(data):
    stored = struct.unpack_from(">I", data, 0x16c)[0]
    return [p for p in range(6) if weighted(data[512:], p) == stored]


def segments(body):
    need(struct.unpack_from(">II", body, 0x164) == (len(body) - 512, len(body)), "container length mismatch")
    need(phases(body) == [0], "body must have unique checksum phase 0")
    rows = []
    for i in range(16):
        src, va, size, bss, bsize = struct.unpack_from(">5I", body, 0x20 + i * 20)
        need(size > 0 and src + 512 + size <= len(body), "container segment outside file")
        need(va + size <= 2**32 and bss + bsize <= 2**32, "container address overflow")
        row = dict(index=i, source=src, offset=src + 512, va=va, size=size, bss=bss, bss_size=bsize)
        for prior in rows:
            need(not (row["offset"] < prior["offset"] + prior["size"] and prior["offset"] < row["offset"] + size), "overlapping container file segments")
            need(not (va < prior["va"] + prior["size"] and prior["va"] < va + size), "overlapping container VA segments")
        rows.append(row)
    return rows


def mapped(rows, va, length):
    found = [r for r in rows if r["va"] <= va and va + length <= r["va"] + r["size"]]
    need(length > 0 and len(found) == 1, "VA does not map uniquely into an initialized container segment")
    row = found[0]
    return row["offset"] + va - row["va"], row["index"]


def elf_input(data, policy):
    need(data[:7] == b"\x7fELF\x01\x02\x01" and len(data) >= 52, "ELF32 big-endian required")
    kind, machine, ver, entry, po, so, flags, eh, pe, pn, se, sn, ni = struct.unpack_from(">HHIIIIIHHHHHH", data, 16)
    need((kind, machine, ver, eh, pe, se) == (2, 88, 1, 52, 32, 40) and flags == 0, "unsupported final M32R ELF")
    need(pn == 3 and po == 52 and sn == 7 and ni < sn and so >= 52 and so + sn * se <= len(data), "unexpected ELF tables")
    raw_sections = [struct.unpack_from(">10I", data, so + i * se) for i in range(sn)]
    table = raw_sections[ni]
    need(table[1] == 3 and table[4] + table[5] <= len(data), "invalid ELF section names")
    names = data[table[4]:table[4] + table[5]]

    def string(blob, index):
        need(0 <= index < len(blob) and b"\0" in blob[index:], "invalid ELF string")
        return blob[index:blob.index(0, index)].decode("ascii")

    sections = {}
    for i, row in enumerate(raw_sections):
        n, typ, attrs, va, off, size, link, info, align, ent = row
        name = string(names, n)
        need(name not in sections and typ not in (4, 9) and not attrs & 0x400, "duplicate, TLS or relocation section")
        need(align == 0 or align & (align - 1) == 0, "invalid ELF alignment")
        need(typ == 8 or off + size <= len(data), "ELF section exceeds file")
        sections[name] = dict(index=i, type=typ, flags=attrs, va=va, offset=off, size=size, link=link, entsize=ent)
    need(set(sections) == {"", ".payload", ".root", ".root_pins", ".symtab", ".strtab", ".shstrtab"}, "unexpected ELF section inventory")
    code, bss, pins = (sections[n] for n in (".payload", ".root", ".root_pins"))
    base, root, end = (policy[k] for k in ("window_start", "root_start", "window_end"))
    need((code["type"], code["flags"], code["va"]) == (1, 6, base)
         and code["size"] > 0 and code["size"] % 4 == 0 and base + code["size"] <= root, "E_PAYLOAD_RANGE: payload exceeds code window")
    need((bss["type"], bss["flags"], bss["va"], bss["size"]) == (8, 3, root, 244), "unexpected root NOBITS")
    need((pins["type"], pins["flags"], pins["va"], pins["size"]) == (1, 2, end - 12, 12), "unexpected root pins")
    need({s["index"] for s in sections.values() if s["flags"] & 2} == {code["index"], bss["index"], pins["index"]}, "unexpected allocated section")
    normalized = bytearray(data)
    load_rows, prefixes = [], []
    for i, sec in enumerate((code, bss, pins)):
        typ, off, va, pa, fs, ms, attrs, align = struct.unpack_from(">8I", data, po + i * pe)
        need(typ == 1 and va == pa and attrs == (5, 6, 4)[i], "unexpected ELF program segment")
        need(align in (1, 4) and (va - off) % align == 0, "unaligned ELF load segment")
        if i == 0:
            prefix = sec["offset"] - off
            need(prefix >= 0 and va + prefix == base and fs == ms == prefix + sec["size"], "code PT_LOAD does not cover exact payload")
            if prefix:
                need(off == 0 and prefix == po + pe * pn == sec["offset"] and prefix == 148, "only the complete 148B ELF header prefix may be excluded")
                prefixes.append(dict(file_offset=0, va=va, bytes=prefix))
            struct.pack_into(">8I", normalized, po, 1, sec["offset"], base, base, sec["size"], sec["size"], attrs, align)
        elif i == 1:
            need(va == root and fs == 0 and ms == 244, "root load must have no initialized bytes")
        else:
            need((off, va, fs, ms) == (sec["offset"], sec["va"], 12, 12), "pins PT_LOAD mismatch")
        load_rows.append(dict(va=sec["va"], file_bytes=0 if i == 1 else sec["size"], memory_bytes=sec["size"], flags=attrs))
    symtab = sections[".symtab"]
    need(symtab["type"] == 2 and symtab["entsize"] == 16 and symtab["size"] % 16 == 0 and symtab["link"] == sections[".strtab"]["index"], "invalid symbol table")
    ss = sections[".strtab"]
    st = data[ss["offset"]:ss["offset"] + ss["size"]]
    symbols = {}
    for pos in range(symtab["offset"], symtab["offset"] + symtab["size"], 16):
        n, value, size, info, other, si = struct.unpack_from(">IIIBBH", data, pos)
        need(not n or si not in (0, 0xfff2), "undefined or COMMON ELF symbol")
        need(si < sn or si == 0xfff1, "invalid symbol section")
        if n and info >> 4 in (1, 2):
            name = string(st, n)
            need(name not in symbols, "duplicate global ELF symbol")
            symbols[name] = dict(value=value, section=si, type=info & 15)
    need("rv_hook_shared" in symbols and entry == symbols["rv_hook_shared"]["value"] and base <= entry < base + code["size"], "ELF entry mismatch")
    for h in policy["hooks"]:
        if not h["enabled"] or h["kind"] != "BRA24":
            continue
        symbol = symbols.get(h["target_symbol"])
        need(symbol is not None and symbol["section"] == code["index"] and symbol["value"] % 4 == 0
             and base <= symbol["value"] <= base + code["size"] - 4, "hook symbol is not inside resident code")
    window = bytearray(b"\xff" * (end - base))
    for sec in (code, pins):
        window[sec["va"] - base:sec["va"] - base + sec["size"]] = data[sec["offset"]:sec["offset"] + sec["size"]]
    return dict(window=bytes(window), code=data[code["offset"]:code["offset"] + code["size"]],
                normalized=bytes(normalized), symbols=symbols, loads=load_rows, prefixes=prefixes,
                code_bytes=code["size"], margin=root - base - code["size"])


def hook_patches(body, reference, rows, source, patch_source, policy, elf):
    hooks = json_read(source)
    manifest = json_read(patch_source)
    need(isinstance(hooks, list) and len(hooks) == 37, "hooks must contain all 37 source records")
    need([h.get("number") for h in hooks] == list(range(1, 38)), "hook order/numbers changed")
    need(isinstance(manifest, list) and len(manifest) == 37
         and [m.get("hook") for m in manifest] == [f"H{n:02}" for n in range(1, 38)],
         "patch manifest must contain all 37 ordered source records")
    patches = []
    for h, m, p in zip(hooks, manifest, policy["hooks"]):
        need(h["id"] == p["id"] and int(h["va"], 0) == p["va"] and h["length"] == p["length"], "hook inventory differs from pinned policy")
        need(int(m["address"], 0) == p["va"] and m["length"] == p["length"], "patch manifest address/length differs from policy")
        off, segment = mapped(rows, p["va"], p["length"])
        old = bytes.fromhex(h["original_bytes"])
        need(int(h["file_offset"], 0) == off and h["segment"] == segment and len(old) == p["length"]
             and body[off:off + len(old)] == old, "hook original bytes/mapping mismatch")
        need(type(h.get("enabled")) is bool and h["enabled"] == p["enabled"]
             and type(m.get("enabled")) is bool and m["enabled"] == p["enabled"], "enabled state differs from v3 policy")
        need(h["kind"] == ("data" if p["kind"] == "stock_data" else "execution"), "hook kind differs from v3 policy")
        need(bytes.fromhex(m["original"]) == old, "patch manifest original differs from official")
        prior = h.get("existing_stage2l_bytes")
        need(m["stage2l_reference"] == prior and (prior is None or bytes.fromhex(prior) == reference[off:off + len(old)]),
             "patch manifest Stage2l reference mismatch")
        need(m["constrained_link"] is True and m["installable"] is False, "patch manifest is not constrained/unreviewed")
        new, target = old, None
        if p["enabled"] and p["kind"] == "BRA24":
            target = elf["symbols"][p["target_symbol"]]["value"]
            delta = target - p["va"]
            need(p["va"] % 4 == 0 and delta % 4 == 0 and -(1 << 25) <= delta < (1 << 25), "BRA24 target out of range")
            new = struct.pack(">I", 0xff000000 | ((delta // 4) & 0xffffff)) + b"\x70\x00\xf0\x00" * (p["length"] // 4 - 1)
        for key in ("replacement", "new_bytes"):
            need(key not in h or bytes.fromhex(h[key]) == new, "explicit replacement differs from ELF/policy")
        need(bytes.fromhex(m["replacement"]) == new, "patch manifest replacement differs from ELF/policy")
        patches.append(dict(number=p["number"], id=p["id"], va=p["va"], file_offset=off, segment=segment,
                            length=len(old), original=old.hex(), replacement=new.hex(), enabled=p["enabled"],
                            kind=p["kind"], target_symbol=p["target_symbol"], target=target))
    return patches


def package(args):
    output = args.output.resolve()
    preflight(output)
    policy_bytes = (HERE / "policy.json").read_bytes()
    need(sha(policy_bytes) == POLICY_SHA, "policy hash mismatch")
    policy = json_read(policy_bytes)
    official = {name: read_input(args.official.resolve().parent / name) for name in policy["official"]}
    need(args.official.name == "ilaunch3" and all(sha(data) == policy["official"][name] for name, data in official.items()), "official 29-file identity mismatch")
    body = official["ilaunch3"]
    stage = args.stage2l.resolve()
    reference = read_input(stage / "candidate/SD_ROOT/ilaunch3")
    need(sha(reference) == policy["stage2l_sha256"] and len(reference) == len(body), "Stage2l reference identity mismatch")
    need(reference[:0x16c] == body[:0x16c] and reference[0x170:512] == body[0x170:512]
         and phases(reference) == [0], "Stage2l header/checksum rule mismatch")
    need(all(read_input(stage / "recovery-official-1.51/SD_ROOT" / n) == d for n, d in official.items()), "Stage2l recovery differs from official")
    rows = segments(body)
    source_elf = read_input(args.elf.resolve())
    source_hooks = read_input(args.hooks.resolve())
    source_patch_manifest = read_input(args.patch_manifest.resolve())
    elf = elf_input(source_elf, policy)
    patches = hook_patches(body, reference, rows, source_hooks, source_patch_manifest, policy, elf)
    hook_counts = dict(enabled_points=sum(p["enabled"] for p in patches),
                       code_hooks=sum(p["enabled"] and p["kind"] == "BRA24" for p in patches),
                       stock_data_points=sum(p["enabled"] and p["kind"] == "stock_data" for p in patches),
                       disabled_points=sum(not p["enabled"] for p in patches),
                       execution_overwrite_bytes=sum(p["length"] for p in patches if p["enabled"] and p["kind"] == "BRA24"))
    start, seg = mapped(rows, policy["window_start"], len(elf["window"]))
    need(seg == 0 and body[start:start + len(elf["window"])] == b"\xff" * len(elf["window"]), "official payload window is not entirely FF")
    candidate = bytearray(body)
    candidate[start:start + len(elf["window"])] = elf["window"]
    for p in patches:
        if p["enabled"] and p["kind"] == "BRA24":
            off = p["file_offset"]
            need(not (off < start + len(elf["window"]) and start < off + p["length"]), "hook overlaps payload")
            candidate[off:off + p["length"]] = bytes.fromhex(p["replacement"])
    struct.pack_into(">I", candidate, 0x16c, weighted(candidate[512:]))
    need(phases(candidate) == [0], "candidate checksum did not verify")
    outputs = dict(official, ilaunch3=bytes(candidate))
    manifest = dict(schema="gxr-image-v3/1", status="UNREVIEWED_DO_NOT_COPY_TO_CARD", notice=NOTICE,
                    image_sha256=sha(candidate), image_bytes=len(candidate), official_sha256=policy["body_sha256"],
                    stage2l_sha256=policy["stage2l_sha256"], policy_sha256=POLICY_SHA,
                    inputs_sha256={"elf": sha(source_elf), "hooks": sha(source_hooks), "patch_manifest": sha(source_patch_manifest)},
                    normalized_elf_sha256=sha(elf["normalized"]), payload_sha256=sha(elf["code"]),
                    window_sha256=sha(elf["window"]), code_bytes=elf["code_bytes"], root_bytes=256,
                    root_nobits_bytes=244, root_pins_bytes=12, occupied_bytes=elf["code_bytes"] + 256,
                    margin_bytes=elf["margin"], elf_metadata_prefixes=elf["prefixes"], elf_loads=elf["loads"],
                    **hook_counts,
                    candidate_files=29, official_recovery_files=29,
                    candidate_sha256={n: sha(d) for n, d in outputs.items()}, recovery_sha256=policy["official"],
                    checksum=dict(field=0x16c, phase=0, method="sum(payload[i] * (i % 6 + 2)) mod 2^32",
                                  segment_checksum_fields=False, other_header_bytes="identical to official and Stage2l"),
                    camera_executed=False, sd_accessed=False,
                    tool_sha256={n: sha((HERE / n).read_bytes()) for n in ("build.py", "audit.py", "policy.json")})
    output.mkdir(parents=True)
    for directory, files in (("candidate", outputs), ("recovery-official-1.51", official)):
        dest = output / directory / "SD_ROOT"
        dest.mkdir(parents=True)
        for n, d in sorted(files.items()):
            (dest / n).write_bytes(d)
    (output / "candidate/README.txt").write_text(NOTICE + "\nilaunch3 SHA-256: " + sha(candidate) + "\n", encoding="utf-8")
    evidence = output / "evidence"
    evidence.mkdir()
    for name, data in (("resident.source.elf", source_elf), ("resident.load.elf", elf["normalized"]),
                       ("hooks.source.json", source_hooks), ("patch-manifest.source.json", source_patch_manifest),
                       ("payload.bin", elf["code"])):
        (evidence / name).write_bytes(data)
    save_json(evidence / "patches.json", patches)
    save_json(output / "manifest.json", manifest)
    (output / "README.txt").write_text(
        NOTICE + "\n机身 SHA-256: " + sha(candidate) + "\n"
        "candidate/SD_ROOT：29 个更新组件，仅 ilaunch3 改写。未附旧 Stage2l 的 6 个表文件。\n"
        "recovery-official-1.51/SD_ROOT：29 个逐字节不变的官方 1.51 文件。\n"
        "ELF 文件头前缀不写入机身；evidence/resident.load.elf 的所有文件加载字节均写入窗口。\n"
        "244 B root NOBITS 与代码后空隙保持官方 FF；12 B root pins 取自 ELF。\n"
        "头部只更新 0x16c 的全 payload 加权校验；16 个描述符没有独立段校验字段。\n"
        "这是离线打包结果。审计通过不代表实机运行、安全刷机或任意故障可恢复。\n"
        "最终人工核对见 firmware/image_v3/COORDINATOR.md。\n", encoding="utf-8")
    sums = "".join(f"{sha(p.read_bytes())}  {p.relative_to(output).as_posix()}\n"
                   for p in sorted(output.rglob("*")) if p.is_file())
    (output / "SHA256SUMS").write_text(sums, encoding="ascii")
    print("BUILD_PASS " + NOTICE)
    print("IMAGE_SHA256=" + sha(candidate))
    print(f"PAYLOAD code={elf['code_bytes']} root=256 occupied={elf['code_bytes'] + 256} margin={elf['margin']}")
    print("PACKAGE=" + str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official", type=Path, required=True, help="official ilaunch3; its 28 siblings are also required")
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--hooks", type=Path, required=True)
    parser.add_argument("--patch-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage2l", type=Path, default=STAGE)
    args = parser.parse_args()
    try:
        package(args)
    except (ValueError, OSError, KeyError, TypeError, struct.error) as error:
        print("BUILD_REJECT " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
