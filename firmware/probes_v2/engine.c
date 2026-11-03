#include "probes.h"
#ifndef PV_ENGINE
#error PV_ENGINE must select LIFE, NOTICE or VIEW
#endif
_Static_assert(PV_ENGINE>=PV_LIFE && PV_ENGINE<=PV_VIEW,"engine variant");
#ifndef PV_HOST
_Static_assert(sizeof(void *)==4 && sizeof(RvApi)==160,"target API layout");
#endif

static void clear(void *p,uint32_t n)
{ uint8_t *b=p; while (n--) *b++=0; }
static void copy(void *d,const void *s,uint32_t n)
{ uint8_t *a=d; const uint8_t *b=s; while (n--) *a++=*b++; }
static int same(const void *a,const void *b,uint32_t n)
{ const uint8_t *x=a,*y=b; while (n--) if (*x++!=*y++) return 0; return 1; }
static void *pointer(uint32_t address,uint32_t bytes)
{
#ifdef PV_HOST
    return pv_host_pointer(address,bytes);
#else
    (void)bytes; return (void *)(uintptr_t)address;
#endif
}
static uint32_t address(const void *p,uint32_t bytes)
{
#ifdef PV_HOST
    return pv_host_address(p,bytes);
#else
    (void)bytes; return (uint32_t)(uintptr_t)p;
#endif
}
static int inside(uint32_t base,uint32_t length,uint32_t p,uint32_t bytes)
{ return p>=base && bytes<=length && p-base<=length-bytes; }
static void header(void *buffer,uint32_t bytes)
{
    RvBufferHeader *h=buffer;
    clear(buffer,bytes); h->version=1; h->bytes=(uint16_t)bytes;
}
static int buffer_ok(const RvBufferHeader *h,uint32_t bytes)
{ return h->version==1 && h->bytes==bytes && !h->flags; }
static uint32_t crc_byte(uint32_t crc,uint8_t b)
{
    unsigned i;
    crc^=b;
    for (i=0;i<8;++i) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1u)));
    return crc;
}
uint32_t pv_crc32(const void *p,uint32_t bytes)
{
    const uint8_t *b=p; uint32_t crc=0xffffffffu;
    while (bytes--) crc=crc_byte(crc,*b++);
    return crc^0xffffffffu;
}
static uint32_t word_be(const uint8_t *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static char hex_digit(uint32_t n)
{ return (char)(n<10 ? '0'+n : 'A'+n-10); }
void pv_encode(uint32_t page,uint32_t sample,uint32_t session,uint32_t flags,
               uint32_t engine,const uint32_t *data,char rows[16][13])
{
    uint32_t words[16],crc=0xffffffffu; unsigned i,j;
    words[0]=1u<<24 | engine<<16 | page<<8 | flags;
    words[1]=sample; words[2]=session;
    for (i=0;i<12;++i) words[i+3]=data[i];
    for (i=0;i<15;++i) for (j=0;j<4;++j)
        crc=crc_byte(crc,(uint8_t)(words[i]>>(24-8*j)));
    words[15]=crc^0xffffffffu;
    for (i=0;i<16;++i) {
        rows[i][0]=engine==PV_LIFE ? 'L' : engine==PV_NOTICE ? 'N' : 'V';
        rows[i][1]=hex_digit(i>>4); rows[i][2]=hex_digit(i&15); rows[i][3]=' ';
        for (j=0;j<8;++j) rows[i][4+j]=hex_digit((words[i]>>(28-4*j))&15);
        rows[i][12]=0;
    }
}

int pv_service_allowed(uint32_t id,uint32_t op)
{
    if (id==RV_STORAGE) return op==1 || op==2 || op==4 || op==6;
    if (id==RV_LEASE) return op==1 || op==2 || op==3;
    if (id==RV_SETTINGS) return op==1 || op==3;
    if (id==RV_UNIT || id==RV_SD_ID) return op==1;
    if (id==RV_EPOCHS) return op==12;
    if (id==RV_UI_LIST) return op==1 || op==3 || op==4;
    if (id==RV_UI_TEXT) return op==1 || op==2;
    if (id==RV_EVENTS) return op==1;
    if (id==RV_QUERY) return op<=2;
    return 0;
}
static int api_ok(const RvApi *api)
{ return api && api->version==1 && api->bytes==sizeof(*api) && api->call && api->service_count<=16; }
static int advertised(const RvApi *api,uint32_t id,uint32_t op)
{
    uint32_t i;
    for (i=0;i<api->service_count;++i)
        if (api->services[i].id==id && api->services[i].request_bytes==64)
            return (api->services[i].operations & (1u<<op))!=0;
    return 0;
}
static void error(PvState *s,uint32_t stage,int32_t status,int32_t native,uint32_t detail)
{
    s->last_stage=stage; s->last_status=(uint32_t)status;
    s->last_native=(uint32_t)native; s->last_detail=detail; s->flags|=PV_ERROR;
}
static void request(PvState *s)
{
    RvRequest *q=&s->request;
    clear(q,sizeof(*q)); q->version=1; q->bytes=64;
    q->args[0]=s->context; q->args[1]=s->lease;
    q->args[2]=s->epochs[RV_BOOT_E]; q->args[3]=s->epochs[RV_HEAP_E];
    q->args[4]=s->epochs[RV_LINK_E]; q->args[5]=s->epochs[RV_UNIT_E];
    q->args[6]=s->epochs[RV_VIEW_E]; q->args[7]=s->epochs[RV_S_E];
}
static void output_buffer(PvState *s,void *b,uint32_t bytes)
{ s->request.args[10]=address(b,bytes); s->request.args[11]=bytes; }
static int32_t call(const RvApi *api,PvState *s,uint32_t id,uint32_t op,uint32_t stage)
{
    int32_t status;
    clear(&s->reply,sizeof(s->reply));
    if (!pv_service_allowed(id,op) || !advertised(api,id,op)) {
        s->reply.version=1; s->reply.bytes=32; s->reply.status=RV_UNSUPPORTED;
        error(s,stage,RV_UNSUPPORTED,0,id<<16 | op); return RV_UNSUPPORTED;
    }
    status=api->call(id,op,&s->request,&s->reply);
    if (s->reply.version!=1 || s->reply.bytes!=32 || s->reply.status!=status) {
        s->sticky|=PV_BAD_REPLY;
        clear(&s->reply,sizeof(s->reply));
        s->reply.status=RV_VERIFY; s->reply.native_result=(int32_t)PV_UNKNOWN;
        error(s,stage,RV_VERIFY,(int32_t)PV_UNKNOWN,id<<16 | op); return RV_VERIFY;
    }
    if (status<0 || status==RV_UNAVAILABLE)
        error(s,stage,status,s->reply.native_result,s->reply.detail);
    return status;
}
static int increment(PvState *s,uint32_t *p)
{
    if (*p==0xffffffffu) { s->sticky|=PV_COUNTER_END; s->flags|=PV_LOST; return 0; }
    ++*p; return 1;
}
static PvState *ingress(const RvApi *api,uint32_t context,const RvRequest *q,
                         const PvInvocation **out,int initialized)
{
    const PvInvocation *f; PvState *s;
    if (!api_ok(api) || !q || q->version!=1 || q->bytes!=64 || q->flags ||
        q->args[0]!=context || !context || q->args[11]!=sizeof(PvInvocation) ||
        q->args[12] || q->args[13] || (q->args[10]&3u)) return 0;
    f=pointer(q->args[10],sizeof(*f));
    if (!f || !buffer_ok(&f->header,sizeof(*f)) || !f->state_lease ||
        f->state_lease!=q->args[1] || (f->state_address&3u) ||
        f->state_bytes<sizeof(PvState) || !f->nonce || !f->image_lease ||
        !f->code_bytes || !inside(f->image_address,f->image_bytes,f->code_address,f->code_bytes) ||
        (f->witness_bytes!=256 && f->witness_bytes!=32768) ||
        f->reference_valid>1 || (f->reference_valid &&
          ((f->reference_replica!=2 && f->reference_replica!=3) ||
           !f->reference_bytes || f->reference_bytes>PV_MAX_IROM))) return 0;
    if (f->ui_state_bytes && ((f->ui_state_address&3u) ||
        !inside(f->state_address,f->state_bytes,f->ui_state_address,f->ui_state_bytes) ||
        f->ui_state_address-f->state_address<sizeof(PvState))) return 0;
    s=pointer(f->state_address,sizeof(*s));
    if (!s || (initialized && (s->magic!=PV_STATE_MAGIC || s->context!=context ||
        s->lease!=f->state_lease || s->nonce!=f->nonce))) return 0;
    *out=f; return s;
}
static int32_t finish(PvState *s,RvReply *p,int32_t result,int32_t status)
{
    if (p) {
        clear(p,sizeof(*p)); p->version=1; p->bytes=32; p->status=status;
        if (s) { p->native_result=(int32_t)s->last_native; p->detail=s->sticky; }
    }
    return result;
}
static int epochs(const RvApi *api,PvState *s,int first)
{
    unsigned i; RvEpochSnapshot *e=&s->epoch_buffer;
    header(e,sizeof(*e)); request(s); output_buffer(s,e,sizeof(*e));
    if (call(api,s,RV_EPOCHS,12,PV_STAGE_EPOCHS)!=RV_OK) return 0;
    if (!buffer_ok(&e->header,sizeof(*e)) || s->reply.actual!=sizeof(*e) || !e->session_token)
        { error(s,PV_STAGE_EPOCHS,RV_VERIFY,0,0); return 0; }
    if (!first && (e->session_token!=s->session || e->epochs[RV_BOOT_E]!=s->boot ||
                   e->epochs[RV_HEAP_E]!=s->heap)) {
        s->sticky|=e->session_token!=s->session ? PV_ROOT_NEW : PV_HEAP_LOST;
        s->flags|=PV_LOST; return 0;
    }
    if (!first) {
        if (e->epochs[RV_UNIT_E]!=s->epochs[RV_UNIT_E] || e->epochs[RV_LINK_E]!=s->epochs[RV_LINK_E])
            s->valid&=~PV_HAVE_UNIT;
        if (e->epochs[RV_SD_E]!=s->epochs[RV_SD_E]) s->valid&=~PV_HAVE_SD;
        if (e->epochs[RV_S_E]!=s->epochs[RV_S_E]) s->valid&=~PV_HAVE_S;
    }
    for (i=0;i<RV_EPOCH_COUNT;++i) {
        s->epochs[i]=e->epochs[i];
        if (first) s->initial_epochs[i]=e->epochs[i];
    }
    if (first) { s->session=e->session_token; s->boot=s->epochs[RV_BOOT_E]; s->heap=s->epochs[RV_HEAP_E]; }
    return 1;
}
static int events(const RvApi *api,PvState *s)
{
    uint32_t i,previous=s->last_sequence; PvEvents *e=&s->event_buffer;
    header(e,sizeof(*e)); request(s); s->request.args[8]=previous;
    output_buffer(s,e,sizeof(*e));
    if (call(api,s,RV_EVENTS,1,PV_STAGE_EVENTS)!=RV_OK) return 0;
    if (e->header.version!=1 || e->header.flags || e->count>16 ||
        (e->header.bytes!=sizeof(*e) && e->header.bytes!=24+16*e->count) ||
        s->reply.actual!=24+16*e->count ||
        (e->count && (!e->first_sequence || e->last_sequence<e->first_sequence ||
         e->last_sequence-e->first_sequence!=e->count-1 || e->first_sequence<=previous)) ||
        e->dropped<s->dropped) { error(s,PV_STAGE_EVENTS,RV_VERIFY,0,0); return 0; }
    if (e->dropped) s->sticky|=PV_RING_GAP;
    if (e->count && e->first_sequence-1>previous) {
        uint32_t missing=e->first_sequence-previous-1;
        if (missing>0xffffffffu-s->gaps) { s->flags|=PV_LOST; s->sticky|=PV_COUNTER_END; return 0; }
        s->gaps+=missing; s->sticky|=PV_SEQ_GAP;
    }
    for (i=0;i<e->count;++i) {
        RvEvent *v=&e->events[i]; uint32_t h=v->hook,j;
        if (v->sequence!=e->first_sequence+i || v->phase>3) {
            error(s,PV_STAGE_EVENTS,RV_VERIFY,0,i); return 0;
        }
        if (s->trace_count==16) {
            for (j=0;j<15;++j) s->trace[j]=s->trace[j+1];
        } else ++s->trace_count;
        s->trace[s->trace_count-1]=*v;
        if (h<38) {
            if (v->phase==0 && !increment(s,&s->hook_pre[h])) return 0;
            if (v->phase==1 && !increment(s,&s->hook_post[h])) return 0;
            s->hook_last_a[h]=v->a; s->hook_last_b[h]=v->b;
        }
        s->last_sequence=v->sequence;
    }
    s->ring_first=e->first_sequence; s->ring_last=e->last_sequence; s->dropped=e->dropped;
    return 1;
}
static int inspect_witness(const RvApi *api,PvState *s)
{
    RvLeaseInfo *l=&s->lease_buffer; PvWitness *w=&s->witness;
    header(l,sizeof(*l)); request(s); s->request.args[1]=w->token;
    output_buffer(s,l,sizeof(*l));
    if (call(api,s,RV_LEASE,3,PV_STAGE_INSPECT)!=RV_OK) return 0;
    if (!buffer_ok(&l->header,sizeof(*l)) || s->reply.actual!=sizeof(*l) ||
        l->token!=w->token || l->base!=w->address || l->length<w->bytes ||
        l->boot_epoch!=w->boot || l->heap_epoch!=w->heap) return 0;
    return 1;
}
static uint8_t pattern(uint32_t nonce,uint32_t offset)
{
    uint32_t x=nonce^(offset*0x45d9f3bu);
    x^=x>>16; x*=0x45d9f3bu; x^=x>>16;
    return (uint8_t)x;
}
static int witness(const RvApi *api,PvState *s,const PvInvocation *f)
{
    PvWitness *w=&s->witness; RvLeaseInfo *l=&s->lease_buffer;
    uint8_t *b; uint32_t i;
    if (!w->attempted) {
        w->attempted=1; header(l,sizeof(*l)); request(s);
        s->request.args[8]=f->witness_bytes; s->request.args[9]=f->witness_usage;
        output_buffer(s,l,sizeof(*l));
        if (call(api,s,RV_LEASE,1,PV_STAGE_ALLOC)!=RV_OK) return 0;
        if (!buffer_ok(&l->header,sizeof(*l)) || s->reply.actual!=sizeof(*l) || !l->token ||
            l->length<f->witness_bytes || l->boot_epoch!=s->boot || l->heap_epoch!=s->heap ||
            (l->base&3u) || l->base>0xffffffffu-f->witness_bytes) return 0;
        w->allocations=1; w->token=l->token; w->address=l->base; w->bytes=f->witness_bytes;
        w->nonce=s->nonce; w->boot=s->boot; w->heap=s->heap;
        b=pointer(w->address,w->bytes);
        if (!b) return 0;
        for (i=0;i<w->bytes;++i) b[i]=pattern(w->nonce,i);
        w->baseline_crc=pv_crc32(b,w->bytes);
    }
    if (!w->token || !inspect_witness(api,s)) {
        s->sticky|=PV_HEAP_LOST; s->flags|=PV_LOST; return 0;
    }
    b=pointer(w->address,w->bytes);
    if (!b) return 0;
    w->crc=pv_crc32(b,w->bytes);
    w->canary_bad=0;
    for (i=0;i<4;++i) {
        if (b[i]!=pattern(w->nonce,i)) w->canary_bad|=1;
        if (b[w->bytes/2+i]!=pattern(w->nonce,w->bytes/2+i)) w->canary_bad|=2;
        if (b[w->bytes-4+i]!=pattern(w->nonce,w->bytes-4+i)) w->canary_bad|=4;
    }
    if (w->crc!=w->baseline_crc) s->sticky|=PV_DATA_BAD;
    if (w->canary_bad) s->sticky|=PV_CANARY_BAD;
    if (s->sticky&(PV_DATA_BAD|PV_CANARY_BAD)) { s->flags|=PV_LOST; return 0; }
    return increment(s,&w->checks);
}
static uint32_t capacity_bytes(unsigned i)
{ return (i==0 ? 64u : i==1 ? 48u : i==2 ? 40u : i==3 ? 32u : 16u)<<10; }
static uint32_t page_count(void)
{ return PV_ENGINE==PV_LIFE ? 17 : 12; }
static int capacity(const RvApi *api,PvState *s,const PvInvocation *f,uint32_t stage)
{
    PvCapacity *c=&s->capacity[stage]; RvLeaseInfo *l=&s->lease_buffer;
    uint32_t i,bit,token,bytes; int32_t status;
    if (c->state) return c->state==2;
    c->state=1; c->session=s->session; c->sample=s->sample;
    c->boot=s->boot; c->heap=s->heap; c->witness_bytes=s->witness.bytes;
    for (i=0;i<5;++i) {
        bit=1u<<i; bytes=capacity_bytes(i); c->attempted_mask|=bit;
        header(l,sizeof(*l)); request(s); s->request.args[8]=bytes;
        s->request.args[9]=f->witness_usage; output_buffer(s,l,sizeof(*l));
        status=call(api,s,RV_LEASE,1,PV_STAGE_CAP_ALLOC);
        c->alloc_status[i]=(uint32_t)status; c->alloc_native[i]=(uint32_t)s->reply.native_result;
        if (status!=RV_OK) {
            if (status==RV_STALE || status==RV_OWNER || status==RV_FAULTED || (s->sticky&PV_BAD_REPLY))
                { c->state=3; s->flags|=PV_LOST; s->sticky|=PV_CAPACITY_BAD; return 0; }
            continue;
        }
        /* Never read, write, hash or map the returned allocation. Validation
         * touches only the reply descriptor in the existing state lease. */
        if (!buffer_ok(&l->header,sizeof(*l)) || s->reply.actual!=sizeof(*l) || !l->token ||
            !l->base || l->length<bytes || l->boot_epoch!=s->boot || l->heap_epoch!=s->heap ||
            l->token==s->lease || l->token==f->image_lease || l->token==s->witness.token) {
            c->state=3; s->flags|=PV_LOST; s->sticky|=PV_CAPACITY_BAD;
            error(s,PV_STAGE_CAP_ALLOC,RV_VERIFY,0,i); return 0;
        }
        token=l->token; c->allocated_mask|=bit;
        /* The very next service call after successful alloc is free. */
        request(s); s->request.args[1]=token;
        status=call(api,s,RV_LEASE,2,PV_STAGE_CAP_FREE);
        c->free_status[i]=(uint32_t)status; c->free_native[i]=(uint32_t)s->reply.native_result;
        if (status!=RV_OK) { c->state=3; s->flags|=PV_LOST; s->sticky|=PV_CAPACITY_BAD; return 0; }
        c->freed_mask|=bit;
        if (bytes>c->maximum_bytes) c->maximum_bytes=bytes;
    }
    if (!epochs(api,s,0)) { c->state=3; s->flags|=PV_LOST; s->sticky|=PV_CAPACITY_BAD; return 0; }
    c->state=2; return 1;
}
static uint32_t capacity_codes(const PvCapacity *c,int release)
{
    uint32_t packed=0,i,code,mask=release ? c->allocated_mask : c->attempted_mask;
    for (i=0;i<5;++i) {
        int32_t status=(int32_t)(release ? c->free_status[i] : c->alloc_status[i]);
        code=!(mask&(1u<<i)) ? 14u : status<=0 && status>=-12 ? (uint32_t)-status : 13u;
        packed|=code<<(4*i);
    }
    return packed;
}
static void sd_snapshot(const RvApi *api,PvState *s)
{
    uint32_t old_valid=s->sd_seen,i; int nonzero=0; int32_t status;
    s->valid&=~PV_HAVE_SD; clear(s->sd,16);
    request(s); output_buffer(s,s->sd,16);
    status=call(api,s,RV_SD_ID,1,PV_STAGE_SD);
    s->sd_status=(uint32_t)status; s->sd_native=(uint32_t)s->reply.native_result;
    if (status!=RV_OK || s->reply.actual!=16 || s->reply.epoch!=s->epochs[RV_SD_E]) return;
    for (i=0;i<16;++i) nonzero|=s->sd[i];
    if (!nonzero) { s->sd_status=(uint32_t)RV_VERIFY; return; }
    s->sd_old_epoch=s->sd_epoch; s->sd_epoch=s->reply.epoch; s->valid|=PV_HAVE_SD;
    if (old_valid) {
        if (!same(s->sd,s->sd_old,16)) increment(s,&s->sd_changed);
        else if (s->sd_epoch!=s->sd_old_epoch) increment(s,&s->sd_same);
    }
    copy(s->sd_old,s->sd,16); s->sd_seen=1;
}
static void unit_snapshot(const RvApi *api,PvState *s)
{
    int32_t status; uint32_t old_valid=s->unit_seen;
    s->valid&=~PV_HAVE_UNIT; header(&s->unit,sizeof(s->unit));
    request(s); output_buffer(s,&s->unit,sizeof(s->unit));
    status=call(api,s,RV_UNIT,1,PV_STAGE_UNIT);
    s->unit_status=(uint32_t)status; s->unit_native=(uint32_t)s->reply.native_result;
    if (status!=RV_OK || !buffer_ok(&s->unit.header,sizeof(s->unit)) ||
        s->reply.actual!=sizeof(s->unit) || s->unit.valid!=1 ||
        s->unit.unit_epoch!=s->epochs[RV_UNIT_E] || s->unit.link_epoch!=s->epochs[RV_LINK_E]) return;
    s->valid|=PV_HAVE_UNIT;
    if (old_valid && (s->unit.unit_epoch!=s->unit_old.unit_epoch ||
        s->unit.link_epoch!=s->unit_old.link_epoch || s->unit.rx_sequence!=s->unit_old.rx_sequence)) {
        increment(s,&s->unit_changes);
        if (same(s->unit.name,s->unit_old.name,8)) increment(s,&s->unit_same);
    }
    s->unit_old=s->unit; s->unit_seen=1;
}
static void settings(const RvApi *api,PvState *s)
{
    RvSettingsInfo *b=&s->settings_buffer; const uint8_t *p; int32_t status;
    uint32_t old=s->valid&PV_HAVE_S;
    if (old) { s->wb_old0=s->wb0; s->wb_old1=s->wb1; }
    s->valid&=~PV_HAVE_S; s->wb0=PV_UNKNOWN; s->wb1=PV_UNKNOWN;
    header(b,sizeof(*b)); request(s); output_buffer(s,b,sizeof(*b));
    status=call(api,s,RV_SETTINGS,1,PV_STAGE_SETTINGS);
    s->s_status=(uint32_t)status; s->s_native=(uint32_t)s->reply.native_result;
    if (status!=RV_OK) return;
    if (buffer_ok(&b->header,sizeof(*b)) && s->reply.actual==sizeof(*b) && b->token &&
        b->length>0x6de && b->settings_epoch==s->epochs[RV_S_E] && b->address<=0xffffffffu-b->length) {
        p=pointer(b->address+0x6dd,2);
        if (p) {
            s->wb0=p[0]; s->wb1=p[1];
            if (s->wb0>=1 && s->wb0<=17 && s->wb1>=1 && s->wb1<=17) {
                s->valid|=PV_HAVE_S;
                if (old && (s->wb0!=s->wb_old0 || s->wb1!=s->wb_old1)) increment(s,&s->wb_changes);
            }
        }
    }
    /* A failed snapshot never authorizes using/releasing an undefined token. */
    if (buffer_ok(&b->header,sizeof(*b)) && s->reply.actual==sizeof(*b) && b->token) {
        request(s);
        if (call(api,s,RV_SETTINGS,3,PV_STAGE_RELEASE)!=RV_OK) s->valid&=~PV_HAVE_S;
    }
}
static int32_t storage(const RvApi *api,PvState *s,uint32_t op,uint32_t token,
                         uint32_t bytes,uint32_t stage)
{
    /* STORAGE uses its original wire offsets, not generic args semantics. */
    clear(&s->request,sizeof(s->request)); s->request.version=1; s->request.bytes=64;
    if (op!=1) s->request.args[0]=s->irom.epoch;
    if (op==2) { s->request.args[2]=1; s->request.args[5]=s->irom.replica; }
    if (op==4 || op==6) s->request.args[1]=token;
    if (op==4) { s->request.args[6]=address(s->io,bytes); s->request.args[7]=bytes; }
    return call(api,s,RV_STORAGE,op,stage);
}
static void irom_read(const RvApi *api,PvState *s,const PvInvocation *f,uint32_t replica)
{
    PvIrom *v=&s->irom; int32_t status;
    uint32_t token,crc=0xffffffffu,i,limit,ask,done=0,before_irom=s->epochs[RV_IROM_E];
    uint32_t have_ref=f->reference_valid && f->reference_replica==replica;
    clear(v,sizeof(*v)); v->state=PV_IROM_READ; v->replica=replica;
    v->close_status=PV_UNKNOWN; v->close_native=PV_UNKNOWN;
    v->expected_bytes=have_ref ? f->reference_bytes : PV_UNKNOWN;
    v->expected_crc=have_ref ? f->reference_crc : PV_UNKNOWN;
    v->sd_before=s->epochs[RV_SD_E];
    status=storage(api,s,1,0,0,PV_STAGE_CAPS);
    if (status!=RV_OK || !(s->reply.capabilities&2u)) {
        v->status=status==RV_OK ? (uint32_t)RV_CAPABILITY : (uint32_t)status;
        v->native_result=(uint32_t)s->reply.native_result; v->state=PV_IROM_FAILED; return;
    }
    v->epoch=s->reply.epoch;
    status=storage(api,s,2,0,0,PV_STAGE_OPEN);
    v->status=(uint32_t)status; v->native_result=(uint32_t)s->reply.native_result;
    if (status!=RV_OK || !s->reply.token) { v->state=PV_IROM_FAILED; return; }
    token=s->reply.token; limit=have_ref ? f->reference_bytes : PV_MAX_IROM;
    for (v->reads=0;v->reads<96;++v->reads) {
        ask=v->actual<limit ? limit-v->actual : 1;
        if (ask>sizeof(s->io)) ask=sizeof(s->io);
        status=storage(api,s,4,token,ask,PV_STAGE_READ);
        v->status=(uint32_t)status; v->native_result=(uint32_t)s->reply.native_result;
        if ((status!=RV_OK && status!=RV_EOF) || s->reply.actual>ask ||
            (status==RV_EOF && s->reply.actual)) break;
        if (!s->reply.actual) { done=1; break; }
        if (v->actual==limit) { v->status=(uint32_t)RV_VERIFY; break; }
        for (i=0;i<s->reply.actual;++i) crc=crc_byte(crc,s->io[i]);
        v->actual+=s->reply.actual;
    }
    v->crc=crc^0xffffffffu;
    status=storage(api,s,6,token,0,PV_STAGE_CLOSE);
    v->close_status=(uint32_t)status; v->close_native=(uint32_t)s->reply.native_result;
    if (!done || status!=RV_OK || (have_ref &&
        (v->actual!=f->reference_bytes || v->crc!=f->reference_crc))) v->state=PV_IROM_FAILED;
    else v->state=have_ref ? PV_IROM_MATCH : PV_IROM_UNREFERENCED;
    if (!done && v->status==RV_OK) v->status=(uint32_t)RV_BUSY;
    if (done && have_ref && (v->actual!=f->reference_bytes || v->crc!=f->reference_crc))
        v->status=(uint32_t)RV_VERIFY;
    status=storage(api,s,1,0,0,PV_STAGE_CAPS);
    if (status!=RV_OK || s->reply.epoch!=v->epoch) v->state=PV_IROM_FAILED;
    if (!epochs(api,s,0)) { v->state=PV_IROM_FAILED; return; }
    v->sd_after=s->epochs[RV_SD_E];
    if (before_irom!=s->epochs[RV_IROM_E] || v->sd_before!=v->sd_after) v->state=PV_IROM_FAILED;
}
static void ingest(PvState *s,const PvInvocation *f)
{
    if (buffer_ok(&f->input.header,sizeof(f->input)) && f->input.valid_fields) {
        s->input=f->input; s->valid|=PV_HAVE_INPUT;
    }
    if (buffer_ok(&f->refresh.header,sizeof(f->refresh)) && f->refresh.valid_fields) {
        s->refresh=f->refresh; s->valid|=PV_HAVE_REFRESH;
    }
}
static int sample(const RvApi *api,PvState *s,const PvInvocation *f)
{
    const void *code;
    if ((s->flags&PV_LOST) || !epochs(api,s,0) || !increment(s,&s->sample)) return 0;
    ingest(s,f);
    if (!events(api,s)) return 0;
    if (PV_ENGINE==PV_LIFE && !witness(api,s,f)) return 0;
    if (PV_ENGINE==PV_LIFE && !s->capacity[0].state && !capacity(api,s,f,0)) return 0;
    if (PV_ENGINE==PV_NOTICE || PV_ENGINE==PV_LIFE) sd_snapshot(api,s);
    if (PV_ENGINE==PV_NOTICE) unit_snapshot(api,s);
    if (PV_ENGINE==PV_VIEW) settings(api,s);
    code=pointer(f->code_address,f->code_bytes);
    if (!code) return 0;
    s->witness.code_crc=pv_crc32(code,f->code_bytes);
    if (s->witness.code_crc!=s->witness.baseline_code_crc) {
        s->sticky|=PV_CODE_BAD; s->flags|=PV_LOST; return 0;
    }
    return epochs(api,s,0);
}

static void page_data(PvState *s,uint32_t *d)
{
    uint32_t i,p=s->page;
    for (i=0;i<12;++i) d[i]=PV_UNKNOWN;
    if (p==0) {
        d[0]=s->sticky; d[1]=s->valid; d[2]=s->last_stage; d[3]=s->last_status;
        d[4]=s->last_native; d[5]=s->last_detail; d[6]=s->mark;
        d[7]=s->dropped; d[8]=s->gaps; d[9]=s->ring_first; d[10]=s->ring_last; d[11]=s->nonce;
    } else if (p==1) for (i=0;i<12;++i) d[i]=s->epochs[i];
    else if ((PV_ENGINE==PV_LIFE && p>=8 && p<=13) || (PV_ENGINE!=PV_LIFE && p>=6)) {
        uint32_t start=(p-(PV_ENGINE==PV_LIFE ? 8 : 6))*3,j;
        for (i=0;i<3 && start+i<s->trace_count;++i) {
            const RvEvent *v=&s->trace[start+i]; j=i*4;
            d[j]=v->sequence; d[j+1]=(uint32_t)v->hook<<16 | v->phase; d[j+2]=v->a; d[j+3]=v->b;
        }
    } else if (PV_ENGINE==PV_LIFE) {
        if (p==2) {
            d[0]=s->irom.state; d[1]=s->irom.replica; d[2]=s->irom.status; d[3]=s->irom.native_result;
            d[4]=s->irom.actual; d[5]=s->irom.crc; d[6]=s->irom.close_status; d[7]=s->irom.close_native;
            d[8]=s->irom.expected_bytes; d[9]=s->irom.expected_crc; d[10]=s->irom.sd_before; d[11]=s->irom.sd_after;
        } else if (p==3) {
            d[0]=s->witness.allocations; d[1]=s->witness.token; d[2]=s->witness.address; d[3]=s->witness.bytes;
            d[4]=s->witness.nonce; d[5]=s->witness.baseline_crc; d[6]=s->witness.crc;
            d[7]=s->witness.canary_bad; d[8]=s->witness.baseline_code_crc; d[9]=s->witness.code_crc;
            d[10]=s->witness.checks; d[11]=s->witness.attempted;
        } else if (p==4) {
            d[0]=s->hook_pre[15]; d[1]=s->hook_pre[16]; d[2]=s->hook_pre[17]; d[3]=s->hook_post[17];
            d[4]=s->hook_last_a[17]; d[5]=s->hook_last_b[17]; d[6]=s->hook_pre[18]; d[7]=s->hook_post[18];
            d[8]=s->hook_last_a[18]; d[9]=s->hook_last_b[18]; d[10]=s->session;
            /* Stack witness republishing has no frozen service in ABI v1. */
        } else if (p>=5 && p<=7) {
            const PvCapacity *c=&s->capacity[p-5];
            d[0]=c->state; d[1]=c->maximum_bytes; d[2]=c->attempted_mask;
            d[3]=c->allocated_mask; d[4]=c->freed_mask; d[5]=c->session;
            d[6]=c->sample; d[7]=c->boot; d[8]=c->heap;
            d[9]=capacity_codes(c,0); d[10]=capacity_codes(c,1); d[11]=c->witness_bytes;
        } else if (p>=14 && p<=16) {
            const PvCapacity *c=&s->capacity[p-14];
            for (i=0;i<5;++i) {
                if (c->attempted_mask&(1u<<i)) d[i]=c->alloc_native[i];
                if (c->allocated_mask&(1u<<i)) d[i+5]=c->free_native[i];
            }
            d[10]=c->state; d[11]=c->maximum_bytes;
        }
    } else if (PV_ENGINE==PV_NOTICE) {
        if (p==2) {
            for (i=0;i<4;++i) d[i]=word_be(s->sd+i*4);
            d[4]=s->sd_epoch; d[5]=s->sd_old_epoch; d[6]=s->sd_changed; d[7]=s->sd_same;
            d[8]=s->sd_status; d[9]=s->sd_native; d[10]=s->hook_pre[22]; d[11]=s->hook_post[22];
        } else if (p==3) {
            d[0]=word_be(s->unit.name); d[1]=word_be(s->unit.name+4);
            d[2]=(uint32_t)s->unit.main_version<<16 | s->unit.cmp_version;
            d[3]=s->valid&PV_HAVE_UNIT ? s->unit.valid : 0; d[4]=s->unit.unit_epoch; d[5]=s->unit.link_epoch;
            d[6]=s->unit.rx_sequence; d[7]=s->unit_changes; d[8]=s->unit_same;
            d[9]=s->unit_status; d[10]=s->unit_native; d[11]=s->hook_pre[21];
        } else if (p==4) {
            if (s->valid&PV_HAVE_INPUT) {
                d[0]=s->input.sequence; d[1]=s->input.event; d[2]=s->input.source; d[3]=s->input.edge;
                d[4]=s->input.activity; d[5]=s->input.state; d[6]=s->input.part; d[7]=s->input.tag;
                d[8]=s->input.top_tag; d[9]=s->input.top_state; d[10]=s->input.count; d[11]=s->input.view_epoch;
            }
        } else if (p==5) {
            d[0]=s->hook_pre[10]; d[1]=s->hook_pre[6]; d[2]=s->hook_pre[11]; d[3]=s->hook_pre[12];
            d[4]=s->hook_pre[13]; d[5]=s->hook_pre[14]; d[6]=s->hook_pre[19];
            d[7]=s->hook_pre[20]; d[8]=s->hook_post[20]; d[9]=s->hook_last_b[20];
            d[10]=s->input.valid_fields; d[11]=s->panel;
        }
    } else if (p==2) {
        d[0]=s->valid&PV_HAVE_S ? s->wb0 : PV_UNKNOWN; d[1]=s->valid&PV_HAVE_S ? s->wb1 : PV_UNKNOWN;
        d[2]=s->valid&PV_HAVE_S ? s->wb0-9 : PV_UNKNOWN; d[3]=s->valid&PV_HAVE_S ? s->wb1-9 : PV_UNKNOWN;
        d[4]=s->wb_old0; d[5]=s->wb_old1; d[6]=s->wb_changes; d[7]=s->epochs[RV_S_E];
        d[8]=s->s_status; d[9]=s->s_native;
        /* d[10..11] are axis identity/enable condition, deliberately UNKNOWN. */
    } else if (p==3) {
        d[0]=s->hook_pre[37]; d[1]=s->hook_post[37]; d[2]=s->hook_last_a[37]; d[3]=s->hook_last_b[37];
        if (s->valid&PV_HAVE_REFRESH) {
            d[4]=s->refresh.valid_fields; d[5]=s->refresh.sequence;
            d[6]=s->refresh.apply_sequence; d[7]=s->refresh.stage;
            d[8]=s->refresh.native_result; d[9]=s->refresh.rows_verified;
            d[10]=s->refresh.s_published; d[11]=s->refresh.preview_sequence;
        }
        /* No frame completion or write driver exists in this engine. */
    } else if (p==4) {
        d[0]=0; d[1]=0; d[2]=PV_UNKNOWN; d[3]=PV_UNKNOWN;
    } else if (p==5) for (i=0;i<6;++i) d[i]=s->draft[i];
}
static int display(const RvApi *api,PvState *s,const PvInvocation *f)
{
    uint32_t d[12],i,language; RvUiText *t=&s->text; RvUiList *l=&s->list;
    page_data(s,d); pv_encode(s->page,s->sample,s->session,s->flags,PV_ENGINE,d,s->rows);
    if (!f->ui_state_bytes) return 1;
    request(s);
    if (call(api,s,RV_UI_TEXT,2,PV_STAGE_LANGUAGE)!=RV_OK) return 0;
    /* Current resident_impl returns the scalar language in detail. */
    language=s->reply.detail;
    for (i=0;i<16;++i) {
        header(t,sizeof(*t)); t->source_address=address(s->rows[i],13); t->source_bytes=12;
        t->source_lease=s->lease; t->glyph_address=address(s->glyphs[i],96);
        t->glyph_capacity=96; t->glyph_lease=s->lease; t->language=language;
        request(s); output_buffer(s,t,sizeof(*t));
        if (call(api,s,RV_UI_TEXT,1,PV_STAGE_GLYPH)!=RV_OK) return 0;
        if (t->actual_bytes>96 || !t->actual_bytes) return 0;
        s->labels[i]=t->glyph_address; s->table[i]=address(&s->labels[i],4);
    }
    header(l,sizeof(*l)); l->view_token=s->ui_view_token ? s->ui_view_token : f->view_token;
    l->state_address=f->ui_state_address;
    l->state_bytes=f->ui_state_bytes; l->rows=16; l->cursor=0;
    l->label_table=address(s->table,sizeof(s->table)); l->details=address(s->details,sizeof(s->details));
    l->lease_token=s->lease; request(s); s->request.args[9]=16; output_buffer(s,l,sizeof(*l));
    if (call(api,s,RV_UI_LIST,1,PV_STAGE_BIND)!=RV_OK) return 0;
    s->ui_view_token=l->view_token;
    request(s); s->request.args[9]=16; output_buffer(s,l,sizeof(*l));
    return call(api,s,RV_UI_LIST,3,PV_STAGE_BIND)==RV_OK;
}
int32_t pv_bootstrap(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    RvEngineEntries *e; uint32_t base=q && q->args[8] ? q->args[8] : PV_IMAGE_ENGINE_OFFSET;
    (void)context;
    if (!api_ok(api) || !q || q->version!=1 || q->bytes!=64 || q->flags ||
        base<PV_IMAGE_ENGINE_OFFSET || (base&3u) || base>0xffffffffu-160 || q->args[9] ||
        q->args[11]!=sizeof(RvEngineEntries) || (q->args[10]&3u))
        return finish(0,p,RV_FAULT,RV_ARGUMENT);
    e=pointer(q->args[10],sizeof(*e));
    if (!e) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    clear(e,sizeof(*e)); e->version=1; e->bytes=40;
    e->init=base+16; e->menu_open=base+32; e->event=base+48;
    e->panel_open=base+64; e->panel_event=base+80; e->panel_abort=base+96;
    e->apply_step=base+112; e->shutdown=base+128; e->abort=base+144;
    finish(0,p,RV_PASS,RV_OK);
    if (p) p->actual=40;
    return RV_PASS;
}
int32_t pv_init(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,0); const void *code; unsigned i;
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    if (s->magic) return finish(s,p,RV_FAULT,RV_CONFLICT);
    clear(s,sizeof(*s)); s->magic=PV_STATE_MAGIC; s->context=context; s->lease=f->state_lease;
    s->nonce=f->nonce; s->flags=PV_RO|PV_GAPS;
    s->epochs[RV_BOOT_E]=q->args[2]; s->epochs[RV_HEAP_E]=q->args[3];
    s->epochs[RV_LINK_E]=q->args[4]; s->epochs[RV_UNIT_E]=q->args[5];
    s->epochs[RV_VIEW_E]=q->args[6]; s->epochs[RV_S_E]=q->args[7];
    s->wb0=s->wb1=s->wb_old0=s->wb_old1=PV_UNKNOWN;
    s->irom.close_status=s->irom.close_native=PV_UNKNOWN;
    for (i=0;i<6;++i) s->draft[i]=0;
    if (!epochs(api,s,1)) return finish(s,p,RV_FAULT,(int32_t)s->last_status);
    code=pointer(f->code_address,f->code_bytes);
    if (!code) return finish(s,p,RV_FAULT,RV_RANGE);
    s->witness.baseline_code_crc=pv_crc32(code,f->code_bytes);
    s->witness.code_crc=s->witness.baseline_code_crc;
    finish(s,p,RV_PASS,RV_OK);
    if (p) p->capabilities=PV_READY_UI_CAP;
    return RV_PASS;
}
int32_t pv_menu_open(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,1);
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    if (!sample(api,s,f)) return finish(s,p,RV_FAULT,RV_VERIFY);
    if (!display(api,s,f)) return finish(s,p,RV_FAULT,(int32_t)s->last_status);
    return finish(s,p,RV_CONSUMED,RV_OK);
}
int32_t pv_event(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,1);
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    if (!epochs(api,s,0) || !events(api,s)) return finish(s,p,RV_FAULT,RV_VERIFY);
    ingest(s,f);
    /* Physical/logical keys always retain their native behavior. */
    return finish(s,p,RV_PASS,RV_OK);
}
int32_t pv_apply_step(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,1);
    uint32_t op=q ? q->args[8] : 0,value=q ? q->args[9] : 0;
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    if ((s->flags&PV_LOST) || !epochs(api,s,0)) return finish(s,p,RV_FAULT,RV_STALE);
    if (op==PV_SELECT_ROW) {
        if (value<12) { op=PV_PAGE; }
        else if (value==12) op=PV_SAMPLE;
        else if (value==13) op=PV_READ_A;
        else if (value==14) op=PV_READ_B;
        else if (value==15) {
            if (!increment(s,&s->mark)) return finish(s,p,RV_FAULT,RV_RANGE);
            op=PV_MARK; value=s->mark;
        }
        else return finish(s,p,RV_CONSUMED,RV_ARGUMENT);
    }
    if (op==PV_PAGE && value<page_count()) s->page=value;
    else if (op==PV_MARK) s->mark=value;
    else if (op==PV_SAMPLE) {
        if (!sample(api,s,f)) return finish(s,p,RV_FAULT,RV_VERIFY);
        if (PV_ENGINE==PV_LIFE && (s->page==6 || s->page==7) && !s->capacity[s->page-5].state &&
            !capacity(api,s,f,s->page-5)) return finish(s,p,RV_FAULT,RV_VERIFY);
    } else if (op==PV_CAPACITY && PV_ENGINE==PV_LIFE && value<3) {
        if (s->capacity[value].state || (value && s->capacity[0].state!=2))
            return finish(s,p,RV_CONSUMED,RV_CONFLICT);
        if (!increment(s,&s->sample)) return finish(s,p,RV_FAULT,RV_RANGE);
        if (!capacity(api,s,f,value)) return finish(s,p,RV_FAULT,RV_VERIFY);
        s->page=5+value;
    } else if ((op==PV_READ_A || op==PV_READ_B) && PV_ENGINE==PV_LIFE) {
        if (!increment(s,&s->sample)) return finish(s,p,RV_FAULT,RV_RANGE);
        irom_read(api,s,f,op==PV_READ_A ? 2 : 3); s->page=2;
        if (s->flags&PV_LOST) return finish(s,p,RV_FAULT,RV_STALE);
    } else return finish(s,p,RV_CONSUMED,RV_UNSUPPORTED);
    if (!display(api,s,f)) return finish(s,p,RV_FAULT,(int32_t)s->last_status);
    /* Never PASS an unknown row/command into native recipe application. */
    return finish(s,p,RV_CONSUMED,RV_OK);
}
int32_t pv_panel_open(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,1);
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    if (PV_ENGINE==PV_LIFE) {
        if (!epochs(api,s,0)) return finish(s,p,RV_FAULT,RV_STALE);
        s->page=s->page+1<page_count() ? s->page+1 : 0;
        if (!display(api,s,f)) return finish(s,p,RV_FAULT,(int32_t)s->last_status);
        return finish(s,p,RV_CONSUMED,RV_OK);
    }
    /* Full native nine-row view state is not defined by the frozen ABI.
     * A draft-only panel cannot claim that UI replacement has been tested. */
    s->panel=1; s->flags|=PV_PANEL;
    return finish(s,p,RV_CONSUMED,RV_UNSUPPORTED);
}
int32_t pv_panel_event(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,1);
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    ingest(s,f);
    if (s->panel && q->args[8]<6 && (int32_t)q->args[9]>=-5 && (int32_t)q->args[9]<=5) {
        s->draft[q->args[8]]=q->args[9]; return finish(s,p,RV_CONSUMED,RV_OK);
    }
    return finish(s,p,RV_PASS,RV_OK);
}
static int32_t close_probe(const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    const PvInvocation *f; PvState *s=ingress(api,context,q,&f,1); int32_t status=RV_OK;
    if (!s) return finish(0,p,RV_FAULT,RV_ARGUMENT);
    s->panel=0; s->flags&=~PV_PANEL;
    if (f->ui_state_bytes && !(s->flags&PV_LOST)) {
        header(&s->list,sizeof(s->list));
        s->list.view_token=s->ui_view_token;
        s->list.lease_token=s->lease;
        request(s); output_buffer(s,&s->list,sizeof(s->list));
        status=call(api,s,RV_UI_LIST,4,PV_STAGE_RELEASE);
    }
    /* Resident retains/reclaims leases only after native references drain.
     * In particular, this code never frees a stale witness or its own image. */
    return finish(s,p,status==RV_OK ? RV_CLOSE_AND_PASS : RV_FAULT,status);
}
int32_t pv_panel_abort(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *p)
{ return close_probe(a,c,q,p); }
int32_t pv_shutdown(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *p)
{ return close_probe(a,c,q,p); }
int32_t pv_abort(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *p)
{ return close_probe(a,c,q,p); }
