"""Compile current unmodified C parsers into a private host dylib."""
from pathlib import Path
import ctypes as CT
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
F=C.load(C.ROOT/'research/v39_g153/format_checks.py','review_g156_format')
F.PRODUCT=C.ENGINE/'candidate/containers/product';F.TMP=C.TMP/'format';F.HERE=C.HERE
lib=F.library();rows=[]
for profile in ('release','test'):
    raw=(C.PACKAGES[profile]/'GXRCE.DAT').read_bytes()
    old=(C.ROOT/('firmware/package_v310_g155c'+('_test'if profile=='test'else''))/'GXRCE.DAT').read_bytes()
    for unit in range(3):
        got=lib.check_dat(CT.create_string_buffer(raw),len(raw),CT.create_string_buffer(F.trust(raw)),unit)
        rejected=lib.check_dat(CT.create_string_buffer(old),len(old),CT.create_string_buffer(F.trust(old)),unit)
        assert got==0 and rejected!=0
        rows.append(dict(profile=profile,unit=unit,current_result=got,old_result=rejected,DAT_sha256=C.sha(raw)))
C.save(C.HERE/'evidence/parsers.json',dict(status='PASS',rows=rows,library_sha256=C.sha((F.TMP/'parsers.dylib').read_bytes()),
    boundary='Host C gate, semantic validator and UI-extension parser. Execution of the final M32R gate is recorded separately.'))
print(json.dumps(dict(status='PASS',cases=len(rows))))
