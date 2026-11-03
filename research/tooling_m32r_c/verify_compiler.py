#!/usr/bin/env python3
"""Compile and inspect a freestanding M32R object without executing it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifacts/recipe-core/m32r"
EVIDENCE = HERE / "evidence"
GCC = HERE / "prefix/gcc/bin/m32r-elf-gcc"
CC1 = HERE / "prefix/gcc/libexec/gcc/m32r-elf/13.4.0/cc1"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
OBJCOPY = ROOT / "research/tooling_m32r_asm/prefix/bin/m32r-elf-objcopy"
AS = ROOT / "research/tooling_m32r_asm/prefix/bin/m32r-elf-as"
LD = ROOT / "research/tooling_m32r_asm/prefix/bin/m32r-elf-ld"
SOURCE = HERE / "tiny-core.c"
CORE_DIR = ROOT / "firmware/recipe_core"
CORE_SOURCE = CORE_DIR / "recipe_core.c"
FLAGS = [
    "-std=c11",
    "-Os",
    "-ffreestanding",
    "-fno-builtin",
    "-fno-stack-protector",
    "-fno-common",
    "-fno-pic",
    "-m32r",
    "-Wall",
    "-Wextra",
    "-Werror",
]


def run(command: list[str], *, stdin: str | None = None) -> str:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
    ).stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compile_unit(
    name: str,
    source: Path,
    include_dirs: list[Path],
    *,
    require_no_undefined: bool,
) -> dict[str, object]:
    object_file = OUTPUT / f"{name}.o"
    assembly = OUTPUT / f"{name}.s"
    binary = OUTPUT / f"{name}.text.bin"
    include_flags = [item for path in include_dirs for item in ("-I", str(path))]
    unit_flags = [*FLAGS, *include_flags]
    compile_command = [
        str(GCC),
        *unit_flags,
        "-fstack-usage",
        "-c",
        str(source),
        "-o",
        str(object_file),
    ]
    assembly_command = [
        str(GCC),
        *unit_flags,
        "-S",
        str(source),
        "-o",
        str(assembly),
    ]
    run(compile_command)
    run(assembly_command)

    elf = object_file.read_bytes()
    if elf[:4] != b"\x7fELF" or elf[4] != 1 or elf[5] != 2:
        raise ValueError(f"{name} is not 32-bit big-endian ELF")
    machine = struct.unpack_from(">H", elf, 18)[0]
    if machine != 88:
        raise ValueError(f"unexpected ELF machine for {name}: {machine}")

    headers = run([str(OBJDUMP), "-f", "-h", str(object_file)])
    disassembly = run([str(OBJDUMP), "-dr", str(object_file)])
    symbols = run([str(OBJDUMP), "-t", str(object_file)])
    (OUTPUT / f"{name}.headers.txt").write_text(headers, encoding="utf-8")
    (OUTPUT / f"{name}.disasm.txt").write_text(disassembly, encoding="utf-8")
    (OUTPUT / f"{name}.symbols.txt").write_text(symbols, encoding="utf-8")

    text_match = re.search(r"^\s*\d+\s+\.text\s+([0-9a-fA-F]+)\s", headers, re.MULTILINE)
    if not text_match:
        raise ValueError(f"objdump did not report a .text section for {name}")
    text_size = int(text_match.group(1), 16)
    if text_size == 0:
        raise ValueError(f"compiler emitted an empty .text section for {name}")
    undefined = sorted(
        line.split()[-1]
        for line in symbols.splitlines()
        if "*UND*" in line and line.split()
    )
    if require_no_undefined and undefined:
        raise ValueError(f"unexpected undefined symbols for {name}: {undefined}")

    run(
        [
            str(OBJCOPY),
            "-O",
            "binary",
            "--only-section=.text",
            str(object_file),
            str(binary),
        ]
    )
    if binary.stat().st_size != text_size:
        raise ValueError(f"raw .text size does not match for {name}")

    stack_usage = OUTPUT / f"{name}.su"
    if not stack_usage.is_file() or not stack_usage.read_text(encoding="utf-8").strip():
        raise ValueError(f"GCC did not emit stack usage data for {name}")

    return {
        "input": {
            "path": str(source.relative_to(ROOT)),
            "sha256": sha256(source),
        },
        "flags": unit_flags,
        "compile_command": compile_command,
        "assembly_command": assembly_command,
        "object": {
            "path": str(object_file.relative_to(ROOT)),
            "sha256": sha256(object_file),
            "elf_class": 32,
            "endianness": "big",
            "machine": machine,
            "text_size": text_size,
            "undefined_symbols": undefined,
        },
        "assembly": str(assembly.relative_to(ROOT)),
        "text_binary": {
            "path": str(binary.relative_to(ROOT)),
            "sha256": sha256(binary),
            "size": binary.stat().st_size,
        },
        "stack_usage": str(stack_usage.relative_to(ROOT)),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for tool in (GCC, CC1, OBJDUMP, OBJCOPY, AS, LD):
        if not tool.is_file():
            raise FileNotFoundError(tool)

    tiny_result = compile_unit(
        "tiny-core", SOURCE, [], require_no_undefined=True
    )
    core_result = compile_unit(
        "recipe_core", CORE_SOURCE, [CORE_DIR], require_no_undefined=False
    )
    core_result["headers"] = [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256(path),
        }
        for path in (CORE_DIR / "recipe_core.h", CORE_DIR / "recipe_storage.h")
    ]

    macros = run([str(GCC), *FLAGS, "-dM", "-E", "-"], stdin="")
    (EVIDENCE / "predefined-macros.txt").write_text(macros, encoding="utf-8")
    required_macros = ["#define __M32R__ 1", "#define __BIG_ENDIAN__ 1"]
    missing_macros = [macro for macro in required_macros if macro not in macros]
    if missing_macros:
        raise ValueError(f"missing target macros: {missing_macros}")

    gcc_version = run([str(GCC), "--version"]).splitlines()[0]
    target = run([str(GCC), "-dumpmachine"]).strip()
    if target != "m32r-elf":
        raise ValueError(f"unexpected GCC target: {target}")
    verbose = subprocess.run(
        [str(GCC), "-v"], check=True, capture_output=True, text=True
    )
    (EVIDENCE / "gcc-version.txt").write_text(
        verbose.stdout + verbose.stderr, encoding="utf-8"
    )

    result = {
        "compiler": {
            "path": str(GCC.relative_to(ROOT)),
            "version": gcc_version,
            "target": target,
            "sha256": sha256(GCC),
            "cc1": {
                "path": str(CC1.relative_to(ROOT)),
                "sha256": sha256(CC1),
            },
            "assembler": {
                "path": run([str(GCC), "-print-prog-name=as"]).strip(),
                "sha256": sha256(AS),
            },
            "linker": {
                "path": run([str(GCC), "-print-prog-name=ld"]).strip(),
                "sha256": sha256(LD),
            },
        },
        "units": {
            "tiny_core": tiny_result,
            "recipe_core": core_result,
        },
        "limits": [
            "The object is not integrated into Ricoh firmware.",
            "The GCC target ABI has not been matched to the camera ABI.",
            "The object is never executed.",
            "No camera update package is produced.",
        ],
    }
    manifest = EVIDENCE / "verification.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "compiler": gcc_version,
        "target": target,
        "tiny_text_size": tiny_result["object"]["text_size"],
        "recipe_core_text_size": core_result["object"]["text_size"],
        "recipe_core_undefined_symbols": core_result["object"]["undefined_symbols"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
