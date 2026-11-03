/* SIZE PROTOTYPE ONLY (g140 design, layer 2 option X). Not product code.
 * Effects live in the DAT after the kv2 block (same layout as the card file
 * body), validated once at init; selection returns a pointer into the DAT. */
#include <stdint.h>
#include "src/firmware/card_container_v2/internal.h"
enum { FX_UNIT=512, FX_HEAD=64, FX_DIR=16, FX_MAX=16 };
int fx_unit_valid(const uint8_t *);
static const uint8_t *fx_region;static uint32_t fx_bytes;
int fx_x_validate(const uint8_t *f,uint32_t bytes)
{
    unsigned i,count,mask,k,units;uint32_t at,len;
    if(bytes<FX_HEAD||!equal(f,(const uint8_t *)"GXRFX140",8)||be32(f+12)!=bytes||be32(f+16)!=gxr2_crc_zeroed(f,FX_HEAD+FX_DIR*FX_MAX,16,4))return 0;
    count=be16(f+20);if(count>FX_MAX)return 0;
    for(i=0;i<count;++i){
        const uint8_t *d=f+FX_HEAD+FX_DIR*i;
        mask=d[1];at=be32(d+4);len=be32(d+8);units=(mask&1u)+(mask>>1&1u)+(mask>>2&1u);
        if(d[0]!=i+1||!mask||mask>7||at>bytes||len>bytes-at||len!=16+FX_UNIT*units||gxr2_crc32(f+at,len)!=be32(d+12))return 0;
        for(k=0;k<units;++k)if(!fx_unit_valid(f+at+16+FX_UNIT*k))return 0;
    }
    fx_region=f;fx_bytes=bytes;return 1;
}
const uint8_t *fx_x_block(unsigned id,uint32_t bind,unsigned unit)
{
    const uint8_t *d;unsigned mask,k,n;
    if(!fx_region||!id||id>be16(fx_region+20))return 0;
    d=fx_region+FX_HEAD+FX_DIR*(id-1);mask=d[1];
    if(be32(d+12)!=bind||!(mask>>unit&1u))return 0;
    for(k=0,n=0;k<unit;++k)n+=mask>>k&1u;
    return fx_region+be32(d+4)+16+FX_UNIT*n;
}
