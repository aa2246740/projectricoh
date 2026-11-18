#!/usr/bin/python3
"""Build the retained two-IROM-source research candidate."""
from pathlib import Path
import runpy,sys
root=Path(__file__).resolve().parents[3]
entry=root/"research/g155/build_resident.py"
sys.argv=[str(entry),*sys.argv[1:]]
runpy.run_path(str(entry),run_name="__main__")
