#include "internal.h"
#include "../../../fx_pool.h"

static const uint16_t row_bytes[9]={62,33,96,56,62,33,66,62,33};
static const uint16_t row_offset[9]={20,82,115,216,284,346,379,456,518};
static const uint16_t row_crc[9]={8,12,16,212,272,276,280,448,452};
static const uint8_t row_mask[9]={0,0,0,1,16,16,2,0,0};
static const uint8_t row_boundary[9]={0,2,0,0,0,1,0,0,1};

static int map_valid(const uint8_t *m,const Gxr2Unit *unit)
{
    unsigned i,j; uint32_t a,b;
    if(!equal(m,(const uint8_t *)"GXMP",4) || be16(m+4)!=2 || be16(m+6)!=152 ||
       !unit_equal(m+8,unit) || be16(m+20)!=9 || !zero(m+22,2) ||
       be16(m+28)!=0x12c0 || be16(m+30)!=0x2444 || be16(m+140)!=505 ||
       be16(m+142)!=503 || !zero(m+144,8)) return 0;
    for(i=0;i<9;++i) {
        const uint8_t *r=m+32+12u*i; a=be32(r);
        if(!a || a>UINT32_MAX-row_bytes[i] || (a&1u)!=(i==5||i==8?1u:0u) ||
           be16(r+4)!=row_bytes[i] || be16(r+6)!=row_offset[i] ||
           be16(r+8)!=row_crc[i] || r[10]!=row_mask[i] || r[11]!=row_boundary[i]) return 0;
        for(j=0;j<i;++j) { b=be32(m+32+12u*j); if(a<b+row_bytes[j] && b<a+row_bytes[i]) return 0; }
    }
    return be32(m+24)==be32(m+44)+32u;
}

static int record_valid(const uint8_t *r,unsigned slot)
{
    unsigned active,i;
    if(r[0]!=slot || r[1]>1 || be32(r+60)!=gxr2_crc32(r,60)) return 0;
    if(!r[1]) return zero(r+2,58);
    if(!r[2] || r[2]>32 || !zero(r+4+r[2],32u-r[2]) || !zero(r+51,9)) return 0;
    for(i=0;i<r[2];++i) if(r[4+i]<32 || r[4+i]>126) return 0;
    switch(r[3]) { case 1: active=0; break; case 4: active=13; break;
        case 3: active=2; break; case 6: active=3; break; default: return 0; }
    for(i=0;i<active;++i) if(r[36+i]<1 || r[36+i]>9) return 0;
    if(r[3]==6) {
        i=r[39]; if(i!=1 && i!=2 && i!=3 && i!=4 && i!=6) return 0; active=4;
    }
    return zero(r+36+active,13u-active) && signed_byte(r[49])>=-8 && signed_byte(r[49])<=8 &&
           signed_byte(r[50])>=-8 && signed_byte(r[50])<=8;
}

static int bank_valid(const uint8_t *b)
{
    unsigned i;
    if(!equal(b,(const uint8_t *)"GXRRV201",8) || be16(b+8)!=2 || be16(b+10)!=32 ||
       be16(b+12)!=64 || be16(b+14)!=16 || !be32(b+16) || be32(b+20)!=1024 ||
       be32(b+24)!=gxr2_crc32(b+32,1024) || be32(b+28)!=gxr2_crc32(b,28)) return 0;
    for(i=0;i<16;++i) if(!record_valid(b+32+64u*i,i+1)) return 0;
    return b[32+3*64+1]==1;
}

static uint32_t identity_crc(const uint8_t *r)
{
    uint8_t id[49];
    id[0]=r[2]; copy(id+1,r+4,32); id[33]=r[3]; copy(id+34,r+36,15);
    return gxr2_crc32(id,49);
}

int a_valid(const uint8_t *p,unsigned limit)
{
    unsigned i,previous=0,v;
    for(i=0;i<31;++i) { v=be16(p+2u*i); if(v<=previous || v>limit) return 0; previous=v; }
    return 1;
}

int matrix_valid(const uint8_t *m)
{
    unsigned row,i,v;
    for(row=0;row<2;++row) for(i=0;i<14;++i) {
        v=be16(m+28u*row+2u*i); if(v>4095) return 0;
        if(i<9) { if((v&2047u)>(i<3?2047u:1279u)) return 0; }
        else if(i==10 || i==11) { if(v<120 || v>136) return 0; }
        else if(v) return 0;
    }
    return 1;
}

static int pool_valid(const Gxr2View *v)
{
    const uint8_t *p=v->bytes+v->sections[5].offset,*b,*row;
    unsigned kind,i,j,k,m,n,len,index; static uint8_t seen[4][30];
    for(kind=0;kind<4;++kind) for(i=0;i<30;++i) seen[kind][i]=0;
    for(kind=0;kind<4;++kind) {
        b=p+16+12u*kind; n=be16(b); len=be16(b+2); row=p+be32(b+4);
        if(be32(b+8)!=gxr2_crc32(row,n*len) || !zero(row+n*len,align4(n*len)-n*len)) return 0;
        for(i=0;i<n;++i) {
            const uint8_t *a=row+i*len;
            for(j=0;j<i;++j) if(equal(a,row+j*len,len)) return 0;
            if(kind==0 && !a_valid(a,4095)) return 0;
            if(kind==1) for(j=1;j<33;++j) if(a[j]<a[j-1]) return 0;
            if(kind==3 && !matrix_valid(a)) return 0;
        }
    }
    for(m=0;m<3;++m) {
        const uint8_t *d=directory(v,m),*t=v->bytes+be32(d+20),*e;
        const uint8_t *bank=v->bytes+be32(d+16); unsigned slots=0;
        n=d[30];
        if(!equal(t,(const uint8_t *)"GXDT",4) || t[4]!=6 || t[5]!=n ||
           !zero(t+6,2) || be16(t+8)!=20 || !zero(t+10,2) ||
           be32(t+12)!=gxr2_crc32(t+16,n*20u)) return 0;
        for(i=0;i<n;++i) {
            static const uint8_t kinds[10]={0,1,2,3,0,1,1,1,0,1};
            Gxr2Row r; unsigned slot,mask;
            e=t+16+20u*i; slot=e[0]; mask=e[1];
            if(slot<1 || slot>16 || mask>31 || ((mask&6u)!=0 && (mask&6u)!=6) ||
               be16(e+2)!=((mask&4u)?0u:2u) || (slots&(1u<<(slot-1u))) ||
               (i==0 && (slot!=4 || mask)) || (i!=0 && slot==4)) return 0;
            if(!zero(e+18,2))return 0;
            slots|=1u<<(slot-1u);
            if(!bank[32+(slot-1)*64+1] || be32(e+4)!=identity_crc(bank+32+(slot-1)*64)) return 0;
            for(k=0;k<10;++k) {
                r=gxr2_raw_row(v,e,k); if(!r.bytes) return 0;
                index=e[8+k]; seen[kinds[k]][index>>3]|=(uint8_t)(1u<<(index&7u));
                if((k==0||k==8) && !a_valid(r.bytes,4094)) return 0;
                if((k==6 || k==7) && (mask&2u) && r.bytes[32]<128) return 0;
            }
        }
    }
    for(kind=0;kind<4;++kind) for(i=0;i<be16(p+16+12u*kind);++i)
        if(!(seen[kind][i>>3]&(1u<<(i&7u)))) return 0;
    return 1;
}

static int tweaks_valid(const Gxr2View *v)
{
    const uint8_t *h=v->bytes+v->sections[6].offset,*t,*r,*e,*owner;
    unsigned m,s,k,n=v->param_slots,ids=0,seen,index,flags,count,pid;
    int lo,hi,def;
    for(k=0;k<n;++k) {
        pid=be32(h+32+4u*k);
        if(!pid) continue;
        if(pid>6 || (ids&(1u<<pid))) return 0;
        ids|=1u<<pid;
    }
    if(ids!=126) return 0;
    for(m=0;m<3;++m) {
        const uint8_t *bank=v->bytes+be32(directory(v,m)+16);
        count=directory(v,m)[30]; seen=0;
        for(s=1;s<=16;++s) {
            t=metadata(v,m,s); r=bank+32+(s-1)*64;
            index=t[3*n]; flags=t[3*n+1];
            if(t[3*n+2]!=2 || !zero(t+3*n+3,v->record_bytes-(3*n+3)) ||
               (flags&~3u) || (flags&1u)!=r[1]) return 0;
            if(!r[1]) { if(index!=255 || flags || !zero(t,3*n)) return 0; continue; }
            for(k=0;k<n;++k) {
                lo=signed_byte(t[3*k]); hi=signed_byte(t[3*k+1]); def=signed_byte(t[3*k+2]);
                if(lo>def || def>hi || (!be32(h+32+4u*k) && (lo || hi || def))) return 0;
            }
            if(index>=count || (s==4 && (index || flags!=3))) return 0;
            e=descriptor(v,m,index);
            if(flags&2u) {
                owner=bank+32+(e[0]-1u)*64u;
                if(r[3]!=owner[3] || !equal(r+36,owner+36,15)) return 0;
                if(index==0 && (r[3]!=1 || !zero(r+36,15))) return 0;
            } else if(index==0 || e[0]!=s) return 0;
            seen|=1u<<index;
        }
        if(seen!=((1u<<count)-1u)) return 0;
        for(index=0;index<count;++index) {
            e=descriptor(v,m,index); t=metadata(v,m,e[0]);
            if(t[3*n]!=index || t[3*n+1]!=(index?1u:3u)) return 0;
        }
    }
    return 1;
}

Gxr2Status gxr2_semantic_validate(const Gxr2View *gate,const Gxr2Trust *trust,Gxr2View *out)
{
    static uint8_t digest[32]; unsigned i,j; uint32_t crc; Gxr2Row row;
    if(!gate || !trust || !out || !gate->bytes || gate->semantic || gate->selected_module>=3)
        return GXR2_ARGUMENT;
    /* The gate view is an in-process capability, never a serialized input. */
    for(i=0;i<3;++i) {
        const uint8_t *d=directory(gate,i),*map=gate->bytes+be32(d+12),*e=descriptor(gate,i,0);
        if(!map_valid(map,&trust->modules[i].unit)) return GXR2_MAP;
        if(!bank_valid(gate->bytes+be32(d+16))) return GXR2_BANK;
        crc=gxr2_crc_add(gxr2_crc_begin(),map,152);
        for(j=0;j<10;++j) {
            row=gxr2_raw_row(gate,e,j); if(!row.bytes) return GXR2_TABLE;
            crc=gxr2_crc_add(crc,row.bytes,row.length);
        }
        crc=gxr2_crc_end(gxr2_crc_add(crc,e+2,2));
        for(j=0;j<32;++j)digest[j]=0;
        put32(digest,crc);
        if(!equal(d+32,trust->modules[i].stock_sha256,32) ||
           !equal(digest,trust->modules[i].stock_sha256,32)) return GXR2_PIN;
    }
    if(!pool_valid(gate)) return GXR2_TABLE;
    if(!tweaks_valid(gate)) return GXR2_TWEAK;
    if(!fx_area_valid(gate)) return GXR2_TABLE;
    /* Byte copy avoids a compiler-emitted libc struct assignment. */
    copy((uint8_t *)out,(const uint8_t *)gate,sizeof(*out)); out->semantic=1;
    return GXR2_OK;
}

static const uint8_t *slot_descriptor(const Gxr2View *v,unsigned m,unsigned s)
{
    const uint8_t *t;
    if(!v || !v->semantic || m>=3 || s<1 || s>16) return NULL;
    t=metadata(v,m,s); if(!(t[3u*v->param_slots+1]&1u)) return NULL;
    return descriptor(v,m,t[3u*v->param_slots]);
}

Gxr2Status gxr2_row(const Gxr2View *v,unsigned m,unsigned s,unsigned row,Gxr2Row *out)
{
    const uint8_t *e=slot_descriptor(v,m,s);
    if(!e || row>=10 || !out) return GXR2_ARGUMENT;
    *out=gxr2_raw_row(v,e,row); return GXR2_OK;
}

Gxr2Status gxr2_expand_descriptor(const Gxr2View *v,const uint8_t *e,unsigned effects,uint8_t out[552])
{
    static const uint16_t offsets[10]={20,82,115,216,284,346,379,412,456,518};
    Gxr2Row r; unsigned i;
    if(!e || !out) return GXR2_ARGUMENT;
    for(i=0;i<552;++i) out[i]=0;
    out[0]=e[0]; out[1]=e[1]; copy(out+4,e+4,4); copy(out+445,e+2,2);
    for(i=0;i<10;++i) { r=effects?fx_raw_row(v,e,i):gxr2_raw_row(v,e,i);
        if(!r.bytes)return GXR2_ARGUMENT;
        copy(out+offsets[i],r.bytes,r.length); }
    for(i=0;i<9;++i) put32(out+row_crc[i],gxr2_crc32(out+row_offset[i],row_bytes[i]));
    return GXR2_OK;
}

Gxr2Status gxr2_expand(const Gxr2View *v,unsigned m,unsigned s,uint8_t out[552])
{ return gxr2_expand_descriptor(v,slot_descriptor(v,m,s),0,out); }

Gxr2Status gxr2_parameter(const Gxr2View *v,unsigned m,unsigned s,uint32_t id,
                        int32_t *lo,int32_t *hi,int32_t *def)
{
    const uint8_t *t,*h; unsigned i;
    if(!lo || !hi || !def || !id || !slot_descriptor(v,m,s)) return GXR2_ARGUMENT;
    t=metadata(v,m,s); h=v->bytes+v->sections[6].offset;
    for(i=0;i<v->param_slots;++i) if(be32(h+32+4u*i)==id) {
        *lo=signed_byte(t[3*i]); *hi=signed_byte(t[3*i+1]); *def=signed_byte(t[3*i+2]); return GXR2_OK;
    }
    return GXR2_ARGUMENT;
}

