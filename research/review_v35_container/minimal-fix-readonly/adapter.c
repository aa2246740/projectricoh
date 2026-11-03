#include "integrated.h"
#include "blackbox.h"
#include "src/firmware/engine/core/eng_core.h"
#include "src/firmware/card_container_v2/internal.h"
#ifndef ENG_HOST
const char ig_engine_version[] __attribute__((used,section(".engine_version")))="v3.4c";
#else
const char ig_engine_version[]="v3.4c";
#endif
typedef struct { PnGxts tweak; uint8_t bytes[256]; PsStore preference; } SessionWork;
typedef struct {
    const RvApi *api;
    RvPrivateContext *context;
    RvRequest request;
    Gxr2View gate;
    Gxr2Trust trust;
    PnPort port;
    PnPanel panel;
    EngTweak values[16];
    uint8_t tweaks_loaded, tweak_io_error[16], param_index[6];
    int8_t lo[4],hi[4];
    PsStore store;
    uint32_t rpc, view;
    uint8_t initialized, active, install_attempted, stopped, release_failed, workspace_released;
    uint8_t gxts_read_error;
    uint8_t last_slot, last_attempted, quarantined, safe_entry, flush_reason;
    uint32_t last_generation;
    int32_t last_store;
    RvLeaseInfo workspace;
    int32_t install_status;
    union { uint32_t align; uint8_t bytes[80]; } scratch;
    uint8_t glyph[16][70];
    uint32_t labels[16],refs[16],details[16][3];
    RvUiList list;
    PnNativeSeed seed;
} Integrated;
static Integrated n;
static int32_t workspace_close(void);
static int32_t last_verify(const PsObject *,const uint8_t *,uint32_t,PsInfo *);
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
    if(!services||c->nonce!=context||(n.context&&c!=n.context)||n.active||n.stopped)return 0;
    n.context=c;n.api=services;n.request=*q;n.active=1;
    n.port.api=services;n.port.context=context;n.port.io_lease=n.port.ui_lease=c->state_lease;
    n.port.address=address;
    for(i=0;i<6;i++)n.port.epochs[i]=q->args[2+i];
    return 1;
}
static int32_t finish(RvReply *r,EngStatus status)
{
    static const int32_t map[]={RV_OK,RV_CONFLICT,RV_UNCERTAIN,RV_STALE,RV_IO,RV_FAULTED};
    if(status!=ENG_OK) {
        ig_bx_event(5,eng_stage(),status,0,0,map[status]);
        if(workspace_close()!=RV_OK)status=ENG_FAULT;
        n.stopped=1;
    }
    if(n.safe_entry&&(status!=ENG_OK||n.flush_reason))ig_bx_flush(status!=ENG_OK?3:n.flush_reason);
    n.safe_entry=n.flush_reason=0;
    n.active=0;r->status=map[status];r->detail=eng_stage();
    return status==ENG_OK?RV_CONSUMED:(status==ENG_UNCERTAIN||status==ENG_FAULT?RV_FAULT:RV_CLOSE_AND_PASS);
}
static int32_t core_call(void *unused,uint32_t id,uint32_t op,uint32_t a,uint32_t b,
                         void *buffer,uint32_t bytes,uint32_t count,RvReply *r)
{
    static RvRequest q;q=n.request;int32_t result;(void)unused;
    if(bytes>sizeof(n.scratch.bytes))return RV_RANGE;
    q.args[8]=a;q.args[9]=b;q.args[10]=bytes?eng_wire_address(n.scratch.bytes):0;
    q.args[11]=bytes;q.args[12]=count;q.args[13]=0;
    if(bytes)pn_copy(n.scratch.bytes,buffer,bytes);
    if(id==RV_RPC8&&op!=1)q.args[1]=n.rpc;
    if(id==RV_SETTINGS&&op==3)q.args[8]=0;
    result=n.api->call(id,op,&q,r);
    if(id==RV_RPC8||id==RV_LEASE)ig_bx_event(id==RV_RPC8?8:9,op,a,r->token,r->detail,r->native_result);
    if(result==RV_OK&&r->status==RV_OK&&r->version==1&&r->bytes==32) {
        if(id==RV_RPC8&&op==1)n.rpc=r->token;
        if(id==RV_RPC8&&op==5)n.rpc=0;
        if(bytes)pn_copy(buffer,n.scratch.bytes,bytes);
    }
    return result;
}
static void grain_snapshot(void *unused,uint32_t mode,uint32_t enabled)
{(void)unused;es_grain_commit(RV_PTR(n.context->root_address),mode,enabled);}
static int32_t verify(void *unused,const PsObject *o,const uint8_t *p,uint32_t bytes,PsInfo *info)
{
    static Gxr2View v;Gxr2Unit *u=&n.trust.modules[n.gate.selected_module].unit;(void)unused;
    if(o->kind==PS_LAST)return last_verify(o,p,bytes,info);
    if(o->kind!=PS_ENGINE||gxr2_validate(p,bytes,&n.trust,u,0,&v)!=GXR2_OK)return RV_VERIFY;
    info->generation=v.build_number;info->bytes=bytes;info->crc32=gxr2_crc32(p,bytes);return RV_OK;
}
static int32_t lease(uint32_t bytes,uint32_t usage,RvLeaseInfo *l)
{
    static RvReply r;pn_zero(l,sizeof(*l));l->header=(RvBufferHeader){1,sizeof(*l),0};
    return core_call(0,RV_LEASE,1,bytes,usage,l,sizeof(*l),0,&r);
}
static int32_t release(RvLeaseInfo *l)
{
    static RvRequest q;static RvReply r;int32_t status;
    if(!l->token)return RV_OK;
    pn_request(&n.port,&q,l->token);status=pn_call(&n.port,RV_LEASE,2,&q,&r);
    if(status==RV_OK)pn_zero(l,sizeof(*l));else n.release_failed=1;
    return status;
}
static int32_t workspace_close(void)
{
    if(!n.workspace.token)return RV_OK;
    if(n.workspace_released)return RV_FAULTED;
    n.workspace_released=1;
    return release(&n.workspace);
}
static int32_t workspace_open(void)
{
    int32_t status;SessionWork *w;
    if(n.release_failed||n.workspace_released)return RV_FAULTED;
    if(n.workspace.token)return RV_OK;
    status=lease(sizeof(SessionWork),4,&n.workspace);
    if(status!=RV_OK)return status;
    w=eng_wire_pointer(n.workspace.base);pn_zero(w,sizeof(*w));
    ps_init(&n.store,&n.port,w->bytes,sizeof(w->bytes),verify,0);
    return RV_OK;
}
static int32_t ui_finish(RvReply *r,int32_t result)
{
    if(result==RV_FAULT) {
        if(workspace_close()!=RV_OK)r->detail=RV_FAULTED;
        n.stopped=1;
    }
    if(n.safe_entry&&(result==RV_FAULT||n.flush_reason))ig_bx_flush(result==RV_FAULT?3:n.flush_reason);
    n.safe_entry=n.flush_reason=0;
    n.active=0;r->status=result==RV_FAULT?RV_FAULTED:RV_OK;return result;
}
static int32_t install(void)
{
    static RvLeaseInfo raw,work;PsStore *store=&n.store;PsInstallResult result;
    const PsObject object={PS_ENGINE,0,0};uint32_t fd=0,total=0,got=0;
    int32_t status,c;
    pn_zero(&raw,sizeof(raw));pn_zero(&work,sizeof(work));
    if(n.release_failed)return RV_FAULTED;
    status=lease(73728,2,&raw);if(status!=RV_OK)return status;
    status=lease(73728,2,&work);if(status!=RV_OK) {
        if(release(&raw)!=RV_OK)return RV_FAULTED;
        return status;
    }
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
    c=release(&work);if(release(&raw)!=RV_OK)c=RV_FAULTED;
    if(c!=RV_OK)return RV_FAULTED;
    return status;
}
static int32_t list_bind(void)
{
    const EngList *list=eng_list();static RvRequest q;static RvReply r;RvUiText t;unsigned i,count;
    ig_bx_receipt(0,0,15);
    ig_bx_seed();
    if(rv_native_seed(n.context)!=RV_OK)return RV_UNAVAILABLE;
    for(i=0;i<list->rows;i++) {
        const char *text=list->row[i].ascii;
        for(count=0;count<32&&text[count];count++){}
        pn_zero(&t,sizeof(t));t.header=(RvBufferHeader){1,sizeof(t),0};
        t.source_address=eng_wire_address(text);t.source_bytes=count;t.source_lease=n.port.ui_lease;
        t.glyph_address=eng_wire_address(n.glyph[i]);t.glyph_capacity=sizeof(n.glyph[i]);t.glyph_lease=n.port.ui_lease;
        pn_request(&n.port,&q,n.port.ui_lease);
        ig_bx_event(3,16,i,0,0,0);
        if(pn_call(&n.port,RV_UI_TEXT,2,&q,&r)!=RV_OK)return RV_IO;
        t.language=r.detail;
        pn_copy(n.scratch.bytes,&t,sizeof(t));q.args[10]=eng_wire_address(n.scratch.bytes);q.args[11]=sizeof(t);
        ig_bx_event(3,17,i,0,0,0);
        if(pn_call(&n.port,RV_UI_TEXT,1,&q,&r)!=RV_OK)return RV_IO;
        n.refs[i]=eng_wire_address(n.glyph[i]);n.labels[i]=eng_wire_address(&n.refs[i]);
    }
    n.list.header=(RvBufferHeader){1,sizeof(n.list),0};n.list.view_token=n.view;
    n.list.state_address=n.context->ui_state_address;n.list.state_bytes=n.context->ui_state_bytes;
    n.list.rows=list->rows;n.list.cursor=list->cursor-1;n.list.label_table=eng_wire_address(n.labels);
    n.list.details=eng_wire_address(n.details);n.list.lease_token=n.port.ui_lease;
    RV_WORD(n.list.state_address+4)=n.list.state_address+32;
    RV_WORD(n.list.state_address+32+5*12)=n.list.label_table;
    RV_BYTE(n.list.state_address+32+5*12+4)=list->rows;
    RV_WORD(n.list.state_address+32+5*12+8)=0;
    pn_request(&n.port,&q,n.port.ui_lease);q.args[9]=q.args[12]=list->rows;
    q.args[10]=eng_wire_address(&n.list);q.args[11]=sizeof(n.list);
    ig_bx_receipt(0,0,26);
    if(pn_call(&n.port,RV_UI_LIST,1,&q,&r)!=RV_OK){ig_bx_receipt(0,RV_IO,26);return RV_IO;}
    ig_bx_receipt(0,1,26);
    n.view=r.token;return RV_OK;
}
static int preload_gxts(void)
{
    static EngRecipeRef ref;PnGxts *tweak;
    unsigned i,slot;const uint8_t *dir,*records;int32_t status=RV_OK;
    const Gxr2View *semantic=eng_validated_view();
    if(n.tweaks_loaded)return RV_OK;
    ref.unit=n.gate.selected_module;
    dir=semantic->bytes+semantic->sections[2].offset+64*ref.unit;
    records=semantic->bytes+((uint32_t)dir[16]<<24|(uint32_t)dir[17]<<16|(uint32_t)dir[18]<<8|dir[19])+32;
    for(i=0;i<6;++i){int index=eng_parameter_index(i+1);if(index<0)return RV_VERIFY;n.param_index[i]=(uint8_t)index;}
    tweak=&((SessionWork *)eng_wire_pointer(n.workspace.base))->tweak;
    for(slot=1;slot<=eng_visible_rows();++slot) {
        ref.slot=(uint8_t)slot;eng_identity(records+64*(slot-1),ref.identity);
        status=pn_gxts_bind(tweak,&n.store,semantic,&ref,n.param_index);
        if(status==RV_OK)status=pn_gxts_load(tweak,&n.values[slot-1]);
        n.gxts_read_error|=tweak->read_error;
        if(status!=RV_OK)break;
        n.tweak_io_error[slot-1]=tweak->selection.io_error_mask;
    }
    if(status==RV_OK)n.tweaks_loaded=1;
    return status;
}
enum { LAST_BYTES=192 };
static uint32_t last_u32(const uint8_t *p)
{return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static void last_p32(uint8_t *p,uint32_t value)
{p[0]=value>>24;p[1]=value>>16;p[2]=value>>8;p[3]=value;}
static int32_t last_binding(unsigned slot,PnGxts **out)
{
    const Gxr2View *v=eng_validated_view();const uint8_t *d,*record;
    EngRecipeRef ref;PnGxts *tweak;
    if(!slot || slot>eng_visible_rows())return RV_VERIFY;
    d=v->bytes+v->sections[2].offset+64*v->selected_module;
    record=v->bytes+last_u32(d+16)+32+64*(slot-1);
    ref.unit=v->selected_module;ref.slot=(uint8_t)slot;eng_identity(record,ref.identity);
    tweak=&((SessionWork *)eng_wire_pointer(n.workspace.base))->tweak;
    if(pn_gxts_bind(tweak,&n.store,v,&ref,n.param_index)!=RV_OK)return RV_VERIFY;
    *out=tweak;return RV_OK;
}
static int32_t last_verify(const PsObject *o,const uint8_t *raw,uint32_t bytes,PsInfo *info)
{
    PnGxts *tweak;unsigned i;
    if(bytes!=LAST_BYTES || !pn_equal(raw,"GXLS",4) || raw[4] || raw[5]!=1 ||
       raw[6] || raw[7]!=LAST_BYTES || !last_u32(raw+8) ||
       raw[17]!=n.gate.selected_module || o->unit!=raw[17]+1 || o->slot ||
       last_u32(raw+12)!=gxr2_crc_zeroed(raw,bytes,12,4))return RV_VERIFY;
    for(i=18;i<24;++i)if(raw[i])return RV_VERIFY;
    for(i=184;i<LAST_BYTES;++i)if(raw[i])return RV_VERIFY;
    if(last_binding(raw[16],&tweak)!=RV_OK || !pn_equal(raw+24,tweak->binding.identity,160))return RV_VERIFY;
    info->generation=last_u32(raw+8);info->bytes=bytes;info->crc32=gxr2_crc32(raw,bytes);return RV_OK;
}
static int32_t last_read(uint8_t raw[LAST_BYTES])
{
    uint32_t bytes=0;PsCandidate chosen;PsStore *store;int32_t status;
    PsObject o={PS_LAST,(uint8_t)(n.gate.selected_module+1),0};SessionWork *w;
    w=eng_wire_pointer(n.workspace.base);store=&w->preference;
    ps_init(store,&n.port,w->bytes,sizeof(w->bytes),verify,0);
    status=ps_load(store,&o,raw,LAST_BYTES,&bytes,&chosen);
    if(status==RV_OK) {n.last_slot=raw[16];n.last_generation=chosen.info.generation;}
    else if(status==RV_UNAVAILABLE) {n.last_slot=0;n.last_generation=0;}
    return status;
}
static EngStatus remember_load(void *unused,uint8_t *slot,EngTweak *t)
{
    uint8_t raw[LAST_BYTES];(void)unused;
    if(n.gxts_read_error)return ENG_REJECTED;
    /* Preference read failures never poison the tweak store or stop the menu. */
    if(last_read(raw)!=RV_OK)return ENG_REJECTED;
    *slot=n.last_slot;*t=n.values[*slot-1];return ENG_OK;
}
static int rejected_card_present(void)
{
    RvRoot *root=RV_PTR(n.context->root_address);
    if(root->flags&RF_QUARANTINE)n.quarantined=1;
    if(n.install_status==RV_CONFLICT)n.quarantined=1;
    if(n.quarantined)root->flags|=RF_QUARANTINE;
    return n.quarantined;

}
static void remember_save(unsigned slot)
{
    uint8_t raw[LAST_BYTES];PnGxts *tweak;PsInfo info;PsStore *store;SessionWork *w;
    PsObject o={PS_LAST,(uint8_t)(n.gate.selected_module+1),0};
    /* A recipe commit succeeds before this preference write. An older card
     * session must remain read-only while browsing over a newer IROM copy. */
    if(n.gxts_read_error || n.install_status==RV_CONFLICT)return;
    /* A failed final readback may have committed the new generation. Recover
     * from verified A/B evidence before constructing the next generation. */
    if(n.last_store!=RV_OK) {
        n.last_store=last_read(raw);
        if(n.last_store!=RV_OK&&n.last_store!=RV_UNAVAILABLE)return;
        n.last_store=RV_OK;
    }
    if(slot==n.last_slot)return;
    /* Positive card rejection remains sticky until the next cold boot. */
    if(rejected_card_present())return;
    if(n.last_generation==UINT32_MAX || last_binding(slot,&tweak)!=RV_OK) {n.last_store=RV_VERIFY;return;}
    pn_zero(raw,sizeof(raw));pn_copy(raw,"GXLS",4);raw[5]=1;raw[7]=LAST_BYTES;
    last_p32(raw+8,n.last_generation+1);raw[16]=(uint8_t)slot;raw[17]=n.gate.selected_module;
    pn_copy(raw+24,tweak->binding.identity,160);last_p32(raw+12,gxr2_crc_zeroed(raw,sizeof(raw),12,4));
    if(last_verify(&o,raw,sizeof(raw),&info)!=RV_OK) {n.last_store=RV_VERIFY;return;}
    w=eng_wire_pointer(n.workspace.base);store=&w->preference;ps_init(store,&n.port,w->bytes,sizeof(w->bytes),verify,0);
    n.last_store=ps_save_record(store,&o,raw,sizeof(raw));
    if(n.last_store==RV_OK) {n.last_slot=(uint8_t)slot;n.last_generation=info.generation;}
}
static EngStatus select_cached(unsigned slot)
{
    if(!n.tweaks_loaded||slot<1||slot>eng_visible_rows())return ENG_REJECTED;
    return eng_select_saved((uint8_t)slot,&n.values[slot-1]);
}
static void remember_close(void)
{
    EngRecipeRef recipe;EngTweak values;
    if(n.last_attempted)return;
    n.last_attempted=1;
    if(eng_current(&recipe,&values)==ENG_OK)remember_save(recipe.slot);
}
static int32_t a4_finish(PnPanel *p,int save)
{
    int32_t status;
    if(!p->open)return RV_PASS;
    if(eng_uncertain())return RV_FAULT;
    if(save) {
        if(eng_apply(&p->recipe,&p->draft)!=ENG_OK)return RV_FAULT;
        PnGxts *tweak=&((SessionWork *)eng_wire_pointer(n.workspace.base))->tweak;
        status=n.gxts_read_error?RV_IO:
            (n.install_status==RV_CONFLICT||rejected_card_present()?RV_CONFLICT:RV_OK);
        if(status==RV_OK) {
            status=pn_gxts_bind(tweak,&n.store,eng_validated_view(),&p->recipe,n.param_index);
            if(status==RV_OK) {
                tweak->loaded=1;tweak->selection.io_error_mask=n.tweak_io_error[p->recipe.slot-1];
                status=pn_gxts_save(tweak,&p->recipe,&p->draft);
            }
            n.gxts_read_error|=tweak->read_error;
        }
        p->last_store=status;
        if(status!=RV_OK) {
            /* Storage uncertainty is distinct from native apply uncertainty.
             * Restore first, including the uncertain rename/close paths. */
            if(eng_apply(&p->recipe,&p->committed)!=ENG_OK)return RV_FAULT;
            p->draft=p->committed;p->dirty=0;p->open=0;p->input_enabled=0;
            eng_menu_close();return status==RV_UNCERTAIN?RV_FAULT:RV_CLOSE_AND_PASS;
        }
        n.values[p->recipe.slot-1]=p->draft;n.tweak_io_error[p->recipe.slot-1]=0;
        p->committed=p->draft;p->dirty=0;
    }
    p->open=0;p->input_enabled=0;eng_menu_close();return RV_CLOSE_AND_PASS;
}
static int32_t a4_open(void)
{
    PnPanel *p=&n.panel;uint32_t array,count,top;int index;
    if(p->open) {
        p->parameter=(p->parameter+1)&3;index=p->param_index[p->parameter];
        p->cursor=(uint8_t)(p->draft.v[index]+5);
        return pn_ui_render(p,0)==RV_OK?RV_CONSUMED:RV_FAULT;
    }
    pn_zero(p,sizeof(*p));p->port=&n.port;p->ops.build=pn_native_from_seed;
    if(n.gxts_read_error)p->last_store=RV_IO;
    if(eng_current(&p->recipe,&p->committed)!=ENG_OK)return RV_FAULT;
    p->draft=p->committed;
    pn_copy(p->param_index,n.param_index,6);
    {
        unsigned i;int32_t lo,hi,def;
        for(i=0;i<4;++i) {
            if(gxr2_parameter(eng_validated_view(),p->recipe.unit,p->recipe.slot,i+1,&lo,&hi,&def)!=GXR2_OK)return RV_FAULT;
            n.lo[i]=(int8_t)lo;n.hi[i]=(int8_t)hi;
        }
    }
    n.seed=(PnNativeSeed){eng_wire_pointer(n.context->ui_state_address),
        eng_wire_pointer(n.context->ui_state_address+32),eng_wire_pointer(n.context->ui_state_address+104),32,72,132};
    p->ops.build_context=&n.seed;
    p->cursor=(uint8_t)(p->draft.v[p->param_index[0]]+5);
    if(p->cursor>=11)return RV_FAULT;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(!array||count<1||count>2)return RV_FAULT;
    top=array+8*(count-1);p->view.expected_array=array;p->view.expected_count=count;
    p->view.expected_top_tag=RV_BYTE(top);p->view.expected_top_state=RV_WORD(top+4);
    if(pn_ui_render(p,1)!=RV_OK)return RV_FAULT;
    p->open=p->input_enabled=1;return RV_CONSUMED;
}
static int32_t a4_move(unsigned row)
{
    PnPanel *p=&n.panel;EngTweak draft;unsigned index=p->param_index[p->parameter];
    if(!p->open||row>=11)return RV_FAULT;
    if((int)row-5<n.lo[p->parameter]||(int)row-5>n.hi[p->parameter]) {
        p->cursor=(uint8_t)(p->draft.v[index]+5);
        return pn_ui_render(p,0)==RV_OK?RV_CONSUMED:RV_FAULT;
    }
    draft=p->draft;draft.v[index]=(int8_t)((int)row-5);
    p->draft=draft;p->cursor=(uint8_t)row;p->preview_attempted=1;
    p->dirty=(uint8_t)!pn_equal(&p->draft,&p->committed,sizeof(draft));
    return pn_ui_render(p,0)==RV_OK?RV_CONSUMED:RV_FAULT;
}
int32_t ig_init(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    const uint8_t *p;static EngPort port;EngStatus status;Gxr2Unit unit;
    if(!ingress(a,c,q,r))return RV_FAULT;
    if(n.initialized){r->capabilities=CAP_UI|CAP_S|CAP_W;return finish(r,ENG_OK);}
    p=eng_wire_pointer(n.context->image_address);pn_zero(&n.gate,sizeof(n.gate));
    n.gate.bytes=p;n.gate.length=n.context->image_bytes;
    {
        RvSession *s=RV_PTR(n.context->session_address);pn_copy(&unit,&s->unit,sizeof(unit));
    }
    trust_init();
    if(gxr2_gate_relocated_validate(p,n.context->image_bytes,&n.trust,&unit,
                                   n.context->image_address,&n.gate)!=GXR2_OK){
        n.safe_entry=1;ig_bx_unit(1,RV_VERIFY);n.flush_reason=3;return finish(r,ENG_REJECTED);
    }
    ig_bx_unit(0,RV_OK);
    pn_zero(&port,sizeof(port));port.call=core_call;port.gated=&n.gate;port.commit_grain=grain_snapshot;port.remember_load=remember_load;
    status=eng_init(p,n.gate.length,&port);
    if(status!=ENG_OK)return finish(r,status);
    n.initialized=1;n.install_status=RV_UNAVAILABLE;
    r->capabilities=CAP_UI|CAP_S|CAP_W;
    return finish(r,ENG_OK);
}
int32_t ig_menu(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;RvSession *s;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    n.safe_entry=1;ig_bx_event(10,0,0,0,0,0);
    (void)rejected_card_present();
    s=RV_PTR(n.context->session_address);
    if(s->selected_source==RV_SOURCE_CARD&&!n.install_attempted) {
        n.install_attempted=1;n.install_status=install();
        if(n.install_status!=RV_OK&&n.install_status!=RV_UNAVAILABLE){n.quarantined=1;((RvRoot *)RV_PTR(n.context->root_address))->flags|=RF_QUARANTINE;}
        ig_bx_receipt(1,n.install_status,8);
        if(n.release_failed)return finish(r,ENG_FAULT);
        if(n.install_status==RV_STALE||n.install_status==RV_UNCERTAIN)return finish(r,ENG_STALE);
    }
    if(!eng_visible_rows()) {n.active=0;r->status=RV_OK;return RV_PASS;}
    ig_bx_event(10,9,0,0,0,0);
    if(workspace_open()!=RV_OK)return finish(r,ENG_IO);
    if(!eng_list()->opened)n.last_attempted=0;
    status=preload_gxts()==RV_OK?eng_menu_open():ENG_IO;
    if(status==ENG_OK&&list_bind()!=RV_OK)status=ENG_IO;
    return finish(r,status);
}
int32_t ig_apply(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;uint32_t slot;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    n.safe_entry=1;
    if(n.panel.open)return ui_finish(r,a4_move(q->args[8]));
    slot=q->args[8]+1;status=eng_cursor((uint8_t)slot);
    if(status==ENG_OK&&list_bind()!=RV_OK)status=ENG_IO;
    return finish(r,status);
}
int32_t ig_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    n.safe_entry=1;
    if(q->args[8]==7) {
        if(q->args[13]==0x23&&(q->args[12]==0x202c2d74||q->args[12]==0x202c2d84))n.flush_reason=2;
        /* Native keep=0 forces close after this call, for every result.
         * Finish the OK save or MENU/forced-exit rollback before returning. */
        int32_t result;
        if(n.panel.open)result=a4_finish(&n.panel,q->args[13]==0x23&&(q->args[12]==0x202c2d74||q->args[12]==0x202c2d84));
        else {
            if(q->args[13]==0x23&&(q->args[12]==0x202c2d74||q->args[12]==0x202c2d84)) {
                uint32_t tw=0,ww=0;unsigned slot=RV_BYTE(0x2022f726);
                EngStatus status=select_cached(slot);
                eng_apply_witness(&tw,&ww);
                ig_bx_apply(q->args[13],q->args[12],q->args[9],slot,status,tw,ww);
                if(status!=ENG_OK)return finish(r,status);
            }
            if(!q->args[9])eng_menu_close();
            result=q->args[9]?RV_CONSUMED:RV_CLOSE_AND_PASS;
        }
        if(result!=RV_FAULT&&!eng_list()->opened){remember_close();n.flush_reason=1;}
        return ui_finish(r,result);
    }
    n.active=0;r->status=RV_OK;return RV_PASS;
}
int32_t ig_panel_open(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    int32_t result;unsigned row;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    n.safe_entry=1;n.flush_reason=2;
    if(!n.panel.open) {
        row=RV_BYTE(0x2022f726);
        if(row<1||row>eng_visible_rows()||select_cached(row)!=ENG_OK){
            uint32_t tw=0,ww=0;eng_apply_witness(&tw,&ww);
            ig_bx_apply(0x25,q->args[12],0,row,ENG_REJECTED,tw,ww);
            return finish(r,ENG_REJECTED);
        }
    }
    result=a4_open();return ui_finish(r,result);
}
int32_t ig_panel_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    int32_t result;
    if(!ingress(a,c,q,r)||!n.initialized)return RV_FAULT;
    n.safe_entry=1;result=a4_move(q->args[8]);return ui_finish(r,result);
}
int32_t ig_panel_abort(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    int32_t result;if(!ingress(a,c,q,r))return RV_FAULT;
    result=a4_finish(&n.panel,0);return ui_finish(r,result);
}
int32_t ig_stop(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;if(!ingress(a,c,q,r))return RV_FAULT;
    if(n.panel.open&&a4_finish(&n.panel,0)==RV_FAULT)return finish(r,ENG_UNCERTAIN);
    status=ENG_OK;eng_menu_close();
    if(workspace_close()!=RV_OK)status=ENG_FAULT;
    n.stopped=1;return finish(r,status);
}
#ifndef ENG_HOST
extern uint8_t __image_base[] __attribute__((visibility("hidden")));
static uint32_t offset(RvEngineEntry p){return (uint32_t)((uintptr_t)p-(uintptr_t)__image_base);}
#define OFF(name) offset(name)
#else
#ifndef ACCEPTANCE_ENTRIES_HEADER
#define ACCEPTANCE_ENTRIES_HEADER "../../local/product/entries.h"
#endif
#include ACCEPTANCE_ENTRIES_HEADER
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
int32_t ig_host_last_store(void){return n.last_store;}
void ig_host_region(void **p,uint32_t *bytes){*p=&n;*bytes=sizeof(n);}
uint32_t ig_host_workspace_bytes(void){return sizeof(SessionWork);}
#endif
int32_t ig_bootstrap(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    RvEngineEntries *e;if(!ingress(a,c,q,r))return RV_FAULT;
    if(ig_control_off()){n.active=0;n.stopped=1;r->status=RV_FAULTED;r->detail=0x44495341;return RV_CLOSE_AND_PASS;}
    ig_bx_init(n.context);
    e=eng_wire_pointer(n.context->entries_address);pn_zero(e,sizeof(*e));e->version=1;e->bytes=40;
    e->init=OFF(ig_init);e->menu_open=OFF(ig_menu);e->event=OFF(ig_event);
    e->panel_open=OFF(ig_panel_open);e->panel_event=OFF(ig_panel_event);e->panel_abort=OFF(ig_panel_abort);
    e->apply_step=OFF(ig_apply);e->shutdown=e->abort=OFF(ig_stop);
    r->actual=40;r->status=RV_OK;n.active=0;return RV_CONSUMED;
}
