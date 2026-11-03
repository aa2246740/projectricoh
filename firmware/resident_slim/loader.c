#include "resident.h"
static const char sources[3][17]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};
static int unchanged(RvRoot *r,const uint32_t *e)
{return rv_equal(r->epoch,e,48)&&!(r->flags&RF_STOP);}
/* Every call opens and closes exactly one fd. Allocation happens only after
 * the header call has returned, and the full read uses a new fd. */
static int32_t read_one(RvRoot *r,unsigned source,uint8_t *out,uint32_t length,int eof)
{
    uint32_t epochs[12],n=0,want;int32_t fd,k,result=RV_OK;uint8_t extra;
    memcpy(epochs,r->epoch,48);
    if(source==2&&!(r->flags&RF_SD))return RV_UNAVAILABLE;
    fd=rv_native_open(sources[source],0);
    if(fd<0)return unchanged(r,epochs)?RV_IO:RV_STALE;
    while(result==RV_OK){
        if(!unchanged(r,epochs)){result=RV_STALE;break;}
        want=length-n;
        if(!want&&!eof)break;
        k=rv_native_read(fd,want?out+n:&extra,want?want:1);
        if(k<0||(uint32_t)k>(want?want:1)){result=RV_IO;break;}
        if(!want){if(k)result=RV_VERIFY;break;}
        if(!k){result=RV_VERIFY;break;}
        n+=k;
    }
    if(rv_native_close(fd)!=0&&result==RV_OK)result=RV_IO;
    if(!unchanged(r,epochs))result=RV_STALE;
    return result;
}
static int32_t probe(RvRoot *r,unsigned source,const RvTrust *trust,RvCandidate *c)
{
    uint8_t header[256];int32_t result;
    c->valid=0;result=read_one(r,source,header,256,0);if(result)return result;
    c->bytes=rv_be32(header+16);
    if(rv_header(header,c->bytes,trust))return RV_VERIFY;
    c->generation=rv_be32(header+28);c->bss=rv_be32(header+116);c->valid=1;
    return RV_OK;
}
static __attribute__((noinline)) int32_t discard_main(RvRoot *r)
{
    uint32_t address=r->block,detail;int32_t result;
    r->block=r->inverse=0;result=rv_free_checked(r,address,&detail);
    if(result)r->fault=result;
    return result;
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
    RvCandidate c[3];GxrceView v;RvRequest q;RvReply reply;RvSession *s;
    uint32_t address=0,boot,heap,n=0,i,j,bytes,*ep,epochs[12],detail;int32_t chosen=2,status=RV_VERIFY;uint8_t *work;
    rv_clear(&q,sizeof(q));
    if(!trust)return RV_ARGUMENT;
    if((r->flags&RF_BUSY)||r->inflight)return RV_BUSY;
    if((r->flags&RF_STOP)||r->state==RV_FAILED){rv_ui_abort(r);return RV_FAULTED;}
    r->flags|=RF_BUSY;rv_ui_abort(r);r->state=RV_LOADING;
    memcpy(epochs,r->epoch,48);boot=r->epoch[RV_BOOT_E];heap=r->epoch[RV_HEAP_E];
    s=rv_session(r);if(s&&s->image_bytes)goto init;
    if(r->next_token==~0u){r->fault=RV_RANGE;r->flags|=RF_STOP;goto fail;}
    r->lease=++r->next_token;
    status=probe(r,2,trust,&c[2]);if(status==RV_STALE)goto fail;
    for(j=0;j<3;++j){
        if(j==1)for(i=0;i<2;++i){status=probe(r,i,trust,&c[i]);if(status==RV_STALE)goto fail;}
        chosen=j?rv_choose(c):2;if(chosen<0)break;
        if(!c[chosen].valid)continue;
        bytes=rv_block_bytes(c[chosen].bytes,c[chosen].bss);
        address=rv_native_alloc(bytes);
        if(boot!=r->epoch[RV_BOOT_E]||heap!=r->epoch[RV_HEAP_E]||!address||!rv_heap_span(address,bytes))goto fail;
        r->block=address;r->inverse=~address;r->boot_epoch=boot;r->heap_epoch=heap;
        s=RV_PTR(address);rv_clear(s,sizeof(*s));
        s->leases[0]=(RvLease){r->lease,~r->lease,address,bytes,1};
        s->image_address=address+RV_SESSION_BYTES;work=RV_PTR(s->image_address);
        if(!unchanged(r,epochs)){status=RV_STALE;goto fail;}
        n=c[chosen].bytes;status=read_one(r,(unsigned)chosen,work,n,1);if(status==RV_STALE)goto fail;
        if(!status&&!rv_validate(work,n,trust,&v)&&v.build_number==c[chosen].generation&&v.bss_bytes==c[chosen].bss)goto accepted;
        c[chosen].valid=0;status=discard_main(r);if(status)goto fail;
    }
    goto fail;
accepted:
    s->selected_source=chosen+1;s->bss_bytes=v.bss_bytes;s->image_bytes=n;
    s->code_begin=v.sections[0].offset;s->code_end=s->code_begin+v.sections[0].length;
    s->crc=gxrce_crc32(work,n);
    for(i=0;i<v.sections[1].length;i+=8){
        const uint8_t *d=work+v.sections[1].offset+i;
#ifdef RV_HOST
        rv_put32(work+rv_be32(d),s->image_address+rv_be32(d+4));
#else
        /* The gate proved 4 B patch alignment. The target is big-endian. */
        _Static_assert(__BYTE_ORDER__==__ORDER_BIG_ENDIAN__,"M32R BE relocation");
        *(uint32_t *)(void *)(work+rv_be32(d))=s->image_address+rv_be32(d+4);
#endif
    }
    rv_clear(work+n,bytes-RV_SESSION_BYTES-n);
    rv_cache_sync();if(!unchanged(r,epochs))goto fail;r->state=RV_VALIDATED;
    status=rv_engine(r,v.entry_offset,&q,&reply);
    if(status>RV_CONSUMED||reply.status!=RV_OK||reply.actual!=40)goto fail;
    if(s->entries.version!=1||s->entries.bytes!=40)goto fail;
    ep=&s->entries.init;
    for(j=0;j<9;++j)if(!entry(ep[j],&v))goto fail;
init:
    r->state=RV_VALIDATED;s->capabilities=RV_READ_CAPS;memcpy(s->bindings,r->epoch,48);
    status=rv_engine(r,s->entries.init,&q,&reply);
    if(status>RV_CONSUMED||reply.status!=RV_OK||r->state!=RV_VALIDATED)goto fail;
    {uint32_t irq=rv_irq_save();
     if(!unchanged(r,epochs)||!rv_session(r)){rv_irq_restore(irq);goto fail;}
     s->capabilities=RV_READ_CAPS|(reply.capabilities&(CAP_UI|CAP_S|CAP_W));r->flags&=~RF_BUSY;
     __asm__ __volatile__("" ::: "memory");r->state=RV_READY;rv_irq_restore(irq);}
    return RV_OK;
fail:
    rv_ui_abort(r);s=rv_session(r);
    if(s){
        for(i=0;i<2;++i)if(s->files[i].token){uint32_t fd=s->files[i].fd;s->files[i].token=0;rv_native_close(fd);if(!rv_session(r))break;}
        if(rv_session(r))for(i=1;i<RV_LEASES;++i)if(s->leases[i].token){
            address=s->leases[i].base;s->leases[i].token=0;
            if(rv_free_checked(r,address,&detail))r->fault=RV_IO;
            if(!rv_session(r))break;
        }
        if(rv_session(r))discard_main(r);
    }
    r->lease=0;r->state=RV_FAILED;r->flags&=~RF_BUSY;
    return status<0?status:RV_VERIFY;
}
