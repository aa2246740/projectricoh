#!/usr/bin/env python3
"""顺序重做本目录的静态证据，不执行目标固件。"""
import runpy
from pathlib import Path

OUT = Path(__file__).resolve().parent
runpy.run_path(str(OUT / "prepare_inputs.py"), run_name="__main__")
x = runpy.run_path(str(OUT / "audit.py"))
for name in ("jlaunch3", "ilaunch3", "jlaunch0"):
    x["full"](name)
runpy.run_path(str(OUT / "collect_evidence.py"), run_name="__main__")
runpy.run_path(str(OUT / "facts.py"), run_name="__main__")
tasks = [
    ("jlaunch3", "k2-k4-references", [0x201123B0, 0x201123D4, 0x201123EC,
         0x20255600, 0x20256988, 0xF0318000, 0xF0318004, 0xF0318008, 0xF031800C,
         0x200B81D4, 0x20022000]),
    ("jlaunch3", "k2-generic-entries", [0x20255740, 0x20255850, 0x20255964,
         0x20255A78, 0x20112394, 0x20065CA0, 0x2011A62C]),
    ("jlaunch3", "k2-mirror-references", [0x20141584, 0x20141588, 0x2014158C,
         0x20141590, 0x2029C364]),
    ("ilaunch3", "k2-body-register-references", [0xF0318000, 0xF0318004, 0xF0318008, 0xF031800C]),
    ("jlaunch0", "k2-boot-register-references", [0xF0318000, 0xF0318004, 0xF0318008, 0xF031800C]),
]
for name, label, targets in tasks:
    x["refs"](name, targets, label)
runpy.run_path(str(OUT / "scan_review.py"), run_name="__main__")
print("Static evidence refresh OK")
