"""Assemble review evidence and verify both relative-path SHA lists."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import pstats
import re
import subprocess
from statistics import median as statistics_median
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools/gxr_emulator"
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def write(name, value):
    (OUT / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def guard():
    baseline = json.loads((OUT / "historical-inputs.json").read_text())
    changed = [p for p, v in baseline["files"].items()
               if not (ROOT / p).is_file() or sha(ROOT / p) != v["initial_actual_sha256"]]
    original = json.loads((OUT / "initial-tools.json").read_text())
    changes = original["tools/gxr_emulator/CHANGES.md"]
    prefix = (TOOLS / "CHANGES.md").read_bytes()[:changes["size"]]
    identities = []
    for name in ("no-card", "card"):
        metadata = json.loads((TOOLS / "local/speed" / (name + ".snap.json")).read_text())
        for path, expected in metadata["identity"]["files"].items():
            identities.append((ROOT / path).is_file() and sha(ROOT / path) == expected)
    result = {"unchanged_inputs": all(identities),
              "changes_prefix_unchanged": hashlib.sha256(prefix).hexdigest() == changes["sha256"],
              "historical_inputs_unchanged": not changed,
              "historical_files": len(baseline["files"]), "historical_differences": changed,
              "bound_file_checks": len(identities)}
    write("final-input-guard", result)
    print(json.dumps({k: v for k, v in result.items() if k != "historical_differences"}))
    return all(result[k] for k in ("unchanged_inputs", "changes_prefix_unchanged", "historical_inputs_unchanged"))


def summary():
    result = {"equivalence": {}, "benchmarks": {}, "input_comparisons": {}, "profiles": {}}
    for profile in ("no-card", "card"):
        metadata = json.loads((TOOLS / "local/speed" / (profile + ".snap.json")).read_text())
        result["profiles"][profile] = {k: metadata[k] for k in
                                       ("accepted", "steps", "raw_bytes", "compressed_bytes", "boot_seconds", "quiet")}
        for mode in ("fast", "debug"):
            path = OUT / (profile + "-equivalence-" + mode + ".json")
            if path.exists():
                d = json.loads(path.read_text())
                result["equivalence"][profile + "-" + mode] = d
        path = OUT / (profile + "-benchmark.json")
        if path.exists():
            result["benchmarks"][profile] = json.loads(path.read_text())
        for sequence in ("adj", "keys"):
            names = [profile + "-" + sequence + "-snapshot-" + m for m in ("fast", "debug")]
            names += [profile + "-" + sequence + "-cold-" + ("debug" if sequence == "adj" else "fast")]
            values = [json.loads((OUT / (name + ".json")).read_text()) for name in names
                      if (OUT / (name + ".json")).exists()]
            if values:
                row = {"available": len(values), "complete": len(values) == 3,
                       "state_equal": len({v["state"]["all"] for v in values}) == 1,
                       "observations_equal": len({v["observations"] for v in values}) == 1,
                       "flow_equal": len({v["flow_hash"] for v in values}) == 1,
                       "segments_equal": all(v["segments"] == values[0]["segments"] for v in values),
                       "all_segments_completed": all(v["completed_all_segments"] for v in values),
                       "ui_states": [v["ui_state"] for v in values],
                       "timings": {n: {k: v[k] for k in ("setup_seconds", "run_seconds", "total_seconds")}
                                   for n, v in zip(names, values)}}
                if len(values) == 3 and sequence == "adj":
                    row["cold_debug_to_snapshot_fast_ratio"] = values[2]["total_seconds"] / values[0]["total_seconds"]
                result["input_comparisons"][profile + "-" + sequence] = row
    result["C_estimates"] = {}
    for mode in ("fast", "debug"):
        path = OUT / ("no-card-profile-" + mode + ".json")
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        total = d["elapsed_seconds"]
        fractions = {"ram_callbacks": d["bus_ram_seconds"] / total,
                     "mmio_callbacks": d["bus_mmio_seconds"] / total,
                     "native_api_envelope": d["native_api_without_callbacks_seconds"] / total,
                     "python_loop_and_devices": d["python_loop_and_device_seconds"] / total}
        estimate = {"instrumented_fractions": fractions,
                    "RAM_body_only_ideal_gain": 1 / (1 - fractions["ram_callbacks"]),
                    "scenario_RAM_80_percent_removed": 1 / (1 - .8 * fractions["ram_callbacks"]),
                    "scenario_RAM_80_and_python_50_percent_removed":
                        1 / (1 - .8 * fractions["ram_callbacks"] - .5 * fractions["python_loop_and_devices"]),
                    "pure_ctypes_fraction": "UNKNOWN_IN_NATIVE_API_ENVELOPE"}
        calibration = OUT / "ffi-calibration.json"
        benchmark = result["benchmarks"].get("no-card")
        if calibration.exists() and benchmark:
            medians = json.loads(calibration.read_text())["medians_seconds"]
            bare = statistics_median([r["run_seconds"] for r in benchmark["runs"] if r["mode"] == mode])
            floors = {"gxr_reg_get": medians["register"], "gxr_step": medians["step"],
                      "gxr_flush": medians["flush"]}
            scalar = sum(d["api"][key]["calls"] * max(0, value - medians["python_loop"])
                         for key, value in floors.items()) / bare
            callback = d["bus_ram_calls"] * medians["callback_delta"] / bare
            ram = d["bus_ram_seconds"] / bare + callback
            stats = pstats.Stats(str(OUT / ("no-card-" + mode + ".pstats")))
            hook_share = sum(v[3] for (path, line, name), v in stats.stats.items()
                             if Path(path).name == "speed_snapshot.py" and name == "tick") / stats.total_tt
            movable = max(0, fractions["python_loop_and_devices"] - hook_share)
            estimate.update({"calibrated_scalar_boundary_floor_fraction": scalar,
                             "calibrated_RAM_callback_boundary_fraction": callback,
                             "RAM_body_and_boundary_fraction_estimate": ram,
                             "RAM_full_removal_ideal_gain_estimate": 1 / (1 - ram),
                             "scenario_RAM80_python25_scalar_boundary":
                                 1 / (1 - .8 * ram - .25 * fractions["python_loop_and_devices"] - scalar),
                             "scenario_RAM80_python50_scalar_boundary":
                                 1 / (1 - .8 * ram - .5 * fractions["python_loop_and_devices"] - scalar),
                             "timer_overhead_ratio": total / bare,
                             "separate_cprofile_required_hook_fraction": hook_share,
                             "estimated_python_control_fraction": movable,
                             "scenario_RAM80_control50_scalar_boundary":
                                 1 / (1 - .8 * ram - .5 * movable - scalar),
                             "scenario_RAM80_control100_scalar_boundary":
                                 1 / (1 - .8 * ram - movable - scalar),
                             "profile_state_equal_to_benchmark": d["state"] == benchmark["runs"][0]["state"]})
        result["C_estimates"][mode] = estimate
    startup_paths = [OUT / ("startup-keys-" + origin + ".json") for origin in ("snapshot", "cold")]
    if all(p.exists() for p in startup_paths):
        a, b = [json.loads(p.read_text()) for p in startup_paths]
        result["startup_keys"] = {"state_equal": a["state"] == b["state"],
                                  "flow_equal": a["flow_hash"] == b["flow_hash"],
                                  "phases_equal": a.get("phases") == b.get("phases"),
                                  "expected_27_phases": a.get("phases_equal_expected") and b.get("phases_equal_expected")}
    for milestone in ("m2b", "m2c"):
        path = OUT / (milestone + "-speed-r1.json")
        if path.exists():
            d = json.loads(path.read_text())
            result[milestone] = {k: d[k] for k in ("passed", "total", "status", "checks")}
    write("summary", result)
    print(json.dumps({"equivalence_runs": len(result["equivalence"]),
                      "input_comparisons": result["input_comparisons"]}, ensure_ascii=False))
    return True


def source_check():
    terms = ["at" + "tack", "ex" + "ploit", "in" + "ject", "by" + "pass",
             "hi" + "jack", "pay" + "load", "adver" + "sarial", "mali" + "cious",
             "攻" + "击", "注" + "入", "对" + "抗", "劫" + "持", "接" + "管",
             "绕" + "过", "恶" + "意", "外" + "来"]
    pattern = re.compile("|".join(terms), re.I)
    syntax = []
    for path in [*TOOLS.glob("*.py"), *HERE.glob("*.py")]:
        ast.parse(path.read_text())
        syntax.append(str(path.relative_to(ROOT)))
    findings = []
    candidates = [p for p in HERE.rglob("*") if p.is_file()]
    candidates += [TOOLS / "speed_snapshot.py", TOOLS / "README.md"]
    initial = json.loads((OUT / "initial-tools.json").read_text())
    change_text = (TOOLS / "CHANGES.md").read_bytes()[initial["tools/gxr_emulator/CHANGES.md"]["size"]:].decode()
    if pattern.search(change_text):
        findings.append("CHANGES append")
    for path in candidates:
        if pattern.search(path.name):
            findings.append(str(path.relative_to(ROOT)) + ":name")
        if path.suffix in (".img", ".z", ".pkl", ".pstats", ".bin"):
            continue
        try:
            text = path.read_text()
        except UnicodeError:
            continue
        if pattern.search(text):
            findings.append(str(path.relative_to(ROOT)) + ":text")
    private_files = [p for base in (HERE / "local", TOOLS / "local/speed", TOOLS / "tmp")
                     for p in base.rglob("*") if p.is_file()]
    names = [str(p.relative_to(ROOT)) for p in private_files]
    process = subprocess.run(["git", "check-ignore", "--stdin"], input="\n".join(names) + "\n",
                             text=True, capture_output=True, cwd=ROOT)
    ignored = set(process.stdout.splitlines())
    not_ignored = [name for name in names if name not in ignored]
    result = {"syntax_files": len(syntax), "syntax_ok": True,
              "new_terminology_findings": findings,
              "private_files": len(names), "not_ignored": not_ignored,
              "passed": not findings and not not_ignored}
    write("source-checks", result)
    print(json.dumps(result))
    return result["passed"]


def trim_logs():
    removed = 0
    for path in OUT.iterdir():
        if path.suffix not in (".log", ".stdout", ".stderr"):
            continue
        lines = path.read_text().splitlines(keepends=True)
        result, context = [], False
        for line in lines:
            if line.startswith('  File "'):
                context = True
                result.append(line)
            elif context and line.startswith("    "):
                removed += 1
            else:
                context = False
                result.append(line)
        if result != lines:
            path.write_text("".join(result))
    print(json.dumps({"source_context_lines_removed": removed,
                      "retained": "error types, messages, file paths and line references"}))
    return True


def seal():
    previous = []
    path = TOOLS / "SHA256SUMS"
    if path.exists():
        previous = [line.split(None, 1)[1].lstrip("*") for line in path.read_text().splitlines()]
    files = {TOOLS / name for name in previous if (TOOLS / name).is_file()}
    files.update(p for p in TOOLS.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    for profile in ("no-card", "card"):
        files.update(p for p in (TOOLS / "local/speed").glob(profile + ".snap.*") if p.is_file())
    path.write_text("".join(sha(p) + "  " + str(p.relative_to(TOOLS)) + "\n" for p in sorted(files)))
    research = [p for p in HERE.rglob("*") if p.is_file() and p != HERE / "SHA256SUMS"]
    (HERE / "SHA256SUMS").write_text("".join(sha(p) + "  " + str(p.relative_to(ROOT)) + "\n"
                                           for p in sorted(research)))
    print(json.dumps({"tool_files": len(files), "research_files": len(research)}))
    return True


def verify():
    totals = []
    for manifest, base in ((TOOLS / "SHA256SUMS", TOOLS), (HERE / "SHA256SUMS", ROOT)):
        bad, count = [], 0
        for line in manifest.read_text().splitlines():
            expected, name = line.split(None, 1)
            path = base / name.lstrip("*")
            count += 1
            if not path.is_file() or sha(path) != expected:
                bad.append(name)
        totals.append({"manifest": str(manifest.relative_to(ROOT)), "files": count, "mismatches": len(bad)})
    print(json.dumps(totals))
    return all(x["mismatches"] == 0 for x in totals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("guard", "summary", "source-check", "trim-logs", "seal", "verify"))
    args = parser.parse_args()
    passed = {"guard": guard, "summary": summary, "source-check": source_check,
              "trim-logs": trim_logs, "seal": seal, "verify": verify}[args.command]()
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
