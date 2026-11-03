#include "engine_services.h"

static RvRoot *root(void)
{
#ifdef RV_HOST
    return rv_host_root;
#else
    return RV_PTR(RV_ROOT);
#endif
}
const RvApi *rv_services_init(const RvPrivateContext *c)
{
    RvRoot *r=root();RvSession *s=rv_session(r);
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION||!s||c!=&s->context)return 0;
    if(!c->header.version){
        es_storage_reset();
        RvPrivateContext *x=&s->context;
        s->generation=rv_be32((const uint8_t *)RV_PTR(s->image_address)+28);
        s->entry_offset=rv_be32((const uint8_t *)RV_PTR(s->image_address)+112);s->source_bytes=s->image_bytes;
        x->header=(RvBufferHeader){1,sizeof(*x),0};x->root_address=RV_ROOT;x->root_bytes=256;
        x->session_address=r->block;x->session_bytes=sizeof(*s);
        x->state_address=s->image_address+rv_image_span(s->image_bytes,s->bss_bytes);x->state_bytes=RV_STATE_BYTES;x->state_lease=r->lease;
        x->image_address=s->image_address;x->image_bytes=s->image_bytes;x->image_lease=r->lease;
        x->code_address=s->image_address+s->code_begin;x->code_bytes=s->code_end-s->code_begin;
        x->image_bss_bytes=s->bss_bytes;x->nonce=r->lease;
        x->ui_state_address=x->state_address+RV_STATE_BYTES;x->ui_state_capacity=RV_UI_CAPACITY;
        x->entries_address=r->block+offsetof(RvSession,entries);x->entries_bytes=40;x->lease_max_bytes=RV_MAX_LEASE;
    }
    if(!s||c!=&s->context||c->header.version!=1||c->header.bytes!=sizeof(*c)||c->header.flags||
       c->root_address!=RV_ROOT||c->root_bytes!=sizeof(*r)||c->session_address!=r->block||
       c->session_bytes!=sizeof(*s)||c->lease_max_bytes!=RV_MAX_LEASE||!c->nonce||c->nonce!=r->lease||
       c->image_address!=s->image_address||c->image_bytes!=s->image_bytes||
       c->image_bss_bytes!=s->bss_bytes||c->code_address!=s->image_address+s->code_begin||
       c->code_bytes!=s->code_end-s->code_begin||
       !rv_range(r,c->state_lease,c->state_address,c->state_bytes)||
       !rv_range(r,c->image_lease,c->image_address,c->image_bytes+c->image_bss_bytes)||
       !rv_range(r,c->state_lease,c->ui_state_address,c->ui_state_capacity)||
       c->ui_state_bytes>c->ui_state_capacity)return 0;
    {GxrceUnit unit;if(rv_unit(r,&unit)||!rv_equal(&unit,&r->unit,sizeof(unit)))return 0;}
    return &rv_api;
}
int32_t rv_call(uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{return rv_service(root(),id,op,q,p);}
int32_t rv_unit(RvRoot *r,GxrceUnit *u)
{
    const uint8_t *p=RV_PTR(0x2040f818);GxrceUnit again;
    if(!RV_WORD(0x2040f804)||!rv_native_rpc_ready())return RV_STALE;
    memcpy(u->name,p+4,8);u->main_version=rv_be16(p+0x30);u->cmp_version=rv_be16(p+0x32);
    __asm__ __volatile__("" ::: "memory");
    memcpy(again.name,p+4,8);again.main_version=rv_be16(p+0x30);again.cmp_version=rv_be16(p+0x32);
    return rv_equal(u,&again,sizeof(again))&&rv_equal(u,&r->unit,sizeof(again))?RV_OK:RV_STALE;
}
#define D(i,m) {i,64,m}
const RvApi rv_api={1,sizeof(RvApi),16,RV_READ_CAPS,256,rv_call,{0},
 {D(1,0x3fe),D(2,14),D(3,2),D(4,62),D(5,2),D(6,14),D(7,2),D(8,2),
  D(9,0x1fff),D(10,30),D(11,6),D(12,14),D(13,6),D(14,15),D(15,2),D(16,0)}};
