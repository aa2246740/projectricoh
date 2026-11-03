"""S-1 static proof: service numbers at every service call site of the final g139 ELF.

Every DAT service request is issued through one of three wrappers:
  svc.constprop.0  (eng_core.c svc: id in r0)  -> EngPort.call = core_call
  core_call        (adapter.c: id in r1)       -> n.api->call = rv_call
  pn_call.constprop.0 (panel_port.c: id in r0) -> port.api->call = rv_call
For each direct `bl` to a wrapper this resolves the id register to the last
`ldi` in the same straight-line block. The proof fails if any site is
unresolved or resolves to RV_STORAGE (1). It also lists every indirect `jl`
in the image with its function, so the reviewer can confirm that only the
wrappers reach rv_call. Output: research/g139_fix/service-proof.json.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ELF = ROOT / sys.argv[1] if len(sys.argv) > 1 else ROOT / 'firmware/engine_v56_g139/candidate/local/full-r13/engine.elf'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
WRAPPERS = {'svc.constprop.0': 'r0', 'core_call': 'r1', 'pn_call.constprop.0': 'r0'}
# Values from firmware/resident_v38/resident/abi.h enum RvService.
NAMES = {1: 'STORAGE', 2: 'LEASE', 3: 'CACHE', 4: 'RPC8', 5: 'PREVIEW', 6: 'SETTINGS', 7: 'UNIT', 8: 'SD_ID',
         9: 'EPOCHS', 10: 'UI_LIST', 11: 'UI_TEXT', 12: 'UI_VIEW', 13: 'EVENTS', 14: 'QUERY', 15: 'CRC32', 16: 'SHA256'}


def main():
    text = subprocess.check_output([str(OBJDUMP), '-d', str(ELF)], text=True)
    rows, function = [], None
    for line in text.splitlines():
        head = re.match(r'^([0-9a-f]+) <([^>]+)>:$', line)
        if head:
            label = head.group(2)
            if not label.startswith('.L'):
                function = label
            rows.append(('label', int(head.group(1), 16), label, function))
            continue
        m = re.match(r'^\s+([0-9a-f]+):\t[0-9a-f ]+\t(.*)$', line)
        if m:
            rows.append(('insn', int(m.group(1), 16), m.group(2).strip(), function))
    sites, indirect = [], []
    for index, (kind, address, asm, owner) in enumerate(rows):
        if kind != 'insn':
            continue
        if re.search(r'\bjl r\d+', asm):
            indirect.append(dict(address=hex(address), function=owner, insn=asm))
        call = re.search(r'\bbl [0-9a-f]+ <([^>+]+)>', asm)
        if not call or call.group(1) not in WRAPPERS or owner == call.group(1):
            continue
        register = WRAPPERS[call.group(1)]
        value = None
        # The id may be loaded in the same parallel pair (ldi r0,#9 -> bl svc).
        pieces = [asm] + [rows[j][2] for j in range(index - 1, max(-1, index - 24), -1) if rows[j][0] == 'insn']
        for j, piece in enumerate(pieces):
            if j and rows[index - j][0] == 'label':
                break
            for part in reversed(re.split(r'\s*(?:->|\|\|)\s*', piece)):
                m = re.match(r'ldi ' + register + r',#(-?\d+)$', part)
                if m and value is None:
                    value = int(m.group(1))
                elif re.match(r'(mv|ld\w*|add3|or3|seth) ' + register + r',', part) and value is None:
                    value = 'UNRESOLVED'
            if value is not None:
                break
        sites.append(dict(address=hex(address), caller=owner, wrapper=call.group(1),
                          id=value, service=NAMES.get(value, 'UNRESOLVED')))
    used = sorted({s['service'] for s in sites})
    bad = [s for s in sites if s['id'] == 1 or not isinstance(s['id'], int)]
    result = dict(status='PASS' if not bad else 'FAIL', elf=str(ELF.relative_to(ROOT)),
                  elf_sha256=hashlib.sha256(ELF.read_bytes()).hexdigest(), sites=sites, services_used=used,
                  storage_sites=[s for s in sites if s['id'] == 1], unresolved=[s for s in sites if not isinstance(s['id'], int)],
                  indirect_calls=indirect)
    (Path(__file__).resolve().parent / 'service-proof.json').write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(dict(status=result['status'], sites=len(sites), services_used=used, unresolved=len(result['unresolved']),
                          indirect=len(indirect))))
    sys.exit(0 if not bad else 1)


if __name__ == '__main__':
    main()
