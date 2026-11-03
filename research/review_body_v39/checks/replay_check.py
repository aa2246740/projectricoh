#!/usr/bin/python3 -I
"""Replay the frozen final ELF and retain batch statistics."""
from pathlib import Path
import importlib.util
import os
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_model

source = batch_model.ROOT / 'research/body_v39/tests/replay_v39.py'
sys.argv = [str(source), str(batch_model.OUT / 'replay.json')]
spec = importlib.util.spec_from_file_location('review_resident_replay', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
assert batch_model.INSTANCES
assert sum(item.batch_stats.get('batch-steps', 0) for item in batch_model.INSTANCES) > 0
