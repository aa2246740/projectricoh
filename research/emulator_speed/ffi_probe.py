"""Calibrate empty native calls and the memory callback boundary, without a model."""
import ctypes as C
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from backend import BUS


def main():
    target = OUT / "libffi_probe.dylib"
    temporary = OUT / "temporary"
    environment = dict(os.environ, TMPDIR=str(temporary))
    object_file = OUT / "ffi_probe.o"
    subprocess.run(["/usr/bin/clang", "-O2", "-c", str(HERE / "ffi_probe.c"),
                    "-o", str(object_file)], check=True, env=environment)
    subprocess.run(["/usr/bin/clang", "-dynamiclib", str(object_file),
                    "-o", str(target)], check=True, env=environment)
    lib = C.CDLL(str(target))
    lib.read_value.argtypes = [C.c_void_p, C.c_int]
    lib.read_value.restype = C.c_uint64
    lib.one_step.argtypes = [C.c_void_p]
    lib.clear_cache.argtypes = [C.c_void_p]
    lib.call_bus.argtypes = [BUS, C.c_void_p, C.c_int]
    callback_count = [0]
    def received(context, pc, address, size, pointer, writing):
        callback_count[0] += 1
        return size
    callback = BUS(received)
    count = 200000
    rows = []
    functions = [("python_loop", lambda: None), ("register", lambda: lib.read_value(None, 0)),
                 ("step", lambda: lib.one_step(None)), ("flush", lambda: lib.clear_cache(None)),
                 ("bus_off", lambda: lib.call_bus(callback, None, 0)),
                 ("bus_on", lambda: lib.call_bus(callback, None, 1))]
    for repeat in range(5):
        for name, function in functions if repeat % 2 == 0 else reversed(functions):
            before = callback_count[0]
            start = time.perf_counter()
            for _ in range(count):
                function()
            elapsed = time.perf_counter() - start
            observed = callback_count[0] - before
            if observed != (count if name == "bus_on" else 0):
                raise RuntimeError("calibration callback work count differs")
            rows.append({"repeat": repeat, "kind": name, "count": count,
                         "seconds": elapsed, "seconds_per_call": elapsed / count})
    medians = {name: statistics.median(r["seconds_per_call"] for r in rows if r["kind"] == name)
               for name, _ in functions}
    medians["callback_delta"] = medians["bus_on"] - medians["bus_off"]
    result = {"rows": rows, "medians_seconds": medians,
              "compiler_TMPDIR": str(temporary), "object_file": str(object_file),
              "callback_count": callback_count[0], "expected_callbacks": 5 * count,
              "scope": "empty host-call calibration; no firmware or model execution"}
    (OUT / "ffi-calibration.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(medians))


if __name__ == "__main__":
    main()
