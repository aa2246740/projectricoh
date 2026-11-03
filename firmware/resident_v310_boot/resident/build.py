#!/usr/bin/python3
"""Build the body BOOT research candidate with the fixed window."""
from pathlib import Path
import runpy,sys
root=Path(__file__).resolve().parents[3]
entry=root/"research/v310_resident/measure.py"
sys.argv=[str(entry),*sys.argv[1:]]
runpy.run_path(str(entry),run_name="__main__")
