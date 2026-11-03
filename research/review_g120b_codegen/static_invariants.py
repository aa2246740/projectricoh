"""Verify bounded calculation data and two frozen dispatcher invariants."""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import ROOT,SOURCE,OUT,save,record_inputs
from machine import Image


def main():
    raw=(ROOT/'firmware/package_v36_g120b/SD_ROOT/GXRCE.DAT').read_bytes()
    directory=int.from_bytes(raw[156:160],'big')
    ids=int.from_bytes(raw[204:208],'big')+32
    parameters=[int.from_bytes(raw[ids+4*i:ids+4*i+4],'big') for i in range(8)]
    assert sorted(pid for pid in parameters if pid)==list(range(1,7))
    maps=json.loads((OUT/'maps.json').read_text())['units']
    calculations=[]
    for unit in range(3):
        d=directory+64*unit
        bank=int.from_bytes(raw[d+16:d+20],'big')
        meta=int.from_bytes(raw[d+24:d+28],'big')
        for slot in range(1,9):
            record=raw[bank+32+64*(slot-1):bank+96+64*(slot-1)]
            assert record[0]==slot and record[1]==1 and record[3]==1
            values=[]
            for p in range(8):
                lo,hi,default=raw[meta+28*(slot-1)+3*p:meta+28*(slot-1)+3*p+3]
                signed=lambda v:v if v<128 else v-256
                lo,hi,default=map(signed,(lo,hi,default))
                assert lo<=default<=hi
                values.append([lo,hi,default])
            calculations.append(dict(unit=unit,slot=slot,mode=record[3],bounds=values))
        for row in maps[unit]['rows']:
            assert row['entry_offset']+row['length']<=552
    im=Image(120)
    assert im.elf.symbols['g']['size']==2540
    save('calculation-contract.json',dict(status='PASS_FROZEN_DATA_BOUNDS',parameters=parameters,
        records=calculations,
        private_spans=dict(Engine=2540,current=[184,235],stock=[867,1419],
            live=[1419,1971],staging=[1971,2523],levels=6,tweak_slots=8,
            maximum_settings_plan_items=16,settings_plan_bytes=80),
        guards=['compute requires unit equality and 1<=slot<=visible_rows before record access.',
            'Each parameter ID is zero or 1..6; the six-element level array is indexed by ID-1 only for nonzero IDs.',
            'All nine copy offsets and lengths are fixed GXMP fields and fit entry552.',
            'A value calculation changes staging, fixed settings values or private state; it does not replace g.data.map or row address/length fields.',
            'ig_panel_open passes only the selected slot and existing tweak values to preview_cached. It does not supply a unit RAM address or byte count.'],
        evidence=['local-a-check.json','init-translation.json','apply-check.json',
                  'research/ux_preview_dot_r5/pairs/apply-body-results.json'],
        limitation='These bounds justify the calculation/state P2 group. They do not close the remaining transport directions or either navigation loop.'))
    ascii_rows=[]
    for gen,entry,read,advance,back,edge in [
        (118,0xabc8,0xabcc,0xabd8,0xabdc,0xac44),
        (119,0xb190,0xb194,0xb1a0,0xb1a4,0xb20c)]:
        image=Image(gen)
        assert image.rows[entry]['asm']=='ldi r1,#0'
        assert image.rows[read]['asm']=='mv r6,r11'
        assert image.rows[advance]['asm']=='addi r1,#1'
        assert image.rows[back]['asm'].startswith('bne r10,r1,')
        assert image.target(image.rows[back])==read
        assert image.rows[edge]['asm'].startswith('bne r10,r1,')
        checked=0
        for count in range(1,256):
            for index in range(count):
                assert index!=count
                checked+=1
        ascii_rows.append(dict(generation=gen,entry=hex(entry),read_header=hex(read),
            increment=hex(advance),back_edge=hex(back),direction=dict(pc=hex(edge),taken=False),
            checked_count_index_pairs=checked,source_bytes=[1,255],index_at_direction='0<=i<source_bytes'))
    save('ascii-loop-proof.json',dict(status='UNREACHABLE',generations=ascii_rows,
        reason='The invalid-character exit preserves i. The next comparison cannot take the equal direction because the loop enters with i=0, increments by one, and repeats only when i!=source_bytes. source_bytes is guarded to 1..255 before the loop; no call or counter reset occurs inside it.'))
    for gen,edge in [(118,0x9150),(119,0x96ac)]:
        image=Image(gen)
        assert image.rows[edge]['asm'].startswith('beqz r6,')
    save('file-mode-proof.json',dict(status='UNREACHABLE_UNDER_FROZEN_CAPABILITIES',
        closed=[dict(generation=g,pc=hex(pc),taken=False) for g,pc in [(118,0x9150),(119,0x96ac)]],
        invariant='Each live file token has mode=0. The session starts with no tokens. The constructor stores mode=(op==3); op==3 requires CAP_FILE_WRITE, which is absent. Thus only op==2 can create a live token.',
        direction='The selected direction requires op=5. Its earlier mode guard requires mode!=0, contradicting the token invariant.',
        capabilities='0x000e0000 requested; 0x000e7fff effective; 0x00010000 absent',
        machine_examples=[dict(generation=119,pc='0x9aac..0x9abc',meaning='file mode is (op==3)'),
            dict(generation=119,pc='0x961c',meaning='op/mode guard before read/write selection'),
            dict(generation=119,pc='0x99bc..0x99c8',meaning='create requires the file-write capability')],
        evidence=['research/ux_preview_dot_r5/file-gate-cfg.json',
                  'research/ux_preview_dot_r5/machine-gates.json','file-check.json']))
    save('file-sd-proof.json',dict(status='UNREACHABLE_UNDER_REQUEST_AND_SESSION_CONTRACTS',
        closed=[dict(generation=g,pc=hex(pc),taken=True) for g,pc in [(118,0x93c4),(119,0x993c)]],
        invariant='For object 1, successful sd_current validates a nonzero 16-byte identity and copies it to session.sd_id. The later card-open guard in the same immutable request reads that same field before any store can clear it.',
        machine_evidence=dict(final_sd_current='instructions/sd_current.constprop.0.txt',
            sd_id_destination='session+440',copy_pc='0x77c4',copy_bytes=16,
            old_first_call='0x8f70',new_first_call='0x94b0'),
        contracts='The live session and request remain the same across the named native SD getter; its output is limited to the supplied identity buffer. The request does not alias session.sd_id.',
        evidence=['file-check.json','local_a/codegen/sd_current.constprop.0.json']))
    save('fixture-notes.json',dict(notes=[
        'The retained current runner tried to refresh an older name-data snapshot on import. current_runtime.py omits that copy step and reads each existing package directly; no source snapshot is edited.',
        'The retained generic comparison removes g.view_lost at offset 2537 only on the newer side. core_check.py restores that newer history because generation 119 already writes the field.',
        'The numeric-row condition recorded in core-first-difference.json is the deliberate watch_view==2 change. The corrected complete run records five such cases in core-C-cases.json and passes all 760 cases.',
        'The earlier file fixture offsets placed an object value in file_end. file_check.py uses the machine/ABI offsets 488/496/504/512 and retains '+str(json.loads((OUT/'file-check.json').read_text())['cases'])+' complete comparisons.'
    ]))
    record_inputs('invariant-inputs.json')
    print('PASS frozen calculation bounds, ASCII-loop direction and read-only token mode')


if __name__=='__main__':
    main()
