"""Check the unchanged init graph around the eight-instruction RAM change."""
from pathlib import Path
import difflib
import json
import re
import sys
import types

sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_scope import ROOT,SOURCE,OUT,load,save,sha,record_inputs


def main():
    common=types.ModuleType('common')
    common.ROOT,common.OUT=ROOT,SOURCE
    common.load,common.save,common.sha=load,save,sha
    sys.modules['common']=common
    c=load(SOURCE/'codegen.py','review_init_translation')
    atoms={g:c.atoms(g,'ig_init')[0] for g in (119,120)}
    norm,branches={},{}
    for g in atoms:
        norm[g],branches[g],_=c.symbolic(g,'ig_init',atoms[g])
    compare=lambda rows:[re.sub(r'self@\d+','SELF',row) for row in rows]
    matcher=difflib.SequenceMatcher(None,compare(norm[119]),compare(norm[120]),autojunk=False)
    changes=[op for op in matcher.get_opcodes() if op[0]!='equal']
    assert len(changes)==1 and changes[0][0]=='insert',changes
    _,old_begin,old_end,new_begin,new_end=changes[0]
    assert new_end-new_begin==8
    mapping={}
    for op,a,b,x,y in matcher.get_opcodes():
        if op=='equal':
            mapping.update(zip(range(a,b),range(x,y)))
    assert len(mapping)==len(atoms[119])
    old_br={x['atom']:x for x in branches[119]}
    new_br={x['atom']:x for x in branches[120]}
    targets={g:c.data_targets(g,'ig_init',atoms[g]) for g in atoms}
    data_checks=[]
    for old,new in mapping.items():
        a,b=atoms[119][old],atoms[120][new]
        assert compare([norm[119][old]])==compare([norm[120][new]])
        ra,rb=bytes.fromhex(a['raw']),bytes.fromhex(b['raw'])
        if len(ra)==2:ra=(int.from_bytes(ra,'big')&0x7fff).to_bytes(2,'big')
        if len(rb)==2:rb=(int.from_bytes(rb,'big')&0x7fff).to_bytes(2,'big')
        if old in old_br:
            x,y=old_br[old],new_br[new]
            assert x['opcode']==y['opcode']
            if x['logical'].startswith('self@'):
                target=mapping[int(x['logical'][5:])]
                assert y['logical']=='self@'+str(target)
            else:
                assert x['logical']==y['logical']
            if x['return_atom'] is not None:
                expected_return=new_begin if x['return_atom']==old_begin else mapping[x['return_atom']]
                assert expected_return==y['return_atom']
        elif a['relocation'] and a['relocation'][0] in {
            'R_M32R_GOTOFF_HI_SLO','R_M32R_GOTOFF_LO','R_M32R_GOTPC_HI_SLO','R_M32R_GOTPC_LO'}:
            assert a['relocation'][0]==b['relocation'][0] and ra[:2]==rb[:2]
        else:
            assert ra==rb,(old,new,a,b)
        if old in targets[119]:
            assert new in targets[120]
            check=c.check_data(targets[119][old],targets[120][new])
            assert check['equal'],check
            data_checks.append(check)
    added=[dict(pc=hex(row['pc']),asm=row['asm']) for row in atoms[120][new_begin:new_end]]
    expected=['ldub r4,@(64,r10)','add3 r1,r10,#186','ld r0,@(48,r10)',
              'stb r4,@(184,r10)','ldi r4,#4','add3 r0,r0,#224',
              'stb r4,@(185,r10)','bl eng_identity']
    assert norm[120][new_begin:new_end]==expected,norm[120][new_begin:new_end]
    inventory={r['name']:r for r in json.loads((OUT/'local_a/codegen-inventory.json').read_text())}
    assert inventory['eng_identity']['local_A'] and inventory['ig_copy']['local_A']
    save('init-translation.json',dict(status='PASS_A_PLUS_C',function='ig_init',
        old_atoms=len(atoms[119]),new_atoms=len(atoms[120]),aligned_atoms=len(mapping),
        instruction_map=[dict(old=hex(atoms[119][i]['pc']),new=hex(atoms[120][j]['pc'])) for i,j in mapping.items()],
        data_checks=data_checks,added=added,
        contract='After successful map/data validation and the stock/live copies, initialize g.current.unit, slot=4 and identity[49]. The only added stores are g+184..g+234; the Engine object is 2540 bytes. The new block issues no RPC, file or UI service.',
        preserved='Every old instruction, stack operation, branch destination, call return point and data reference retains its mapped counterpart. Both directions of every existing init branch are included.'))
    record_inputs('init-inputs.json')
    print('PASS init translation:',len(mapping),'aligned atoms; eight RAM instructions')


if __name__=='__main__':
    main()
