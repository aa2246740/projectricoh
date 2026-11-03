#include "resident.h"

static const char sources[3][18]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};
static int unchanged(RvRoot *r,const uint32_t *e) { return rv_equal(r->epoch,e,48)&&!r->flags[F_STOP]; }
static int32_t read_one(RvRoot *r,unsigned source,uint8_t *out,uint32_t *length,int compare)
{
    uint32_t epochs[12],id[4],end_id[4],n=0,want;int32_t fd,k,result=RV_OK;uint8_t chunk[64];
    memcpy(epochs,r->epoch,48);
    if(source==2&&(!r->flags[F_SD]||rv_native_sd_id(id)!=0||!(id[0]|id[1]|id[2]|id[3])))return RV_UNAVAILABLE;
    fd=rv_native_open(sources[source],0);if(fd<0)return RV_IO;
    if(!unchanged(r,epochs))result=RV_STALE;
    while(result==RV_OK) {
        want=compare?64:RV_MAX_FILE-n;if(!want)want=1;
        k=rv_native_read(fd,compare||n==RV_MAX_FILE?chunk:out+n,want);
        if(!unchanged(r,epochs)) {result=RV_STALE;break;}
        if(k<0||(uint32_t)k>want){result=RV_IO;break;}
        if(!k)break;
        if(n+(uint32_t)k>RV_MAX_FILE||(compare&&(n>*length||(uint32_t)k>*length-n||!rv_equal(chunk,out+n,k)))) {result=RV_VERIFY;break;}
        n+=k;
    }
    if(rv_native_close(fd)!=0&&result==RV_OK)result=RV_IO;
    if(!unchanged(r,epochs))result=RV_STALE;
    if(source==2&&(rv_native_sd_id(end_id)!=0||!rv_equal(id,end_id,16)))result=RV_STALE;
    if(compare&&n!=*length)result=RV_VERIFY;
    if(!compare)*length=n;
    return result;
}
int32_t rv_choose(const RvCandidate c[3])
{
    int best=-1;unsigned i;
    for(i=0;i<2;++i)if(c[i].valid) {
        if(best<0||c[i].generation>c[best].generation)best=i;
        else if(c[i].generation==c[best].generation&&(c[i].bytes!=c[best].bytes||c[i].crc!=c[best].crc))
            return c[2].valid&&c[2].generation>c[i].generation?2:RV_CONFLICT;
    }
    if(c[2].valid&&(best<0||c[2].generation>c[best].generation))best=2;
    return best;
}
static int entry(uint32_t x,const GxrceView *v)
{ return !(x&3)&&x>=v->sections[0].offset&&x<=v->sections[0].offset+v->sections[0].length-4; }
int32_t rv_load(RvRoot *r,const RvTrust *trust,const GxrceUnit *unit)
{
    RvCandidate c[3];GxrceView v;RvRequest q;RvReply reply;RvSession *s;
    uint32_t address,boot,heap,n=0,i,j,*ep,epochs[12];int32_t chosen,status=RV_VERIFY;uint8_t *work;
    if(!trust||!unit)return RV_ARGUMENT;
    if(r->busy||r->inflight)return RV_BUSY;
    if(r->flags[F_STOP]||r->state==RV_FAILED)return RV_FAULTED;
    r->busy=1;rv_ui_abort(r);r->state=RV_LOADING;r->capabilities=RV_READ_CAPS;memcpy(epochs,r->epoch,48);boot=r->epoch[RV_BOOT_E];heap=r->epoch[RV_HEAP_E];
    s=rv_session(r);
    if(s&&r->image_bytes) {
        /* Binding changes retain the accepted image. The engine repeats its
         * own current-unit map/stock pin check during pure init. */
        goto init;
    }
    if(r->flags[F_NEXT]==~0u){r->fault=RV_RANGE;r->flags[F_STOP]=1;goto fail;}
    address=rv_native_alloc(RV_BLOCK_BYTES);
    if(boot!=r->epoch[RV_BOOT_E]||heap!=r->epoch[RV_HEAP_E]||!address||!rv_heap_span(address,RV_BLOCK_BYTES))goto fail;
    r->reserved[0]=address;r->reserved[1]=~address;r->flags[F_BOOT]=boot;r->flags[F_HEAP]=heap;
    s=RV_PTR(address);rv_clear(s,sizeof(*s));r->lease=++r->flags[F_NEXT];
    if(!r->lease)goto fail;
    s->leases[0]=(RvLease){r->lease,~r->lease,address,RV_BLOCK_BYTES,1};
    r->image_address=address+((sizeof(*s)+3)&~3u);work=RV_PTR(r->image_address);
    rv_clear(c,sizeof(c));
    for(i=0;i<3;++i) {
        status=read_one(r,i,work,&n,0);
        if(status==RV_STALE)goto fail;
        if(status||rv_validate(work,n,trust,&v))continue;
        c[i]=(RvCandidate){1,v.build_number,n,gxrce_crc32(work,n)};
    }
    chosen=rv_choose(c);if(chosen<0){status=chosen==RV_CONFLICT?RV_CONFLICT:RV_VERIFY;goto fail;}
    /* A CRC collision never makes equal generations equivalent. */
    if(c[0].valid&&c[1].valid&&c[0].generation==c[1].generation) {
        status=read_one(r,0,work,&n,0);if(status==RV_STALE)goto fail;
        if(!status)status=read_one(r,1,work,&n,1);
        if(status==RV_STALE)goto fail;
        if(status) {
            if(c[2].valid&&c[2].generation>c[0].generation)chosen=2;
            else {status=RV_CONFLICT;goto fail;}
        }
    }
    if(read_one(r,chosen,work,&n,0)||rv_validate(work,n,trust,&v)||
       n!=c[chosen].bytes||v.build_number!=c[chosen].generation||gxrce_crc32(work,n)!=c[chosen].crc)goto fail;
    if(chosen<2&&c[2].valid&&c[2].generation==c[chosen].generation&&read_one(r,2,work,&n,1))r->fault=RV_CONFLICT;
    r->selected_source=chosen+1;r->generation=v.build_number;r->source_bytes=n;
    r->entry_offset=v.entry_offset;r->bss_bytes=v.bss_bytes;r->image_bytes=n;
    s->code_begin=v.sections[0].offset;s->code_end=s->code_begin+v.sections[0].length;s->crc=c[chosen].crc;
    for(i=0;i<v.sections[1].length;i+=8) {
        const uint8_t *d=work+v.sections[1].offset+i;
        rv_put32(work+rv_be32(d),r->image_address+rv_be32(d+4));
    }
    rv_clear(work+n,v.bss_bytes);rv_cache_sync();if(!unchanged(r,epochs))goto fail;r->state=RV_VALIDATED;
    rv_clear(&q,sizeof(q));q.args[10]=address+offsetof(RvSession,entries);q.args[11]=40;
    status=rv_engine(r,v.entry_offset,&q,&reply);
    if(status>RV_CONSUMED||reply.status!=RV_OK||reply.actual!=40)goto fail;
    if(s->entries.version!=1||s->entries.bytes!=40)goto fail;
    ep=&s->entries.init;
    for(j=0;j<9;++j) if(!entry(ep[j],&v))goto fail;
init:
    s->unit=*unit;r->state=RV_VALIDATED;
    s->bindings[0]=r->epoch[RV_LINK_E];s->bindings[1]=r->epoch[RV_UNIT_E];
    s->bindings[2]=r->epoch[RV_S_E];s->bindings[3]=r->epoch[RV_VIEW_E];
    rv_clear(&s->init_wire,sizeof(s->init_wire));s->init_wire.header.version=1;s->init_wire.header.bytes=36;
    s->init_wire.image_address=r->image_address;s->init_wire.image_bytes=r->image_bytes;
    rv_clear(&q,sizeof(q));q.args[10]=r->reserved[0]+offsetof(RvSession,init_wire);q.args[11]=36;
    status=rv_engine(r,s->entries.init,&q,&reply);
    if(status>RV_CONSUMED||reply.status!=RV_OK||r->state!=RV_VALIDATED||
       s->bindings[0]!=r->epoch[RV_LINK_E]||s->bindings[1]!=r->epoch[RV_UNIT_E])goto fail;
    {uint32_t irq=rv_irq_save();
     if(!unchanged(r,epochs)||!rv_session(r)){rv_irq_restore(irq);goto fail;}
     r->capabilities=RV_READ_CAPS|(reply.capabilities&(CAP_UI|CAP_S|CAP_W));r->busy=0;
     __asm__ __volatile__("" ::: "memory");r->state=RV_READY;rv_irq_restore(irq);}

    return RV_OK;
fail:
    r->capabilities=RV_READ_CAPS;rv_ui_abort(r);
    s=rv_session(r);
    if(s) {
        for(i=0;i<2;++i)if(r->files[i].token){uint32_t fd=r->files[i].fd;r->files[i].token=0;rv_native_close(fd);if(!rv_session(r))break;}
        if(rv_session(r))for(i=1;i<RV_LEASES;++i)if(s->leases[i].token){address=s->leases[i].base;s->leases[i].token=0;rv_native_free(address);if(!rv_session(r))break;}
        if(rv_session(r)){address=r->reserved[0];r->reserved[0]=r->reserved[1]=0;rv_native_free(address);}
    }
    r->image_address=0;r->image_bytes=0;r->lease=0;r->state=RV_FAILED;r->busy=0;
    return status<0?status:RV_VERIFY;
}
