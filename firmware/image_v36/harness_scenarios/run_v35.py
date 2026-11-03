"""Body-only scenarios for resident v3.6 and unchanged gen 116 engine.

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

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/native_harness"))

import field_replay as fr
import harness as harness_mod
import product_execute as pe
from harness import Harness
from image_loader import Elf, Image
from python_backend import PythonBackend

BODY = ROOT / "firmware/image_v36/local/package/SD_ROOT/ilaunch3"
BODY_SHA = "50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008"
DAT = ROOT / "firmware/image_v35/local/package/SD_ROOT/GXRCE.DAT"
RESIDENT_ELF = ROOT / "firmware/resident_v36/local/resident/build/resident.elf"
ENGINE_ELF = ROOT / "firmware/engine_v37/candidate/local/full-r13/engine.elf"
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
        self.settings = self.u(0x200c0dac)
        self.b.map(self.settings, bytes([1]) * 4096)
        self.phase = "model:settings_input"
        for off, value in ((988, 1), (926, 2), (1513, 3), (1514, 4), (1515, 8)):
            self.put(self.settings + off, value, 1)
        self.b.map(0x206b0000, self.settings.to_bytes(4, "big"))
        self.b.set_reg("r8", 0x206b0000)
        self.run_slice(0x202aaef4, 0x202aaf54)
        self.model_font_refs()


def bind():
    if hashlib.sha256(DAT.read_bytes()).hexdigest() != "1e033dfbcc3ca0bec0e1e5befbdb5579950e9aa8aacfbfd56f8c7342b9a97864":
        raise SystemExit("GXRCE.DAT sha changed")
    harness_mod.Harness = V35Harness
    pe.STAGED = DAT
    pe.STAGED_SHA = hashlib.sha256(DAT.read_bytes()).hexdigest()
    pe.ENGINE_ELF = ENGINE_ELF
    trust = json.loads((ROOT / "firmware/resident_v36/local/resident/trust.json").read_text())
    old_edge = pe.FileEdge
    class BodyTestFileEdge(old_edge):
        def __init__(self, dat):
            assert dat[80:112].hex() == "9cc5359e073a3b65a223ca3af41055fd10e52b5e701db1fe08426023aea731ba"
            assert dat[212:228].hex() == trust["resident_abi_id"]
            model = bytearray(dat)
            model[80:112] = bytes.fromhex(trust["resident_build_id"])
            struct.pack_into(">I", model, 20, 0)
            struct.pack_into(">I", model, 20, zlib.crc32(model[:256]) & 0xffffffff)
            assert model[256:] == dat[256:]
            super().__init__(bytes(model))
    pe.FileEdge = BodyTestFileEdge
    elf = Elf(RESIDENT_ELF)
    fr.LAND = {
        elf.symbols["rv_skip_06"]: "h06_skip",
        elf.symbols["rv_close_07"]: "h07_close",
        elf.symbols["rv_skip_08"]: "h08_skip",
        0x202871dc: "native_setter",
        0x20268768: "native_setter_store",
        0x20268774: "native_row_store",
        0x202688d4: "native_row_compare",
    }
    fr.OBSERVE = elf.symbols["rv_hook_observe"]


def mode(h):
    return fr.settings_byte(h)[1]


def lands(rows):
    return [name for row in rows for name in row["land"]]


def fail(name, detail):
    print("FAIL", name, detail)
    return False


def boot(*args, **kwargs):
    """The body reads BSS 0x200d7fd8 itself. The harness stub at 0x2009359c
    is not on that path, so the scenario publishes the same word the lens task
    writes."""
    h, product, watch = fr.boot(*args, **kwargs)
    if product.ready:
        h.put(0x200d7fd8, 1)
    return h, product, watch


def ok_then_menu():
    h, product, watch = boot()
    opened, _, error = fr.publish(h, product, watch)
    if error or not opened["ok"] or fr.u8(h, 0x2022f5ac) != 8:
        return fail("ok_then_menu", error or opened)
    fr.preset_mode(h, 9)
    at = watch.mark()
    ok = fr.press(h, 0x23)
    ok_rows = watch.since(at)
    if not ok["ok"] or mode(h) != 1 or "h07_close" not in lands(ok_rows) or "native_setter" in lands(ok_rows):
        return fail("ok_then_menu", ("ok", ok["ok"], mode(h), lands(ok_rows)))
    at = watch.mark()
    menu = fr.press(h, 0x29)
    menu_rows = watch.since(at)
    if not menu["ok"] or mode(h) != 1 or "h07_close" not in lands(menu_rows) or "native_setter" in lands(menu_rows):
        return fail("ok_then_menu", ("menu", menu["ok"], mode(h), lands(menu_rows)))
    print("PASS ok_then_menu mode", mode(h))
    return True


def fn2_then_ok():
    h, product, watch = boot()
    opened, _, error = fr.publish(h, product, watch)
    if error or not opened["ok"]:
        return fail("fn2_then_ok", error or opened)
    fn = fr.native(h, 0x202be220)
    if not fn["ok"]:
        return fail("fn2_then_ok", fn)
    fr.preset_mode(h, 9)
    at = watch.mark()
    ok = fr.press(h, 0x23)
    rows = watch.since(at)
    if not ok["ok"] or mode(h) != 1 or "native_setter" in lands(rows) or "h07_close" not in lands(rows):
        return fail("fn2_then_ok", (ok["ok"], mode(h), lands(rows)))
    print("PASS fn2_then_ok mode", mode(h))
    return True


def inflight_h07():
    h, product, watch = boot()
    opened, _, error = fr.publish(h, product, watch)
    if error or not opened["ok"] or fr.u8(h, ROOT_ADDR + 5) != READY:
        return fail("inflight_h07", error or opened)
    h.put(ROOT_ADDR + 6, 1, 1)
    fr.preset_mode(h, 9)
    at = watch.mark()
    pressed = fr.press(h, 0x23)
    rows = watch.since(at)
    diag = fr.u32(h, ROOT_ADDR + 232)
    if not pressed["ok"] or mode(h) != 9 or "h07_close" not in lands(rows) or "native_setter" in lands(rows):
        return fail("inflight_h07", (pressed["ok"], mode(h), lands(rows), hex(diag)))
    if (diag & 0xffff) != (7 | (3 << 8)):
        return fail("inflight_h07", ("diag", hex(diag)))
    print("PASS inflight_h07 diag", hex(diag))
    return True


def check_ui_retire():
    h, product, watch = boot()
    opened, _, error = fr.publish(h, product, watch)
    if error or not opened["ok"]:
        return fail("check_ui_retire", error or opened)
    root = fr.root_fields(h)
    if not root["ui_block"]:
        return fail("check_ui_retire", "no ui block")
    h.put(root["ui_block"] + 1960, fr.u32(h, root["ui_block"] + 1960) ^ 1)
    fr.preset_mode(h, 9)
    at = watch.mark()
    pressed = fr.press(h, 0x23)
    rows = watch.since(at)
    if "h07_close" not in lands(rows) or "native_setter" in lands(rows):
        return fail("check_ui_retire", lands(rows))
    if fr.u8(h, ROOT_ADDR + 5) != 6 or fr.u32(h, ROOT_ADDR + 152) != 7:
        return fail("check_ui_retire", (fr.u8(h, ROOT_ADDR + 5), fr.u32(h, ROOT_ADDR + 152)))
    if mode(h) != 9:
        return fail("check_ui_retire", ("mode", mode(h)))
    print("PASS check_ui_retire", "call", pressed["ok"])
    return True


def retry_28mm():
    h, product, watch = boot("28mm", ready=0, link=1)
    first = fr.open_settings(h)
    state, flags, rows = fr.u8(h, ROOT_ADDR + 5), fr.u32(h, ROOT_ADDR + 212), fr.u8(h, 0x2022f5ac)
    if not first["ok"] or state != 0 or (flags & 32) or rows == 8:
        return fail("retry_28mm", ("first", first["ok"], state, flags, rows))
    product.ready = 1
    h.put(0x200d7fd8, 1)
    second = fr.open_settings(h)
    if not second["ok"] or fr.u8(h, ROOT_ADDR + 5) != READY or fr.u8(h, 0x2022f5ac) != 8:
        return fail("retry_28mm", ("second", second["ok"], fr.u8(h, ROOT_ADDR + 5), fr.u8(h, 0x2022f5ac)))
    print("PASS retry_28mm rows", fr.u8(h, 0x2022f5ac))
    return True


def never_ready():
    h, product, watch = boot(ready=0, link=0)
    first = fr.open_settings(h)
    if fr.u8(h, ROOT_ADDR + 5) != 0 or (fr.u32(h, ROOT_ADDR + 212) & 0x80):
        return fail("never_ready", ("load", first["ok"], fr.u8(h, ROOT_ADDR + 5), fr.u32(h, ROOT_ADDR + 212)))
    fr.preset_mode(h, 9)
    at = watch.mark()
    pressed = fr.press(h, 0x23)
    rows = watch.since(at)
    if "h07_close" in lands(rows):
        return fail("never_ready", ("shielded", lands(rows)))
    if not pressed["ok"]:
        return fail("never_ready", pressed)
    print("PASS never_ready lands", lands(rows), "mode", mode(h))
    return True


def main():
    bind()
    checks = (ok_then_menu, fn2_then_ok, inflight_h07, check_ui_retire, retry_28mm, never_ready)
    results = [check() for check in checks]
    if not all(results):
        raise SystemExit(1)
    print("PASS v35 scenarios", len(checks))


if __name__ == "__main__":
    main()
