"""Apply the reviewable g156 -> g157 source transformation once."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
P=C.PRODUCT
def edit(rel,old,new):
    p=P/rel;s=p.read_text();assert s.count(old)==1,(rel,old,s.count(old));p.write_text(s.replace(old,new))
for rel,old,new in (
 ('src/firmware/card_container_v2/gate.c','build_number==156','build_number==157'),
 ('src/firmware/engine/core/eng_data.c','build_number==156','build_number==157'),
 ('ui_v2_data.c','build_number!=156','build_number!=157'),
 ('pack.py','build == 155','build == 157'),
 ('src/firmware/card_container_v2/gxrce.h','GXR2_DESCRIPTOR=20,','GXR2_FX_MAX=48, GXR2_DESCRIPTOR=20,'),
 ('fx_pool.c','be16(a+8)>48','be16(a+8)>GXR2_FX_MAX'),
 ('adapter.c','"blackbox.h"','"diagnostic.h"')):edit(rel,old,new)
p=P/'adapter.c';p.write_text(p.read_text().replace('"g155c"','"g157"').replace('G155_BOOT','G157_BOOT'))
p=C.ENGINE/'candidate/engine_services/services.c';s=p.read_text()
start=s.index('static int owned_record(');end=s.index('static int32_t settings(',start)
s=s[:start]+'''static int __attribute__((noinline)) owned_record(const uint8_t p[40])
{ return memory_owned(p,gxrce_crc32(p,36)); }
'''+s[end:];s='#include "../memory_codec.h"\n'+s;p.write_text(s)
p=P/'src/firmware/engine/core/eng_core.c';s=p.read_text()
s=s.replace('#include "eng_internal.h"','#include "eng_internal.h"\n#include "../../../../../../memory_codec.h"\n#include "../../../../diagnostic.h"')
s=s.replace('} Engine;\nstatic Engine g;','''    EngRecipeRef saved; UvLevels saved_t;
    uint32_t saved_epoch,saved_crc;
    uint8_t saved_user,memory_result,memory_error,auto_result;
} Engine;
_Static_assert(sizeof(Engine)<=DIAG_ENGINE_BYTES,"Engine arena bound");
#ifdef ENG_HOST
static Engine host_engine;
static Engine *g=&host_engine;
#else
static Engine *g;
#endif
int eng_attach_state(const RvPrivateContext *c)
{
    Engine *p;
    if(!c||c->state_bytes!=DIAG_ENGINE_BYTES+DIAG_BYTES||(c->state_address&3u)||
       c->state_address>UINT32_MAX-c->state_bytes||c->ui_state_address<c->state_address+c->state_bytes)return 0;
    p=eng_wire_pointer(c->state_address);if(!p)return 0;
#ifndef ENG_HOST
    if(g&&g!=p)return 0;
#endif
    g=p;return 1;
}''')
s=s.replace('g.','g->').replace('sizeof(g)','sizeof(*g)').replace('&g,sizeof(*g)','g,sizeof(*g)').replace('(uint8_t *)&g','(uint8_t *)g').replace('*p=&g;','*p=g;')
s=s.replace('if(!port || !port->call ||','if(!g || !port || !port->call ||')
s=s.replace('g->memory_dirty=m!=RV_OK;g->memory_blocked=m==RV_CONFLICT;g->s_busy|=m==RV_BUSY;', '''g->memory_dirty=m!=RV_OK;g->memory_blocked=m!=RV_OK&&m!=RV_BUSY;
            g->memory_error=m==RV_OK?0:m==RV_BUSY?1:m==RV_CONFLICT?2:3;g->s_busy|=m==RV_BUSY;
            if(m==RV_OK){g->saved=*r;g->saved_t=*t;g->saved_user=g->memory_want?g->memory_user:g->current_user;g->memory_result=1;}''')
# A new explicit choice may replace a recognized old record after a failed attempt.
s=s.replace('if(!g->memory_blocked&&(g->memory_want||','if((g->memory_want||!g->memory_blocked)&&(g->memory_want||')
s=s.replace('if(status==ENG_OK&&!g->restore_done)status=boot_restore();','if(status==ENG_OK&&!g->remember_checked)status=boot_restore();')
start=s.index('static EngStatus boot_restore(void)\n{');end=s.index('/* Recipe number whose apply',start)
s=s[:start]+'''static EngStatus boot_restore(void)
{
    int mismatch=0;const uint8_t *S;
    eng_read_saved();g->remember_checked=1;
    /* Establish active 04 independently. Native Vivid/WB is never 04. */
    if(settings_match(&(unsigned){0},0)!=ENG_OK)return ENG_OK;
    S=eng_wire_pointer(io.info.address);
    if(!S||S[0x36e]!=1||S[0x6dd]!=9||S[0x6de]!=9||S[8]||
       live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2){
        if(t_seen>=0&&t_seen!=2){g->t_warn=1;g->t_warn_slot=4;}
        return ENG_OK;
    }
    g->baseline=g->live_verified=1;return ENG_OK;
}
void eng_boot_source(unsigned my){g->boot_my=(uint8_t)(my!=0);}
int eng_saved_selection(EngRecipeRef *r,UvLevels *t,unsigned *user)
{
    if(g->memory_result!=1)return 0;
    *r=g->saved;*t=g->saved_t;*user=g->saved_user;return 1;
}
unsigned eng_memory_result(void){return g->memory_result;}
unsigned eng_memory_error(void){return g->memory_error;}
unsigned eng_saved_code(void)
{return g->memory_result==1?(g->saved_user?0x80+g->saved_user-1:g->saved.effect?0x40+g->saved.effect-1:g->saved.slot):0;}
'''+s[end:]
p.write_text(s)
edit('src/firmware/engine/core/eng_core.h','unsigned eng_preselect(UvLevels *t);', '''int eng_saved_selection(EngRecipeRef *,UvLevels *,unsigned *);
void eng_read_saved(void);
unsigned eng_memory_result(void);
unsigned eng_memory_error(void);
unsigned eng_saved_code(void);''')
edit('src/firmware/engine/core/eng_internal.h','EngStatus eng_init(', 'int eng_attach_state(const RvPrivateContext *);\nEngStatus eng_init(')
# Retire every old blackbox writer and format, including dead file writers.
old=(C.BASE/'candidate/containers/product/blackbox.c').read_text()
control=old[old.index('static uint32_t get32'):old.index('static void binding')]
control=control[:control.index('static void p16')]+control[control.index('static uint32_t crc'):]
(P/'diagnostic.c').write_text('#include "diagnostic.h"\n#include "src/firmware/card_container_v2/internal.h"\n'+control+'''
static const RvPrivateContext *dc;
static BootDiagnostic *d;
void diag_init(const RvPrivateContext *c)
{
    dc=c;d=eng_wire_pointer(c->state_address+DIAG_ENGINE_BYTES);
    pn_zero(d,sizeof(*d));d->magic=0x47313537;
}
void diag_capture(unsigned entry)
{
    RvRoot *r=RV_PTR(dc->root_address);RvSession *s=RV_PTR(dc->session_address);
    if(d->entry)return;
    d->entry=(uint8_t)entry;d->phase=1;
    d->settings=RV_WORD(0x200c0dac);d->length=RV_WORD(0x200c0db0);
    d->mode=RV_BYTE(0x205d9a7f);d->submode=RV_BYTE(0x205d9a9f);
    d->my=RV_BYTE(0x205d9aa3);d->pending=RV_BYTE(0x205da00b);
    d->activity=RV_WORD(0x205d9bf8);d->state=RV_WORD(0x205d9c00);
    d->boot_word=r->reserved_lane;d->root_flags=r->flags;d->resident=r->state;
    d->source=(uint8_t)s->selected_source;d->settings_epoch=r->epoch[RV_S_E];
    d->first_failure=r->check_failure;
    if(entry==51)d->seen=7; /* H50 inferred from pending; H51 and DAT entry observed. */
    if(d->settings>=0x20000000u&&d->settings<=0x207ff000u&&d->length==0x1000){
        d->selection=RV_WORD(d->settings+0x2fc);d->selector=RV_BYTE(d->settings+0x36e);
        d->wb[0]=RV_BYTE(d->settings+0x6dd);d->wb[1]=RV_BYTE(d->settings+0x6de);
    }
}
void diag_reason(unsigned reason,uint32_t bits)
{ d->failed|=bits;if(!d->reason)d->reason=(uint8_t)reason; }
void diag_engine(unsigned stage){d->seen|=8;d->stage=(uint8_t)stage;}
unsigned diag_page(void)
{
    if(!d->entry){diag_capture(1);diag_reason(1,BF_DISPATCH);}
    if(d->shown||!d->reason)return 0;
    d->shown=1;return 1;
}
unsigned diag_code(void){return d->reason;}
static void hex(char *p,uint32_t value,unsigned n)
{static const char digits[]="0123456789ABCDEF";while(n){p[--n]=digits[value&15];value>>=4;}}
void diag_text(unsigned row,char out[14])
{
    EngRecipeRef ref;UvLevels t;unsigned user;
    pn_zero(out,14);
    switch(row){
    case 0:pn_copy(out,"G157B00R00A--",13);out[5]='0'+d->reason/10;out[6]='0'+d->reason%10;
        hex(out+8,eng_saved_code(),2);
        if(eng_display_current(&ref,&t)==ENG_OK)hex(out+11,ref.slot,2);
        else if(eng_baseline())pn_copy(out+11,"04",2);break;
    case 1:pn_copy(out,"F00000000R00",12);hex(out+1,d->failed,8);hex(out+10,eng_memory_result(),2);break;
    case 2:pn_copy(out,"M00U00Y00P00",12);hex(out+1,d->mode,2);hex(out+4,d->submode,2);hex(out+7,d->my,2);hex(out+10,d->pending,2);break;
    case 3:pn_copy(out,"A00000000H00",12);hex(out+1,d->activity,8);hex(out+10,d->seen,2);break;
    case 4:pn_copy(out,"V00000000T00",12);hex(out+1,d->state,8);hex(out+10,d->stage,2);break;
    case 5:pn_copy(out,"N00000000L00",12);hex(out+1,d->selection,8);hex(out+10,d->source,2);break;
    case 6:out[0]='S';hex(out+1,d->settings,8);hex(out+9,d->length,4);break;
    default:pn_copy(out,"I000000Q0D0G0",13);hex(out+1,d->selector,2);hex(out+3,d->wb[0],2);hex(out+5,d->wb[1],2);
        hex(out+8,d->resident,1);out[10]='0'+!!(d->boot_word&4);out[12]='0'+!!(d->boot_word&8);break;
    }
    (void)user;
}
''')
(P/'blackbox.c').unlink();(P/'blackbox.h').unlink()
edit('build.py',"HERE/'blackbox.c'","HERE/'diagnostic.c'")
edit('adapter.c','    if(id==RV_RPC8||id==RV_LEASE)ig_bx_event(id==RV_RPC8?8:9,op,a,r->token,r->detail,r->native_result);\n','')
edit('adapter.c','    ig_bx_init(n.context);','    if(!eng_attach_state(n.context))return finish(r,ENG_REJECTED);\n    diag_init(n.context);')
print('g157 structural source changes applied')
