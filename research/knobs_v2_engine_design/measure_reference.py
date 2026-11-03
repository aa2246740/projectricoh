#!/usr/bin/python3
"""测量既有参考源的目标对象和布局常量，不链接引擎。"""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LOCAL = OUT / "local"
GCC = ROOT / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
SOURCE = ROOT / "research/knobs_v2_r2/src/knobs.c"


def run(arguments):
    result = subprocess.run([str(a) for a in arguments], cwd=ROOT, text=True,
                            capture_output=True, timeout=60, check=False,
                            env={**os.environ, "TMPDIR": str(LOCAL / "tmp")})
    if result.returncode:
        raise RuntimeError("目标测量失败：" + result.stderr[-1000:])
    return result.stdout


def main():
    if not all(p.is_file() for p in (GCC, OBJDUMP)):
        raise SystemExit("项目内目标工具不完整")
    if run(["git", "check-ignore", "research/knobs_v2_engine_design/local/check.o"]).strip() == "":
        raise SystemExit("local 未被忽略")
    include = LOCAL / "include"
    include.mkdir(parents=True, exist_ok=True)
    (LOCAL / "tmp").mkdir(exist_ok=True)
    (include / "string.h").write_text(
        "#include <stddef.h>\n"
        "void *memcpy(void *, const void *, size_t);\n"
        "void *memmove(void *, const void *, size_t);\n"
        "int memcmp(const void *, const void *, size_t);\n")
    flags = ["-std=c11", "-Os", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
             "-fno-common", "-fpic", "-m32r", "-mmodel=medium", "-msdata=none", "-G0",
             "-fstack-usage", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
             "-fno-partial-inlining", "-fno-ipa-sra", "-fno-inline-small-functions"]
    target = LOCAL / "reference.o"
    run([GCC, *flags, "-I", include, "-c", SOURCE, "-o", target])
    undefined = [line.split()[-1] for line in run([OBJDUMP, "-t", target]).splitlines()
                 if "*UND*" in line]
    section_text = run([OBJDUMP, "-h", target])
    rows = []
    for line in (LOCAL / "reference.su").read_text().splitlines():
        fields = line.split("\t")
        rows.append({"function": fields[0].split(":")[-1], "bytes": int(fields[1]), "kind": fields[2]})
    probe = LOCAL / "layout_probe.c"
    probe.write_text(
        '#include "firmware/resident_v36/resident/loader.c"\n'
        "const uint32_t design_sizes[]={sizeof(RvSession),RV_BLOCK_OVERHEAD,"
        "RV_MAX_BLOCK_BYTES,sizeof(GxrceView),sizeof(RvUiSnapshot),sizeof(RvLoadWork)};\n")
    assembly = LOCAL / "layout_probe.s"
    run([GCC, *flags, "-I", ROOT, "-S", probe, "-o", assembly])
    tail = assembly.read_text().split("design_sizes:\n", 1)[1]
    size_lines = []
    for line in tail.splitlines():
        match = re.fullmatch(r"\s*\.(?:long|word)\s+(0x[0-9a-fA-F]+|[0-9]+)\s*", line)
        if not match:
            break
        size_lines.append(match.group(1))
    sizes = [int(x, 0) for x in size_lines]
    if len(sizes) != 6:
        raise ValueError("布局常量计数不符")
    report = {
        "scope": "既有参考源的独立目标对象；未链接实现，未测相机栈水位",
        "compiler_sha256": hashlib.sha256(GCC.read_bytes()).hexdigest(),
        "reader_sha256": hashlib.sha256(OBJDUMP.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "object_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "layout_assembly_sha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
        "flags": flags, "frames": rows, "undefined_symbols": undefined,
        "section_sizes": section_text.replace(str(ROOT) + "/", ""),
        "target_layout": dict(zip(("session_bytes", "main_overhead_bytes", "main_request_max_bytes",
                                   "view_bytes", "ui_snapshot_bytes", "loader_work_bytes"), sizes)),
    }
    (OUT / "reference_measurement.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("参考源目标帧与布局测量已写入 reference_measurement.json")
    print("最大单帧 " + str(max(row["bytes"] for row in rows)) + " B")


if __name__ == "__main__":
    main()
