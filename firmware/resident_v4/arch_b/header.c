#include "abi.h"
static int span(uint32_t offset,uint32_t bytes,uint32_t length)
{return offset>=BV4_HEADER_BYTES&&!(offset&3)&&offset<=length&&bytes<=length-offset;}
int32_t bv4_header(const uint8_t *p,Bv4Validated *v)
{
    uint32_t file=rv4_be32(p+12),bss=rv4_be32(p+16),code=rv4_be32(p+20);
    uint32_t bytes=rv4_be32(p+24),init=rv4_be32(p+28),hook=rv4_be32(p+32);
    uint32_t reloc=rv4_be32(p+36),count=rv4_be32(p+40),i;
    if(!rv4_equal(p,"GXRB4E01",8)||rv4_be32(p+8)!=BV4_HEADER_BYTES||
       rv4_be32(p+140)!=((uint32_t)RV4_FIRMWARE_REVISION<<16|RV4_CPU_ID))return RV4_VERSION;
    for(i=144;i<160;++i)if(p[i])return RV4_UNSUPPORTED;
    if(file<BV4_HEADER_BYTES||file>BV4_MAX_FILE||bss>BV4_MAX_BSS)return RV4_RANGE;
    /* official, window build and ABI are one contiguous 80-byte identity. */
    if(!rv4_equal(p+44,&bv4_trust,80))return RV4_IDENTITY;
    if(bytes<4||!span(code,bytes,file)||(bytes&3)||count>BV4_MAX_RELOCATIONS||
       !span(reloc,count*8,file)||(count&&code<reloc+count*8&&reloc<code+bytes)||
       ((init|hook)&3)||init<code||hook<code||init>code+bytes-4||hook>code+bytes-4)return RV4_LAYOUT;
    v->file_bytes=file;v->bss_bytes=bss;v->code_offset=code;v->code_bytes=bytes;
    v->init_offset=init;v->hook_offset=hook;v->reloc_offset=reloc;v->reloc_count=count;
    return RV4_OK;
}
int32_t bv4_relocate(uint8_t *p,uint32_t base,const Bv4Validated *v)
{
    uint32_t i,patch,target,previous=0;
    /* Validate every descriptor before changing any instruction or pointer. */
    for(i=0;i<v->reloc_count;++i){
        const uint8_t *d=p+v->reloc_offset+8*i;patch=rv4_be32(d);target=rv4_be32(d+4);
        if((patch&3)||patch<v->code_offset||patch>v->code_offset+v->code_bytes-4||
           (i&&patch<=previous)||target<BV4_HEADER_BYTES||target>=v->file_bytes+v->bss_bytes||
           rv4_be32(p+patch)!=target)return RV4_RELOCATION;
        previous=patch;
    }
    for(i=0;i<v->reloc_count;++i){
        const uint8_t *d=p+v->reloc_offset+8*i;
        rv4_put32(p+rv4_be32(d),base+rv4_be32(d+4));
    }
    return RV4_OK;
}
