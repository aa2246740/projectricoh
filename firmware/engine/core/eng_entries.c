#include "eng_entries.h"
typedef struct {
    uint8_t glyph[16][96]; uint32_t labels[16],table[16],details[16][3]; uint8_t state[64];
} NativeUi;
static struct {
    const RvApi *api; uint32_t context; RvRequest request;
    union { uint32_t align; uint8_t bytes[80]; } scratch;
    NativeUi *ui; uint32_t ui_lease,view; uint8_t initialized,active;
} n;
static void zero(void *p,unsigned bytes) { uint8_t *b=p; while(bytes--) *b++=0; }
static void copy(void *p,const void *q,unsigned bytes)
{ uint8_t *a=p; const uint8_t *b=q; while(bytes--) *a++=*b++; }
#ifndef ENG_HOST
uint32_t eng_wire_address(const void *p) { return (uint32_t)(uintptr_t)p; }
void *eng_wire_pointer(uint32_t a) { return (void *)(uintptr_t)a; }
#endif
static int request_ok(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *r)
{
    if(!api || !q || !r || api->version!=1 || api->bytes<sizeof(*api) || !api->call ||
       q->version!=1 || q->bytes!=sizeof(*q) || q->flags || q->args[0]!=context || !context) return 0;
    zero(r,sizeof(*r)); r->version=1; r->bytes=sizeof(*r); return 1;
}
static int32_t service(void *user,uint32_t sid,uint32_t op,uint32_t a,uint32_t b,
                       void *buffer,uint32_t bytes,uint32_t count,RvReply *r)
{
    RvRequest q=n.request; int32_t result; (void)user;
    if(bytes>sizeof(n.scratch.bytes)) { r->status=RV_RANGE; return RV_RANGE; }
    q.args[8]=a; q.args[9]=b; q.args[10]=0; q.args[11]=bytes; q.args[12]=count; q.args[13]=0;
    if(bytes) { copy(n.scratch.bytes,buffer,bytes); q.args[10]=eng_wire_address(n.scratch.bytes); }
    /* The init-supplied table owns dispatch, including engine-local services. */
    result=n.api->call(sid,op,&q,r);
    if(result==RV_OK && r->status==RV_OK && r->version==1 && r->bytes==sizeof(*r) && bytes)
        copy(buffer,n.scratch.bytes,bytes);
    return result;
}
static int32_t finish(RvReply *r,EngStatus s,int consumed)
{
    static const int32_t status[]={RV_OK,RV_CONFLICT,RV_UNCERTAIN,RV_STALE,RV_IO,RV_FAULTED};
    n.active=0; r->status=status[s]; r->detail=eng_stage();
    return s==ENG_OK?(consumed?RV_CONSUMED:RV_PASS):s==ENG_UNCERTAIN || s==ENG_FAULT?RV_FAULT:RV_CLOSE_AND_PASS;
}
static EngStatus ui_release(void)
{
    RvReply r; int32_t result;
    if(!n.view) return ENG_OK;
    result=service(0,RV_UI_LIST,4,n.view,0,0,0,0,&r);
    if(result!=RV_OK) return ENG_IO;
    n.view=0; return ENG_OK;
}
static void ui_description(RvUiList *d)
{
    zero(d,sizeof(*d)); d->header.version=1; d->header.bytes=sizeof(*d);
    d->view_token=n.view; d->state_address=eng_wire_address(n.ui->state); d->state_bytes=sizeof(n.ui->state);
    d->rows=16; d->cursor=eng_list()->cursor; d->label_table=eng_wire_address(n.ui->table);
    d->details=eng_wire_address(n.ui->details); d->lease_token=n.ui_lease;
}
static EngStatus ui_cursor(void)
{
    RvUiList d; RvReply r;
    if(!n.view || !n.ui) return ENG_STALE;
    ui_description(&d);
    return service(0,RV_UI_LIST,2,0,16,&d,sizeof(d),16,&r)==RV_OK?ENG_OK:ENG_IO;
}
static EngStatus ui_bind(void)
{
    const EngList *list=eng_list(); RvReply r; RvUiList d; RvUiText text; RvLeaseInfo lease;
    unsigned i; int32_t result;
    if(!n.ui) {
        zero(&lease,sizeof(lease)); lease.header.version=1; lease.header.bytes=sizeof(lease);
        if(service(0,RV_LEASE,1,sizeof(NativeUi),3,&lease,sizeof(lease),0,&r)!=RV_OK ||
           lease.header.version!=1 || lease.header.bytes!=sizeof(lease) || lease.length<sizeof(NativeUi) ||
           !lease.base || !lease.token) return ENG_IO;
        n.ui=eng_wire_pointer(lease.base); n.ui_lease=lease.token;
        zero(n.ui,sizeof(*n.ui)); n.ui->state[0]=5;
    }
    for(i=0;i<16;i++) {
        const char *source=list->row[i].ascii; unsigned count=0;
        while(count<32 && source[count]) count++;
        zero(&text,sizeof(text)); text.header.version=1; text.header.bytes=sizeof(text);
        text.source_address=eng_wire_address(source); text.source_bytes=count;
        text.source_lease=n.request.args[1]; text.glyph_address=eng_wire_address(n.ui->glyph[i]);
        text.glyph_capacity=96; text.glyph_lease=n.ui_lease;
        if(service(0,RV_UI_TEXT,2,0,0,0,0,0,&r)!=RV_OK) return ENG_IO;
        text.language=r.detail;
        if(service(0,RV_UI_TEXT,1,0,0,&text,sizeof(text),0,&r)!=RV_OK ||
           !text.actual_bytes || text.actual_bytes>96) return ENG_IO;
        n.ui->labels[i]=eng_wire_address(n.ui->glyph[i]); n.ui->table[i]=eng_wire_address(&n.ui->labels[i]);
    }
    ui_description(&d);
    n.ui->state[10]=list->cursor;
    result=service(0,RV_UI_LIST,1,0,16,&d,sizeof(d),16,&r);
    if(result!=RV_OK || !r.token) return ENG_IO;
    n.view=r.token; return ENG_OK;
}
static int enter(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    if(!request_ok(api,c,q,r) || !n.initialized || api!=n.api || c!=n.context) return 0;
    if(n.active) { r->status=RV_BUSY; return 0; }
    n.active=1; n.request=*q; return 1;
}
int32_t eng_entry_init(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngInitWire *w; EngPort port; EngStatus s;
    if(!request_ok(api,c,q,r) || n.initialized || n.active || q->args[11]!=sizeof(*w)) return RV_FAULT;
    w=eng_wire_pointer(q->args[10]);
    if(!w || w->header.version!=1 || w->header.bytes!=sizeof(*w) || w->header.flags ||
       !w->gate_view_address || w->gate_view_bytes!=sizeof(Gxr2View) ||
       (w->grain_address && w->grain_bytes!=sizeof(EngGrain)) || (!w->grain_address && w->grain_bytes)) return RV_FAULT;
    /* GXTM v2 has no authorized binding extension; reject a fabricated one. */
    if(w->wb[0].valid || w->wb[1].valid || w->wb[2].valid) return RV_FAULT;
    n.active=1; n.api=api; n.context=c; n.request=*q;
    zero(&port,sizeof(port)); port.call=service; port.grain=eng_wire_pointer(w->grain_address); port.gated=eng_wire_pointer(w->gate_view_address);
    s=eng_init(eng_wire_pointer(w->image_address),w->image_bytes,&port);
    if(s==ENG_OK) n.initialized=1;
    return finish(r,s,1);
}
int32_t eng_entry_menu(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus s;
    if(!enter(api,c,q,r)) return RV_FAULT;
    s=eng_menu_open(); if(s==ENG_OK) s=ui_bind();
    if(s!=ENG_OK) { (void)ui_release(); eng_menu_close(); }
    return finish(r,s,1);
}
int32_t eng_entry_event(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus s; unsigned event;
    if(!enter(api,c,q,r)) return RV_FAULT;
    event=q->args[8];
    /* Versioned engine-local event kinds: 1 selection, 2 close, 3 invalidate,
     * 4 rebind. Native physical keys remain the resident/panel's contract. */
    if(event==1) {
        EngStatus cursor;
        s=q->args[9]>=1 && q->args[9]<=16 ? eng_select((uint8_t)q->args[9]) : ENG_REJECTED;
        cursor=ui_cursor(); if(s==ENG_OK) s=cursor;
    }
    else if(event==2 || event==3) {
        s=ui_release(); eng_menu_close(); if(event==3) eng_invalidate();
    } else if(event==4) s=eng_rebind();
    else { n.active=0; return RV_PASS; }
    return finish(r,s,1);
}
int32_t eng_entry_apply(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngRecipeRef ref; EngTweak tweak; int i; uint32_t id;
    EngStatus s;
    if(!enter(api,c,q,r)) return RV_FAULT;
    s=eng_current(&ref,&tweak); if(s!=ENG_OK) return finish(r,s,1);
    /* IDs in the public vector follow the GXTM table. Querying metadata does
     * not expose IDs, so batch vectors are the engine-local apply wire. */
    if(q->args[10] && q->args[11]==sizeof(EngTweak)) tweak=*(const EngTweak *)eng_wire_pointer(q->args[10]);
    else {
        id=q->args[8];

        if(id<1 || id>6 || (int32_t)q->args[9]<-128 || (int32_t)q->args[9]>127) return finish(r,ENG_REJECTED,1);
        i=eng_parameter_index(id); if(i<0) return finish(r,ENG_REJECTED,1);
        tweak.v[i]=(int8_t)(int32_t)q->args[9];
    }
    return finish(r,eng_apply(&ref,&tweak),1);
}
static int32_t panel_unlinked(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    if(!enter(api,c,q,r)) return RV_FAULT;
    n.active=0; r->status=RV_UNSUPPORTED; return RV_CLOSE_AND_PASS;
}
static int32_t engine_stop(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus s;
    if(!enter(api,c,q,r)) return RV_FAULT;
    s=ui_release(); eng_menu_close();
    if(s==ENG_OK) s=eng_restore_stock();
    /* This is bounded by seven rows plus two control stores. Unknown W state
     * refuses recovery, and a caller must use its reviewed native failure path. */
    if(s!=ENG_OK) { (void)finish(r,s,0); return RV_FAULT; }
    return finish(r,ENG_OK,0);
}
#ifndef ENG_HOST
extern uint8_t __image_base[] __attribute__((visibility("hidden")));
static uint32_t offset(RvEngineEntry p)
{ return (uint32_t)((uintptr_t)p-(uintptr_t)__image_base); }
#else
static uint32_t offset(RvEngineEntry p) { return eng_wire_address((const void *)(uintptr_t)p); }
#endif
int32_t eng_bootstrap(const RvApi *api,uint32_t c,const RvRequest *q,RvReply *r)
{
    RvEngineEntries *e;
    if(!request_ok(api,c,q,r) || q->args[11]!=sizeof(*e)) return RV_FAULT;
    e=eng_wire_pointer(q->args[10]); if(!e) return RV_FAULT;
    e->version=1; e->bytes=sizeof(*e); e->init=offset(eng_entry_init); e->menu_open=offset(eng_entry_menu);
    e->event=offset(eng_entry_event); e->panel_open=offset(panel_unlinked); e->panel_event=offset(panel_unlinked);
    e->panel_abort=offset(panel_unlinked); e->apply_step=offset(eng_entry_apply); e->shutdown=offset(engine_stop); e->abort=offset(engine_stop);
    r->actual=sizeof(*e); r->status=RV_OK; return RV_CONSUMED;
}
