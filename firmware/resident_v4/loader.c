#include "resident.h"
typedef struct {uint32_t valid,generation,bytes,bss,header_crc;} Candidate;
typedef struct {
    uint8_t header[256];Candidate candidates[3];Rv4Validated v;
    uint32_t epochs[12],unit[3],media[4];
} LoadWork;
_Static_assert(sizeof(LoadWork)<=2048,"loader workspace");
static const char sources[3][17]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};
static int unchanged(Rv4Root *r,const LoadWork *w)
{
    uint32_t unit[3];
    rv4_native_unit(unit);
    return !rv4_storage_scope(r)&&!(r->header.flags&RV4_STOP)&&
        rv4_equal(w->epochs,r->epochs,48)&&rv4_equal(w->unit,unit,12)&&
        r->image.heap_begin==RV4_WORD(RV4_HEAP_BEGIN)&&r->image.heap_end==RV4_WORD(RV4_HEAP_END);
}
static int media_same(uint32_t source,const LoadWork *w)
{
    uint32_t now[4];
    return source!=2||(!rv4_native_sd_id(now)&&rv4_equal(now,w->media,16));
}
static int32_t read_one(Rv4Root *r,uint32_t source,uint8_t *p,uint32_t bytes,uint32_t eof,LoadWork *w)
{
    uint32_t done=0,want;int32_t fd,n,result=RV4_OK;uint8_t extra;
    if(source>=3||!p||!bytes)return RV4_ARGUMENT;
    if(!unchanged(r,w))return RV4_STALE;
    if(source==2&&(rv4_native_sd_id(w->media)||!(w->media[0]|w->media[1]|w->media[2]|w->media[3])))return RV4_UNAVAILABLE;
    if(!unchanged(r,w))return RV4_STALE;
    fd=rv4_native_open(sources[source],0);
    if(fd<0)return !unchanged(r,w)?RV4_STALE:fd==-1?RV4_UNAVAILABLE:RV4_IO;
    while(1){
        if(!unchanged(r,w)||!media_same(source,w)){result=RV4_STALE;break;}
        want=bytes-done;if(want>4096)want=4096;
        if(!want&&!eof)break;
        n=rv4_native_read(fd,want?p+done:&extra,want?want:1);
        if(n<0||(uint32_t)n>(want?want:1)){result=RV4_IO;break;}
        if(!want){if(n)result=RV4_LAYOUT;break;}
        if(!n){result=RV4_LAYOUT;break;}
        done+=(uint32_t)n;
    }
    /* A lost scope/media identity prohibits another native I/O, including close. */
    if(!unchanged(r,w)||!media_same(source,w)){
        r->header.flags|=RV4_HANDLE_UNCERTAIN;rv4_retire(r,RV4_STALE);return RV4_STALE;
    }
    n=rv4_native_close(fd);
    if(n){r->header.flags|=RV4_HANDLE_UNCERTAIN;rv4_retire(r,RV4_IO);return RV4_IO;}
    if(!unchanged(r,w)||!media_same(source,w))return RV4_STALE;
    return result;
}
static int32_t probe(Rv4Root *r,uint32_t source,const Rv4Trust *t,LoadWork *w)
{
    Candidate *c=&w->candidates[source];int32_t status;
    c->valid=0;status=read_one(r,source,w->header,256,0,w);
    if(status)return status;
    status=rv4_header(w->header,rv4_be32(w->header+16),t,&w->v);if(status)return status;
    c->valid=1;c->bytes=w->v.file_bytes;c->bss=w->v.bss_bytes;c->generation=w->v.generation;
    c->header_crc=rv4_be32(w->header+20);return RV4_OK;
}
static int choose(const Candidate c[3])
{
    if(c[2].valid)return 2;
    if(!c[0].valid)return c[1].valid?1:-1;
    return c[1].valid&&c[1].generation>c[0].generation?1:0;
}
int32_t rv4_load(Rv4Root *r,const Rv4Trust *trust)
{
    uint32_t i,j,workspace,base=0,bytes,irq;int chosen;int32_t status;
    LoadWork *w;Candidate *c;Rv4Validated *v;uint8_t *p;
    Rv4Event event;Rv4Reply reply;
    if(!rv4_root_valid(r)||trust!=&rv4_trust)return RV4_ARGUMENT;
    status=rv4_storage_scope(r);if(status)return status;
    irq=rv4_irq_save();
    if(r->header.state!=RV4_COLD||r->header.inflight||(r->header.flags&(RV4_STOP|RV4_ATTEMPTED))){
        rv4_irq_restore(irq);return RV4_BUSY;
    }
    r->header.flags|=RV4_ATTEMPTED;r->header.state=RV4_LOADING;
    r->image.heap_begin=RV4_WORD(RV4_HEAP_BEGIN);r->image.heap_end=RV4_WORD(RV4_HEAP_END);
    rv4_irq_restore(irq);
    workspace=rv4_native_alloc(sizeof(*w));
    if(rv4_storage_scope(r)||!workspace||!rv4_allocation(workspace,sizeof(*w),0)){status=RV4_UNAVAILABLE;goto fail;}
    w=RV4_PTR(workspace);rv4_clear(w,sizeof(*w));
    memcpy(w->epochs,r->epochs,48);rv4_native_unit(w->unit);
    c=w->candidates;v=&w->v;
    status=probe(r,2,trust,w);
    if(!unchanged(r,w))goto fail;
    for(j=0;j<3;++j){
        if(j==1){for(i=0;i<2;++i){status=probe(r,i,trust,w);if(!unchanged(r,w))goto fail;}}
        chosen=j?choose(c):(c[2].valid?2:-1);
        if(chosen<0){if(!j)continue;break;}
        bytes=(c[chosen].bytes+c[chosen].bss+3)&~3u;
        if(bytes>RV4_MAX_ALLOCATION){status=RV4_RANGE;goto fail;}
        base=rv4_native_alloc(bytes);
        if(!unchanged(r,w)||!base||!rv4_allocation(base,bytes,0)){status=RV4_UNAVAILABLE;goto fail;}
        p=RV4_PTR(base);status=read_one(r,(uint32_t)chosen,p,c[chosen].bytes,1,w);
        if(!unchanged(r,w))goto fail;
        if(!status)status=rv4_validate(p,c[chosen].bytes,trust,v);
        if(!status&&(v->generation!=c[chosen].generation||v->bss_bytes!=c[chosen].bss||
           rv4_be32(p+20)!=c[chosen].header_crc))status=RV4_STALE;
        if(!status)goto accepted;
        c[chosen].valid=0;
        if(!rv4_allocation(base,bytes,0)){status=RV4_STALE;goto fail;}
        rv4_native_free(base);base=0;
    }
    status=RV4_UNAVAILABLE;goto fail;
accepted:
    for(i=0;i<v->reloc_count;++i){
        const uint8_t *d=p+v->reloc_offset+8*i;
        rv4_put32(p+rv4_be32(d),base+rv4_be32(d+4));
    }
    rv4_clear(p+v->file_bytes,bytes-v->file_bytes);
    r->image.base=base;r->image.inverse=~base;r->image.alloc_bytes=RV4_WORD(base-4);
    r->image.file_bytes=v->file_bytes;r->image.bss_bytes=v->bss_bytes;
    r->image.code_offset=v->code_offset;r->image.code_bytes=v->code_bytes;
    r->image.heap_epoch=r->epochs[RV4_E_HEAP];r->image.link_epoch=r->epochs[RV4_E_LINK];
    memcpy(&r->image.unit_name0,w->unit,12);r->image.generation=v->generation;
    r->image.code_crc=rv4_crc(p+v->code_offset,v->code_bytes);
    memcpy(r->entries,v->entries,sizeof(r->entries));
    rv4_cache_sync();if(!unchanged(r,w)){status=RV4_STALE;goto fail;}
    if(r->header.next_token==~0u){status=RV4_RANGE;goto fail;}
    r->header.session_token=++r->header.next_token;r->header.state=RV4_VALIDATED;
    rv4_clear(&event,sizeof(event));event.version=4;event.bytes=64;
    event.event=RV4_ENTRY_INIT;event.session_token=r->header.session_token;
    event.session_generation=v->generation;event.view_generation=r->epochs[RV4_E_VIEW];
    event.owner_context=RV4_CONTEXT_INIT;
    status=rv4_call(r,RV4_ENTRY_INIT,RV4_CONTEXT_INIT,&event,&reply);
    if(status||reply.action!=RV4_ACTION_PASS||!unchanged(r,w))goto fail;
    irq=rv4_irq_save();
    if(r->header.flags&RV4_STOP){rv4_irq_restore(irq);status=RV4_STALE;goto fail;}
    r->header.capabilities=RV4_CAP_QUERY;
    if(rv4_native_profile.proof_flags&RV4_UI_PROTOCOL_PROVEN)r->header.capabilities|=v->capabilities&(RV4_CAP_UI_PUBLISH|RV4_CAP_UI_HINT);
    if(v->capabilities&~r->header.capabilities){rv4_irq_restore(irq);status=RV4_UNSUPPORTED;goto fail;}
    r->header.state=RV4_READY;RV4_BARRIER();rv4_irq_restore(irq);
    /* Exactly one bounded loader workspace is retained per attempted boot. */
    return RV4_OK;
fail:
    rv4_retire(r,status?status:RV4_STALE);return status?status:RV4_STALE;
}
