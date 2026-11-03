#!/usr/bin/python3 -I
"""Reproduce the Fn example's identity-check failure without executing a DAT."""
from pathlib import Path
import importlib.util
import json
import os
import re
import sys
import traceback

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=ROOT/'research/review_g151_body/evidence'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g151')/f'fn-doc-p{os.getpid()}'
source=ROOT/'research/body_v39/tests/dat_rotate.py'
text=source.read_text()
package=re.search(r'V39_PACKAGE=(\S+)',text).group(1)
engine=re.search(r'V39_ENGINE=(\S+)',text).group(1)
os.environ.update(V39_PACKAGE=package,V39_ENGINE=engine,TMPDIR=str(TMP))
for name in ('V39_REFERENCE','V39_BODY_SHA','V39_RESIDENT'):
    os.environ.pop(name,None)
path=ROOT/'research/body_v39/tests/v39_host.py'
spec=importlib.util.spec_from_file_location('review_fn_doc_host',path)
H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
H.TMP=TMP;H.LOCAL=TMP/'model'
failure=None
try:
    H.setup()
except AssertionError as error:
    failure=traceback.extract_tb(error.__traceback__)[-1]
assert failure is not None
sums=dict(reversed(line.split('  ',1)) for line in (H.PACKAGE.parents[1]/'SHA256SUMS').read_text().splitlines())
assert H.sha(H.DAT)==sums[str(H.DAT.relative_to(ROOT))]
assert H.sha(H.BODY)!=H.BODY_SHA
result=dict(status='OBSERVED_P2',source='research/body_v39/tests/dat_rotate.py:4',
    documented_package=package,generation=int.from_bytes(H.DAT.read_bytes()[28:32],'big'),
    dat_sha256=H.sha(H.DAT),actual_body_sha256=H.sha(H.BODY),expected_body_sha256=H.BODY_SHA,
    legacy_dat_matches_its_manifest=True,failure_file=failure.filename,failure_line=failure.lineno,
    camera_constructed=False)
assert result['generation']==149
H.PACKAGE=ROOT/'research/body_v39/local/fntest-package-g151/local/SD_ROOT'
H.DAT=H.PACKAGE/'GXRCE.DAT';H.BODY=H.PACKAGE/'ilaunch3'
H.setup()
assert int.from_bytes(H.DAT.read_bytes()[28:32],'big')==151
result.update(correct_package=str(H.PACKAGE.parents[1].relative_to(ROOT)),
    correct_dat_sha256=H.sha(H.DAT),correct_preflight_passed=True)
(OUT/'fn_doc_path.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
