#!/usr/bin/python3
"""Check frozen inputs, target size, symbol closure and stack paths."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MODULE=ROOT/"firmware/kv2_modules/math"
BUILD=MODULE/"local"


def check_inputs():
    frozen=json.loads((HERE/"inputs.json").read_text())
    changes=[name for name,expected in frozen.items()
             if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected]
    if changes:
        raise RuntimeError("frozen input changed: "+", ".join(changes))
    return len(frozen)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-only",action="store_true")
    args=parser.parse_args()
    result={"frozen_inputs":check_inputs()}
    if args.inputs_only:
        print("PASS frozen inputs",result["frozen_inputs"])
        return
    sections=(BUILD/"sections.txt").read_text()
    sizes={m[1]:int(m[2],16) for m in re.finditer(
        r"^\s*\d+\s+(\.\w+)\s+([0-9a-f]+)",sections,re.M)}
    result["sections"]=sizes
    result["code_and_constants"]=sizes[".text"]+sizes[".rodata"]
    assert result["code_and_constants"]<=7500
    assert sizes.get(".bss",0)==sizes.get(".data",0)==0
    frames={}
    for path in sorted(BUILD.glob("*.su")):
        for line in path.read_text().splitlines():
            location,size,kind=line.split("\t")
            name=location.rsplit(":",1)[1]
            assert kind=="static",(name,kind)
            frames[name]=int(size)
    assert frames and max(frames.values())<=128
    graph={name:set() for name in frames}
    current=None
    instructions=(BUILD/"target.dis").read_text()
    for line in instructions.splitlines():
        header=re.match(r"[0-9a-f]+ <([^>]+)>:",line)
        if header:
            current=header[1]
        if current not in graph:
            continue
        for match in re.finditer(r"\b(bl|bra)\s+[0-9a-f]+\s+<([^>+]+)(?:\+[^>]*)?>",line):
            callee=match[2]
            if callee!=current:
                assert callee in frames,(current,callee)
                graph[current].add(callee)
        if re.search(r"\bjl\s+",line):
            raise RuntimeError("indirect call in standalone module")
    def depth(name,seen=()):
        assert name not in seen,"recursive path"
        suffix=max((depth(child,(*seen,name)) for child in graph[name]),
                   default=(0,[]),key=lambda item:item[0])
        return frames[name]+suffix[0],[name,*suffix[1]]
    maximum,path=depth("kv_apply_work")
    assert maximum<=512
    for name in ("__muldi3","__divdi3"):
        assert not graph[name],(name,graph[name])
    symbols=(BUILD/"symbols.txt").read_text()
    assert "*UND*" not in symbols
    floats=re.findall(r"\b__(?:\w*(?:sf|df|xf|tf)\w*|float\w*|fix\w*)\b",symbols)
    assert not floats,floats
    for name in ("kv_math.c","kv_i64.c"):
        source=(MODULE/name).read_text()
        assert not re.search(r"\b(?:float|double|malloc|calloc|realloc|free)\b",source)
    result.update({"maximum_frame":max(frames.values()),"frames":frames,
                   "maximum_chain":maximum,"deepest_path":path,
                   "call_graph":{name:sorted(callees) for name,callees in graph.items()},
                   "undefined_symbols":[],"floating_symbols":[],"work_bytes":2288})
    target=HERE/"target_results.json"
    if target.exists():
        execution=json.loads(target.read_text())
        assert execution["module_sha256"]==hashlib.sha256((BUILD/"kv_math.bin").read_bytes()).hexdigest()
        assert execution["parity"]["maximum_stack"]<=maximum
        assert execution["extended"]["maximum_stack"]<=maximum
        result["observed_stack"]=max(execution[group]["maximum_stack"] for group in ("parity","extended"))
    result["artifact_sha256"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(BUILD.iterdir()) if p.is_file() and
                                (p.suffix in (".o",".elf",".su",".bin") or p.name=="target.dis")}
    result["status"]="PASS"
    (HERE/"size_stack_symbols.json").write_text(json.dumps(result,indent=2)+"\n")
    (HERE/"target_stack.tsv").write_text("function\tbytes\tkind\n"+"".join(
        name+"\t"+str(size)+"\tstatic\n" for name,size in sorted(frames.items())))
    (HERE/"target_calls.tsv").write_text("caller\tcallee\n"+"".join(
        name+"\t"+child+"\n" for name in sorted(graph) for child in sorted(graph[name])))
    (HERE/"target_sections.txt").write_text(sections.replace(str(ROOT)+"/",""))
    (HERE/"target_symbols.txt").write_text(symbols.replace(str(ROOT)+"/",""))
    print(json.dumps({k:result[k] for k in ("status","code_and_constants","maximum_frame",
                                         "maximum_chain","deepest_path","frozen_inputs")}))


if __name__=="__main__":
    main()
