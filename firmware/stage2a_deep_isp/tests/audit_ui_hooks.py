#!/usr/bin/env python3
"""Audit the actual Stage 1b nine hooks and the Stage 2a eight replacements."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
OUT = ROOT/'research/stage2a_deep_isp/ui_regression'


def main():
    baseline = ROOT/'artifacts/stage1b-candidate/packages/stage1b-16-recipes-012bcd24e77b'
    stock = (ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    before = (baseline/'candidate/SD_ROOT/ilaunch3').read_bytes()
    candidate = (HERE/'build/candidate/ilaunch3').read_bytes()
    assert hashlib.sha256(before).hexdigest() == 'd01a26dea0e72609ffacc1ea1e31083e8d350b131293c09dc082466fb4a4de63'
    segments = [struct.unpack_from('>5I',stock,32+i*20) for i in range(16)]

    def offset(va, count):
        hits = [src+512+va-base for src,base,n,_,_ in segments if base <= va and va+count <= base+n]
        assert len(hits) == 1
        return hits[0]

    old = json.loads((baseline/'evidence/hooks.json').read_text())['hooks']
    new = json.loads((HERE/'build/hooks.json').read_text())['hooks']
    assert len(old) == 9 and len(new) == 8
    assert {h['id'] for h in old} - {h['id'] for h in new} == {'force_adj_image'}
    assert not ({h['id'] for h in new} - {h['id'] for h in old})
    records = []
    for h in old:
        va, size = int(h['va'],16), h['length']
        start = offset(va,size)
        assert start == int(h['file_offset'],16)
        assert stock[start:start+size] == bytes.fromhex(h['original_bytes'])
        assert before[start:start+size] == bytes.fromhex(h['new_bytes'])
        after = next((v for v in new if v['id'] == h['id']),None)
        expected = bytes.fromhex(after['new_bytes'] if after else h['original_bytes'])
        assert candidate[start:start+size] == expected
        records.append(dict(id=h['id'],vma=h['va'],file_offset=h['file_offset'],
                            before=before[start:start+size].hex(),after=expected.hex(),
                            disposition='removed; official bytes restored' if after is None else 'retained with current ELF target'))
    requested = []
    for va in (0x201e47ac,0x201e483c,0x201e46c0,0x201e4c9c,0x201e4d5c):
        start = offset(va,8)
        assert stock[start:start+8] == before[start:start+8] == candidate[start:start+8]
        requested.append(dict(runtime_vma=hex(va),file_offset=hex(start),
                              bytes=stock[start:start+8].hex(),unchanged_in_both=True))
    protected = []
    for label,va,end in (
        ('ADJ function dispatcher',0x202ba6fc,0x202ba9e8),
        ('ADJ function case table',0x20377434,0x20377460),
        ('Fn2 native activity gate',0x202be23c,0x202be24c),
        ('Live native activity gate',0x202bb960,0x202bb968)):
        start = offset(va,end-va)
        assert candidate[start:start+end-va] == stock[start:start+end-va]
        protected.append(dict(name=label,vma=hex(va),length=end-va,byte_identical=True))
    report = dict(passed=True,actual_stage1b_hooks=records,requested_runtime_windows=requested,
                  protected_native_paths=protected,stage1b_sha256=hashlib.sha256(before).hexdigest(),
                  candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                  address_correction='file offset 0x1e47ac maps to runtime 0x2022f5ac; runtime 0x201e47ac is a distinct unchanged ISO instruction window',
                  native_up_down_handlers_patched=False,custom_up_down_commit_cancel_symbols=False,
                  camera_executed=False)
    (OUT/'hook_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'old_hooks':9,'new_hooks':8,'requested_windows_unchanged':5}))


if __name__ == '__main__':
    main()
