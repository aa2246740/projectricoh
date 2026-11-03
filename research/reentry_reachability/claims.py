"""Check the concrete links used by the report, without running firmware."""
from pathlib import Path
import json
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit
import flow


def main():
    audit.preflight()
    raw,sections=audit.image('v36')
    packets=flow.listing()
    index=json.loads((audit.LOCAL/'v36-index.json').read_text())
    refs=index['calls']+index['branches']
    checked=[]
    def op(pc,expected):
        packet=pc&~3
        actual=packets[packet][(pc-packet)//2]
        assert actual==expected,(hex(pc),actual,expected)
        checked.append(dict(address=pc,operation=actual))
    def link(site,target):
        assert any(r['source']==site and r['target']==target for r in refs),(hex(site),hex(target))
        checked.append(dict(source=site,target=target))
    def word(pc,value):
        assert int.from_bytes(audit.at(raw,sections,pc,4),'big')==value,hex(pc)
        checked.append(dict(address=pc,value=value))
    for site,target in [
        (0x2005cd7c,0x20069d4c),(0x202af5d8,0x202b1100),(0x202b1170,0x202b0b18),
        (0x202b0b66,0x20332c58),(0x20332c8e,0x2037280c),(0x20372822,0x20069160),
        (0x20069192,0x200690b0),(0x200690de,0x2005e078),(0x200690fe,0x2006aab8),
        (0x20069132,0x20069018),(0x20069068,0x20068de0),
        (0x20062fb4,0x20062a48),(0x20062a9e,0x20062914),(0x20072cee,0x20072594),
        (0x2007264a,0x20071fc0),(0x200726e6,0x20071fc0),(0x2007204a,0x2006a934),
        (0x200693e8,0x2006abdc),
        (0x202ba76c,0x20287080),(0x202b878a,0x202c25b8),(0x202b869a,0x202c2880),
        (0x202c27dc,0x202bb4bc),(0x202c2aa4,0x202bb4bc),
        (0x202b8d9a,0x202871d8),(0x202bd88e,0x202871d8),(0x202bea52,0x202871d8),
        (0x202c2d72,0x202871d8),(0x202c2d82,0x202871d8),
        (0x20053034,0x20054068),(0x20053e3c,0x20054598),(0x20052bfc,0x201c092c),
        (0x200900b6,0x2005e360),(0x2009011c,0x20093d48),(0x20090172,0x200949bc),
        (0x200949da,0x2005e628),(0x200949f2,0x2005e5ac),
        (0x201d73fa,0x201d330c),(0x201dc18c,0x201dc168),
        (0x2005ffea,0x2005fdfc),(0x2005fe6a,0x20060300),
        (0x20066a14,0x2006666c),(0x2006667e,0x2006b84c),(0x2006b9bc,0x2006b70c),
        (0x203ad5c8,0x2026ae50),(0x2026b16a,0x20268768),
    ]:link(site,target)
    for pc,expected in [
        (0x2005cee8,'ldi r4,#6'),(0x2005cef4,'or3 r5,r5,#0xcc7c'),
        (0x200630b0,'ldi r4,#3'),(0x200630c0,'or3 r5,r5,#0x2f18'),
        (0x20072e44,'or3 r6,r6,#0x1ee8'),(0x20072e4c,'ldi r7,#10'),
        (0x20071f08,'ldi r5,#64'),(0x20071f60,'ldi r5,#128'),
        (0x20071f38,'ldi r4,#20'),(0x20071f44,'ldi r4,#21'),
        (0x20062940,'ldi r5,#9748'),(0x20072c3c,'beq r5,r0,0x20072ce4'),
        (0x20072048,'ldi r4,#2'),(0x2006aa34,'st r8,@(8,r10)'),
        (0x200693cc,'or3 r4,r4,#0x929c'),(0x2006aa7c,'jl r0'),
        (0x2006aa38,'st r9,@(12,r10)'),(0x2006aa54,'st r12,@(16,r10)'),
        (0x2006938c,'ldi r4,#1'),(0x20069390,'ldi r6,#140'),
        (0x2006939c,'ldi r7,#8960'),(0x200692c0,'ldi r6,#2'),(0x200692d4,'ldi r7,#0'),
        (0x20068ef8,'ldi r0,#28683'),(0x20068efc,'sth r0,@(6,r8)'),
        (0x202aff40,'addi r9,#29'),(0x202aff4c,'addi r9,#58'),(0x202aff5c,'addi r9,#87'),
        (0x202b1298,'ld r0,@(4,r0)'),(0x202b12a4,'jl r0'),
        (0x202b1308,'ld r0,@(8,r0)'),(0x202b130c,'jl r0'),
        (0x20268774,'stb r4,@(878,r1)'),(0x20054078,'jl r4'),
        (0x20052bee,'ldi r5,#1'),(0x20052bf0,'ldi r6,#0'),
        (0x20052c0a,'st r0,@r1'),(0x0500c900,'sth r9,@r4'),
        (0x0500c92c,'mvtc r8,spu'),(0x0500c938,'mvtc r5,psw'),
        (0x203ad2e0,'or3 r5,r5,#0xd428'),(0x203ad2e4,'ld24 r6,0xff00'),
        (0x2006bbfc,'or3 r6,r6,#0xb70c'),(0x2006bc04,'ldi r5,#2'),
    ]:op(pc,expected)
    for pc,value in [
        (0x2037f738,0x203764c8),(0x203764cc,0x202ba5c8),(0x20376608,0x202be220),
        (0x20376544,0x202c2880),(0x20376550,0x202c2880),(0x20376574,0x202c2880),
        (0x2037655c,0x202c25b8),(0x20376568,0x202c25b8),(0x20376580,0x202c25b8),
        (0x20375f1c,0x000f0002),(0x20375f20,0x00100003),
        (0x200c169c,0x202aeaf8),(0x200c166c,0x20374208),
        (0x200c1628,0x203ad008),(0x203c32e4,0x203ad2a8),
        (0x20221084,0x201c49f4),(0x2022f71c,0x05ffffff),
    ]:word(pc,value)
    symbols=json.loads((audit.LOCAL/'resident-symbols.json').read_text())
    for pc,ident in [(0x2028709c,1),(0x202be24c,6),(0x202871d8,7),(0x202bb968,8)]:
        link(pc,symbols['rv_hook_'+f'{ident:02d}']['address'])
    callers=json.loads((audit.LOCAL/'callers.json').read_text())
    setter=next(r for r in callers if r['target']==0x20268768)
    assert len(setter['fixed_callers'])==68 and not setter['pointer_slots']
    assert all(r['owner_candidate'] for r in setter['fixed_callers'])
    audit.save('local/checked-sites.json',checked)
    fence_checks=[]
    for event,args in [('open',(str(audit.ROOT/'README.md'),'w',os.O_WRONLY)),('socket.connect',())]:
        try:audit.guard(event,args)
        except PermissionError:fence_checks.append(event)
        else:raise AssertionError('guard accepted disallowed operation')
    result=dict(status='PASS_STATIC',checked_facts=len(checked),fixed_setter_call_sites=68,
        ui_state_tables=106,write_and_network_guard_checks=fence_checks,
        camera_execution=False,new_firmware=False,new_dat=False,
        limitation='Checks establish bytes, literal references and local control flow; they do not prove every dynamic caller or camera scheduling.')
    audit.save('evidence.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
