#ifndef GXR_RECIPE_V1_INTERNAL_H
#define GXR_RECIPE_V1_INTERNAL_H
#include "recipe_v1.h"

static inline uint32_t rv1_be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | p[3];
}
static inline void rv1_put32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}
static inline int rv1_equal(const uint8_t *a, const uint8_t *b, size_t n)
{
    size_t i;
    for (i = 0; i < n; ++i) {
        if (a[i] != b[i]) return 0;
    }
    return 1;
}
static inline int rv1_zero(const uint8_t *a, size_t n)
{
    size_t i;
    for (i = 0; i < n; ++i) {
        if (a[i] != 0) return 0;
    }
    return 1;
}
static inline void rv1_clear(uint8_t *a, size_t n)
{
    size_t i;
    for (i = 0; i < n; ++i) a[i] = 0;
}
#endif
