#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include "../../firmware/engine_diag_v2/resident/resident.h"
#include <string.h>

static uint8_t ram[0x800000];
static uint32_t reads,low_read,high_read;
static uint32_t host_word(uint32_t address)
{
    uint32_t o;
    if((address&3u)||address<0x20000000u||address>0x207ffffcu)abort();
    o=address-0x20000000u;++reads;
    if(address<low_read)low_read=address;if(address>high_read)high_read=address;
    return ((uint32_t)ram[o]<<24)|((uint32_t)ram[o+1]<<16)|((uint32_t)ram[o+2]<<8)|ram[o+3];
}
static uint8_t host_byte(uint32_t address)
{
    if(address<0x20000000u||address>0x207fffffu)abort();
    ++reads;if(address<low_read)low_read=address;if(address>high_read)high_read=address;
    return ram[address-0x20000000u];
}
#define DH_WORD(a) host_word(a)
#define DH_BYTE(a) host_byte(a)
#include "../../firmware/engine_diag_v2/candidate/containers/product/diag_heap.h"
static DhSnapshot snapshots[2];
static char rows[8][9];
void test_reset(void)
{memset(ram,0,sizeof(ram));memset(snapshots,0,sizeof(snapshots));reads=0;low_read=~0u;high_read=0;}
void test_set(uint32_t address,uint32_t value,uint32_t width)
{
    uint32_t i;
    if(address<0x20000000u||address+width>0x20800000u)abort();
    for(i=0;i<width;++i)ram[address-0x20000000u+i]=(uint8_t)(value>>(8u*(width-i-1u)));
}
void test_take(uint32_t pass){if(pass>1)abort();dh_take(&snapshots[pass]);}
int test_equal(void){return dh_equal(&snapshots[0],&snapshots[1]);}
const char *test_row(uint32_t row,uint32_t opens,uint32_t changed)
{
    memset(rows,0,sizeof(rows));rows[0][0]='H';dh_hex(rows[0]+1,opens&65535u,4);
    rows[0][5]=' ';rows[0][6]=changed?'C':'S';dh_rows(&snapshots[1],rows);
    return row<8?rows[row]:0;
}
uint32_t test_value(uint32_t what)
{
    switch(what){
    case 0:return snapshots[1].physical_hops;
    case 1:return snapshots[1].free_hops;
    case 2:return reads;
    case 3:return low_read;
    case 4:return high_read;
    case 5:return (uint32_t)sizeof(DhSnapshot);
    default:return 0;
    }
}
static uint32_t shape_one(void)
{
    uint32_t i;
    dh_rows(&snapshots[1],rows);
    for(i=0;i<8;++i)if(strlen(rows[i])>8u)abort();
    return 1;
}
uint32_t test_shapes(void)
{
    uint32_t x,i,n=0;static const char paths[]="RPFMSN";
    DhSnapshot *s=&snapshots[1];memset(s,0,sizeof(*s));
    s->main_kind=s->snapshot_kind='0';
    for(x=0;x<=DH_LIMIT;++x){s->used_count=x;s->free_count=x;n+=shape_one();}
    for(x=0;x<=262144u;x+=4u){
        s->used_bytes=x;s->free_bytes=x;s->largest=x;s->main_bytes=x;s->snapshot_bytes=x;
        n+=shape_one();
    }
    for(x=0;x<512u;++x){s->native_bits=x;s->stale_bits=x;n+=shape_one();}
    for(i=0;i<sizeof(paths)-1u;++i)for(x=0;x<=DH_LIMIT;++x){s->bad=paths[i];s->bad_hop=x;n+=shape_one();}
    for(x=0;x<65536u;++x){
        rows[0][0]='H';dh_hex(rows[0]+1,x,4);rows[0][5]=' ';rows[0][6]=(x&1u)?'C':'S';rows[0][7]=0;
        n+=shape_one();
    }
    return n;
}
