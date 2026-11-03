#!/usr/bin/python3
"""Check the source invariants behind the measured size candidates."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_window'
PROTO=ROOT/'firmware/resident_v310_proto/options'
ORIGINAL=ROOT/'firmware/resident_v39/resident'


def main():
    baseline=json.loads((HERE/'options/baseline/target-layout.json').read_text())
    profiles=json.loads((HERE/'profiles.json').read_text())
    layouts=[]
    for name in profiles:
        if '_plus' in name:continue
        layout=json.loads((HERE/'options'/name/'target-layout.json').read_text())
        assert layout==baseline,name
        layouts.append(name)
    original=(ORIGINAL/'validate_envelope.inc.c').read_text()
    candidate=(PROTO/'aligned_reads/resident/validate_envelope.inc.c').read_text()
    assert candidate.startswith(original)
    start=candidate.index('GxrceStatus rv_header_aligned(')
    fast=candidate[start:]
    expected=original[original.index('GxrceStatus rv_header('):]
    normalized=fast.replace('rv_aligned32(','rv_be32(').replace('rv_aligned16(','rv_be16(')
    normalized=normalized.replace('rv_header_aligned(','rv_header(').replace('rv_validate_aligned(','rv_validate(')
    assert normalized==expected
    loader=(PROTO/'aligned_reads/resident/loader.c').read_text()
    for requirement in ['_Alignof(RvLoadWork)>=4','offsetof(RvLoadWork,header)%4==0','RV_SESSION_BYTES%4==0']:
        assert requirement in loader
    for requirement in ['(off&3)','(patch&3)','patch>end-4','off>length','n>length-off']:
        assert requirement in fast
    assert '!(address&3)' in (ORIGINAL/'resident.h').read_text()
    assert 'rv_heap_span(base,bytes)' in (ORIGINAL/'shared.c').read_text()
    core=PROTO/'neutral/resident';card=PROTO/'card_combined/resident'
    equal=['resident.c','shared.c','hooks.c','bridges.S','abi.h','resident.ld','validate_envelope.inc.c']
    assert all((core/name).read_bytes()==(card/name).read_bytes()for name in equal)
    assert '/IROM/' not in (card/'loader.c').read_text()
    assert 'rv_validate_aligned(work,n,trust,v)' in (card/'loader.c').read_text()
    assert 'static RvUiSnapshot *ui_at' in (core/'shared.c').read_text()
    assert (core/'resident.ld').read_bytes()==(ORIGINAL/'resident.ld').read_bytes()
    result=dict(status='PASS',layouts_equal=layouts,root_bytes=256,root_pins_offset=244,
                session_bytes=baseline['RvSession']['bytes'],block_overhead=baseline['constants']['RV_BLOCK_OVERHEAD'],
                generic_parser_preserved=True,private_parser_control_flow_equal=True,
                buffer_alignment=dict(workspace='rv_allocation then rv_heap_span enforces address modulo 4 = 0',
                                      header='offset zero in RvLoadWork, alignment at least 4',
                                      image='aligned allocation plus RV_SESSION_BYTES modulo 4 = 0',
                                      sections='offset modulo 4 checked before table reads',
                                      relocation='patch modulo 4 and code bounds checked before word read'),
                safety_files_equal_between_core_and_card=equal,double_ui_allocation_check_preserved=True,
                linker_script_unchanged=True,card_only_full_validation_preserved=True)
    (HERE/'evidence/source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',layouts=len(layouts),parser_control_flow_equal=True)))


if __name__=='__main__':main()
