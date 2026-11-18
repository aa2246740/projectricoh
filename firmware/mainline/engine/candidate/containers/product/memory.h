#ifndef IG_MEMORY_H
#define IG_MEMORY_H
#include <stdint.h>
#include <stddef.h>
void ig_zero(void *,uint32_t);
void ig_copy(void *,const void *,uint32_t);
int ig_equal(const void *,const void *,uint32_t);
#endif
