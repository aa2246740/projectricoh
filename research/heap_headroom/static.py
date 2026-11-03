#!/usr/bin/python3
"""Prepare local disassembly inputs and census constant call references."""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/heap_headroom"
LOCAL = OUT / "local"
BODY = ROOT / "artifacts/firmware/gxr-1.51/ilaunch3"
SECTIONS = ROOT / "research/body_v4_archB/local/static/sections.json"
BODY_SHA = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
KNOWN = {
    0x2005BF00: "heap_init", 0x2005BF5C: "heap_alloc", 0x2005C038: "heap_free",
    0x200BBDBC: "tracked_release_all", 0x200BBE00: "tracked_alloc",
    0x200BBE5C: "tracked_resize", 0x200BBEE4: "tracked_array",
    0x200BBF20: "tracked_free",
    0x20062860: "system_alloc", 0x20062874: "system_free",
    0x200BBD98: "tracked_list_init",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_image():
    data = BODY.read_bytes()
    assert hashlib.sha256(data).hexdigest() == BODY_SHA
    sections = json.loads(SECTIONS.read_text())
    return data, sections


def prepare():
    data, sections = load_image()
    LOCAL.mkdir(parents=True, exist_ok=True)
    begin = min(s["base"] for s in sections if s["base"] >= 0x20000000)
    end = max(s["base"] + s["bytes"] for s in sections if s["base"] >= 0x20000000)
    main = bytearray(end - begin)
    for s in sections:
        block = data[s["offset"]:s["offset"]+s["bytes"]]
        assert len(block) == s["bytes"]
        if s["base"] >= 0x20000000:
            main[s["base"]-begin:s["base"]-begin+s["bytes"]] = block
        else:
            (LOCAL / "auxiliary.bin").write_bytes(block)
    (LOCAL / "main.bin").write_bytes(main)
    identity = {"body": str(BODY.relative_to(ROOT)), "body_sha256": BODY_SHA,
                "body_bytes": len(data), "sections_source": str(SECTIONS.relative_to(ROOT)),
                "sections_sha256": digest(SECTIONS), "sections": sections,
                "objdump": str(OBJDUMP.relative_to(ROOT)), "objdump_sha256": digest(OBJDUMP),
                "main_base": begin, "main_end": end,
                "auxiliary_base": next(s["base"] for s in sections if s["base"] < 0x20000000)}
    (OUT / "input-identity.json").write_text(json.dumps(identity, indent=2)+"\n")
    print(json.dumps({"main_base":hex(begin),"main_end":hex(end),"objdump_sha256":digest(OBJDUMP)}))


def read_operations(path):
    pattern = re.compile(r"^([0-9a-f]+):\t([0-9a-f ]+)\t(.+)$")
    with path.open() as stream:
        for line in stream:
            m = pattern.match(line)
            if not m:
                continue
            pc = int(m[1],16)
            raw = bytes.fromhex(m[2])
            text = m[3].strip()
            parts = re.split(r"\s+(?:->|\|\|)\s+",text)
            for offset, part in enumerate(parts):
                yield {"pc":pc+offset*2,"text":part,"line_pc":pc,"raw_length":len(raw)}


def scan():
    data, sections = load_image()
    operations = []
    for name in ["main.asm.txt","auxiliary.asm.txt"]:
        operations.extend(read_operations(LOCAL/name))
    boundaries = set()
    for op in operations:
        text = op["text"]
        if text.startswith(("b",)):
            for s in re.findall(r"0x[0-9a-f]+",text): boundaries.add(int(s,16))
    registers, sources, calls, constants, code_constants = {}, {}, [], [], []
    all_calls, unresolved = [], 0

    def read_word(address, width=4, signed=False):
        for s in sections:
            if s["base"] <= address and address + width <= s["base"] + s["bytes"]:
                offset=s["offset"]+address-s["base"]
                return int.from_bytes(data[offset:offset+width],"big",signed=signed)&0xffffffff
        return None

    def value(s):
        if s in registers:return registers[s]
        if s.startswith("#"):s=s[1:]
        try:return int(s,0)&0xffffffff
        except ValueError:return None

    def save(reg, val, pc):
        if val is None:registers.pop(reg,None); sources.pop(reg,None)
        else:
            registers[reg]=val&0xffffffff
            sources[reg]=pc
            if 0x2004B000 <= (val&0xffffffff) < 0x2040AF84 or 0x05000C00 <= (val&0xffffffff) < 0x0500F8FC:
                code_constants.append({"pc":hex(pc),"register":reg,"target":hex(val&0xffffffff)})
            if val&0xffffffff in KNOWN:
                constants.append({"pc":hex(pc),"register":reg,"target":hex(val&0xffffffff),"name":KNOWN[val&0xffffffff]})

    for item in operations:
        pc, text = item["pc"], item["text"]
        if pc in boundaries:registers.clear();sources.clear()
        opcode, _, operand = text.partition(" ")
        args=[s.strip() for s in operand.split(",")]
        if opcode in ("jl","jmp","bl","bra"):
            target=value(operand)
            if opcode in ("jl","bl") or opcode=="jmp" and operand!="lr" or target in KNOWN:
                call={"pc":hex(pc),"operation":opcode,"target":hex(target) if target is not None else None,
                      "r4":registers.get("r4"),"r5":registers.get("r5"),"r6":registers.get("r6"),
                      "r4_source":hex(sources["r4"]) if "r4" in sources else None}
                all_calls.append(call)
                if target is None:unresolved+=1
                if target in KNOWN:
                    call["name"]=KNOWN[target];calls.append(call)
            if opcode in ("jl","bl"):
                for reg in ["r%d"%i for i in range(8)]:registers.pop(reg,None);sources.pop(reg,None)
            else:registers.clear();sources.clear()
            continue
        if opcode.startswith("b"):
            registers.clear();sources.clear();continue
        if not args or not re.fullmatch(r"r\d+|lr|sp|fp",args[0]):continue
        reg=args[0]
        if opcode=="seth":save(reg,value(args[1])<<16 if value(args[1]) is not None else None,pc)
        elif opcode in ("ldi","ld24","mv"):save(reg,value(args[1]),pc)
        elif opcode in ("or3","and3","xor3","add3","sll3","sra3","srl3"):
            a,b=value(args[1]),value(args[2]);result=None
            if a is not None and b is not None:
                if opcode=="or3":result=a|b
                elif opcode=="and3":result=a&b
                elif opcode=="xor3":result=a^b
                elif opcode=="add3":result=a+b
                elif opcode=="sll3":result=a<<(b&31)
                elif opcode=="srl3":result=a>>(b&31)
                elif opcode=="sra3":result=(a if a<0x80000000 else a-0x100000000)>>(b&31)
            save(reg,result,pc)
        elif opcode in ("addi","add","sub","and","or","xor","mul","slli","srli","srai"):
            a,b=value(reg),value(args[1]);result=None
            if a is not None and b is not None:
                if opcode in ("addi","add"):result=a+b
                elif opcode=="sub":result=a-b
                elif opcode=="and":result=a&b
                elif opcode=="or":result=a|b
                elif opcode=="xor":result=a^b
                elif opcode=="mul":result=a*b
                elif opcode=="slli":result=a<<(b&31)
                elif opcode=="srli":result=a>>(b&31)
                elif opcode=="srai":result=(a if a<0x80000000 else a-0x100000000)>>(b&31)
            save(reg,result,pc)
        elif opcode=="neg":
            a=value(args[1]);save(reg,-a if a is not None else None,pc)
        elif opcode.startswith("ld"):
            match=re.search(r"@\(([-0-9]+),(r\d+)\)|@(r\d+)",operand)
            address=None
            if match:
                source=match[2] or match[3]
                if source in registers:address=registers[source]+int(match[1] or 0)
            width={"ldb":1,"ldub":1,"ldh":2,"lduh":2,"ld":4}.get(opcode)
            result=read_word(address,width,opcode in ("ldb","ldh")) if address is not None and width else None
            save(reg,result,pc)
        elif opcode in ("pop","mvtc","mvfc","not","div","rem","divu","remu"):
            save(reg,None,pc)
        elif opcode in ("cmp","cmpu","cmpi","cmpui","cmpeq","cmpz","push","st","stb","sth"):
            pass
        elif opcode not in ("nop",):save(reg,None,pc)

    word_refs=[]
    for s in sections:
        block=data[s["offset"]:s["offset"]+s["bytes"]]
        for target,name in KNOWN.items():
            needle=struct.pack(">I",target)
            start=0
            while True:
                pos=block.find(needle,start)
                if pos<0:break
                word_refs.append({"address":hex(s["base"]+pos),"target":hex(target),"name":name,"aligned":pos%4==0})
                start=pos+1
    (LOCAL/"all-calls.json").write_text(json.dumps(all_calls,indent=2)+"\n")
    (LOCAL/"code-constants.json").write_text(json.dumps(code_constants,indent=2)+"\n")
    encoded_refs=[]
    for s in sections:
        block=data[s["offset"]:s["offset"]+s["bytes"]]
        for target,name in KNOWN.items():
            for reg in range(16):
                suffix=bytes([0x80+reg,0xe0+reg])+struct.pack(">H",target&0xffff)
                prefix=bytes([0xd0+reg,0xc0])+struct.pack(">H",target>>16)
                start=0
                while True:
                    pos=block.find(suffix,start)
                    if pos<0:break
                    nearby=block[max(0,pos-64):pos]
                    before=nearby.rfind(prefix)
                    if before>=0 and (pos%2==0):
                        encoded_refs.append({"address":hex(s["base"]+pos),"target":hex(target),"name":name,
                                             "prefix_address":hex(s["base"]+max(0,pos-64)+before)})
                    start=pos+1
    result={"operations":len(operations),"all_call_candidates":len(all_calls),"unresolved_call_candidates":unresolved,
            "calls":calls,"constant_references":constants,"word_references":word_refs,
            "same_register_encoding_candidates":encoded_refs,
            "limitations":["Linear decoding includes data.","Constants are reset at branches and branch destinations.",
                           "Indirect calls and run-time values remain unresolved.","No interprocedural value-flow closure is claimed."]}
    (OUT/"call-census.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


def window(begin,end):
    for name in ["main.asm.txt","auxiliary.asm.txt"]:
        with (LOCAL/name).open() as stream:
            for line in stream:
                m=re.match(r"^([0-9a-f]+):",line)
                if m and begin<=int(m[1],16)<end:print(line,end="")


def callers(targets):
    wanted={int(t,16) for t in targets}
    calls=json.loads((LOCAL/"all-calls.json").read_text())
    for target in sorted(wanted):
        rows=[c for c in calls if c["target"]==hex(target)]
        print(hex(target),len(rows))
        for row in rows:print(json.dumps(row))


def references(targets):
    wanted={int(t,16) for t in targets}
    constants=json.loads((LOCAL/"code-constants.json").read_text())
    for target in sorted(wanted):
        rows=[c for c in constants if c["target"]==hex(target)]
        print(hex(target),len(rows))
        for row in rows:print(json.dumps(row))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=["prepare","scan","window","callers","references"])
    parser.add_argument("addresses",nargs="*")
    args=parser.parse_args()
    if args.mode=="prepare":prepare()
    elif args.mode=="scan":scan()
    elif args.mode=="callers":callers(args.addresses)
    elif args.mode=="references":references(args.addresses)
    else:window(*(int(a,16) for a in args.addresses))
