"""Read the native file and volume state from trusted local checkpoints."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from file_calls import Calls
from storage_run import Machine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("checkpoints", type=Path, nargs="+")
    args = parser.parse_args()
    rows = []
    for checkpoint in args.checkpoints:
        machine = Machine(None, checkpoint)
        try:
            row = {"checkpoint": str(checkpoint), "task": machine.task(),
                   "state": Calls(machine).state(), "sd_counts": dict(machine.sd.counts)}
            rows.append(row)
        finally:
            machine.close()
    result = {"premise": "A returned byte count proves that native writes reached the image.",
              "verdict": "The independent image check disproves this premise.",
              "observations": rows}
    if not args.output.resolve().is_relative_to(OUT):
        raise ValueError("state record must stay in M2c local")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"checkpoints": len(rows)}))


if __name__ == "__main__":
    main()
