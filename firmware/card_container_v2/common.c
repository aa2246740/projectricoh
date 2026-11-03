#include "internal.h"

uint32_t gxr2_crc_begin(void) { return UINT32_C(0xffffffff); }
uint32_t gxr2_crc_add(uint32_t crc,const uint8_t *p,size_t n)
{
    size_t j; unsigned i;
    for(j=0;j<n;++j) {
        crc^=p[j];
        for(i=0;i<8;++i) crc=(crc>>1)^((crc&1u)?UINT32_C(0xedb88320):0u);
    }
    return crc;
}
uint32_t gxr2_crc_end(uint32_t crc) { return crc^UINT32_C(0xffffffff); }
uint32_t gxr2_crc32(const uint8_t *p,size_t n)
{ return gxr2_crc_end(gxr2_crc_add(gxr2_crc_begin(),p,n)); }
uint32_t gxr2_crc_zeroed(const uint8_t *p,size_t n,size_t start,size_t count)
{
    static const uint8_t z=0;
    size_t i; uint32_t c=gxr2_crc_begin();
    for(i=0;i<n;++i) c=gxr2_crc_add(c,(i>=start && i-start<count)?&z:p+i,1);
    return gxr2_crc_end(c);
}

Gxr2Row gxr2_raw_row(const Gxr2View *v,const uint8_t *d,unsigned row)
{
    static const uint8_t kinds[8]={0,1,2,3,0,1,1,1};
    const uint8_t *p=v->bytes+v->sections[5].offset;
    const uint8_t *b=p+16+12u*kinds[row];
    unsigned index=d[8+row];
    Gxr2Row r; r.bytes=NULL; r.length=0;
    if(index<be16(b)) { r.length=be16(b+2); r.bytes=p+be32(b+4)+index*r.length; }
    return r;
}

