#include "internal.h"
#include "gxts.h"

GxtsStatus gxts_bind(const Gxr2View *v,unsigned m,unsigned s,GxtsBinding *out)
{
    static const uint8_t algorithm[]="gxr-recipe-tweak/odds-q12-v2";
    GxtsBinding binding; Gxr2Row row;
    const uint8_t *d,*e,*r,*h,*t; unsigned i,pos,n;
    uint8_t content[411],meta[4+sizeof(algorithm)-1+7*GXR2_PARAM_MAX];
    if(!v || !v->semantic || !out || m>=3 || s<1 || s>16) return GXTS_ARGUMENT;
    t=metadata(v,m,s); n=v->param_slots;
    if(!(t[3*n+1]&1u)) return GXTS_ARGUMENT;
    d=directory(v,m); e=descriptor(v,m,t[3*n]);
    r=v->bytes+be32(d+16)+32+(s-1)*64; h=v->bytes+v->sections[6].offset;
    for(i=0;i<160;++i) binding.identity[i]=0;
    copy(binding.identity,d,12); copy(binding.identity+12,d+32,32);
    binding.identity[44]=r[2]; copy(binding.identity+45,r+4,32);
    binding.identity[77]=r[3]; copy(binding.identity+78,r+36,15);
    content[0]=e[1]; pos=1;
    for(i=0;i<8;++i) { row=gxr2_raw_row(v,e,i); copy(content+pos,row.bytes,row.length); pos+=row.length; }
    copy(content+pos,e+2,2); gxr2_sha256(content,sizeof(content),binding.identity+96);
    put16(meta,2); put16(meta+2,(uint16_t)n);
    copy(meta+4,algorithm,sizeof(algorithm)-1); pos=4+sizeof(algorithm)-1;
    copy(meta+pos,h+32,4*n); pos+=4*n;
    copy(meta+pos,t,3*n); pos+=3*n;
    gxr2_sha256(meta,pos,binding.identity+128);
    for(i=0;i<6;++i)
        if(gxr2_parameter(v,m,s,i+1,&binding.lo[i],&binding.hi[i],&binding.def[i])!=GXR2_OK) return GXTS_ARGUMENT;
    binding.module=(uint8_t)m; binding.slot=(uint8_t)s;
    copy((uint8_t *)out,(const uint8_t *)&binding,sizeof(binding));
    return GXTS_OK;
}

static int values_valid(const GxtsBinding *b,const GxtsState *s)
{
    unsigned i;
    for(i=0;i<6;++i) if(s->values[i]<b->lo[i] || s->values[i]>b->hi[i]) return 0;
    return 1;
}

GxtsStatus gxts_encode(const GxtsBinding *binding,const GxtsState *s,uint8_t out[GXTS_BYTES])
{
    uint8_t b[GXTS_BYTES]; unsigned i;
    if(!binding || !s || !out) return GXTS_ARGUMENT;
    if(!s->generation) return GXTS_GENERATION;
    if(!values_valid(binding,s)) return GXTS_RANGE;
    for(i=0;i<GXTS_BYTES;++i) b[i]=0;
    copy(b,(const uint8_t *)"GXTS",4); put16(b+4,2); put16(b+6,192);
    put32(b+8,GXTS_BYTES); put32(b+12,s->generation);
    copy(b+20,binding->identity,160);
    put16(b+180,6); put16(b+182,8); put32(b+184,192);
    for(i=0;i<6;++i) { put32(b+192+8u*i,i+1); put32(b+196+8u*i,(uint32_t)s->values[i]); }
    put32(b+16,gxr2_crc_zeroed(b,sizeof(b),16,4)); copy(out,b,sizeof(b));
    return GXTS_OK;
}

GxtsStatus gxts_decode(const uint8_t *b,size_t n,const GxtsBinding *binding,GxtsState *out)
{
    GxtsState s; unsigned i,id,seen=0; uint32_t value;
    if(!b || !binding || !out) return GXTS_ARGUMENT;
    if(n!=GXTS_BYTES) return GXTS_LENGTH;
    if(!equal(b,(const uint8_t *)"GXTS",4) || be16(b+4)!=2 || be16(b+6)!=192 ||
       be32(b+8)!=GXTS_BYTES || be16(b+180)!=6 || be16(b+182)!=8 ||
       be32(b+184)!=192 || be32(b+188)) return GXTS_VERSION;
    if(be32(b+16)!=gxr2_crc_zeroed(b,n,16,4)) return GXTS_CRC;
    if(!equal(b+20,binding->identity,160)) return GXTS_IDENTITY;
    s.generation=be32(b+12); if(!s.generation) return GXTS_GENERATION;
    for(i=0;i<6;++i) {
        id=be32(b+192+8u*i);
        if(id<1 || id>6 || (seen&(1u<<id))) return GXTS_VERSION;
        seen|=1u<<id; value=be32(b+196+8u*i);
        s.values[id-1]=value<=INT32_MAX?(int32_t)value:-(int32_t)(UINT32_MAX-value)-1;
    }
    if(!values_valid(binding,&s)) return GXTS_RANGE;
    copy((uint8_t *)out,(const uint8_t *)&s,sizeof(s)); return GXTS_OK;
}

GxtsStatus gxts_select(const uint8_t *a,size_t an,const uint8_t *b,size_t bn,
                     const GxtsBinding *binding,GxtsSelection *out)
{
    GxtsState as,bs; GxtsStatus sa,sb; GxtsSelection result;
    if(!binding || !out || (!a && an) || (!b && bn)) return GXTS_ARGUMENT;
    sa=an?gxts_decode(a,an,binding,&as):GXTS_MISSING;
    sb=bn?gxts_decode(b,bn,binding,&bs):GXTS_MISSING;
    if(sa!=GXTS_OK && sb!=GXTS_OK) return GXTS_MISSING;
    if(sa==GXTS_OK && sb==GXTS_OK && as.generation==bs.generation &&
       (an!=bn || !equal(a,b,an))) return GXTS_CONFLICT;
    result.selected=(sa!=GXTS_OK || (sb==GXTS_OK && bs.generation>as.generation))?1u:0u;
    copy((uint8_t *)&result.state,(const uint8_t *)(result.selected?&bs:&as),sizeof(as));
    result.invalid_mask=(an && sa!=GXTS_OK?1u:0u)|(bn && sb!=GXTS_OK?2u:0u);
    result.io_error_mask=0;
    copy((uint8_t *)out,(const uint8_t *)&result,sizeof(result)); return GXTS_OK;
}

void gxts_defaults(const GxtsBinding *b,GxtsState *out)
{
    unsigned i; out->generation=0;
    for(i=0;i<6;++i) out->values[i]=b->def[i];
}

const char *gxts_status_name(GxtsStatus s)
{
    static const char *const names[]={"OK","ARGUMENT","LENGTH","VERSION","CRC","IDENTITY",
        "RANGE","CONFLICT","MISSING","GENERATION","IO","UNCERTAIN"};
    return (unsigned)s<sizeof(names)/sizeof(names[0])?names[s]:"UNKNOWN";
}
