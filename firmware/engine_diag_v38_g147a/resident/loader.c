#include "resident.h"
typedef struct {
    uint8_t header[256];RvCandidate candidates[3];GxrceView view;
    RvRequest request;RvReply reply;
    uint32_t epochs[12],read_epochs[12],id[4],now[4];
} RvLoadWork;
static const char sources[3][17]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};
static int unchanged(RvRoot *r,const uint32_t *e)
{
    GxrceUnit unit;rv_unit_snapshot(&unit);
    return r->magic==RV_ROOT_MAGIC&&rv_equal(r->epoch,e,48)&&!(r->flags&RF_STOP)&&
        r->heap_begin==RV_WORD(0x200d3488)&&r->heap_end==RV_WORD(0x200d348c)&&
        rv_equal(&unit,&r->unit,sizeof(unit));
}
/* Every call opens and closes exactly one fd. Allocation happens only after
 * the header call has returned, and the full read uses a new fd. */
static int32_t read_one(RvRoot *r,unsigned source,uint8_t *out,uint32_t length,int eof,RvLoadWork *w)
{
    uint32_t *epochs=w->read_epochs,*id=w->id,*now=w->now,n=0,want;int32_t fd,k,result=RV_OK;uint8_t extra;
    memcpy(epochs,r->epoch,48);
    if(source==2&&(rv_native_sd_id(id)||!(id[0]|id[1]|id[2]|id[3])))return RV_UNAVAILABLE;
    fd=rv_native_open(sources[source],0);
    if(fd<0)return unchanged(r,epochs)?(fd==-1?RV_UNAVAILABLE:RV_IO):RV_STALE;
    while(result==RV_OK){
        if(!unchanged(r,epochs)||(source==2&&(rv_native_sd_id(now)||!rv_equal(id,now,16)))){result=RV_STALE;break;}
        want=length-n;
        if(!want&&!eof)break;
        k=rv_native_read(fd,want?out+n:&extra,want?want:1);
        if(k<0||(uint32_t)k>(want?want:1)){result=RV_IO;break;}
        if(!want){if(k)result=RV_VERIFY;break;}
        if(!k){result=RV_VERIFY;break;}
        n+=k;
    }
    if(rv_native_close(fd)!=0&&result==RV_OK)result=RV_IO;
    if(!unchanged(r,epochs)||(source==2&&(rv_native_sd_id(now)||!rv_equal(id,now,16))))result=RV_STALE;
    return result;
}
static int32_t probe(RvRoot *r,unsigned source,const RvTrust *trust,RvCandidate *c,RvLoadWork *w)
{
    uint8_t *header=w->header;int32_t result;
    c->valid=0;result=read_one(r,source,header,256,0,w);if(result)return result;
    c->bytes=rv_be32(header+16);
    if(rv_header(header,c->bytes,trust))return RV_VERIFY;
    c->generation=rv_be32(header+28);c->bss=rv_be32(header+116);c->valid=1;
    return RV_OK;
}
static __attribute__((noinline)) int32_t discard_main(RvRoot *r)
{
    uint32_t address=r->block;
    if(r->state!=RV_LOADING||!rv_session(r)||r->ui_restore[0]||(r->flags&RF_STOP))return RV_STALE;
    rv_native_free(address);
    r->block=r->inverse=r->code_address=r->code_bytes=r->code_crc=0;
    return RV_OK;
}
static int32_t rv_choose(const RvCandidate c[2])
{
    if(!c[0].valid)return c[1].valid?1:-1;
    return c[1].valid&&c[1].generation>c[0].generation?1:0;
}
static int entry(uint32_t x,const GxrceView *v)
{return !(x&3)&&x>=v->sections[0].offset&&x<=v->sections[0].offset+v->sections[0].length-4;}
int32_t rv_load(RvRoot *r,const RvTrust *trust)
{
    RvLoadWork *w;RvCandidate *c;GxrceView *v;RvRequest *q;RvReply *reply;RvSession *s;
    uint32_t address=0,boot,heap,n=0,i,j,bytes,*ep,*epochs;int32_t chosen=2,status=RV_VERIFY;uint8_t *work;
    if(!trust)return RV_ARGUMENT;
    if((r->flags&RF_BUSY)||r->inflight)return RV_BUSY;
    if(r->state==RV_DISABLED_UNTIL_REBOOT||(r->flags&(RF_STOP|RF_ATTEMPTED)))return RV_FAULTED;
    /* rpc_ready (0x2009359c) loads BSS 0x200d7fd8. Either word still zero
     * means the lens task has not published yet. Leave RV_FACTORY and do
     * not consume the once-per-boot latch, so the next H01 retries. */
#ifdef RV_HOST
    if(!rv_native_rpc_ready()||!RV_WORD(0x2040f804))return RV_STALE;
#else
    {
        uint32_t ready;
        __asm__ volatile(
            "seth %0,#0x200d\n\t"
            "or3 %0,%0,#0x7fd8\n\t"
            "ld %0,@%0\n\t"
            "seth r4,#0x2040\n\t"
            "or3 r4,r4,#0xf804\n\t"
            "ld r4,@r4\n\t"
            "and %0,r4"
            : "=&r"(ready) : : "r4");
        if(!ready)return RV_STALE;
    }
#endif
    r->flags|=RF_ATTEMPTED|RF_BUSY;r->state=RV_LOADING;
    status=rv_native_open(sources[2],0);
    if(status<0)status=rv_native_open(sources[0],0);
    if(status<0)status=rv_native_open(sources[1],0);
    if(status<0){status=RV_UNAVAILABLE;goto fail;}
    if(rv_native_close(status))goto fail;
    /* One bounded unpublished workspace per boot, deliberately retained. */
    address=rv_native_alloc(sizeof(RvLoadWork));
    if(!address||!rv_allocation(address,sizeof(RvLoadWork),0))goto fail;
    w=RV_PTR(address);rv_clear(w,sizeof(*w));
    c=w->candidates;v=&w->view;q=&w->request;reply=&w->reply;epochs=w->epochs;
    memcpy(epochs,r->epoch,48);boot=r->epoch[RV_BOOT_E];heap=r->epoch[RV_HEAP_E];
    r->heap_begin=RV_WORD(0x200d3488);r->heap_end=RV_WORD(0x200d348c);rv_unit_snapshot(&r->unit);
    if(r->next_token==~0u){r->fault=RV_RANGE;r->flags|=RF_STOP;goto fail;}
    r->lease=++r->next_token;r->lease_inverse=~r->lease;
    status=probe(r,2,trust,&c[2],w);if(status&&status!=RV_UNAVAILABLE)r->flags|=RF_QUARANTINE;if(status==RV_STALE)goto fail;
    for(j=0;j<3;++j){
        if(j==1)for(i=0;i<2;++i){status=probe(r,i,trust,&c[i],w);if(status==RV_STALE)goto fail;}
        chosen=j?rv_choose(c):2;if(chosen<0)break;
        if(!c[chosen].valid)continue;
        bytes=rv_block_bytes(c[chosen].bytes,c[chosen].bss);
        address=rv_native_alloc(bytes);
        if(boot!=r->epoch[RV_BOOT_E]||heap!=r->epoch[RV_HEAP_E]||!address||!rv_allocation(address,bytes,0))goto fail;
        r->block=address;r->inverse=~address;r->boot_epoch=boot;r->heap_epoch=heap;
        r->block_bytes=bytes;r->alloc_bytes=RV_WORD(address-4);
        s=RV_PTR(address);rv_clear(s,sizeof(*s));
        s->unit=r->unit;
        s->leases[0]=(RvLease){r->lease,~r->lease,address,bytes,1};
        s->image_address=address+RV_SESSION_BYTES;work=RV_PTR(s->image_address);
        if(!unchanged(r,epochs)){status=RV_STALE;goto fail;}
        n=c[chosen].bytes;status=read_one(r,(unsigned)chosen,work,n,1,w);if(status==RV_STALE)goto fail;
        if(!status&&!rv_validate(work,n,trust,v)&&v->build_number==c[chosen].generation&&v->bss_bytes==c[chosen].bss)goto accepted;
        if(chosen==2&&status!=RV_UNAVAILABLE)r->flags|=RF_QUARANTINE;
        c[chosen].valid=0;status=discard_main(r);if(status)goto fail;
    }
    goto fail;
accepted:
    s->selected_source=chosen+1;s->bss_bytes=v->bss_bytes;s->image_bytes=n;
    s->code_begin=v->sections[0].offset;s->code_end=s->code_begin+v->sections[0].length;
    s->crc=gxrce_crc32(work,n);
    for(i=0;i<v->sections[1].length;i+=8){
        const uint8_t *d=work+v->sections[1].offset+i;
#ifdef RV_HOST
        rv_put32(work+rv_be32(d),s->image_address+rv_be32(d+4));
#else
        /* The gate proved 4 B patch alignment. The target is big-endian. */
        _Static_assert(__BYTE_ORDER__==__ORDER_BIG_ENDIAN__,"M32R BE relocation");
        *(uint32_t *)(void *)(work+rv_be32(d))=s->image_address+rv_be32(d+4);
#endif
    }
    rv_clear(work+n,bytes-RV_SESSION_BYTES-n);
    r->code_address=s->image_address+s->code_begin;r->code_bytes=s->code_end-s->code_begin;
    r->code_crc=rv_code_guard(r->code_address,r->code_bytes);
    rv_cache_sync();if(!unchanged(r,epochs))goto fail;r->state=RV_VALIDATED;
    status=rv_engine(r,v->entry_offset,q,reply);
    if(status>RV_CONSUMED||reply->status!=RV_OK||reply->actual!=40)goto fail;
    if(s->entries.version!=1||s->entries.bytes!=40)goto fail;
    ep=&s->entries.init;
    for(j=0;j<9;++j)if(!entry(ep[j],v))goto fail;
r->state=RV_VALIDATED;s->capabilities=RV_READ_CAPS;memcpy(s->bindings,r->epoch,48);
    status=rv_engine(r,s->entries.init,q,reply);
    if(status>RV_CONSUMED||reply->status!=RV_OK||r->state!=RV_VALIDATED)goto fail;
    {uint32_t irq=rv_irq_save();
     if(!unchanged(r,epochs)||!rv_session(r)){rv_irq_restore(irq);goto fail;}
     s->capabilities=RV_READ_CAPS|(reply->capabilities&(CAP_FILE_WRITE|CAP_UI|CAP_S|CAP_W));
     r->flags=(r->flags&~RF_BUSY)|RF_PUBLISHED;
     __asm__ __volatile__("" ::: "memory");r->state=RV_READY;rv_irq_restore(irq);}
    return RV_OK;
fail:
    rv_retire(r,r->check_failure);
    r->flags&=~RF_BUSY;
    return status<0?status:RV_VERIFY;
}
