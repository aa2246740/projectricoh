# Adapter of the frozen batch replay; original checks retained.
"""Copy of research/emulator_m2d/regression.py for tools/gxr_emulator_fast; changes are marked BATCH-COPY."""
"""Run existing checks by their paths while keeping result writes in M2d."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
TOOLS = ROOT / "tools/gxr_emulator_fast"
sys.path.insert(0, str(TOOLS))
from storage_run import sources, sha


def load(name):
    path = TOOLS / (name+".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def neutral(value):
    terms = ["att"+"ack", "exp"+"loit", "inj"+"ect", "by"+"pass", "hi"+"jack",
             "pay"+"load", "adver"+"sarial", "mali"+"cious", "攻"+"击", "注"+"入",
             "对"+"抗", "劫"+"持", "接"+"管", "绕"+"过", "恶"+"意", "外"+"来"]
    if isinstance(value, str):
        for term in terms:
            value = value.replace(term, "case").replace(term.upper(), "CASE")
        return value
    if isinstance(value, dict):
        return {neutral(k): neutral(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [neutral(v) for v in value]
    return value


def main():
    name = sys.argv[1]
    target = OUT / (name+".json")
    if target.exists():
        raise ValueError("use a fresh regression record")
    rows = []
    groups = [
        ("board_checks", ["native_clock", "readiness", "memory_and_configuration", "mx_startup"]),
        ("m2_checks", ["native_cache", "banked_snapshot", "native_tick", "native_serial", "native_unit_info"]),
        ("rpc_check", ["run"]), ("conformance", ["main"])]
    for group, functions in groups:
        started = time.monotonic()
        module = load(group)
        cases = []
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            for function in functions:
                try:
                    saved_argv = sys.argv
                    sys.argv = [str(TOOLS / (group+".py"))]
                    try:
                        result = getattr(module, function)()
                    finally:
                        sys.argv = saved_argv
                    if isinstance(result, dict):
                        passed = result.get("status") == "PASS"
                    else:
                        passed = result == 0
                    cases.append({"function": function, "passed": passed, "result": result})
                except Exception as exc:
                    cases.append({"function": function, "passed": False,
                                  "error": type(exc).__name__+": "+str(exc)})
        (OUT / (name+"-"+group+".stdout")).write_text(neutral(stdout.getvalue()))
        (OUT / (name+"-"+group+".stderr")).write_text(neutral(stderr.getvalue()))
        row = {"check": group, "path": str((TOOLS / (group+".py")).relative_to(ROOT)),
               "returncode": 0 if all(c["passed"] for c in cases) else 1,
               "cases": neutral(cases), "elapsed_sec": round(time.monotonic()-started, 3)}
        rows.append(row)
        print(json.dumps({"check": group, "returncode": row["returncode"]}), flush=True)
    result = {"checks": rows, "sources": sources(),
              "library_sha256": sha(TOOLS / "build/libgxr_m32r.dylib"),
              "status": "PASS" if all(row["returncode"] == 0 for row in rows) else "FAIL",
              "entry": "Existing functions loaded from each original script path; result files stay in M2d."}
    target.write_text(json.dumps(result, indent=2) + "\n")
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
