#include "records.h"
void *memcpy(void *d,const void *s,size_t size)
{uint8_t *a=d;const uint8_t *b=s;while(size--)*a++=*b++;return d;}
void *memset(void *d,int v,size_t size)
{uint8_t *a=d;while(size--)*a++=(uint8_t)v;return d;}
int rv_equal(const void *a,const void *b,uint32_t size)
{const uint8_t *x=a,*y=b;while(size--)if(*x++!=*y++)return 0;return 1;}
uint32_t rv_be32(const uint8_t *p){return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3];}
