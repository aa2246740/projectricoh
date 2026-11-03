#!/usr/bin/python3
"""Run frozen sanitizer cases with the new module and additional overlaps."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MODULE=ROOT/"firmware/kv2_modules/math"
LOCAL=HERE/"local/sanitizers"


def main():
    LOCAL.mkdir(exist_ok=True)
    os.environ["TMPDIR"]=str(LOCAL)
    sys.path.insert(0,str(ROOT/"research/knobs_v2_r2/src"))
    data=runpy.run_path(str(ROOT/"research/knobs_v2_r2/src/verify.py"),run_name="frozen_sanitizers")
    support=data["s"]
    support.LOCAL=LOCAL
    support.dump=lambda path,value: Path(path).write_text(json.dumps(value,indent=2)+"\n")

    def compile_module(sources,output,sanitize=False):
        selected=[]
        for path in sources:
            if Path(path).name=="knobs.c":
                selected.extend(MODULE/name for name in ("kv_math.c","kv_i64.c","test_adapter.c"))
            else:
                selected.append(path)
        selected=[path if Path(path).is_absolute() else ROOT/"research/knobs_v2_r2/src"/path
                  for path in selected]
        command=["clang","-std=c11","-O1","-Wall","-Wextra","-Werror","-pedantic",
                 "-Wno-misleading-indentation","-fno-modules","-fno-implicit-modules",
                 "-ffreestanding","-fno-builtin","-g","-fsanitize=address,undefined",
                 "-fno-sanitize-recover=all",*(str(path) for path in selected),"-o",str(output)]
        run=subprocess.run(command,capture_output=True,text=True)
        (LOCAL/"compile.log").write_text(run.stdout+run.stderr)
        run.check_returncode()
        return None

    data["sanitized"].__globals__["compile_c"]=compile_module
    modules=support.parse()
    outcome=data["sanitized"](modules)
    raw=b"".join(bytes(m["entries"][4])+bytes(m["entries"][slot])
                 for m in modules for slot in range(1,9))
    (LOCAL/"edge_inputs.bin").write_bytes(raw)
    common=["clang","-std=c11","-O1","-g","-fno-omit-frame-pointer",
            "-ffreestanding","-fno-builtin","-fsanitize=address,undefined",
            "-fno-sanitize-recover=all"]
    subprocess.run([*common,str(MODULE/"kv_math.c"),str(MODULE/"kv_i64.c"),
                    str(MODULE/"test_edges.c"),"-o",str(LOCAL/"test_edges")],check=True)
    edge=subprocess.run([str(LOCAL/"test_edges"),str(LOCAL/"edge_inputs.bin")],
                        check=True,capture_output=True,text=True).stdout.strip()
    subprocess.run([*common,str(MODULE/"kv_i64.c"),str(MODULE/"test_i64.c"),
                    "-o",str(LOCAL/"test_i64")],check=True)
    integers=subprocess.run([str(LOCAL/"test_i64"),str(HERE/"local/i64_cases.bin")],
                            check=True,capture_output=True,text=True).stdout.strip()
    # The original menu rejection cases run against a menu linked to this core.
    subprocess.run(["clang","-std=c11","-Os","-dynamiclib","-ffreestanding","-fno-builtin",
                    str(ROOT/"research/knobs_v2_r2/src/menu.c"),str(MODULE/"kv_math.c"),
                    str(MODULE/"kv_i64.c"),str(MODULE/"test_adapter.c"),"-o",str(LOCAL/"menu.dylib")],check=True)
    cm=data["CMenu"](build=False)
    table=json.loads((ROOT/"research/knobs_v2_r2/tables/final.json").read_text())
    invalid=data["invalid_menu"](cm,table,modules)
    assert invalid==492,invalid
    result={"status":"PASS","frozen_sanitizer":outcome,"extra_edges":edge,
            "integer_pairs":integers,
            "invalid_menu_cases":invalid,"full_domain_requests":20000,"legal_menu_requests":20000,
            "sanitizers":["ASan","UBSan"]}
    (HERE/"sanitizer_results.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))


if __name__=="__main__":
    main()
