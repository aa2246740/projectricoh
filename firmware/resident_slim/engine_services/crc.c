#include "engine_services.h"
uint32_t rv_crc_update(uint32_t crc,const uint8_t *p,uint32_t n)
{
    unsigned k;
    while(n--){crc^=*p++;for(k=0;k<8;++k)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1)));}
    return crc;
}
uint32_t gxrce_crc32(const uint8_t *p,size_t n){return ~rv_crc_update(~0u,p,(uint32_t)n);}

