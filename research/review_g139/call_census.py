"""Check direct native file-mutation callers in the final ELF."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from static_review import body_at

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ELF=ROOT/'firmware/engine_v56_g139/candidate/local/full-r13/engine.elf'
OBJDUMP=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
listing=subprocess.check_output([str(OBJDUMP),'-d',str(ELF)],text=True)
(HERE/'evidence/engine-disassembly.txt').write_text(listing)
calls=[]
owner=None
for line in listing.splitlines():
    head=re.match(r'^([0-9a-f]+) <([^>]+)>:$',line)
    if head and not head.group(2).startswith('.L'): owner=head.group(2)
    address=re.match(r'^\s*([0-9a-f]+):',line)
    call=re.search(r'\bbl(?:\.[sl])?\s+([0-9a-f]+) <([^>+]+)',line)
    if call:
        calls.append(dict(pc='0x'+address.group(1),caller=owner,target=call.group(2)))
mutations=('rv_native_create','rv_native_write','rv_native_rename','rv_native_delete')
bad=[row for row in calls if row['target'] in mutations]
assert not bad,bad
native=[row for row in calls if row['target'].startswith('rv_native_')]
body=(ROOT/'firmware/package_v38_g139_test/local/SD_ROOT/ilaunch3').read_bytes()
lock_reference=(ROOT/'research/persist_recipe_r2/local/lock-core.bin').read_bytes()
assert body_at(body,0x20060b84,len(lock_reference))==lock_reference
result=dict(status='PASS_STATIC',elf_sha256=hashlib.sha256(ELF.read_bytes()).hexdigest(),
            native_calls=native,mutating_native_calls=bad,
            note='The bridge object retains native mutation wrappers. They have no direct caller in the final DAT. The common native trampoline is shared by all wrappers; its symbol label alone is not its purpose.',
            read_control_file='/ATA1/GXRCE.CTL',storage_service='RV_UNSUPPORTED before dispatch',
            lock_core=dict(address='0x20060b84',bytes=len(lock_reference),sha256=hashlib.sha256(lock_reference).hexdigest(),current_body_equal=True))
(HERE/'evidence/call-census.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
