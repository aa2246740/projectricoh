#!/usr/bin/env python3
"""Exercise report classification only; fixtures do not claim compiler execution."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("switch_package_gate", HERE / "package_fix.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def fixture(*, sanitizers=False, daily=False):
    label = "daily-sweep" if daily else "fixed-stage2l"
    report = json.loads((HERE / "local" / label / "results.json").read_text())
    report["bank_sha256"] = gate.BANK_SHA
    report["sources_sha256"]["research/switch_residue/reproduce.py"] = "0" * 64
    report["sanitizers"] = sanitizers
    report["compiler_args"] = ["clang", "-DRECIPE_FW_HOST", "-DRFW_DEEP_ENABLED=1"]
    if sanitizers:
        report["compiler_args"] += ["-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"]
    report["executable_sha256"] = "0" * 64
    return report


def main():
    checks = []
    for daily in (False, True):
        for sanitizers in (False, True):
            report = fixture(sanitizers=sanitizers, daily=daily)
            keys = set(report["sources_sha256"])
            gate.validate_report(report, sanitizers=sanitizers, daily=daily, expected_keys=keys)
            checks.append(f"accepted schema: daily={daily}, sanitizers={sanitizers}")
    def reject(name, change, *, sanitizers=False, daily=False):
        report = fixture(sanitizers=sanitizers, daily=daily)
        keys = set(report["sources_sha256"])
        change(report)
        try:
            gate.validate_report(report, sanitizers=sanitizers, daily=daily, expected_keys=keys)
        except (AssertionError, KeyError):
            checks.append(name)
        else:
            raise AssertionError(f"accepted malformed report: {name}")
    # R1's actual bug: a plain report copied to a sanitizer directory.
    reject("plain host relabeled as sanitizer", lambda r: r.update(sanitizers=False), sanitizers=True)
    reject("plain sweep relabeled as sanitizer", lambda r: r.update(sanitizers=False), sanitizers=True, daily=True)
    reject("sanitizer flag without compiler instrumentation", lambda r: r.update(compiler_args=["clang", "-DRECIPE_FW_HOST", "-DRFW_DEEP_ENABLED=1"]), sanitizers=True)
    reject("wrong production tree", lambda r: r.update(source="firmware/stage2j"))
    reject("wrong card table", lambda r: r.update(table_sha256=gate.DAILY_TABLE_SHA))
    reject("wrong recipe bank", lambda r: r.update(bank_sha256="0" * 64))
    for key in ("research/switch_residue/reproduce.py", "research/switch_residue/reproduce.c",
                "firmware/stage2l_switch/recipe_fw.h", "firmware/stage2l_switch/tests/test_host.c"):
        reject("missing identity: " + key, lambda r, k=key: r["sources_sha256"].pop(k))
    reject("extra source outside expected set", lambda r: r["sources_sha256"].update({"../other.c": "0" * 64}))
    reject("false per-case result with green total", lambda r: r["cases"][0].update(check_passed=False))
    reject("duplicate case with green total", lambda r: r["cases"].__setitem__(0, deepcopy(r["cases"][1])))
    reject("failure published new slot", lambda r: r["cases"][0].update(applied_slot=4))
    reject("sweep omits slot pairs", lambda r: r["cases"][0].update(ordered_pairs=63), daily=True)
    result = {"evidence": "REPORT_GATE_FIXTURES_ONLY_NO_COMPILATION", "checks_passed": len(checks), "checks": checks}
    (HERE / "local/package-gate-r2.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
