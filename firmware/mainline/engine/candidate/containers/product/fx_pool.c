#include "fx_pool.h"
static const uint8_t kinds[10]={0,1,2,3,0,1,1,1,0,1};
static const uint8_t lengths[4]={62,33,96,56};
static unsigned wide(const uint8_t *a){return be16(a+4)==2;}
static unsigned capacity(const uint8_t *a,unsigned k)
{return wide(a)?be16(a+16+2*k):a[16+k];}
static unsigned used(const uint8_t *a,unsigned k)
{return wide(a)?be16(a+24+2*k):a[20+k];}
static unsigned data_start(const uint8_t *a)
{return be16(a+6)+be16(a+12)*be16(a+8);}
const uint8_t *fx_area(const Gxr2View *v)
{
    const Gxr2Section *s;const uint8_t *p,*a;uint32_t off,len,need,k;
    if(!v||!v->bytes)return 0;
    s=&v->sections[5];
    if(s->offset>v->length||s->length>v->length-s->offset||s->length<80)return 0;
    p=v->bytes+s->offset;
    if(!equal(p,(const uint8_t *)"GXDP",4)||be16(p+4)!=2||be16(p+6)!=80)return 0;
    off=be32(p+64);len=be32(p+68);
    if((off&3u)||off<80||off>s->length||len<32||len!=s->length-off||!zero(p+72,8))return 0;
    a=p+off;
    if(!equal(a,(const uint8_t *)"GXFX",4)||be16(a+8)>GXR2_FX_MAX)return 0;
    if(wide(a)){
        if(len<48||!equal(v->bytes,(const uint8_t *)"GXRCL002",8)||be16(a+6)!=48||be16(a+12)!=44)return 0;
    }else if(be16(a+4)!=1||be16(a+6)!=32||be16(a+12)!=32)return 0;
    need=data_start(a);
    for(k=0;k<4;++k){
        if(capacity(a,k)>(wide(a)?32767u:127u))return 0;
        need+=align4(capacity(a,k)*lengths[k]);
    }
    return need==len?a:0;
}
const uint8_t *fx_entry(const Gxr2View *v,unsigned index)
{
    const uint8_t *a=fx_area(v);
    return a&&index<be16(a+10)?a+be16(a+6)+be16(a+12)*index:0;
}
unsigned fx_unit_mask(const Gxr2View *v,const uint8_t *e)
{const uint8_t *a=fx_area(v);return a&&e?e[wide(a)?28:18]:0;}
static const uint8_t *fx_rows(const uint8_t *a,unsigned kind)
{
    unsigned k,at=data_start(a);
    for(k=0;k<kind;++k)at+=align4(capacity(a,k)*lengths[k]);
    return a+at;
}
Gxr2Row fx_raw_row(const Gxr2View *v,const uint8_t *e,unsigned row)
{
    Gxr2Row r={0,0};const uint8_t *a,*p,*b;unsigned i,kind,extra;
    if(!e||row>=10)return r;
    a=fx_area(v);if(!a)return r;
    kind=kinds[row];i=wide(a)?be16(e+8+2*row):e[8+row];extra=wide(a)?32768u:128u;
    if(i&extra){
        i&=extra-1u;
        if(i<used(a,kind)){r.bytes=fx_rows(a,kind)+i*lengths[kind];r.length=lengths[kind];}
    }else{
        p=v->bytes+v->sections[5].offset;b=p+16+12u*kind;
        if(i<be16(b)){r.length=be16(b+2);r.bytes=p+be32(b+4)+i*r.length;}
    }
    return r;
}
int fx_row_valid(const uint8_t *r,unsigned row,unsigned flags)
{
    unsigned j,kind=kinds[row];
    if(kind==0&&!a_valid(r,(row==0||row==8)?4094:4095))return 0;
    if(kind==1)for(j=1;j<33;++j)if(r[j]<r[j-1])return 0;
    if(kind==3&&!matrix_valid(r))return 0;
    return !((row==6||row==7)&&(flags&2u)&&r[32]<128);
}
int fx_area_valid(const Gxr2View *v)
{
    const uint8_t *a=fx_area(v),*e,*d,*t;Gxr2Row row;
    unsigned i,j,k,m,n,cap,name,mask;uint32_t size;
    if(!a)return 0;
    n=be16(a+10);cap=be16(a+8);name=wide(a)?32:20;
    if(be16(a+14)||n>cap)return 0;
    if(wide(a)){
        if(!zero(a+36,8)||be32(a+44)!=gxr2_crc32(a,44))return 0;
    }else if(be32(a+28)!=gxr2_crc32(a,28))return 0;
    size=data_start(a);
    for(k=0;k<4;++k){
        if(used(a,k)>capacity(a,k))return 0;
        size+=align4(capacity(a,k)*lengths[k]);
        t=fx_rows(a,k)+used(a,k)*lengths[k];
        if(!zero(t,align4(capacity(a,k)*lengths[k])-used(a,k)*lengths[k]))return 0;
    }
    if(be32(a+(wide(a)?32:24))!=gxr2_crc32(a+be16(a+6),size-be16(a+6))||
       !zero(a+be16(a+6)+be16(a+12)*n,be16(a+12)*(cap-n)))return 0;
    for(i=0;i<n;++i){
        e=a+be16(a+6)+be16(a+12)*i;mask=fx_unit_mask(v,e);
        if(e[0]<1||e[0]>8||e[0]==4||mask<1||mask>7||
           !zero(e+(wide(a)?29:19),wide(a)?3:1)||be16(e+2)!=((e[1]&4u)?0u:2u))return 0;
        for(m=0;m<3;++m)if(mask>>m&1u){
            t=metadata(v,m,e[0]);d=descriptor(v,m,t[3u*v->param_slots]);
            if(!(t[3u*v->param_slots+1]&1u)||d[0]!=e[0]||d[1]!=e[1])return 0;
        }
        for(j=0;j<FX_NAME&&e[name+j];++j){
            uint8_t c=e[name+j];if(c<32||c>126||c==92||c==42)return 0;
        }
        if(!j||!zero(e+name+j,FX_NAME-j))return 0;
        for(k=0;k<10;++k){row=fx_raw_row(v,e,k);if(!row.bytes||!fx_row_valid(row.bytes,k,e[1]))return 0;}
    }
    return 1;
}
Gxr2Status fx_expand(const Gxr2View *v,unsigned index,uint8_t out[552])
{const uint8_t *e=fx_entry(v,index);return e?gxr2_expand_descriptor(v,e,1,out):GXR2_ARGUMENT;}
int fx_visible(const Gxr2View *v,unsigned unit,unsigned ordinal)
{
    const uint8_t *a=fx_area(v),*e;unsigned i,n=a?be16(a+10):0,mask;
    if(unit>=3)return -1;
    mask=a&&wide(a)?28:18;e=a?a+be16(a+6):0;
    for(i=0;i<n;++i,e+=be16(a+12))if(e[mask]>>unit&1u){if(!ordinal)return (int)i;--ordinal;}
    return -1;
}
unsigned fx_count(const Gxr2View *v,unsigned unit)
{
    const uint8_t *a=fx_area(v),*e;unsigned i,n=0,count,mask;
    if(!a||unit>=3)return 0;
    count=be16(a+10);mask=wide(a)?28:18;e=a+be16(a+6);
    for(i=0;i<count;++i,e+=be16(a+12))if(e[mask]>>unit&1u)++n;
    return n;
}
void fx_name(const Gxr2View *v,unsigned index,char out[FX_NAME+1])
{
    const uint8_t *a=fx_area(v),*e=fx_entry(v,index);unsigned i,name=a&&wide(a)?32:20;
    for(i=0;i<=FX_NAME;++i)out[i]=0;
    if(e)for(i=0;i<FX_NAME&&e[name+i];++i)out[i]=(char)e[name+i];
}
