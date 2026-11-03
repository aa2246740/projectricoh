/* SIZE PROTOTYPE ONLY (g140 design, layer 1). Not product code.
 * GXUI v2 region (1,984 B, same place as v1): 64 B header + 60 x 32 B records.
 * Replaces uv_validate + kv_ui_legacy_record/levels + uv_count_group/uv_group_entry. */
#include "ui_v2_data.h"
#include "memory.h"
#include "src/firmware/card_container_v2/internal.h"
enum { U2_REC=32, U2_CAP=60, U2_ENGINE_MAX=32, U2_NAME=7, U2_FX_MAX=16 };
static int name_char(unsigned c)
{
    /* g140 charset: A-Z a-z 0-9 space - + . _ ( markers > < * excluded ) */
    return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c==' '||c=='-'||c=='+'||c=='.'||c=='_';
}
const uint8_t *u2_region(const Gxr2View *v){return v->bytes+v->sections[6].offset+UV_LEGACY;}
unsigned u2_count(const Gxr2View *v){return be16(u2_region(v)+22);}
const uint8_t *u2_record(const Gxr2View *v,unsigned i){return i<u2_count(v)?u2_region(v)+64+U2_REC*i:0;}
/* Decode one record into levels; 0 ok, -1 reject. */
int u2_levels(const uint8_t *r,unsigned *slot,UvLevels *out)
{
    unsigned i;UvLevels t;
    t.v[0]=r[10];for(i=1;i<10;++i)t.v[i]=(int8_t)r[10+i];
    *slot=r[0]&15u;*out=t;return 0;
}
int uv2_validate(const Gxr2View *v,const KvDataView *knobs,uint32_t kv_crc)
{
    const uint8_t *h=u2_region(v),*r;unsigned m,j,k,n,len,slot;UvLevels t;KvRequest q;
    if(v->sections[6].length!=UV_LEGACY+UV_EXT_BYTES+KV_DATA_BYTES)return 0;
    if(!equal(h,(const uint8_t *)"GXUI140",8)||be16(h+8)!=2||be16(h+10)!=64||be32(h+12)!=UV_EXT_BYTES||
       be32(h+16)!=gxr2_crc_zeroed(h,UV_EXT_BYTES,16,4)||be16(h+20)!=U2_REC||be16(h+22)>U2_ENGINE_MAX||
       be16(h+24)!=U2_CAP||be16(h+26)!=1||be32(h+28)!=64||be32(h+44)!=kv_crc||!zero(h+48,16))return 0;
    for(m=0;m<3;++m)if(be32(h+32+4*m)!=gxr2_crc32(v->bytes+be32(directory(v,m)+16)+32,1024))return 0;
    n=be16(h+22);
    for(j=0;j<n;++j) {
        r=h+64+U2_REC*j;slot=r[0]&15u;
        if(slot<1||slot>8||(r[0]&0x70u)||r[1]<1||r[1]>7||r[9]||!zero(r+25,3))return 0;
        for(len=0;len<8&&r[2+len];++len)if(!name_char(r[2+len]))return 0;
        if(!len||len>U2_NAME||!zero(r+2+len,8-len)||r[2]==' '||r[1+len]==' ')return 0;
        if(r[0]&0x80u){if(!r[24]||r[24]>U2_FX_MAX||!be32(r+28))return 0;}
        else if(r[24]||be32(r+28))return 0;
        u2_levels(r,&k,&t);
        for(m=0;m<3;++m)if((r[1]>>m&1u)&&kv_data_request(knobs,m,slot,&t,&q))return 0;
    }
    return zero(h+64+U2_REC*n,U2_REC*(U2_CAP-n));
}
/* Flat MyRec list filtered by the current unit (adapter side). */
unsigned u2_visible(const Gxr2View *v,unsigned unit)
{unsigned i,c=0;for(i=0;i<u2_count(v);++i)if(u2_record(v,i)[1]>>unit&1u)++c;return c;}
unsigned u2_entry(const Gxr2View *v,unsigned unit,unsigned row)
{unsigned i,c=0;for(i=0;i<u2_count(v);++i)if(u2_record(v,i)[1]>>unit&1u&&++c==row)return i+1;return 0;}
/* Row text: marker in column 0, up to seven name characters. */
void u2_row(const Gxr2View *v,unsigned user,char marker,char text[9])
{
    const uint8_t *r=u2_record(v,user-1);unsigned i;
    for(i=0;i<9;++i)text[i]=0;
    text[0]=marker;for(i=0;i<U2_NAME&&r[2+i];++i)text[1+i]=(char)r[2+i];
}
