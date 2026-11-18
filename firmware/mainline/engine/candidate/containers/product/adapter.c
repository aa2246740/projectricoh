#include "integrated.h"
#include "diagnostic.h"
#ifndef G175_BOOT
#define G175_BOOT 0
#endif
#include "ui_v2_data.h"
#include "fx_pool.h"
#include "fx_store.h"
#include "fx_image.h"
#ifdef HF1
#include "hf1.h"
#endif
#include "src/firmware/engine/core/eng_core.h"
#include "src/firmware/card_container_v2/internal.h"
#ifndef ENG_HOST
const char ig_engine_version[] __attribute__((used,section(".engine_version")))="g187";
#else
const char ig_engine_version[]="g187";
#endif
typedef struct { PnGxts tweak; uint8_t bytes[256]; PsStore preference; } SessionWork;
enum { UV_L1,UV_CARD,UV_ITEMS,UV_VALUE,UV_DIAG=5,UV_ERR=6 };
typedef struct {
    UvLevels levels,saved[UV_USERS];
    KvUiNav nav;KvUiFrame frame;
    char text[UV_PHYSICAL][KV_UI_TEXT];
    uint8_t screen,physical,slot,param,group,armed;uint16_t cur,top,count;
    uint8_t applied_user,origin,confirmed_user;uint16_t l1_cur,card_cur,item_cur,entry_cur,last_cur,effect,look_cur;
} UvState;
/* Buffers that only live inside one adapter call. */
/* preselect: the remembered recipe offered at the first H01 (P1-03 B). */
typedef struct { RvRequest call,list; RvReply list_reply; EngPort port; uint16_t preselect; } AdapterIo;
typedef struct {
    const RvApi *api;
    RvPrivateContext *context;
    RvRequest request;
    Gxr2View gate;
    Gxr2Trust trust;
    PnPort port;
    PnPanel panel;
    UvLevels values[8];
    uint8_t tweaks_loaded, tweak_io_error[16], param_index[6];
    int8_t lo[4],hi[4];
    /* store is unused in this profile; its bytes back AdapterIo. */
    union { PsStore store; AdapterIo io; } spare;
    uint32_t rpc, view;
    uint8_t initialized, active, install_attempted, stopped, release_failed, workspace_released;
    uint8_t gxts_read_error;
    uint8_t last_slot, last_attempted, quarantined, safe_entry, flush_reason;
    uint32_t last_generation;
    int32_t last_store;
    RvLeaseInfo workspace;
    int32_t install_status;
    union { uint32_t align; uint8_t bytes[80]; } scratch;
    uint8_t glyph[8][70];
    uint32_t labels[8],refs[8],details[8][3];
    RvUiList list;
    PnNativeSeed seed;
    uint8_t failed,watch_view,view_lost,comm_failed;
    uint8_t entry;uint32_t rpc_sequence;char failed_text[15];
    uint8_t retry,ui_failed;
    UvState ui;
} Integrated;
static Integrated n;
volatile uint32_t *eng_colour_guard(void)
{ return &((RvRoot *)RV_PTR(n.context->root_address))->reserved_lane; }
/* v3.9 body entries (gen 153). Kept apart from Integrated (fixed layout).
 * grain: 0x80|mode as v3.8 root->grain; only the UI lane writes it.
 * The image record is written only by the H40/H41 entry. */
typedef struct {
    uint32_t grain;
} BodyState;
static BodyState body;
static uint32_t boot_mode_epoch,boot_settings,boot_settings_bytes;
/* Build-time configuration (DAT only). Event codes as seen at H10 (r11).
 * fn_next/fn_prev: 0 = off. The physical Fn1/Fn2 codes are still unconfirmed
 * on the camera, so rotation ships off. ok_to_panel: OK press 0x23 on an
 * L1 recipe row of our own list becomes DISP 0x25 (H06, open its card).
 * image_follow: H40 answers DONE (no edits) on the two vetted outer callers
 * so that H41 runs; every other caller gets PASS. */
typedef struct { uint8_t ok_to_panel,fn_next,fn_prev,image_follow; } BodyConfig;
const BodyConfig ig_body_config={1,0,0,1};
_Static_assert(sizeof(AdapterIo)<=sizeof(PsStore),"adapter buffers fit the unused store");
#ifndef ENG_HOST
_Static_assert(KV_UI_TEXT==14,"effect line includes prefix and terminator");
#endif
static int keep_view(RvReply *r);
static void cache_home(void);
static int view_owned(void)
{
    const RvUiList *u=(n.panel.open||n.watch_view==2)?&n.panel.list:&n.list;
    return rv_view_owned(RV_PTR(n.context->root_address),u,0);
}
int eng_settings_owned(void)
{
    const RvUiList *u=(n.panel.open||n.watch_view==2)?&n.panel.list:&n.list;
    if(n.entry==51)return rv_settings_owned(RV_PTR(n.context->root_address),n.request.args[6]);
    return rv_view_owned(RV_PTR(n.context->root_address),u,n.entry==1);
}
static int start_view(void)
{
    n.watch_view=n.panel.open?2:1;n.view_lost=n.comm_failed=0;eng_view_lost(0);
    return view_owned();
}
static int32_t release_view(RvReply *r)
{
    /* Returning PASS would make the unchanged resident restore/hide the
     * other_menu list. Consume this entry's stock Image continuation. Later
     * native events proceed normally, with no engine-owned UI writes. */
    RvRoot *root=RV_PTR(n.context->root_address);
    if(!n.failed&&root->ui_restore[6]&&RV_WORD(0x2022f5a8)==root->ui_restore[6]&&
       RV_WORD(0x205d9bf8)==8&&RV_WORD(0x205d9c00)==56) {
        cache_home();(void)es_ui_abort(root);
    }
    if(n.entry==7&&!n.request.args[9])cache_home();
    eng_view_lost(0);eng_menu_close();n.panel.open=n.panel.input_enabled=0;
    n.watch_view=0;n.active=0;n.safe_entry=n.flush_reason=0;
    r->status=RV_OK;r->detail=eng_stage();return RV_CONSUMED;
}
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
static void hf_suspend_all(void)
{
    fx_mask_suspend();
#ifdef HF1
    hf1_suspend();
#endif
}
static int ingress(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *r)
{
    RvPrivateContext *c;const RvApi *services;unsigned i;
    if(!q||!r||api||q->version!=1||q->bytes!=64||q->flags||q->args[0]!=context||
       q->args[11]!=sizeof(RvPrivateContext)||!q->args[10]){if(!n.active)hf_suspend_all();return 0;}
    pn_zero(r,sizeof(*r));r->version=1;r->bytes=32;r->status=RV_ARGUMENT;
    c=eng_wire_pointer(q->args[10]);services=rv_services_init(c);
    if(!services||c->nonce!=context||(n.context&&c!=n.context)||n.active||n.stopped){
        if(!n.active)hf_suspend_all();
        return 0;
    }
#ifdef HF9_REVIEW
    /* the other permanent stop: leave no armed half-frame review flag behind */
    if(n.initialized&&!fx_store_live()){hf_suspend_all();hf9_disarm();fx_store_discard(RV_STALE);n.stopped=1;return 0;}
#else
    if(n.initialized&&!fx_store_live()){hf_suspend_all();fx_store_discard(RV_STALE);n.stopped=1;return 0;}
#endif
    n.context=c;n.api=services;n.request=*q;n.active=1;n.ui_failed=0;
    rv_settings_entry(RV_PTR(c->root_address),0);
    n.port.api=services;n.port.context=context;n.port.io_lease=n.port.ui_lease=c->state_lease;
    n.port.address=address;
    for(i=0;i<6;i++)n.port.epochs[i]=q->args[2+i];
    return 1;
}
static void record_failure(unsigned status)
{
    if(n.failed||!eng_uncertain()||(!eng_write_started()&&!eng_snapshot_failed()))return;
    {
        static const char digits[]="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        unsigned e=n.entry==1?0:n.entry==6?1:n.entry==7?2:3,i;
        unsigned code=(((e*7+eng_stage())*6+status)*256)+(n.rpc_sequence&255);
        pn_copy(n.failed_text,"ERR 0000",9);
        for(i=0;i<4;++i){n.failed_text[7-i]=digits[code%36];code/=36;}
    }
    n.failed=1;
}
static int32_t finish(RvReply *r,EngStatus status)
{
    if(status!=ENG_OK) {
        record_failure(status);
        if(n.initialized&&!n.failed&&!eng_uncertain())eng_require_recheck();
        if(n.initialized) {
            if(keep_view(r))return RV_CONSUMED;
            return release_view(r);
        }
        n.active=0;r->status=RV_OK;r->detail=status;return RV_CLOSE_AND_PASS;
    }
    if(n.watch_view&&(n.view_lost||!view_owned()))return release_view(r);
    n.watch_view=0;n.safe_entry=n.flush_reason=0;n.active=0;
    r->status=RV_OK;r->detail=eng_stage();return RV_CONSUMED;
}
static int32_t core_call(void *unused,uint32_t id,uint32_t op,uint32_t a,uint32_t b,
                         void *buffer,uint32_t bytes,uint32_t count,RvReply *r)
{
    RvRequest *const q=&n.spare.io.call;int32_t result;(void)unused;
    *q=n.request;
    if(bytes>sizeof(n.scratch.bytes))return RV_RANGE;
    q->args[8]=a;q->args[9]=b;q->args[10]=bytes?eng_wire_address(n.scratch.bytes):0;
    q->args[11]=bytes;q->args[12]=count;q->args[13]=0;
    if(bytes)pn_copy(n.scratch.bytes,buffer,bytes);
    if(id==RV_RPC8&&op!=1)q->args[1]=n.rpc;
    if(id==RV_SETTINGS&&op==3)q->args[8]=0;
    if(id==RV_RPC8&&op>=2&&op<=4)++n.rpc_sequence;
    result=n.api->call(id,op,q,r);
    /* v3.8 services cleared root->grain at these two points: the S plan
     * write (op 2 reached the write section: OK or VERIFY) and the RPC W
     * (op 3 reached the native write: reply.detail 1). */
    if((id==RV_SETTINGS&&op==2&&(result==RV_OK||result==RV_VERIFY))||(id==RV_RPC8&&op==3&&r->detail==1))body.grain=0;
    if(id==RV_RPC8&&(result!=RV_OK||r->status!=RV_OK||
       (op>=2&&op<=4&&(r->native_result<0||r->native_result>65535))))n.comm_failed=1;
    if(id==RV_RPC8&&n.watch_view&&!view_owned()) {
        n.view_lost=1;eng_view_lost(1);
    } else if(id==RV_RPC8&&n.watch_view==1&&!eng_uncertain()&&!n.retry) {
        /* A native arrow already processed while RPC yielded can supersede
         * this target before its first W. Never abandon a partial write. */
        uint32_t row=RV_BYTE(0x2022f726);
        if(row>=1&&row<=UV_PHYSICAL&&row!=(unsigned)n.ui.physical+1u)eng_view_lost(1);
    }
    if(result==RV_OK&&r->status==RV_OK&&r->version==1&&r->bytes==32) {
        if(id==RV_RPC8&&op==1)n.rpc=r->token;
        if(id==RV_RPC8&&op==5)n.rpc=0;
        if(bytes)pn_copy(buffer,n.scratch.bytes,bytes);
    }
    return result;
}
/* Same predicate as the v3.8 resident rv_grain_commit (root->grain). */
static void grain_snapshot(void *unused,uint32_t mode,uint32_t enabled)
{
    RvRoot *root=RV_PTR(n.context->root_address);(void)unused;
    body.grain=root->state==RV_READY&&!(root->flags&(RF_UNCERTAIN|RF_STOP))&&enabled&&mode<=6?0x80|mode:0;
}

static unsigned uv_looks(void)
{return fx_count(eng_validated_view(),eng_validated_view()->selected_module);}
static unsigned uv_current_row(void)
{
    unsigned i,count=uv_looks();
#ifdef HF1
    if(n.ui.applied_user)return 5+count;
#else
    if(n.ui.applied_user)return 4+count;
#endif
    if(n.ui.effect)for(i=0;i<count;++i)
        if(fx_visible(eng_validated_view(),eng_validated_view()->selected_module,i)+1==n.ui.effect)return 4+i;
    return n.ui.slot-1;
}
static unsigned uv_saved_row(void)
{
    const EngSavedSelection *saved=eng_saved_selection();unsigned i,count=uv_looks();
    if(!saved)return 65535;
#ifdef HF1
    if(saved->user)return 5+count;
#else
    if(saved->user)return 4+count;
#endif
    if(!saved->ref.effect)return saved->ref.slot-1;
    for(i=0;i<count;++i)if(fx_visible(eng_validated_view(),saved->ref.unit,i)+1==saved->ref.effect)return 4+i;
    return 65535;
}
static int uv_adjusted(const UvLevels *levels)
{unsigned i;for(i=0;i<KV_DATA_CONTROLS;++i)if(levels->v[i]!=(i?0:100))return 1;return 0;}
static void uv_nav_load(void)
{
    KvUiNav *nav=&n.ui.nav;
    nav->screen=n.ui.screen;nav->control=n.ui.param;nav->armed=n.ui.armed;
    nav->current[nav->screen]=n.ui.cur;nav->top[nav->screen]=n.ui.top;
}
static void uv_nav_accept(const KvUiNav *nav)
{
    n.ui.nav=*nav;n.ui.screen=nav->screen;n.ui.param=nav->control;n.ui.armed=nav->armed;
    n.ui.cur=nav->current[nav->screen];n.ui.top=nav->top[nav->screen];
}
static void uv_value_realign(void)
{
    unsigned cursor;
    if(n.ui.screen==UV_VALUE&&!kv_ui_value_cursor(eng_knobs_view(),eng_validated_view()->selected_module,
        n.ui.slot,n.ui.param,n.ui.levels.v[n.ui.param],&cursor))n.ui.cur=(uint16_t)cursor;
}
static void uv_sync(void)
{
    EngRecipeRef r;UvLevels t;
    if(eng_display_current(&r,&t)==ENG_OK){
        const uint8_t *entry;unsigned user=eng_current_user();n.ui.applied_user=(uint8_t)user;
        n.ui.slot=r.slot;n.ui.effect=r.effect;n.ui.levels=t;
        if(r.effect)n.ui.applied_user=user=0;
        entry=user?uv_user(eng_validated_view(),user-1):0;
        if(entry&&(entry[0]!=r.slot||!pn_equal(&n.ui.saved[user-1],&n.ui.levels,sizeof(n.ui.levels)))){
            user=n.ui.confirmed_user;entry=user?uv_user(eng_validated_view(),user-1):0;
            n.ui.applied_user=(entry&&entry[0]==r.slot&&pn_equal(&n.ui.saved[user-1],&n.ui.levels,sizeof(n.ui.levels)))?(uint8_t)user:0;
        }
        if(!n.ui.applied_user&&!r.effect)n.values[r.slot-1]=t;
    }else {n.ui.slot=4;n.ui.effect=0;n.ui.applied_user=0;pn_zero(&n.ui.levels,sizeof(n.ui.levels));n.ui.levels.v[0]=100;}
}
static void uv_store(void)
{
    if(n.ui.applied_user)n.ui.saved[n.ui.applied_user-1]=n.ui.levels;
    else if(!n.ui.effect)n.values[n.ui.slot-1]=n.ui.levels;
}
static void uv_name(char *text,unsigned slot,unsigned user,char first,const UvLevels *levels)
{
    unsigned i;const char *name=eng_list()->row[slot-1].ascii+1;
    text[0]=first;
    if(user){
        const uint8_t *entry=uv_user(eng_validated_view(),user-1);
        pn_copy(text+1,entry+2,7);text[4]=uv_adjusted(levels)?'*':'-';
    }else{
        for(i=0;i<7&&name[i];++i)text[i+1]=name[i];
        if(uv_adjusted(levels))text[2]='*';
    }
}
static unsigned uv_rows(void)
{
    if(n.ui.screen==UV_DIAG)return DIAG_ROWS+uv_users(eng_validated_view());
#ifdef HF1
    if(n.ui.screen==UV_L1)return 6+uv_looks();
#else
    if(n.ui.screen==UV_L1)return 5+uv_looks();
#endif
    if(n.ui.screen<KV_UI_SCREENS){
        const char *names[8];KvUiModel model;unsigned i;
        for(i=0;i<8;++i)names[i]=eng_list()->row[i].ascii+3;
        /* No applied mark until this boot is a verified baseline or a commit. */
        uv_nav_load();model=(KvUiModel){eng_validated_view()->selected_module,n.ui.slot,eng_baseline()&&!n.ui.effect?n.ui.slot:0,
            n.ui.applied_user,&n.ui.levels,n.values,names};
        if(kv_ui_render(eng_knobs_view(),&model,&n.ui.nav,&n.ui.frame))return 0;
        return n.ui.frame.logical_count;
    }
    return 1;
}
static void uv_text(unsigned row,char text[KV_UI_TEXT])
{
    const Gxr2View *v=eng_validated_view();pn_zero(text,KV_UI_TEXT);
    if(n.ui.screen==UV_DIAG){if(row<DIAG_ROWS)diag_text(row,text);else uv_name(text,uv_user(v,row-DIAG_ROWS)[0],row-(DIAG_ROWS-1),' ',&n.ui.saved[row-DIAG_ROWS]);return;}
    if(n.ui.screen==UV_L1){
        unsigned count=uv_looks();
        if(row<4){
            unsigned applied=eng_baseline()&&!n.ui.effect&&!n.ui.applied_user&&n.ui.slot==row+1;
            (void)kv_ui_title(eng_knobs_view(),v->selected_module,row+1,
                applied?&n.ui.levels:&n.values[row],eng_list()->row[row].ascii+3,applied?'>':' ',text);
        }else if(row<4+count){
            int index=fx_visible(v,v->selected_module,row-4);
            text[0]=n.ui.effect==(unsigned)index+1u?(uv_adjusted(&n.ui.levels)?'*':'>'):' ';
            fx_name(v,(unsigned)index,text+1);
#ifdef HF1
        }else if(row==4+count){
            hf1_row_text(text);
#endif
        }else {pn_copy(text," B00 Status",12);text[2]='0'+diag_code()/10;text[3]='0'+diag_code()%10;}
        if(text[0]==' '&&row==uv_saved_row())text[0]='~';
        if(text[0]=='>'&&eng_memory_pending()){
            pn_copy(text,">M00 Unsaved",13);text[3]='0'+eng_memory_error();
        }
        {unsigned w=eng_t_warn();if(w&&row==w-1){text[1]=(char)('0'+w);pn_copy(text+2," Error",6);}}
        return;
    }
    if(n.ui.screen<KV_UI_SCREENS){
        pn_copy(text,n.ui.frame.text[row-n.ui.frame.top],KV_UI_TEXT);
        if(!row&&n.ui.applied_user&&(n.ui.screen==UV_CARD||n.ui.screen==UV_ITEMS)){
            pn_copy(text+1,uv_user(v,n.ui.applied_user-1)+2,7);
            text[4]=uv_adjusted(&n.ui.levels)?'*':'-';
        }
        if(n.ui.effect&&!row&&(n.ui.screen==UV_CARD||n.ui.screen==UV_ITEMS)){
            text[0]='<';fx_name(v,n.ui.effect-1u,text+1);
        }
        return;
    }
    pn_copy(text,n.failed_text,8);
}
static void cursor_cache(unsigned row,const RvUiList *u,unsigned constructing)
{
    RvRoot *root=RV_PTR(n.context->root_address);uint32_t irq=rv_irq_save(),state=RV_WORD(0x205a293c);
    if(rv_view_owned(root,u,constructing)&&(state==0x2022f71c||state==root->ui_block))RV_BYTE(0x205a2944)=row;
    rv_irq_restore(irq);
}
static void cache_home(void)
{
    RvRoot *root=RV_PTR(n.context->root_address);unsigned home=root->ui_restore[11];
    if(root->ui_restore[0]&&home>=1&&home<=7)cursor_cache(home,&n.list,0);
}
static int32_t list_bind_impl(unsigned operation)
{
    RvRequest *const q=&n.spare.io.list;RvReply *const r=&n.spare.io.list_reply;RvUiText t;UvWindow window;unsigned i,count,logical,top,redrawn=0;
 again:
    if(operation!=1&&!view_owned()){n.view_lost=1;return RV_STALE;}
    if(n.failed){n.ui.screen=UV_ERR;n.ui.cur=0;n.ui.armed=0;}
    n.ui.count=(uint16_t)uv_rows();if(!n.ui.count||n.ui.count>9+GXR2_FX_MAX+UV_USERS)return RV_RANGE;
    if(n.ui.cur>=n.ui.count)n.ui.cur=n.ui.count-1;
    uv_window(n.ui.count,n.ui.cur,n.ui.top,&window);
    top=window.top;n.ui.top=window.top;n.ui.physical=window.cursor;
    if(rv_native_seed(n.context)!=RV_OK)return RV_UNAVAILABLE;
    for(i=0;i<UV_PHYSICAL;++i){
        logical=top+i;pn_zero(n.ui.text[i],KV_UI_TEXT);
        if(logical<n.ui.count)uv_text(logical,n.ui.text[i]);
        else if(logical==n.ui.count)pn_copy(n.ui.text[i],"--------",8);
        else n.ui.text[i][0]=' ';
        for(count=0;count<KV_UI_TEXT-1&&n.ui.text[i][count];++count){}
        pn_zero(&t,sizeof(t));t.header=(RvBufferHeader){1,sizeof(t),0};
        t.source_address=eng_wire_address(n.ui.text[i]);t.source_bytes=count;t.source_lease=n.port.ui_lease;
        t.glyph_address=eng_wire_address(n.glyph[i]);t.glyph_capacity=sizeof(n.glyph[i]);t.glyph_lease=n.port.ui_lease;
        pn_request(&n.port,q,n.port.ui_lease);
        if(pn_call(&n.port,RV_UI_TEXT,2,q,r)!=RV_OK)return RV_IO;
        t.language=r->detail;pn_copy(n.scratch.bytes,&t,sizeof(t));
        q->args[10]=eng_wire_address(n.scratch.bytes);q->args[11]=sizeof(t);
        if(pn_call(&n.port,RV_UI_TEXT,1,q,r)!=RV_OK)return RV_IO;
        n.refs[i]=eng_wire_address(n.glyph[i]);n.labels[i]=eng_wire_address(&n.refs[i]);
    }
    n.list.header=(RvBufferHeader){1,sizeof(n.list),0};n.list.view_token=n.view;
    n.list.state_address=n.context->ui_state_address;n.list.state_bytes=n.context->ui_state_bytes;
    n.list.rows=UV_PHYSICAL;n.list.cursor=n.ui.physical;n.list.label_table=eng_wire_address(n.labels);
    n.list.details=eng_wire_address(n.details);n.list.lease_token=n.port.ui_lease;
    RV_WORD(n.list.state_address+4)=n.list.state_address+32;
    RV_WORD(n.list.state_address+32+5*12)=n.list.label_table;
    RV_BYTE(n.list.state_address+32+5*12+4)=UV_PHYSICAL;
    RV_WORD(n.list.state_address+32+5*12+8)=0;
    pn_request(&n.port,q,n.port.ui_lease);q->args[9]=q->args[12]=UV_PHYSICAL;
    q->args[10]=eng_wire_address(&n.list);q->args[11]=sizeof(n.list);
    if(pn_call(&n.port,RV_UI_LIST,operation,q,r)!=RV_OK)return RV_IO;
    n.view=r->token;
    if(!n.failed){
        unsigned shown=eng_memory_pending();
        EngStatus status=eng_check_settings();
        if(status!=ENG_OK){record_failure(status);return RV_IO;}
        /* P2-01: redraw once when the save result changed the hint. The
         * H01 publication (operation 1) cannot be updated inside the same
         * constructor entry; its next redraw shows the result. */
        if(operation!=1&&!redrawn&&shown!=(unsigned)eng_memory_pending()){redrawn=1;operation=3;goto again;}
    }
    cursor_cache(n.ui.physical+1,&n.list,operation==1);return RV_OK;
}
static int32_t list_bind(unsigned operation)
{int32_t status=list_bind_impl(operation);if(status!=RV_OK)n.ui_failed=1;return status;}
static int keep_view(RvReply *r)
{
    int32_t status;unsigned i;RvRoot *root=RV_PTR(n.context->root_address);
    if(!n.watch_view||n.ui_failed||n.view_lost||!view_owned())return 0;
    for(i=0;i<4;++i)if(n.port.epochs[i]!=root->epoch[i])return 0;
    n.port.epochs[4]=root->epoch[RV_VIEW_E];n.port.epochs[5]=root->epoch[RV_S_E];
    if(!n.failed){
        eng_require_recheck();eng_restore_cursor();n.retry=1;uv_sync();n.ui.cur=n.ui.last_cur;
        uv_value_realign();
    }
    status=list_bind(3);if(status!=RV_OK)return 0;
    if(n.entry==7&&!n.request.args[9])cache_home();
    n.watch_view=n.safe_entry=n.flush_reason=n.active=0;
    r->status=RV_OK;r->detail=eng_stage();return 1;
}
static int32_t ui_finish(RvReply *r,int32_t result)
{
    if(result==RV_FAULT){record_failure(eng_uncertain()?ENG_UNCERTAIN:ENG_IO);
        if(!n.failed&&!eng_uncertain())eng_require_recheck();
        if(keep_view(r))return RV_CONSUMED;
        return release_view(r);}
    if(n.watch_view&&(n.view_lost||!view_owned()))return release_view(r);
    if(result==RV_CLOSE_AND_PASS)cache_home();
    n.watch_view=n.safe_entry=n.flush_reason=n.active=0;r->status=RV_OK;return result;
}
static EngStatus retry_view(void)
{
    EngStatus status;
    if(!n.retry)return ENG_OK;
    if(n.rpc){RvReply closed;if(core_call(0,RV_RPC8,5,0,0,0,0,0,&closed)!=RV_OK)return ENG_IO;}
    status=eng_retry_live();if(status==ENG_OK){n.retry=0;uv_sync();}return status;
}
static int32_t deferred_menu(RvReply *r,EngStatus status)
{
    record_failure(status);
    if(!n.failed){eng_require_recheck();n.retry=0;return release_view(r);}
    if(list_bind(1)!=RV_OK)return finish(r,ENG_IO);
    return finish(r,ENG_OK);
}
static EngStatus uv_preview(unsigned slot,const UvLevels *levels,unsigned user)
{
    EngStatus status;EngRecipeRef actual;UvLevels tweak;UvLevels current;
    eng_memory_user(user);status=eng_project_preview(slot,levels);
    if(status!=ENG_OK)return status;
    if(eng_display_current(&actual,&tweak)!=ENG_OK)return ENG_STALE;
    current=tweak;
    if(actual.effect||actual.slot!=slot||!pn_equal(&current,levels,sizeof(current)))return ENG_IO;
    n.ui.effect=0;n.ui.applied_user=(uint8_t)user;n.ui.slot=actual.slot;n.ui.levels=current;uv_store();
    return ENG_OK;
}
static EngStatus uv_effect(unsigned effect,const UvLevels *levels)
{
    EngStatus status;EngRecipeRef r;UvLevels t;
    status=eng_preview_effect(effect,levels);
    if(status!=ENG_OK)return status;
    if(eng_display_current(&r,&t)!=ENG_OK||r.effect!=effect||!pn_equal(&t,levels,sizeof(t)))return ENG_IO;
    n.ui.effect=r.effect;n.ui.slot=r.slot;n.ui.levels=t;n.ui.applied_user=0;
    return ENG_OK;
}
static EngStatus uv_active(const UvLevels *levels)
{return n.ui.effect?uv_effect(n.ui.effect,levels):uv_preview(n.ui.slot,levels,n.ui.applied_user);}
static EngStatus uv_look_row(unsigned ordinal)
{
    int index=fx_visible(eng_validated_view(),eng_validated_view()->selected_module,ordinal);
    const uint8_t *e;UvLevels t;const EngSavedSelection *saved=eng_saved_selection();
    if(index<0)return ENG_REJECTED;
    e=fx_entry(eng_validated_view(),(unsigned)index);
    if(n.ui.effect==(unsigned)index+1u)t=n.ui.levels;
    else if(saved&&saved->ref.effect==(unsigned)index+1u)t=saved->levels;
    else if(kv_ui_default(eng_knobs_view(),eng_validated_view()->selected_module,e[0],&t))return ENG_REJECTED;
    return uv_effect((unsigned)index+1u,&t);
}
static EngStatus uv_flat_row(unsigned row)
{
    unsigned count=uv_looks();
    if(row<4)return uv_preview(row+1,&n.values[row],0);
    if(row<4+count)return uv_look_row(row-4);
    return ENG_OK;
}
static EngStatus uv_move(unsigned physical)
{
    unsigned old=n.ui.physical,target=n.ui.cur;int delta;UvLevels levels;EngStatus status=ENG_OK;KvUiNav nav;
    if(physical>=UV_PHYSICAL)return ENG_REJECTED;
    
    n.spare.io.preselect=0;n.ui.last_cur=n.ui.cur;
    if(n.ui.screen==UV_L1||n.ui.screen==UV_DIAG){
        if(physical==(old+1)%UV_PHYSICAL)delta=1;
        else if(physical==(old+UV_PHYSICAL-1)%UV_PHYSICAL)delta=-1;
        else delta=0;
        n.ui.armed=0;n.ui.physical=(uint8_t)physical;
        target=(target+n.ui.count+delta)%n.ui.count;
        if(n.ui.screen!=UV_DIAG)status=uv_flat_row(target);
        if(status==ENG_OK)n.ui.cur=(uint16_t)target;
        return status;
    }
    if(n.ui.screen<KV_UI_SCREENS){
        uv_nav_load();
        if(kv_ui_native_move(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,
            &n.ui.levels,&n.ui.nav,physical,&levels,&nav))return ENG_REJECTED;
        n.ui.physical=(uint8_t)physical;
        if(n.ui.screen==UV_VALUE&&!pn_equal(&levels,&n.ui.levels,sizeof(levels)))status=uv_active(&levels);
        if(status==ENG_OK)uv_nav_accept(&nav);
    }
    return status;
}
static int32_t uv_disp(void)
{
    unsigned cur=n.ui.cur,offer=n.spare.io.preselect;UvLevels levels;KvUiNav nav;KvUiEvent event;
    n.ui.last_cur=n.ui.cur;
    if(n.ui.screen==UV_DIAG){
        if(cur>=DIAG_ROWS){unsigned u=cur-DIAG_ROWS;const uint8_t *e=uv_user(eng_validated_view(),u);
            if(!e||uv_preview(e[0],&n.ui.saved[u],u+1)!=ENG_OK)return RV_FAULT;
            if(kv_ui_nav_init(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,&n.ui.levels,&nav))return RV_FAULT;
#ifdef HF1
            n.ui.l1_cur=5+uv_looks();uv_nav_accept(&nav);
#else
            n.ui.l1_cur=4+uv_looks();uv_nav_accept(&nav);
#endif
            return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;
        }else{n.ui.screen=UV_L1;n.ui.cur=offer?offer-1:uv_current_row();n.ui.top=0;return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;}
    }
#ifdef HF1
    if(n.ui.screen==UV_L1&&cur+2u==n.ui.count){hf1_toggle();return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;}
#endif
    if(n.ui.screen==UV_L1&&cur+1u==n.ui.count){n.ui.screen=UV_DIAG;n.ui.cur=n.ui.top=0;return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;}
    n.spare.io.preselect=0;
    if(offer&&n.ui.screen==UV_L1&&cur==offer-1u&&uv_flat_row(cur)!=ENG_OK)return RV_FAULT;
    if(n.ui.screen==UV_L1){
        if(kv_ui_nav_init(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,&n.ui.levels,&nav))return RV_FAULT;
        n.ui.l1_cur=n.ui.cur;uv_nav_accept(&nav);
    }else if(n.ui.screen==UV_CARD&&!cur){
        n.ui.screen=UV_L1;n.ui.cur=n.ui.l1_cur;n.ui.top=0;
    }else if(n.ui.screen<KV_UI_SCREENS){
        uv_nav_load();
        if(kv_ui_disp(eng_knobs_view(),eng_validated_view()->selected_module,n.ui.slot,&n.ui.levels,
            &n.ui.nav,&levels,&nav,&event))return RV_FAULT;
        if(event.kind==KV_UI_EVENT_DEFAULT&&uv_active(&levels)!=ENG_OK)return RV_FAULT;
        uv_nav_accept(&nav);
    }
    return list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT;
}
void xpan_label_once(void);
/* 1 = H01 load released BO_PENDING. Other values are the check that refused. */
uint32_t xpan_lane_handoff __attribute__((used));
/* H51 stores BO_ATTEMPTED before rv_load and runs BOOT_RUN only after that
 * load returns. An H01 load sets RF_ATTEMPTED and leaves the word at
 * BO_PENDING, so every later H51 retries rv_load, gets RV_FAULTED, and never
 * reaches body_event. Releasing exactly BO_PENDING here is the handoff to
 * maintenance. It does not raise BO_DIRTY and does not run the boot
 * transaction; the H51 path never matches this word value. */
static void release_pending_lane_after_load(void)
{
    RvRoot *root;RvSession *s;
    xpan_lane_handoff=2;
    if(!n.context)return;
    root=RV_PTR(n.context->root_address);
    s=RV_PTR(n.context->session_address);
    if(root->magic!=RV_ROOT_MAGIC||root->version!=RV_ROOT_VERSION){xpan_lane_handoff=3;return;}
    if(root->state!=RV_VALIDATED){xpan_lane_handoff=4;return;}
    if(root->flags&(RF_STOP|RF_UNCERTAIN)){xpan_lane_handoff=5;return;}
    if(!(root->flags&RF_ATTEMPTED)||!root->lease||root->lease!=n.context->nonce||
       root->lease_inverse!=~root->lease||n.context->session_address!=root->block){xpan_lane_handoff=6;return;}
    if(s->leases[0].token!=root->lease||s->leases[0].inverse!=~root->lease||
       s->leases[0].base!=root->block){xpan_lane_handoff=7;return;}
    if(s->bindings[RV_BOOT_E]!=root->epoch[RV_BOOT_E]||
       s->bindings[RV_HEAP_E]!=root->epoch[RV_HEAP_E]||
       s->bindings[RV_MODE_E]!=root->epoch[RV_MODE_E]){xpan_lane_handoff=8;return;}
    if(root->reserved_lane!=BO_PENDING){xpan_lane_handoff=9;return;}
    root->reserved_lane=BO_ATTEMPTED;
    xpan_lane_handoff=1;
}
static int32_t init_core(RvReply *r)
{
    const uint8_t *p;EngPort *const port=&n.spare.io.port;EngStatus status;Gxr2Unit unit;unsigned i;
    if(n.initialized){r->capabilities=CAP_UI|CAP_S|CAP_W|CAP_BODY|CAP_TICK;return finish(r,ENG_OK);}
    p=eng_wire_pointer(n.context->image_address);pn_zero(&n.gate,sizeof(n.gate));
    n.gate.bytes=p;n.gate.length=n.context->image_bytes;
    {RvSession *s=RV_PTR(n.context->session_address);pn_copy(&unit,&s->unit,sizeof(unit));}
    trust_init();
    if(fx_store_read())return finish(r,ENG_REJECTED);
    p=fx_store_candidate();
    if(!p||gxr2_gate_validate(p,fx_store_catalog_bytes(),&n.trust,&unit,0,&n.gate)!=GXR2_OK||!uv_validate(&n.gate)){
        fx_store_discard(RV_VERIFY);return finish(r,ENG_REJECTED);}
    /* Catalogue bytes are data only. Resident entry offsets always point
     * into the newly linked private engine, never into the library. */
    pn_zero(port,sizeof(*port));port->call=core_call;port->gated=&n.gate;port->commit_grain=grain_snapshot;
    status=eng_init(p,n.gate.length,port);if(status!=ENG_OK)return finish(r,status);
    for(i=0;i<8;++i)if(kv_ui_default(eng_knobs_view(),n.gate.selected_module,i+1,&n.values[i]))return finish(r,ENG_REJECTED);
    n.ui.levels=n.values[3];n.ui.param=1;
    if(kv_ui_nav_init(eng_knobs_view(),n.gate.selected_module,4,&n.ui.levels,&n.ui.nav))return finish(r,ENG_REJECTED);
    for(i=0;i<uv_users(&n.gate);++i){unsigned slot;KvRequest request;
        if(kv_ui_legacy_record(uv_user(&n.gate,i),24,&slot,&n.ui.saved[i])||
           kv_data_request(eng_knobs_view(),n.gate.selected_module,slot,&n.ui.saved[i],&request))return finish(r,ENG_REJECTED);
    }
    if(fx_store_publish())return finish(r,ENG_REJECTED);
    n.ui.slot=4;n.ui.group=1;n.initialized=1;n.install_status=RV_UNAVAILABLE;
    r->capabilities=CAP_UI|CAP_S|CAP_W|CAP_BODY|CAP_TICK;
    /* Both successful loads return through here, before the first menu or format.
     * The lane handoff is the H01 case only; an H51 load already stored
     * BO_ATTEMPTED and still continues into BOOT_RUN after rv_load returns. */
    xpan_label_once();
    release_pending_lane_after_load();
    return finish(r,ENG_OK);
}
int32_t ig_init(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    if(!ingress(a,c,q,r))return RV_FAULT;
    return init_core(r);
}
#ifdef XPAN_D2_DIAG
void xd_log(void);
void xd_freeze(void);
#endif
int32_t ig_menu(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;
#ifdef XPAN_D2_DIAG
    xd_freeze();
#endif
    if(!ingress(a,c,q,r)||!n.initialized){fx_mask_suspend();n.active=0;return RV_FAULT;}
    /* The setup menu can be opened after a body path has put 16:9 back. */
    fx_mask_suspend();
#ifdef HF1
    hf1_suspend();
#endif
    {RvRoot *root=RV_PTR(n.context->root_address);
     if(root->state==RV_READY&&!(root->flags&(RF_STOP|RF_UNCERTAIN|RF_BUSY)))xpan_label_once();}
    n.entry=1;rv_settings_entry(RV_PTR(n.context->root_address),n.entry);n.watch_view=n.view_lost=n.comm_failed=0;eng_view_lost(0);
    if(n.failed){int32_t visible=list_bind(1);if(visible==RV_OK)visible=rv_native_layer(2,0,0);
        return ui_finish(r,visible==RV_OK?RV_CONSUMED:RV_FAULT);}
    if(n.rpc){RvReply closed;if(core_call(0,RV_RPC8,5,0,0,0,0,0,&closed)!=RV_OK)return deferred_menu(r,ENG_IO);}
    status=eng_rebind();if(status!=ENG_OK)return deferred_menu(r,status);
    /* P1-03 (A): 0x205D9AA3 is the native MY dial position (1..3) read by
     * the MY dispatcher at 0x202E43D4. A MY boot is not restored. */
    eng_boot_source(RV_BYTE(0x205d9aa3));
    n.panel.open=n.panel.input_enabled=0;
    status=eng_menu_open();if(status!=ENG_OK)return deferred_menu(r,status);
    {const EngSavedSelection *saved=eng_saved_selection();unsigned row;
     if(saved){if(saved->user)n.ui.saved[saved->user-1]=saved->levels;else if(!saved->ref.effect)n.values[saved->ref.slot-1]=saved->levels;}
     uv_sync();n.ui.confirmed_user=n.ui.applied_user;n.ui.screen=UV_L1;n.ui.cur=uv_current_row();n.ui.armed=n.ui.top=0;
     n.spare.io.preselect=0;row=saved?uv_saved_row():65535;
     if(row<65535&&!eng_active_code()){n.ui.cur=(uint16_t)row;n.spare.io.preselect=(uint16_t)(row+1);}}
    if(diag_page()){n.ui.screen=UV_DIAG;n.ui.cur=n.ui.top=0;}
    if(list_bind(1)!=RV_OK)return finish(r,ENG_IO);
    n.retry=0;return finish(r,ENG_OK);
}
int32_t ig_apply(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;unsigned row,round=0;
    if(!ingress(a,c,q,r)||!n.initialized){fx_mask_suspend();n.active=0;return RV_FAULT;}
    n.entry=8;rv_settings_entry(RV_PTR(n.context->root_address),n.entry);n.comm_failed=0;
    if(!start_view())return release_view(r);
    if(n.failed)return ui_finish(r,list_bind(3)==RV_OK?RV_CONSUMED:RV_FAULT);
    eng_key_begin();
    status=retry_view();if(status!=ENG_OK)return finish(r,status);
    row=q->args[8];
    do{
        eng_view_lost(0);status=uv_move(row);
        if(n.view_lost||!view_owned())return finish(r,status);
        row=RV_BYTE(0x2022f726);
        if(row<1||row>UV_PHYSICAL||row==(unsigned)n.ui.physical+1u)break;
        if(status!=ENG_OK&&(eng_uncertain()||n.comm_failed))break;
        --row;
    }while(++round<16);
    if(status==ENG_OK&&list_bind(3)!=RV_OK)status=ENG_IO;
    return finish(r,status);
}
int32_t ig_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngRecipeRef current;UvLevels tweak;EngStatus status;
    if(!ingress(a,c,q,r)||!n.initialized){fx_mask_suspend();n.active=0;return RV_FAULT;}
    n.entry=7;rv_settings_entry(RV_PTR(n.context->root_address),n.entry);if(!start_view())return release_view(r);n.ui.armed=0;
    if(n.failed)return ui_finish(r,q->args[9]?RV_CONSUMED:RV_CLOSE_AND_PASS);
    eng_key_begin();
    status=retry_view();if(status!=ENG_OK)return finish(r,status);
    if(q->args[8]==7){
        unsigned offer=n.spare.io.preselect;n.spare.io.preselect=0;n.ui.last_cur=n.ui.cur;
        /* OK (native key 0x23 in args[13]) on the offered row applies it.
         * ADJ, half-press and any other exit leave pure 04. */
        if(offer&&q->args[13]==0x23&&n.ui.screen==UV_L1&&n.ui.cur==offer-1u&&
           uv_flat_row(offer-1)!=ENG_OK)return ui_finish(r,RV_FAULT);
        status=eng_check_settings();if(status!=ENG_OK)return finish(r,status);
        if(eng_display_current(&current,&tweak)==ENG_OK&&eng_confirm_live(&current,&tweak)!=ENG_OK)return ui_finish(r,RV_FAULT);
        n.ui.confirmed_user=n.ui.applied_user;
        if(!q->args[9])eng_menu_close();
        return ui_finish(r,q->args[9]?RV_CONSUMED:RV_CLOSE_AND_PASS);
    }
    n.active=0;r->status=RV_OK;return RV_PASS;
}
int32_t ig_panel_open(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status;
    if(!ingress(a,c,q,r)||!n.initialized){fx_mask_suspend();n.active=0;return RV_FAULT;}
    n.entry=6;rv_settings_entry(RV_PTR(n.context->root_address),n.entry);if(!start_view())return release_view(r);if(n.failed)return ui_finish(r,RV_CONSUMED);
    eng_key_begin();
    status=retry_view();if(status!=ENG_OK)return finish(r,status);
    return ui_finish(r,uv_disp());
}
/* ---- v3.9 body entries. The resident calls panel_event for H09/H10 (UI
 * lane, task 6) and panel_abort for H40/H41 (task 26). Neither runs the
 * menu ingress: no service, no session or context write, n.active and the
 * shared request stay untouched. Any unexpected request answers PASS, which
 * leaves the stock path unchanged. */
static int body_request(uint32_t c,const RvRequest *q,RvReply *r,const RvApi *a)
{
    if(!q||!r||a||q->version!=1||q->bytes!=64||q->flags||q->args[0]!=c||!n.context||
       q->args[10]!=eng_wire_address(n.context)||q->args[11]!=sizeof(RvPrivateContext)||
       n.context->nonce!=c||!n.initialized||n.stopped||n.active){
        if(!n.active&&(n.stopped||!n.initialized)){fx_mask_hw_restore();
#ifdef HF1
            hf1_suspend();
#endif
        }
        return 0;
    }
    r->version=1;r->bytes=32;r->status=RV_OK;r->actual=r->token=r->epoch=r->capabilities=r->detail=0;
    return 1;
}
/* H09: the v3.8 rv_grain, unchanged, answered as an edit list. */
static int32_t body_grain(const uint8_t *p,RvReply *r)
{
    RvRoot *root=RV_PTR(n.context->root_address);uint32_t g=body.grain,s=RV_WORD(0x200c0dac),size,level;
    if(root->state!=RV_READY||!g||(root->flags&(RF_UNCERTAIN|RF_STOP))||
       !s||RV_WORD(0x200c0db0)<0xc9e||RV_BYTE(s+0x36e)!=(g&127)||
       (RV_BYTE(0x205d9a7f)!=0&&RV_BYTE(0x205d9a7f)!=4)||
       (p[0x1a]|p[0x14]|p[0x75]|p[0x1e]|p[0x26]))return RV_PASS;
    size=RV_BYTE(s+0x3aa);
    if(size>16||!((0x11126u>>size)&1))return RV_PASS;
    level=RV_BYTE(s+0xc9d);level=level-1<3?level:1;
    /* (offset<<8|value), two per word, high half first: same order as v3.8 */
    r->actual=(0x1a15u<<16)|0x1000u;r->token=(0x3201u<<16)|(0x6f00u|level);r->detail=4;
    return RV_CONSUMED;
}
static int ok_entry_row(void)
{
    unsigned offer=n.spare.io.preselect;
#ifdef HF1
    return n.watch_view==0&&!n.failed&&!n.ui_failed&&!n.panel.open&&n.ui.screen==UV_L1&&n.ui.cur+2u<n.ui.count&&
        !(offer&&n.ui.cur==offer-1u)&&rv_view_owned(RV_PTR(n.context->root_address),&n.list,0);
#else
    return n.watch_view==0&&!n.failed&&!n.ui_failed&&!n.panel.open&&n.ui.screen==UV_L1&&n.ui.cur+1u<n.ui.count&&
        !(offer&&n.ui.cur==offer-1u)&&rv_view_owned(RV_PTR(n.context->root_address),&n.list,0);
#endif
}
static int32_t body_key(uint32_t code,RvReply *r)
{
    uint32_t view=RV_WORD(0x205d9c00);
#ifdef HF1
    if(view==56&&code==0x23&&((n.ui.screen==UV_DIAG)||(n.ui.screen==UV_L1&&(n.ui.cur+1u==n.ui.count||n.ui.cur+2u==n.ui.count))||(ig_body_config.ok_to_panel&&ok_entry_row()))){r->detail=0x25;return RV_CONSUMED;}
#else
    if(view==56&&code==0x23&&((n.ui.screen==UV_DIAG)||(n.ui.screen==UV_L1&&n.ui.cur+1u==n.ui.count)||(ig_body_config.ok_to_panel&&ok_entry_row()))){r->detail=0x25;return RV_CONSUMED;}
#endif
    return RV_PASS;
}
#include "boot_adapter.inc.c"
#ifdef MERGED_R1
static void dispatch_frame_key(uint32_t code)
{
    if(fx_aspect_169()){
        hf1_frame_key(code);
        fx_frame_key(code);
    }else{
        fx_frame_key(code);
        hf1_frame_key(code);
    }
#ifdef HF9_REVIEW
    hf9_frame_key(); /* half-frame review flag block, after the half-frame state moved */
#endif
}
#endif
int32_t ig_panel_event(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    if(!body_request(c,q,r,a))return RV_PASS;
#ifdef MERGED_R1
    if(q->args[8]==51){
#ifdef L2N_FOLD_A
        l2n_fold_apply_once();
#endif
        dispatch_frame_key(0x29);return RV_PASS;}
#elif defined(XPAN_D2_DIAG)
    if(q->args[8]==51){fx_frame_key(0x29);xd_log();return RV_PASS;}
#else
    if(q->args[8]==51){fx_frame_key(0x29);
#ifdef HF1
        hf1_frame_key(0x29);
#endif
        return RV_PASS;}
#endif
    if(q->args[8]==0x101)return boot_run(a,c,q,r);
    if(q->args[8]==9){
        uint32_t p=q->args[9];
        /* Parameter notify can follow the focus-window clear. Repaint first. */
#ifdef MERGED_R1
        if(RV_WORD(0x205d9c00u)==5u)dispatch_frame_key(0x29);
#else
        if(RV_WORD(0x205d9c00u)==5u)fx_frame_key(0x29);
#endif
        if(p<0x20000000u||p>0x20800000u-144u)return RV_PASS;
        return body_grain(RV_PTR(p),r);
    }
    if(q->args[8]==10){
        RvRoot *root=RV_PTR(n.context->root_address);
        if(root->state==RV_READY&&!(root->flags&(RF_STOP|RF_UNCERTAIN|RF_BUSY)))xpan_label_once();
#ifdef L2N_FOLD_A
        l2n_fold_apply_once();
#endif
#ifdef MERGED_R1
        dispatch_frame_key(q->args[9]);
#else
        fx_frame_key(q->args[9]);
#ifdef XPAN_D2_DIAG
        xd_log();
#endif
#ifdef HF1
        hf1_frame_key(q->args[9]);
#endif
#endif
        return body_key(q->args[9],r);
    }
    return RV_PASS;
}
/* H40/H41: pass-through, read only. No K, descriptor or pixel write and no
 * IMG_TOUCHED store, so the resident never skips encoding for this DAT. */
int32_t ig_panel_abort(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    uint32_t sp,outer=0;
#ifdef HF5_H42
    uint32_t outer42=0;
#endif
    if(!q||!r||a||q->version!=1||q->bytes!=64||q->flags||q->args[0]!=c||!n.initialized||n.stopped)return RV_PASS;
    r->version=1;r->bytes=32;r->status=RV_OK;r->actual=r->token=r->epoch=r->capabilities=r->detail=0;
    sp=q->args[12];
    if(sp>=0x20000000u&&sp<=0x20800000u-8u&&!(sp&3)){
        outer=RV_WORD(sp+4);
#ifdef HF5_H42
        outer42=RV_WORD(sp);
#endif
    }
    if(q->args[8]==42){
#if defined(HF8_DIAG) && !defined(HF9_DIAG)
        hf8_rec_review(q->args[9]);
#endif
#ifdef HF5_H42
        int32_t rv=fx_image_entry(q,r);
        if(hf1_on_h40(n.context,q->args[9],outer42,q->args[13],ig_body_config.image_follow)){r->detail=IMG_REPLY_DONE;return RV_CONSUMED;}
        return rv;
#else
        return fx_image_entry(q,r);
#endif
    }
    if(q->args[8]==41){fx_image_entry(q,r);return RV_PASS;}
#ifdef HF7_H43
    if(q->args[8]==43){
        if(hf7_on_h43(n.context,q->args[9],q->args[12],q->args[13])){r->detail=IMG_REPLY_DONE;return RV_CONSUMED;}
        return RV_PASS;
    }
#endif
    if(q->args[8]==40)fx_image_entry(q,r);
    if(q->args[8]!=40)return RV_PASS;
#ifdef HF1
#ifdef HF5_H42
    hf5_on_h40(q->args[9],outer,q->args[13]);
#else
    if(hf1_on_h40(n.context,q->args[9],outer,q->args[13],ig_body_config.image_follow)){r->detail=IMG_REPLY_DONE;return RV_CONSUMED;}
#endif
#endif
    if(ig_body_config.image_follow&&(outer==0x201558a8u||outer==0x2015eaa4u)){r->detail=IMG_REPLY_DONE;return RV_CONSUMED;}
    return RV_PASS;
}
int32_t ig_stop(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    fx_mask_suspend();
#ifdef HF1
    hf1_suspend();
#endif
    if(!ingress(a,c,q,r))return RV_FAULT;
    fx_mask_suspend();
#ifdef HF1
    hf1_suspend();
#endif
#ifdef HF9_REVIEW
    hf9_disarm();
#endif
    cache_home();eng_menu_close();n.stopped=1;return finish(r,ENG_OK);
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
void ig_host_body(void **p,uint32_t *bytes){*p=&body;*bytes=sizeof(body);}
void ig_host_body_reset(void){pn_zero(&body,sizeof(body));}
uint32_t ig_host_workspace_bytes(void){return sizeof(SessionWork);}
#endif
int32_t ig_bootstrap(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    RvEngineEntries *e;if(!ingress(a,c,q,r))return RV_FAULT;
    if(ig_control_off()){n.active=0;n.stopped=1;r->status=RV_FAULTED;r->detail=0x44495341;return RV_CLOSE_AND_PASS;}
    if(!eng_attach_state(n.context)){n.active=0;r->status=RV_RANGE;return RV_FAULT;}
    diag_init(n.context);
    e=eng_wire_pointer(n.context->entries_address);pn_zero(e,sizeof(*e));e->version=1;e->bytes=40;
    e->init=OFF(ig_init);e->menu_open=OFF(ig_menu);e->event=OFF(ig_event);
    e->panel_open=OFF(ig_panel_open);e->panel_event=OFF(ig_panel_event);e->panel_abort=OFF(ig_panel_abort);
    e->apply_step=OFF(ig_apply);e->shutdown=e->abort=OFF(ig_stop);
    /* r7 handshake: the same call runs the pure init. RV_INIT_DONE and the
     * entry table size are reported only after init has fully succeeded. */
    {int32_t result=init_core(r);
     if(result!=RV_CONSUMED||r->status!=RV_OK||!n.initialized)return result==RV_CONSUMED?RV_CLOSE_AND_PASS:result;
     r->actual=40;r->detail=RV_INIT_DONE;return RV_CONSUMED;}
}
