"""Evaluate the cumulative native boot conditions from actual run records."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
TOOLS = ROOT / "tools/gxr_emulator"
sys.path.insert(0, str(TOOLS))
from storage_run import Machine


def read(name):
    return json.loads((OUT / (name + ".json")).read_text())


def states(run):
    return {row["id"]: row["state"] for row in run["observations"]["tasks"]}


def native_ready(run):
    rows = run["observations"]["startup_ready_services"]
    expected = {8: 0x00800000, 9: 0x02000000, 10: 0x04000000}
    return all(any(row["service"] == 144 and row.get("task") == task
                   and row["psw"] & 0x80 and row["args"][:3] == [1, flag, 4]
                   for row in rows) for task, flag in expected.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cold", required=True)
    parser.add_argument("--stable", required=True)
    parser.add_argument("--card", required=True)
    parser.add_argument("--regression", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().parent != OUT:
        raise ValueError("use a fresh M2c local result")
    cold, stable, card, regression = map(read, (args.cold, args.stable, args.card, args.regression))
    native_ticks = []
    for name in (args.cold, args.stable):
        machine = Machine(resume=OUT / (name + "-stop.pkl"))
        native_ticks.append(int.from_bytes(machine.cpu.read(0x200D183C, 4), "big"))
        machine.close()
    observation = cold["observations"]
    current = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in TOOLS.glob("*.py")}
    baseline = ("backend.py", "board.py", "devices.py", "image.py", "m2.py", "observe.py",
                "peripherals.py", "unit_peer.py", "sdcard.py", "storage_run.py")
    checks = {
        "official_MAIN": cold["start_step"] == 0 and cold["resume"] is None
                         and cold["image_sha256"] == "da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7",
        "bounded_runs_without_fault": all(run["stop"]["reason"] == "max_steps" for run in (cold, stable)),
        "current_MAIN_and_board_sources": all(run["sources"].get("tools/gxr_emulator/" + name)
                                              == current["tools/gxr_emulator/" + name]
                                              for run in (cold, stable) for name in baseline),
        "same_frozen_library": cold["library_sha256"] == stable["library_sha256"]
                               == "ba1efa53ce71dbd5632b2a540d0ca3ad02c395498688ce90089a41d85e8c07ff",
        "continuation_identity": stable["start_step"] == cold["steps"]
                                 and Path(stable["resume"]).name == args.cold + "-stop.pkl",
        "stable_native_tick_window": stable["steps"] - cold["steps"] == 5000000
                                     and native_ticks[1] > native_ticks[0]
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
        key = "Task6_native_creation" if task == 6 else f"Task{task}_native_creation_and_scheduling"
        checks[key] = observation["created_tasks"].get(str(task), {}).get("result") == 0 \
                      and observation["task_entry_records"].get(str(task), {}).get("current_task") == task \
                      and observation["scheduled"].get(str(task), 0) > 0
        if queue is None:
            continue
        checks[f"queue{queue}_native_creation"] = observation["created_queues"].get(str(queue), {}).get("result") == 0
        for label, run in (("cold", cold), ("stable", stable)):
            wait = run["observations"]["queue_waits"].get(str(task), {})
            checks[f"Task{task}_{label}_native_message_wait"] = states(run).get(task) == 0x200 \
                and (label == "stable" or wait.get("queue_id") == queue)
    checks.update({
        "diagnostic_ready_disabled": all("synthetic_unit_ready" not in run["arguments"] for run in (cold, stable)),
        "native_startup_ready_observed": native_ready(cold),
        "ordinary_device_clock": cold["timer_expirations"] > 0,
        "board_and_native_regressions": len(regression["checks"]) == 4
                                        and all(row["returncode"] == 0 for row in regression["checks"]),
    })
    result = {"checks": checks, "passed": sum(checks.values()), "total": len(checks),
              "status": "passed" if all(checks.values()) else "incomplete",
              "runs": [args.cold, args.stable],
              "timer_expirations": [cold["timer_expirations"], stable["timer_expirations"]],
              "native_tick_address": "0x200D183C", "native_ticks": native_ticks,
              "card": {"run": args.card, "steps": card["steps"], "stop": card["stop"],
                       "states": states(card), "native_ready": native_ready(card),
                       "same_wait_state": all(states(card).get(task) == 0x200 for task in (8, 28))},
              "layer": "original firmware under declared emulator devices"}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "passed": result["passed"], "total": len(checks)}))


if __name__ == "__main__":
    main()
