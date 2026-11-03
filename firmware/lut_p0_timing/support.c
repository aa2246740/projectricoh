#include "probe.h"
void pn_zero(void *p,uint32_t n){uint8_t *b=p;while(n--)*b++=0;}
void pn_copy(void *p,const void *q,uint32_t n){uint8_t *a=p;const uint8_t *b=q;while(n--)*a++=*b++;}
int pn_equal(const void *p,const void *q,uint32_t n){const uint8_t *a=p,*b=q;while(n--)if(*a++!=*b++)return 0;return 1;}
uint32_t gxr2_crc32(const uint8_t *p,size_t n){return ~gxr2_crc_add(~0u,p,(uint32_t)n);}
#ifndef RV_HOST
void *memcpy(void *p,const void *q,size_t n){pn_copy(p,q,(uint32_t)n);return p;}
void *memset(void *p,int v,size_t n){uint8_t *b=p;size_t i;for(i=0;i<n;++i)b[i]=(uint8_t)v;return p;}
#endif
