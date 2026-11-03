#include "memory.h"
/* Shared implementations; the freestanding libc symbols live in eng_mem.c. */
void ig_zero(void *p,uint32_t n){uint8_t *a=p;while(n--)*a++=0;}
void ig_copy(void *p,const void *q,uint32_t n){uint8_t *a=p;const uint8_t *b=q;while(n--)*a++=*b++;}
int ig_equal(const void *p,const void *q,uint32_t n){const uint8_t *a=p,*b=q;while(n--)if(*a++!=*b++)return 0;return 1;}
