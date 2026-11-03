#!/usr/bin/python3
"""Execute byte-checked M32R code with the repository decoder and two cores."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / "local"
MODULE = ROOT / "firmware/kv2_modules/math"
BUILD = MODULE / "local"


def reg(text):
    if text == "fp":
        return "r[13]"
    if text == "sp":
        return "r[15]"
    if text == "lr":
        return "r[14]"
    assert re.fullmatch(r"r(?:[0-9]|1[0-5])", text), text
    return "r[" + text[1:] + "]"


def number(text):
    return str(int(text.lstrip("#"), 0)) + "u"


def memory(text):
    if text.startswith("@+"):
        return "(" + reg(text[2:]) + "+=4)"
    if text.endswith("+"):
        return "((" + reg(text[1:-1]) + "+=4)-4)"
    if text.startswith("@("):
        offset, base = text[2:-1].split(",")
        return "(" + reg(base) + "+(uint32_t)(" + str(int(offset, 0)) + "))"
    assert text.startswith("@"), text
    return reg(text[1:])


def statement(name, args, at):
    if name == "nop":
        return ""
    if name in ("ldi", "ld24"):
        return reg(args[0]) + "=(uint32_t)(" + str(int(args[1].lstrip("#"), 0)) + ");"
    if name == "seth":
        return reg(args[0]) + "=" + number(args[1]) + "<<16;"
    if name == "mv":
        return reg(args[0]) + "=" + reg(args[1]) + ";"
    if name == "mvfc":
        assert args[1] == "cbr"
        return reg(args[0]) + "=cf;"
    if name in ("neg", "not"):
        return reg(args[0]) + "=" + ("0u-" if name == "neg" else "~") + reg(args[1]) + ";"
    operators = {"add": "+", "sub": "-", "and": "&", "or": "|", "xor": "^", "mul": "*"}
    if name in operators:
        return reg(args[0]) + operators[name] + "=" + reg(args[1]) + ";"
    if name in ("add3", "and3", "or3"):
        return reg(args[0])+"="+reg(args[1])+{"add3":"+","and3":"&","or3":"|"}[name]+"(uint32_t)("+str(int(args[2].lstrip("#"),0))+");"
    if name == "addi":
        return reg(args[0]) + "+=(uint32_t)(" + str(int(args[1][1:], 0)) + ");"
    if name in ("sll3", "srl3", "sra3", "slli", "srli", "srai"):
        dest = reg(args[0]); source = reg(args[1]) if name.endswith("3") else dest
        amount = number(args[-1])
        if name.startswith("sra"):
            return dest + "=(uint32_t)((int32_t)" + source + ">>" + amount + ");"
        return dest + "=" + source + ("<<" if name.startswith("sll") else ">>") + amount + ";"
    if name in ("cmp", "cmpu", "cmpi", "cmpui"):
        left = reg(args[0]); right = "(uint32_t)("+str(int(args[1][1:],0))+")" if name.endswith("i") else reg(args[1])
        cast = "(int32_t)" if name in ("cmp", "cmpi") else ""
        return "cf="+cast+left+"<"+cast+right+";"
    if name in ("addx", "subx"):
        return ("add_carry" if name == "addx" else "sub_carry")+"("+reg(args[0])[2:-1]+","+reg(args[1])+");"
    if name in ("div", "rem"):
        a,b=map(reg,args)
        return "if(!"+b+")fail(\"zero divisor\");"+a+"=(uint32_t)((int64_t)(int32_t)"+a+("/" if name=="div" else "%")+"(int32_t)"+b+");"
    if name in ("ld", "ldub", "lduh"):
        return reg(args[0])+"=read_mem("+memory(args[1])+","+("4" if name=="ld" else "2" if name=="lduh" else "1")+");"
    if name in ("st", "stb"):
        return "write_mem("+memory(args[1])+","+reg(args[0])+","+("4" if name=="st" else "1")+");"
    if name == "push":
        return "r[15]-=4;write_mem(r[15],"+reg(args[0])+",4);"
    if name == "pop":
        return reg(args[0])+"=read_mem(r[15],4);r[15]+=4;"
    if name == "jmp":
        return "next_pc="+reg(args[0])+"&~3u;"
    if name in ("bra", "bl"):
        return ("r[14]="+str((at&~3)+4)+"u;" if name=="bl" else "")+"next_pc="+number(args[0])+";"
    if name in ("bc", "bnc"):
        condition = "cf" if name=="bc" else "!cf"
    elif name in ("beq", "bne"):
        condition = reg(args[0])+("==" if name=="beq" else "!=")+reg(args[1])
    elif name in ("beqz", "bnez", "bltz", "bgez", "blez", "bgtz"):
        condition = "(int32_t)"+reg(args[0])+{"beqz":"==","bnez":"!=","bltz":"<","bgez":">=","blez":"<=","bgtz":">"}[name]+"0"
    else:
        raise RuntimeError("unsupported instruction: "+name+str(args))
    return "if("+condition+")next_pc="+number(args[-1])+";"


def backend():
    sys.path.insert(0,str(ROOT/"tools/native_harness"))
    module=runpy.run_path(str(ROOT/"tools/native_harness/python_backend.py"))
    cls=module["PythonBackend"]
    cls._decode.__globals__["CACHE"]=LOCAL/"decode"
    instance=cls()
    instance.map(0x100000,(BUILD/"kv_math.bin").read_bytes(),False)
    instance.map(0x200000,bytes(65536))
    return instance


def symbols():
    result={}
    for line in (BUILD/"symbols.txt").read_text().splitlines():
        match=re.match(r"([0-9a-f]+)\s+.*\s(\w+)$",line)
        if match:
            result[match[2]]=int(match[1],16)
    return result


def make_program(instance):
    starts=[]
    for line in (BUILD/"target.dis").read_text().splitlines():
        match=re.match(r"\s*([0-9a-f]+):\s+[0-9a-f]{2} ",line)
        if match:
            starts.append(int(match[1],16))
    for at in starts:
        instance._decode(at)
    end=symbols()["exp_q12"]
    text_end=min(int(m[1],16)+int(m[2],16) for m in re.finditer(
        r"\s+\d+ \.text\s+([0-9a-f]+)\s+([0-9a-f]+)",(BUILD/"sections.txt").read_text()))
    del end
    rows={at:row for at,row in instance.rows.items() if 0x100000<=at<text_end}
    output=[]
    ops=set()
    for at,(raw,instructions,parallel,pretty) in sorted(rows.items()):
        if parallel:
            assert any(name=="nop" for name,args in instructions),pretty
        parts=[]
        for index,(name,args) in enumerate(instructions):
            part=statement(name,args,at)
            if index+1<len(instructions) and (name.startswith("b") or name=="jmp"):
                if part.startswith("if("):
                    condition,assignment=part.split("next_pc=",1)
                    part=condition+"{next_pc="+assignment+"break;}"
                else:
                    part+="break;"
            parts.append(part)
        body="".join(parts)
        ops.update(name for name,args in instructions)
        output.append("case "+hex(at)+":next_pc="+hex(at+len(raw))+"u;"+body+"break;")
    (LOCAL/"program.inc").write_text("\n".join(output)+"\n")
    return {"decoded_rows":len(rows),"instructions":sorted(ops),
            "module_sha256":hashlib.sha256((BUILD/"kv_math.bin").read_bytes()).hexdigest()}


def native_checks(instance,entry,indices=None):
    path=LOCAL/"parity_cases.bin"
    count=path.stat().st_size//1740
    if indices is None:
        indices=sorted(set([0,1,2,82,count-1]+list(range(0,count,max(1,count//96)))))
    maximum=0
    with path.open("rb") as stream:
        for index in indices:
            stream.seek(index*1740);record=stream.read(1740)
            instance.write(0x200000,record[:552])
            instance.write(0x200300,record[552:1104])
            instance.write(0x200600,record[1104:1156])
            instance.write(0x200700,bytes([165])*552)
            instance.write(0x200a00,struct.pack(">7i",*([-777]*7)))
            instance.set_reg("r15",0x20f000)
            instance.write(0x20f000,struct.pack(">2I",0x200a00,0x201000))
            stop=instance.call(entry,[0x200000,0x200300,0x200600,0x200700],0x300000,2000000)
            assert stop.reason=="return",stop
            assert instance.get_reg("r0")==struct.unpack(">I",record[1156:1160])[0]
            assert instance.read(0x200700,552)==record[1188:],("native bytes",index)
            assert instance.read(0x200a00,28)==record[1160:1188],("native stats",index)
            maximum=max(maximum,stop.steps)
    return {"native_backend_cases":len(indices),"native_maximum_steps":maximum}


def native_i64_checks(instance,names):
    raw=(LOCAL/"i64_cases.bin").read_bytes()
    count=len(raw)//32
    indices=sorted(set(range(121))|set(range(0,count,max(1,count//64))))
    for index in indices:
        record=raw[index*32:(index+1)*32]
        args=struct.unpack(">4I",record[:16])
        for name,offset in (("__muldi3",16),("__divdi3",24)):
            instance.set_reg("r15",0x20f000)
            for saved in range(8,14):
                instance.set_reg("r"+str(saved),0x12340000+saved)
            stop=instance.call(names[name],list(args),0x300000,20000)
            assert stop.reason=="return",stop
            actual=struct.pack(">2I",instance.get_reg("r0"),instance.get_reg("r1"))
            assert actual==record[offset:offset+8],(name,index)
            assert instance.get_reg("r15")==0x20f000
            for saved in range(8,14):
                assert instance.get_reg("r"+str(saved))==0x12340000+saved
    return len(indices)


def main():
    os.environ["TMPDIR"]=str(LOCAL)
    instance=backend();names=symbols()
    result=make_program(instance)
    subprocess.run(["clang","-std=c11","-O2","-Wall","-Wextra","-I",str(LOCAL),
                    str(HERE/"target_runner.c"),"-o",str(LOCAL/"target_runner")],check=True)
    for label,file in (("parity","parity_cases.bin"),("extended","extended_cases.bin")):
        run=subprocess.run([str(LOCAL/"target_runner"),str(BUILD/"kv_math.bin"),"parity",
                            str(LOCAL/file),hex(names["kv_apply_work"])],capture_output=True,text=True,check=True)
        result[label]=json.loads(run.stdout)
        assert result[label]["cases"]=={"parity":13330,"extended":2504}[label]
        print(label,run.stdout.strip(),flush=True)
    run=subprocess.run([str(LOCAL/"target_runner"),str(BUILD/"kv_math.bin"),"i64",
                        str(LOCAL/"i64_cases.bin"),hex(names["__muldi3"]),hex(names["__divdi3"])],
                       capture_output=True,text=True,check=True)
    result["i64"]=json.loads(run.stdout)
    assert result["i64"]["i64_pairs"]==100121
    print("i64",run.stdout.strip(),flush=True)
    result.update(native_checks(instance,names["kv_apply_work"]))
    result["native_i64_pairs"]=native_i64_checks(instance,names)
    result["status"]="PASS"
    (HERE/"target_results.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)


if __name__=="__main__":
    main()
