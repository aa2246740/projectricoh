#!/usr/bin/env python3
"""Recompile submitted research size samples, never link an image or DAT."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as v

def sections(path):
    b = path.read_bytes()
    assert b[:4] == b"\x7fELF" and b[4:6] == bytes((1, 2))
    off = int.from_bytes(b[32:36], "big")
    ent, n, names = struct.unpack_from(">3H", b, 46)
    rows = [struct.unpack_from(">10I", b, off+i*ent) for i in range(n)]
    names_raw = b[rows[names][4]:rows[names][4]+rows[names][5]]
    result = []
    for row in rows:
        name = names_raw[row[0]:].split(b"\0", 1)[0].decode()
        result.append(dict(name=name, kind=row[1], flags=row[2], address=row[3], offset=row[4], size=row[5]))
    return result

def main():
    v.preflight()
    gcc = v.ROOT / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
    assert v.sha(gcc) == "4864b9476b06cd488292c9937ddb92b021605e89ccd06a859f5d4146b46393de"
    tmp = v.OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(tmp))
    flags = ["-std=c11", "-Os", "-fomit-frame-pointer", "-ffreestanding", "-fno-builtin",
             "-fno-stack-protector", "-fno-common", "-fno-pic", "-m32r", "-mmodel=large",
             "-msdata=none", "-G0", "-Wall", "-Wextra", "-Werror", "-fno-unwind-tables",
             "-fno-asynchronous-unwind-tables", "-fstack-usage", "-ffunction-sections", "-fdata-sections"]
    result = []
    for name, opts in (("bridge_sizing.c", flags), ("bridge_trampoline.S", ["-m32r"])):
        src = v.ROOT / "research/body_v4_storage/gpt" / name
        obj = v.OUT / (Path(name).stem + ".o")
        cmd = [str(gcc), *opts, "-c", str(src), "-o", str(obj)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=v.OUT)
        (v.OUT / (Path(name).stem + ".compiler.stdout")).write_text(r.stdout)
        (v.OUT / (Path(name).stem + ".compiler.stderr")).write_text(r.stderr)
        assert r.returncode == 0, r.stderr
        sec = sections(obj)
        result.append(dict(source=str(src.relative_to(v.ROOT)), source_sha256=v.sha(src),
                           object=str(obj.relative_to(v.ROOT)), object_sha256=v.sha(obj), command=cmd,
                           sections=sec, code=sum(x["size"] for x in sec if x["flags"] & 2 and x["kind"] == 1),
                           bss=sum(x["size"] for x in sec if x["flags"] & 2 and x["kind"] == 8)))
    v.save("size-rerun.json", dict(status="PASS_RELOCATABLE_SAMPLES_ONLY", compiler_sha256=v.sha(gcc),
                                 objects=result, limits="Native ports, other hooks and final link remain absent. Objects are size samples, not product artifacts."))
    print(json.dumps([{k:r[k] for k in ("source", "code", "bss", "object_sha256")} for r in result]))

if __name__ == "__main__":
    main()
