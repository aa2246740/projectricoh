"""Check that resuming at an observed entry does not create a second call."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from input_run import Flow, machine_from
from storage_run import sources


def main():
    name = sys.argv[1]
    path = OUT / (name+".json")
    if path.exists():
        raise ValueError("choose a fresh observer check name")
    checkpoint = OUT / "record-ready-r7-stop.pkl"
    metadata = json.loads(checkpoint.with_suffix(".json").read_text())
    machine = machine_from(checkpoint, name)
    try:
        cpu = machine.cpu
        assert cpu.get_reg("pc") == 0x20069160 and machine.task() == 6
        flow = Flow(machine, pending=metadata["flow_open_calls"])
        started = cpu.steps
        stop = cpu.run(100)
        calls = [r for r in flow.rows if r["kind"] == "queue1-wait-call"]
        next_calls = [r for r in flow.rows if r["kind"] == "event-next-call"]
        pending = [entry for row in flow.open_calls() for entry in row["calls"]
                   if row["task"] == 6 and entry["name"] == "queue1-wait"]
        assert not calls and len(next_calls) == len(pending) == 1
        result = {"passed": 1, "total": 1, "start_step": started, "steps": cpu.steps,
                  "stop": stop.to_dict(), "resumed_entry_records": len(calls),
                  "nested_event_next_calls": len(next_calls), "pending_queue_calls": len(pending),
                  "flow": flow.rows, "sources": sources()}
        path.write_text(json.dumps(result, indent=2)+"\n")
        print(json.dumps({"passed": 1, "total": 1}))
    finally:
        machine.close()


if __name__ == "__main__":
    main()
