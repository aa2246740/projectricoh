#!/usr/bin/python3 -I
"""Rebuild resident into the review's temporary directory with original inputs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import signal
import sys

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'research/review_g151_body/evidence'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g151/resident-rebuild')
signal.alarm(1800)
path=ROOT/'firmware/resident_v39/resident/build.py'
spec=importlib.util.spec_from_file_location('review_build',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.LOCAL=TMP
def preflight():
    assert os.environ['TMPDIR'].startswith('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g151/')
    recorded=json.loads((ROOT/'firmware/resident_v39/local/resident/inputs.json').read_text())
    assert all(m.sha(ROOT/name)==value for name,value in recorded.items())
    TMP.mkdir(parents=True,exist_ok=True)
    (TMP/'tmp').mkdir(exist_ok=True)
m.preflight=preflight
sys.argv=[str(path)]
assert m.main()==0
final=ROOT/'firmware/resident_v39/local/resident'
comparisons={name:(TMP/name).read_bytes()==(final/name).read_bytes() for name in [
    'build/resident.bin','build/resident.elf','target-layout.json','patch-manifest.json','trust.json']}
assert all(comparisons.values()),comparisons
result=dict(status='PASS',comparisons=comparisons,
    elf_sha256=hashlib.sha256((TMP/'build/resident.elf').read_bytes()).hexdigest(),
    size=json.loads((TMP/'size.json').read_text()),
    commands=json.loads((TMP/'commands.json').read_text()))
(OUT/'resident_rebuild.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(status='PASS',comparisons=comparisons,elf_sha256=result['elf_sha256'])))
