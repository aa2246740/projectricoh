#include "internal.h"
#include "../../../fx_pool.h"

Gxr2Status gxr2_tweak_layout(const Gxr2View *v,uint16_t *params,uint16_t *stride)
{
    const Gxr2Section *s=&v->sections[6];
    const uint8_t *t=v->bytes+s->offset;
    uint32_t n,r,off;
    if(s->length<32 || !equal(t,(const uint8_t *)"GXTM",4) ||
       be16(t+4)!=2 || be16(t+6)!=32) return GXR2_LAYOUT;
    n=be16(t+8); r=align4(3u*n+4u); off=32u+4u*n;
    if(n<8 || n>GXR2_PARAM_MAX || be16(t+10)!=3 || be16(t+12)!=16 ||
       be16(t+14)!=r || be32(t+16)!=32 || be32(t+20)!=off ||
       be32(t+24)!=48u*r || be32(t+28) || (s->length!=off+48u*r && !(v->build_number==175 && n==8 && s->length==9568))) return GXR2_LAYOUT;
    *params=(uint16_t)n; *stride=(uint16_t)r;
    return GXR2_OK;
}

Gxr2Status gxr2_pool_layout(const Gxr2View *v)
{
    static const uint16_t lengths[4]={62,33,96,56},limits[4]={144,240,48,48};
    const Gxr2Section *s=&v->sections[5];
    const uint8_t *p=v->bytes+s->offset,*d,*b;
    uint32_t next=80,n,len; unsigned i;
    if(s->length<80 || !equal(p,(const uint8_t *)"GXDP",4) ||
       be16(p+4)!=2 || be16(p+6)!=80 || be32(p+8)!=s->length ||
       be16(p+12)!=16 || be16(p+14)!=4) return GXR2_LAYOUT;
    for(i=0;i<3;++i) {
        d=directory(v,i); n=d[30]; len=16u+20u*n;
        if(n<1 || n>16 || be32(d+20)!=s->offset+next || be16(d+28)!=len ||
           next>s->length || len>s->length-next) return GXR2_LAYOUT;
        next+=len;
    }
    for(i=0;i<4;++i) {
        b=p+16+12u*i; n=be16(b); len=n*lengths[i];
        if(n<1 || n>limits[i] || be16(b+2)!=lengths[i] || be32(b+4)!=next ||
           next>s->length || align4(len)>s->length-next) return GXR2_LAYOUT;
        next+=align4(len);
    }
    return next==be32(p+64)&&fx_area(v)?GXR2_OK:GXR2_LAYOUT;
}


static void view_copy(Gxr2View *out,const Gxr2View *v)
{
    unsigned i;
    out->bytes=v->bytes; out->length=v->length; out->build_number=v->build_number;
    out->entry_offset=v->entry_offset; out->bss_bytes=v->bss_bytes;
    for(i=0;i<7;++i) { out->sections[i].offset=v->sections[i].offset; out->sections[i].length=v->sections[i].length; }
    out->param_slots=v->param_slots; out->record_bytes=v->record_bytes;
    out->selected_module=v->selected_module; out->executable=v->executable; out->semantic=v->semantic;
}

#if USER_SLOTS_R4
/* Catalogue bytes 228..255 are zero, or one or two ancestor identities.
 * Byte 228 is the count. Each identity is the next 5 bytes. The unused
 * tail stays zero. An all-zero identity is not a declaration. */
static int __attribute__((noinline)) ancestor_ok(const uint8_t *p)
{
    unsigned n=p[228],i;
    if(!n)return zero(p+228,28);
    if(n>2||!zero(p+229+5u*n,27u-5u*n))return 0;
    for(i=0;i<n;++i)if(zero(p+229+5u*i,5))return 0;
    return 1;
}
#endif
static Gxr2Status gate_validate(const uint8_t *p,size_t length,const Gxr2Trust *trust,
                            const Gxr2Unit *unit,unsigned options,Gxr2View *out,uint32_t private_base)
{
    static const uint8_t names[3][8]={"jlaunch","qlaunch","l08firm"};
    static const uint8_t stub[16]="HOSTSTUB";
    static Gxr2View v; Gxr2Status status; Gxr2Row row;
    const uint8_t *d,*e,*t;
    uint32_t next,off,len,flags,patch,target,previous=0,c;
    unsigned i,j,n,selected=3;int catalog;
    if(!p || !trust || !unit || !out || (options&~1u)) return GXR2_ARGUMENT;
    if(length<256 || length>98304) return GXR2_LENGTH;
    catalog=equal(p,(const uint8_t *)"GXRCL001",8)||equal(p,(const uint8_t *)"GXRCL002",8);
    if((!catalog&&!equal(p,(const uint8_t *)"GXRCE001",8)) || be16(p+8)!=1 || be16(p+10)!=256 ||
       be16(p+32)!=1 || be16(p+34)!=3 || !equal(p+36,(const uint8_t *)"M32B",4) ||
       be16(p+40)!=0x151 || be16(p+42) || be16(p+44)!=7 || be16(p+46)!=3) return GXR2_VERSION;
    if(be32(p+16)!=length || !be32(p+28) || be32(p+116)>114688-length) return GXR2_LENGTH;
    flags=be32(p+12);
#if USER_SLOTS_R4
    if((catalog?flags!=2:flags>1) || !zero(p+122,6) || !(catalog?ancestor_ok(p):zero(p+228,28))) return GXR2_FLAGS;
#else
    if((catalog?flags!=2:flags>1) || !zero(p+122,6) || !zero(p+228,28)) return GXR2_FLAGS;
#endif
    if(be32(p+20)!=gxr2_crc_zeroed(p,256,20,4) ||
       (!private_base && be32(p+24)!=gxr2_crc32(p+256,length-256))) return GXR2_CRC;
    if(!equal(p+48,trust->body_sha256,32)) return GXR2_BODY_ID;
    if(!equal(p+80,trust->resident_build_id,32) || !equal(p+212,trust->resident_abi_id,16)) return GXR2_RESIDENT_ID;
    if(unit->main_version!=0x151 || unit->cmp_version) return GXR2_MODULE_ID;
    for(i=0;i<3;++i) {
        if(!equal(trust->modules[i].unit.name,names[i],8) ||
           trust->modules[i].unit.main_version!=0x151 || trust->modules[i].unit.cmp_version) return GXR2_MODULE_ID;
        if(equal(unit->name,names[i],8)) selected=i;
    }
    if(selected==3) return GXR2_MODULE_ID;
    v.bytes=p; v.length=(uint32_t)length; v.build_number=be32(p+28);
    v.entry_offset=be32(p+112); v.bss_bytes=be32(p+116);
    v.selected_module=(uint8_t)selected; v.executable=(uint8_t)(!catalog&&flags==0); v.semantic=0;
    next=256;
    for(i=0;i<7;++i) {
        d=p+128+12u*i; off=be32(d+4); len=be32(d+8);
        if(be16(d)!=i+1 || be16(d+2) || off!=next || (off&3u) || (len&3u) ||
           off>length || len>length-off || (!len && i!=1 && !(catalog&&i==0))) return GXR2_LAYOUT;
        v.sections[i].offset=off; v.sections[i].length=len; next=off+len;
    }
    if(next!=length || (catalog?v.sections[0].length!=0:(v.sections[0].length<16 || v.sections[0].length>69632)) ||
       v.sections[1].length>2048 || v.sections[2].length!=192 ||
       v.sections[3].length!=456 || v.sections[4].length!=3168) return GXR2_LAYOUT;
    if(catalog?(v.entry_offset||v.bss_bytes||v.sections[1].length):((v.entry_offset&3u) || v.entry_offset<256 || v.entry_offset>256+v.sections[0].length-4)) return GXR2_LAYOUT;
    n=be16(p+120);
    if(n>256 || v.sections[1].length!=n*8u) return GXR2_RELOCATION;
    for(i=0;i<n;++i) {
        d=p+v.sections[1].offset+8u*i; patch=be32(d); target=be32(d+4);
        if(patch<256 || patch>256+v.sections[0].length-4 || (patch&3u) ||
           (i && patch<=previous) || target<256 || target>=length+v.bss_bytes ||
           be32(p+patch)!=private_base+target) return GXR2_RELOCATION;
        previous=patch;
    }
    if(catalog) { if(n||private_base)return GXR2_RELOCATION; } else if(flags) {
        if(!(options&GXR2_HOST_ONLY) || v.sections[0].length!=16 || !equal(p+256,stub,16) ||
           v.bss_bytes || n || v.entry_offset!=256 || !zero(p+80,32)) return GXR2_PLACEHOLDER;
    } else if(zero(p+80,32) || equal(p+256,stub,16)) return GXR2_PLACEHOLDER;
    status=gxr2_tweak_layout(&v,&v.param_slots,&v.record_bytes);
    if(status!=GXR2_OK) return status;
    t=p+v.sections[6].offset;
    for(i=0;i<3;++i) {
        d=directory(&v,i);
        if(!unit_equal(d,&trust->modules[i].unit) || d[31]) return GXR2_MODULE_ID;
        if(be32(d+12)!=v.sections[3].offset+152u*i || be32(d+16)!=v.sections[4].offset+1056u*i ||
           be32(d+24)!=v.sections[6].offset+be32(t+20)+16u*v.record_bytes*i) return GXR2_LAYOUT;
    }
    status=gxr2_pool_layout(&v); if(status!=GXR2_OK) return status;
    for(i=0;i<3;++i) {
        d=directory(&v,i); e=descriptor(&v,i,0);
        if(e[0]!=4 || e[1] || be16(e+2)!=2) return GXR2_PIN;
        c=gxr2_crc_add(gxr2_crc_begin(),p+be32(d+12),152);
        for(j=0;j<10;++j) {
            row=gxr2_raw_row(&v,e,j); if(!row.bytes) return GXR2_LAYOUT;
            c=gxr2_crc_add(c,row.bytes,row.length);
        }
        c=gxr2_crc_end(gxr2_crc_add(c,e+2,2));
        if(c!=trust->modules[i].stock_crc32) return GXR2_PIN;
    }
    view_copy(out,&v); return GXR2_OK;
}
Gxr2Status gxr2_gate_validate(const uint8_t *p,size_t n,const Gxr2Trust *t,
                            const Gxr2Unit *u,unsigned options,Gxr2View *out)
{ return gate_validate(p,n,t,u,options,out,0); }
/* Only the resident-validated, privately leased image may enter this path.
 * Its original whole-file CRC was checked before BE32 pointer relocation.
 * Header CRC, every inner bound/pin and each relocated cell remain checked. */
Gxr2Status gxr2_gate_relocated_validate(const uint8_t *p,size_t n,const Gxr2Trust *t,
                            const Gxr2Unit *u,uint32_t base,Gxr2View *out)
{ if(!base||n>UINT32_MAX-base)return GXR2_ARGUMENT;return gate_validate(p,n,t,u,0,out,base); }
