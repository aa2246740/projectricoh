# Adapter of the frozen batch replay; original checks retained.
"""Copy of research/emulator_m2d/acceptance.py for tools/gxr_emulator_fast; changes are marked BATCH-COPY."""
"""Evaluate cumulative milestones from native runs and SHA-bound checkpoints."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "local"
TOOLS = ROOT / "tools/gxr_emulator_fast"
sys.path.insert(0, str(TOOLS))
from input_run import CheckpointReader
from storage_run import sha, sources

MAIN_SHA = "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7"
# BATCH-COPY: the frozen-library check binds this study's rebuilt library instead of ba1efa53...
LIB_SHA = sha(TOOLS / "build/libgxr_m32r.dylib")
WRITTEN_SHA = "47bbc5ee8a4585c558ad1e5b9a9c9da604ead3c82bb6c327cd80285847d46e41"
SEED_SHA = "1dcaaea6de71feceab845d0fac6fd266871df5ab6f5606738fde680747b402cf"


def read(name):
    return json.loads((OUT / (name+".json")).read_text())


def checkpoint(name):
    path = OUT / (name+"-stop.pkl")
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert sha(path) == metadata["sha256"]
    with path.open("rb") as stream:
        state = CheckpointReader(stream).load()
    return state


def integer(state, address, size=4):
    for base, data, _ in state["regions"]:
        if base <= address and address+size <= base+len(data):
            return int.from_bytes(data[address-base:address-base+size], "big")
    raise ValueError("native address is outside mapped memory")


def states(run):
    return {row["id"]: row["state"] for row in run["observations"]["tasks"]}


def ready(run):
    rows = run["observations"]["startup_ready_services"]
    return all(any(row["service"] == 144 and row.get("task") == task
                   and row["psw"] & 0x80 and row["args"][:3] == [1, mask, 4]
                   for row in rows)
               for task, mask in ((8, 0x800000), (9, 0x2000000), (10, 0x4000000)))


def m2b(args):
    cold, stable, card, regression = map(read, (args.cold, args.stable, args.card, args.regression))
    snapshots = [checkpoint(name) for name in (args.cold, args.stable)]
    ticks = [integer(state, 0x200D183C) for state in snapshots]
    current = sources()
    baseline = ("backend.py", "board.py", "devices.py", "image.py", "m2.py", "observe.py",
                "peripherals.py", "unit_peer.py", "sdcard.py", "storage_run.py", "panel.py", "input_run.py")
    observation = cold["observations"]
    checks = {
        "official_MAIN": cold["start_step"] == 0 and cold["resume"] is None
                         and cold["image_sha256"] == MAIN_SHA,
        "bounded_runs_without_fault": all(r["stop"]["reason"] == "max_steps" for r in (cold, stable)),
        "current_MAIN_and_board_sources": all(r["sources"].get("tools/gxr_emulator_fast/"+name)
                                              == current["tools/gxr_emulator_fast/"+name]
                                              for r in (cold, stable) for name in baseline),
        "same_frozen_library": cold["library_sha256"] == stable["library_sha256"] == LIB_SHA,
        "continuation_identity": stable["start_step"] == cold["steps"]
                                 and stable["resume_sha256"] == sha(OUT / (args.cold+"-stop.pkl"))
                                 and Path(stable["resume"]).name == args.cold+"-stop.pkl",
        "stable_native_tick_window": stable["steps"]-cold["steps"] == 5000000
                                     and ticks[1] > ticks[0]
                                     and stable["timer_expirations"] > cold["timer_expirations"],
        "shared_initializers": len(observation["drivers"]) == 41
                               and all(row.get("result") == 0 for row in observation["drivers"].values()),
        "component_initializers": len(observation["components"]) == 8
                                  and all(row.get("result") == 0 for row in observation["components"].values()),
        "Task6_UI_initialization": len(observation["ui_initializers"]) == 3
                                   and all(row.get("result") == 0 for row in observation["ui_initializers"].values())
                                   and len(observation["application_returns"]) == 10
                                   and all(row["result"] < 0x80000000 for row in observation["application_returns"])
                                   and any(row["task"] == 6 for row in observation["ui_loop_entries"]),
    }
    for task, queue in ((6, None), (8, 2), (28, 15)):
        label = "Task6_native_creation" if task == 6 else f"Task{task}_native_creation_and_scheduling"
        checks[label] = observation["created_tasks"].get(str(task), {}).get("result") == 0 \
            and observation["task_entry_records"].get(str(task), {}).get("current_task") == task \
            and observation["scheduled"].get(str(task), 0) > 0
        if queue is None:
            continue
        checks[f"queue{queue}_native_creation"] = observation["created_queues"].get(str(queue), {}).get("result") == 0
        for label, run in (("cold", cold), ("stable", stable)):
            wait = run["observations"]["queue_waits"].get(str(task), {})
            checks[f"Task{task}_{label}_native_message_wait"] = states(run).get(task) == 512 \
                and (label == "stable" or wait.get("queue_id") == queue)
    boards = [next(d for d in state["devices"] if "enable_ready" in d) for state in snapshots]
    checks.update({
        "diagnostic_ready_disabled": all(not d["enable_ready"] and not d["ready_sent"] for d in boards),
        "native_startup_ready_observed": ready(cold),
        "ordinary_device_clock": cold["timer_expirations"] > 0,
        "board_and_native_regressions": len(regression["checks"]) == 4
                                        and all(row["returncode"] == 0 for row in regression["checks"]),
    })
    return {"milestone": "M2b", "checks": checks, "native_ticks": ticks,
            "runs": [args.cold, args.stable], "regression": args.regression,
            "card": {"run": args.card, "states": states(card), "native_ready": ready(card),
                     "same_wait_state": all(states(card).get(task) == 512 for task in (8, 28))},
            "layer": "原厂固件在声明的离线设备模型下运行；UI 初始化不等于 ADJ 打开"}


def file_value(metadata):
    row = next((r for r in metadata["files"] if r["name"] == "M2CWRITE.BIN"), {})
    return row.get("size") == 4099 and row.get("sha256") == WRITTEN_SHA \
        and bool(row.get("clusters")) and metadata["fat_copies_equal"] \
        and not metadata["unreferenced_clusters"]


def mounted(case, name):
    return any(row["name"] == name and row["state_before"].get("volume", {}).get("mounted_flags", 0) & 1
               for row in case["calls"])


def error(case, first, second):
    return any(row["kind"] == "file-error-code" and row["args"][:2] == [first, second]
               for row in case["events"])


def task_lock(case):
    selected = {"open-test-file", "read-short-file", "close-read-file", "create-new-file",
                "write-new-file", "close-written-file"}
    rows = [row for row in case["calls"] if row["name"] in selected]
    return bool(rows) and all(row["task"] == row["return_task"] == 8 and row["psw"] & 0x80
                              and row["semaphore47_before"] == row["semaphore47_after"] == 1
                              and row["stop"]["reason"] == "return" for row in rows)


def m2c(args):
    names = tuple(name+"-"+args.file_series for name in
                  ("files", "readback", "full", "read-error", "write-error", "no-card"))
    cases = list(map(read, names))
    files, back, full, read_error, write_error, no_card = cases
    boot_name = "reboot-"+args.file_series
    boot, boot_input = read(boot_name), read(boot_name+"-input")
    reboot = checkpoint(boot_name)
    guard, cumulative, model = read("final-input-guard"), read(args.cumulative), read("storage-checks-r1")
    raw = files["read"]
    source_paths = ("backend.py", "board.py", "devices.py", "image.py", "m2.py", "observe.py",
                    "peripherals.py", "unit_peer.py", "sdcard.py", "storage_run.py", "file_calls.py",
                    "fat_image.py", "panel.py", "input_run.py")
    current = sources()
    same_files = all(case["sources"].get("tools/gxr_emulator_fast/"+name)
                     == current["tools/gxr_emulator_fast/"+name] for case in cases+[boot] for name in source_paths)
    checks = {
        "declared_block_model": model["passed"] >= 13,
        "fresh_MAIN_restart": boot["start_step"] == 0 and boot["resume"] is None
                              and boot["image_sha256"] == MAIN_SHA
                              and boot["stop"]["reason"] == "breakpoint" and boot["stop"]["pc"] == 0x2010E23C,
        "native_card_mount": integer(reboot, 0x200D1838, 2) == 8
                             and reboot["registers"]["pc"] == 0x2010E23C and reboot["registers"]["r0"] == 0,
        "seed_open_read_close": files["status"] == "passed" and raw["returned"] == 3077
                                and raw["byte_equal"] and raw["sha256"] == SEED_SHA and files["read_close"] == 0,
        "short_read_preserves_tail": raw["requested"] == 3204 and raw["returned"] == 3077 and raw["tail_unchanged"],
        "native_create_write_close": files["written"] == 4099 and files["write_close"] == 0,
        "independent_FAT_after_write": file_value(files["medium"]),
        "same_image_bytes_at_restart": boot_input["source_medium_sha256"] == files["medium"]["image_sha256"]
                                       == boot_input["restart_medium_sha256"] and boot_input["checkpoint_input"] is None,
        "native_read_after_restart": back["status"] == "passed" and back["filename"] == "/ATA1/M2CWRITE.BIN"
                                     and Path(back["resume"]).name == boot_name+"-stop.pkl"
                                     and back["read"]["returned"] == 4099 and back["read"]["byte_equal"]
                                     and back["read"]["sha256"] == WRITTEN_SHA and back["read_close"] == 0,
        "independent_FAT_after_restart": file_value(back["medium"])
                                         and back["medium"]["image_sha256"] == boot_input["restart_medium_sha256"],
        "full_medium_branch": full["status"] == "passed" and full["medium"]["free_clusters"] == 0
                              and full.get("create_result", 0) < 0 and mounted(full, "create-new-file") and error(full, 4, 17),
        "read_error_branch": read_error["status"] == "passed" and read_error["read"]["returned"] <= 0
                             and read_error["sd_counts"].get("io-error", 0) > 0
                             and mounted(read_error, "read-short-file") and error(read_error, 223, 255),
        "write_error_branch": write_error["status"] == "passed"
                              and (write_error["written"] <= 0 or write_error["write_close"] < 0)
                              and write_error["sd_counts"].get("io-error", 0) > 0
                              and mounted(write_error, "write-new-file") and error(write_error, 67, 255),
        "no_card_branch": no_card["status"] == "passed" and no_card["open_result"] == -1,
        "native_Task8_and_semaphore47": all(task_lock(case) for case in cases),
        "M2b_cumulative": cumulative["status"] == "passed" and cumulative["passed"] == cumulative["total"] == 22,
        "card_reaches_same_wait_state": cumulative["card"]["same_wait_state"],
        "fixed_inputs": guard["unchanged_inputs"] and guard["changes_prefix_unchanged"]
                        and guard["historical_inputs_unchanged"],
        "current_file_entry_evidence": same_files,
        "GXRCE_absent": all(not any(row["name"].rsplit("/", 1)[-1].upper() == "GXRCE.DAT"
                                     for row in case["medium"]["files"]) for case in (files, back)),
        "final_SD_model_identity": all(case["sources"]["tools/gxr_emulator_fast/sdcard.py"]
                                        == current["tools/gxr_emulator_fast/sdcard.py"] for case in cases+[boot])
                                   and model["source_hashes"]["tools/gxr_emulator_fast/sdcard.py"]
                                       == current["tools/gxr_emulator_fast/sdcard.py"],
    }
    return {"milestone": "M2c", "checks": checks, "runs": list(names)+[boot_name],
            "native_mount_return_pc": "0x2010E23C", "cumulative": args.cumulative,
            "layer": "Task 8 原厂文件调用及重新从 MAIN 启动后的介质内容"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("milestone", choices=("m2b", "m2c"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--cold", default="cold-final-r2")
    parser.add_argument("--stable", default="stable-final-r2")
    parser.add_argument("--card", default="cold-card-final-r2")
    parser.add_argument("--regression", default="regression-final-r2")
    parser.add_argument("--cumulative", default="m2b-final-r2")
    parser.add_argument("--file-series", default="r1")
    args = parser.parse_args()
    target = OUT / (args.name+".json")
    if target.exists() or target.resolve().parent != OUT:
        raise ValueError("choose a fresh result name")
    result = {"m2b": m2b, "m2c": m2c}[args.milestone](args)
    evidence = list(result["runs"])
    if args.milestone == "m2b":
        evidence += [args.regression, args.card]
    else:
        evidence += [args.cumulative, "final-input-guard", "storage-checks-r1",
                     "reboot-"+args.file_series+"-input"]
    result["evidence_sha256"] = {name: sha(OUT / (name+".json")) for name in sorted(set(evidence))}
    result["checker_sha256"] = sha(Path(__file__))
    result["current_sources"] = sources()
    result.update(passed=sum(result["checks"].values()), total=len(result["checks"]))
    result["status"] = "passed" if all(result["checks"].values()) else "incomplete"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("milestone", "passed", "total", "status")}))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
