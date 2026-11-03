#include "panel_gxts.h"
#include "../../card_container_v2/internal.h"

void pn_gxts_crc_field(const uint8_t *p,size_t n,uint8_t out[32])
{ uint32_t c=gxr2_crc32(p,n);pn_zero(out,32);put32(out,c); }

/* gxts_bind needs this accessor, not the upstream SHA semantic validator.
 * Input views already passed the core's complete CRC semantic validation. */
#ifndef PN_GXTS_SHARED_PARAMETER
Gxr2Status gxr2_parameter(const Gxr2View *v,unsigned m,unsigned s,uint32_t id,int32_t *lo,int32_t *hi,int32_t *def)
{
    const uint8_t *h,*t,*d;uint32_t ids,off;unsigned i;
    if(!v || !v->semantic || !v->bytes || !lo || !hi || !def || m>=3 || s<1 || s>16 ||
       !id || v->param_slots>GXR2_PARAM_MAX || v->sections[6].length<32 ||
       v->sections[6].offset>v->length || v->sections[6].length>v->length-v->sections[6].offset ||
       v->sections[2].offset>v->length || 192>v->length-v->sections[2].offset) return GXR2_ARGUMENT;
    h=v->bytes+v->sections[6].offset;ids=be32(h+16);
    if(ids>v->sections[6].length || 4u*v->param_slots>v->sections[6].length-ids)return GXR2_TWEAK;
    d=directory(v,m);off=be32(d+24);
    if(off>v->length || (uint32_t)v->record_bytes*16>v->length-off || v->record_bytes<3u*v->param_slots+4)return GXR2_TWEAK;
    t=v->bytes+off+(s-1)*v->record_bytes;
    for(i=0;i<v->param_slots;i++)if(be32(h+ids+4*i)==id) {
        *lo=signed_byte(t[3*i]);*hi=signed_byte(t[3*i+1]);*def=signed_byte(t[3*i+2]);return GXR2_OK;
    }
    return GXR2_TWEAK;
}
#endif
int32_t pn_gxts_bind(PnGxts *a,PsStore *store,const Gxr2View *v,const EngRecipeRef *r,const uint8_t indices[6])
{
    GxtsBinding b;const uint8_t *d,*e;Gxr2Row row;uint32_t crc;unsigned i;
    if(!v || !r || !v->semantic || r->unit>2 || r->slot<1 || r->slot>16)return RV_ARGUMENT;
    if(gxts_bind(v,r->unit,r->slot,&b)!=GXTS_OK)return RV_VERIFY;
    d=directory(v,r->unit);e=descriptor(v,r->unit,0);
    crc=gxr2_crc_add(gxr2_crc_begin(),v->bytes+be32(d+12),128);
    for(i=0;i<8;i++){row=gxr2_raw_row(v,e,i);if(!row.bytes)return RV_VERIFY;crc=gxr2_crc_add(crc,row.bytes,row.length);}
    crc=gxr2_crc_end(gxr2_crc_add(crc,e+2,2));pn_zero(b.identity+12,32);put32(b.identity+12,crc);
    return pn_gxts_attach(a,store,&b,r,indices);
}
