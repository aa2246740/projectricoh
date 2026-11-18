#include "eng_internal.h"
#include "eng_core_private.h"
#include "../../../../../../memory_codec.h"
#include "../../../../diagnostic.h"
#include "../../../../ui_v2_data.h"
#include "../../../../memory.h"
#include "../../../../fx_pool.h"
#include "../../../../kv2/kv_math.h"
typedef struct {
    EngPort port; EngData data; EngEpoch epoch;
    EngRecipeRef current,confirmed; UvLevels tweak,confirmed_tweak; EngList list;
    uint8_t stock[552],live[552],staging[552];
    KvWork work;
    uint8_t ready,bound,busy,committed,uncertain,t_checked,t_warn,t_pending;
    uint8_t neighbor,neighbor_valid,stage,remember_checked,confirmed_valid,previewing,view_lost;
    uint8_t write_started,recheck,settings_pending;
    /* Remembered recipe (settings record). Appended: older offsets stay unchanged.
     * memory_dirty: the current committed state is a user choice whose
     * record is not stored yet. User indices remain one-based in RAM. */
    uint8_t restore_done,baseline,memory_want,memory_dirty,memory_user,current_user,confirmed_user,memory_blocked;
    /* P1-03 (B): remembered recipe offered at the first H01, never applied
     * there. boot_my: the native MY dial position was non-zero. */
    uint8_t boot_my,preselect,t_warn_slot;UvLevels preselect_t;
    /* s_busy: the stock lock was busy during this key press (one lock try:
     * op 6, op 2 or op 5). s_refused: this recovery stopped on that lock.
     * s_unwritten: the committed state's S plan was not written (the view
     * was lost first). A deferred check (settings_pending only) is not. */
    uint8_t s_busy,s_refused,s_unwritten;
    /* Without a baseline, live_verified belongs only to the active apply.
     * snapshot_fault keeps failed capture or compensation uncertain, even
     * if no W has been sent. */
    uint8_t live_verified,snapshot_fault,boot_active,boot_committed;
    EngSavedSelection saved;
    uint8_t memory_result,memory_error,auto_result;
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
}
static int32_t t_seen=-1;
static uint16_t w_count;
/* Service request and reply buffers. settings_match and apply_impl never
 * nest; rpc and end are siblings; a reply read again after fresh() keeps its
 * own buffer. They share KvWork.stage: kv_apply_work's scratch is dead
 * outside compute(), and compute() makes no service call. */
typedef struct {
    RvSettingsInfo info; RvReply reply,rpc,snap; RvEpochSnapshot epochs;
    union { RvSettingsPlan plan; RvSettingsRecord record; } request;
} EngIo;
typedef union { KvStage math; EngIo io; } EngScratch;
_Static_assert(sizeof(EngIo)<=sizeof(KvStage),"service buffers fit the math scratch");
#define io (((EngScratch *)(void *)&g->work.stage)->io)
const Gxr2View *eng_validated_view(void){return &g->data.view;}
uint8_t *eng_work_area(void){return g->work.base;}
_Static_assert(sizeof(Gxr2Trust)<=sizeof(g->work.result),"trust fits the idle result buffer");
Gxr2Trust *eng_work_trust(void){return (Gxr2Trust *)(void *)g->work.result;}
const KvDataView *eng_knobs_view(void){return &g->data.knobs;}
#ifdef ENG_HOST
void eng_host_reset(void) { unsigned i;for(i=0;i<sizeof(*g);i++)((uint8_t *)g)[i]=0; t_seen=-1;w_count=0; }
void eng_host_region(void **p,uint32_t *bytes){*p=g;*bytes=sizeof(*g);}
#endif
static uint16_t b16(const uint8_t *p) { return (uint16_t)((unsigned)p[0]*256u+p[1]); }
static uint32_t b32(const uint8_t *p) { return (uint32_t)b16(p)*65536u+b16(p+2); }
#define copy ig_copy
#define clear ig_zero
#define equal ig_equal
static void expire_previous(void)
{
    /* An observed initial state is not a recipe ledger. Neither its rows
     * nor its T/neighbor observations qualify for a later transaction. */
    if(!g->baseline)g->live_verified=g->t_checked=g->t_pending=g->neighbor_valid=0;
}
static void disarm(void)
{ if(g->port.commit_grain)g->port.commit_grain(g->port.user,0,0);
  if(g->port.grain) { g->port.grain->armed=0; __asm__ __volatile__("":::"memory"); } }
static EngStatus mapped(int32_t s)
{
    if(s==RV_OK) return ENG_OK;
    if(s==RV_UNCERTAIN || g->uncertain) return ENG_UNCERTAIN;
    if(s==RV_STALE || s==RV_OWNER) return ENG_STALE;
    if(s==RV_IO) return ENG_IO;
    if(s==RV_FAULTED) return ENG_FAULT;
    return ENG_REJECTED;
}
static int32_t svc(unsigned s,unsigned op,unsigned a,unsigned b,void *p,unsigned n,unsigned count,RvReply *r)
{
    int32_t result;
    clear(r,sizeof(*r)); r->version=1; r->bytes=sizeof(*r);
    if(g->boot_active&&!eng_boot_check())return RV_STALE;
    result=g->port.call(g->port.user,s,op,a,b,p,n,count,r);
    if(g->boot_active&&!eng_boot_check())return RV_STALE;
    if(r->version!=1 || r->bytes!=sizeof(*r) || result!=r->status) return RV_IO;
    return result;
}
static int snapshot(EngEpoch *e,RvUnitInfo *u)
{
    clear(&io.epochs,sizeof(io.epochs)); io.epochs.header.version=1; io.epochs.header.bytes=sizeof(io.epochs);
    if(svc(RV_EPOCHS,12,0,0,&io.epochs,sizeof(io.epochs),0,&io.snap)!=RV_OK || io.epochs.header.version!=1 || io.epochs.header.bytes!=sizeof(io.epochs) || io.epochs.header.flags) return 0;
    e->boot=io.epochs.epochs[RV_BOOT_E]; e->heap=io.epochs.epochs[RV_HEAP_E];
    e->link=io.epochs.epochs[RV_LINK_E]; e->unit=io.epochs.epochs[RV_UNIT_E];
    e->view=io.epochs.epochs[RV_VIEW_E]; e->settings=io.epochs.epochs[RV_S_E]; e->mode=io.epochs.epochs[RV_MODE_E];
    if(!u) return 1;
    clear(u,sizeof(*u)); u->header.version=1; u->header.bytes=sizeof(*u);
    return svc(RV_UNIT,1,0,0,u,sizeof(*u),0,&io.snap)==RV_OK && u->header.version==1 &&
        u->header.bytes==sizeof(*u) && !u->header.flags && u->valid==1 && u->unit_epoch==e->unit && u->link_epoch==e->link;
}
static int same_epoch(const EngEpoch *a,const EngEpoch *b)
{
    return a->boot==b->boot && a->heap==b->heap && a->link==b->link &&
           a->unit==b->unit && a->settings==b->settings && a->mode==b->mode;
}
static int fresh(void)
{
    EngEpoch e;
    if(!g->bound || !snapshot(&e,0) || !same_epoch(&e,&g->epoch)) {
        g->bound=0; disarm(); return 0;
    }
    return 1;
}
static int rpc(unsigned op,unsigned value,int32_t *native)
{
    int32_t s;unsigned tentative;
    if(!fresh()) return 0;
    tentative=op==3&&!g->uncertain;
    if(op==3){g->uncertain=1;__asm__ __volatile__("":::"memory");}
    s=svc(RV_RPC8,op,value,0,0,0,0,&io.rpc);
    if(op==3) {
        if(io.rpc.detail==1)g->write_started=1;
        else if(tentative&&!g->write_started)g->uncertain=0;
    }
    if(s!=RV_OK || !fresh()) return 0;
    if(op>=2 && op<=4 && (io.rpc.native_result<0 || io.rpc.native_result>65535)) return 0;
    *native=io.rpc.native_result; return 1;
}
static int expect(unsigned op,unsigned value,unsigned expected)
{ int32_t n; return rpc(op,value,&n) && (uint32_t)n==expected; }
static int t_read(void)
{ int32_t n; int ok=expect(4,b16(g->data.map+28),b16(g->data.map+28)) && rpc(2,b16(g->data.map+30),&n);
  t_seen=ok?n:-1; return ok?n:-1; }
static int write_word(unsigned value)
{
    if(g->view_lost&&!g->uncertain)return 0;
    /* The RPC boundary marks uncertainty and records an actual W send. */
    if(!expect(3,value,value)) return 0;
    if(w_count!=65535) w_count++;
    return 1;
}
void eng_apply_witness(uint32_t *t,uint32_t *w){if(t)*t=(uint32_t)t_seen;if(w)*w=w_count;}
static int t_store(unsigned value)
{ return write_word(value) && expect(2,b16(g->data.map+30),value); }
static int begin(void) { int32_t n; return rpc(1,0,&n); }
static int end(void)
{
    int32_t status;
    /* Cleanup may follow an epoch change. The dispatcher still validates the
     * live code lease and transaction owner; it must never resume W here. */
    status=svc(RV_RPC8,5,0,0,0,0,0,&io.rpc);
    if(status!=RV_OK) {
        /* op 5 closes its token even when the write result is uncertain.
         * Keep only that identity so a fresh, fully verified compensation
         * can run. Stale/owner/transport cleanup failures still unbind. */
        if(status!=RV_UNCERTAIN)g->bound=0;
        return 0;
    }
    return 1;
}
static EngStatus failure(void) { return g->uncertain?ENG_UNCERTAIN:(!g->bound?ENG_STALE:ENG_IO); }
static void publish(void)
{
    volatile EngGrain *r=g->port.grain;
    if(g->port.commit_grain)g->port.commit_grain(g->port.user,g->current.identity[33],(g->live[1]&ENG_GRAIN)&&!g->uncertain);
    if(!r) return;
    disarm(); r->boot=g->epoch.boot; r->heap=g->epoch.heap; r->link=g->epoch.link;
    r->unit=g->epoch.unit; r->settings=g->epoch.settings; r->mode=g->epoch.mode;
    r->recipe=(uint32_t)g->live[1]<<8 | g->current.identity[33];
    __asm__ __volatile__("":::"memory");
    if((g->live[1]&ENG_GRAIN) && !g->uncertain) r->armed=1;
}
EngStatus eng_init(const uint8_t *image,uint32_t length,const EngPort *port)
{
    EngEpoch e; RvUnitInfo u;
    if(!g || !port || !port->call || g->busy || g->uncertain || g->committed || eng_data_accept(port->gated)!=ENG_OK) return ENG_REJECTED;
    clear(g,sizeof(*g)); g->port=*port;
    if(!snapshot(&e,&u)) return ENG_STALE;
    if(eng_data_validate(image,length,&u,&g->data)!=ENG_OK) return ENG_REJECTED;
    g->epoch=e; g->ready=g->bound=1;g->tweak.v[0]=100;
    copy(g->stock,eng_entry(&g->data,0),552); copy(g->live,g->stock,552);
    g->current.unit=g->data.unit;g->current.slot=4;
    eng_identity(eng_record(&g->data,4),g->current.identity);
    g->stage=ENG_STAGE_IDLE;
    return g->bound?ENG_OK:ENG_STALE;
}
static EngStatus __attribute__((noinline)) project_compute(const EngRecipeRef *r,const UvLevels *levels,uint8_t out[552])
{
    const uint8_t *record,*base;uint8_t id[49];
    if(!r||!levels||!out||r->unit!=g->data.unit||r->slot<1||r->slot>8)return ENG_REJECTED;
    record=eng_record(&g->data,r->slot);eng_identity(record,id);
    if(!record[1]||!equal(id,r->identity,49)||
       kv_data_request(&g->data.knobs,g->data.unit,r->slot,levels,&g->work.request))return ENG_REJECTED;
    if(r->effect){
        const uint8_t *effect=fx_entry(&g->data.view,r->effect-1u);
        if(!effect||effect[0]!=r->slot||!(fx_unit_mask(&g->data.view,effect)>>g->data.unit&1u)||
           !equal(effect+4,r->effect_crc,4)||fx_expand(&g->data.view,r->effect-1u,g->work.base)!=GXR2_OK)return ENG_REJECTED;
    }else{
        if(!equal(r->effect_crc,"\0\0\0\0",4))return ENG_REJECTED;
        base=eng_entry(&g->data,eng_meta_record(&g->data,r->slot)[24]);
        if(!base)return ENG_REJECTED;
        copy(g->work.base,base,552);
    }
    return kv_apply_work(g->stock,g->work.base,&g->work.request,out,&g->work.stats,&g->work)?ENG_REJECTED:ENG_OK;
}
static EngStatus compute(const EngRecipeRef *r,const UvLevels *levels,uint8_t wb[2])
{
    unsigned held=g->busy;EngStatus status;const uint8_t *record;
    g->busy=1;status=project_compute(r,levels,g->staging);g->busy=(uint8_t)held;
    if(status!=ENG_OK)return status;
    record=eng_record(&g->data,r->slot);
    wb[0]=(uint8_t)((int)(int8_t)record[49]+9);wb[1]=(uint8_t)((int)(int8_t)record[50]+9);
    return ENG_OK;
}
EngStatus eng_project_compute(unsigned slot,const UvLevels *levels,uint8_t out[552])
{
    EngRecipeRef ref={0};EngStatus status;
    if(!g->ready||g->busy||slot<1||slot>8||!out)return ENG_REJECTED;
    ref.unit=g->data.unit;ref.slot=(uint8_t)slot;eng_identity(eng_record(&g->data,slot),ref.identity);
    g->busy=1;status=project_compute(&ref,levels,out);g->busy=0;
    return status;
}
EngStatus eng_project_preview(unsigned slot,const UvLevels *levels)
{if(slot<1||slot>8)return ENG_REJECTED;return eng_preview_saved((uint8_t)slot,levels);}
static EngStatus deep(unsigned recovery)
{
    unsigned row,have=g->live[1]&ENG_CONTROL,want=g->staging[1]&ENG_CONTROL,changed=0;
    int32_t first; int ok=1; uint32_t address;
    for(row=0;row<9;row++) {
        const uint8_t *r=g->data.map+32+12*row;
        if(!equal(g->live+b16(r+6),g->staging+b16(r+6),b16(r+4))) changed|=1u<<row;
    }
    if(recovery)changed=511;
    if(g->t_pending&&!recovery)return ENG_REJECTED;
    if(!changed && !((have!=0)^(want!=0)) && g->t_checked)return ENG_OK;
    {
        unsigned first_apply=!g->t_checked;
        if(first_apply)g->t_pending=0;
        if(!begin())return failure();
        g->stage=ENG_STAGE_T;
        int actual=t_read();
        if(recovery?(actual!=0&&actual!=2):(actual!=(have?0:2))) {
            g->t_warn=1;g->t_pending=1;(void)end();return ENG_REJECTED;
        }
        g->t_pending=0;g->t_checked=1;
        if(recovery)have=(unsigned)(actual==0);
    }
    if(have && !t_store(2))ok=0;
    /* B5's adjacent byte is read from the actual live unit, not stock. */
    /* Re-read the live neighbour on every B5 write. A cached high byte can
     * belong to the previous unit. */
    if(changed&2u) g->neighbor_valid=0;
    if(ok && (changed&2u) && !g->neighbor_valid) {
        address=b32(g->data.map+24);
        if(!expect(4,address>>16,address>>16) || !rpc(2,address&65535,&first) ||
           (!recovery&&((unsigned)first>>8)!=g->live[114])) ok=0;
        else { g->neighbor=(uint8_t)first; g->neighbor_valid=1; }
    }
    if(ok) g->stage=ENG_STAGE_ROWS;
    for(row=0;ok && row<9;row++) {
        const uint8_t *r=g->data.map+32+12*row,*old=g->live+b16(r+6),*p=g->staging+b16(r+6);
        unsigned bytes=b16(r+4); int i;
        if(!(changed&(1u<<row))) continue;
        address=b32(r); i=-(int)(address&1u);
        if(!expect(4,address>>16,address>>16) || !rpc(2,(address&65535)&65534,&first) ||
           (!recovery&&(i ? ((unsigned)first&255)!=old[0] : (unsigned)first!=b16(old)))) { ok=0; break; }
        for(;i<(int)bytes;i+=2) {
            unsigned value=(i<0?(unsigned)first>>8:p[i])*256u;
            value|=i+1<(int)bytes?p[i+1]:g->neighbor;
            if(!write_word(value)) { ok=0; break; }
        }
        if(ok&&recovery) {
            uint32_t page=address>>16;
            if(!expect(4,page,page)){ok=0;break;}
            for(i=-(int)(address&1u);i<(int)bytes;i+=2) {
                uint32_t at=(address&~1u)+(unsigned)(i+(int)(address&1u));
                unsigned value=(i<0?(unsigned)first>>8:p[i])*256u;
                value|=i+1<(int)bytes?p[i+1]:g->neighbor;
                if(at>>16!=page) {
                    page=at>>16;
                    if(!expect(4,page,page)){ok=0;break;}
                }
                if(!expect(2,at&65535,value)){ok=0;break;}
            }
        }
    }
    if(ok && want) { g->stage=ENG_STAGE_T; if(t_read()!=2 || !t_store(0)) ok=0; }
    if(ok&&recovery&&t_read()!=(want?0:2))ok=0;
    if(!end()) ok=0;
    return ok?ENG_OK:failure();
}
static void make_plan(const EngRecipeRef *ref,const uint8_t wb[2],uint32_t token,RvSettingsPlan *p)
{
    ENG_PLAN_COLOUR
    ENG_PLAN_BW_TE
    const uint8_t *r=eng_record(&g->data,ref->slot); const uint16_t *offsets;
    unsigned i,n=r[3]==4?13:r[3]==3?2:r[3]==6?4:0;
    offsets=r[3]==4?colour:r[3]==3?bw:te;
    clear(p,sizeof(*p)); p->header.version=1; p->header.bytes=sizeof(*p); p->settings_token=token;
    for(i=0;i<n;i++) { p->writes[i].offset=offsets[i]; p->writes[i].value=r[36+i]; }
    p->writes[n].offset=ENG_OFF_WB0; p->writes[n++].value=wb[0];
    p->writes[n].offset=ENG_OFF_WB1; p->writes[n++].value=wb[1];
    p->writes[n].offset=ENG_OFF_RECIPE; p->writes[n++].value=r[3]; p->count=n;
}
/* GXR2 v3 with one slot per unit (g173). Bytes 0..7 and the CRC-32 at 36..39 keep the g172 grammar,
 * so g172 still calls the tail its own (and replaces it) instead of refusing to write.
 *   5,6    recipe code and unit saved last (only for that grammar)
 *   8..30  three unit slots as one bit stream from bit 64, MSB first, per unit: 8-bit code (0 = no
 *          memory), 8-bit Amount, nine 5-bit levels (controls 1..9, level+9); the last bit is zero
 *   31..35 first five bytes of this DAT's header identity (any new DAT forgets)
 * A g172 record (one unit, ten int16 levels, eight identity bytes) is read as the slot of its unit.
 * Every field is built from shifts, so the layout does not depend on the host byte order. */
enum { MEM_TAG=31 };
/* The 33 slot values f[11*unit+i] (i=0 code, 1 Amount, 2..10 levels+9) to and from bytes 8..30. */
static void __attribute__((noinline)) mem_stream(uint8_t *p,uint16_t *f,unsigned write)
{
    unsigned i,o=8,nb=0,acc=0,w,z,wide=1;
    for(i=0;i<33;++i){
        w=i%11==0?(wide?11u:8u):i%11==1?8u:5u;
        if(write){acc=acc<<w|f[i];nb+=w;while(nb>=8){nb-=8;z=(uint8_t)(acc>>nb);if(o<31)p[o]=z;else{unsigned a=z/3u;p[5]=(uint8_t)(a<8?a+1:a<56?a+56:a+72);p[6]=(uint8_t)(z%3u);}++o;acc&=(1u<<nb)-1u;}}
        else{while(nb<w){z=p[5];z=z<9?z-1:z<112?z-56:z-72;acc=acc<<8|(o<31?p[o]:3u*z+p[6]);++o;nb+=8;}nb-=w;f[i]=(uint16_t)(acc>>nb);acc&=(1u<<nb)-1u;}
    }
    if(write&&nb)p[o]=(uint8_t)(acc<<(8-nb));
}
/* One slot from a code and ten levels. The levels were checked by kv_data_request (or came with a
 * valid g172 record) and the decoder checks them again, so the packing only masks them to their field. */
static void __attribute__((noinline)) mem_set(uint16_t *s,unsigned code,const int16_t *v)
{
    unsigned c;
    s[0]=(uint16_t)code;s[1]=(uint8_t)v[0];
    for(c=1;c<10;++c)s[c+1]=(uint8_t)((v[c]+9)&31);
}
static void mem_seal(uint8_t *p)
{uint32_t crc=eng_crc(p,36);unsigned i;for(i=0;i<4;++i)p[36+i]=(uint8_t)(crc>>(24-8*i));}
#if USER_SLOTS_R4
/* 5 not ours, unknown, or an incompatible version.
 * 3 is only a retained older catalogue. 1 is this catalogue, or a catalogue
 * that names this memory tag as an ancestor. A match loads the slots. The
 * next save retags them. The engine compares the declared bytes.
 * Current identity and a declared ancestor share the version and spill checks. */
static int __attribute__((noinline)) ancestor_declared(const uint8_t tag[5])
{
    const uint8_t *image=g->data.image;unsigned n,i;
    if(!image||g->data.length<256)return 0;
    n=image[228];
    if(!n||n>2)return 0;
    for(i=0;i<n;++i)if(equal(image+229+5u*i,tag,5))return 1;
    return 0;
}
#else
/* 5 not ours, unknown, or an incompatible version.
 * 3 is only a retained older catalogue. 1 is this catalogue's wide record. */
#endif
static int migration_tag(const uint8_t *tag)
{
    static const uint8_t known[][5]={
        ENG_MIGRATION_TAG_ROWS
    };
    unsigned i;
    for(i=0;i<sizeof known/sizeof known[0];++i)if(equal(tag,known[i],5))return 1;
    return 0;
}
static unsigned __attribute__((noinline)) mem_kind(const uint8_t *p)
{
    if(!memory_owned(p,eng_crc(p,36)))return 5;
#if USER_SLOTS_R4
    if(!equal(p+MEM_TAG,g->data.image+20,5)&&!ancestor_declared(p+MEM_TAG))
        return migration_tag(p+MEM_TAG)?3u:5u;
#else
    if(!equal(p+MEM_TAG,g->data.image+20,5))return migration_tag(p+MEM_TAG)?3u:5u;
#endif
    if(p[4]!=MEMORY_VERSION||p[5]>157||(p[5]==157&&p[6]))return 5;
    return 1;
}
static unsigned __attribute__((noinline)) mem_load(uint8_t *p,uint16_t *f)
{
    unsigned kind=mem_kind(p);
    clear(f,66);
    if(kind==1)mem_stream(p,f,0);
    return kind;
}
/* p holds the stored tail on entry and the record to store on exit: only the slot of this unit changes. */
static void __attribute__((noinline)) memory_build(uint8_t p[40],const EngRecipeRef *r,const UvLevels *t,unsigned user)
{
    uint16_t f[33];unsigned u=g->data.unit,code=user?(unsigned)MEMORY_USER_FIRST+user-1u:
        r->effect?(unsigned)MEMORY_FX_FIRST+r->effect-1u:r->slot;
    (void)mem_load(p,f);mem_set(f+11u*u,code,t->v);
    clear(p,40);copy(p,"GXR2",4);p[4]=MEMORY_VERSION;p[5]=4;p[6]=(uint8_t)u;p[7]=1;
    mem_stream(p,f,1);copy(p+MEM_TAG,g->data.image+20,5);mem_seal(p);
}
/* RV_SETTINGS op 4 reads the record into io.request; op 5 stores the record
 * of (r,t,user) after merging it into the record read just before. Both run
 * under the op 1 token held in io.info. */
static int32_t memory_op(unsigned op,const EngRecipeRef *r,const UvLevels *t,unsigned user)
{
    RvSettingsRecord *m=&io.request.record;int32_t s;
    clear(m,sizeof(*m));m->header.version=1;m->header.bytes=sizeof(*m);
    m->settings_token=io.info.token;m->settings_epoch=io.info.settings_epoch;
    if(op==5){
        s=svc(RV_SETTINGS,4,0,0,m,sizeof(*m),0,&io.reply);if(s!=RV_OK)return s;
        memory_build(m->record,r,t,user);
    }
    return svc(RV_SETTINGS,op,0,0,m,sizeof(*m),0,&io.reply);
}
static int32_t settings_info(void)
{
    clear(&io.info,sizeof(io.info));io.info.header.version=1;io.info.header.bytes=sizeof(io.info);
    return svc(RV_SETTINGS,1,0,0,&io.info,sizeof(io.info),0,&io.reply);
}
static int32_t settings_release(void)
{return svc(RV_SETTINGS,3,io.info.token,0,0,0,0,&io.reply);}
/* read_record: also read the remembered settings record into io.request (first H01). */
static EngStatus settings_match(unsigned *different,unsigned read_record)
{
    uint8_t wb[2];const uint8_t *settings;EngStatus status;unsigned i;
    *different=0;status=compute(&g->current,&g->tweak,wb);
    if(status!=ENG_OK)return status;
        status=mapped(settings_info());
    if(status!=ENG_OK)return status;
    if(io.info.header.version!=1||io.info.header.bytes!=sizeof(io.info)||io.info.header.flags||!io.info.token||
       io.info.length<ENG_SETTINGS_SPAN||io.info.settings_epoch!=g->epoch.settings||!fresh())status=ENG_STALE;
    else {
        settings=eng_wire_pointer(io.info.address);
        if(!settings)status=ENG_STALE;
        else {
            make_plan(&g->current,wb,io.info.token,&io.request.plan);
            for(i=0;i<io.request.plan.count;++i)
                if(settings[io.request.plan.writes[i].offset]!=io.request.plan.writes[i].value)*different=1;
            if(read_record)(void)memory_op(4,0,0,0);
        }
    }
    {int32_t released=settings_release();
     if(released!=RV_OK&&status==ENG_OK)status=mapped(released);}
    return status;
}
/* R1/P1-01: a refused change leaves the previous complete state in effect:
 * the unit holds g->live and S was not written. Re-arm its grain. */
static EngStatus refused(unsigned stage,unsigned pending)
{
    g->s_refused=1;
    g->stage=(uint8_t)stage;g->settings_pending=(uint8_t)pending;
    if(g->committed&&!g->settings_pending)publish();
    return ENG_REJECTED;
}
/* The stock lock was busy at S after this change wrote the unit: write and
 * read back the previous rows and T (S is untouched), then refuse. */
static EngStatus restore_previous(unsigned stage,unsigned pending)
{
    if(!g->live_verified){g->snapshot_fault=g->uncertain=1;return ENG_UNCERTAIN;}
    if(w_count){copy(g->staging,g->live,552);if(deep(1)!=ENG_OK){
        g->snapshot_fault=g->uncertain=1;return ENG_UNCERTAIN;}}
    g->uncertain=g->write_started=0;
    return refused(stage,pending);
}
static EngStatus live_check(int *,unsigned capture);
static EngStatus capture_previous(void)
{
    ENG_ROW_AT
    int mismatch=0;unsigned row;
    if(live_check(&mismatch,1)!=ENG_OK)goto failed;
    /* A boot may hold stock rows with T=0. Validate observed row structure
     * independently from the target recipe's T/C/D relationship. */
    for(row=0;row<10;++row)if(!fx_row_valid(g->live+at[row],row,0))goto failed;
    if(live_check(&mismatch,0)!=ENG_OK||mismatch||!fresh()||g->view_lost||!eng_settings_owned())goto failed;
    for(row=0;row<9;++row){
        const uint8_t *r=g->data.map+32+12*row;uint32_t crc=eng_crc(g->live+b16(r+6),b16(r+4));
        unsigned field=b16(r+8);
        g->live[field]=(uint8_t)(crc>>24);g->live[field+1]=(uint8_t)(crc>>16);
        g->live[field+2]=(uint8_t)(crc>>8);g->live[field+3]=(uint8_t)crc;
    }
    g->live_verified=1;return ENG_OK;
 failed:
    g->snapshot_fault=g->uncertain=1;return ENG_UNCERTAIN;
}
#ifndef G179_COPYRIGHT_NAME
#define G179_COPYRIGHT_NAME 0
#endif
static int copyright_store(const uint8_t text[47])
{
    RvCopyrightSlot slot; unsigned i;
    clear(&slot,sizeof(slot));
    slot.header.version=1; slot.header.bytes=sizeof(slot);
    slot.settings_token=io.info.token; slot.settings_epoch=io.info.settings_epoch;
    for(i=0;i<47;++i) slot.text[i]=text[i];
    return svc(RV_SETTINGS,7,0,0,&slot,sizeof(slot),0,&io.reply);
}
/* Menu order is Amt, Cont, High, Shad, Fade, Satu, Warm, Tint, Splt, Filt.
 * Amount is tenths (0..15). Signed levels are stored as value+9 (0..18).
 * A control this recipe does not offer is '-'. */
static void __attribute__((noinline)) copyright_tweaks(const EngRecipeRef *r,const UvLevels *t,uint8_t out[10])
{
    unsigned i;
    for(i=0;i<10;++i){
        KvDataItem item; int n,lim;
        if(kv_data_find(&g->data.knobs,g->data.unit,r->slot,i,&item)){out[i]='-';continue;}
        n=i?(int)t->v[i]+9:(int)t->v[i]/10;
        lim=i?18:15;
        if(n<0)n=0;
        if(n>lim)n=lim;
        out[i]=(uint8_t)(n<10?'0'+n:'A'+(n-10));
    }
}
static void copyright_sentence(const EngRecipeRef *r,const UvLevels *t,uint8_t out[47])
{
    unsigned i,pos;
    const uint8_t *id=g->data.image+20;
    static const char hex[]="0123456789abcdef";
    const char *unit=g->data.unit==0?"50":g->data.unit==1?"28":"MT";
    for(i=0;i<47;++i)out[i]=0;
    pos=r->effect?r->effect+4u:r->slot;
    out[0]='G';out[1]='X';out[2]='R';out[3]='1';out[4]=' ';
    for(i=0;i<5;++i){out[5+2*i]=(uint8_t)hex[id[i]>>4];out[6+2*i]=(uint8_t)hex[id[i]&15];}
    out[15]=' ';out[16]=(uint8_t)unit[0];out[17]=(uint8_t)unit[1];out[18]=' ';
    out[19]=(uint8_t)('0'+(pos/10u)%10u);out[20]=(uint8_t)('0'+pos%10u);
    out[21]=' ';
    copyright_tweaks(r,t,out+22);
}
/* Read the copyright member only. A matching read is not a colour, settings,
 * white-balance or whole-transaction proof. */
static int copyright_matches(const uint8_t expect[47])
{
    const uint8_t *settings=eng_wire_pointer(io.info.address);
    return settings&&io.info.length>=ENG_COPYRIGHT_AT+47u&&equal(settings+ENG_COPYRIGHT_AT,expect,47);
}
/* 1: stored and the 47 bytes match, or legitimately skipped. 0: a required
 * store did not happen, or the service returned success while the bytes differ.
 * The first call captures the preimage. A later call in the same transaction
 * must not replace that preimage with text this transaction already wrote. */
static int copyright_publish(const EngRecipeRef *r,const UvLevels *t,uint8_t saved[47],int *wrote)
{
    const uint8_t *settings; uint8_t text[47]; unsigned i;
    settings=eng_wire_pointer(io.info.address);
    if(!io.info.token||!settings||io.info.length<ENG_COPYRIGHT_AT+47u)return 0;
    if(!*wrote){for(i=0;i<47;++i)saved[i]=settings[ENG_COPYRIGHT_AT+i];}
    if(saved[0]&&!(saved[0]=='G'&&saved[1]=='X'&&saved[2]=='R'&&saved[3]=='1'))return 1;
    copyright_sentence(r,t,text);
    if(copyright_store(text)!=RV_OK)return 0;
    /* The service status is not the 47 bytes. A later check can still fail. */
    *wrote=1;
    if(!copyright_matches(text))return 0;
    return 1;
}
/* Undo only while this call still holds the token. 1 means the 47 preimage
 * bytes were read back, or there was nothing to undo. The service status
 * alone does not count. */
static int copyright_undo(const uint8_t saved[47],int *wrote)
{
    if(!*wrote)return 1;
    if(!io.info.token||!fresh()||!eng_settings_owned())return 0;
    if(copyright_store(saved)!=RV_OK||!copyright_matches(saved))return 0;
    *wrote=0;
    return 1;
}
static void release_lost(EngStatus *status)
{
    g->uncertain=1;
    g->bound=0;
    *status=ENG_UNCERTAIN;
}
/* choice: a user choice (select, Default, preview). Boundary re-applies of
 * the current state and recoveries are not choices. */
static EngStatus apply_impl(const EngRecipeRef *r,const UvLevels *t,unsigned recovery,unsigned confirm,unsigned choice)
{
    EngStatus status; uint8_t wb[2]; int acquired=0; unsigned stage=g->stage,pending=g->settings_pending,change=0;
    uint8_t saved_copy[47]; int copyright_wrote=0;
    volatile uint32_t *word=eng_colour_guard();
    w_count=0;t_seen=-1;
    if(g->uncertain&&!recovery) return ENG_UNCERTAIN;
    if(!g->ready || !g->bound) return ENG_STALE;
    if(g->busy) return ENG_REJECTED;
    g->busy=1;
    recovery|=!!(*word&12u);
    expire_previous();
    status=compute(r,t,wb); if(status!=ENG_OK) goto done;
    if(!fresh()) { status=ENG_STALE; goto done; }
    g->s_refused=0;
    disarm(); g->stage=ENG_STAGE_IDLE;
    if(!recovery&&(!g->baseline||!g->live_verified)){status=capture_previous();if(status!=ENG_OK)goto done;}
        status=mapped(settings_info());
    if(status!=ENG_OK) goto done;
    acquired=1;
    if(io.info.header.version!=1 || io.info.header.bytes!=sizeof(io.info) || io.info.header.flags || !io.info.token ||
       io.info.length<ENG_SETTINGS_SPAN || io.info.settings_epoch!=g->epoch.settings || !fresh()) { status=ENG_STALE; goto done; }
    make_plan(r,wb,io.info.token,&io.request.plan);
    {
        const uint8_t *settings=eng_wire_pointer(io.info.address); unsigned i,count=0;
        if(!settings) { status=ENG_STALE; goto done; }
        for(i=0;i<io.request.plan.count;i++) if(settings[io.request.plan.writes[i].offset]!=io.request.plan.writes[i].value)
            io.request.plan.writes[count++]=io.request.plan.writes[i];
        io.request.plan.count=count;
    }
    /* R1/P1-01: a change is all or nothing-> Before any unit write, check the
     * stock lock once with IRQs off (op 6, no write). Busy refuses it. */
    change=choice&&!(g->committed&&equal(r,&g->current,sizeof(*r))&&equal(t,&g->tweak,sizeof(*t)));
    if(change&&io.request.plan.count&&(g->s_busy||
       svc(RV_SETTINGS,6,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply)==RV_BUSY)){
        g->s_busy=1;status=refused(stage,pending);goto done;}
    /* P1-01: an unverified boot has no trusted row ledger: write and read
     * back all nine rows and T, as a recovery does. */
    /* H52 must block capture before the first possible W, including S and
     * preview failures. Only a complete transaction clears this latch. */
    *word|=12u;__asm__ __volatile__("":::"memory");
    status=deep(recovery|!g->baseline);
    if(status!=ENG_OK) { if(g->t_warn&&!g->t_warn_slot)g->t_warn_slot=r->slot; goto done; }
    if(!fresh()) { status=failure(); goto done; }
    if(!eng_settings_owned()){g->settings_pending=1;goto settings_done;}
    g->settings_pending=0;
    if(io.request.plan.count) {
        /* P2-02: at most one lock try per key press while the lock is busy. */
        if(g->s_busy)goto busy;
        g->stage=ENG_STAGE_SETTINGS; g->uncertain=1;
        status=mapped(svc(RV_SETTINGS,2,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply));
        if(status!=ENG_OK || !fresh()) {
            /* The stock lock is busy (zero S writes), or the view is no
             * longer ours: S stays pending for the next boundary. */
            if(fresh()&&io.reply.status==RV_BUSY){g->s_busy=1;goto busy;}
            if(fresh()&&io.reply.status==RV_STALE&&!eng_settings_owned()){g->settings_pending=1;goto settings_done;}
            status=failure();goto done;
        }
    }
    if(!eng_settings_owned()){g->settings_pending=1;goto settings_done;}
    g->stage=ENG_STAGE_PREVIEW;
    status=mapped(svc(RV_PREVIEW,1,0,0,0,0,0,&io.reply));
    if(status!=ENG_OK || !fresh()) {
        if(io.reply.status==RV_STALE&&fresh()&&!eng_settings_owned()){g->settings_pending=1;goto settings_done;}
        status=failure();goto done;
    }
    /* A user choice is now fully in effect, or this same state still has an
     * unstored record: store it. Busy or stale keeps the old record and
     * leaves this one for the next boundary. */
    if((g->memory_want||!g->memory_blocked)&&(g->memory_want||(g->memory_dirty&&equal(r,&g->current,sizeof(*r))&&equal(t,&g->tweak,sizeof(*t))))){
        /* R1/P2-02: the record also gets one lock try per key press. */
        if(g->s_busy)g->memory_dirty=1;
        else {
            int32_t m=memory_op(5,r,t,g->memory_want?g->memory_user:g->current_user);
            /* P1-02: an unknown tail is never overwritten; stop retrying-> */
            g->memory_dirty=m!=RV_OK;g->memory_blocked=m!=RV_OK&&m!=RV_BUSY;
            g->memory_error=m==RV_OK?0:m==RV_BUSY?1:m==RV_CONFLICT?2:3;g->s_busy|=m==RV_BUSY;
            if(m==RV_OK){g->saved.ref=*r;g->saved.levels=*t;g->saved.user=g->memory_want?g->memory_user:g->current_user;g->memory_result=1;}
        }
    }
 settings_done:
    /* Publish while the token is still held. A required store that fails
     * is uncertain: do not report success and do not start another acquire. */
    if(status==ENG_OK&&!g->settings_pending&&fresh()&&eng_settings_owned()){
        if(!copyright_publish(r,t,saved_copy,&copyright_wrote)){
            /* The store may already have landed. Put the preimage back on
             * this token and read all 47 bytes before releasing it. Colour
             * and settings written above are a different member: matching
             * copyright does not finish the transaction or take a new token. */
            if(copyright_wrote)(void)copyright_undo(saved_copy,&copyright_wrote);
            copyright_wrote=0;
            g->uncertain=1;
            status=ENG_UNCERTAIN;
            if(acquired){
                if(settings_release()!=RV_OK)status=ENG_UNCERTAIN;
                acquired=0;
            }
            g->bound=0;
            goto finish;
        }
    }
    if(status==ENG_OK&&copyright_wrote&&(!fresh()||!eng_settings_owned())){
        if(!copyright_undo(saved_copy,&copyright_wrote))copyright_wrote=0;
        release_lost(&status);
    }
    if(acquired){
        int32_t released=settings_release();
        int committed_ok=status==ENG_OK;
        int published=copyright_wrote;
        acquired=0;copyright_wrote=0;
        if(released!=RV_OK){
            /* One probe under the token this call already holds. Success
             * means release never took that token. The probe is a store, not
             * a permission check, and it must not acquire another token.
             * A byte match is still only the copyright member: colour and
             * settings stay as the failed transaction left them. Finish on
             * this same token; do not fall into done, which would acquire
             * again while this ownership is still alive. */
            if(published&&io.info.token&&fresh()&&eng_settings_owned()&&
               copyright_store(saved_copy)==RV_OK&&copyright_matches(saved_copy)){
                int32_t closed;
                /* Copyright is back. Colour and settings were written by
                 * this attempt and were not part of the probe, so the
                 * transaction stays uncertain and the guard stays up.
                 * Release only this token. */
                g->uncertain=1;
                status=ENG_UNCERTAIN;
                closed=settings_release();
                acquired=0;copyright_wrote=0;
                /* Drop the epoch binding after this token is closed so the
                 * caller's compensation cannot apply for a second token. */
                g->bound=0;
                if(closed!=RV_OK)status=ENG_UNCERTAIN;
                goto finish;
            }
            release_lost(&status);goto done;
        }
        if(!fresh()){
            /* Release returned success, then the epoch check failed.
             * Colour and a successful copyright store already committed.
             * Record that recipe and stop. Do not store on the dropped token. */
            if(committed_ok){
                g->current=*r;g->tweak=*t;g->committed=1;
                g->list.applied=r->slot;g->list.cursor=r->slot;
            }
            release_lost(&status);goto done;
        }
        if(status!=ENG_OK){status=failure();goto done;}
    }else if(status!=ENG_OK){status=failure();goto done;}
    /* A full write read T back as its target: the T warning is resolved. */
    copy(g->live,g->staging,552);if(recovery|!g->baseline)g->t_warn=g->t_warn_slot=0;g->baseline=g->live_verified=1;
    /* A user choice records its state. Any other state change (baseline
     * cleanup, compensation) leaves the stored record as it is. */
    if(g->memory_want){g->current_user=g->memory_user;if(g->settings_pending)g->memory_dirty=1;}
    else if(!equal(r,&g->current,sizeof(*r))||!equal(t,&g->tweak,sizeof(*t)))g->memory_dirty=g->current_user=0;
    g->current=*r; g->tweak=*t;g->s_unwritten=g->settings_pending;
    g->committed=1; g->list.applied=r->slot; g->list.cursor=r->slot;
    g->previewing=(uint8_t)!confirm;
    if(confirm){g->confirmed=*r;g->confirmed_tweak=*t;g->confirmed_valid=1;g->confirmed_user=g->current_user;}
    g->stage=confirm?ENG_STAGE_COMMITTED:ENG_STAGE_BROWSING; __asm__ __volatile__("":::"memory");
    g->uncertain=g->write_started=g->snapshot_fault=0;
    if(!g->settings_pending){*word&=~12u;publish();} status=ENG_OK;
    goto done;
 busy:
    /* R1/P1-01: S cannot be written under the busy stock lock. A change goes
     * back to the previous complete state and is refused; a recovery fails
     * (ERR, as in g138); a boundary re-apply of the current state keeps S
     * pending, as before. */
    if(change)status=restore_previous(stage,pending);
    else if(recovery){g->s_refused=1;status=failure();}
    else{g->settings_pending=1;goto settings_done;}
 done:
    /* Early failures still hold the token. Undo first, then release once.
     * A non-OK release is uncertain on this ABI and must not store again. */
    if(copyright_wrote&&status!=ENG_OK){
        if(!copyright_undo(saved_copy,&copyright_wrote)){copyright_wrote=0;release_lost(&status);}
    }
    if(acquired){
        int32_t released=settings_release();
        acquired=0;copyright_wrote=0;
        if(released!=RV_OK)release_lost(&status);
    }
 finish:
    if(status!=ENG_OK && g->committed) g->list.cursor=g->current.slot;
    expire_previous();g->busy=0; return status;
}
static EngStatus recover_confirmed(void)
{
    EngRecipeRef r={0};UvLevels t={{100}};EngStatus status;unsigned fallback=g->uncertain||g->snapshot_fault;
    if(!fallback&&g->confirmed_valid){r=g->confirmed;t=g->confirmed_tweak;g->memory_user=g->confirmed_user;}
    else {r.unit=g->data.unit;r.slot=4;eng_identity(eng_record(&g->data,4),r.identity);}
    /* Restoring the confirmed state is remembered; the 04 fallback is not. */
    g->memory_want=!fallback&&g->confirmed_valid;
    /* The live row ledger is invalid after a failed W. Rewrite and read back
     * all nine rows before clearing uncertainty or publishing a cursor. */
    {
        status=apply_impl(&r,&t,1,0,0);
        g->memory_want=0;
        /* One complete compensation pass. A failed pass keeps H52 latched. */
        if(status==ENG_OK&&fallback)g->confirmed_valid=0;
    }
    if(status==ENG_OK){g->previewing=0;g->stage=g->confirmed_valid?ENG_STAGE_COMMITTED:ENG_STAGE_IDLE;}
    return status==ENG_OK&&fallback?ENG_IO:status;
}
EngStatus eng_confirm_live(EngRecipeRef *r,UvLevels *t)
{
    if(g->uncertain)return ENG_UNCERTAIN;
    /* R1/P1-01: OK never confirms a state whose S is still pending-> */
    if(!g->ready||g->busy||g->s_unwritten||!g->baseline)return ENG_STALE;
    g->confirmed=g->current;g->confirmed_tweak=g->tweak;g->confirmed_valid=1;g->confirmed_user=g->current_user;
    g->previewing=0;g->stage=ENG_STAGE_COMMITTED;
    *r=g->current;*t=g->tweak;return ENG_OK;
}
EngStatus eng_apply(const EngRecipeRef *r,const UvLevels *t)
{
    EngStatus status;
    if(r&&t&&!g->busy&&!g->uncertain&&g->committed&&
       equal(r,&g->current,sizeof(*r))&&equal(t,&g->tweak,sizeof(*t))&&fresh()) {
        g->confirmed=*r;g->confirmed_tweak=*t;g->confirmed_valid=1;g->confirmed_user=g->current_user;g->previewing=0;
        g->stage=ENG_STAGE_COMMITTED;return ENG_OK;
    }
    status=apply_impl(r,t,0,1,1);
    if(status!=ENG_OK&&g->ready&&!g->busy&&g->uncertain)(void)recover_confirmed();
    return status;
}
EngStatus eng_preview_saved(uint8_t slot,const UvLevels *t)
{
    EngRecipeRef r={0};EngStatus status;
    if(!g->list.opened||slot<1||slot>g->list.rows)return ENG_REJECTED;
    r.unit=g->data.unit;r.slot=slot;eng_identity(eng_record(&g->data,slot),r.identity);
    g->memory_want=1;status=apply_impl(&r,t,0,0,1);g->memory_want=0;
    if(status==ENG_OK)return status;
    if(!g->uncertain)return status;
    g->list.warning=1;
    return recover_confirmed();
}
EngStatus eng_preview_effect(unsigned effect,const UvLevels *t)
{
    EngRecipeRef r={0};EngStatus status;const uint8_t *e;
    if(!g->list.opened||!effect)return ENG_REJECTED;
    e=fx_entry(&g->data.view,effect-1u);
    if(!e||!(fx_unit_mask(&g->data.view,e)>>g->data.unit&1u))return ENG_REJECTED;
    r.unit=g->data.unit;r.slot=e[0];r.effect=(uint16_t)effect;
    copy(r.effect_crc,e+4,4);eng_identity(eng_record(&g->data,r.slot),r.identity);
    g->memory_want=1;g->memory_user=0;status=apply_impl(&r,t,0,0,1);g->memory_want=0;
    if(status==ENG_OK||!g->uncertain)return status;
    g->list.warning=1;return recover_confirmed();
}
EngStatus eng_current(EngRecipeRef *r,UvLevels *t)
{
    if(g->uncertain) return ENG_UNCERTAIN;
    if(!r || !t) return ENG_REJECTED;
    if(!g->committed || !fresh()) return ENG_STALE;
    *r=g->current; *t=g->tweak; return ENG_OK;
}
EngStatus eng_metadata(uint8_t slot,int8_t min[8],int8_t max[8],int8_t def[8])
{
    const uint8_t *m; unsigned i;
    if(!g->ready || !fresh()) return ENG_STALE;
    if(!min || !max || !def || slot<1 || slot>16 || !eng_record(&g->data,slot)[1]) return ENG_REJECTED;
    m=eng_meta_record(&g->data,slot);
    for(i=0;i<8;i++) { min[i]=(int8_t)m[3*i]; max[i]=(int8_t)m[3*i+1]; def[i]=(int8_t)m[3*i+2]; }
    return ENG_OK;
}
int __attribute__((noinline,used)) eng_uncertain(void) { return g->uncertain!=0; }
int eng_write_started(void) { return g->write_started!=0; }
int eng_snapshot_failed(void) { return g->snapshot_fault!=0; }
void eng_require_recheck(void) { expire_previous();g->recheck=1; }
void eng_restore_cursor(void)
{
    g->list.cursor=g->committed?g->current.slot:4;
    g->list.applied=g->committed?g->current.slot:0;
}
EngStatus eng_display_current(EngRecipeRef *r,UvLevels *t)
{
    if(!g->committed||!r||!t)return ENG_STALE;
    *r=g->current;*t=g->tweak;return ENG_OK;
}
void eng_view_lost(unsigned lost) { if(lost)expire_previous();g->view_lost=(uint8_t)lost; }
unsigned eng_stage(void) { return g->stage; }
int eng_parameter_index(uint32_t id)
{ unsigned i; if(!g->ready || !id) return -1; for(i=0;i<8;i++) if(b32(g->data.ids+4*i)==id) return (int)i; return -1; }
const EngList *eng_list(void) { return &g->list; }
unsigned eng_visible_rows(void)
{
    unsigned slot,rows=0;
    if(!g->ready)return 0;
    for(slot=1;slot<=16;++slot) {
        const uint8_t *m=eng_meta_record(&g->data,slot);
        const uint8_t *d=g->data.pool+16+20*m[24];
        if(slot!=4 && d[0]!=4)rows=slot;
    }
    return rows && rows<4?4:rows;
}
static EngStatus validate_live(void);
static EngStatus boot_restore(void);
static int boot_s_valid(void);
static void accept_menu_preview(void)
{
    /* Native shutter exits can withdraw ADJ without H07. Re-entering the
     * constructor accepts the already verified live preview in that case. */
    if(g->previewing&&g->committed) {
        g->confirmed=g->current;g->confirmed_tweak=g->tweak;g->confirmed_valid=1;g->confirmed_user=g->current_user;
        g->previewing=0;g->stage=ENG_STAGE_COMMITTED;
    }
}
static EngStatus menu_list(void)
{
    unsigned slot,j;
    g->list.rows=(uint8_t)eng_visible_rows();
    if(!g->list.rows)return ENG_OK;
    for(slot=1;slot<=g->list.rows;slot++) {
        EngListRow *row=&g->list.row[slot-1]; const uint8_t *r=eng_record(&g->data,slot);
        clear(row,sizeof(*row)); row->occupied=r[1]; row->canonical_stock=(uint8_t)(slot==4);
        if(r[1]) { for(j=0;j<r[2];j++) row->ascii[j]=(char)r[4+j]; }
        else { row->ascii[0]=(char)('0'+slot/10); row->ascii[1]=(char)('0'+slot%10); }
    }
    g->list.warning=g->t_warn; g->list.opened=1;
    /* Cold boot is pure canonical stock 04; only a live commit owns another row. */
    g->list.cursor=g->confirmed_valid?g->confirmed.slot:g->committed?g->current.slot:4;
    return ENG_OK;
}
EngStatus eng_menu_open(void)
{
    EngStatus status;
    expire_previous();
    if(!g->ready||!fresh())return ENG_STALE;
    if(g->busy)return ENG_REJECTED;
    accept_menu_preview();
    g->list.rows=(uint8_t)eng_visible_rows();
    if(!g->list.rows)return ENG_OK;
    status=validate_live();
    if(status==ENG_OK&&!g->remember_checked)status=boot_restore();
    return status==ENG_OK?menu_list():status;
}
EngStatus eng_select(uint8_t slot)
{
    EngRecipeRef r={0}; UvLevels t={{100}}; EngStatus s;
    if(!g->list.opened) return ENG_STALE;
    if(slot<1||slot>8)return ENG_REJECTED;
    r.unit=g->data.unit; r.slot=slot; eng_identity(eng_record(&g->data,slot),r.identity);
    g->list.cursor=slot; s=eng_apply(&r,&t);
    if(s!=ENG_OK && g->committed) g->list.cursor=g->current.slot;
    return s;
}
EngStatus eng_select_saved(uint8_t slot,const UvLevels *t)
{
    EngRecipeRef r={0};EngStatus s;
    if(!g->list.opened||slot<1||slot>g->list.rows)return ENG_REJECTED;
    r.unit=g->data.unit;r.slot=slot;eng_identity(eng_record(&g->data,slot),r.identity);
    g->list.cursor=slot;s=eng_apply(&r,t);
    if(s!=ENG_OK&&g->committed)g->list.cursor=g->current.slot;
    return s;
}
EngStatus eng_restore_stock(void)
{
    EngRecipeRef r={0}; UvLevels zero={{100}};
    if(g->uncertain) return ENG_UNCERTAIN;
    if(!g->ready || !g->bound) return ENG_STALE;
    if(!g->committed) return ENG_OK;
    r.unit=g->data.unit; r.slot=4; eng_identity(eng_record(&g->data,4),r.identity);
    return eng_apply(&r,&zero);
}
void eng_menu_close(void) { expire_previous();g->list.opened=0; }
void eng_invalidate(void)
{ expire_previous();disarm(); g->bound=0; g->list.opened=0; g->neighbor_valid=0; }
static EngStatus rebind_impl(void)
{
    EngEpoch e;RvUnitInfo u;
    if(!g->ready||g->uncertain||!snapshot(&e,&u))return ENG_STALE;
    if(e.boot!=g->epoch.boot||e.heap!=g->epoch.heap||e.link!=g->epoch.link||
       e.unit!=g->epoch.unit)return ENG_STALE;
    g->epoch=e;g->bound=1;g->neighbor_valid=0;g->t_pending=0;g->s_busy=0;
    return ENG_OK;
}
EngStatus eng_rebind(void)
{
    EngStatus status;
    if(g->busy)return ENG_REJECTED;
    expire_previous();
    status=rebind_impl();return status;
}

EngStatus eng_check_settings(void)
{
    unsigned different,previewing=g->previewing,pending=g->settings_pending;EngStatus status;
    if(!g->ready||g->busy||!fresh())return ENG_STALE;
    if(g->uncertain)return ENG_UNCERTAIN;
    /* A refused choice preserves actual S, including through exit/reopen.
     * Only a new valid apply may resume automatic settings synchronization. */
    if(g->s_refused)return ENG_OK;
    /* An unverified boot keeps the user's native state until a real choice. */
    if(!g->committed&&!g->baseline)return ENG_OK;
    if(!eng_settings_owned()){if(!g->boot_committed)g->settings_pending=1;return ENG_OK;}
    g->settings_pending=0;
    status=settings_match(&different,0);if(status!=ENG_OK)return status;
    /* The first H01 publishes the committed BOOT state. A constructor
     * without a list does not create a pending apply or another preview. */
    if(g->boot_committed){
        if(different||pending)return ENG_STALE;
        g->boot_committed=0;
    }
    /* A legal boundary: an unstored record is retried by reapplying the state. */
    if(different||pending||(g->memory_dirty&&!g->memory_blocked&&!g->s_busy)) {
        EngRecipeRef ref=g->current;UvLevels tweak=g->tweak;
        status=apply_impl(&ref,&tweak,0,0,0);
        if(status!=ENG_OK) {
            if(g->uncertain&&g->write_started)status=recover_confirmed();
            else g->uncertain=0;
            return status;
        }
        g->previewing=(uint8_t)previewing;
        g->stage=previewing?ENG_STAGE_BROWSING:g->confirmed_valid?ENG_STAGE_COMMITTED:ENG_STAGE_IDLE;
    }
    return ENG_OK;
}

/* Read the T control and every owned byte; flag any difference from live. */
static EngStatus live_check(int *mismatch,unsigned capture)
{
    unsigned row;int32_t value;int actual,ok=1;
    if(!begin())return failure();
    actual=t_read();
    if(actual<0)ok=0;
    else if(capture){
        if(actual!=0&&actual!=2)ok=0;
        else {g->live[1]=(uint8_t)(actual==0?(ENG_AUX|ENG_CONTROL):0);g->live[445]=0;g->live[446]=(uint8_t)actual;}
    }else if((unsigned)actual!=b16(g->live+445))*mismatch=1;
    for(row=0;ok&&row<9;++row) {
        const uint8_t *r=g->data.map+32+12*row;uint8_t *p=g->live+b16(r+6);
        uint32_t address=b32(r),page=address>>16;unsigned bytes=b16(r+4);int i;
        if(!expect(4,page,page)){ok=0;break;}
        for(i=-(int)(address&1u);i<(int)bytes;i+=2) {
            uint32_t at=(address&~1u)+(unsigned)(i+(int)(address&1u));
            if(at>>16!=page){page=at>>16;if(!expect(4,page,page)){ok=0;break;}}
            if(!rpc(2,at&65535,&value)){ok=0;break;}
            if(capture){if(i>=0)p[i]=(uint8_t)((unsigned)value>>8);if(i+1<(int)bytes)p[i+1]=(uint8_t)value;}
            else{
                if(i>=0&&((unsigned)value>>8)!=p[i])*mismatch=1;
                if(i+1<(int)bytes&&((unsigned)value&255)!=p[i+1])*mismatch=1;
            }
        }
    }
    if(ok&&t_read()!=actual)ok=0;
    if(!end())ok=0;
    return ok?ENG_OK:failure();
}
/* Compare every owned byte at a new menu entry. Native capture can restore
 * unit rows without changing any resident epoch. */
static EngStatus validate_live(void)
{
    int mismatch=0;EngStatus status;
    /* Only a known recipe baseline can be checked or restored here. A
     * transaction-local initial snapshot must never become that ledger. */
    if(!g->baseline){expire_previous();g->recheck=0;return ENG_OK;}
    status=live_check(&mismatch,0);if(status!=ENG_OK)return status;
    if(mismatch) {
        status=recover_confirmed();
        if(status==ENG_OK)g->recheck=0;
        return status;
    }
    status=eng_check_settings();if(status!=ENG_OK)return status;
    g->recheck=0;return ENG_OK;
}
/* First menu entry of this boot only. Confirms the stock baseline
 * (Standard, WB 9/9, Body start settings, T 2, all nine rows stock) and, on
 * a whole valid record and a non-MY boot, offers that recipe: the cursor
 * stops on it with its values. Nothing is written here (P1-03 option B);
 * the user's OK applies it through the normal path.
 * g173: a boot whose BOOT already applied and verified a state has its baseline (rows, T and S
 * were read back); that state is a recipe whose T may be 0, so it is not checked against pure 04. */
static EngStatus boot_restore(void)
{
    int mismatch=0,valid;
    eng_read_saved();g->remember_checked=1;
    if(g->baseline)return ENG_OK;
    /* Establish active 04 independently. Native Vivid/WB is never 04. */
    if(settings_info()!=RV_OK)return ENG_OK;
    valid=io.info.token&&io.info.header.version==1&&io.info.header.bytes==sizeof(io.info)&&!io.info.header.flags&&boot_s_valid();
    if(settings_release()!=RV_OK||!valid)return ENG_OK;
    if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2){
        if(t_seen>=0&&t_seen!=2){g->t_warn=1;g->t_warn_slot=4;}
        return ENG_OK;
    }
    g->baseline=g->live_verified=1;return ENG_OK;
}
void eng_boot_source(unsigned my){g->boot_my=(uint8_t)(my!=0);}
const EngSavedSelection *eng_saved_selection(void)
{return g->memory_result==1?&g->saved:0;}
unsigned eng_active_code(void)
{return !g->committed?0:g->current_user?0x80u+g->current_user-1:g->current.effect?(unsigned)MEMORY_FX_FIRST+g->current.effect-1u:g->current.slot;}
unsigned eng_memory_result(void){return g->memory_result;}
unsigned eng_memory_error(void){return g->memory_error;}
unsigned eng_saved_code(void)
{return g->memory_result==1?(g->saved.user?0x80u+g->saved.user-1u:g->saved.ref.effect?(unsigned)MEMORY_FX_FIRST+g->saved.ref.effect-1u:g->saved.ref.slot):0;}
/* Recipe number whose apply was refused on an unexpected T control, or 0. */
unsigned eng_t_warn(void){return g->t_warn?g->t_warn_slot:0;}
void eng_memory_user(unsigned user){g->memory_user=(uint8_t)user;}
unsigned eng_current_user(void){return g->current_user;}
/* A new key press: the stock lock may be tried once more. */
void eng_key_begin(void){g->s_busy=0;}
/* R1/P1-01: a complete user choice is in effect (S written) but its record
 * is not stored. An S-pending state is not shown as unsaved. */
int eng_memory_pending(void){return g->memory_dirty&&!g->s_unwritten;}
unsigned eng_baseline(void){return g->baseline||g->committed;}
/* Image-lane query only. It makes no service call and changes no engine
 * state. Standard/WB fields alone also describe some fitted Looks. */
int eng_stock04_verified(void)
{
    unsigned i;
    if(!g||!g->ready||!g->bound||!g->baseline||!g->live_verified||g->busy||g->uncertain||g->snapshot_fault||
       g->current.slot!=4||g->current.effect||g->current_user||g->tweak.v[0]!=100)return 0;
    for(i=1;i<10;++i)if(g->tweak.v[i])return 0;
    return equal(g->live,g->stock,552);
}

EngStatus eng_retry_live(void)
{
    EngStatus status;
    if(g->snapshot_fault||(g->uncertain&&g->write_started))return ENG_UNCERTAIN;
    g->uncertain=0;
    status=eng_rebind();
    return status==ENG_OK?validate_live():status;
}

EngStatus eng_cursor(uint8_t slot)
{
    if(!g->list.opened||slot<1||slot>g->list.rows)return ENG_REJECTED;
    g->list.cursor=slot;return ENG_OK;
}

#include "eng_boot.inc.c"
