"""Run the original three calibration subcommands with a task-local write fence."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime

if __name__ == '__main__':
    runtime.calibrate.main()
