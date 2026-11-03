#ifndef RV_MIN_H
#define RV_MIN_H
#include <stdint.h>
#ifndef RV_PTR
#define RV_PTR(a) ((void *)(uintptr_t)(a))
#define RV_WORD(a) (*(volatile uint32_t *)RV_PTR(a))
#endif
#endif
