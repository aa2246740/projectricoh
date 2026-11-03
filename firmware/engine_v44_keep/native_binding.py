"""Integration binding for the exact v3.6 body and packaged gen 117.

Imports tools/native_harness read-only. The body and the DAT are this
round's artifacts. Native UI bytes are written by the image, except the
labelled negative that forces RV_CHECK_UI.
"""
import hashlib
import json
import struct
import zlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/native_harness"))

import field_replay as fr
import harness as harness_mod
import product_execute as pe
from harness import Harness
from image_loader import Elf, Image
import python_backend
python_backend.CACHE = Path(__file__).resolve().parent / "local/integration/decode"
from python_backend import PythonBackend

BODY = ROOT / "firmware/image_v36/local/package/SD_ROOT/ilaunch3"
BODY_SHA = "50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008"
DAT = ROOT / "firmware/package_v36_g117/SD_ROOT/GXRCE.DAT"
RESIDENT_ELF = ROOT / "firmware/resident_v36/local/resident/build/resident.elf"
ENGINE_ELF = ROOT / "firmware/engine_v44_keep/candidate/local/full-r13/engine.elf"
ROOT_ADDR = pe.ROOT_ADDR
READY = 3


class V35Harness(Harness):
    def __init__(self, body=BODY, backend_factory=PythonBackend):
        self.b = backend_factory()
        self.image = Image(body, BODY_SHA)
        self.image.verify_csv()
        self.image.load(self.b)
        self.b.map(0x206e0000, bytes(0x20000))
        self.b.map(0x20704800, bytes(0x40000))
        self.b.map(0x20020000, bytes(0x4000))
        self.b.set_reg("r15", 0x206ffff0)
        self.writes, self.calls, self.stub_hits = [], [], {}
        self.phase = "setup"
        self.b.add_write_trace(0, 2**32, self.trace)
        self.symbols = Elf(RESIDENT_ELF).symbols
        self.install_native_boundaries()
        self.b.breakpoints.pop(0x20271fec, None)
        self.settings = self.u(0x200c0dac)
        self.b.map(self.settings, bytes([1]) * 4096)
        self.phase = "model:settings_input"
        for off, value in ((988, 1), (926, 2), (1513, 3), (1514, 4), (1515, 8)):
            self.put(self.settings + off, value, 1)
        self.b.map(0x206b0000, self.settings.to_bytes(4, "big"))
        self.b.set_reg("r8", 0x206b0000)
        self.run_slice(0x202aaef4, 0x202aaf54)
        self.model_font_refs()

