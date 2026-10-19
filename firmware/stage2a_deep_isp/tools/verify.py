#!/usr/bin/env python3
"""Run build, host behavior, sanitizers, bridge model and rejection checks."""
import importlib.util
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
OUT = HERE/"build"
spec = importlib.util.spec_from_file_location("builder",HERE/"tools/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def run(argv,label,expect=0):
    p = subprocess.run([str(value) for value in argv],cwd=ROOT,text=True,capture_output=True)
    (OUT/f"{label}.txt").write_text(p.stdout+p.stderr)
    if p.returncode != expect:
        raise RuntimeError(f"{label} exit {p.returncode}: {p.stderr}")
    return p.stdout+p.stderr


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=('safe','deep'), default='deep')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.out.resolve()
    if not OUT.is_relative_to(HERE):
        parser.error('Verification output must stay in Stage 2a')
    OUT.mkdir(parents=True,exist_ok=True)
    before = builder.protected()
    run([sys.executable,"-I","-B",HERE/"tools/build.py",'--variant',args.variant,'--out',OUT],"build-results")
    run([sys.executable,"-I",HERE/"tools/make_recipes.py",HERE/"tools/example_recipes.json",
         "--output",OUT/"RECIPES0.DAT"],"recipe-generator-results")
    run([sys.executable,"-I",HERE/"tools/make_recipes.py",HERE/"tools/validation_recipes_16.json",
         "--output",OUT/"validation-RECIPES0.DAT"],"validation-recipe-generator-results")
    for prefix in ("", "validation-"):
        run([sys.executable,"-I",HERE/"tools/make_recipes.py","--import-v1",OUT/f"{prefix}RECIPES0.DAT",
             "--output",OUT/f"{prefix}RECIPE20.DAT"],f"{prefix}migration-results")
    sources = [HERE/"tests/test_host.c",HERE/"ui.c",HERE/"platform.c",HERE/"deep_isp.c",HERE/"deep_tables.c"] + [HERE/"recipe_v1"/name for name in
               ("recipe_format.c","recipe_store.c","recipe_apply.c")]
    common = ["clang","-std=c11","-O1","-g","-Wall","-Wextra","-Werror","-DRECIPE_FW_HOST",
              f"-DRFW_DEEP_ENABLED={int(args.variant == 'deep')}","-I",HERE]
    host = []
    for name,flags in (("host",[]),("sanitizers",["-fsanitize=address,undefined","-fno-omit-frame-pointer"])):
        executable = OUT/f"test_{name}"
        run([*common,*flags,*sources,"-o",executable],f"{name}-compile")
        bank = 'DEEPISP0.DAT' if args.variant == 'deep' else 'RECIPE20.DAT'
        log = run([executable,OUT/"RECIPE20.DAT",OUT/"validation-RECIPE20.DAT",HERE/'examples'/bank,
                   HERE/'examples/RECIPES0.DAT'],f"{name}-results")
        count = int(re.search(r"RESULT (\d+) cases passed",log)[1])
        host.append({"mode":name,"cases":count,"pass":True})
    run([sys.executable,"-I",HERE/"tests/test_abi.py",OUT],"abi-results")
    tool_log = run([sys.executable,"-I",HERE/"tests/test_tools.py"],"tools-results")
    tool_cases = int(re.search(r"Ran (\d+) tests",tool_log)[1])
    # A separate target object measures target sizes without adding globals.
    run([builder.GCC,"-std=c11","-Os","-ffreestanding","-fno-builtin","-fno-common","-m32r",
         "-mmodel=large","-msdata=none","-G0","-I",HERE,"-c",HERE/"tests/layout.c",
         "-o",OUT/"layout.o"],"layout-compile")
    obj = builder.Elf(OUT/"layout.o")
    symbol = obj.symbols["rfw_layout"]
    section = obj.sections[symbol["section"]]
    values = struct.unpack_from(">7I",obj.content(section),symbol["value"])
    layout = dict(zip(("cache_bytes","bank_bytes","recipe_bytes","bank_offset","scratch_offset","busy_offset","applied_slot_offset"),values))
    rejections = []
    for section in ("data","bss","mystery"):
        source, object_path = OUT/f"reject-{section}.S",OUT/f"reject-{section}.o"
        source.write_text(".text\n.align 2\n.global ricoh_recipe_open\nricoh_recipe_open:\n jmp lr\n nop\n"
                          + f".section .{section},\"aw\"\n.space 4\n")
        run([builder.BIN/"m32r-elf-as","-m32r","-EB",source,"-o",object_path],f"reject-{section}-assemble")
        log = run([builder.BIN/"m32r-elf-ld","--no-undefined","--orphan-handling=error","-T",HERE/"payload.ld",
                   object_path,"-o",OUT/f"reject-{section}.elf"],f"reject-{section}-link",1)
        expected = "Mutable globals and runtime sections are forbidden" if section != "mystery" else "unplaced orphan section"
        if expected not in log: raise ValueError("rejected for unexpected reason")
        rejections.append({"case":f"reject_{section}","pass":True,"reason":expected})
    run([sys.executable,"-I",HERE/"tools/build.py","--base","0x20052770","--capacity","8336",
         '--variant',args.variant,"--out",OUT/"relocated"],"relocated-build-results")
    relocated = json.loads((OUT/"relocated/manifest.json").read_text())
    manifest = json.loads((OUT/"manifest.json").read_text())
    assert relocated["payload_bytes"] == manifest["payload_bytes"]
    assert relocated["payload_base"] == "0x20052770"
    for key in ("va_start","va_end_exclusive","file_offset","length","integration_writes"):
        assert relocated["probe"][key] == manifest["probe"][key]
    assert relocated["probe"]["additional_free_bytes_before_tail"] == manifest["probe"]["additional_free_bytes_before_tail"] - 4
    log = run([sys.executable,"-I",HERE/"tools/build.py","--base","0x30000000",
               '--variant',args.variant,"--out",OUT/"out-of-range"],"out-of-range-results",1)
    if "branch out of range" not in log: raise ValueError("far base did not fail distance guard")
    assert not (OUT/"out-of-range/payload.elf").exists()
    rejections.append({"case":"reject_far_base_before_link","pass":True})
    log = run([sys.executable,"-I",HERE/"tools/build.py","--probe-reserve","2048",
               '--variant','deep',"--out",OUT/"oversize"],"oversize-results",1)
    if "payload exceeds reserved capacity before link" not in log: raise ValueError("reserve overflow was accepted")
    rejections.append({"case":"reject_probe_overlap_before_link","pass":True})
    assert builder.protected() == before
    abi = json.loads((OUT/"abi-tests.json").read_text())
    report = {"variant":args.variant,"host":host,"abi_model_cases":abi["cases"],"tool_cases":tool_cases,"rejections":rejections,
              "target_layout":layout,"relocated_base_verified":True,"protected_inputs":len(before),
              "protected_inputs_unchanged":True,"payload_sha256":manifest["payload_sha256"],
              "inputs_sha256":{str(path.relative_to(ROOT)):builder.sha(path.read_bytes()) for path in
                  sources+[HERE/"recipe_fw.h",HERE/"foreign.h",HERE/"deep_isp.h",HERE/"tools/verify.py",
                           HERE/"tests/test_deep.inc",HERE/"tests/test_abi.py",HERE/"tests/test_tools.py",
                           HERE/"examples/DEEPISP0.DAT",HERE/"examples/deep_inputs.json",
                           HERE/"examples/RECIPE20.DAT",HERE/"examples/canonical_surface.json",
                           HERE/"examples/RECIPES0.DAT",HERE/"examples/canonical_v1_fallback.json"]},
              "camera_executed":False,"upgrade_package_generated":False}
    builder.save_json(OUT/"verification.json",report)
    print(json.dumps(report,ensure_ascii=False))


if __name__ == "__main__":
    main()
