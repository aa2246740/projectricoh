"""Check recorded native effects against exact final and reference artifacts."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import *
from static_audit import symbols

def main():
    spans=symbols(ELF)
    records=[]
    for generation,unit in ((124,'50mm'),(121,'50mm'),(126,'50mm'),(126,'28mm'),(126,'mount')):
        path=OUT/'local/ownership-settings'/f'{generation}-{unit}.json'
        r=json.loads(path.read_text())
        assert not r['native_UI']['host_ui_writes'] and not r['native_UI']['getter_callback_present']
        assert not any(r['file_mutations'].values())
        arrow,switch=r['events']
        assert arrow['before']['rows']==7 and arrow['after']['mode']==5
        assert switch['before']['rows']==8 and switch['after']['native_activity']==7
        assert switch['before']['root']['inflight']==switch['after']['root']['inflight']==1
        stores=r['stores_after_switch']
        owners=[]
        if generation==126:
            assert r['dat_sha256']==PIN and len(stores)==3
            assert {x['offset']:x['value'] for x in stores}=={'0x6dd':9,'0x6de':9,'0x36e':1}
            assert all(x['activity']==7 and x['state']==56 for x in stores)
            assert r['final']['mode']==1
            image_base=r['final']['root']['code_address']-256
            for row in stores:
                pc=int(row['pc'],16)-image_base
                found=[dict(symbol=name,elf_pc=hex(pc),**item) for name,item in spans.items()
                       if item['address']<=pc<item['address']+item['size']]
                assert found
                owners.extend(found)
            assert any(x['service']==6 and x['operation']==2 for x in r['services_after_switch'])
        else:
            assert not stores and not r['services_after_switch'] and r['final']['mode']==5
        records.append(dict(generation=generation,unit=unit,source=str(path.relative_to(ROOT)),source_sha256=file_sha(path),
            dat_sha256=r['dat_sha256'],late_settings_stores=stores,compiled_owners=owners,
            original_native_mode_write_observed=True,host_UI_writes=0,file_mutations=0))
    save('evidence/findings-verified.json',dict(status='P1_NEW_LATE_SETTINGS_WRITES_CONFIRMED',records=records,
        scope='Two native task contexts sharing modeled RAM. Native constructors and direction handlers execute fixed-body instructions. No physical scheduling or camera reachability claim.'))
    print('P1 confirmed: three final units versus gen124/gen121 controls')

if __name__=='__main__':main()
