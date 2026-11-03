#include "integrated.h"
typedef struct {
    const RvApi *api;
    RvPrivateContext *context;
    RvRequest request;
    Gxr2View gate, semantic;
    Gxr2Trust trust;
    PnPort port;
    PnPanel panel;
    PnGxts gxts;
    PsStore store;
    uint32_t rpc, view, irom_epoch;
    uint8_t initialized, active, install_attempted;
    int32_t install_status;
    union { uint32_t align; uint8_t bytes[80]; } scratch;
    uint8_t glyph[16][70],state[32],tweak_work[256];
    uint32_t labels[16],refs[16],details[16][3];
    RvUiList list;
    PnNativeSeed seed;
} Integrated;
static Integrated n;
#ifndef ENG_HOST
uint32_t eng_wire_address(const void *p) { return (uint32_t)(uintptr_t)p; }
void *eng_wire_pointer(uint32_t a) { return (void *)(uintptr_t)a; }
#endif
static uint32_t address(void *unused,const void *p,uint32_t bytes)
{ (void)unused;(void)bytes;return eng_wire_address(p); }
static void trust_init(void)
{
    static const uint8_t names[3][8]={"jlaunch","qlaunch","l08firm"};
    const uint8_t *p=n.gate.bytes;unsigned i;uint32_t pin;
    pn_zero(&n.trust,sizeof(n.trust));pn_copy(n.trust.body_sha256,p+48,32);
    pn_copy(n.trust.resident_build_id,p+80,32);pn_copy(n.trust.resident_abi_id,p+212,16);
    for(i=0;i<3;i++) {
        pn_copy(n.trust.modules[i].unit.name,names[i],8);n.trust.modules[i].unit.main_version=0x151;
        pin=rv_unit_pin((uint8_t)i);n.trust.modules[i].stock_crc32=pin;
        n.trust.modules[i].stock_sha256[0]=pin>>24;n.trust.modules[i].stock_sha256[1]=pin>>16;
        n.trust.modules[i].stock_sha256[2]=pin>>8;n.trust.modules[i].stock_sha256[3]=pin;
    }
}
static int ingress(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *r)
{
    RvPrivateContext *c;const RvApi *services;unsigned i;
    if(!q||!r||api||q->version!=1||q->bytes!=64||q->flags||q->args[0]!=context||
       q->args[11]!=sizeof(RvPrivateContext)||!q->args[10])return 0;
    pn_zero(r,sizeof(*r));r->version=1;r->bytes=32;r->status=RV_ARGUMENT;
    c=eng_wire_pointer(q->args[10]);services=rv_services_init(c);
    if(!services||c->nonce!=context||(n.context&&c!=n.context)||n.active)return 0;
    n.context=c;n.api=services;n.request=*q;n.active=1;
    n.port.api=services;n.port.context=context;n.port.io_lease=n.port.ui_lease=c->state_lease;
    n.port.address=address;
    for(i=0;i<6;i++)n.port.epochs[i]=q->args[2+i];
    return 1;
}
static int32_t finish(RvReply *r,EngStatus status)
{
    static const int32_t map[]={RV_OK,RV_CONFLICT,RV_UNCERTAIN,RV_STALE,RV_IO,RV_FAULTED};
    n.active=0;r->status=map[status];r->detail=eng_stage();
    return status==ENG_OK?RV_CONSUMED:(status==ENG_UNCERTAIN||status==ENG_FAULT?RV_FAULT:RV_CLOSE_AND_PASS);
}
static int32_t core_call(void *unused,uint32_t id,uint32_t op,uint32_t a,uint32_t b,
                         void *buffer,uint32_t bytes,uint32_t count,RvReply *r)
{
    RvRequest q=n.request;int32_t result;(void)unused;
    if(bytes>sizeof(n.scratch.bytes))return RV_RANGE;
    q.args[8]=a;q.args[9]=b;q.args[10]=bytes?eng_wire_address(n.scratch.bytes):0;
    q.args[11]=bytes;q.args[12]=count;q.args[13]=0;
    if(bytes)pn_copy(n.scratch.bytes,buffer,bytes);
    if(id==RV_RPC8&&op!=1)q.args[1]=n.rpc;
    if(id==RV_SETTINGS&&op==3)q.args[8]=0;
    result=n.api->call(id,op,&q,r);
    if(result==RV_OK&&r->status==RV_OK&&r->version==1&&r->bytes==32) {
        if(id==RV_RPC8&&op==1)n.rpc=r->token;
        if(id==RV_RPC8&&op==5)n.rpc=0;
        if(bytes)pn_copy(buffer,n.scratch.bytes,bytes);
    }
    return result;
}
static int32_t verify(void *unused,const PsObject *o,const uint8_t *p,uint32_t bytes,PsInfo *info)
{
    Gxr2View v;Gxr2Unit *u=&n.trust.modules[n.gate.selected_module].unit;(void)unused;
    if(o->kind!=PS_ENGINE||gxr2_validate(p,bytes,&n.trust,u,0,&v)!=GXR2_OK)return RV_VERIFY;
    info->generation=v.build_number;info->bytes=bytes;info->crc32=gxr2_crc32(p,bytes);return RV_OK;
}
static int32_t lease(uint32_t bytes,RvLeaseInfo *l)
{
    RvReply r;pn_zero(l,sizeof(*l));l->header=(RvBufferHeader){1,sizeof(*l),0};
    return core_call(0,RV_LEASE,1,bytes,2,l,sizeof(*l),0,&r);
}
static void release(uint32_t token)
{
    RvRequest q;RvReply r;pn_request(&n.port,&q,token);(void)pn_call(&n.port,RV_LEASE,2,&q,&r);
}
static int32_t install(void)
{
    RvLeaseInfo raw,work;PsStore *store=&n.store;PsInstallResult result;
    const PsObject object={PS_ENGINE,0,0};uint32_t fd=0,total=0,got=0;
    int32_t status,c;
    pn_zero(&raw,sizeof(raw));pn_zero(&work,sizeof(work));
    status=lease(65536,&raw);if(status!=RV_OK)return status;
    status=lease(65536,&work);if(status!=RV_OK){release(raw.token);return status;}
    ps_init(store,&n.port,eng_wire_pointer(work.base),work.length,verify,0);
    status=ps_fixed_begin(store,&object,0);
    if(status==RV_OK)status=ps_fixed_open(store,&object,PS_CARD,0,0,0,&fd);
    while(status==RV_OK&&total<raw.length) {
        status=ps_fixed_transfer(store,4,fd,(uint8_t *)eng_wire_pointer(raw.base)+total,raw.length-total,&got);
        if(status==RV_EOF){status=RV_OK;break;}
        if(status!=RV_OK||!got)break;
        total+=got;
    }
    if(fd){c=ps_fixed_close(store,fd);if(c!=RV_OK)status=c;}
    status=ps_fixed_end(store,status);
    if(status==RV_OK) {
        RvSession *s=RV_PTR(n.context->session_address);
        if(total!=n.gate.length||gxr2_crc32(eng_wire_pointer(raw.base),total)!=s->crc)status=RV_STALE;
        else status=ps_install(store,eng_wire_pointer(raw.base),total,&result);
    }
    release(work.token);release(raw.token);
    ps_init(store,&n.port,n.tweak_work,sizeof(n.tweak_work),verify,0);return status;
}
static int32_t list_bind(void)
{
    const EngList *list=eng_list();RvRequest q;RvReply r;RvUiText t;unsigned i,count;
    for(i=0;i<16;i++) {
        const char *text=list->row[i].ascii;
        for(count=0;count<32&&text[count];count++){}
        pn_zero(&t,sizeof(t));t.header=(RvBufferHeader){1,sizeof(t),0};
        t.source_address=eng_wire_address(text);t.source_bytes=count;t.source_lease=n.port.ui_lease;
        t.glyph_address=eng_wire_address(n.glyph[i]);t.glyph_capacity=sizeof(n.glyph[i]);t.glyph_lease=n.port.ui_lease;
        pn_request(&n.port,&q,n.port.ui_lease);
        if(pn_call(&n.port,RV_UI_TEXT,2,&q,&r)!=RV_OK)return RV_IO;
        t.language=r.detail;
        pn_copy(n.scratch.bytes,&t,sizeof(t));q.args[10]=eng_wire_address(n.scratch.bytes);q.args[11]=sizeof(t);
        if(pn_call(&n.port,RV_UI_TEXT,1,&q,&r)!=RV_OK)return RV_IO;
        n.refs[i]=eng_wire_address(n.glyph[i]);n.labels[i]=eng_wire_address(&n.refs[i]);
    }
    n.state[0]=5;n.list.header=(RvBufferHeader){1,sizeof(n.list),0};n.list.view_token=n.view;
    n.list.state_address=eng_wire_address(n.state);n.list.state_bytes=sizeof(n.state);
    n.list.rows=16;n.list.cursor=list->cursor-1;n.list.label_table=eng_wire_address(n.labels);
    n.list.details=eng_wire_address(n.details);n.list.lease_token=n.port.ui_lease;
    pn_request(&n.port,&q,n.port.ui_lease);q.args[9]=q.args[12]=16;
    q.args[10]=eng_wire_address(&n.list);q.args[11]=sizeof(n.list);
    if(pn_call(&n.port,RV_UI_LIST,1,&q,&r)!=RV_OK)return RV_IO;
    n.view=r.token;return RV_OK;
}
static int bind_gxts(int restore)
{
    EngRecipeRef ref;EngTweak tweak;uint8_t indices[6];unsigned i;
    if(eng_current(&ref,&tweak)!=ENG_OK)return RV_STALE;
    for(i=0;i<6;i++){int index=eng_parameter_index(i+1);if(index<0)return RV_VERIFY;indices[i]=(uint8_t)index;}
    if(pn_gxts_bind(&n.gxts,&n.store,&n.semantic,&ref,indices)!=RV_OK)return RV_VERIFY;
    if(restore) {
        int32_t result=pn_gxts_load(&n.gxts,&tweak);if(result!=RV_OK)return result;
        if(eng_apply(&ref,&tweak)!=ENG_OK)return RV_FAULTED;
    }
    return RV_OK;
}
int32_t ig_init(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    const uint8_t *p;EngPort port;EngStatus status;Gxr2Unit unit;
    if(!ingress(a,c,q,r))return RV_FAULT;
    if(n.initialized) {
        status=eng_rebind();return finish(r,status);
    }
    p=eng_wire_pointer(n.context->image_address);pn_zero(&n.gate,sizeof(n.gate));
    n.gate.bytes=p;n.gate.length=n.context->image_bytes;
    {
        RvSession *s=RV_PTR(n.context->session_address);pn_copy(&unit,&s->unit,sizeof(unit));
    }
    trust_init();
    if(gxr2_gate_relocated_validate(p,n.context->image_bytes,&n.trust,&unit,
                                   n.context->image_address,&n.gate)!=GXR2_OK)return finish(r,ENG_REJECTED);
    if(gxr2_semantic_validate(&n.gate,&n.trust,&n.semantic)!=GXR2_OK)return finish(r,ENG_REJECTED);
    pn_zero(&port,sizeof(port));port.call=core_call;port.gated=&n.gate;
    /* Grain has no leased 32-byte publication in the frozen resident context. */
    status=eng_init(p,n.gate.length,&port);
    if(status!=ENG_OK)return finish(r,status);
    {
        RvReply reply;
        if(core_call(0,RV_EPOCHS,RV_IROM_E,0,0,0,0,0,&reply)!=RV_OK)return finish(r,ENG_STALE);
        n.irom_epoch=reply.epoch;
    }
    n.initialized=1;n.install_status=RV_UNAVAILABLE;
    ps_init(&n.store,&n.port,n.tweak_work,sizeof(n.tweak_work),verify,0);
    r->capabilities=CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W;
    return finish(r,ENG_OK);
}
int32_t ig_menu(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;RvSession *s;RvReply observed;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    s=RV_PTR(n.context->session_address);
    if(core_call(0,RV_EPOCHS,RV_IROM_E,0,0,0,0,0,&observed)!=RV_OK)return finish(r,ENG_STALE);
    if(observed.epoch!=n.irom_epoch) {
        RvRoot *root=RV_PTR(n.context->root_address);
        status=eng_restore_stock();eng_menu_close();
        (void)core_call(0,RV_UI_LIST,4,n.view,0,0,0,0,&observed);
        eng_invalidate();root->grain=0;root->flags|=RF_STOP;root->state=RV_FENCED;
        r->status=status==ENG_OK?RV_STALE:RV_UNCERTAIN;n.active=0;return RV_FAULT;
    }
    if(s->selected_source==RV_SOURCE_CARD&&!n.install_attempted) {
        n.install_attempted=1;n.install_status=install();
        if(n.install_status==RV_STALE||n.install_status==RV_UNCERTAIN)return finish(r,ENG_STALE);
    }
    status=eng_menu_open();if(status==ENG_OK&&list_bind()!=RV_OK)status=ENG_IO;
    return finish(r,status);
}
int32_t ig_apply(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;uint32_t slot;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    slot=q->args[8]+1;status=slot<=16?eng_select((uint8_t)slot):ENG_REJECTED;
    if(status==ENG_OK&&bind_gxts(1)!=RV_OK)status=ENG_IO;
    if(status==ENG_OK&&list_bind()!=RV_OK)status=ENG_IO;
    return finish(r,status);
}
int32_t ig_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    /* H07's native keep-open argument is transport, not a recipe number. */
    if(q->args[8]==7){n.active=0;r->status=RV_OK;return RV_CONSUMED;}
    if(q->args[8]==0x23||q->args[8]==0x29) {
        EngStatus status=eng_restore_stock();eng_menu_close();
        if(status==ENG_OK){RvReply reply;(void)core_call(0,RV_UI_LIST,4,n.view,0,0,0,0,&reply);}
        return finish(r,status);
    }
    n.active=0;r->status=RV_OK;return RV_PASS;
}
int32_t ig_panel_open(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    PnPanelOps ops;PnOpenView view;uint32_t array,count,top;int32_t result;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    if(n.panel.open){result=RV_CONSUMED;goto done;}
    if(n.panel.ui_pinned||n.panel.unknown||n.panel.commit_uncertain)return finish(r,ENG_REJECTED);
    if(bind_gxts(0)!=RV_OK||ig_native_seed(n.context)!=RV_OK)return finish(r,ENG_REJECTED);
    n.seed=(PnNativeSeed){eng_wire_pointer(n.context->ui_state_address),
        eng_wire_pointer(n.context->ui_state_address+32),eng_wire_pointer(n.context->ui_state_address+104),32,72,108};
    pn_zero(&ops,sizeof(ops));ops.build=pn_native_from_seed;ops.build_context=&n.seed;
    ops.save=pn_gxts_save;ops.save_context=&n.gxts;ops.param_index=n.gxts.param_index;
    pn_panel_init(&n.panel,&n.port,&ops);
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);top=count&&count<=2?array+8*(count-1):0;
    view=(PnOpenView){RV_WORD(0x205d9c00),RV_WORD(0x205d9bf8),array,count,
        top?RV_BYTE(top):0,top?RV_WORD(top+4):0,q->args[8]};
    result=pn_panel_open(&n.panel,&view);
done:
    n.active=0;r->status=result==RV_FAULT?RV_IO:RV_OK;return result;
}
int32_t ig_panel_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    int32_t result;uint32_t event,phase;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    event=q->args[8];phase=q->args[9];
    /* The frozen ingress forwards input words unchanged. Accept only the
     * explicit PRESS/RELEASE/REPEAT encoding here until P8 proves native flags. */
    if(phase>PN_REPEAT)return finish(r,ENG_REJECTED);
    result=pn_panel_event(&n.panel,event,(PnKeyPhase)phase);
    if(!n.panel.open&&result==RV_CONSUMED&&list_bind()!=RV_OK)result=RV_FAULT;
    n.active=0;r->status=result==RV_FAULT?RV_FAULTED:RV_OK;return result;
}
int32_t ig_panel_abort(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    int32_t result;if(!ingress(a,c,q,r))return RV_FAULT;
    result=pn_panel_notify(&n.panel,PN_STORAGE_INVALIDATED,q->args[9]!=0);
    n.active=0;r->status=result==RV_FAULT?RV_STALE:RV_OK;return result;
}
int32_t ig_stop(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;if(!ingress(a,c,q,r))return RV_FAULT;
    if(n.panel.open&&pn_panel_cancel(&n.panel)==RV_FAULT)return finish(r,ENG_UNCERTAIN);
    status=eng_restore_stock();eng_menu_close();return finish(r,status);
}
#ifndef ENG_HOST
extern uint8_t __image_base[] __attribute__((visibility("hidden")));
static uint32_t offset(RvEngineEntry p){return (uint32_t)((uintptr_t)p-(uintptr_t)__image_base);}
#define OFF(name) offset(name)
#else
#include "local/entries.h"
#define OFF(name) OFF_##name
#define OFF_ig_init OFF_IG_INIT
#define OFF_ig_menu OFF_IG_MENU
#define OFF_ig_event OFF_IG_EVENT
#define OFF_ig_panel_open OFF_IG_PANEL_OPEN
#define OFF_ig_panel_event OFF_IG_PANEL_EVENT
#define OFF_ig_panel_abort OFF_IG_PANEL_ABORT
#define OFF_ig_apply OFF_IG_APPLY
#define OFF_ig_stop OFF_IG_STOP
void ig_host_reset(void){pn_zero(&n,sizeof(n));eng_host_reset();}
const PnPanel *ig_host_panel(void){return &n.panel;}
int32_t ig_host_install_status(void){return n.install_status;}
void ig_host_region(void **p,uint32_t *bytes){*p=&n;*bytes=sizeof(n);}
#endif
int32_t ig_bootstrap(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    RvEngineEntries *e;if(!ingress(a,c,q,r))return RV_FAULT;
    e=eng_wire_pointer(n.context->entries_address);pn_zero(e,sizeof(*e));e->version=1;e->bytes=40;
    e->init=OFF(ig_init);e->menu_open=OFF(ig_menu);e->event=OFF(ig_event);
    e->panel_open=OFF(ig_panel_open);e->panel_event=OFF(ig_panel_event);e->panel_abort=OFF(ig_panel_abort);
    e->apply_step=OFF(ig_apply);e->shutdown=e->abort=OFF(ig_stop);
    r->actual=40;r->status=RV_OK;n.active=0;return RV_CONSUMED;
}
