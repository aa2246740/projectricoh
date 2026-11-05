"""Remove duplicated settings call setup while retaining each caller's checks."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();p=C.PRODUCT/'src/firmware/engine/core/eng_core.c';s=p.read_text()
s=s.replace('static void memory_build(', 'static void __attribute__((noinline)) memory_build(')
release='svc(RV_SETTINGS,3,io.info.token,0,0,0,0,&io.reply)'
s=s.replace(release,'settings_release()')
acquire='svc(RV_SETTINGS,1,0,0,&io.info,sizeof(io.info),0,&io.reply)'
s=s.replace('clear(&io.info,sizeof(io.info));io.info.header.version=1;io.info.header.bytes=sizeof(io.info);\n','')
s=s.replace('clear(&io.info,sizeof(io.info)); io.info.header.version=1; io.info.header.bytes=sizeof(io.info);\n','')
s=s.replace(acquire,'settings_info()')
at=s.index('/* read_record:')
s=s[:at]+'''static int32_t settings_info(void)
{
    clear(&io.info,sizeof(io.info));io.info.header.version=1;io.info.header.bytes=sizeof(io.info);
    return svc(RV_SETTINGS,1,0,0,&io.info,sizeof(io.info),0,&io.reply);
}
static int32_t settings_release(void)
{return svc(RV_SETTINGS,3,io.info.token,0,0,0,0,&io.reply);}
'''+s[at:]
p.write_text(s)
p=C.PRODUCT/'src/firmware/engine/core/eng_boot.inc.c';s=p.read_text().replace(release,'settings_release()').replace(acquire,'settings_info()')
s=s.replace('    clear(&io.info,sizeof(io.info));io.info.header.version=1;io.info.header.bytes=sizeof(io.info);\n','')
p.write_text(s)
p=C.PRODUCT/'boot_adapter.inc.c';s=p.read_text()
start=s.index('    if(bits&BF_ACTIVITY)reason=10;');end=s.index('    if(q->args[9]',start)
s=s[:start]+s[end:]
s=s.replace('bits|=BF_SETTINGS;if(!reason)reason=14;','bits|=BF_SETTINGS;').replace('bits|=BF_RECORD;if(!reason)reason=21;','bits|=BF_RECORD;').replace('bits|=BF_NATIVE;if(!reason)reason=20;','bits|=BF_NATIVE;')
s=s.replace('#if !G157_BOOT\n', '''    {static const uint8_t reasons[]={10,11,12,13,14,15,20,21};unsigned i;
     for(i=0;i<8;++i)if(bits&(2u<<i)){reason=reasons[i];break;}}
#if !G157_BOOT
''')
p.write_text(s)
# Install the remembered user's levels before uv_sync identifies an active user.
p=C.PRODUCT/'adapter.c';s=p.read_text()
old='''    uv_sync();n.ui.confirmed_user=n.ui.applied_user;n.ui.screen=UV_L1;n.ui.cur=uv_current_row();n.ui.armed=n.ui.top=0;
    n.spare.io.preselect=0;
    {EngRecipeRef ref;UvLevels t;unsigned user,row;
     if(eng_saved_selection(&ref,&t,&user)){
        if(user)n.ui.saved[user-1]=t;else if(!ref.effect)n.values[ref.slot-1]=t;
        row=uv_saved_row();
        if(eng_display_current(&ref,&t)!=ENG_OK&&row<255){n.ui.cur=(uint8_t)row;n.spare.io.preselect=(uint8_t)(row+1);}
     }}'''
new='''    {EngRecipeRef ref;UvLevels t;unsigned user,row,remembered=eng_saved_selection(&ref,&t,&user);
     if(remembered){if(user)n.ui.saved[user-1]=t;else if(!ref.effect)n.values[ref.slot-1]=t;}
     uv_sync();n.ui.confirmed_user=n.ui.applied_user;n.ui.screen=UV_L1;n.ui.cur=uv_current_row();n.ui.armed=n.ui.top=0;
     n.spare.io.preselect=0;
     row=remembered?uv_saved_row():255;
     if(row<255&&eng_display_current(&ref,&t)!=ENG_OK){n.ui.cur=(uint8_t)row;n.spare.io.preselect=(uint8_t)(row+1);}}'''
assert old in s;s=s.replace(old,new);p.write_text(s)
print('settings call setup shared; restored-user cache ordering corrected')
