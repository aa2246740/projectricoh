#include "resident.h"
uint32_t rv_crc_update(uint32_t crc,const uint8_t *p,uint32_t n)
{
    unsigned k;
    while(n--){crc^=*p++;for(k=0;k<8;++k)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));}
    return crc;
}
uint32_t gxrce_crc32(const uint8_t *p,size_t n){return ~rv_crc_update(~0u,p,(uint32_t)n);}

/* Only the executable envelope belongs here. Directory, map, GXDP/GXDT,
 * recipe, metadata and stock-pin parsing belong to the engine's pure init. */
GxrceStatus rv_validate(const uint8_t *p,size_t length,const RvTrust *t,GxrceView *out)
{
    GxrceView v;uint32_t i,j,off,n,end,patch,target,previous=0,crc;const uint8_t *d;
    if(!p||!t||!out)return GXRCE_ARGUMENT;
    if(length<256||length>RV_MAX_FILE||rv_be32(p+16)!=length||rv_be32(p+116)>RV_MAX_IMAGE-length)return GXRCE_LENGTH;
    if(!rv_equal(p,"GXRCE001",8)||rv_be16(p+8)!=1||rv_be16(p+10)!=256||
       rv_be16(p+32)!=1||!rv_equal(p+36,"M32B",4)||rv_be16(p+40)!=0x151||
       rv_be16(p+44)!=7||!rv_be32(p+28))return GXRCE_VERSION;
    if(rv_be32(p+12)||rv_be16(p+42))return GXRCE_FLAGS;
    crc=rv_crc_update(~0u,p,20);
    {static const uint8_t zero[4]={0};crc=rv_crc_update(crc,zero,4);}
    crc=~rv_crc_update(crc,p+24,232);
    if(crc!=rv_be32(p+20)||gxrce_crc32(p+256,length-256)!=rv_be32(p+24))return GXRCE_CRC;
    if(!rv_equal(p+48,t->body,32))return GXRCE_BODY_ID;
    if(!rv_equal(p+80,t->build,32)||!rv_equal(p+212,t->abi,16))return GXRCE_RESIDENT_ID;
    v.bytes=p;v.length=length;v.build_number=rv_be32(p+28);v.entry_offset=rv_be32(p+112);
    v.bss_bytes=rv_be32(p+116);v.selected_module=255;v.executable=1;
    for(i=0;i<7;++i){
        d=p+128+12*i;off=rv_be32(d+4);n=rv_be32(d+8);
        if(rv_be16(d)!=i+1||rv_be16(d+2)||off<256||(off&3)||(n&3)||off>length||n>length-off)return GXRCE_LAYOUT;
        for(j=0;j<i;++j)if(n&&v.sections[j].length&&off<v.sections[j].offset+v.sections[j].length&&v.sections[j].offset<off+n)return GXRCE_LAYOUT;
        v.sections[i].offset=off;v.sections[i].length=n;
    }
    end=v.sections[0].offset+v.sections[0].length;
    if(v.sections[0].length<4||v.sections[0].length>RV_MAX_CODE||(v.entry_offset&3)||
       v.entry_offset<v.sections[0].offset||v.entry_offset>end-4)return GXRCE_LAYOUT;
    n=rv_be16(p+120);if(n>256||v.sections[1].length!=8*n)return GXRCE_RELOCATION;
    for(i=0;i<n;++i){
        d=p+v.sections[1].offset+8*i;patch=rv_be32(d);target=rv_be32(d+4);
        if(patch<v.sections[0].offset||patch>end-4||(patch&3)||(i&&patch<=previous)||target<256||
           target>=length+v.bss_bytes||rv_be32(p+patch)!=target)return GXRCE_RELOCATION;
        previous=patch;
    }
    *out=v;return GXRCE_OK;
}
