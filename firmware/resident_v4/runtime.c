#include "resident.h"
void rv4_clear(void *p,uint32_t n)
{ uint8_t *b=p; while(n--)*b++=0; }
int rv4_equal(const void *a,const void *b,uint32_t n)
{ const uint8_t *x=a,*y=b;while(n--)if(*x++!=*y++)return 0;return 1; }
void *memcpy(void *d,const void *s,size_t n)
{ uint8_t *x=d;const uint8_t *y=s;while(n--)*x++=*y++;return d; }
uint16_t rv4_be16(const uint8_t *p)
{ return (uint16_t)((uint16_t)p[0]<<8|p[1]); }
uint32_t rv4_be32(const uint8_t *p)
{ return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]; }
void rv4_put32(uint8_t *p,uint32_t x)
{p[0]=x>>24;p[1]=x>>16;p[2]=x>>8;p[3]=x;}
#ifndef RV4_HOST
int32_t rv4_invoke(uint32_t address,const Rv4HostApi *host,uint32_t token,const Rv4Event *event,Rv4Reply *reply)
{return ((int32_t (*)(const Rv4HostApi *,uint32_t,const Rv4Event *,Rv4Reply *))(uintptr_t)address)(host,token,event,reply);}
#endif
int rv4_span(uint32_t address,uint32_t bytes,uint32_t begin,uint32_t length)
{return bytes&&address>=begin&&address-begin<length&&bytes<=length-(address-begin);}
int rv4_allocation(uint32_t base,uint32_t bytes,uint32_t expected)
{
    uint32_t begin=RV4_WORD(RV4_HEAP_BEGIN),end=RV4_WORD(RV4_HEAP_END),n;
    if((base&3)||base<12||begin>=end||!bytes||
       !rv4_span(base-12,12,begin,end-begin)||!rv4_span(base,bytes,begin,end-begin))return 0;
    n=RV4_WORD(base-4);
    return !RV4_WORD(base-12)&&RV4_BYTE(base-8)==1&&n>=12&&bytes<=n-12&&
        n<RV4_WORD(RV4_ALLOC_LIMIT)&&rv4_span(base-12,n,begin,end-begin)&&(!expected||n==expected);
}
