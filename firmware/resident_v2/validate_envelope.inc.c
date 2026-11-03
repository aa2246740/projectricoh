/* Appended to the unchanged crypto prefix of gxrce.c inside ignored local/.
 * This is a proposed resident subset, not a replacement for the full parser.
 * Engine init must run the full semantic checks before READY or any writes. */
#include "resident.h"

GxrceStatus rv_validate(const uint8_t *p, size_t length, const GxrceTrust *t,
                        const GxrceUnit *u, GxrceView *out)
{
    GxrceView v;
    uint32_t next=256, off, n, end, table_next, patch, target, previous=0;
    uint32_t meta_records,meta_stride=256;
    unsigned i,j,count,selected=3,data_version;
    const uint8_t *d,*map,*pool;
    static const uint16_t row_off[7]={20,82,115,216,284,346,379};
    static const uint16_t row_len[7]={62,33,96,56,62,33,66};
    uint8_t digest[32];
    Sha256 s;
    if (!p || !t || !u || !out) return GXRCE_ARGUMENT;
    if (length<256 || length>32768) return GXRCE_LENGTH;
    data_version=be16(p+34);
    if (!equal(p,(const uint8_t *)"GXRCE001",8) || be16(p+8)!=1 || be16(p+10)!=256 ||
        be16(p+32)!=1 || (data_version!=1 && data_version!=2) || !equal(p+36,(const uint8_t *)"M32B",4) ||
        be16(p+40)!=0x0151 || be16(p+42) || be16(p+44)!=7 || be16(p+46)!=3)
        return GXRCE_VERSION;
    if (be32(p+16)!=length || !be32(p+28) || be32(p+116)>4096) return GXRCE_LENGTH;
    if (be32(p+12) || !zero(p+122,6) || !zero(p+228,28)) return GXRCE_FLAGS;
    if (be32(p+20)!=header_crc(p) || be32(p+24)!=gxrce_crc32(p+256,length-256)) return GXRCE_CRC;
    if (!equal(p+48,t->body_sha256,32)) return GXRCE_BODY_ID;
    if (zero(p+80,32) || !equal(p+80,t->resident_build_id,32) ||
        !equal(p+212,t->resident_abi_id,16)) return GXRCE_RESIDENT_ID;
    if (u->main_version!=0x0151 || u->cmp_version) return GXRCE_MODULE_ID;
    for (i=0;i<3;++i)
        if (equal(u->name,t->modules[i].unit.name,8) &&
            t->modules[i].unit.main_version==0x0151 && !t->modules[i].unit.cmp_version) selected=i;
    if (selected==3) return GXRCE_MODULE_ID;
    v.bytes=p; v.length=(uint32_t)length; v.build_number=be32(p+28);
    v.entry_offset=be32(p+112); v.bss_bytes=be32(p+116);
    v.selected_module=(uint8_t)selected; v.executable=1;
    for (i=0;i<7;++i) {
        d=p+128+12*i; off=be32(d+4); n=be32(d+8);
        if (be16(d)!=i+1 || be16(d+2) || off!=next || (off&3) || (n&3) ||
            off>length || n>length-off || (!n && i!=1)) return GXRCE_LAYOUT;
        v.sections[i].offset=off; v.sections[i].length=n; next=off+n;
    }
    if (next!=length || v.sections[0].length<16 || v.sections[0].length>10240 ||
        v.sections[2].length!=192 || v.sections[3].length!=384 ||
        v.sections[4].length!=3168) return GXRCE_LAYOUT;
    meta_records=v.sections[6].offset;
    if (data_version==1) {
        if (v.sections[6].length!=768) return GXRCE_LAYOUT;
    } else {
        uint32_t params,stride,records;
        d=p+v.sections[6].offset; n=v.sections[6].length;
        if (n<32 || !equal(d,(const uint8_t *)"GXTM",4) || be16(d+4)!=2 ||
            be16(d+6)!=32 || be16(d+10)!=3 || be16(d+12)!=16 || be32(d+28))
            return GXRCE_TWEAK;
        params=be16(d+8);stride=(3*params+7)&~3u;records=32+4*params;
        if (be16(d+14)!=stride || be32(d+16)!=32 || be32(d+20)!=records ||
            be32(d+24)!=48*stride || records>n || 48*stride!=n-records)
            return GXRCE_TWEAK;
        meta_records+=records;meta_stride=16*stride;
    }
    end=256+v.sections[0].length;
    if ((v.entry_offset&3) || v.entry_offset<256 || v.entry_offset>end-4 ||
        equal(p+256,(const uint8_t *)"HOSTSTUB",8)) return GXRCE_PLACEHOLDER;
    count=be16(p+120);
    if (count>256 || v.sections[1].length!=count*8u) return GXRCE_RELOCATION;
    for (i=0;i<count;++i) {
        d=p+v.sections[1].offset+8*i; patch=be32(d); target=be32(d+4);
        if (patch<256 || patch>end-4 || (patch&3) || (i && patch<=previous) ||
            target<256 || target>=length+v.bss_bytes || be32(p+patch)!=target)
            return GXRCE_RELOCATION;
        previous=patch;
    }
    table_next=v.sections[5].offset;
    end=table_next+v.sections[5].length;
    for (i=0;i<3;++i) {
        const GxrceModuleTrust *m=&t->modules[i];
        d=p+v.sections[2].offset+64*i;
        if (!equal(d,m->unit.name,8) || be16(d+8)!=m->unit.main_version ||
            be16(d+10)!=m->unit.cmp_version || d[31]) return GXRCE_MODULE_ID;
        if (be32(d+12)!=v.sections[3].offset+128*i ||
            be32(d+16)!=v.sections[4].offset+1056*i || be32(d+20)!=table_next ||
            be32(d+24)!=meta_records+meta_stride*i) return GXRCE_LAYOUT;
        count=d[30]; n=be16(d+28);
        if (!count || count>16 || n!=16+448*count || table_next>end || n>end-table_next)
            return GXRCE_LAYOUT;
        map=p+be32(d+12); pool=p+table_next;
        if (!equal(d+32,m->stock_pin,32) || pool[16]!=4 || pool[17] ||
            be16(pool+16+445)!=2) return GXRCE_PIN;
        sha_init(&s); sha_add(&s,map,128);
        for (j=0;j<7;++j) sha_add(&s,pool+16+row_off[j],row_len[j]);
        sha_add(&s,pool+16+445,2); sha_finish(&s,digest);
        if (!equal(digest,m->stock_pin,32)) return GXRCE_PIN;
        table_next+=n;
    }
    if (table_next!=end) return GXRCE_LAYOUT;
    *out=v;
    return GXRCE_OK;
}
