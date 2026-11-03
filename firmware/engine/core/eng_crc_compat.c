#include "eng_internal.h"
/* The legacy 32-byte binding cell now holds BE32 CRC followed by 28 zeros.
 * No SHA implementation is linked. The packer must emit this encoding too. */
void eng_crc_binding(const uint8_t *p,size_t n,uint8_t out[32])
{
    uint32_t c=gxr2_crc32(p,n); unsigned i;
    out[0]=(uint8_t)(c>>24);out[1]=(uint8_t)(c>>16);out[2]=(uint8_t)(c>>8);out[3]=(uint8_t)c;
    for(i=4;i<32;i++)out[i]=0;
}
uint32_t eng_crc(const uint8_t *p,size_t n) { return gxr2_crc32(p,n); }
