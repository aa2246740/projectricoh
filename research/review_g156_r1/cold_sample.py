"""Reviewed r4 driver, private outputs, strict_r3, always a fresh Machine."""
from pathlib import Path
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
sys.path.insert(1,str(C.ORIGINAL))
source=(C.ORIGINAL/'r2_strict_flow.py').read_text()
changes=[("tools/gxr_emulator_fast/strict_r2", "tools/gxr_emulator_fast/strict_r3"),
         ("if a.unit=='28mm':", "if a.unit=='28mm' and not a.target:"),
         ("if a.backend=='reference' and a.settings:", "cold_active=[True]\n        if a.backend=='reference':"),
         ("if u(0x200547ec)==6:boot_stores.append((at-settings,len(data),m.cpu.get_reg('pc')))",
          "if cold_active[0]:boot_stores.append((at-settings,len(data),m.cpu.get_reg('pc')))"),
         ("m.cpu.run(5000000)\n        base=", "m.cpu.run(5000000)\n        cold_active[0]=False\n        base="),
         ("result['io_counts']=N.export_state(m)['io_counts']", "result['io_counts']={str(k):v for k,v in m.cpu.io_counts.items()}")]
for old,new in changes:
    assert source.count(old)==1,old
    source=source.replace(old,new)
if os.environ.get('G156_REVIEW_NAMES'):
    names=os.environ['G156_REVIEW_NAMES'].split(';')
    anchor="        entries=[row for row in maps['after'][unit_name] if row['action']=='replace']"
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+"\n        entries=[row for row in entries if row['name'] in "+repr(names)+"]\n        assert {row['name'] for row in entries}==set("+repr(names)+")")
if os.environ.get('G156_REVIEW_CLOSE_EACH')=='1':
    anchor="\n            result['checks'].append(check)\n"
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+"""            key('DISP');key('OK');assert state()['state']==5 and state()['word']==2
            check['OK_close_this_recipe']=True
            open_menu();readback(expected)
            key('ADJ');assert state()['state']==5 and state()['word']==2
            check['ADJ_close_this_recipe']=True
            open_menu();readback(expected)
""")
if os.environ.get('G156_REVIEW_OLD_RECORD')=='1' or os.environ.get('G156_REVIEW_BOOT_ONLY')=='1':
    anchor="        maps=json.loads((C.HERE/'evidence'/('r2-maps-'+a.profile+'.json')).read_text())"
    assert source.count(anchor)==1
    if os.environ.get('G156_REVIEW_BOOT_ONLY')=='1':
        addition="""        assert a.settings and a.target
        assert m.cpu.read(S+0xfd4,40)==a.settings.read_bytes()[0xfd4:0xffc]
        result['BOOT_and_menu_readback']=readback(a.target.read_bytes())
        assert result['first_menu']['levels']==list(struct.unpack('>10h',a.settings.read_bytes()[0xfdc:0xff0]))
        result.update(record_40B_preserved=True,unit_W=writes(),status='PASS')
        return
"""
    else:
        addition="""        assert a.settings and not a.target
        old_record=a.settings.read_bytes()[0xfd4:0xffc]
        assert old_record[28:36]!=raw[20:28]
        assert m.cpu.read(S+0xfd4,40)==old_record
        assert writes()==0, 'old record caused a unit colour write'
        result['old_record_552_stock']=readback(D.expand(raw,unit,4),False)
        assert result['first_menu']['levels']==[100,0,0,0,0,0,0,0,0,0]
        assert u(S+0x36e,1)==1 and u(S+0x6dd,1)==u(S+0x6de,1)==9
        result.update(old_record_clean_reject=True,record_40B_preserved=True,
                      unit_W=0,status='PASS')
        return
"""
    source=source.replace(anchor,addition+anchor)
label=sys.argv[sys.argv.index('--label')+1]
assert label.isascii() and '/' not in label and '\\' not in label
p=C.LOCAL/'cold_drivers'/(label+'.py')
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(source)
scope=dict(__file__=str(p),__name__='review_g156_cold_driver')
exec(compile(source,str(p),'exec'),scope)
scope['main']()
