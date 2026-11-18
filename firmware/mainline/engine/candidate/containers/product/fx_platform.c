/* Offline review prototype. One attempt, held until resident retirement. */
#define RV_ENGINE_SERVICES 1
#include "fx_store.h"
#include "../../engine_services/engine_services.h"
static RvLeaseInfo library;
static uint32_t allocation_bytes;
static uint32_t allocation_attempted;
static int allocation_live(RvRoot *r)
{
    RvSession *s;unsigned i;
    if(!library.base||!library.token||library.length!=65536||
       library.boot_epoch!=r->epoch[RV_BOOT_E]||library.heap_epoch!=r->epoch[RV_HEAP_E]||
       !rv_heap_span(library.base,65536)||!rv_heap_span(library.base-12,12))return 0;
    s=rv_session(r);
    /* Root-lease changes make rv_session return null. Walking it faults. */
    if(!s)return 0;
    for(i=1;i<RV_LEASES;++i)if(s->leases[i].token==library.token&&
       s->leases[i].inverse==~library.token&&s->leases[i].base==library.base&&
       s->leases[i].length==65536&&s->leases[i].usage==5)
        return rv_allocation(library.base,65536,allocation_bytes);
    return 0;
}
int fx_io_live(void)
{
    RvRoot *r=RV_PTR(RV_ROOT);unsigned i;
    if(!rv_root_valid(r)||(r->state!=RV_VALIDATED&&r->state!=RV_READY)||
       (r->flags&RF_STOP)||!allocation_live(r)||fx_store.stamp.lease!=library.token||
       fx_store.stamp.region!=library.base)return 0;
    for(i=0;i<12;++i)if(i!=RV_VIEW_E&&i!=RV_S_E&&i!=RV_IO_E&&r->epoch[i]!=fx_store.stamp.epochs[i])return 0;
    return 1;
}
int32_t fx_io_open(const char *p){return rv_native_open(p,0);}
int32_t fx_io_read(int32_t fd,void *p,uint32_t n){return rv_native_read(fd,p,n);}
int32_t fx_io_close(int32_t fd){return rv_native_close(fd);}
uint8_t *fx_io_target(uint32_t p){return RV_PTR(p);}
/* This target is the allocator's cached CPU alias, exactly as for DAT data.
 * The file wrapper copies bytes to it with CPU stores. It is never passed
 * to a pixel DMA or switched to another alias. Silicon still needs testing. */
void fx_io_cache_prepare(void){}
int32_t fx_io_stamp(FxStamp *s)
{
    RvRoot *r=RV_PTR(RV_ROOT);RvRequest q;RvReply reply;
    uint32_t i,any=0,view=RV_WORD(0x205d9c00),activity=RV_WORD(0x205d9bf8);
    if(!rv_root_valid(r)||r->state!=RV_VALIDATED||!r->inflight||
       (r->flags&RF_STOP)||!(r->flags&RF_SD)||!r->lease)return -5;
    if(RV_WORD(0x200c0dd0)!=0x808bc000u||RV_WORD(0x200c0dd4)!=0x076c0000u)return -10;
    if(!((view==5&&activity==0)||(view==56&&activity==8&&RV_BYTE(0x2022f5ac)==7))||
       (r->flags&RF_PUBLISHED)||r->ui_block||RV_BYTE(0x205da00b)||
       !RV_WORD(0x200d7fd8)||!RV_WORD(0x2040f804)||!rv_native_rpc_ready())return -5;
    if(!library.base){
        if(allocation_attempted)return -1;
        allocation_attempted=1;
        rv_clear(&q,sizeof(q));rv_clear(&library,sizeof(library));
        q.version=1;q.bytes=64;q.args[0]=q.args[1]=r->lease;
        for(i=0;i<4;i++)q.args[2+i]=r->epoch[i];
        q.args[6]=r->epoch[RV_VIEW_E];q.args[7]=r->epoch[RV_S_E];
        q.args[8]=65536;q.args[9]=5;q.args[10]=(uint32_t)(uintptr_t)&library;q.args[11]=32;
        library.header.version=1;library.header.bytes=32;
        if(rv_service(r,RV_LEASE,1,&q,&reply)||!library.base||library.length!=65536)return -1;
        allocation_bytes=RV_WORD(library.base-4);
    }
    if(!allocation_live(r))return -5;
    for(i=0;i<12;i++)s->epochs[i]=r->epoch[i];
    s->lease=library.token;s->descriptor=0;s->descriptor2=s->descriptor3=0;
    s->raw_size=allocation_bytes;s->rounded_size=65536;
    s->region=library.base;s->capacity=65536;s->view=view;s->activity=activity;
    s->rpc=RV_WORD(0x200d7fd8);s->pending=RV_BYTE(0x205da00b);
    if(rv_native_sd_id(s->cid))return -5;
    for(i=0;i<16;i++)any|=s->cid[i];
    return any?0:-5;
}
