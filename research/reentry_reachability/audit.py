"""Offline, bounded M32R reference study. Run with /usr/bin/python3 -I -B."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import plistlib
import re
import struct
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LOCAL = OUT / "local"
TOOL = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
IMAGES = {
    "official": ("artifacts/firmware/gxr-1.51/ilaunch3", "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"),
    "v36": ("firmware/image_v36/local/package/SD_ROOT/ilaunch3", "50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008"),
}
LINE = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} ){1,7}[0-9a-f]{2})\s+(.+)$")


def guard(event, args):
    paths = []
    if event == "open":
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and (
            isinstance(mode, str) and any(c in mode for c in "wax+") or
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            paths.append(path)
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime", "os.truncate"):
        paths.append(args[0])
    elif event in ("os.rename", "os.link", "os.symlink"):
        paths.extend(args[:2])
    elif event.startswith("socket."):
        raise PermissionError("NETWORK_DISABLED")
    for path in paths:
        if not Path(os.fsdecode(path)).resolve().is_relative_to(OUT):
            raise PermissionError("WRITE_OUTSIDE_RESEARCH: " + os.fsdecode(path))


sys.addaudithook(guard)


def save(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight():
    assert ROOT == Path("/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh")
    info = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Workspace"]))
    assert info["VolumeUUID"] == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8"
    assert info["MountPoint"] == "/Volumes/Workspace" and info["FilesystemType"] == "apfs"
    assert info["WritableVolume"] and info["WritableMedia"]
    LOCAL.mkdir(exist_ok=True)
    with (OUT / "commands.jsonl").open("a") as stream:
        stream.write(json.dumps({"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "argv": ["/usr/bin/python3", "-I", "-B", *sys.argv], "cwd": str(Path.cwd())}) + "\n")


def image(name):
    rel, expected = IMAGES[name]
    raw = (ROOT / rel).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    sections = []
    for i in range(16):
        src, va, size, bss, bs = struct.unpack_from(">5I", raw, 0x20 + 20 * i)
        assert src + 512 + size <= len(raw)
        sections.append(dict(index=i, file=src+512, va=va, end=va+size, size=size, bss=bss, bss_size=bs))
    return raw, sections


def at(raw, sections, address, size):
    for section in sections:
        if section["va"] <= address and address + size <= section["end"]:
            offset = section["file"] + address - section["va"]
            return raw[offset:offset+size]
    raise ValueError("unmapped address " + hex(address))


def address_of(sections, offset):
    for section in sections:
        if section["file"] <= offset < section["file"] + section["size"]:
            return section["va"] + offset - section["file"]
    return None


def operations(text):
    result = []
    for line in text.splitlines():
        match = LINE.match(line)
        if match:
            pc = int(match[1], 16)
            code = bytes.fromhex(match[2])
            for index, op in enumerate(re.split(r"\s*(?:->|\|\|)\s*", match[3].strip())):
                result.append((pc + 2 * index, op, pc, code))
    return result


def decode(raw, sections, lo, hi, stem):
    data = at(raw, sections, lo, hi-lo)
    path = LOCAL / (stem + ".bin")
    path.write_bytes(data)
    cmd = [str(TOOL), "-D", "-z", "-b", "binary", "-m", "m32r", "-EB", f"--adjust-vma={lo:#x}", str(path)]
    listing = subprocess.check_output(cmd, text=True)
    (LOCAL / (stem + ".asm")).write_text(listing)
    checked = 0
    for line in listing.splitlines():
        match = LINE.match(line)
        if match:
            pc, code = int(match[1], 16), bytes.fromhex(match[2])
            assert at(raw, sections, pc, len(code)) == code
            checked += len(code)
    assert checked == len(data) - len(data) % 4, (stem, checked, len(data))
    return operations(listing), checked


def number(text):
    return int(text.removeprefix("#"), 0)


def index_ops(ops):
    constants, calls, branches, indirect = [], [], [], []
    regs = {}
    previous = -8
    for pc, op, packet, code in ops:
        if pc - previous > 4:
            regs.clear()
        previous = pc
        if match := re.fullmatch(r"(b\w*)\s+(?:[^ ]*,)?(0x[0-9a-f]+|[0-9a-f]+)", op):
            branches.append(dict(source=pc, target=int(match[2], 16), kind=match[1]))
        if match := re.fullmatch(r"(jl|jmp) (r\d+|lr|fp|sp)", op):
            row = dict(source=pc, kind=match[1], register=match[2])
            if match[2] in regs:
                value, origin = regs[match[2]]
                row.update(target=value & ~3, origin=origin)
                calls.append(row)
            elif match[2] != "lr":
                indirect.append(row)
            regs.clear()
            continue
        match = re.fullmatch(r"seth (r\d+|lr|fp),#(0x[0-9a-f]+|\d+)", op)
        if match:
            regs[match[1]] = (number(match[2]) << 16, pc)
            continue
        match = re.fullmatch(r"(ld24|ldi) (r\d+|lr|fp),#?(0x[0-9a-f]+|-?\d+)", op)
        if match:
            value = number(match[3]) & 0xffffffff
            regs[match[2]] = (value, pc)
            constants.append(dict(source=pc, value=value, origin=pc, register=match[2]))
            continue
        match = re.fullmatch(r"(or3|add3|and3) (r\d+|lr|fp),(r\d+|lr|fp),#(0x[0-9a-f]+|-?\d+)", op)
        if match:
            kind, dest, src, imm = match.groups()
            if src in regs:
                old, origin = regs[src]
                n = number(imm)
                if kind == "or3": value = old | n
                elif kind == "and3": value = old & n
                else: value = old + (n-65536 if 32768 <= n <= 65535 else n)
                value &= 0xffffffff
                regs[dest] = (value, origin)
                constants.append(dict(source=pc, value=value, origin=origin, register=dest))
            else:
                regs.pop(dest, None)
            continue
        match = re.fullmatch(r"mv (r\d+|lr|fp),(r\d+|lr|fp)", op)
        if match:
            if match[2] in regs: regs[match[1]] = regs[match[2]]
            else: regs.pop(match[1], None)
            continue
        if match := re.match(r"(?:ld\w*|pop|add\w*|sub\w*|mvfc|sll\w*|srl\w*|and\w*|or\w*|xor\w*|not|neg|mul\w*) (r\d+|lr|fp)\b", op):
            regs.pop(match[1], None)
        if op.startswith(("bra ", "bra.s ", "bra.l ", "bl ", "bl.s ", "bl.l ", "trap ", "rte")):
            regs.clear()
    return dict(constants=constants, calls=calls, branches=branches, unresolved_register_calls=indirect)


def inventory():
    paths = {TOOL, ROOT / "research/firmware/ilaunch3-sections.csv"}
    paths.update(ROOT / rel for rel, _ in IMAGES.values())
    for tree in ("firmware/resident_v36/resident", "firmware/engine_v46_ui/candidate/engine_services",
                 "firmware/engine_v45_verify/candidate/engine_services", "firmware/engine_diag_v1/candidate/engine_services"):
        paths.update(p for p in (ROOT / tree).rglob("*") if p.is_file() and p.suffix in (".c", ".h", ".S", ".py", ".ld"))
    for rel in ("research/review_g122/REVIEW.md", "research/review_g123/REVIEW.md", "research/review_g124/REVIEW.md",
                "research/review_diag/REVIEW.md", "research/emulator_m2/REPORT.md", "tools/gxr_emulator/observe.py",
                "tools/native_harness/python_backend.py", "tools/native_harness/backend_api.py", "tools/native_harness/image_loader.py"):
        paths.add(ROOT / rel)
    rows = [{"path": str(p.relative_to(ROOT)), "size": p.stat().st_size, "sha256": digest(p)} for p in sorted(paths)]
    save("inputs-before.json", rows)
    print(json.dumps({"inputs": len(rows), "tool": subprocess.check_output([str(TOOL), "--version"], text=True).splitlines()[0]}))


def collect(name):
    raw, sections = image(name)
    full = dict(constants=[], calls=[], branches=[], unresolved_register_calls=[])
    checked = 0
    op_count = 0
    for section in sections:
        if not section["size"]: continue
        ops, count = decode(raw, sections, section["va"], section["end"], f"{name}-s{section['index']:02d}")
        part = index_ops(ops)
        for key in full: full[key].extend(part[key])
        checked += count
        op_count += len(ops)
    save("local/" + name + "-index.json", full)
    save("local/" + name + "-sections.json", sections)
    result = dict(image=name, sha256=hashlib.sha256(raw).hexdigest(), mapped_bytes=sum(s["size"] for s in sections),
                  checked_bytes=checked, decoded_items=op_count, counts={key: len(value) for key, value in full.items()},
                  limitation="Linear disassembly includes data; constant tracking is bounded and does not close dynamic calls.")
    save("local/" + name + "-decode-summary.json", result)
    print(json.dumps(result))


def references(name, values):
    raw, sections = image(name)
    full = json.loads((LOCAL / (name + "-index.json")).read_text())
    rows = []
    for value in values:
        pointers = []
        for variant in range(value, value+4):
            token = variant.to_bytes(4, "big")
            pos = raw.find(token)
            while pos >= 0:
                pointers.append(dict(file_offset=pos, address=address_of(sections, pos), value=variant, aligned=pos % 4 == 0))
                pos = raw.find(token, pos+1)
        row = dict(target=value, pointers=pointers,
                   constants=[r for r in full["constants"] if value <= r["value"] < value+4],
                   calls=[r for r in full["calls"] if r["target"] == value],
                   branches=[r for r in full["branches"] if r["target"] == value])
        rows.append(row)
    save("local/refs-" + name + "-" + "-".join(f"{v:08x}" for v in values) + ".json", rows)
    for row in rows:
        print(json.dumps(dict(target=hex(row['target']),
            pointers=[hex(p['address']) if p['address'] is not None else 'file:'+hex(p['file_offset']) for p in row['pointers']],
            constants=len(row['constants']), constant_sites=[hex(p['source']) for p in row['constants']] if len(row['constants'])<9 else [],
            calls=[hex(p['source']) for p in row['calls']],
            branches=[hex(p['source']) for p in row['branches']])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inventory", "collect", "win", "refs", "words", "text", "drivers", "calls", "verify"))
    parser.add_argument("values", nargs="*")
    parser.add_argument("--image", choices=IMAGES, default="v36")
    args = parser.parse_args()
    preflight()
    if args.action == "inventory": inventory()
    elif args.action == "collect": collect(args.image)
    elif args.action == "refs": references(args.image, [int(v, 16) for v in args.values])
    elif args.action == "drivers":
        raw, sections = image(args.image)
        rows = []
        for pc in range(0x200c0e60, 0x200c14c8, 40):
            data = at(raw, sections, pc, 40)
            rows.append(dict(address=pc, name=data[:16].split(b'\0')[0].decode('ascii','replace'),
                words=[int.from_bytes(data[i:i+4],'big') for i in range(16,40,4)]))
        save('local/drivers-'+args.image+'.json',rows)
        for row in rows: print(hex(row['address']),row['name'],*[hex(v) for v in row['words']])
    elif args.action == "calls":
        targets = {int(v,16) for v in args.values}
        full = json.loads((LOCAL / (args.image + '-index.json')).read_text())
        sites = {r['source'] for r in full['calls'] + full['branches'] if r['target'] in targets}
        for path in sorted(LOCAL.glob(args.image+'-s??.asm')):
            ops = operations(path.read_text())
            for i,(pc,op,_,_) in enumerate(ops):
                if pc in sites:
                    print('site',hex(pc))
                    for p,o,_,_ in ops[max(0,i-10):i+3]: print(f'{p:08x} {o}')
    elif args.action == "win":
        lo, hi = [int(v, 16) for v in args.values]
        raw, sections = image(args.image)
        stem = f"{args.image}-{lo:08x}-{hi:08x}"
        ops, checked = decode(raw, sections, lo, hi, stem)
        print("local/" + stem + ".asm", checked, "checked bytes")
        for pc, op, _, _ in ops: print(f"{pc:08x} {op}")
    elif args.action == "words":
        lo, hi = [int(v, 16) for v in args.values]
        raw, sections = image(args.image)
        rows = [dict(address=pc, value=int.from_bytes(at(raw, sections, pc, 4), "big")) for pc in range(lo, hi, 4)]
        save(f"local/{args.image}-words-{lo:08x}-{hi:08x}.json", rows)
        for row in rows: print(f"{row['address']:08x} {row['value']:08x}")
    elif args.action == "text":
        raw, sections = image(args.image)
        for term in args.values:
            pos = raw.lower().find(term.lower().encode())
            hits = []
            while pos >= 0:
                hits.append(dict(offset=pos, address=address_of(sections, pos),
                    context=raw[max(0,pos-28):pos+72].decode('ascii','replace')))
                pos = raw.lower().find(term.lower().encode(), pos+1)
            save('local/text-'+args.image+'-'+term+'.json', hits)
            print(json.dumps(dict(term=term, hits=hits)))
    else:
        rows = json.loads((OUT / "inputs-before.json").read_text())
        results = [{**r, "unchanged": digest(ROOT / r["path"]) == r["sha256"]} for r in rows]
        save("inputs-after.json", results)
        assert all(r["unchanged"] for r in results)
        print(json.dumps(dict(status="PASS", unchanged=len(results))))


if __name__ == "__main__":
    main()
