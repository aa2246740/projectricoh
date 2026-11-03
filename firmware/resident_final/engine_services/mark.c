#include "engine_services.h"
static int same(RvRoot *r,const uint32_t e[12],const uint8_t id[16])
{
    uint8_t now[16];
    return !(r->flags&RF_STOP)&&(r->flags&RF_SD)&&rv_equal(r->epoch,e,48)&&
        rv_native_sd_id(now)==0&&rv_equal(now,id,16);
}
static int32_t read_exact(int32_t fd,uint8_t *p,uint32_t want)
{
    uint32_t n=0;int32_t k;
    while(n<want){k=rv_native_read(fd,p+n,want-n);if(k<=0||(uint32_t)k>want-n)return RV_VERIFY;n+=(uint32_t)k;}
    return RV_OK;
}
int32_t es_storage_mark(RvRoot *r,const RvRequest *q,RvReply *reply)
{
    RvSession *s=rv_session(r);uint32_t e[12],n,remaining,crc=~0u;
    uint8_t a[128],b[128],id[16];int32_t card=-1,installed=-1,result=RV_VERIFY,k;
    const char *path=q->args[10]==2?"/IROM/GXRCE0.DAT":"/IROM/GXRCE1.DAT";
    if(!s||q->args[2]!=1||q->args[5]!=1||q->args[9]!=5||
       (q->args[10]!=2&&q->args[10]!=3)||q->args[8]||s->selected_source!=RV_SOURCE_CARD)return RV_ARGUMENT;
    if(!(s->sd_id[0]|s->sd_id[1]|s->sd_id[2]|s->sd_id[3]))return RV_STALE;
    memcpy(e,r->epoch,48);memcpy(id,s->sd_id,16);
    if(!same(r,e,id))return RV_STALE;
    card=rv_native_open("/ATA1/GXRCE.DAT",0);installed=rv_native_open(path,0);
    if(card<0||installed<0)goto done;
    remaining=s->source_bytes;
    while(remaining) {
        n=remaining>sizeof(a)?sizeof(a):remaining;
        if(read_exact(card,a,n)||read_exact(installed,b,n)||!rv_equal(a,b,n))goto done;
        crc=rv_crc_update(crc,a,n);remaining-=n;
        if(!same(r,e,id)){result=RV_STALE;goto done;}
    }
    k=rv_native_read(card,a,1);if(k)goto done;k=rv_native_read(installed,b,1);if(k)goto done;
    if(~crc!=s->crc)goto done;
    result=RV_OK;
done:
    if(card>=0&&rv_native_close(card))result=RV_IO;
    if(installed>=0&&rv_native_close(installed))result=RV_IO;
    if(!same(r,e,id))return RV_STALE;
    if(result!=RV_OK)return result;
    reply->native_result=rv_native_rename("/ATA1/GXRCE.DAT","/ATA1/GXRCE.OK");
    if(reply->native_result){r->flags|=RF_UNCERTAIN;return RV_UNCERTAIN;}
    return same(r,e,id)?RV_OK:RV_STALE;
}
