#include "resident.h"
void rv_clear(void *p,uint32_t n) { uint8_t *b=p;while(n--) *b++=0; }
int rv_equal(const void *a,const void *b,uint32_t n)
{ const uint8_t *x=a,*y=b;while(n--) if(*x++!=*y++) return 0;return 1; }
void *memcpy(void *d,const void *s,size_t n)
{ uint8_t *x=d;const uint8_t *y=s;size_t i;for(i=0;i<n;++i)x[i]=y[i];return d; }
#ifndef RV_HOST
int32_t rv_invoke(uint32_t address,const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{ return ((RvEngineEntry)(uintptr_t)address)(api,context,q,p); }
#endif
void *memset(void *p,int value,size_t n)
{uint8_t *b=p;size_t i;for(i=0;i<n;++i)b[i]=(uint8_t)value;return p;}
