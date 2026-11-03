/* SIZE PROTOTYPE ONLY (g140 design, layer 2 option Y). Not product code.
 * Reads /ATA1/GXRFX.BIN with the g146-proven shape: try semaphore 47 once,
 * fresh handle, fill the handle's one-cluster buffer from position 0, copy
 * the selected effect's block for this unit, release, signal 47.
 * File: 64 B header + 16 x 16 B directory + effects (16 B head + n x 512 B). */
#include <stdint.h>
#include "src/firmware/card_container_v2/internal.h"
#include "rv_min.h"
enum { FX_UNIT=512, FX_HEAD=64, FX_DIR=16, FX_MAX=16, FX_LIMIT=FX_HEAD+FX_DIR*FX_MAX+FX_MAX*(16+3*FX_UNIT) };
enum { FX_OK, FX_BUSY, FX_OPEN, FX_READ, FX_BAD, FX_GONE };
int32_t dg_lock_try(void);
void dg_lock_release(void);
int32_t dg_fs_parse(const char *);
int32_t dg_fs_lookup(uint32_t,uint32_t);
int32_t dg_fs_attach(int32_t,uint32_t,uint32_t);
int32_t dg_fs_release(int32_t);
int32_t dg_fs_fill(int32_t,uint32_t,uint32_t);
int fx_unit_valid(const uint8_t *);
#define FS_OPEN_COUNT 0x204c8668u
#define FS_TABLE 0x204c866cu
#define FS_ENTRIES 0x204c8680u
#define FS_HALF(a) (*(volatile uint16_t *)RV_PTR(a))
static const char fx_path[]="/ATA1/GXRFX.BIN";
/* Two slots: the effect in the unit now and the confirmed one (recovery). */
uint8_t fx_slot[2][FX_UNIT];
static int32_t fs_open(uint32_t *entry)
{
    int32_t fd;uint32_t e;
    if(RV_WORD(FS_OPEN_COUNT)>=2)return -2;
    (void)dg_fs_parse(fx_path);
    fd=dg_fs_lookup(FS_TABLE,2);
    if(fd==-1)return -1;
    e=FS_ENTRIES+16*((uint32_t)fd&15);
    if(dg_fs_attach(fd,e+4,e+2)==-1){(void)dg_fs_release(fd);return -1;}
    RV_WORD(FS_OPEN_COUNT)=RV_WORD(FS_OPEN_COUNT)+1;RV_WORD(e+8)=0;FS_HALF(e)=0;
    *entry=e;return fd;
}
static int32_t fs_close(int32_t fd,uint32_t e)
{
    RV_WORD(e+8)=0;FS_HALF(e)=0;
    if(RV_WORD(FS_OPEN_COUNT))RV_WORD(FS_OPEN_COUNT)=RV_WORD(FS_OPEN_COUNT)-1;
    return dg_fs_release(fd);
}
/* Find effect id, check the binding CRC from the DAT entry and the unit bit,
 * copy this unit's block into slot. Nothing outside slot changes on failure. */
static unsigned pick(const uint8_t *f,uint32_t got,unsigned id,uint32_t bind,unsigned unit,uint8_t *slot)
{
    unsigned i,count,at,len,mask,k,n;
    if(got<FX_HEAD||!equal(f,(const uint8_t *)"GXRFX140",8)||be32(f+12)!=got||be32(f+16)!=gxr2_crc_zeroed(f,FX_HEAD+FX_DIR*FX_MAX,16,4))return FX_BAD;
    count=be16(f+20);if(count>FX_MAX)return FX_BAD;
    for(i=0;i<count;++i){
        const uint8_t *d=f+FX_HEAD+FX_DIR*i;
        if(d[0]!=id)continue;
        mask=d[1];at=be32(d+4);len=be32(d+8);
        if(be32(d+12)!=bind||!(mask>>unit&1u)||at>got||len>got-at||len<16)return FX_BAD;
        if(gxr2_crc32(f+at,len)!=bind)return FX_BAD;
        for(k=0,n=0;k<unit;++k)n+=mask>>k&1u;
        if(len!=16+FX_UNIT*(unsigned)(((mask&1u)+(mask>>1&1u)+(mask>>2&1u))))return FX_BAD;
        if(!fx_unit_valid(f+at+16+FX_UNIT*n))return FX_BAD;
        copy(slot,f+at+16+FX_UNIT*n,FX_UNIT);return FX_OK;
    }
    return FX_GONE;
}
unsigned fx_load(unsigned id,uint32_t bind,unsigned unit,unsigned which)
{
    int32_t fd,got;uint32_t e,size,buffer;unsigned result;
    if(which>1)return FX_BAD;
    got=dg_lock_try();
    if(got)return FX_BUSY;
    fd=fs_open(&e);
    if(fd<0){dg_lock_release();return FX_OPEN;}
    size=(uint32_t)FS_HALF(e+2)<<9;buffer=RV_WORD(e+4);
    if(size<FX_HEAD||buffer<0x20000000u||buffer>0x207fffffu-size)result=FX_READ;
    else {
        FS_HALF(e)=2;got=dg_fs_fill(fd,0,size);RV_WORD(e+12)=got==-1?0:(uint32_t)got;
        result=got<=0||(uint32_t)got>=size?FX_READ:pick(RV_PTR(buffer),(uint32_t)got,id,bind,unit,fx_slot[which]);
    }
    if(fs_close(fd,e)==-1&&result==FX_OK)result=FX_READ;
    dg_lock_release();
    return result;
}
