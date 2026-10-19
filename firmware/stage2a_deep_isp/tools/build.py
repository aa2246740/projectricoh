#!/usr/bin/env python3
"""Build and audit isolated M32R assets. Never writes a firmware container."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
GCC = ROOT / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
BIN = ROOT / "research/tooling_m32r_asm/prefix/bin"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
IMAGE = ROOT / "artifacts/firmware/gxr-1.51/ilaunch3"
IMAGE_SHA = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
# This shared UI function is also called outside recipe screens. Keeping its
# whole body original removes the old unconditional jump into our payload.
PROTECTED_CODE = (
    ("native_layer_action", 0x201c092c, 0x201c0cf4),
    ("native_fn2_activity_gate", 0x202be23c, 0x202be24c),
    ("native_live_activity_gate", 0x202bb960, 0x202bb968),
    ("native_adj_function_dispatch", 0x202ba6fc, 0x202ba9e8),
    ("native_adj_function_case_table", 0x20377434, 0x20377460),
)
NATIVE = {
    "native_commit_epilogue": 0x202bcf58,
    "native_commit_resume": 0x202bb96c,
    "native_fn2_epilogue": 0x202be6a8,
    "native_fn2_resume": 0x202be250,
    "native_action_resume": 0x202871dc,
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(argv, out, name):
    p = subprocess.run([str(arg) for arg in argv], cwd=ROOT, text=True, capture_output=True)
    (out / f"{name}.txt").write_text(p.stdout + p.stderr)
    if p.returncode:
        raise RuntimeError(f"{name} exited {p.returncode}: {p.stderr.strip()}")
    return p.stdout


class Elf:
    def __init__(self, path):
        self.bytes = Path(path).read_bytes()
        if self.bytes[:6] != b"\x7fELF\x01\x02":
            raise ValueError("expected ELF32 big endian")
        header = struct.unpack_from(">HHIIIIIHHHHHH", self.bytes, 16)
        self.kind, machine, _, self.entry = header[:4]
        if machine != 88:
            raise ValueError("expected M32R machine 88")
        shoff, shsize, count, names_index = header[5], header[10], header[11], header[12]
        if shsize != 40:
            raise ValueError("unexpected section header size")
        self.sections = []
        for i in range(count):
            values = struct.unpack_from(">10I", self.bytes, shoff + i * 40)
            keys = ("name_offset","type","flags","va","offset","size","link","info","align","entsize")
            self.sections.append(dict(zip(keys, values), index=i))
        names = self.content(self.sections[names_index])
        for section in self.sections:
            section["name"] = self.string(names, section["name_offset"])
        self.symbol_tables = {}
        self.symbols = {}
        for section in self.sections:
            if section["type"] != 2:
                continue
            strings = self.content(self.sections[section["link"]])
            symbols = []
            for i in range(0, section["size"], 16):
                n, value, size, info, other, index = struct.unpack_from(">IIIBBH", self.bytes, section["offset"] + i)
                symbol = {"name": self.string(strings,n), "value": value, "size": size,
                          "info": info, "other": other, "section": index}
                symbols.append(symbol)
                if symbol["name"]:
                    self.symbols[symbol["name"]] = symbol
            self.symbol_tables[section["index"]] = symbols

    @staticmethod
    def string(blob, offset):
        return blob[offset:blob.index(0, offset)].decode("ascii")

    def content(self, section):
        return self.bytes[section["offset"]:section["offset"] + section["size"]]


def distance(pc, target, bits, aligned_pc=False):
    origin = pc & ~3 if aligned_pc else pc
    delta = target - origin
    limit = (1 << (bits - 1)) * 4
    ok = target % 4 == 0 and delta % 4 == 0 and -limit <= delta <= limit - 4
    result = {"pc": hex(pc), "target": hex(target), "delta_bytes": delta,
              "bits": bits, "min_bytes": -limit, "max_bytes": limit - 4, "pass": ok}
    if not ok:
        raise ValueError(f"branch out of range: {result}")
    return result


def layout(objects, base):
    positions, symbols, spans = {}, dict(NATIVE), []
    position = base
    for prefix in (".text", ".rodata"):
        position = (position + 3) & ~3
        for index, obj in enumerate(objects):
            for section in obj.sections:
                if section["name"] != prefix and not section["name"].startswith(prefix + "."):
                    continue
                alignment = max(section["align"], 1)
                position = (position + alignment - 1) & -alignment
                positions[index, section["index"]] = position
                if prefix == ".text" and section["size"]:
                    spans.append((position, position + section["size"]))
                position += section["size"]
        position = (position + 3) & ~3
    for index, obj in enumerate(objects):
        for name, symbol in obj.symbols.items():
            if (index, symbol["section"]) in positions and symbol["info"] >> 4 != 0:
                symbols[name] = positions[index, symbol["section"]] + symbol["value"]
    return positions, symbols, spans, position


def prelink_branches(objects, positions, symbols, out, object_paths):
    checks = []
    for index, obj in enumerate(objects):
        text = run([OBJDUMP, "-r", object_paths[index]], out, f"relocations-{index}")
        names, section_name = {}, None
        for line in text.splitlines():
            heading = re.match(r"RELOCATION RECORDS FOR \[(.*)\]:",line)
            if heading: section_name = heading[1]
            relocation = re.match(r"([0-9a-f]+)\s+(R_M32R_\S+)",line)
            if relocation: names[section_name,int(relocation[1],16)] = relocation[2]
        for section in obj.sections:
            if section["type"] != 4:
                continue
            for offset in range(0, section["size"], 12):
                address, info, addend = struct.unpack_from(">IIi", obj.bytes, section["offset"] + offset)
                kind = names.get((obj.sections[section["info"]]["name"],address), "")
                if "PCREL" in kind and not re.search(r"R_M32R_(10|18|26)_PCREL",kind):
                    raise ValueError(f"unsupported PC-relative relocation: {kind}")
                match = re.search(r"R_M32R_(10|18|26)_PCREL", kind)
                if not match:
                    continue
                symbol = obj.symbol_tables[section["link"]][info >> 8]
                if symbol["section"] == 0:
                    target = symbols[symbol["name"]] + addend
                elif symbol["section"] == 0xfff1:
                    target = symbol["value"] + addend
                else:
                    target = positions[index, symbol["section"]] + symbol["value"] + addend
                bits = int(match[1]) - 2
                pc = positions[index, section["info"]] + address
                check = distance(pc, target, bits, bits == 8)
                checks.append(dict(check, kind=kind, symbol=symbol["name"], object=object_paths[index].name))
    return checks


def image_segments(image):
    rows = list(csv.DictReader((ROOT / "research/firmware/ilaunch3-sections.csv").open()))
    segments = []
    for i in range(16):
        source, va, size, bss, bss_size = struct.unpack_from(">5I", image, 0x20 + i*20)
        expected = (source, source+512, va, size, bss, bss_size)
        actual = tuple(int(rows[i][key]) for key in
                       ("source_payload_offset","file_offset","load_address","initialized_size","bss_address","bss_size"))
        if expected != actual:
            raise ValueError("container/CSV mismatch")
        segments.append((i, va, size, source+512))
    return segments


def map_va(segments, va, length):
    candidates = [(i, offset + va - start) for i,start,size,offset in segments
                  if start <= va and va + length <= start + size]
    if len(candidates) != 1:
        raise ValueError(f"VA is not uniquely inside an initialized segment: {va:#x}")
    return candidates[0]


def evidence(va):
    hits = []
    for index in (8,9):
        path = ROOT / f"research/tooling_m32r/disasm/ilaunch3-sec{index:02d}-load-{'201bdc00' if index == 8 else '2025d800'}.disasm.txt"
        for line_number, line in enumerate(path.open(), 1):
            if line.startswith(f"{va:08x}:"):
                hits.append({"file": str(path.relative_to(ROOT)), "line": line_number, "text": line.strip()})
                break
    return hits


def hooks(image, segments, symbols, out, base, capacity, reserve, payload):
    specifications = []

    def add(identifier, va, old, new, kind, notes, target=None, returns=None, checks=None):
        original, replacement = bytes.fromhex(old), bytes.fromhex(new)
        if len(original) != len(replacement):
            raise ValueError("hook must be equal length")
        index, offset = map_va(segments,va,len(original))
        if image[offset:offset + len(original)] != original:
            raise ValueError(f"expected bytes mismatch at {va:#x}")
        entry = {"id": identifier, "va": hex(va), "file_offset": hex(offset), "segment": index,
                 "length": len(original), "original_bytes": old, "new_bytes": new,
                 "instruction_kind": kind, "parameters_and_return": notes,
                 "original_disassembly": evidence(va), "branch_checks": checks or []}
        if kind == "SETH_OR3":
            entry["original_target_va"] = hex((int.from_bytes(original[2:4],"big") << 16) | int.from_bytes(original[6:8],"big"))
        if target is not None:
            entry.update(target_symbol=target, target_va=hex(symbols[target]))
        if returns is not None:
            entry["continuations"] = [hex(value) for value in returns]
        specifications.append(entry)

    def branch(identifier, va, old, target, notes, returns):
        check = distance(va,symbols[target],24)
        word = 0xff000000 | ((check["delta_bytes"]//4) & 0xffffff)
        add(identifier,va,old,f"{word:08x}","BRA24",notes,target,returns,[check])

    def absolute(identifier,va,old,register,target,notes,returns=None):
        address = symbols[target]
        if not 0 <= address <= 0xffffffff or address % 4:
            raise ValueError("absolute hook target must be aligned u32")
        new = struct.pack(">HHHH",0xd0c0 | register << 8,address >> 16,
                          0x80e0 | register << 8 | register,address & 0xffff).hex()
        check = {"kind": "absolute_u32", "target": hex(address), "delta_limit": None, "pass": True}
        add(identifier,va,old,new,"SETH_OR3",notes,target,returns,[check])

    absolute("init_recipe_cache",0x2028709c,"d0c0202780e01fec",0,"ricoh_recipe_open",
             "Retain native prologue, 0x20331d18 call and overlay_word=32. Existing jl r0 at 0x202870a4 returns cursor 1..16 in r0; saves r8..r13/lr.",[0x202870a8])
    check = distance(0x202870aa,0x20287118,8,True)
    add("init_cursor_bypass_enum",0x202870a8,"12806005","18807f1c","MV_BRA8",
        "mv r8,r0 executes before bra.s. Skip native seven-value switch; resume common type5/layer2/tag33 init. lr unchanged.",
        returns=[0x20287118],checks=[check])
    add("adj_name_table",0x2022f5a8,"2022d610",struct.pack(">I",symbols["rfw_closed_table"]).hex(),"BE32_TABLE_POINTER",
        "Only ADJ type5 descriptor. First open publishes the resident heap table; close clears its open flag without freeing native label addresses. Reopen reloads the banks using the same allocation.","rfw_closed_table")
    add("adj_count_16",0x2022f5ac,"07","10","U8_COUNT",
        "Change only ADJ count. Preserve three ff control bytes and zero filter pointer. Main-menu seven-item descriptor is unchanged.")
    absolute("adj_empty_details",0x201febe4,"d2c0202382e2fd38",2,"rfw_no_details",
             "Keep r11/type discrimination and type9 branch. Substitute 16 x 12 zero bytes, preventing row8..16 reads of old seven-item details.",[0x201febec])
    branch("fn2_no_editor",0x202be24c,"d0c02026","recipe_fn2_guard",
           "Original bne at 202be248 rejects non-Image activities before payload entry. For Image, only active type5/layer2/tag33/state2022f71c returns handled=2 using saved r8 and native epilogue, including failed-load or closed-cache states with 16 visible rows. Inactive fallback replays seth r0,2026 and resumes 202be250. Preserve all other live registers and PSW.",
           [0x202be250,0x202be6a8])
    branch("adj_confirm_close",0x202871d8,"2e7ff000","ricoh_recipe_action",
           "Preserve all registers/PSW for the page-type guard. Only active type5/layer2/tag33/state2022f71c enters the recipe action. Otherwise replay push lr and resume original function at 202871dc with original r4. Recipe route maps native r4=keep_open to GCC r0 and never indexes old seven-mode enums.",
           [0x202871dc])
    branch("live_recipe_commit",0x202bb968,"dbc02022","recipe_live_commit",
           "Original ldi r2,8 and bne at 202bb964 reject non-Image activities before payload entry. If recipe UI is active (type5/layer2/tag33/state2022f71c), consume native cursor at 2022f726 then return through 202bcf58 even if the cache is unavailable, avoiding all seven-mode setters. Inactive fallback replays seth r11,2022 and resumes 202bb96c. Save all other live GPRs/lr/PSW.",
           [0x202bb96c,0x202bcf58])
    original_flow = {
        "init_cursor_bypass_enum": "Displaced mv r2,r0; ldi r0,5, then seven-mode conditional switch.",
        "fn2_no_editor": "Original bne at 0x202be248 stays intact; displaced seth r0,0x2026 resumes at 0x202be250.",
        "adj_confirm_close": "Original function prologue push lr; original return jmp lr at 0x202872dc.",
        "live_recipe_commit": "Original ldi and bne stay intact; displaced seth r11,0x2022 resumes at 0x202bb96c.",
    }
    for entry in specifications:
        if entry["id"] in original_flow: entry["original_flow"] = original_flow[entry["id"]]
        if entry["id"] == "adj_confirm_close":
            entry["return_address_mode"] = "inherited_native_lr"
    for entry in specifications:
        if entry["id"] == "adj_confirm_close":
            entry["preserved_call_examples"] = [
                {"call_va":"0x202b8d98","return_va":"0x202b8d9c","r4":0},
                {"call_va":"0x202bd88c","return_va":"0x202bd890","r4":0},
                {"call_va":"0x202bea50","return_va":"0x202bea54","r4":0},
                {"call_va":"0x202c2d70","return_va":"0x202c2d74","r4":1},
                {"call_va":"0x202c2d80","return_va":"0x202c2d84","r4":0},
            ]
            for call in entry["preserved_call_examples"]:
                _, offset = map_va(segments,int(call["call_va"],16),4)
                expected_word = struct.pack(">HH",0x6400 | call["r4"],0x1ec0)
                if image[offset-8:offset] != bytes.fromhex("d0c0202880e071d8") or image[offset:offset+4] != expected_word:
                    raise ValueError("native call example target or parameter preparation differs")
                call["original_bytes"] = expected_word.hex()
                call["target_construction_verified"] = True
    occupied = []
    for entry in specifications:
        start = int(entry["file_offset"],16)
        if any(start < end and start+entry["length"] > begin for begin,end in occupied):
            raise ValueError("overlapping hooks")
        occupied.append((start,start+entry["length"]))
        blob = bytes.fromhex(entry["new_bytes"])
        path = out / (entry["id"] + ".hook.bin")
        path.write_bytes(blob)
        if entry["instruction_kind"] not in ("BE32_TABLE_POINTER","U8_COUNT"):
            decoded = run([OBJDUMP,"-D","-b","binary","-m","m32r","-EB",
                           f"--adjust-vma={entry['va']}",path],out,entry["id"] + "-disasm")
            entry["replacement_disassembly"] = str((out/(entry["id"]+"-disasm.txt")).relative_to(ROOT))
            if entry["instruction_kind"] == "BRA24":
                if not re.search(rf"\bbra\s+0x{symbols[entry['target_symbol']]:x}\b",decoded):
                    raise ValueError("hook branch disassembly target mismatch")
            if entry["instruction_kind"] == "MV_BRA8" and not re.search(r"\bbra\s+0x20287118\b",decoded):
                raise ValueError("short hook branch disassembly target mismatch")
    segment, offset = map_va(segments,base,len(payload))
    if image[offset:offset+len(payload)] != b"\xff"*len(payload):
        raise ValueError("payload insertion does not match all-FF bytes")
    if any(offset < end and offset+len(payload) > begin for begin,end in occupied):
        raise ValueError("payload overlaps hook")
    map_va(segments,base,capacity)
    protected_code = check_protected_code(image, segments, specifications, offset, len(payload))
    return {"schema": "gxr.recipe-hooks.v1", "image": str(IMAGE.relative_to(ROOT)), "image_sha256": IMAGE_SHA,
            "candidate_vma_approved": False, "camera_verified": False, "upgrade_package_generated": False,
            "hook_count": len(specifications), "hooks": specifications, "protected_code": protected_code,
            "payload_patch": {"va": hex(base),"file_offset": hex(offset),"segment": segment,
                              "length": len(payload),"instruction_kind": "PAYLOAD",
                              "original_bytes": {"repeat": "ff","count": len(payload)},
                              "original_sha256": sha(b"\xff"*len(payload)),
                              "new_bytes_asset": str((out/"payload.bin").relative_to(ROOT)),
                              "new_sha256": sha(payload), "equal_length": True},
            "probe_contract": {"va_start": hex(base+capacity-reserve),"va_end_exclusive": hex(base+capacity),
                               "file_offset": hex(map_va(segments,base+capacity-reserve,reserve)[1]),
                               "length": reserve,"owner": "probe worker",
                               "integration_writes": False,"initial_bytes": "ff",
                               "additional_free_bytes_before_tail": capacity-reserve-len(payload)}}


def check_protected_code(image, segments, specifications, payload_offset, payload_length):
    changes = [(int(hook["file_offset"],16), hook["length"]) for hook in specifications]
    changes.append((payload_offset,payload_length))
    records = []
    for name, begin, end in PROTECTED_CODE:
        _, offset = map_va(segments,begin,end-begin)
        if any(start < offset+end-begin and start+length > offset for start,length in changes):
            raise ValueError(f"patch overlaps protected code: {name}")
        records.append({"name":name,"va_start":hex(begin),"va_end_exclusive":hex(end),
                        "file_offset":hex(offset),"length":end-begin,
                        "sha256":sha(image[offset:offset+end-begin]),"no_patch_overlap":True})
    return records


def protected():
    files = [IMAGE]
    for directory in ("firmware/recipe_v1","firmware/recipe_core","scripts"):
        files += sorted(path for path in (ROOT/directory).rglob("*") if path.is_file()
                        and not {"build", "__pycache__"}.intersection(path.relative_to(ROOT).parts))
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",type=lambda s:int(s,0),default=0x2005276c)
    parser.add_argument("--capacity",type=lambda s:int(s,0),default=8340)
    parser.add_argument("--probe-reserve",type=lambda s:int(s,0),default=256)
    parser.add_argument("--out",type=Path,default=HERE/"build")
    parser.add_argument("--variant",choices=("safe","deep"),default="deep")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(HERE) or args.base % 4 or args.probe_reserve < 256:
        parser.error("outputs must stay in recipe_fw; aligned base and >=256-byte reserve required")
    out.mkdir(parents=True,exist_ok=True)
    baseline = protected(); save_json(out/"protected-inputs.json",baseline)
    image = IMAGE.read_bytes()
    if sha(image) != IMAGE_SHA: raise ValueError("official image hash mismatch")
    segments = image_segments(image)
    sources = [HERE/"abi.S",HERE/"platform.c",HERE/"ui.c",HERE/"deep_isp.c",HERE/"deep_tables.c"] + [HERE/"recipe_v1"/name for name in
                 ("recipe_format.c","recipe_apply.c")]
    flags = ["-std=c11","-Os","-ffreestanding","-fno-builtin","-fno-stack-protector",
             "-fno-common","-fno-pic","-m32r","-mmodel=large","-msdata=none","-G0",
             "-Wall","-Wextra","-Werror","-fno-unwind-tables","-fno-asynchronous-unwind-tables","-fstack-usage"]
    flags += [f"-DRFW_DEEP_ENABLED={int(args.variant == 'deep')}", "-DRFW_READ_ONLY_BUILD=1"]
    paths, commands = [], []
    for source in sources:
        obj = out/(source.stem+".o"); paths.append(obj)
        # .S contains the same safe/deep flag as C; preprocess it explicitly.
        command = [GCC,*flags,"-I",HERE,"-I",HERE/"recipe_v1","-c",source,"-o",obj]
        commands.append([str(arg) for arg in command]); run(command,out,"compile-"+source.stem)
    objects = [Elf(path) for path in paths]
    positions, expected_symbols, spans, end = layout(objects,args.base)
    if end > args.base+args.capacity-args.probe_reserve: raise ValueError("payload exceeds reserved capacity before link")
    checks = prelink_branches(objects,positions,expected_symbols,out,paths)
    elf_path = out/"payload.elf"
    command = [BIN/"m32r-elf-ld","--no-undefined","--orphan-handling=error",
               f"--defsym=RECIPE_BASE={args.base:#x}",f"--defsym=RECIPE_CAPACITY={args.capacity}",
               f"--defsym=PROBE_RESERVE={args.probe_reserve}","-T",HERE/"payload.ld",
               f"-Map={out/'payload.map'}","-o",elf_path,*paths]
    commands.append([str(arg) for arg in command]); run(command,out,"link")
    elf = Elf(elf_path)
    symbols = {name:value["value"] for name,value in elf.symbols.items()}
    for name,address in expected_symbols.items():
        if symbols.get(name) != address: raise ValueError(f"independent layout differs at {name}")
    if symbols["__payload_end"] != end: raise ValueError("independent payload end mismatch")
    if symbols["rfw_closed_table"] == symbols["rfw_empty_table"]: raise ValueError("open/closed tables were merged")
    payload_section = [section for section in elf.sections if section["name"] == ".payload"]
    if len(payload_section) != 1 or payload_section[0]["va"] != args.base: raise ValueError("bad payload layout")
    for section in elf.sections:
        if section["size"] and section["flags"] & 2 and section["name"] != ".payload":
            raise ValueError("unexpected allocated section")
        if section["size"] and section["type"] in (4,9): raise ValueError("remaining relocation")
    if any(symbol["section"] == 0 and symbol["name"] for symbol in elf.symbols.values()):
        raise ValueError("unresolved symbol")
    disassembly = run([OBJDUMP,"-d",elf_path],out,"payload-disasm")
    for check in checks:
        line = re.search(rf"^\s*{int(check['pc'],16):x}:.*$",disassembly,re.M)
        if line is None or not re.search(rf"\b(?:bl|bra|bc|bnc)\s+{int(check['target'],16):x}\b",line[0]):
            raise ValueError(f"linked branch does not decode to requested target: {check}")
        check["decoded_target_matches"] = True
    # Encoded local conditional/short branches also have independent limits.
    local_checks = []
    for line in disassembly.splitlines():
        match = re.match(r"\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+)+)\s*(.*)",line)
        if not match: continue
        pc, instruction = int(match[1],16), match[3]
        if not any(begin <= pc < finish for begin,finish in spans): continue
        for branch in re.finditer(r"\b(bl|bra|bc|bnc|beqz|bnez|beq|bne|bgez|bgtz|blez|bltz)\s+(?:r\w+,)*([0-9a-f]+)\b",instruction):
            raw = bytes.fromhex(match[2]); bits = 24 if len(raw) == 4 and raw[0] in (0xfc,0xfd,0xfe,0xff) else 16 if raw[0] >= 0x80 else 8
            branch_pc = pc
            if bits == 8 and "->" in instruction and instruction.index(branch[0]) > instruction.index("->"):
                branch_pc += 2
            check = distance(branch_pc,int(branch[2],16),bits,bits == 8)
            local_checks.append(dict(check,instruction=line.strip()))
    payload = elf.content(payload_section[0])
    run([BIN/"m32r-elf-objcopy","-O","binary","--only-section=.payload",elf_path,out/"payload.bin"],out,"objcopy")
    if (out/"payload.bin").read_bytes() != payload: raise ValueError("objcopy/ELF mismatch")
    run([OBJDUMP,"-h","-t","-r",elf_path],out,"payload-headers")
    specification = hooks(image,segments,symbols,out,args.base,args.capacity,args.probe_reserve,payload)
    save_json(out/"hooks.json",specification)
    if out == (HERE/"build").resolve(): save_json(HERE/"hooks.json",specification)
    if protected() != baseline: raise ValueError("protected inputs changed during build")
    stack = [line for path in out.glob("*.su") for line in path.read_text().splitlines()]
    manifest = {"status": "LINKED_STATIC_ONLY", "variant":args.variant,
                "target_deep_injection_enabled":args.variant == "deep",
                "candidate_vma_approved": False,"camera_executed": False,
                "payload_bytes": len(payload),"payload_sha256": sha(payload),"payload_base":hex(args.base),
                "payload_end":hex(end),"capacity":args.capacity,"probe":specification["probe_contract"],
                "hook_count":len(specification["hooks"]),"protected_code":specification["protected_code"],"prelink_branches":checks,
                "decoded_branch_checks":local_checks,"mutable_bytes":0,"remaining_relocations":0,
                "undefined_symbols":0,"commands":commands,"static_stack_frames":stack,
                "source_sha256":{str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in sources},
                "build_inputs_sha256":{str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in
                   sources+[HERE/"foreign.h",HERE/"recipe_fw.h",HERE/"deep_isp.h",HERE/"payload.ld",HERE/"tools/build.py",
                            HERE/"recipe_v1/recipe_v1.h",HERE/"recipe_v1/internal.h"]},
                "tool_sha256":{str(path.relative_to(ROOT)):sha(path.read_bytes()) for path in (GCC,OBJDUMP,BIN/"m32r-elf-as",BIN/"m32r-elf-ld",BIN/"m32r-elf-objcopy")},
                "protected_inputs_unchanged":True,"symbols":{key:hex(value) for key,value in symbols.items()}}
    save_json(out/"manifest.json",manifest)
    print(json.dumps({"payload_bytes":len(payload),"hooks":len(specification["hooks"]),
                      "probe_start":hex(args.base+args.capacity-args.probe_reserve),
                      "prelink_checks":len(checks),"decoded_checks":len(local_checks),"out":str(out)}))


if __name__ == "__main__":
    main()
