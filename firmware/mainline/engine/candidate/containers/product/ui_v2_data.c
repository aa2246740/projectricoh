#include "ui_v2_data.h"
#include "fx_pool.h"
#include "memory.h"
#include "src/firmware/card_container_v2/internal.h"
static const char groups[8][4]={"GRP","GRN","HCB","STD","FCC","FCN","LCH","LVI"};
void __attribute__((noinline)) uv_window(unsigned count,unsigned current,unsigned previous,UvWindow *out)
{
    unsigned top=previous;
    if(count<=UV_PHYSICAL)top=0;
    else {
        if(top>count-UV_PHYSICAL)top=count-UV_PHYSICAL;
        if(current<top)top=current;
        if(current>=top+UV_PHYSICAL)top=current-UV_PHYSICAL+1;
        if(current==top&&top)--top;
        if(current==top+UV_PHYSICAL-1&&top+UV_PHYSICAL<count)++top;
    }
    out->top=(uint16_t)top;out->cursor=(uint16_t)(current-top);
}
const uint8_t *uv_extension(const Gxr2View *v)
{return v->bytes+v->sections[6].offset+UV_LEGACY;}
unsigned uv_users(const Gxr2View *v){return be16(uv_extension(v)+24);}
const uint8_t *uv_user(const Gxr2View *v,unsigned index)
{return index<uv_users(v)?uv_extension(v)+UV_USER_OFFSET+24*index:0;}
int uv_validate(const Gxr2View *v)
{
    /* GXUI v2 (g175): header, bank pins and the user entries; the v1 config table is gone.  The ranges a user entry is checked
     * against are the metadata triples of the four legacy parameters, which is what the table repeated. */
    const uint8_t *h,*r,*meta,*ids;unsigned m,s,k,j,n,seen,pos[4];uint16_t ord[8]={0};
    static const uint8_t legacy[4]={1,3,4,2};
    if(v->build_number!=175||v->sections[6].length!=UV_LEGACY+UV_EXT_BYTES+KV_DATA_BYTES)return 0;
    h=uv_extension(v);
    if(!equal(h,(const uint8_t *)"GXUI124",8)||be16(h+8)!=2||be16(h+10)!=64||
       be32(h+12)!=UV_EXT_BYTES||be32(h+16)!=gxr2_crc_zeroed(h,UV_EXT_BYTES,16,4)||
       be16(h+20)||be16(h+22)||be16(h+24)>UV_USERS||
       be16(h+26)!=24||be16(h+28)!=UV_PARAMS||be16(h+30)!=UV_USERS||
       be32(h+32)||be32(h+36)!=UV_USER_OFFSET||!zero(h+52,12))return 0;
    ids=v->bytes+v->sections[6].offset+32;
    for(k=0;k<4;++k) {
        for(j=0;j<8&&be32(ids+4*j)!=legacy[k];++j){}
        if(j==8)return 0;
        pos[k]=j;
    }
    for(m=0;m<3;++m) {
        if(be32(h+40+4*m)!=gxr2_crc32(v->bytes+be32(directory(v,m)+16)+32,1024))return 0;
        for(s=1;s<=8;++s) {
            meta=metadata(v,m,s);
            for(k=0;k<4;++k)
                if(signed_byte(meta[3*pos[k]])>0||signed_byte(meta[3*pos[k]+1])<0||meta[3*pos[k]+2])return 0;
        }
    }
    n=uv_users(v);
    if(9+fx_count(v,v->selected_module)+n>9+GXR2_FX_MAX+UV_USERS)return 0;
    for(j=0;j<n;++j) {
        r=h+UV_USER_OFFSET+24*j;s=r[0];
        if(s<1||s>8||r[1]||r[9]||r[21]||be16(r+22)!=++ord[s-1])return 0;
        seen=0;
        for(m=0;m<3;++m) {
            meta=metadata(v,m,s);
            for(k=0;k<UV_PARAMS;++k) {
                int value=signed_byte(r[10+k]);
                if(k<4) {
                    if(value<signed_byte(meta[3*pos[k]])||value>signed_byte(meta[3*pos[k]+1]))return 0;
                } else if(value)return 0;
                if(value)seen=1;
            }
        }
        if(!equal(r+2,(const uint8_t *)groups[s-1],3)||r[5]!=(seen?'*':'-')||
           r[6]!='0'+ord[s-1]/100||r[7]!='0'+ord[s-1]/10%10||r[8]!='0'+ord[s-1]%10)return 0;
    }
    if(!zero(h+UV_USER_OFFSET+24*n,24*(UV_USERS-n)))return 0;
    {KvDataView view;return kv_data_open(h+UV_EXT_BYTES,KV_DATA_BYTES,&view)==0;}
}
