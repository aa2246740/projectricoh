#include "eng_internal.h"
#include "../../card_container_v2/internal.h"
/* Only a resident-gated, private and immutable image may enter semantics.
 * Gxr2View is an in-process capability, not a serialized wire struct. */
static Gxr2View admitted;
/* Expansion buffer: the engine's idle work base (never live during these calls). */
#define expanded (eng_work_area())
static const uint8_t names[3][8]={"jlaunch","qlaunch","l08firm"};
static const uint32_t stock_entry_crc[3]={UINT32_C(0x94762b9f),UINT32_C(0x1ff40907),UINT32_C(0xf80736de)};
EngStatus eng_data_accept(const Gxr2View *v)
{
    unsigned i;uint32_t next=256;
    if(!v || !v->bytes || v->length<256 || v->length>98304 || v->bss_bytes>114688-v->length ||
       v->executable || v->semantic || v->selected_module>=3 || v->param_slots!=8 || v->record_bytes!=28) return ENG_REJECTED;
    for(i=0;i<7;i++) {
        const Gxr2Section *s=&v->sections[i];
        if(s->offset!=next || (s->offset&3u) || (s->length&3u) || next>v->length || s->length>v->length-next) return ENG_REJECTED;
        next+=s->length;
    }
    if(next!=v->length || v->sections[0].length || v->entry_offset || v->bss_bytes ||
       v->sections[1].length || v->sections[2].length!=192 || v->sections[3].length!=456 ||
       v->sections[4].length!=3168 || (v->sections[6].length!=1408 && !(v->build_number==175 && v->sections[6].length==9568))) return ENG_REJECTED;
    admitted=*v; return ENG_OK;
}
void eng_identity(const uint8_t *r,uint8_t id[49])
{ id[0]=r[2];copy(id+1,r+4,32);id[33]=r[3];copy(id+34,r+36,15); }
const uint8_t *eng_record(const EngData *d,unsigned slot) { return d->bank+32+(slot-1)*64; }
const uint8_t *eng_meta_record(const EngData *d,unsigned slot) { return d->meta+(slot-1)*28; }
const uint8_t *eng_entry(const EngData *d,unsigned index)
{
    const uint8_t *e;
    if(index>=d->count)return NULL;
    e=d->pool+16+20*index;
    if(gxr2_expand(&d->view,d->unit,e[0],expanded)!=GXR2_OK)return NULL;
    return expanded;
}
EngStatus eng_data_validate(const uint8_t *p,uint32_t length,const RvUnitInfo *u,EngData *out)
{
    Gxr2Trust *trust=eng_work_trust();EngData *d=out;
    unsigned i,j,selected=3;const uint8_t *dir,*meta,*ids;uint32_t crc;
    if(!p || !u || !out || p!=admitted.bytes || length!=admitted.length || !u->valid ||
       u->main_version!=0x151 || u->cmp_version)return ENG_REJECTED;
    for(i=0;i<3;i++)if(equal(u->name,names[i],8))selected=i;
    if(selected==3)return ENG_REJECTED;
    for(i=0;i<sizeof(*trust);i++)((uint8_t *)trust)[i]=0;
    for(i=0;i<3;i++) {
        uint32_t pin=rv_unit_pin((uint8_t)i);uint8_t *tag=trust->modules[i].stock_sha256;
        copy(trust->modules[i].unit.name,names[i],8);trust->modules[i].unit.main_version=0x151;
        trust->modules[i].stock_crc32=pin;
        tag[0]=(uint8_t)(pin>>24);tag[1]=(uint8_t)(pin>>16);tag[2]=(uint8_t)(pin>>8);tag[3]=(uint8_t)pin;
    }
    admitted.selected_module=(uint8_t)selected;
    if(gxr2_semantic_validate(&admitted,trust,&d->view)!=GXR2_OK)return ENG_REJECTED;
    /* Keep Stage2l's entry CRC contract separate from the map+stock pin. */
    for(i=0;i<3;i++)if(gxr2_expand(&d->view,i,4,expanded)!=GXR2_OK ||
        eng_crc(expanded,552)!=stock_entry_crc[i])return ENG_REJECTED;
    dir=directory(&d->view,selected);ids=p+d->view.sections[6].offset+32;
    for(i=0;i<3;i++)for(j=1;j<=16;j++) {
        const uint8_t *r=p+be32(directory(&d->view,i)+16)+32+(j-1)*64;
        unsigned k;meta=metadata(&d->view,i,j);
        for(k=0;k<8;k++) {
            uint32_t id=be32(ids+4*k);int lo=signed_byte(meta[3*k]),hi=signed_byte(meta[3*k+1]);
            if((j==4 && (lo>0 || hi<0)) || (id>=1 && id<=4 && (lo < -8 || hi>8)) ||
               (id==2 && (r[3]==3 || r[3]==6) && (lo || hi || meta[3*k+2])))return ENG_REJECTED;
        }
    }
    /* Explicit READY gate for the connected unit, independent of slot/entry CRC. */
    crc=gxr2_crc_add(gxr2_crc_begin(),p+be32(dir+12),152);
    for(i=0;i<10;i++) {
        Gxr2Row row=gxr2_raw_row(&d->view,descriptor(&d->view,selected,0),i);
        crc=gxr2_crc_add(crc,row.bytes,row.length);
    }
    crc=gxr2_crc_end(gxr2_crc_add(crc,descriptor(&d->view,selected,0)+2,2));
    if(crc!=rv_unit_pin((uint8_t)selected))return ENG_REJECTED;
    d->image=p;d->length=length;d->map=p+be32(dir+12);d->bank=p+be32(dir+16);d->pool=p+be32(dir+20);
    d->meta=p+be32(dir+24);d->ids=ids;d->unit=(uint8_t)selected;d->count=dir[30];d->pin=crc;
    if(kv_data_open(p+d->view.sections[6].offset+1664,KV_DATA_BYTES,&d->knobs))return ENG_REJECTED;
    return ENG_OK;
}
