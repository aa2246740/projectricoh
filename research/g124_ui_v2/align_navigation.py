"""Retain the intermediate artifact and align the adapter with the approved prototype."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

phase=OUT/'local/history/navigation-alignment-74972f244c62'
assert not phase.exists()
phase.mkdir(parents=True)
for name in ('ui-cases','cases','safety','lock-cases','nested','cutpoints-irq-enabled','view-reentry'):
    path=OUT/'local'/name
    if path.exists():shutil.move(str(path),str(phase/name))
for path in list((OUT/'evidence').iterdir()):
    if path.name!='algorithm-ranges.json':shutil.move(str(path),str(phase/path.name))
for path in list((OUT/'local').iterdir()):
    if path.is_file() and (path.name.endswith('.log') or path.name.startswith(('official-half-','labels-','users-','remaining-window'))):
        shutil.move(str(path),str(phase/path.name))
for name in ('GXRCE.DAT','engine.elf','engine.bin','layout.json'):
    shutil.copyfile(TREE/'candidate/local/full-r13'/name,phase/name)
shutil.copyfile(TREE/'candidate/containers/product/adapter.c',phase/'adapter-before-navigation-fix.c')
path=OUT/'implement_ui.py';source=path.read_text()
source=source.replace('if(status==ENG_OK)n.ui.cur=(uint8_t)target;',
    'if(status==ENG_OK){\n        n.ui.cur=(uint8_t)target;\n        if(n.ui.screen==UV_ITEMS&&target)n.ui.card_cur=(uint8_t)(1+(target-1)/2);\n    }')
old='''        else{n.ui.group=(uint8_t)cur;n.ui.screen=UV_ENTRIES;n.ui.cur=1;
            user=uv_group_entry(1);
            if(user){const uint8_t *entry=uv_user(eng_validated_view(),user-1);
                if(uv_preview(entry[0],&n.ui.saved[user-1],user)!=ENG_OK){n.ui.screen=UV_GROUP;n.ui.cur=(uint8_t)cur;return RV_FAULT;}}
        }break;'''
assert old in source
source=source.replace(old,'        else{n.ui.group=(uint8_t)cur;n.ui.screen=UV_ENTRIES;n.ui.cur=1;}\n        break;')
old='        else if(uv_group_entry(cur)){n.ui.entry_cur=n.ui.cur;n.ui.origin=UV_ENTRIES;n.ui.screen=UV_CARD;n.ui.cur=1;}'
assert old in source
source=source.replace(old,'''        else if((user=uv_group_entry(cur))){
            const uint8_t *entry=uv_user(eng_validated_view(),user-1);
            if(uv_preview(entry[0],&n.ui.saved[user-1],user)!=ENG_OK)return RV_FAULT;
            n.ui.entry_cur=n.ui.cur;n.ui.origin=UV_ENTRIES;n.ui.screen=UV_CARD;n.ui.cur=1;
        }''')
source=source.replace('uv_sync();n.ui.screen=UV_L1;', 'uv_sync();n.ui.confirmed_user=n.ui.applied_user;n.ui.screen=UV_L1;')
path.write_text(source)
path=OUT/'user_acceptance.py';source=path.read_text().replace("assert s.state()['labels'][1]=='>FCC*025'\n    s.match(5,[1]+[0]*10)",
    "assert s.state()['labels'][1]==' FCC*025'\n    s.match(8,[0]*11)\n    s.press('DISP');assert s.state()['screen']==1\n    s.match(5,[1]+[0]*10)\n    s.goto(1,0);s.press('DISP');assert s.state()['screen']==5")
path.write_text(source)
path=OUT/'ui_acceptance.py';source=path.read_text().replace("s.press('OK');assert s.state()['rows']==7\n            s.match(5,expected)",
    "s.goto(2,0);s.press('DISP');assert s.state()['screen']==1 and s.state()['cur']==1+param//2\n            s.press('OK');assert s.state()['rows']==7\n            s.match(5,expected)")
path.write_text(source)
(phase/'NOTE.md').write_text('Intermediate gen 124 74972f24. The W/ownership-loss latch repair is retained. Final navigation aligns item-to-card return with the last selected item, preserves effects on group entry, and previews an entry on DISP. Intermediate runs do not count as final-candidate acceptance.\n')
print('Aligned navigation; intermediate evidence retained.')
