/* Offline daily prototype. A data-only catalogue in a dedicated CPU lease. */
#include "fx_store.h"
#include <stddef.h>
extern uint32_t gxr2_crc32(const uint8_t *,size_t);
extern uint32_t gxr2_crc_zeroed(const uint8_t *,size_t,size_t,size_t);
extern int fx_io_live(void);
FxStore fx_store;
static uint32_t rd32(const uint8_t *p)
{return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
static int same_bytes(const void *a,const void *b,uint32_t n)
{const uint8_t *p=a,*q=b;while(n--)if(*p++!=*q++)return 0;return 1;}
static int stable(void)
{
    FxStamp now;uint8_t *p=(uint8_t *)&now;uint32_t i;
    for(i=0;i<sizeof(now);i++)p[i]=0;
    return fx_io_stamp(&now)==0&&same_bytes(&now,&fx_store.stamp,sizeof(now));
}
void fx_store_discard(int32_t why)
{fx_store.published=0;fx_store.pending=0;fx_store.status=why;}
uint32_t fx_store_catalog_bytes(void){return rd32(fx_store.header+40);}
int fx_store_live(void){return fx_store.published&&fx_io_live();}
uint8_t *fx_store_candidate(void)
{return fx_store.pending?fx_io_target(fx_store.stamp.region):0;}
const uint8_t *fx_store_data(void)
{return fx_store_live()?fx_io_target(fx_store.stamp.region):0;}
static int32_t exact(int32_t fd,uint8_t *p,uint32_t bytes)
{
    uint32_t n=0,want;int32_t k;
    while(n<bytes){
        if(!stable())return -5;
        want=bytes-n;if(want>65536)want=65536;
        if(want>fx_store.max_request)fx_store.max_request=want;
        k=fx_io_read(fd,p+n,want);
        if(k<=0||(uint32_t)k>want)return -1;
        n+=(uint32_t)k;fx_store.actual+=(uint32_t)k;
        if(!stable())return -5;
    }
    return 0;
}
int32_t fx_store_read(void)
{
    static const uint8_t magic[8]={'G','X','R','L','B','0','0','3'};
    uint32_t i,total,bytes,cat,count,tail,flags;int32_t fd=-1,result=-10,k;uint8_t extra,*target;
    uint8_t *all=(uint8_t *)&fx_store;
    for(i=0;i<sizeof(fx_store);++i)all[i]=0;
    fx_store.status=-10;
    result=fx_io_stamp(&fx_store.stamp);if(result)goto done;
    result=-10;
    if(fx_store.stamp.capacity!=65536||(fx_store.stamp.region&3u))goto done;
    fd=fx_io_open("/ATA1/GXRFX.BIN");if(fd<0){result=-2;goto done;}
    ++fx_store.opens;
    result=exact(fd,fx_store.header,64);if(result)goto done;
    total=rd32(fx_store.header+12);bytes=rd32(fx_store.header+16);
    cat=rd32(fx_store.header+40);count=rd32(fx_store.header+60);flags=rd32(fx_store.header+28);
    tail=count?30504u:0u;result=-10;
    if(!same_bytes(fx_store.header,magic,8)||fx_store.header[8]||fx_store.header[9]!=3||
       fx_store.header[10]||fx_store.header[11]!=64||total<64||bytes!=total-64||
       total>65528u||cat<256||cat>65528u-64u||cat&3u||count>1||bytes!=cat+tail||
       rd32(fx_store.header+24)!=7||(flags&~3u)||!(flags&1u)||(!count&&(flags&4u))||
       rd32(fx_store.header+32)!=gxr2_crc_zeroed(fx_store.header,64,32,4)||
       rd32(fx_store.header+36)!=178)goto done;
    if(count){
        if(rd32(fx_store.header+44)!=cat||rd32(fx_store.header+48)!=cat+1024u||
           rd32(fx_store.header+52)!=29478u||rd32(fx_store.header+56)!=2u)goto done;
    }else for(i=44;i<60;i+=4)if(rd32(fx_store.header+i))goto done;
    target=fx_io_target(fx_store.stamp.region);if(!target)goto done;
    fx_store.total=total;fx_store.payload_bytes=bytes;
    if(!stable()){result=-5;goto done;}
    fx_io_cache_prepare();
    result=exact(fd,target,bytes);if(result)goto done;
    k=fx_io_read(fd,&extra,1);if(k!=0){result=-1;goto done;}
    if(!stable()){result=-5;goto done;}
    result=gxr2_crc32(target,bytes)==rd32(fx_store.header+20)?0:-6;
    if(!result&&count)for(i=0;i<256;++i){uint32_t c=rd32(target+cat+4*i);if((c>>16)>15u||(c&65535u)>256u){result=-10;break;}}
done:
    if(fd>=0){++fx_store.closes;if(fx_io_close(fd))result=-1;}
    if(!result&&!stable())result=-5;
    if(!result&&fx_store.actual==fx_store.total)fx_store.pending=1;
    else fx_store_discard(result?result:-1);
    fx_store.status=result;return result;
}
int32_t fx_store_publish(void)
{
    if(!fx_store.pending||!stable()){fx_store_discard(-5);return -5;}
    __asm__ __volatile__("" ::: "memory");
    fx_store.published=1;fx_store.pending=0;fx_store.status=0;return 0;
}
