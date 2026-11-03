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

