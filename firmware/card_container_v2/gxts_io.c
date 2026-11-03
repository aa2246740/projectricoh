#include "internal.h"
#include "gxts.h"

static int io_valid(const GxtsIO *io)
{ return io && io->open && io->read && io->write && io->close && io->remove && io->rename_temp; }
static int binding_valid(const GxtsBinding *b)
{ return b && b->module<3 && b->slot>=1 && b->slot<=16; }

static GxtsStatus read_object(const GxtsIO *io,const GxtsBinding *b,unsigned which,
                              uint8_t bytes[257],size_t *length)
{
    uint32_t handle,actual,pos=0,request; int rc,failed=0;
    *length=0;
    rc=io->open(io->context,b->module,b->slot-1u,which,0,&handle);
    if(rc) return rc==1?GXTS_MISSING:GXTS_IO;
    /* Every successful short read advances pos. Zero is EOF. At most 257
     * positive reads and one EOF; no retry of a failed or zero read. */
    while(pos<257) {
        request=257-pos; if(request>256) request=256; actual=0;
        rc=io->read(io->context,handle,bytes+pos,request,&actual);
        if(rc || actual>request) { failed=1; break; }
        pos+=actual; if(!actual) break;
    }
    rc=io->close(io->context,handle);
    if(rc) return GXTS_UNCERTAIN;
    if(failed) return GXTS_IO;
    *length=pos;
    return GXTS_OK;
}

GxtsStatus gxts_load(const GxtsIO *io,const GxtsBinding *b,GxtsSelection *out)
{
    uint8_t a[257],bb[257]; size_t an,bn; GxtsStatus sa,sb,s; GxtsSelection result;
    if(!io_valid(io) || !binding_valid(b) || !out) return GXTS_ARGUMENT;
    sa=read_object(io,b,GXTS_A,a,&an); sb=read_object(io,b,GXTS_B,bb,&bn);
    if(sa!=GXTS_OK) an=0;
    if(sb!=GXTS_OK) bn=0;
    s=gxts_select(a,an,bb,bn,b,&result);
    if(s==GXTS_MISSING && (sa==GXTS_IO || sb==GXTS_IO || sa==GXTS_UNCERTAIN || sb==GXTS_UNCERTAIN)) return GXTS_IO;
    if(s!=GXTS_OK) return s;
    if(sa!=GXTS_OK && sa!=GXTS_MISSING) result.invalid_mask|=1;
    if(sb!=GXTS_OK && sb!=GXTS_MISSING) result.invalid_mask|=2;
    result.io_error_mask=(sa!=GXTS_OK && sa!=GXTS_MISSING?1u:0u)|(sb!=GXTS_OK && sb!=GXTS_MISSING?2u:0u);
    copy((uint8_t *)out,(const uint8_t *)&result,sizeof(result)); return GXTS_OK;
}

GxtsStatus gxts_save(const GxtsIO *io,const GxtsBinding *b,const int32_t values[6],GxtsSelection *out)
{
    uint8_t bytes[GXTS_BYTES],back[257]; size_t n;
    GxtsState state,decoded; GxtsSelection old,result; GxtsStatus s;
    uint32_t handle,pos=0,actual,request; unsigned target,i; int rc,failed=0,have_old;
    if(!io_valid(io) || !binding_valid(b) || !values || !out) return GXTS_ARGUMENT;
    state.generation=1;
    for(i=0;i<6;++i) state.values[i]=values[i];
    s=gxts_encode(b,&state,bytes); if(s!=GXTS_OK) return s;
    s=gxts_load(io,b,&old); have_old=s==GXTS_OK;
    if(!have_old && s!=GXTS_MISSING) return s;
    if(have_old && old.io_error_mask) return GXTS_IO;
    if(have_old && old.state.generation==UINT32_MAX) return GXTS_GENERATION;
    state.generation=have_old?old.state.generation+1u:1u;
    target=have_old?1u-old.selected:0u;
    s=gxts_encode(b,&state,bytes); if(s!=GXTS_OK) return s;
    rc=io->remove(io->context,b->module,b->slot-1u,GXTS_TEMP);
    if(rc!=0 && rc!=1) return GXTS_IO;
    rc=io->open(io->context,b->module,b->slot-1u,GXTS_TEMP,1,&handle);
    if(rc) return GXTS_IO;
    while(pos<GXTS_BYTES) {
        request=GXTS_BYTES-pos; actual=0;
        rc=io->write(io->context,handle,bytes+pos,request,&actual);
        if(rc || !actual || actual>request) { failed=1; break; }
        pos+=actual;
    }
    rc=io->close(io->context,handle);
    if(rc || failed) return GXTS_UNCERTAIN;
    s=read_object(io,b,GXTS_TEMP,back,&n);
    if(s!=GXTS_OK || n!=GXTS_BYTES || !equal(bytes,back,GXTS_BYTES) ||
       gxts_decode(back,n,b,&decoded)!=GXTS_OK) return GXTS_UNCERTAIN;
    /* First install never deletes a formal copy without a valid other copy. */
    if(have_old) {
        rc=io->remove(io->context,b->module,b->slot-1u,target);
        if(rc!=0 && rc!=1) return GXTS_UNCERTAIN;
    }
    if(io->rename_temp(io->context,b->module,b->slot-1u,target)) return GXTS_UNCERTAIN;
    s=read_object(io,b,target,back,&n);
    if(s!=GXTS_OK || n!=GXTS_BYTES || !equal(bytes,back,GXTS_BYTES) ||
       gxts_decode(back,n,b,&decoded)!=GXTS_OK) return GXTS_UNCERTAIN;
    copy((uint8_t *)&result.state,(const uint8_t *)&decoded,sizeof(decoded));
    result.selected=target; result.invalid_mask=0; result.io_error_mask=0;
    copy((uint8_t *)out,(const uint8_t *)&result,sizeof(result)); return GXTS_OK;
}
