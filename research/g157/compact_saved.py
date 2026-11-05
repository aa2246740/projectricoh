"""Pass a read-only saved selection to UI consumers instead of copying it repeatedly."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();P=C.PRODUCT
p=P/'src/firmware/engine/core/eng_core.h';s=p.read_text()
s=s.replace('typedef enum { ENG_OK', 'typedef struct {EngRecipeRef ref;UvLevels levels;uint8_t user;} EngSavedSelection;\ntypedef enum { ENG_OK')
s=s.replace('int eng_saved_selection(EngRecipeRef *,UvLevels *,unsigned *);','const EngSavedSelection *eng_saved_selection(void);\nunsigned eng_active_code(void);')
p.write_text(s)
p=P/'src/firmware/engine/core/eng_core.c';s=p.read_text().replace('EngRecipeRef saved; UvLevels saved_t;','EngSavedSelection saved;').replace('uint8_t saved_user,memory_result,memory_error,auto_result;','uint8_t memory_result,memory_error,auto_result;')
s=s.replace('g->saved_t','g->saved.levels').replace('g->saved_user','g->saved.user').replace('g->saved=*r','g->saved.ref=*r')
start=s.index('int eng_saved_selection(');end=s.index('unsigned eng_memory_result(',start)
s=s[:start]+'''const EngSavedSelection *eng_saved_selection(void)
{return g->memory_result==1?&g->saved:0;}
unsigned eng_active_code(void)
{return !g->committed?0:g->current_user?0x80u+g->current_user-1:g->current.effect?0x40u+g->current.effect-1:g->current.slot;}
'''+s[end:]
s=s.replace('g->saved.effect','g->saved.ref.effect').replace('g->saved.slot','g->saved.ref.slot')
p.write_text(s)
p=P/'src/firmware/engine/core/eng_boot.inc.c';s=p.read_text().replace('g->saved_t','g->saved.levels').replace('g->saved_user','g->saved.user').replace('g->saved=ref','g->saved.ref=ref')
# Rebuild the cached record and compare exactly; no second decode or source substitution.
s=s.replace('if(memory_decode(record,&ref,&levels,&user)!=1||compute(&ref,&levels,wb)!=ENG_OK){diag_reason(21,BF_RECORD);goto clean;}',
    '''ref=g->saved.ref;levels=g->saved.levels;user=g->saved.user;
    memory_build(g->staging,&ref,&levels,user);
    if(!equal(record,g->staging,40)){diag_reason(30,BF_EPOCH);goto clean;}
    if(compute(&ref,&levels,wb)!=ENG_OK){diag_reason(21,BF_RECORD);goto clean;}''')
p.write_text(s)
p=P/'adapter.c';s=p.read_text()
start=s.index('static unsigned uv_saved_row(void)');end=s.index('static int uv_adjusted',start)
s=s[:start]+'''static unsigned uv_saved_row(void)
{
    const EngSavedSelection *saved=eng_saved_selection();unsigned i,count=uv_looks();
    if(!saved)return 255;
    if(saved->user)return 8+count+saved->user-1;
    if(!saved->ref.effect)return saved->ref.slot-1;
    for(i=0;i<count;++i)if(fx_visible(eng_validated_view(),saved->ref.unit,i)+1==saved->ref.effect)return 8+i;
    return 255;
}
'''+s[end:]
s=s.replace('const uint8_t *e;UvLevels t,saved;EngRecipeRef ref;unsigned user;', 'const uint8_t *e;UvLevels t;const EngSavedSelection *saved=eng_saved_selection();')
s=s.replace('else if(eng_saved_selection(&ref,&saved,&user)&&ref.effect==(unsigned)index+1u)t=saved;', 'else if(saved&&saved->ref.effect==(unsigned)index+1u)t=saved->levels;')
start=s.index('    {EngRecipeRef ref;UvLevels t;unsigned user,row,remembered=');end=s.index('    /* Fn rotation:',start)
s=s[:start]+'''    {const EngSavedSelection *saved=eng_saved_selection();unsigned row;
     if(saved){if(saved->user)n.ui.saved[saved->user-1]=saved->levels;else if(!saved->ref.effect)n.values[saved->ref.slot-1]=saved->levels;}
     uv_sync();n.ui.confirmed_user=n.ui.applied_user;n.ui.screen=UV_L1;n.ui.cur=uv_current_row();n.ui.armed=n.ui.top=0;
     n.spare.io.preselect=0;row=saved?uv_saved_row():255;
     if(row<255&&!eng_active_code()){n.ui.cur=(uint8_t)row;n.spare.io.preselect=(uint8_t)(row+1);}}
'''+s[end:]
p.write_text(s)
p=P/'diagnostic.c';s=p.read_text().replace('if(!row){EngRecipeRef ref;UvLevels t;', 'if(!row){unsigned active=eng_active_code();')
s=s.replace('if(eng_display_current(&ref,&t)==ENG_OK){unsigned user=eng_current_user();hex(out+11,user?0x80u+user-1:ref.effect?0x40u+ref.effect-1:ref.slot,2);}', 'if(active)hex(out+11,active,2);')
p.write_text(s)
p=C.HERE/'layout.py';s=p.read_text().replace("'saved','saved_t','saved_user'","'saved.ref','saved.levels','saved.user'");p.write_text(s)
print('saved selection has one read-only UI view')
