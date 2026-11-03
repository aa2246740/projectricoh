#include "resident.h"
uint32_t rv4_crc_update(uint32_t crc,const uint8_t *p,uint32_t n)
{
    unsigned k;
    while(n--){crc^=*p++;for(k=0;k<8;++k)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));}
    return crc;
}
uint32_t rv4_crc(const uint8_t *p,uint32_t n)
{return ~rv4_crc_update(~0u,p,n);}
static int section(uint32_t off,uint32_t bytes,uint32_t length)
{return off>=256&&!(off&3)&&off<=length&&bytes<=length-off;}
int32_t rv4_header(const uint8_t *p,uint32_t length,const Rv4Trust *trust,Rv4Validated *v)
{
    uint32_t i,code,n,reloc,count,crc,required;static const uint8_t zero[4]={0};
    static const uint16_t version_fields[][2]={
        {8,RV4_MAJOR},{12,256},{14,16},{32,RV4_FIRMWARE_REVISION},
        {34,RV4_CPU_ID},{224,4}
    };
    if(!p||!trust||!v)return RV4_ARGUMENT;
    rv4_clear(v,sizeof(*v));
    if(length<256||length>RV4_MAX_FILE||rv4_be32(p+16)!=length||
       rv4_be32(p+116)>RV4_MAX_IMAGE_BSS-length)return RV4_RANGE;
    if(!rv4_equal(p,"GXRCE004",8)||rv4_be16(p+10)>RV4_MINOR||
       !rv4_be32(p+28)||rv4_be32(p+144)!=RV4_SCHEMA||rv4_be32(p+152)>RV4_MINOR||
       rv4_be16(p+226)>RV4_MINOR)return RV4_VERSION;
    for(i=0;i<sizeof(version_fields)/sizeof(version_fields[0]);++i)
        if(rv4_be16(p+version_fields[i][0])!=version_fields[i][1])return RV4_VERSION;
    if(rv4_be32(p+140)||rv4_be32(p+156)||
       (rv4_be32(p+136)&~RV4_IMPLEMENTED_CAPS)||
       (rv4_be32(p+148)&~RV4_KNOWN_EVENTS)||(rv4_be32(p+228)&~0xbu))return RV4_UNSUPPORTED;
    for(i=232;i<256;++i)if(p[i])return RV4_UNSUPPORTED;
    crc=rv4_crc_update(~0u,p,20);crc=rv4_crc_update(crc,zero,4);
    if(~rv4_crc_update(crc,p+24,232)!=rv4_be32(p+20))return RV4_CRC;
    _Static_assert(sizeof(*trust)==80,"contiguous identity fields");
    if(!rv4_equal(p+36,trust,sizeof(*trust)))return RV4_IDENTITY;
    code=rv4_be32(p+120);n=rv4_be32(p+124);reloc=rv4_be32(p+128);count=rv4_be32(p+132);
    if(n<4||n>RV4_MAX_CODE||(n&3)||!section(code,n,length)||count>RV4_MAX_RELOCATIONS||
       !section(reloc,count*8,length)||(count&&code<reloc+count*8&&reloc<code+n))return RV4_LAYOUT;
    required=rv4_be32(p+148)|RV4_REQUIRED_ENTRIES;
    for(i=0;i<16;++i){
        uint32_t x=rv4_be32(p+160+4*i);
        if((i>=12&&x)||(!x&&((required>>i)&1))||
           (x&&((x&3)||x<code||x>code+n-4))){
            rv4_clear(v,sizeof(*v));return RV4_LAYOUT;
        }
        v->entries[i]=x;
    }
    v->generation=rv4_be32(p+28);v->file_bytes=length;v->bss_bytes=rv4_be32(p+116);
    v->code_offset=code;v->code_bytes=n;v->reloc_offset=reloc;v->reloc_count=count;
    v->capabilities=rv4_be32(p+136);v->required_events=rv4_be32(p+148);
    return RV4_OK;
}
int32_t rv4_validate(const uint8_t *p,uint32_t length,const Rv4Trust *trust,Rv4Validated *v)
{
    uint32_t i,patch,target,previous=0;int32_t result=rv4_header(p,length,trust,v);
    if(result)return result;
    result=RV4_CRC;
    if(rv4_crc(p+256,length-256)!=rv4_be32(p+24))goto fail;
    result=RV4_RELOCATION;
    for(i=0;i<v->reloc_count;++i){
        const uint8_t *d=p+v->reloc_offset+8*i;patch=rv4_be32(d);target=rv4_be32(d+4);
        if((patch&3)||patch<v->code_offset||patch>v->code_offset+v->code_bytes-4||
           (i&&patch<=previous)||target<256||target>=length+v->bss_bytes||rv4_be32(p+patch)!=target)goto fail;
        previous=patch;
    }
    return RV4_OK;
fail:
    rv4_clear(v,sizeof(*v));return result;
}
