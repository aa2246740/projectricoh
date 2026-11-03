"""Private, identity-bound UI snapshots for the offline body model."""
import argparse
from collections import Counter, deque
import copy
import hashlib
import io
import json
from pathlib import Path
import pickle
import platform
import shutil
import struct
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "tools/gxr_emulator_batch"
LOCAL = ROOT / "research/review_harness_c/local/snapshots"
FORMAT = "gxr-ui-r1"
IDLE = 0x2005C340
CONFIG = {"board": "m2b", "panel": "five-columns-high", "dial": 2,
          "bios193_high": False, "image": "official", "ready_diagnostic": False}
sys.path.insert(0, str(HERE))
from storage_run import Machine
from panel import Panel
from dial import set_dial
from observe import Observer, CURRENT_TASK, TASK_STATE
import outputs

# Directories for evidence outside the tool's local/; given by the caller.
EVIDENCE = [ROOT / "research/review_harness_c"]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def private(path):
    path = Path(path).resolve()
    roots = (HERE / "local",) + tuple(EVIDENCE)
    if not any(path.is_relative_to(base.resolve()) for base in roots):
        raise ValueError("output must be in a private local directory")
    outputs.declare_media(path.parent)
    return path


def identity(card_seed=None):
    files = set(HERE.glob("*.py")) | set(HERE.glob("*.c")) | set(HERE.glob("*.json"))
    for base in (ROOT / "tools/native_harness", ROOT / "research/native_harness"):
        if base.exists():
            files.update(base.glob("*.py"))
    files.update([ROOT / "artifacts/firmware/gxr-1.51/ilaunch3",
                  ROOT / "artifacts/firmware/gxr-1.51/jlaunch3",
                  ROOT / "research/firmware/ilaunch3-sections.csv",
                  HERE / "build/libgxr_m32r.dylib",
                  ROOT / "research/emulator_m2b/local/nand-reflector.pages.json",
                  ROOT / "research/emulator_m2b/local/unit-info-synthetic.bin"])
    if card_seed:
        files.add(Path(card_seed).resolve())
    return {"format": FORMAT, "configuration": CONFIG,
            "card_seed": str(Path(card_seed).resolve().relative_to(ROOT)) if card_seed else None,
            "runtime": {"python": platform.python_version(), "machine": platform.machine()},
            "files": {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}}


def canonical(value, h):
    """Hash all values with type and length framing, independent of dict order."""
    def part(tag, data):
        h.update(tag + struct.pack(">Q", len(data)))
        h.update(data)
    if value is None:
        h.update(b"n")
    elif isinstance(value, bool):
        h.update(b"t" if value else b"f")
    elif isinstance(value, int):
        part(b"i", str(value).encode())
    elif isinstance(value, str):
        part(b"s", value.encode())
    elif isinstance(value, (bytes, bytearray)):
        part(b"b" if isinstance(value, bytes) else b"a", value)
    elif isinstance(value, dict):
        h.update(b"d" + struct.pack(">Q", len(value)))
        for key in sorted(value, key=lambda x: (type(x).__name__, repr(x))):
            canonical(key, h)
            canonical(value[key], h)
    elif isinstance(value, (set, frozenset)):
        h.update(type(value).__name__.encode())
        canonical(sorted(value, key=lambda x: (type(x).__name__, repr(x))), h)
    elif isinstance(value, (list, tuple, deque)):
        h.update(type(value).__name__.encode() + struct.pack(">Q", len(value)))
        if isinstance(value, deque):
            canonical(value.maxlen, h)
        for item in value:
            canonical(item, h)
    else:
        raise TypeError("unsupported state type: " + type(value).__name__)


def value_hash(value):
    h = hashlib.sha256()
    canonical(value, h)
    return h.hexdigest()


def state_hash(machine):
    state = machine.cpu.snapshot()
    device_state = copy.deepcopy(state["devices"])
    for name, data in zip(state["device_types"], device_state):
        if name == "SdHost" and data.get("medium_record"):
            # A private copy has the same bytes and a different host filename.
            data["medium_record"]["path"] = "private-medium"
    result = {"cpu": value_hash(state["registers"]),
              "memory": value_hash(state["regions"]),
              "devices": value_hash([state["device_types"], device_state,
                                     {"panel_down": sorted(machine.panel.down)}]),
              "steps": state["steps"]}
    result["all"] = value_hash(result)
    return result


class Reader(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "collections" and name in ("Counter", "deque"):
            return {"Counter": Counter, "deque": deque}[name]
        if module == "builtins" and name == "bytearray":
            return bytearray
        raise ValueError("unsupported snapshot value type")


def attach_panel(machine, down=()):
    panel = Panel(machine.cpu, machine.devices)
    panel.down = set(down)
    panel.chain(machine.cpu)
    machine.panel = panel
    return panel


def cold(card_seed=None, mode="fast", medium=None):
    LOCAL.mkdir(parents=True, exist_ok=True)
    if card_seed:
        medium = private(medium or LOCAL / "working.img")
        medium.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(card_seed, medium)
    machine = Machine(medium if card_seed else None)
    machine.cpu.set_mode(mode)
    attach_panel(machine)
    serial = machine.devices["serial"]
    mask, level = serial.input_bytes.get(0, (0, 0))
    serial.input_bytes[0] = (mask | 2, level & ~2)
    set_dial(machine.cpu, machine.devices, 2)
    return machine


def quiet(machine):
    cpu, devices = machine.cpu, machine.devices
    task = int.from_bytes(cpu.read(CURRENT_TASK, 2), "big")
    states = {str(i): int.from_bytes(cpu.read(TASK_STATE + 4 * (i - 1), 4), "big")
              for i in range(1, 45)}
    irq, dma, sd = devices["irq"], devices["dma"], machine.sd
    checks = {"native_idle_loop": cpu.get_reg("pc") == IDLE,
              "word_boundary": cpu.get_reg("pc") % 4 == 0,
              "between_steps": not getattr(cpu, "_in_step", False),
              "no_irq": irq.in_service is None and not irq.pending,
              "no_unit_dma": not dma.pending,
              "no_card_dma": not sd.dma_armed and not sd.dma_delay,
              "no_card_transfer": not sd.pending and not sd.transfer and not sd.stop_pending,
              "ui_state_2": int.from_bytes(cpu.read(0x205D9C00, 4), "big") == 2,
              "ui_queue_wait": states["6"] == 512,
              "file_task_wait": states["8"] == 512,
              "ui_workers_wait": states["9"] == 512 and states["10"] == 512,
              "unit_task_wait": states["28"] == 512}
    strict_waiting = all(value not in (0, 1) for value in states.values())
    return {"checks": checks, "ok": all(checks.values()), "task": task,
            "strict_all_tasks_waiting": strict_waiting,
            "active_tasks": [int(key) for key, value in states.items() if value in (0, 1)],
            "task_states": states, "pc": cpu.get_reg("pc"), "psw": cpu.get_reg("psw"),
            "queue_waits": copy.deepcopy(machine.observer.queue_waits)}


def observer_data(machine):
    return copy.deepcopy({k: v for k, v in vars(machine.observer).items() if k != "cpu"})


def restore_observer(machine, data):
    for key, value in copy.deepcopy(data).items():
        setattr(machine.observer, key, value)
    for task, entry in machine.observer.task_entries.items():
        if entry not in machine.cpu.breakpoints:
            machine.observer.breakpoint(entry, lambda cpu, task=task: machine.observer.entered(task))


def regeneration(profile, card_seed=None):
    command = ("/usr/bin/python3 -I -B " + str(Path(__file__).resolve().relative_to(ROOT))
               + " build --profile " + profile)
    if card_seed:
        command += " --card-seed " + str(Path(card_seed).relative_to(ROOT))
    command += " --revision r" + str(time.time_ns())
    command += " --allow-idle-task"
    return command


def save(machine, path, profile, card_seed=None, bound=None):
    path = private(path)
    proof = quiet(machine)
    if not proof["ok"]:
        raise ValueError("snapshot requires a quiet UI scheduler point")
    current = identity(card_seed)
    if bound is not None and bound != current:
        raise ValueError("boot identity changed while running; " + regeneration(profile, card_seed))
    state = machine.cpu.snapshot()
    medium = None
    if machine.sd.medium:
        medium = path.with_suffix(".img.z")
        medium.write_bytes(zlib.compress(machine.sd.medium.path.read_bytes(), 6))
    record = {"cpu": state, "observer": observer_data(machine),
              "panel_down": sorted(machine.panel.down),
              "machine_events": copy.deepcopy(machine.events),
              "machine_returns": copy.deepcopy(machine.pending_returns)}
    raw = pickle.dumps(record, protocol=4)
    packed = zlib.compress(raw, 6)
    path.write_bytes(packed)
    metadata = {"format": FORMAT, "profile": profile, "identity": current,
                "sha256": sha(path), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "raw_bytes": len(raw), "compressed_bytes": len(packed),
                "medium": {"file": medium.name, "sha256": sha(medium)} if medium else None,
                "quiet": proof, "state_hash": state_hash(machine),
                "steps": machine.cpu.steps, "accepted": proof["strict_all_tasks_waiting"],
                "regenerate": regeneration(profile, card_seed)}
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    return metadata


def load(path, mode="fast", medium=None, configuration=None, allow_idle_task=False):
    path = private(path)
    metadata = json.loads(path.with_suffix(".json").read_text())
    command = metadata.get("regenerate", "rebuild the selected profile")
    def require(condition, message):
        if not condition:
            raise ValueError(message + "; " + command)
    require(metadata.get("format") == FORMAT, "snapshot format differs")
    require(metadata.get("accepted") or allow_idle_task,
            "candidate contains an active idle task; explicit --allow-idle-task is required")
    card_seed = ROOT / metadata["identity"]["card_seed"] if metadata["identity"].get("card_seed") else None
    try:
        current = identity(card_seed)
    except OSError as error:
        raise ValueError("boot identity file is unavailable; " + command) from error
    require(current == metadata["identity"], "boot identity differs")
    require(configuration is None or configuration == metadata["identity"]["configuration"],
            "boot configuration differs")
    require(sha(path) == metadata["sha256"], "snapshot SHA differs")
    require(metadata["quiet"]["ok"], "snapshot has no quiet-point proof")
    if metadata["medium"]:
        source = private(path.parent / metadata["medium"]["file"])
        require(sha(source) == metadata["medium"]["sha256"], "medium SHA differs")
        medium = private(medium or path.with_suffix(".working.img"))
        require(medium != card_seed, "working medium must differ from seed")
        medium.write_bytes(zlib.decompress(source.read_bytes()))
    raw = zlib.decompress(path.read_bytes())
    require(hashlib.sha256(raw).hexdigest() == metadata["raw_sha256"], "state SHA differs")
    record = Reader(io.BytesIO(raw)).load()
    machine = Machine(medium if metadata["medium"] else None)
    try:
        attach_panel(machine, record["panel_down"])
        for name, data in zip(record["cpu"]["device_types"], record["cpu"]["devices"]):
            if name == "SdHost" and data.get("medium_record"):
                data["medium_record"]["path"] = str(medium)
        machine.cpu.restore(record["cpu"])
        machine.cpu.set_mode(mode)
        restore_observer(machine, record["observer"])
        machine.events = record["machine_events"]
        machine.pending_returns = record["machine_returns"]
        require(state_hash(machine) == metadata["state_hash"], "restored state differs")
        require(quiet(machine)["ok"], "restored point is not quiet")
        require(quiet(machine)["strict_all_tasks_waiting"] or allow_idle_task,
                "restored task table contains active tasks")
    except BaseException:
        machine.close()
        raise
    return machine, metadata


def run_steps(machine, count):
    stop = machine.cpu.run(count)
    if stop.reason != "max_steps" or stop.steps != count:
        raise RuntimeError("model stopped before requested work: " + stop.reason)
    return stop


def build(args):
    card = args.card_seed.resolve() if args.card_seed else None
    if (args.profile == "card") != bool(card):
        raise ValueError("card profile requires --card-seed; no-card requires no medium")
    if args.revision and not args.revision.replace("-", "").isalnum():
        raise ValueError("revision must use letters, digits, or hyphens")
    prefix = args.profile + ("-" + args.revision if args.revision else "")
    target = private(LOCAL / (prefix + ".snap.z"))
    if target.exists():
        raise ValueError("snapshot exists; preserve it before selecting a new revision")
    bound = identity(card)
    machine = cold(card, medium=LOCAL / (prefix + "-boot.img"))
    started = time.monotonic()
    ready = []
    previous = machine.cpu.breakpoints.get(0x202B1100)
    def ui_entry(cpu):
        ready.append(cpu.steps)
        if previous:
            return previous(cpu)
        return False
    machine.cpu.add_breakpoint(0x202B1100, ui_entry)
    original = machine.cpu.breakpoints.get(IDLE)
    next_check = [0]
    def idle(cpu):
        if original and original(cpu) is not False:
            return True
        if not ready or cpu.steps < next_check[0]:
            return False
        next_check[0] = cpu.steps + 10000
        return quiet(machine)["ok"]
    machine.cpu.add_breakpoint(IDLE, idle)
    try:
        while machine.cpu.steps < args.budget:
            stop = machine.cpu.run(min(1000000, args.budget - machine.cpu.steps))
            print(json.dumps({"profile": args.profile, "steps": machine.cpu.steps,
                              "seconds": round(time.monotonic() - started, 3),
                              "stop": stop.reason}), flush=True)
            if stop.reason == "breakpoint":
                break
            if stop.reason != "max_steps":
                raise RuntimeError("boot stopped: " + stop.reason)
        if original:
            machine.cpu.breakpoints[IDLE] = original
        else:
            machine.cpu.breakpoints.pop(IDLE, None)
        if previous:
            machine.cpu.breakpoints[0x202B1100] = previous
        else:
            machine.cpu.breakpoints.pop(0x202B1100, None)
        if not quiet(machine)["strict_all_tasks_waiting"] and not args.allow_idle_task:
            raise ValueError("Task 1 is active in the native idle loop; candidate needs --allow-idle-task")
        metadata = save(machine, target, args.profile, card, bound)
        metadata["boot_seconds"] = time.monotonic() - started
        metadata["ui_entries"] = ready
        target.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"saved": str(target.relative_to(ROOT)), "steps": machine.cpu.steps,
                          "bytes": metadata["compressed_bytes"]}), flush=True)
        reference = {"snapshot_sha256": metadata["sha256"], "identity": bound,
                     "boot_seconds": metadata["boot_seconds"], "start_step": machine.cpu.steps,
                     "continuous_from_main": True, "points": {}}
        for distance in (1000000, 10000000):
            began = time.monotonic()
            run_steps(machine, reference["start_step"] + distance - machine.cpu.steps)
            reference["points"][str(distance)] = {
                "state": state_hash(machine), "observations": value_hash(observer_data(machine)),
                "seconds": time.monotonic() - began}
            result_path = outputs.require(args.evidence_dir) / (prefix + "-continuous.json")
            result_path.write_text(json.dumps(reference, indent=2) + "\n")
            print(json.dumps({"profile": args.profile, "continuous_distance": distance,
                              "state": reference["points"][str(distance)]["state"]["all"]}), flush=True)
    finally:
        machine.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--profile", choices=("card", "no-card"), required=True)
    parser.add_argument("--card-seed", type=Path)
    parser.add_argument("--budget", type=int, default=100000000)
    parser.add_argument("--allow-idle-task", action="store_true")
    parser.add_argument("--revision")
    parser.add_argument("--evidence-dir", type=Path,
                        help="directory for the continuous reference (build); no default")
    args = parser.parse_args()
    if args.command == "build":
        outputs.require(args.evidence_dir, "--evidence-dir")
    if args.command == "build":
        build(args)
    else:
        prefix = args.profile + ("-" + args.revision if args.revision else "")
        machine, metadata = load(LOCAL / (prefix + ".snap.z"), allow_idle_task=args.allow_idle_task)
        print(json.dumps({"profile": args.profile, "steps": machine.cpu.steps,
                          "quiet": quiet(machine)["ok"], "state": state_hash(machine)}))
        machine.close()


if __name__ == "__main__":
    main()
