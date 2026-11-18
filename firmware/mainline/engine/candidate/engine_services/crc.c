#include "../memory_codec.h"
#include "engine_services.h"
uint32_t gxr2_crc_add(uint32_t crc,const uint8_t *p,size_t n)
{
    size_t j; unsigned i;
    for(j=0;j<n;++j) {
        crc^=p[j];
        for(i=0;i<8;++i) crc=(crc>>1)^((crc&1u)?UINT32_C(0xedb88320):0u);
    }
    return crc;
}

uint32_t rv_crc_update(uint32_t crc,const uint8_t *p,uint32_t n)
{
    return gxr2_crc_add(crc,p,n);
}
uint32_t gxrce_crc32(const uint8_t *p,size_t n){return ~rv_crc_update(~0u,p,(uint32_t)n);}


int __attribute__((noinline)) memory_owned(const uint8_t p[MEMORY_BYTES],uint32_t crc)
{
    unsigned code=p[5];
    return p[0]=='G'&&p[1]=='X'&&p[2]=='R'&&p[3]=='2'&&p[6]<GXR2_MODULES&&p[7]==1&&
        ((p[4]==1&&code>=1&&code<=8)||(p[4]==3&&((code>=1&&code<=8)||(code>=64&&code<112)||(code>=128&&code<160))))&&
        crc==((uint32_t)p[36]<<24|(uint32_t)p[37]<<16|(uint32_t)p[38]<<8|p[39]);
}
