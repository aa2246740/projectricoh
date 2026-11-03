#include "abi.h"
static const char path[]="/IROM/GXRTR4.EXT";
static int scope(Bv4Scope *s)
{
    return !bv4_native_scope(s)&&s->boot_instance&&s->heap_epoch&&s->owner&&s->mount_epoch&&
        s->phase==BV4_BOOT_PHASE&&s->proofs==BV4_REQUIRED_PROOFS&&!s->reserved0&&!s->reserved1;
}
static int current(Bv4Root *r)
{
    Bv4Scope s;int valid;
    if(r->flags&BV4_SCOPE_LOST)return 0;
    valid=scope(&s)&&rv4_equal(&s,&r->scope,sizeof(s))&&
        r->heap_begin==RV4_WORD(RV4_HEAP_BEGIN)&&r->heap_end==RV4_WORD(RV4_HEAP_END);
    if(!valid)r->flags|=BV4_SCOPE_LOST;
    return valid;
}
static int32_t read_exact(Bv4Root *r,int32_t fd,uint8_t *p,uint32_t bytes)
{
    uint32_t want;int32_t n;
    while(bytes){
        if(!current(r))return RV4_STALE;
        want=bytes>4096?4096:bytes;n=rv4_native_read(fd,p,want);
        if(n<=0||(uint32_t)n>want)return n<0?RV4_IO:RV4_LAYOUT;
        p+=n;bytes-=(uint32_t)n;
    }
    return current(r)?RV4_OK:RV4_STALE;
}
int32_t bv4_boot(Bv4Root *r)
{
    Bv4Scope s;Bv4Validated v;uint8_t header[BV4_HEADER_BYTES],digest[32],extra,*p;
    uint32_t irq,i,base=0,bytes=0;int32_t fd=-1,status=RV4_UNKNOWN,n;
    if(!r)return RV4_ARGUMENT;
    if(!scope(&s))return RV4_UNKNOWN;
    /* Only a proved cold boot may initialize this root. No warm reset/reload. */
    irq=rv4_irq_save();
    for(i=0;i<sizeof(*r);++i)if(((const uint8_t *)r)[i]!=255){
        rv4_irq_restore(irq);return RV4_STALE;
    }
    rv4_clear(r,sizeof(*r));r->scope=s;r->heap_begin=RV4_WORD(RV4_HEAP_BEGIN);
    r->heap_end=RV4_WORD(RV4_HEAP_END);r->state=BV4_LOADING;r->flags=BV4_FACTORY;
    r->magic=BV4_MAGIC;RV4_BARRIER();rv4_irq_restore(irq);
    if(!bv4_trust.pin_enabled){status=RV4_IDENTITY;goto fail;}
    if(r->heap_begin!=0x20704800||r->heap_end!=0x20744800||!current(r))goto fail;
    fd=rv4_native_open(path,0);
    if(fd<0){status=fd==-1?RV4_UNAVAILABLE:RV4_IO;goto fail;}
    status=read_exact(r,fd,header,sizeof(header));if(status)goto fail;
    status=bv4_header(header,&v);if(status)goto fail;
    bytes=(v.file_bytes+v.bss_bytes+3)&~3u;
    if(!current(r)){status=RV4_STALE;goto fail;}
    base=rv4_native_alloc(bytes);
    if(!current(r)||!base||!rv4_allocation(base,bytes,0)){status=RV4_UNAVAILABLE;goto fail;}
    p=RV4_PTR(base);memcpy(p,header,sizeof(header));
    status=read_exact(r,fd,p+sizeof(header),v.file_bytes-sizeof(header));if(status)goto fail;
    if(!current(r)){status=RV4_STALE;goto fail;}
    n=rv4_native_read(fd,&extra,1);
    if(n){status=n<0?RV4_IO:RV4_LAYOUT;goto fail;}
    if(!current(r)){status=RV4_STALE;goto fail;}
    n=rv4_native_close(fd);fd=-1;
    if(n){r->flags|=BV4_HANDLE_UNCERTAIN;status=RV4_IO;goto fail;}
    if(!current(r)){status=RV4_STALE;goto fail;}
    bv4_sha256(p,v.file_bytes,digest);
    if(!rv4_equal(digest,bv4_trust.approved_file_sha256,32)){status=RV4_IDENTITY;goto fail;}
    status=bv4_relocate(p,base,&v);if(status)goto fail;
    rv4_clear(p+v.file_bytes,bytes-v.file_bytes);
    r->base=base;r->inverse=~base;r->alloc_bytes=RV4_WORD(base-4);
    r->file_bytes=v.file_bytes;r->bss_bytes=v.bss_bytes;r->code_offset=v.code_offset;
    r->code_bytes=v.code_bytes;r->init_offset=v.init_offset;r->hook_offset=v.hook_offset;
    memcpy(r->extension_id,p+124,16);
    bv4_sha256(p+v.code_offset,v.code_bytes,r->code_sha256);
    rv4_cache_sync();if(!current(r)){status=RV4_STALE;goto fail;}
    /* INIT may prepare private BSS only. It may not publish UI, callbacks or DAT.
     * The approved extension must prove that contract; no such target is supplied. */
    r->flags=(r->flags&~BV4_FACTORY)|BV4_EVER_ENTERED;r->active_calls=1;
    status=bv4_invoke_init(base+v.init_offset,base,base+v.file_bytes,v.bss_bytes);
    r->active_calls=0;if(status)goto fail;
    bv4_sha256(p+v.code_offset,v.code_bytes,digest);
    if(!rv4_equal(digest,r->code_sha256,32)){status=RV4_IDENTITY;goto fail;}
    irq=rv4_irq_save();
    if(!current(r)||r->state!=BV4_LOADING){rv4_irq_restore(irq);status=RV4_STALE;goto fail;}
    r->flags|=BV4_EVER_READY;r->state=BV4_READY;RV4_BARRIER();rv4_irq_restore(irq);
    return RV4_OK;
fail:
    if(fd>=0){
        if(current(r)){
            if(rv4_native_close(fd))r->flags|=BV4_HANDLE_UNCERTAIN;
        }else r->flags|=BV4_HANDLE_UNCERTAIN;
    }
    /* A block that has ever executed, or lost its heap proof, is quarantined. */
    if(base&&!(r->flags&BV4_EVER_ENTERED)&&current(r)&&rv4_allocation(base,bytes,0)){
        rv4_native_free(base);r->base=0;
    }else if(base)r->flags|=BV4_QUARANTINED;
    if(r->flags&(BV4_EVER_ENTERED|BV4_HANDLE_UNCERTAIN))r->flags&=~BV4_FACTORY;
    r->state=BV4_DISABLED;r->fault=(uint32_t)status;RV4_BARRIER();return status;
}
